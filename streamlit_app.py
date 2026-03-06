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

import streamlit as st
from dotenv import load_dotenv

from src.file_utils import normalise_code_newlines, rename_test_file, save_generated_test
from src.llm_client import LLMClient

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
    test_functions = []
    lines = test_code.splitlines()
    current_test: TestFunction | None = None
    docstring_lines: list[str] = []
    in_docstring = False

    for i, line in enumerate(lines, 1):
        stripped = line.strip()

        # Detect test function definition
        if stripped.startswith("def test_") and "(" in stripped:
            # Save previous test function if exists
            if current_test:
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
        elif current_test and not in_docstring:
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
        elif current_test and in_docstring:
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
        if current_test and in_docstring and i == len(lines):
            current_test.line_end = i
            current_test.docstring = "\n".join(docstring_lines)
            test_functions.append(current_test)

    # Handle case where test function was just defined
    if current_test and not in_docstring:
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
            if match and match.lastindex:
                criteria.append(match.group(match.lastindex).strip())
                break
        else:
            # Match Gherkin syntax
            gherkin_match = gherkin_re.match(line_stripped)
            if gherkin_match:
                # Use the 'when' or 'then' part as the criterion
                for idx in [2, 3]:  # 'when' or 'then' groups
                    if gherkin_match.lastindex and gherkin_match.lastindex >= idx and gherkin_match.group(idx):
                        criteria.append(gherkin_match.group(idx).strip())
                        break
            # Match "should/must" pattern
            elif should_re.match(line_stripped):
                match = should_re.match(line_stripped)
                if match and match.lastindex and match.lastindex >= 2:
                    criteria.append(match.group(2).strip())
                else:
                    criteria.append(line_stripped)

    return criteria if criteria else [user_story.strip()[:120]]


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
    coverage = []

    for i, criterion_text in enumerate(criteria, 1):
        req_id = f"TC-{i:03}"
        linked_tests = []
        criterion_lower = criterion_text.lower()
        criterion_words = set(criterion_lower.split())

        # Create a new coverage entry
        coverage.append(
            RequirementCoverage(
                requirement_id=req_id, text=criterion_text, linked_tests=[], status="pending", confidence=0.0
            )
        )

        # Now try to match tests
        for test_func in test_functions:
            test_text = test_func.docstring.lower() + " " + test_func.description.lower()
            test_words = set(test_text.split())

            # Simple keyword matching
            overlap = len(criterion_words & test_words)
            if overlap >= 2 or any(word in test_func.name for word in criterion_words):
                linked_tests.append(test_func)
                coverage[-1].status = "covered"
                coverage[-1].confidence = 0.9
                break

        # If no tests linked, keep as pending - no duplicate entries
        if not linked_tests:
            coverage[-1].status = "pending"
            coverage[-1].confidence = 0.0

    # Recalculate confidence scores
    for req_cov in coverage:
        if req_cov.linked_tests:
            avg_confidence = sum(0.9 for _ in req_cov.linked_tests) / len(req_cov.linked_tests)
            req_cov.confidence = min(1.0, avg_confidence)
        else:
            req_cov.confidence = 0.0

    return coverage


