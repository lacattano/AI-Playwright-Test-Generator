"""Prompt builder utilities for LLM-powered test generation.

This module centralises the core instructions used when asking the LLM
to generate Playwright pytest tests, so that different frontends can
share the same rules.
"""

from __future__ import annotations

from typing import Final

_BASE_PLAYWRIGHT_RULES: Final[str] = """
BASE REQUIREMENTS:
- Use Python and Playwright sync API for web automation
- Use pytest format: def test_name(page: Page):
- Generate descriptive test names that reflect the criterion being tested
- Include comments explaining each step
- Include assertions to validate expected outcomes
- DO NOT use async/await or asyncio
""".strip()


_PAGE_CONTEXT_RULES: Final[str] = """
IMPORTANT:
- Return ONLY the Python code, no markdown formatting, no explanations
- If PAGE CONTEXT is provided above, use ONLY the locators listed there
- Do not invent selectors that are not in the PAGE CONTEXT
- DO NOT skip the last criteria - all {count} criteria must have tests
""".strip()


_TEST_ISOLATION_RULES: Final[str] = """
TEST ISOLATION — CRITICAL:
- Each test function receives a completely FRESH browser context with NO shared state
- DO NOT assume any navigation, login, or data from a previous test function carries over
- If a test requires the user to be logged in, it MUST include the full login steps itself:
  navigate to the login page, fill credentials, submit — every time, in every test that needs it
- Never split a multi-step user flow across test functions expecting sequential execution
- Treat every test function as if it runs alone in a clean browser with nothing pre-loaded
""".strip()


def get_streamlit_system_prompt_template() -> str:
    """Return the system prompt template used by the Streamlit UI.

    The template contains ``{user_story}``, ``{criteria}``, and ``{count}``
    placeholders which are filled in by the caller.
    """
    return (
        "You are an expert Playwright automation engineer. Generate a complete, "
        "runnable Playwright test for the following user story and acceptance criteria.\n\n"
        "USER STORY:\n"
        "{user_story}\n\n"
        "ACCEPTANCE CRITERIA (enumerate them explicitly - generate ONE test per criterion):\n"
        "{criteria}\n"
        "(Total: {count} criteria)\n\n"
        "CRITICAL REQUIREMENT:\n"
        "- YOU MUST generate a SEPARATE test function for EACH of the {count} acceptance criteria listed above\n"
        "- Do NOT skip, combine, or omit any criteria\n"
        "- Each test function should be named test_<criterion_number>_<short_desc> "
        "(e.g., test_01_can_enter_driver_name)\n"
        "- The test function names must clearly correspond to the criterion number\n\n"
        f"{_BASE_PLAYWRIGHT_RULES}\n\n"
        f"{_TEST_ISOLATION_RULES}\n\n"
        f"{_PAGE_CONTEXT_RULES}\n\n"
        "Generate the Playwright test code now:"
    )
