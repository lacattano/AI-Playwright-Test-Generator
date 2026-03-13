#!/usr/bin/env python3
"""Streamlit application for generating Playwright tests from feature specifications."""

import html as _html
import re
import subprocess
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any

import streamlit as st

from src.file_utils import rename_test_file, save_generated_test

try:
    from src.file_utils import normalise_code_newlines as _normalise
except ImportError:

    def _normalise(code: str) -> str:  # type: ignore[misc]
        return code.replace("\r\n", "\n").replace("\r", "\n") if code else ""


from dotenv import load_dotenv

from src.coverage_utils import build_coverage_analysis
from src.llm_errors import LLMError, LLMErrorType, LLMResult
from src.page_context_scraper import scrape_page_context
from src.prompt_utils import get_streamlit_system_prompt_template
from src.pytest_output_parser import RunResult, TestResult, parse_pytest_output
from src.report_utils import generate_jira_report, generate_local_report
from src.test_generator import TestGenerator

load_dotenv()


# === Session State Defaults ===
_session_defaults = {
    "user_story": "",
    "acceptance_criteria": "",
    "criteria_count": 0,
    "generated_code": "",
    "saved_test_path": "",
    "last_run_success": False,
    "last_run_output": "",
    "last_run_result": None,
    "coverage_analysis": {},
    "page_context": None,
    "selected_model": "llama3.2",
    "confirmed_paste": "",
}


def init_session_state() -> None:
    """Initialize session state with defaults."""
    for key, value in _session_defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def display_run_button() -> None:
    """Display the test run button and show structured results."""

    st.markdown("#### 🏃 Run Tests")
    saved_path: str = st.session_state.get("saved_test_path", "")

    run_now = st.button("▶️ Run Now", type="primary", key="run_btn")

    if run_now and saved_path:
        with st.spinner("⏳ Running tests..."):
            try:
                result = subprocess.run(
                    ["pytest", saved_path, "-v", "--tb=short"],
                    capture_output=True,
                    text=True,
                    timeout=300,
                )
                raw_output = result.stdout + result.stderr
                parsed_result = parse_pytest_output(raw_output)
                st.session_state.last_run_success = result.returncode == 0
                st.session_state.last_run_output = raw_output
                st.session_state.last_run_result = parsed_result
            except subprocess.TimeoutExpired:
                st.error("❌ Test run timed out after 5 minutes")
                st.session_state.last_run_result = None
            except Exception as e:
                st.error(f"❌ Error running tests: {str(e)}")
                st.session_state.last_run_result = None
    elif run_now and not saved_path:
        st.warning("⚠️ No test file saved yet - generate tests first.")

    # Display results
    if st.session_state.last_run_result is not None:
        run_result = st.session_state.last_run_result

        # Summary line with icon
        if run_result.failed == 0 and run_result.errors == 0:
            st.success(f"✅ All {run_result.passed} tests passed in {run_result.duration:.1f}s")
        else:
            st.error(
                f"❌ {run_result.failed} failed - "
                f"{run_result.passed} passed, {run_result.failed} failed in {run_result.duration:.1f}s"
            )

        # Results table in main panel
        if run_result.results:
            rows = []
            for r in run_result.results:
                icon = "✅ Pass" if r.status == "passed" else "❌ Fail"
                duration = f"{r.duration:.1f}s" if r.duration > 0 else "-"
                rows.append({"Test": r.name, "Result": icon, "Duration": duration})

            st.dataframe(rows, use_container_width=True, hide_index=True)

        # Inline failure details
        for r in run_result.results:
            if r.status == "failed" and r.error_message:
                st.warning(f"⚠️ **{r.name}**\n\n`{r.error_message}`")

        # Raw output expander - expanded only on failure
        with st.expander("📄 Raw Output", expanded=run_result.failed > 0):
            st.code(run_result.raw_output, language="plaintext")


