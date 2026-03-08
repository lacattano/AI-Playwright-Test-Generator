"""
streamlit_app.py — AI Playwright Test Generator UI
A clean, terminal-inspired interface for non-technical QA testers.
"""

import os
import re
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import streamlit as st
from dotenv import load_dotenv

from src.file_utils import normalise_code_newlines, rename_test_file, save_generated_test
from src.llm_client import LLMClient
from src.page_context_scraper import PageContext, scrape_page_context

# Load environment variables with explicit path so it works regardless of cwd
load_dotenv(dotenv_path=Path(__file__).parent / ".env")


# ── Phase B: Dataclasses for Coverage Analysis ────────────────────────────────
@dataclass
class TestFunction:
    """Represents a single test function in the generated test file."""

    name: str
    docstring: str
    line_start: int
    line_end: int

    @property
    def description(self) -> str:
        """Return test description from docstring."""
        desc = self.docstring.strip().strip('"')
        return re.sub(r"^\d+: ", "", desc)  # Remove criterion number prefix


@dataclass
class RequirementCoverage:
    """Coverage status for a single requirement/criterion."""

    requirement_id: str
    text: str
    linked_tests: list[TestFunction] = field(default_factory=list)
    status: str = "pending"  # pending, covered, failed
    confidence: float = 0.0  # 0.0 to 1.0


# ── Phase B: Coverage Analysis Helper Functions ─────────────────────────────
def parse_test_file(test_code: str, user_story: str) -> tuple[list[TestFunction], list[str]]:
    """
    Parse a generated test file and extract test functions.
    Also extracts criteria from the user story.

    Args:
        test_code: Python test code as a string
        user_story: Original user story text

    Returns:
        Tuple of (list of TestFunction, list of criteria strings)
    """
    test_functions = parse_test_functions(test_code)
    criteria = extract_criteria_from_user_story(user_story)
    return test_functions, criteria


def parse_test_functions(test_code: str) -> list[TestFunction]:
    """
    Parse a generated test file and extract test functions.

    Args:
        test_code: Python test code as a string

    Returns:
        List of TestFunction dataclass instances
    """
    test_functions: list[TestFunction] = []
    lines = test_code.splitlines()
    current_test: TestFunction | None = None
    docstring_lines: list[str] = []
    in_docstring = False

    for i, line in enumerate(lines, 1):
        stripped = line.strip()

        # Detect test function definition
        if stripped.startswith("def test_") and "(" in stripped:
            # Save previous test function if exists
            if current_test is not None:
                current_test.line_end = i - 1
                test_functions.append(current_test)

            # Start new test function
            current_test = TestFunction(
                name=stripped.split("(")[0].strip().rstrip(":") if ":" in stripped else stripped.split("(")[0].strip(),
                docstring="",
                line_start=i,
                line_end=i,
            )
            in_docstring = False
            docstring_lines = []
        elif current_test is not None and not in_docstring:
            # Check for docstring start (triple quotes)
            if '"""' in stripped or "'''" in stripped:
                in_docstring = True
                quote = '"""' if '"""' in stripped else "'''"
                parts = stripped.split(quote)
                if len(parts) >= 2 and parts[0].strip().startswith(quote):
                    # Single-line docstring: def test_(): "doc"
                    docstring_text = parts[1].strip()
                    current_test.docstring = docstring_text
                    current_test.line_end = i
                    test_functions.append(current_test)
                    current_test = None
                elif len(parts) >= 1:
                    # Multi-line docstring start
                    docstring_lines.append(stripped.split(quote, 1)[1] if ":" not in stripped else "")
                    in_docstring = True
        elif current_test is not None and in_docstring:
            if '"""' in stripped or "'''" in stripped:
                # End of docstring
                quote = '"""' if '"""' in stripped else "'''"
                docstring_lines.append(stripped.split(quote)[0].strip())
                current_test.docstring = "\n".join(docstring_lines)
                current_test.line_end = i
                test_functions.append(current_test)
                current_test = None
                in_docstring = False
            else:
                docstring_lines.append(stripped)

        # If still collecting docstring at end of file
        if current_test is not None and in_docstring and i == len(lines):
            current_test.line_end = i
            current_test.docstring = "\n".join(docstring_lines)
            test_functions.append(current_test)

    # Handle case where test function was just defined
    if current_test is not None and not in_docstring:
        current_test.line_end = len(lines)
        test_functions.append(current_test)

    return test_functions


