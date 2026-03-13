"""Unit tests for prompt utilities."""

from __future__ import annotations

from src.prompt_utils import get_streamlit_system_prompt_template


def test_streamlit_prompt_contains_placeholders() -> None:
    """Template should contain expected placeholders."""
    template = get_streamlit_system_prompt_template()
    assert "{user_story}" in template
    assert "{criteria}" in template
    assert "{count}" in template


def test_streamlit_prompt_mentions_pytest_and_sync() -> None:
    """Template should instruct pytest sync Playwright usage."""
    template = get_streamlit_system_prompt_template().lower()
    assert "pytest format" in template
    assert "sync api" in template or "sync" in template
    assert "async/await" in template


def test_streamlit_prompt_mentions_page_context_rules() -> None:
    """Template should include PAGE CONTEXT locator constraints."""
    template = get_streamlit_system_prompt_template()
    assert "PAGE CONTEXT" in template
    assert "locators listed there" in template or "do not invent selectors" in template


def test_streamlit_prompt_enforces_test_isolation() -> None:
    """Template must instruct the LLM that each test runs in a fresh browser context.

    This prevents the LLM from generating tests that assume state from previous
    test functions (e.g. assuming a login from test_01 persists into test_02).
    """
    template = get_streamlit_system_prompt_template()
    assert "FRESH browser context" in template
    assert "login" in template.lower()
    assert "fresh" in template.lower()


def test_streamlit_prompt_format_resolves_without_error() -> None:
    """Calling .format() with the three expected keys must not raise KeyError.

    Guards against accidental bare braces introduced into the template constants
    that would cause a runtime crash when the prompt is rendered.
    """
    template = get_streamlit_system_prompt_template()
    rendered = template.format(user_story="story", criteria="- do thing", count=3)
    assert "story" in rendered
    assert "do thing" in rendered