def display_coverage(coverage_analysis: dict[str, Any] | None = None, run_result: RunResult | None = None) -> None:
    """Display the coverage analysis table with optional test results integration."""

    if coverage_analysis is None or not coverage_analysis.get("requirements"):
        st.warning("📋 No coverage analysis available. Generate tests first.")
        return

    requirements = coverage_analysis.get("requirements", [])

    # Create rows for dataframe
    rows = []
    for req in requirements:
        status_emoji = "✅" if req.status == "covered" else ("⚠️" if req.status == "partial" else "❌")

        # Add Result column when run results are available
        result_cell = ""
        if run_result is not None:
            # Look up test status for each linked test
            test_statuses = []
            for test_name in req.linked_tests:
                # Find matching test in run results
                for tr in run_result.results:
                    if tr.name == test_name or test_name.startswith(tr.name):
                        icon = "✅" if tr.status == "passed" else "❌"
                        test_statuses.append(icon)
                        break
                else:
                    test_statuses.append("⏳")  # Not in recent run

            result_cell = ", ".join(test_statuses)

        rows.append(
            {
                "ID": f"{status_emoji} {req.id}",
                "Requirement": req.description,
                "Status": req.status.upper(),
                "Tests": "; ".join(req.linked_tests[:3]) + ("..." if len(req.linked_tests) > 3 else ""),
                "Result": result_cell,
            }
        )

    # Show dataframe with formatted columns
    cols = ["ID", "Requirement", "Status"]
    if run_result:
        cols.append("Result")
    cols.extend(["Tests"])

    st.dataframe(
        rows,
        column_config={
            "ID": "ID",
            "Requirement": "Requirement",
            "Status": st.column_config.SelectboxColumn(
                "Status",
                options=["COVERED", "PARTIAL", "NOT_COVERED"],
            ),
            "Result": "Run Status" if run_result else None,
            "Tests": "Linked Tests",
        },
        use_container_width=True,
        hide_index=True,
    )

    # Show error details for failed tests when results are available
    if run_result is not None:
        for result in run_result.results:
            if result.status == "failed" and result.error_message:
                st.warning(f"⚠️ **{result.name}**\n\n`{result.error_message}`")


def _generate_html_report(coverage_analysis: dict | None = None, run_result: RunResult | None = None) -> str:
    """Generate an HTML report with coverage analysis and optional test results."""
    html_parts: list[str] = []
    html_parts.append("""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI Test Generator - Report</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; margin: 40px; background: #f5f5f5; }
        .container { max-width: 1200px; margin: 0 auto; background: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        h1 { color: #1a73e8; border-bottom: 2px solid #1a73e8; padding-bottom: 10px; }
        h2 { color: #333; margin-top: 30px; }
        table { width: 100%; border-collapse: collapse; margin: 15px 0; }
        th, td { padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }
        th { background: #f8f9fa; font-weight: 600; }
        tr:hover { background: #f5f5f5; }
        .pass { color: #2e7d32; font-weight: bold; }
        .fail { color: #c62828; font-weight: bold; }
        .pending { color: #e65100; }
        .summary { background: #e3f2fd; padding: 15px; border-radius: 4px; margin: 20px 0; }
        .timestamp { color: #666; font-size: 0.9em; }
        .coverage-status-COVERED { color: #2e7d32; }
        .coverage-status-PARTIAL { color: #e65100; }
        .coverage-status-NOT_COVERED { color: #c62828; }
    </style>
</head>
<body>
    <div class="container">""")

    html_parts.append(
        f'<h1>🤖 AI Test Generator Report</h1>\n<p class="timestamp">Generated at {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>'
    )

    # Run Results section when available
    if run_result is not None:
        html_parts.append("")
        html_parts.append("<h2>🏃 Test Run Results</h2>")

        status_text = "All tests passed" if run_result.failed == 0 else f"{run_result.failed} test(s) failed"
        html_parts.append(
            f'<p class="summary">{status_text} - {run_result.passed} passed, {run_result.failed} failed in {run_result.duration:.1f}s</p>'
        )

        html_parts.append("<table><thead><tr><th>Test</th><th>Result</th><th>Duration</th></tr></thead><tbody>")
        for r in run_result.results:
            result_class = "pass" if r.status == "passed" else "fail"
            icon = "✅ Pass" if r.status == "passed" else "❌ Fail"
            duration = f"{r.duration:.1f}s" if r.duration > 0 else "-"
            html_parts.append(
                f'<tr><td>{escape_html(r.name)}</td><td class="{result_class}">{icon}</td><td>{duration}</td></tr>'
            )
        html_parts.append("</tbody></table>")

    # Coverage section
    if coverage_analysis and coverage_analysis.get("requirements"):
        html_parts.append("<h2>📊 Coverage Analysis</h2>")

        requirements = coverage_analysis["requirements"]
        covered = sum(1 for r in requirements if r.status == "covered")
        total = len(requirements)

        html_parts.append(
            f'<p class="summary">{covered} of {total} requirements have corresponding test coverage ({(covered / total * 100):.1f}%)</p>'
        )

        html_parts.append(
            "<table><thead><tr><th>ID</th><th>Requirement</th><th>Status</th><th>Linked Tests</th></tr></thead><tbody>"
        )
        for req in requirements:
            status_class = f"coverage-status-{req.status.upper()}"
            tests_html = ", ".join(f'<span class="pending">{t}</span>' for t in req.linked_tests[:5])
            html_parts.append(
                f'<tr><td>{req.id}</td><td>{escape_html(req.description)}</td><td class="{status_class}">{req.status.upper()}</td><td>{tests_html}</td></tr>'
            )
        html_parts.append("</tbody></table>")

    html_parts.append("</div></body>\n</html>")

    return "\n".join(html_parts)


