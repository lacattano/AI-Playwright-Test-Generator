#!/usr/bin/env python3
"""Streamlit application for generating Playwright tests from feature specifications."""

import re
import subprocess
import traceback
from pathlib import Path
from typing import Any

import streamlit as st

from src.code_validator import (
    validate_generated_locator_quality as _validate_locator_quality,
)
from src.code_validator import (
    validate_python_syntax as _validate_python_syntax,
)
from src.code_validator import (
    validate_test_function as _validate_test_function,
)
from src.file_utils import rename_test_file
from src.user_story_parser import FeatureParser, RequirementModel

try:
    from src.file_utils import normalise_code_newlines as _normalise
except ImportError:

    def _normalise(code: str) -> str:  # type: ignore[misc]
        return code.replace("\r\n", "\n").replace("\r", "\n") if code else ""


from dotenv import load_dotenv

from src.coverage_utils import build_coverage_analysis
from src.page_context_scraper import (
    CredentialProfile,
    MultiPageContext,
    execute_journey,
    scrape_multiple_pages,
    scrape_page_context,
)
from src.prompt_utils import (
    build_page_context_prompt_block,
    get_streamlit_system_prompt_template,
)
from src.pytest_output_parser import (
    RunResult,
    format_pytest_output_for_display,
    parse_pytest_output,
)
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
    "input_mode": "paste",
    "requirements_source": "",
    # AI-009 Phase B: Credential profiles
    "credentials_enabled": False,
    "credential_profiles": [],
    "active_credential_profile": None,
    # AI-009 Phase B: Journey steps
    "journey_steps": [],
    "journey_expanded": False,
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
                    [
                        "pytest",
                        "-o",
                        "addopts=",
                        "--browser=chromium",
                        "--screenshot=only-on-failure",
                        saved_path,
                        "-v",
                        "--tb=short",
                        "--maxfail=5",
                    ],
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

        filtered_output = format_pytest_output_for_display(run_result.raw_output)
        if filtered_output:
            with st.expander("📄 Technical Output (filtered)", expanded=run_result.failed > 0):
                st.code(filtered_output, language="plaintext")


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


def parse_feature_text(content: str) -> tuple[str, RequirementModel | None, str | None]:
    """
    Parse a feature specification string into user story and acceptance criteria.

    Uses FeatureParser to extract and structure the feature specification.

    Args:
        content: Raw feature specification text

    Returns:
        Tuple of (user_story_text, requirement_model, error_message)
    """
    parser = FeatureParser()
    result = parser.parse(content)

    if not result.success:
        return "", None, result.error_message

    if result.specification is None:
        return "", None, "Parse failed"

    requirement_model = parser.build_requirement_model(result.specification)
    if requirement_model.count == 0:
        return "", None, "No requirements found in input"

    return (
        result.specification.user_story,
        requirement_model,
        None,
    )


# ─────────────────────────────────────────────────────────────────────────────
# AI-009 Phase B: Credential profiles helper functions
# ─────────────────────────────────────────────────────────────────────────────


def _convert_urls_to_journey(additional_urls: str) -> list[dict]:
    """
    Convert additional URLs textarea into journey steps.

    Each URL becomes: goto → capture sequence.

    Args:
        additional_urls: Newline-separated URLs from textarea

    Returns:
        List of step dicts ready for journey_steps session state
    """
    urls = [url.strip() for url in additional_urls.splitlines() if url.strip()]
    steps = []

    for idx, url in enumerate(urls):
        steps.append(
            {
                "step_type": "goto",
                "url": url,
                "selector": None,
                "visible_text": None,
                "value": None,
                "label": f"Navigate to {url}",
                "capture_label": None,
            }
        )
        steps.append(
            {
                "step_type": "capture",
                "url": None,
                "selector": None,
                "visible_text": None,
                "value": None,
                "label": f"Capture {url}",
                "capture_label": f"Page {idx + 1}",
            }
        )

    return steps


