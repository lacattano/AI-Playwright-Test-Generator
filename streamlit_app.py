#!/usr/bin/env python3
"""Streamlit application for generating Playwright tests from feature specifications."""

import re
import subprocess
import traceback
from pathlib import Path
from typing import Any

import streamlit as st

from src.code_validator import (
    validate_python_syntax as _validate_python_syntax,
)
from src.code_validator import (
    validate_test_function as _validate_test_function,
)
from src.file_utils import rename_test_file
from src.user_story_parser import FeatureParser

try:
    from src.file_utils import normalise_code_newlines as _normalise
except ImportError:

    def _normalise(code: str) -> str:  # type: ignore[misc]
        return code.replace("\r\n", "\n").replace("\r", "\n") if code else ""


from dotenv import load_dotenv

from src.coverage_utils import build_coverage_analysis
from src.page_context_scraper import scrape_multiple_pages, scrape_page_context
from src.prompt_utils import get_streamlit_system_prompt_template
from src.pytest_output_parser import RunResult, parse_pytest_output
from src.report_utils import (
    build_report_dicts,
    generate_html_report,
    generate_jira_report,
    generate_local_report,
)
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
                    # Match: tr.name equals or starts with test_name pattern
                    if tr.name == test_name or tr.name.startswith(test_name):
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


def get_system_prompt() -> str:
    """Return the system prompt template for test generation."""
    return get_streamlit_system_prompt_template()


def parse_feature_text(content: str) -> tuple[str, str, int, str | None]:
    """
    Parse a feature specification string into user story and acceptance criteria.

    Uses FeatureParser to extract and structure the feature specification.

    Args:
        content: Raw feature specification text

    Returns:
        Tuple of (user_story_text, acceptance_criteria_text, criteria_count, error_message)
    """
    parser = FeatureParser()
    result = parser.parse(content)

    if not result.success:
        return "", "", 0, result.error_message

    if result.specification is None:
        return "", "", 0, "Parse failed"

    return (
        result.specification.user_story,
        "\n".join(result.specification.acceptance_criteria),
        result.specification.criteria_count,
        None,
    )