def _get_ollama_models() -> list[str]:
    """Return list of locally available Ollama models by running 'ollama list'."""
    try:
        result = subprocess.run(
            ["ollama", "list"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        lines = result.stdout.strip().splitlines()
        # First line is header ("NAME  ID  SIZE  MODIFIED"), skip it
        models = [line.split()[0] for line in lines[1:] if line.strip()]
        return models if models else ["llama3.2"]
    except Exception:
        return ["llama3.2"]


def escape_html(text: str) -> str:
    """Escape HTML special characters."""
    return _html.escape(text, quote=True)


def _build_report_dicts(
    coverage_analysis: dict | None,
    run_result: RunResult | None,
) -> list[dict]:
    """Convert RequirementCoverage + RunResult to the dict format used by report_utils.

    Args:
        coverage_analysis: dict with "requirements" key containing RequirementCoverage list
        run_result: RunResult from pytest parser, or None

    Returns:
        list of dicts with keys: test_name, status, duration, screenshots, error_message
    """
    rows: list[dict] = []

    requirements = (coverage_analysis or {}).get("requirements", [])
    run_map: dict[str, TestResult] = {}
    if run_result:
        for tr in run_result.results:
            run_map[tr.name] = tr

    for req in requirements:
        linked: list[str] = getattr(req, "linked_tests", []) or []
        status = "unknown"
        duration = 0.0
        error_message = ""

        if linked and run_result:
            for test_name in linked:
                found = run_map.get(test_name)
                if found is not None:
                    status = found.status
                    duration = float(found.duration)
                    error_message = found.error_message or ""
                    break
        elif req.status in ("covered", "not_covered", "partial"):
            status = "pending"

        rows.append(
            {
                "test_name": f"{req.id}: {req.description[:80]}",
                "status": status,
                "duration": duration,
                "screenshots": [],
                "error_message": error_message,
            }
        )

    return rows


def get_system_prompt() -> str:
    """Return the system prompt template for test generation."""
    return get_streamlit_system_prompt_template()


def parse_feature_text(content: str) -> tuple[list[str], list[str]]:
    """
    Parse a feature specification string into user story lines and
    acceptance criteria lines.

    Handles:
    - Structured markdown with ## headings
    - Plain text with no headings (whole block treated as story)
    - Mixed/informal input

    Returns:
        Tuple of (user_story_lines, acceptance_criteria_lines)
    """
    lines = content.split("\n")
    user_story: list[str] = []
    acceptance_criteria_lines: list[str] = []
    in_story_section = False
    in_criteria_section = False

    for line in lines:
        stripped = line.strip()
        stripped_lower = stripped.lower()

        # Detect section headings — handle ##, #, plain text variants
        # Check BEFORE skipping # lines so "## User Story" is caught
        if "user story" in stripped_lower:
            in_story_section = True
            in_criteria_section = False
            continue

        if "acceptance criteria" in stripped_lower:
            in_criteria_section = True
            in_story_section = False
            continue

        # Skip empty lines and markdown dividers
        if not stripped or stripped.startswith("---"):
            continue

        if in_story_section:
            # Skip lines that are just heading markers
            if not stripped.startswith("#"):
                user_story.append(stripped)
        elif in_criteria_section:
            # Strip leading bullet/number markers for cleaner criteria text
            clean = stripped.lstrip("-•*").strip()
            clean = re.sub(r"^\d+[.)]\s*", "", clean)
            if clean:
                acceptance_criteria_lines.append(clean)

    # Fallback: no headings found — treat everything as the user story
    if not user_story and not acceptance_criteria_lines:
        user_story = [line.strip() for line in lines if line.strip() and not line.strip().startswith("---")]

    return user_story, acceptance_criteria_lines


def main() -> None:
    """Main function to run the Streamlit application."""
    st.set_page_config(page_title="AI Test Generator", page_icon="🤖", layout="wide")

    st.title("🤖 AI-Powered Playwright Test Generator")
    st.markdown("---")

    # ── Input: file upload or paste ──────────────────────────────────────────
    base_url = st.text_input(
        "Base URL",
        value="https://",
        help="Full URL including https:// — used for page scraping and test navigation",
    )

    # ── Sidebar — always visible ──────────────────────────────────────────────
    st.sidebar.header("⚙️ Settings")
    available_models = _get_ollama_models()
    selected_model = st.sidebar.selectbox(
        "LLM Model",
        options=available_models,
        index=0,
        help="Local Ollama models available on your machine. Run 'ollama list' to see all.",
    )
    st.session_state.selected_model = selected_model

    tab_file, tab_text = st.tabs(["📄 Upload .md file", "✏️ Paste story"])

    content: str = ""

    with tab_file:
        feature_spec_file = st.file_uploader(
            "Upload Feature Specification (MD)",
            type=["md"],
            key="file_upload",
        )
        if feature_spec_file is not None:
            content = feature_spec_file.read().decode("utf-8")
            with st.expander("📋 Preview uploaded file", expanded=False):
                st.markdown(content)

    with tab_text:
        pasted = st.text_area(
            "Paste your user story and acceptance criteria",
            height=300,
            placeholder=(
                "## User Story\n"
                "As a user I want to log in so that I can access my account.\n\n"
                "## Acceptance Criteria\n"
                "- Login form is displayed\n"
                "- User can enter username and password\n"
                "- Clicking LOGIN redirects to the inventory page"
            ),
            key="pasted_text",
        )
        if st.session_state.get("confirmed_paste", "").strip():
            content = st.session_state.confirmed_paste
            st.success("✅ Story loaded — click **Generate Tests** below.")
        elif pasted.strip():
            content = pasted

    if not content:
        st.info("👆 Upload a feature specification file or paste a user story to begin.")
        return

    # ── Parse content (shared path for both inputs) ───────────────────────────
    user_story, acceptance_criteria_lines = parse_feature_text(content)

    if not user_story:
        st.error("Couldn't find a user story. Add a '## User Story' heading or just type your story directly.")
        return

    if not acceptance_criteria_lines:
        st.info(
            "No '## Acceptance Criteria' section found - the AI will generate tests "
            "from your story directly. For more precise control, add an "
            "**## Acceptance Criteria** section with one criterion per line."
        )
        acceptance_criteria_lines = user_story

    user_story_text = "\n".join(user_story)
    acceptance_criteria_text = "\n".join(acceptance_criteria_lines)
    criteria_count = len(acceptance_criteria_lines)
    st.sidebar.markdown(f"**Criteria Count**: {criteria_count}")

    if st.button("Generate Tests", type="primary"):
        st.session_state.last_run_result = None
        st.session_state.last_run_success = False
        st.session_state.last_run_output = ""
        st.session_state.coverage_analysis = {}

        system_prompt = get_system_prompt().format(
            user_story=user_story_text,
            criteria=acceptance_criteria_text,
            count=criteria_count,
        )

        # R-004: normalise URL and scrape page context
        scrape_url = base_url.strip()
        if scrape_url and not scrape_url.startswith(("http://", "https://")):
            scrape_url = "https://" + scrape_url

        page_context_block = ""
        with st.spinner("🔍 Scraping page context from URL..."):
            try:
                ctx, scrape_err = scrape_page_context(scrape_url)
                if ctx:
                    page_context_block = ctx.to_prompt_block()
                    st.sidebar.success(f"✅ Scraped {ctx.element_count()} elements from page")
                elif scrape_err:
                    st.sidebar.warning(f"⚠️ Scraper: {scrape_err[:120]}")
            except Exception as e:
                st.sidebar.warning(f"⚠️ Scraper failed: {e} — generating without page context")

        prompt_template = f"""
### PAGE CONTEXT (If available):
{page_context_block}
### END PAGE CONTEXT

### GENERATION INSTRUCTIONS:
- If PAGE CONTEXT is provided above, use ONLY the locators listed there.
- Do not invent selectors not in the PAGE CONTEXT.

"""
        full_prompt = system_prompt + prompt_template

        with st.spinner("Generating Playwright tests..."):
            try:
                model = st.session_state.get("selected_model", "llama3.2")
                generator = TestGenerator(page_url=None, model_name=model)
                raw_response = generator.client.generate_test(full_prompt)
                generated_code = _normalise(raw_response)

                llm_result = (
                    LLMResult(code=generated_code)
                    if generated_code
                    else LLMResult(
                        code=None,
                        error=LLMError(
                            error_type=LLMErrorType.EMPTY_RESPONSE,
                            message="The LLM returned an empty response. "
                            "Check that Ollama is running and OLLAMA_TIMEOUT is high enough (recommended: 300).",
                        ),
                    )
                )

                if llm_result.code:
                    saved_path = save_generated_test(
                        test_code=llm_result.code,
                        story_text=user_story_text,
                        base_url=base_url,
                    )
                    st.session_state.generated_code = llm_result.code
                    st.session_state.saved_test_path = saved_path

                    st.session_state.coverage_analysis = build_coverage_analysis(
                        acceptance_criteria_lines=acceptance_criteria_lines,
                        generated_code=llm_result.code,
                    )

                    st.success(f"Tests Generated - saved to `{saved_path}`")

                    # R-006: rename test file
                    with st.expander("✏️ Rename test file"):
                        new_name = st.text_input(
                            "New filename (without .py)",
                            value=Path(saved_path).stem,
                            key="rename_input",
                        )
                        if st.button("Rename", key="rename_btn"):
                            try:
                                new_path = rename_test_file(saved_path, new_name)
                                st.session_state.saved_test_path = new_path
                                st.success(f"Renamed to `{new_path}`")
                            except Exception as rename_err:
                                st.error(f"Rename failed: {rename_err}")

                else:
                    message = (
                        llm_result.error.message
                        if llm_result.error is not None
                        else "Failed to generate tests due to an unknown LLM error."
                    )
                    st.error(f"❌ {message}")
                    with st.expander("🔍 Debug info"):
                        st.write(f"**Model:** {model}")
                        st.write(f"**Raw response type:** {type(raw_response)}")
                        st.write(f"**Raw response value:** `{repr(raw_response)[:500]}`")
                        st.write(f"**Prompt length:** {len(full_prompt)} chars")

            except Exception as e:
                st.error(f"Error: {str(e)}")
                with st.expander("Full traceback"):
                    st.code(traceback.format_exc(), language="plaintext")

    # ── Always render generated code + coverage from session state ────────────
    if st.session_state.get("generated_code") and st.session_state.get("saved_test_path"):
        tab1, tab2 = st.tabs(["📝 Test Code", "📊 Coverage"])
        with tab1:
            st.code(st.session_state.generated_code, language="python")
            url_slug = re.sub(r"[^\w]", "_", base_url).strip("_")
            st.download_button(
                label="⬇️ Download Test File",
                data=st.session_state.generated_code,
                file_name=f"test_{url_slug}.py",
                mime="text/x-python",
                key="dl_py",
            )
        with tab2:
            display_coverage(
                coverage_analysis=st.session_state.coverage_analysis,
                run_result=st.session_state.last_run_result,
            )

    if st.session_state.get("saved_test_path"):
        st.markdown("---")
        display_run_button()

        if st.session_state.last_run_result and st.session_state.coverage_analysis:
            st.markdown("### Coverage x Run Results")
            display_coverage(
                coverage_analysis=st.session_state.coverage_analysis,
                run_result=st.session_state.last_run_result,
            )

        if st.session_state.coverage_analysis or st.session_state.last_run_result:
            report_dicts = _build_report_dicts(
                coverage_analysis=st.session_state.coverage_analysis or None,
                run_result=st.session_state.last_run_result,
            )
            html_report = _generate_html_report(
                coverage_analysis=st.session_state.coverage_analysis or None,
                run_result=st.session_state.last_run_result,
            )
            local_md = generate_local_report(report_dicts)
            jira_md = generate_jira_report(report_dicts)

            st.markdown("#### 📥 Download Reports")
            col_a, col_b, col_c = st.columns(3)
            with col_a:
                st.download_button(
                    label="📄 local.md",
                    data=local_md,
                    file_name="report_local.md",
                    mime="text/markdown",
                    key="dl_local",
                    use_container_width=True,
                )
            with col_b:
                st.download_button(
                    label="🎫 jira.md",
                    data=jira_md,
                    file_name="report_jira.md",
                    mime="text/markdown",
                    key="dl_jira",
                    use_container_width=True,
                )
            with col_c:
                st.download_button(
                    label="🌐 standalone.html",
                    data=html_report,
                    file_name="test_report.html",
                    mime="text/html",
                    key="dl_html",
                    use_container_width=True,
                )


if __name__ == "__main__":
    main()
