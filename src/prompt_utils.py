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
- CRITICAL: Always include these imports at the top: from playwright.sync_api import Page, expect; import re
- Use pytest format: def test_name(page: Page):
- Generate descriptive test names that reflect the criterion being tested
- Include comments explaining each step
- Include assertions to validate expected outcomes
- DO NOT use async/await or asyncio
""".strip()


_PAGE_CONTEXT_RULES: Final[str] = """
CRITICAL PAGE CONTEXT REQUIREMENTS:
- YOU MUST USE ONLY THE LOCATORS LISTED IN THE PAGE CONTEXT ABOVE
- NEVER invent, guess, or create locators that are not explicitly listed
- If a required element is not in the PAGE CONTEXT, use pytest.skip() with a descriptive message instead of omitting the test
- Do not use generic fallbacks like page.locator("button") or page.get_by_text("anything")
- For navigation between pages, use direct page.goto("url") instead of clicking links
- PAGE CONTEXT may contain MULTIPLE PAGES if multi-page scraping was enabled
- Each page section shows "=== PAGE CONTEXT (scraped from URL) ==="
- If navigating to a page not in PAGE CONTEXT, either skip the test or use generic title assertions like re.compile("Page") or re.compile("Site")
- If PAGE CONTEXT is empty or missing, generate only URL navigation tests with generic assertions
- FAILURE TO USE PROVIDED LOCATORS WILL CAUSE TEST TIMEOUTS AND FAILURES
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

_PAGE_TITLE_ASSERTION_RULES: Final[str] = """
PAGE TITLE ASSERTIONS — CRITICAL:
- NEVER invent, guess, or assume page titles — this ALWAYS causes test failures
- ONLY use page title fragments that appear in the PAGE CONTEXT metadata above
- Look for "Page title : " lines in the PAGE CONTEXT and extract fragments from those actual titles
- If no PAGE CONTEXT is provided, use generic fragments like re.compile("Home") or re.compile("Page")
- Page titles in PAGE CONTEXT show actual scraped titles like "Page title : Shopping Cart | Store"
- Extract meaningful fragments like "Shopping Cart" or "Store" from these actual titles
- WRONG: expect(page).to_have_title(re.compile("Cart")) — guessing "Cart" when actual title might be "Basket"
- CORRECT: If PAGE CONTEXT shows "Page title : My Shopping Basket", use re.compile("Shopping Basket")
- ALWAYS check the PAGE CONTEXT first — never invent titles
""".strip()

_EVIDENCE_TRACKER_RULES: Final[str] = """
EVIDENCE TRACKER METHODS — CRITICAL:
- Use evidence_tracker.navigate(url) instead of page.goto(url)
  — Records step and takes entry screenshot automatically

- Use evidence_tracker.fill(locator, value, label=...) instead of
  page.locator(locator).fill(value)
  — Captures bounding box and value for overlay rendering

- Use evidence_tracker.click(locator, label=...) instead of
  page.locator(locator).click()
  — Records click position, drives circle size in annotated view

- Use evidence_tracker.assert_visible(locator, label=...) instead of
  expect(page.locator(locator)).to_be_visible()
  — Takes assertion screenshot and records matched text

- Always add @pytest.mark.evidence(condition_ref=..., story_ref=...)
  decorator to every test function
  — Links test to condition in evidence bundle and heat map

- Never call page.screenshot() directly
  — Tracker handles all screenshots; direct calls break sidecar registration

- When using pytest.skip(), include descriptive messages about missing locators or test coverage gaps
  — This creates evidence records showing what functionality couldn't be tested
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
        "CRITICAL: Return ONLY Python code. No explanations, no markdown, no analysis.\n"
        "Start with: from playwright.sync_api import Page, expect\n"
        "Then: import pytest\n"
        "Then: def test_01_...(page: Page):\n\n"
        f"{_BASE_PLAYWRIGHT_RULES}\n\n"
        f"{_TEST_ISOLATION_RULES}\n\n"
        f"{_PAGE_TITLE_ASSERTION_RULES}\n\n"
        f"{_EVIDENCE_TRACKER_RULES}\n\n"
        f"{_PAGE_CONTEXT_RULES}\n\n"
        "Generate the Python test code now (start directly with imports):"
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
        "PAGE CONTEXT (use these locators only - do not invent new ones):\n"
        f"{compact_block}\n\n"
        "APPROVED LOCATORS:\n"
        f"{approved_block}{truncation_note}\n\n"
        "CRITICAL: Use ONLY the locators listed above. If a locator you need is not listed, use pytest.skip('Required element not found in page context').\n"
    )