def _render_journey_builder_section() -> None:
    """
    Render the journey builder UI section.

    Displays:
    - Journey steps list with dynamic fields per step type
    - Add/Remove step buttons
    - "Build from URL list" helper
    """
    with st.expander(
        "🗺️ Journey steps (optional — for dynamic or authenticated pages)", expanded=st.session_state.journey_expanded
    ):
        st.session_state.journey_expanded = True

        st.markdown("""
**Define the steps the scraper will follow.** Each step is executed in order:

- **Goto**: Navigate directly to a URL
- **Click**: Click an element by selector or visible text
- **Fill**: Fill an input field with a value (use `{{username}}` or `{{password}}` placeholders)
- **Submit**: Click a submit button or press Enter
- **Capture**: Collect page context at the current page
- **Wait**: Wait for a selector to appear before continuing

**Important**: Add a **Capture** step wherever you want page context collected.
""")

        # Ensure journey_steps exists
        if "journey_steps" not in st.session_state:
            st.session_state.journey_steps = []

        # Render existing steps
        for idx, step in enumerate(st.session_state.journey_steps):
            with st.container():
                col1, col2, col3 = st.columns([1, 4, 1])

                with col1:
                    step["step_type"] = st.selectbox(
                        "Type",
                        options=["goto", "click", "fill", "submit", "capture", "wait"],
                        index=["goto", "click", "fill", "submit", "capture", "wait"].index(step["step_type"])
                        if step["step_type"] in ["goto", "click", "fill", "submit", "capture", "wait"]
                        else 0,
                        key=f"step_{idx}_type",
                        label_visibility="collapsed",
                    )

                with col2:
                    step_type = step["step_type"]

                    if step_type == "goto":
                        step["url"] = st.text_input(
                            "URL",
                            value=step.get("url", ""),
                            key=f"step_{idx}_url",
                            label_visibility="collapsed",
                        )
                        step["label"] = st.text_input(
                            "Label",
                            value=step.get("label", ""),
                            key=f"step_{idx}_label",
                            placeholder="e.g., Navigate to dashboard",
                            label_visibility="collapsed",
                        )

                    elif step_type == "click":
                        click_mode = st.radio(
                            "Click by",
                            options=["selector", "visible_text"],
                            index=0 if step.get("selector") else 1,
                            key=f"step_{idx}_click_mode",
                            label_visibility="collapsed",
                            horizontal=True,
                        )
                        if click_mode == "selector":
                            step["selector"] = st.text_input(
                                "Selector",
                                value=step.get("selector", ""),
                                key=f"step_{idx}_selector",
                                placeholder="#submit-button",
                                label_visibility="collapsed",
                            )
                            step["visible_text"] = None
                        else:
                            step["visible_text"] = st.text_input(
                                "Visible text",
                                value=step.get("visible_text", ""),
                                key=f"step_{idx}_visible_text",
                                placeholder="e.g., Sign in",
                                label_visibility="collapsed",
                            )
                            step["selector"] = None
                        step["label"] = st.text_input(
                            "Label",
                            value=step.get("label", ""),
                            key=f"step_{idx}_label_click",
                            placeholder="e.g., Click login button",
                            label_visibility="collapsed",
                        )

                    elif step_type == "fill":
                        step["selector"] = st.text_input(
                            "Selector",
                            value=step.get("selector", ""),
                            key=f"step_{idx}_selector",
                            placeholder="#username",
                            label_visibility="collapsed",
                        )
                        step["value"] = st.text_input(
                            "Value",
                            value=step.get("value", ""),
                            key=f"step_{idx}_value",
                            placeholder="Use {{username}} or {{password}} for credentials",
                            label_visibility="collapsed",
                        )
                        step["label"] = st.text_input(
                            "Label",
                            value=step.get("label", ""),
                            key=f"step_{idx}_label_fill",
                            placeholder="e.g., Fill username",
                            label_visibility="collapsed",
                        )

                    elif step_type == "submit":
                        step["selector"] = st.text_input(
                            "Selector",
                            value=step.get("selector", ""),
                            key=f"step_{idx}_selector_submit",
                            placeholder="#login-form button[type='submit']",
                            label_visibility="collapsed",
                        )
                        step["label"] = st.text_input(
                            "Label",
                            value=step.get("label", ""),
                            key=f"step_{idx}_label_submit",
                            placeholder="e.g., Submit login form",
                            label_visibility="collapsed",
                        )

                    elif step_type == "capture":
                        step["capture_label"] = st.text_input(
                            "Page label",
                            value=step.get("capture_label", ""),
                            key=f"step_{idx}_capture_label",
                            placeholder="e.g., Dashboard page, Cart page",
                            label_visibility="collapsed",
                        )
                        step["label"] = st.text_input(
                            "Step label",
                            value=step.get("label", ""),
                            key=f"step_{idx}_label_capture",
                            placeholder="e.g., Capture dashboard state",
                            label_visibility="collapsed",
                        )

                    elif step_type == "wait":
                        wait_mode = st.radio(
                            "Wait for",
                            options=["selector", "text"],
                            index=0 if step.get("selector") else 1,
                            key=f"step_{idx}_wait_mode",
                            label_visibility="collapsed",
                            horizontal=True,
                        )
                        if wait_mode == "selector":
                            step["selector"] = st.text_input(
                                "Selector",
                                value=step.get("selector", ""),
                                key=f"step_{idx}_selector_wait",
                                placeholder="#loading-spinner",
                                label_visibility="collapsed",
                            )
                        else:
                            step["wait_text"] = st.text_input(
                                "Text to appear",
                                value=step.get("wait_text", ""),
                                key=f"step_{idx}_wait_text",
                                placeholder="e.g., 'Logged in successfully'",
                                label_visibility="collapsed",
                            )
                        step["label"] = st.text_input(
                            "Label",
                            value=step.get("label", ""),
                            key=f"step_{idx}_label_wait",
                            placeholder="e.g., Wait for login complete",
                            label_visibility="collapsed",
                        )

                with col3:
                    if st.button("🗑️", key=f"step_{idx}_remove", type="primary", help="Remove step"):
                        st.session_state.journey_steps.pop(idx)
                        st.rerun()

        # Control buttons row
        btn_col1, btn_col2 = st.columns([1, 1])

        with btn_col1:
            if st.button("➕ Add step", use_container_width=True):
                st.session_state.journey_steps.append(
                    {
                        "step_type": "goto",
                        "url": "",
                        "selector": None,
                        "visible_text": None,
                        "value": None,
                        "label": "",
                        "capture_label": None,
                    }
                )
                st.rerun()

        with btn_col2:
            # Get additional URLs if defined
            additional_urls_raw = st.session_state.get("additional_urls", "")
            if additional_urls_raw.strip():
                if st.button("⚡ Build from URL list → journey steps", use_container_width=True, type="secondary"):
                    new_steps = _convert_urls_to_journey(additional_urls_raw)
                    st.session_state.journey_steps = new_steps
                    st.success(f"Created {len(new_steps)} steps from {len(additional_urls_raw.split(chr(10)))} URLs")
                    st.rerun()
            else:
                st.info("Add URLs in 'Add more pages' section, then click 'Build from URL list'")