def main() -> None:
    """Main function to run the Streamlit application."""
    st.set_page_config(page_title="AI Test Generator", page_icon="🤖", layout="wide")
    init_session_state()

    st.title("🤖 AI-Powered Playwright Test Generator")
    st.markdown("---")

    # ── Input: file upload or paste ──────────────────────────────────────────
    base_url = st.text_input(
        "Base URL",
        value="https://",
        help="Full URL including https:// — used for page scraping and test navigation",
    )

    # ── AI-009: Additional page URLs for multi-page scraping ──────────────────
    with st.expander("➕ Add more pages to scrape (optional)", expanded=False):
        additional_urls_raw = st.text_area(
            "Additional page URLs (one per line)",
            placeholder=(
                "https://www.example.com/inventory.html\n"
                "https://www.example.com/cart.html\n"
                "https://www.example.com/checkout.html"
            ),
            height=100,
            key="additional_urls",
            help="Enter one URL per line. The scraper will visit each page and collect elements for the LLM.",
        )
    additional_urls: list[str] = [
        u.strip() for u in additional_urls_raw.splitlines() if u.strip().startswith(("http://", "https://"))
    ]

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
    user_story_text, acceptance_criteria_text, criteria_count, error = parse_feature_text(content)

    if error:
        st.error(f"Failed to parse input: {error}")
        return

    if not user_story_text:
        st.error("Couldn't find a user story. Add a '## User Story' heading or just type your story directly.")
        return

    if not acceptance_criteria_text:
        st.info(
            "No '## Acceptance Criteria' section found - the AI will generate tests "
            "from your story directly. For more precise control, add an "
            "**## Acceptance Criteria** section with one criterion per line."
        )
        acceptance_criteria_text = user_story_text
        criteria_count = 1

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
        if additional_urls:
            # AI-009: Multi-page scraping
            total_pages = 1 + len(additional_urls)
            with st.spinner(f"🔍 Scraping {total_pages} pages..."):
                try:
                    multi_ctx, scraper_state = scrape_multiple_pages(
                        base_url=scrape_url,
                        additional_urls=additional_urls,
                    )
                    if not multi_ctx.is_empty:
                        page_context_block = multi_ctx.to_prompt_block()
                        st.sidebar.success(
                            f"✅ Scraped {multi_ctx.success_count}/{total_pages} pages "
                            f"— {multi_ctx.total_elements} elements total"
                        )
                        for pg in multi_ctx.pages:
                            st.sidebar.caption(f"  • {pg.url} → {pg.element_count()} elements")
                        # DEBUG: Log page context content
                        st.sidebar.info(f"🔍 Page Context (first 200 chars):\n{page_context_block[:200]}...")
                    if scraper_state.failed_urls:
                        st.sidebar.warning(f"⚠️ Failed to scrape: {', '.join(scraper_state.failed_urls)}")
                    if multi_ctx.is_empty:
                        st.sidebar.warning("⚠️ All pages failed — generating without page context")
                except Exception as e:
                    st.sidebar.warning(f"⚠️ Multi-page scraper failed: {e} — generating without page context")
        else:
            # Single-page scraping (original behaviour)
            with st.spinner("🔍 Scraping page context from URL..."):
                try:
                    ctx, scrape_err = scrape_page_context(scrape_url)
                    if ctx:
                        page_context_block = ctx.to_prompt_block()
                        st.sidebar.success(f"✅ Scraped {ctx.element_count()} elements from page")
                        # DEBUG: Log page context content
                        st.sidebar.info(f"🔍 Page Context (first 200 chars):\n{page_context_block[:200]}...")
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
- Do NOT invent selectors not in the PAGE CONTEXT.
- For assertions after navigation, use `expect(page).to_have_url()` or `expect(page).to_have_title()` instead of making up element IDs like `#react-basics`.

"""
        full_prompt = system_prompt + prompt_template
        # DEBUG: Log prompt being sent to LLM
        st.sidebar.info(f"🔍 Full prompt length: {len(full_prompt)} chars")
        if page_context_block:
            st.sidebar.info(f"🔍 Prompt includes page context: True ({len(page_context_block)} chars)")
        else:
            st.sidebar.warning("⚠️ Prompt has NO page context - LLM will invent selectors")

        with st.spinner("Generating Playwright tests..."):
            try:
                model = st.session_state.get("selected_model", "llama3.2")
                generator = TestGenerator(page_url=None, model_name=model)
                saved_path = generator.generate_and_save(full_prompt)

                # Read the generated code from the saved file
                with open(saved_path, encoding="utf-8") as f:
                    normalised_code = f.read()

                # Normalise code newlines
                normalised_code = _normalise(normalised_code)

                # Validate Python syntax
                syntax_error = _validate_python_syntax(normalised_code)
                if syntax_error:
                    st.error("❌ Generated code failed Python syntax validation")
                    st.code(f"Line {syntax_error}: Syntax error detected")
                    return

                # B-009: Validate test function format (no async def)
                test_error = _validate_test_function(normalised_code)
                if test_error:
                    st.error(f"❌ Generated code failed test validation: {test_error}")
                    st.code(normalised_code, language="python")
                    return

                st.session_state.saved_test_path = saved_path
                st.session_state.generated_code = normalised_code

                # Build coverage analysis
                st.session_state.coverage_analysis = build_coverage_analysis(
                    acceptance_criteria_lines=acceptance_criteria_text.split("\n"),
                    generated_code=normalised_code,
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
            report_dicts = build_report_dicts(
                coverage_analysis=st.session_state.coverage_analysis or None,
                run_result=st.session_state.last_run_result,
            )
            html_report = generate_html_report(report_dicts)
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
