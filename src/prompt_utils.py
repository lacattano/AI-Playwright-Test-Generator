"""Prompt builder utilities for LLM-powered test generation.

This module centralises the core instructions used when asking the LLM
to generate Playwright pytest tests, so that different frontends can
share the same rules.
"""

from __future__ import annotations

import re
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
- If PAGE CONTEXT includes concrete page URLs, use those URLs exactly in assertions/navigation
- Do not invent selectors that are not in the PAGE CONTEXT
- For assertions after navigation, use `expect(page).to_have_url()` or `expect(page).to_have_title()` instead of making up element IDs like `#react-basics`
- Prefer positive URL assertions for target pages; avoid weak negative-only checks like `not_to_have_url(...)`
- Avoid brittle exact base-homepage URL assertions immediately after initial `page.goto(...)`
- Never use broad locators like `page.locator("button")` or `page.locator("a")`
- Never suppress failures with `try/except: pass` in generated tests
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

_MAX_PAGE_CONTEXT_CHARS: Final[int] = 8000
_MAX_APPROVED_LOCATORS: Final[int] = 80
_MAX_APPROVED_LOCATORS_CHARS: Final[int] = 3500


def _locator_priority(locator: str) -> int:
    """Lower score means higher preference for stable test locators."""
    if "get_by_test_id" in locator:
        return 0
    if 'locator("#' in locator:
        return 1
    if "locator(\"[name='" in locator:
        return 2
    if "get_by_role" in locator or "get_by_label" in locator:
        return 3
    if "get_by_text" in locator:
        return 4
    return 5


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


def build_page_context_prompt_block(page_context_block: str) -> str:
    """Build strict page-context instructions appended to the generation prompt."""
    stripped_block = page_context_block.strip()
    if not stripped_block:
        return (
            "### PAGE CONTEXT\n"
            "(No context available)\n"
            "### END PAGE CONTEXT\n\n"
            "### GENERATION INSTRUCTIONS:\n"
            "- No PAGE CONTEXT is available; prefer robust role- and label-based locators.\n"
            '- Avoid brittle generic selectors like `page.locator("button")` or `page.locator("input")`.\n'
        )

    was_truncated = False
    compact_block = stripped_block
    if len(compact_block) > _MAX_PAGE_CONTEXT_CHARS:
        compact_block = compact_block[:_MAX_PAGE_CONTEXT_CHARS].rstrip()
        was_truncated = True

    locator_candidates = re.findall(r"→\s*(page\.[^\n]+)", stripped_block)
    approved_locators: list[str] = []
    for locator in locator_candidates:
        clean_locator = locator.strip()
        if clean_locator and clean_locator not in approved_locators:
            approved_locators.append(clean_locator)

    approved_locators.sort(key=_locator_priority)
    selected_locators: list[str] = []
    selected_chars = 0
    for locator in approved_locators:
        if len(selected_locators) >= _MAX_APPROVED_LOCATORS:
            break
        line = f"- {locator}"
        projected = selected_chars + len(line) + 1
        if projected > _MAX_APPROVED_LOCATORS_CHARS:
            break
        selected_locators.append(locator)
        selected_chars = projected

    locator_lines = "\n".join(f"- {locator}" for locator in selected_locators)
    approved_block = locator_lines if locator_lines else "- (No explicit locator recommendations extracted)"
    truncation_note = ""
    if was_truncated:
        truncation_note = (
            f"\n\nNOTE: PAGE CONTEXT was truncated to {_MAX_PAGE_CONTEXT_CHARS} chars "
            "to keep Ollama requests responsive."
        )

    return (
        "### PAGE CONTEXT\n"
        f"{compact_block}\n"
        "### END PAGE CONTEXT\n\n"
        "### APPROVED LOCATORS (from PAGE CONTEXT)\n"
        f"{approved_block}{truncation_note}\n\n"
        "### GENERATION INSTRUCTIONS:\n"
        "- Use the APPROVED LOCATORS exactly as written when they satisfy a step.\n"
        "- If PAGE CONTEXT exists, never invent new CSS/XPath selectors.\n"
        "- Use only page URLs that appear in PAGE CONTEXT. Do not invent alternate URL variants.\n"
        '- Do NOT use broad fallback selectors such as `page.locator("button")`, `page.locator("input")`, or bare tag locators.\n'
        "- Prefer positive URL assertions for expected destinations instead of negative-only URL checks.\n"
        "- For navigation assertions, use `expect(page).to_have_url()` or `expect(page).to_have_title()`.\n"
    )