def calculate_coverage(coverage: list[RequirementCoverage]) -> dict[str, float]:
    """
    Calculate overall coverage metrics from coverage data.

    Returns:
        Dictionary with coverage metrics:
        - overall: percentage of requirements with at least one test
        - covered: percentage with good confidence (>0.7)
        - pending: percentage with no linked tests
        - high_confidence: percentage with confidence >0.9
    """
    total = len(coverage)
    if total == 0:
        return {"overall": 0.0, "covered": 0.0, "pending": 0.0, "high_confidence": 0.0, "low_confidence": 0.0}

    covered = sum(1 for r in coverage if r.status == "covered" and r.confidence > 0.7)
    pending = sum(1 for r in coverage if r.status == "pending")
    high_conf = sum(1 for r in coverage if r.confidence > 0.9)
    low_conf = sum(1 for r in coverage if 0 < r.confidence <= 0.7)

    return {
        "overall": (covered / total) * 100,
        "covered": (covered / total) * 100,
        "pending": (pending / total) * 100,
        "high_confidence": (high_conf / total) * 100,
        "low_confidence": (low_conf / total) * 100,
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
            ["playwright", "test", file_path],
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
                <div class="val">{len(coverage) - metrics["pending"]:.0f}%</div>
                <div class="lbl">High Confidence</div>
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


def display_run_button(saved_file_path: str) -> tuple[bool, str]:
    """
    Display Run Now button and execute tests.

    Args:
        saved_file_path: Path to the saved test file

    Returns:
        Tuple of (success: bool, output: str)
    """
    col1, col2 = st.columns([1, 3])

    with col1:
        run_button = st.button("▶️ Run Now", use_container_width=True, type="primary", key="run_btn")

    success, output = False, ""

    if run_button:
        with st.spinner("Running tests."):
            success, output = run_playwright_test(saved_file_path)

        # Display results
        if success:
            st.success("✅ All tests passed!")
        else:
            st.error("❌ Some tests failed")

        # Show output in collapsible section
        with st.expander("📄 Test Output", expanded=not success):
            st.code(output, language="plaintext")

    return success, output


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
def generate_test_for_story(prompt_text: str, base_url: str, llm_client: LLMClient) -> str:
    """
    Generate a Playwright test from user story using the AI agent.

    Args:
        prompt_text: User story text
        base_url: Target website URL
        llm_client: LLMClient instance

    Returns:
        Generated test code as a string
    """
    prompt = f"""You are an expert Playwright automation engineer. Generate a complete, runnable Playwright test for the following user story.

USER STORY:
{prompt_text}

BASE URL:
{base_url}

Requirements:
- Use Python and Playwright for web automation
- Test should cover the main acceptance criteria from the user story
- Include proper test structure with setup and teardown
- Use descriptive test names
- Include comments explaining each step
- Handle dynamic content and loading states appropriately
- Include assertions to validate expected outcomes
- Make the test self-contained and runnable without modifications

IMPORTANT:
- Return ONLY the Python code, no markdown formatting, no explanations
- Use proper Playwright API calls
- Handle potential exceptions gracefully

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
def main() -> None:
    """Main application entry point."""
    st.set_page_config(
        page_title="AI Test Generator",
        page_icon="🎭",
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

    # Setup LLM client
    with st.spinner("Initializing AI agent."):
        llm_client = LLMClient()

    # Create file path for logs
    log_file_path = Path("generated_tests") / "generation.log"
    log_file_path.parent.mkdir(exist_ok=True)

    # Sidebar
    with st.sidebar:
        st.markdown("### Configuration")
        st.text_input(
            "🔑 API Key (optional)",
            type="password",
            help="Leave blank to use environment variable or free tier",
        )
        base_url = st.text_input(
            "🌐 Base URL",
            placeholder="https://example.com",
            help="The target website URL to test",
        )
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

        # Generate test
        test_code = generate_test_for_story(user_story, base_url, llm_client)

        if test_code:
            st.success("✅ Test generated successfully!")
            _log(f"Test generated: {len(test_code)} chars")

            # Phase A: Auto-save to disk
            saved_path: str | None = None
            try:
                saved_path = save_generated_test(
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

            # Phase A: Save & Rename UI
            saved_path = st.session_state.saved_test_path
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
                test_functions, criteria = parse_test_file(test_code, user_story)
                st.session_state.criteria_count = len(criteria)
                st.session_state.parse_method = "ast"

                if test_functions:
                    coverage = map_tests_to_criteria(test_functions, criteria)
                    display_coverage(coverage)

                    # Phase C: Run button
                    if saved_path:
                        display_run_button(saved_path)

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
        else:
            st.error("❌ Failed to generate test code")
            _log("Test generation failed", "error")

    elif generate_btn and not user_story:
        st.error("❌ Please enter a user story first")
        _log("Empty user story submitted", "error")

    # Display logs in sidebar
    display_logs()


if __name__ == "__main__":
    main()