def extract_criteria_from_user_story(user_story: str) -> list[str]:
    """
    Extract acceptance criteria from user story text.
    Returns list of criterion strings.
    """
    criteria = []
    lines = user_story.splitlines()

    bullet_re = re.compile(r"^\s*[-•*]\s+(.+)")
    numbered_re = re.compile(r"^\s*\d+[.)]\s+(.+)")
    gherkin_re = re.compile(r"^\s*(given|when|then|and)\s+(.+)", re.I)
    should_re = re.compile(r".*(should|must|shall|can|verify|confirm|ensure)\s+(.+)", re.I)

    for line in lines:
        line_stripped = line.strip()
        if not line_stripped:
            continue

        # Match bullet points or numbered items
        for pattern in [bullet_re, numbered_re]:
            match = pattern.match(line_stripped)
            if match and match.lastindex is not None:
                last_idx = int(match.lastindex)
                criteria.append(match.group(last_idx).strip())
                break
        else:
            # Match Gherkin syntax
            gherkin_match = gherkin_re.match(line_stripped)
            if gherkin_match:
                # Use the 'when' or 'then' part as the criterion
                for idx in [2, 3]:  # 'when' or 'then' groups
                    if (
                        gherkin_match.lastindex is not None
                        and int(gherkin_match.lastindex) >= idx
                        and gherkin_match.group(idx)
                    ):
                        val = str(gherkin_match.group(idx)).strip()
                        criteria.append(val)
                        break
            # Match "should/must" pattern
            elif should_re.match(line_stripped):
                match = should_re.match(line_stripped)
                if match and match.lastindex is not None and int(match.lastindex) >= 2:
                    val = str(match.group(2)).strip()
                    criteria.append(val)
                else:
                    criteria.append(line_stripped)

    return criteria if criteria else [str(user_story).strip()[:120]]


def map_tests_to_criteria(
    test_functions: list[TestFunction],
    criteria: list[str],
) -> list[RequirementCoverage]:
    """
    Map test functions to acceptance criteria from user story.

    Args:
        test_functions: List of parsed test functions
        criteria: List of criterion text strings

    Returns:
        List of RequirementCoverage objects with test mappings
    """
    coverage: list[RequirementCoverage] = []

    for i, criterion_text in enumerate(criteria, 1):
        req_id = f"TC-{i:03}"
        linked_tests: list[TestFunction] = []
        criterion_lower = criterion_text.lower()
        criterion_words = set(criterion_lower.split())

        # Create a new coverage entry
        current_cov = RequirementCoverage(
            requirement_id=req_id, text=criterion_text, linked_tests=[], status="pending", confidence=0.0
        )

        # Now try to match tests
        # Try number-based match first (test_01_ → TC-001)
        criterion_num = f"{i:02}"  # "01", "02" etc
        number_matched = False
        for test_func in test_functions:
            if f"test_{criterion_num}_" in test_func.name or f"test_{i}_" in test_func.name:
                linked_tests.append(test_func)
                current_cov.status = "covered"
                current_cov.confidence = 0.95
                number_matched = True
                break

        # Fall back to keyword matching only if no number match found
        if not number_matched:
            for test_func in test_functions:
                test_text = test_func.docstring.lower() + " " + test_func.description.lower()
                test_words = set(test_text.split())
                overlap = len(criterion_words & test_words)
                if overlap >= 2 or any(word in test_func.name for word in criterion_words):
                    linked_tests.append(test_func)
                    current_cov.status = "covered"
                    current_cov.confidence = 0.8
                    break

    # Recalculate confidence scores
    for req_cov in coverage:
        if req_cov.linked_tests:
            avg_confidence = sum(0.9 for _ in req_cov.linked_tests) / len(req_cov.linked_tests)
            req_cov.confidence = min(1.0, avg_confidence)
        else:
            req_cov.confidence = 0.0

    return coverage


def calculate_coverage(coverage: list[RequirementCoverage]) -> dict[str, float]:
    total = len(coverage)
    if total == 0:
        return {"overall": 0.0, "covered": 0.0, "pending": 0.0, "tests_generated": 0.0}

    covered = sum(1 for r in coverage if r.status == "covered" and r.confidence > 0.7)
    pending = sum(1 for r in coverage if r.status == "pending")
    tests_generated = sum(len(r.linked_tests) for r in coverage)

    return {
        "overall": (covered / total) * 100,
        "covered": (covered / total) * 100,
        "pending": (pending / total) * 100,
        "tests_generated": float(tests_generated),
    }


