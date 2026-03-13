#!/usr/bin/env python3
"""Streamlit application for generating Playwright tests from feature specifications."""

import re
import subprocess
from dataclasses import dataclass
from datetime import datetime

import streamlit as st

from src.file_utils import (  # noqa: F401 (save_generated_test used in generate flow)
    normalise_code_newlines,
    save_generated_test,
)
from src.llm_client import LLMClient  # noqa: F401
from src.page_context_scraper import scrape_page_context  # noqa: F401
from src.pytest_output_parser import RunResult, TestResult, parse_pytest_output
from src.report_utils import generate_html_report as generate_standalone_html  # noqa: F401
from src.report_utils import generate_jira_report, generate_local_report
from src.test_generator import TestGenerator

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
}


def init_session_state() -> None:
    """Initialize session state with defaults."""
    for key, value in _session_defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


@dataclass
class RequirementCoverage:
    """Track coverage for a single requirement."""

    id: str
    description: str
    status: str  # "not_covered", "covered", "partial"
    linked_tests: list  # List of test names that cover this requirement

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "description": self.description,
            "status": self.status,
            "linked_tests": self.linked_tests,
        }


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


def display_coverage(coverage_analysis: dict | None = None, run_result: RunResult | None = None) -> None:
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


def escape_html(text: str) -> str:
    """Escape HTML special characters."""
    return text.replace("&", "&").replace("<", "<").replace(">", ">").replace('"', "&quot;").replace("'", "&#39;")


def _build_report_dicts(
    coverage_analysis: dict | None,
    run_result: RunResult | None,
) -> list[dict]:
    """Convert RequirementCoverage + RunResult to the dict format used by report_utils."""
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
                match: TestResult | None = run_map.get(test_name)
                if match is not None:
                    status = match.status
                    duration = float(match.duration)
                    error_message = match.error_message or ""
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
    return """You are an expert Playwright automation engineer. Generate a complete, runnable Playwright test for the following user story and acceptance criteria.

USER STORY:
{user_story}

ACCEPTANCE CRITERIA (enumerate them explicitly - generate ONE test per criterion):
{criteria}
(Total: {count} criteria)

CRITICAL REQUIREMENT:
- YOU MUST generate a SEPARATE test function for EACH of the {count} acceptance criteria listed above
- Do NOT skip, combine, or omit any criteria
- Each test function should be named test_<criterion_number>_<short_desc> (e.g., test_01_can_enter_driver_name)
- The test function names must clearly correspond to the criterion number

BASE REQUIREMENTS:
- Use Python and Playwright sync API for web automation
- Use pytest format: def test_name(page: Page):
- Generate descriptive test names that reflect the criterion being tested
- Include comments explaining each step
- Include assertions to validate expected outcomes
- DO NOT use async/await or asyncio

IMPORTANT:
- Return ONLY the Python code, no markdown formatting, no explanations
- If PAGE CONTEXT is provided above, use ONLY the locators listed there
- Do not invent selectors that are not in the PAGE CONTEXT
- DO NOT skip the last criteria - all {count} criteria must have tests

Generate the Playwright test code now:"""


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
    base_url = st.text_input("Base URL", value="http://localhost:3000")

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
        if pasted.strip():
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

    # Sidebar extras
    st.sidebar.header("Test Execution Results")
    test_results_file = st.sidebar.file_uploader(
        "Upload Pytest Output (Optional, for advanced analysis)",
        type=["txt", "md"],
        key="test_output",
    )
    st.sidebar.file_uploader(
        "Upload Page Model YAML (Optional, for page object patterns)",
        type=["yaml", "yml"],
        key="page_model",
    )
    if test_results_file is not None:
        st.sidebar.markdown("#### Uploaded Test Results")
        test_content = test_results_file.read().decode("utf-8")
        st.sidebar.text_area("Pytest Output", test_content, height=300)

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
        prompt_template = """
### PAGE CONTEXT (If available):
{page_context}
### END PAGE CONTEXT

### GENERATION INSTRUCTIONS:
- If PAGE CONTEXT is provided above, use ONLY the locators listed there.
- Do not invent selectors not in the PAGE CONTEXT.

"""
        full_prompt = system_prompt + prompt_template

        with st.spinner("Generating Playwright tests..."):
            try:
                generator = TestGenerator(page_url=None)
                generated_code = normalise_code_newlines(generator.client.generate_test(full_prompt))

                if generated_code:
                    saved_path = save_generated_test(
                        test_code=generated_code,
                        story_text=user_story_text,
                        base_url=base_url,
                    )
                    st.session_state.generated_code = generated_code
                    st.session_state.saved_test_path = saved_path

                    test_names = re.findall(r"^def (test_\w+)", generated_code, re.MULTILINE)
                    requirements = []
                    for i, criterion in enumerate(acceptance_criteria_lines, 1):
                        req_id = f"TC-{i:03}"
                        num_str = f"{i:02}"
                        linked = [n for n in test_names if f"test_{num_str}_" in n or f"test_{i}_" in n]
                        if not linked:
                            words = set(criterion.lower().split())
                            linked = [n for n in test_names if len(words & set(n.lower().split("_"))) >= 2]
                        requirements.append(
                            RequirementCoverage(
                                id=req_id,
                                description=criterion,
                                status="covered" if linked else "not_covered",
                                linked_tests=linked,
                            )
                        )
                    st.session_state.coverage_analysis = {"requirements": requirements}

                    st.success(f"Tests Generated - saved to `{saved_path}`")

                    tab1, tab2 = st.tabs(["Test Code", "Coverage"])
                    with tab1:
                        st.code(generated_code, language="python")
                        st.download_button(
                            label="Download Test File",
                            data=generated_code,
                            file_name=f"test_{base_url.split(':')[1].replace('/', '_').strip('_')}.py",
                            mime="text/x-python",
                            key="dl_py",
                        )
                    with tab2:
                        display_coverage(
                            coverage_analysis=st.session_state.coverage_analysis,
                            run_result=st.session_state.last_run_result,
                        )
                else:
                    st.error("Failed to generate tests - the LLM returned an empty response.")

            except Exception as e:
                st.error(f"Error: {str(e)}")
                import traceback

                with st.expander("Full traceback"):
                    st.code(traceback.format_exc(), language="plaintext")

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