def _render_credential_profiles_section() -> None:
    """
    Render the credential profiles section of the UI.

    Displays:
    - Toggle to enable/disable authentication
    - List of credential profiles (label, username, password)
    - Add/remove profile buttons
    - Active profile selector
    """
    # Get current values
    credentials_enabled = st.session_state.get("credentials_enabled", False)
    profiles = st.session_state.get("credential_profiles", [])

    # Toggle
    credentials_enabled = st.toggle(
        "🔐 Pages require login",
        value=credentials_enabled,
        key="credentials_enabled",
    )

    if not credentials_enabled:
        st.session_state.active_credential_profile = None
        return

    # Show profiles only if enabled
    if profiles:
        st.markdown("**Credential Profiles**")
        for idx, profile in enumerate(profiles):
            col1, col2, col3, col4 = st.columns([2, 3, 3, 0.5])

            with col1:
                profile["label"] = st.text_input(
                    "Label",
                    key=f"cred_profile_{idx}_label",
                    value=profile.get("label", ""),
                    placeholder="e.g., Admin user",
                    label_visibility="collapsed",
                )

            with col2:
                profile["username"] = st.text_input(
                    "Username",
                    key=f"cred_profile_{idx}_username",
                    value=profile.get("username", ""),
                    placeholder="email or username",
                    label_visibility="collapsed",
                )

            with col3:
                profile["password"] = st.text_input(
                    "Password",
                    key=f"cred_profile_{idx}_password",
                    value=profile.get("password", ""),
                    placeholder="password",
                    type="password",
                    label_visibility="collapsed",
                )

            with col4:
                if st.button("❌", key=f"cred_profile_{idx}_remove"):
                    profiles.pop(idx)
                    st.rerun()

        # Re-save profiles after modifications
        st.session_state.credential_profiles = profiles

    # Add profile button
    if st.button("+ Add credential profile", type="secondary"):
        profiles.append({"label": "", "username": "", "password": ""})
        st.session_state.credential_profiles = profiles
        st.rerun()

    # Active profile selector
    if profiles:
        profile_labels = [p.get("label", f"Profile {i + 1}") for i, p in enumerate(profiles)]
        active_idx = 0
        active_profile_val = st.session_state.get("active_credential_profile")
        if isinstance(active_profile_val, int) and 0 <= active_profile_val < len(profile_labels):
            active_idx = active_profile_val
            # Migrate legacy index-based value to current label-based value.
            st.session_state.active_credential_profile = profile_labels[active_idx]
        elif isinstance(active_profile_val, str) and active_profile_val in profile_labels:
            active_idx = profile_labels.index(active_profile_val)
        st.selectbox(
            "Active Profile",
            options=profile_labels,
            index=active_idx,
            key="active_credential_profile",
            label_visibility="collapsed",
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

    # ── AI-009 Phase B: Credential profiles section ────────────────────
    _render_credential_profiles_section()

    # ── AI-009 Phase B: Journey builder section ───────────────────────
    _render_journey_builder_section()

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

    content: str = ""

    def _build_credential_profiles() -> list[CredentialProfile]:
        """Build CredentialProfile objects from session state."""
        profiles_data = st.session_state.get("credential_profiles", [])
        return [
            CredentialProfile(
                label=p.get("label", ""),
                username=p.get("username", ""),
                password=p.get("password", ""),
            )
            for p in profiles_data
        ]

    def _get_active_profile_label() -> str | None:
        """Get the label of the active credential profile."""
        active_profile = st.session_state.get("active_credential_profile")
        profiles = st.session_state.get("credential_profiles", [])
        if not profiles:
            return None
        if isinstance(active_profile, str):
            return active_profile if active_profile else None
        if isinstance(active_profile, int) and 0 <= active_profile < len(profiles):
            return profiles[active_profile].get("label", "")
        # Backward-compatible default when a single profile exists
        if len(profiles) == 1:
            return profiles[0].get("label", "") or None
        return None

    input_mode = st.radio(
        "Input mode",
        options=["📄 Upload .md file", "✏️ Paste story"],
        index=0 if st.session_state.get("input_mode") == "upload" else 1,
        horizontal=True,
        key="input_mode_selector",
    )
    st.session_state.input_mode = "upload" if input_mode.startswith("📄") else "paste"

    if st.session_state.input_mode == "upload":
        feature_spec_file = st.file_uploader(
            "Upload Feature Specification (MD)",
            type=["md"],
            key="file_upload",
        )
        if feature_spec_file is not None:
            content = feature_spec_file.read().decode("utf-8")
            with st.expander("📋 Preview uploaded file", expanded=False):
                st.markdown(content)
    else:
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
            st.success("✅ Story loaded - click **Generate Tests** below.")
        elif pasted.strip():
            content = pasted

    if not content:
        st.info("👆 Upload a feature specification file or paste a user story to begin.")
        return

    # ── Parse content (shared path for both inputs) ───────────────────────────
    user_story_text, requirement_model, error = parse_feature_text(content)

    if error:
        st.error(f"Failed to parse input: {error}")
        return

    if not user_story_text:
        st.error("Couldn't find a user story. Add a '## User Story' heading or just type your story directly.")
        return

    if requirement_model is None:
        st.error("Couldn't derive a requirement model from input.")
        return

    requirement_lines = requirement_model.lines
    criteria_count = requirement_model.count
    acceptance_criteria_text = requirement_model.to_numbered_text()
    st.session_state.requirements_source = requirement_model.source

    if requirement_model.source != "acceptance_criteria":
        st.info(
            "No explicit '## Acceptance Criteria' section found. "
            "Using derived requirement lines from your pasted story so parsing, "
            "coverage, and reports stay consistent."
        )

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

        # Decision tree: journey_steps → additional_urls → single page
        journey_steps = st.session_state.get("journey_steps", [])
        credential_profiles = _build_credential_profiles() if st.session_state.get("credentials_enabled", False) else []
        active_profile_label = _get_active_profile_label() if credential_profiles else None

        if journey_steps:
            # Execute journey-based scraping (Phase B)
            with st.spinner("🗺️ Executing scraping journey..."):
                try:
                    from src.page_context_scraper import JourneyStep

                    journey_steps_objects = [
                        JourneyStep(
                            step_type=s["step_type"],
                            url=s.get("url"),
                            selector=s.get("selector"),
                            visible_text=s.get("visible_text"),
                            value=s.get("value"),
                            label=s.get("label"),
                            capture_label=s.get("capture_label"),
                        )
                        for s in journey_steps
                    ]

                    journey_result = execute_journey(
                        journey_steps=journey_steps_objects,
                        credential_profiles=credential_profiles,
                        active_profile_label=active_profile_label,
                    )

                    # Surface errors/warnings from scraper
                    for step in journey_result.failed_steps:
                        st.sidebar.warning(f"⚠️ Scraper: {step}")
                    for url in journey_result.redirected_urls:
                        st.sidebar.warning(f"⚠️ Scraper: Auth redirect detected for {url}")
                    if journey_result.error_message:
                        st.sidebar.error(f"⚠️ {journey_result.error_message}")

                    # Add captured pages
                    if journey_result.captured_pages:
                        st.sidebar.success(f"✅ Captured {len(journey_result.captured_pages)} pages from journey")
                        for page in journey_result.captured_pages:
                            st.sidebar.caption(f"  • {page.url} → {page.element_count()} elements")
                        page_context_block = MultiPageContext(
                            base_url=scrape_url,
                            pages=journey_result.captured_pages,
                        ).to_prompt_block()

                    if journey_result.success:
                        st.sidebar.success("✅ Journey completed successfully")
                    else:
                        st.sidebar.warning("⚠️ Journey completed with some failures")

                except Exception as e:
                    st.sidebar.warning(f"⚠️ Journey scraper failed: {e} — generating without page context")

        elif additional_urls:
            # AI-009 Phase A: Multi-page scraping (static URLs)
            total_pages = 1 + len(additional_urls)
            with st.spinner(f"🔍 Scraping {total_pages} pages..."):
                try:
                    multi_ctx, scraper_state = scrape_multiple_pages(
                        base_url=scrape_url,
                        additional_urls=additional_urls,
                        credential_profiles=credential_profiles,
                        active_profile_label=active_profile_label,
                        restart_from_base=True,
                        max_attempts_per_page=2,
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

        page_context_prompt = build_page_context_prompt_block(page_context_block)
        full_prompt = f"{system_prompt}\n\n{page_context_prompt}"
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

                locator_error = _validate_locator_quality(normalised_code)
                if locator_error:
                    st.error(f"❌ Generated code failed locator quality validation: {locator_error}")
                    st.code(normalised_code, language="python")
                    st.info("Try regenerating with a stronger model (dense/large) or richer page context.")
                    return

                st.session_state.saved_test_path = saved_path
                st.session_state.generated_code = normalised_code

                # Build coverage analysis
                st.session_state.coverage_analysis = build_coverage_analysis(
                    acceptance_criteria_lines=requirement_lines,
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