# ── Phase C: Test Execution Helper ───────────────────────────────────────────
def run_playwright_test(file_path: str, output_dir: str = "test_output") -> tuple[bool, str]:
    """
    Run Playwright tests from a generated test file.

    Args:
        file_path: Path to the test file to execute
        output_dir: Directory for Playwright test reports (optional)

    Returns:
        Tuple of (success: bool, output: str)
    """
    # Ensure output directory exists
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)

    try:
        # Execute playwright test command
        result = subprocess.run(
            ["pytest", file_path, "-v", "--tb=short"],
            capture_output=True,
            text=True,
            timeout=300,  # 5 minute timeout
        )

        output = result.stdout + result.stderr

        # Check if tests passed
        success = result.returncode == 0

        return success, output

    except subprocess.TimeoutExpired:
        return False, "ERROR: Test execution timed out (5 minute limit exceeded)"
    except FileNotFoundError:
        return (
            False,
            "ERROR: Playwright is not installed or not in PATH. Run: pip install playwright && playwright install",
        )
    except Exception as e:
        return False, f"ERROR: Failed to run tests: {str(e)}"


# ── UI Display Functions ──────────────────────────────────────────────────────
def display_coverage(coverage: list[RequirementCoverage]) -> None:
    """
    Display coverage analysis in the Streamlit UI.

    Args:
        coverage: List of RequirementCoverage objects
    """
    if not coverage:
        st.markdown('<div class="status-box warn">⚠ No coverage data to display</div>', unsafe_allow_html=True)
        return

    metrics = calculate_coverage(coverage)

    # Display coverage metrics
    st.markdown("---")
    st.markdown('<span class="section-label">📊 Coverage Analysis</span>', unsafe_allow_html=True)

    st.markdown(
        f"""
        <div class="metric-row">
            <div class="metric-card">
                <div class="val">{metrics["overall"]:.0f}%</div>
                <div class="lbl">Overall Coverage</div>
            </div>
            <div class="metric-card">
                <div class="val">{len([r for r in coverage if r.status == "covered"])}/{len(coverage)}</div>
                <div class="lbl">Requirements</div>
            </div>
            <div class="metric-card">
                <div class="val">{int(metrics["tests_generated"])}</div>
                <div class="lbl">Tests Generated</div>
            </div>
            <div class="metric-card">
                <div class="val" style="font-size:0.85rem;padding-top:0.3rem">{metrics["pending"]:.0f}%</div>
                <div class="lbl">Pending</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Display detailed coverage table
    with st.expander("📋 Detailed Coverage Report", expanded=False):
        for req in coverage:
            status_colors = {"covered": "#4caf50", "pending": "#ff9800", "failed": "#f44336"}
            status_color = status_colors.get(req.status, "#888888")

            cols = st.columns([1, 3, 3, 1])
            with cols[0]:
                st.markdown(
                    f'<span style="color:{status_color};font-weight:bold">{req.requirement_id}</span>',
                    unsafe_allow_html=True,
                )
            with cols[1]:
                st.markdown(f"{req.text[:100]}{'...' if len(req.text) > 100 else ''}")
            with cols[2]:
                if req.linked_tests:
                    for test in req.linked_tests:
                        st.markdown(
                            f'<span style="color:#4caf50">✓</span> {test.name}',
                            unsafe_allow_html=True,
                        )
                else:
                    st.markdown(
                        f'<span style="color:{status_color}">● No tests</span>',
                        unsafe_allow_html=True,
                    )
            with cols[3]:
                st.progress(req.confidence)
                st.caption(f"{req.confidence:.0%} confidence")


def display_analyzed_coverage(analyzed_cases: list[Any]) -> None:
    """
    Display analyzed test cases from story_analyzer in the Streamlit UI.

    Args:
        analyzed_cases: List of AnalyzedTestCase objects from story_analyzer
    """
    from cli.story_analyzer import AnalyzedTestCase

    if not analyzed_cases:
        st.markdown('<div class="status-box warn">⚠ No analyzed test cases to display</div>', unsafe_allow_html=True)
        return

    st.markdown("---")
    st.markdown('<span class="section-label">📊 Jira Analysis Results</span>', unsafe_allow_html=True)

    # Calculate summary metrics
    total_cases = len(analyzed_cases)
    high_complexity = sum(1 for tc in analyzed_cases if tc.estimated_complexity == "high")
    medium_complexity = sum(1 for tc in analyzed_cases if tc.estimated_complexity == "medium")
    low_complexity = sum(1 for tc in analyzed_cases if tc.estimated_complexity == "low")

    st.markdown(
        f"""
        <div class="metric-row">
            <div class="metric-card">
                <div class="val">{total_cases}</div>
                <div class="lbl">Total Test Cases</div>
            </div>
            <div class="metric-card">
                <div class="val">{high_complexity}</div>
                <div class="lbl">High Complexity</div>
            </div>
            <div class="metric-card">
                <div class="val">{medium_complexity}</div>
                <div class="lbl">Medium Complexity</div>
            </div>
            <div class="metric-card">
                <div class="val">{low_complexity}</div>
                <div class="lbl">Low Complexity</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Display detailed test case report
    with st.expander("📋 Detailed Test Case Analysis", expanded=False):
        for tc in analyzed_cases:
            if isinstance(tc, AnalyzedTestCase):
                st.markdown(f"### {tc.title}")
                st.markdown(f"**Description:** {tc.description[:200]}{'...' if len(tc.description) > 200 else ''}")

                cols = st.columns(3)
                with cols[0]:
                    st.markdown(f"**Complexity:** {tc.estimated_complexity.capitalize()}")
                with cols[1]:
                    st.markdown(f"**Actions:** {', '.join(tc.identified_actions)}")
                with cols[2]:
                    st.markdown(f"**Confidence:** {tc.analysis_confidence:.0%}")

                if tc.suggested_data:
                    st.markdown("**Suggested Test Data:**")
                    for key, value in tc.suggested_data.items():
                        st.code(f"{key}: {value}", language=None)

                if tc.dependencies:
                    st.markdown("**Dependencies:**")
                    for dep in tc.dependencies:
                        st.markdown(f"- {dep}")

                st.markdown("---")


def _generate_json_report(test_code: str, coverage: list[RequirementCoverage] | None = None) -> str:
    """Generate a JSON report of the test and coverage data."""
    import json as _json

    report: dict[str, object] = {
        "generated_at": datetime.now().isoformat(),
        "test_code": test_code,
    }
    if coverage:
        report["coverage"] = [
            {
                "id": r.requirement_id,
                "text": r.text,
                "status": r.status,
                "confidence": r.confidence,
                "linked_tests": [t.name for t in r.linked_tests],
            }
            for r in coverage
        ]
    return _json.dumps(report, indent=2)


def _generate_html_report(test_code: str, coverage: list[RequirementCoverage] | None = None) -> str:
    """Generate a standalone HTML report."""
    rows = ""
    if coverage:
        for r in coverage:
            status_icon = "✅" if r.status == "covered" else "🔴"
            tests = ", ".join(t.name for t in r.linked_tests) or "None"
            rows += f"<tr><td>{r.requirement_id}</td><td>{r.text}</td><td>{status_icon} {r.status}</td><td>{r.confidence:.0%}</td><td>{tests}</td></tr>\n"
    import html as _html

    escaped_code = _html.escape(test_code)
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Test Report</title>
<style>
  body {{ font-family: system-ui, sans-serif; max-width: 960px; margin: 2rem auto; padding: 0 1rem; }}
  table {{ border-collapse: collapse; width: 100%; margin: 1rem 0; }}
  th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
  th {{ background: #2d2d2d; color: white; }}
  pre {{ background: #1e1e1e; color: #d4d4d4; padding: 1rem; border-radius: 6px; overflow-x: auto; }}
  h1 {{ color: #333; }} h2 {{ color: #555; }}
</style></head><body>
<h1>🎭 AI Playwright Test Report</h1>
<p>Generated: {datetime.now().isoformat()}</p>
<h2>📊 Coverage</h2>
<table><tr><th>ID</th><th>Requirement</th><th>Status</th><th>Confidence</th><th>Tests</th></tr>
{rows}</table>
<h2>🐍 Test Code</h2>
<pre><code>{escaped_code}</code></pre>
</body></html>"""


def display_run_button(
    saved_file_path: str, test_code: str = "", coverage: list[RequirementCoverage] | None = None
) -> tuple[bool, str]:
    """
    Display Run Now button and download options.

    Args:
        saved_file_path: Path to the saved test file
        test_code: The generated test code string
        coverage: Coverage analysis results for report generation

    Returns:
        Tuple of (success: bool, output: str)
    """
    col1, col2 = st.columns([1, 3])

    with col1:
        run_button = st.button("▶️ Run Now", use_container_width=True, type="primary", key="run_btn")

    # Download section
    st.markdown("#### ⬇️ Download Output")
    dl_col1, dl_col2, dl_col3 = st.columns(3)

    try:
        with open(saved_file_path, encoding="utf-8") as f:
            file_content = f.read()
    except Exception:
        file_content = test_code

    with dl_col1:
        st.download_button(
            label="🐍 Python (.py)",
            data=file_content,
            file_name=os.path.basename(saved_file_path),
            mime="text/x-python",
            use_container_width=True,
            key="download_py",
        )

    with dl_col2:
        json_report = _generate_json_report(file_content, coverage)
        json_name = os.path.basename(saved_file_path).replace(".py", ".json")
        st.download_button(
            label="📋 JSON Report",
            data=json_report,
            file_name=json_name,
            mime="application/json",
            use_container_width=True,
            key="download_json",
        )

    with dl_col3:
        html_report = _generate_html_report(file_content, coverage)
        html_name = os.path.basename(saved_file_path).replace(".py", ".html")
        st.download_button(
            label="🌐 HTML Report",
            data=html_report,
            file_name=html_name,
            mime="text/html",
            use_container_width=True,
            key="download_html",
        )

    success, output = False, ""

    if run_button:
        with st.spinner("Running tests..."):
            success, output = run_playwright_test(saved_file_path)
        st.session_state.last_run_success = success
        st.session_state.last_run_output = output
        st.session_state.last_run_success = None
        st.session_state.last_run_output = ""

    # Render from session_state so it survives download button reruns
    run_success = st.session_state.get("last_run_success")
    run_output = st.session_state.get("last_run_output", "")

    if run_success is not None:
        if run_success:
            st.success("✅ All tests passed!")
        else:
            st.error("❌ Some tests failed")

        with st.expander("📄 Test Output", expanded=not run_success):
            st.code(run_output, language="plaintext")

    return run_success or False, run_output


# ── Session State Management ──────────────────────────────────────────────────
_session_defaults: dict[str, object] = {
    "generated_test": None,
    "report_local": None,
    "report_jira": None,
    "report_html": None,
    "generation_log": [],
    "last_run_time": None,
    "last_story": "",
    "criteria_count": 0,
    "parse_method": "",
    # --- Phase A additions ---
    "saved_test_path": None,  # absolute path to saved file on disk
    "test_filename": None,  # just the filename (no path)
    "last_generated_at": None,  # ISO timestamp of last save
    "page_context": None,  # PageContext from last scrape
    "scrape_duration_ms": 0,  # How long the last scrape took
    "last_run_success": None,  # bool result of last Run Now
    "last_run_output": "",  # stdout/stderr from last run
}


def init_session_state() -> None:
    """Initialize session state with default values."""
    for key, value in _session_defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def _log(message: str, level: str = "info") -> None:
    """Append a log message and display in UI."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    st.session_state.generation_log.append(f"[{timestamp}] {level.upper()}: {message}")


def display_logs() -> None:
    """Display generation logs in the UI."""
    with st.sidebar:
        st.markdown("### 📋 Generation Log")
        for log in st.session_state.generation_log:
            st.caption(log)


# ── Test Generation Logic ────────────────────────────────────────────────────
def generate_test_for_story(
    prompt_text: str,
    base_url: str,
    llm_client: LLMClient,
    page_context: PageContext | None = None,
) -> str:
    """
    Generate a Playwright test from user story using the AI agent.

    Args:
        prompt_text:  User story text
        base_url:     Target website URL
        llm_client:   LLMClient instance
        page_context: Optional scraped page context — injected into prompt
                      when provided, generation falls back gracefully if None

    Returns:
        Generated test code as a string
    """
    # Build context block — empty string if no context available
    context_block = page_context.to_prompt_block() + "\n\n" if page_context else ""

    # Extract and enumerate criteria for explicit LLM instruction
    criteria = extract_criteria_from_user_story(prompt_text)
    criteria_lines = "\n".join([f"  {i + 1}. {crit}" for i, crit in enumerate(criteria)])
    criteria_count = len(criteria)

    prompt = f"""{context_block}You are an expert Playwright automation engineer. Generate a complete, runnable Playwright test for the following user story.

USER STORY:
{prompt_text}

BASE URL:
{base_url}

ACCEPTANCE CRITERIA (explicitly enumerate — generate ONE test per criterion):
{criteria_lines}
(Total: {criteria_count} criteria)

CRITICAL REQUIREMENT:
- YOU MUST generate a SEPARATE test function for EACH of the {criteria_count} acceptance criteria listed above
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
- DO NOT skip the last criteria — all {criteria_count} criteria must have tests

Generate the Playwright test code now:"""

    try:
        with st.spinner("Generating Playwright test."):
            test_code = llm_client.generate_test(prompt)
            if test_code:
                return normalise_code_newlines(test_code.strip())
    except Exception as e:
        _log(f"LLM error: {str(e)}", "error")
        st.error(f"Failed to generate test: {str(e)}")
        return ""

    return ""


# ── Main UI Layout ───────────────────────────────────────────────────────────
def _display_url_clarity_message(base_url: str | None) -> None:
    """Display clarity message about page scraping status based on URL input."""
    if not base_url:
        st.markdown(
            """
            <div class="status-box warn">
                <strong>⚠️ Page Context Scraper Disabled</strong><br>
                Without a base URL, the Page Context Scraper cannot scan the target page.
                Tests will be generated using generic placeholders (e.g., example.com).<br>
                <em>This mode is useful for planning and designing test cases without a specific target.</em>
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f"""
            <div class="status-box success">
                <strong>✅ Page Context Scraper Active</strong><br>
                The scraper will attempt to scan the page at <code>{base_url}</code> to extract real DOM elements.<br>
                <em>This enables generated tests to use actual selectors from the target site.</em>
            </div>
            """,
            unsafe_allow_html=True,
        )


def main() -> None:
    """Main application entry point."""
    st.set_page_config(
        page_title="AI Test Generator",
        page_icon="logo.png",  # shows in browser tab
        layout="wide",
        initial_sidebar_state="expanded",
    )

    # Custom CSS
    st.markdown(
        """
    <style>
    /* --- Terminal-inspired theme --- */
    :root {
        --bg-primary: #1e1e1e;
        --bg-secondary: #252526;
        --bg-tertiary: #333333;
        --bg-code: #1a1a1a;
        --text-primary: #e0e0e0;
        --text-secondary: #b0b0b0;
        --accent-green: #4caf50;
        --accent-red: #f44336;
        --accent-orange: #ff9800;
        --accent-blue: #2196f3;
        --border-color: #444444;
    }

    /* Remove Streamlit chrome */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}

    /* Container */
    .streamlit-expanderHeader, .streamlit-expanderContent {
        border: none;
    }

    /* Metrics styling */
    .metric-row {
        display: flex;
        gap: 20px;
        margin: 20px 0;
    }
    .metric-card {
        background: var(--bg-secondary);
        padding: 15px;
        border-radius: 8px;
        min-width: 120px;
        flex: 1;
        text-align: center;
        border: 1px solid var(--border-color);
    }
    .metric-card .val {
        font-size: 1.8rem;
        font-weight: bold;
        color: var(--accent-blue);
        margin-bottom: 5px;
    }
    .metric-card .lbl {
        font-size: 0.9rem;
        color: var(--text-secondary);
    }

    /* Section headers */
    .section-label {
        display: block;
        font-size: 1.1rem;
        font-weight: bold;
        color: var(--text-primary);
        margin: 20px 0 10px 0;
        padding-bottom: 5px;
        border-bottom: 2px solid var(--accent-blue);
    }

    /* Status boxes */
    .status-box {
        padding: 15px;
        border-radius: 8px;
        margin: 10px 0;
        border: 1px solid var(--border-color);
    }
    .status-box.success {
        background: rgba(76, 175, 80, 0.15);
        border-color: var(--accent-green);
        color: var(--accent-green);
    }
    .status-box.error {
        background: rgba(244, 67, 54, 0.15);
        border-color: var(--accent-red);
        color: var(--accent-red);
    }
    .status-box.warn {
        background: rgba(255, 152, 0, 0.15);
        border-color: var(--accent-orange);
        color: var(--accent-orange);
    }

    /* Code display */
    .stCode {
        background: var(--bg-code);
        border-radius: 8px;
        border: 1px solid var(--border-color);
    }

    /* Progress bars */
    .stProgress > div > div > div > div {
        background: var(--accent-blue);
    }
    .stProgress > div > div > div {
        background: var(--bg-tertiary);
    }

    /* Buttons */
    .stButton>button {
        background: var(--accent-blue);
        color: white;
        border: none;
        border-radius: 6px;
        padding: 10px 24px;
        font-weight: bold;
    }
    .stButton>button:hover {
        background: #1976d2;
    }

    /* Sidebar */
    .stSidebar {
        background: var(--bg-primary);
        border-right: 1px solid var(--border-color);
    }

    /* Input fields */
    input, textarea, select {
        background: var(--bg-tertiary) !important;
        color: var(--text-primary) !important;
        border: 1px solid var(--border-color) !important;
        border-radius: 6px !important;
    }
    input:focus, textarea:focus, select:focus {
        border-color: var(--accent-blue) !important;
        outline: none !important;
    }

    /* Custom expander arrow */
    .streamlit-expanderHeader::before {
        content: '▶';
        display: inline-block;
        margin-right: 8px;
        color: var(--accent-blue);
    }
    </style>
    """,
        unsafe_allow_html=True,
    )

    # Initialize session state
    init_session_state()

    # Header
    st.title("🎭 AI Playwright Test Generator")
    st.markdown("**Save • Review • Run** — Create Playwright tests from user stories in minutes")

    # Fetch dynamic model list from ollama
    _default_models = ["qwen3.5:35b", "qwen2.5-coder:1.5b-base", "qwen2.5:7b", "llama3.2"]
    available_models = _default_models.copy()
    try:
        import subprocess

        result = subprocess.run(["ollama", "list"], capture_output=True, text=True, timeout=3)
        if result.returncode == 0:
            lines = result.stdout.strip().splitlines()[1:]  # skip header
            ollama_models = [line.split()[0] for line in lines if line.strip()]
            if ollama_models:
                available_models = ollama_models
    except Exception:
        pass

    # Setup LLM client
    with st.spinner("Initializing AI agent."):
        # We'll re-init after the user selects a model inside the sidebar
        pass

    # Create file path for logs
    log_file_path = Path("generated_tests") / "generation.log"
    log_file_path.parent.mkdir(exist_ok=True)

    # Sidebar
    with st.sidebar:
        st.image("logo.png", use_container_width=True)
        st.divider()
        st.markdown("### Configuration")
        selected_model = st.selectbox(
            "🧠 LLM Model",
            options=available_models,
            index=0,
            help="Models detected from your local Ollama installation.",
        )

        # Initialize LLM client with the selected model
        llm_client = LLMClient(model_name=str(selected_model))
        base_url = st.text_input(
            "🌐 Base URL",
            placeholder="https://example.com",
            help="The target website URL to test. When empty, tests will use generic placeholders.",
        )

        # Display clarity message based on URL input
        _display_url_clarity_message(base_url if base_url else None)

        st.markdown("### Output")
        st.markdown("**Saved to:** `generated_tests/`")

        if st.button("🧹 Clear State"):
            for key in list(st.session_state.keys()):
                if key not in _session_defaults:
                    del st.session_state[key]
            st.rerun()

    # Main input section
    col1, col2 = st.columns([2, 1])
    with col1:
        user_story = st.text_area(
            "📝 User Story / Requirements",
            height=150,
            placeholder="Example:\nAs a registered user, I want to log in with my email and password so that I can access my account dashboard.",
            help="Enter the user story or acceptance criteria for the test",
        )
    with col2:
        st.markdown("### Instructions")
        st.info("""
        **Steps:**
        1. Enter user story
        2. Set base URL
        3. Click **✨ Generate**
        4. Review coverage
        5. Run test

        **Tips:**
        - Include clear acceptance criteria
        - Specify expected behavior
        - Mention edge cases
        """)

    # Generate button
    generate_btn = st.button("✨ Generate Test", type="primary", use_container_width=True)

    if generate_btn and user_story:
        # Clear previous save state before starting new generation
        st.session_state.saved_test_path = None
        st.session_state.test_filename = None
        st.session_state.last_generated_at = None
        st.session_state.generated_test = None

        # Scrape page context if URL provided
        page_context: PageContext | None = None
        if base_url:
            with st.spinner("🔍 Scanning page for elements…"):
                page_context, scrape_error = scrape_page_context(base_url)
            if scrape_error:
                st.warning(f"⚠️ {scrape_error}")
                _log(f"Scraper: {scrape_error}", "warn")
            else:
                assert page_context is not None
                _log(
                    f"Scraped {page_context.element_count()} elements in {page_context.scrape_duration_ms}ms",
                    "ok",
                )

        # Generate test
        test_code: str = generate_test_for_story(user_story, base_url, llm_client, page_context)
        if test_code:
            st.session_state.generated_test = test_code
            st.session_state.last_story = user_story
            st.success("✅ Test generated successfully!")
            _log(f"Test generated: {len(test_code)} chars")

            # Phase A: Auto-save to disk
            try:
                saved_path: str = save_generated_test(
                    test_code=test_code,
                    story_text=user_story,
                    base_url=base_url,
                    output_dir="generated_tests",
                )
                st.session_state.saved_test_path = saved_path
                st.session_state.test_filename = os.path.basename(saved_path)
                st.session_state.last_generated_at = datetime.now().isoformat()
                _log(f"Saved: {saved_path}", "ok")
            except Exception as e:
                _log(f"Auto-save failed: {e}", "warn")
                st.warning(f"⚠️ Auto-save failed: {e}")
        else:
            st.error("❌ Failed to generate test code")
            _log("Test generation failed", "error")

    elif generate_btn and not user_story:
        st.error("❌ Please enter a user story first")
        _log("Empty user story submitted", "error")
    # ── Output section — rendered from session_state, persists across reruns ──
    test_code = st.session_state.get("generated_test") or ""
    saved_path = st.session_state.get("saved_test_path") or ""
    story_for_coverage: str = st.session_state.get("last_story") or ""
    if test_code:
        # Phase A: Save & Rename UI
        if saved_path:
            filename = st.session_state.test_filename or saved_path
            new_name_input: str | None = None

            st.markdown("---")
            st.markdown("#### 💾 Saved Test")
            st.code(saved_path, language=None)

            col1, col2 = st.columns([3, 1])
            with col1:
                new_name_input = st.text_input(
                    "Rename test file",
                    value=filename if isinstance(filename, str) else "",
                    key="rename_input",
                    help="Edit the filename and click Rename. test_ prefix is enforced automatically.",
                )
            with col2:
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("Rename", key="rename_btn", type="primary"):
                    if new_name_input and saved_path:
                        if Path(saved_path).exists():
                            try:
                                new_path = rename_test_file(saved_path, new_name_input)
                                st.session_state.saved_test_path = new_path
                                st.session_state.test_filename = os.path.basename(new_path)
                                st.success(f"Renamed to: `{os.path.basename(new_path)}`")
                                st.rerun()
                            except FileNotFoundError:
                                st.error("File no longer exists on disk. Please regenerate.")
                            except Exception as e:
                                st.error(f"Rename failed: {e}")
                        else:
                            st.error("File not found on disk. Please regenerate.")

        # Phase B: Coverage analysis
        try:
            test_functions, criteria = parse_test_file(test_code, story_for_coverage)
            st.session_state.criteria_count = len(criteria)
            st.session_state.parse_method = "ast"

            if test_functions:
                coverage = map_tests_to_criteria(test_functions, criteria)
                st.session_state.coverage_results = coverage
                display_coverage(coverage)

                # Phase C: Run button + Download
                if saved_path:
                    display_run_button(saved_path, test_code=test_code, coverage=coverage)

                # Display test code in tabs
                st.markdown("---")
                st.markdown("### 📋 Generated Test Code")
                tab1, tab2 = st.tabs(["🐍 Python Code", "📝 Preview"])

                with tab1:
                    st.code(test_code, language="python")

                with tab2:
                    st.markdown(test_code)
            else:
                st.warning("⚠️ No test functions found in generated code")
                with st.expander("⚠️ Review Generated Code"):
                    st.code(test_code, language="python")
        except Exception as e:
            st.error(f"Failed to analyze coverage: {e}")
            _log(f"Coverage analysis error: {e}", "error")

    # Display logs in sidebar
    display_logs()


if __name__ == "__main__":
    main()
