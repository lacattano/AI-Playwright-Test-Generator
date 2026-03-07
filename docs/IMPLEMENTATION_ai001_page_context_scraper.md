# AI-001 — Page Context Scraper
## Implementation Document

**Status:** Ready for implementation  
**New file:** `src/page_context_scraper.py`  
**Modified file:** `streamlit_app.py`  
**Protected files touched:** None  

---

## Objective

Before calling the LLM, visit the target URL with a headless Playwright
browser, extract all interactive elements, and inject the real DOM structure
into the prompt so the LLM uses real locators instead of inventing them.

Scraper failure is **non-fatal** — if the URL is unreachable for any reason,
generation continues exactly as it does today with a warning shown to the user.

---

## Architecture Decision

The `PageContext` is injected into the prompt string inside
`generate_test_for_story()` in `streamlit_app.py`.

`src/test_generator.py` is **NOT modified** — it is a protected file and the
Streamlit UI already owns the full generation pipeline.

```
User clicks Generate
        │
        ▼
scrape_page_context(base_url)        ← NEW: src/page_context_scraper.py
        │
        ├── success → PageContext.to_prompt_block() prepended to prompt
        └── failure → warning shown, generation continues without context
        │
        ▼
generate_test_for_story(prompt_text, base_url, llm_client, page_context)
        │
        ▼
llm_client.generate_test(prompt)     ← prompt now includes real selectors
```

---

## New File: `src/page_context_scraper.py`

### Data Classes

```python
"""
page_context_scraper.py — Extract interactive elements from a live page.

Uses a headless Playwright browser to visit the target URL and return
a structured PageContext for injection into the LLM prompt.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from playwright.sync_api import Page, TimeoutError as PWTimeout, sync_playwright


@dataclass
class PageElement:
    """A single interactive element extracted from the page."""

    tag: str                              # input, button, a, select, textarea
    role: Optional[str] = None            # ARIA role
    label: Optional[str] = None          # aria-label or associated <label> text
    test_id: Optional[str] = None        # data-testid value
    element_id: Optional[str] = None     # id attribute
    name: Optional[str] = None           # name attribute
    placeholder: Optional[str] = None   # placeholder text
    visible_text: Optional[str] = None  # innerText (buttons/links)
    input_type: Optional[str] = None    # text, password, email, checkbox, etc.
    is_required: bool = False
    recommended_locator: Optional[str] = None  # pre-built Playwright locator


@dataclass
class PageContext:
    """Structured summary of a page's interactive elements."""

    url: str
    page_title: str
    h1_text: Optional[str]
    elements: list[PageElement] = field(default_factory=list)
    forms: list[list[PageElement]] = field(default_factory=list)
    scraped_at: str = ""
    scrape_duration_ms: int = 0

    def element_count(self) -> int:
        """Return total number of interactive elements found."""
        return len(self.elements)

    def to_prompt_block(self) -> str:
        """
        Format page context as a plain-text block for LLM prompt injection.

        Returns a string ready to prepend to the user story prompt.
        """
        lines: list[str] = []
        lines.append(f"=== PAGE CONTEXT (scraped from {self.url}) ===")
        lines.append(f"Page title : {self.page_title}")
        if self.h1_text:
            lines.append(f"H1         : {self.h1_text}")
        lines.append("")
        lines.append("INTERACTIVE ELEMENTS:")

        for el in self.elements:
            parts = [f"  [{el.tag}]"]
            if el.label:
                parts.append(f'aria-label="{el.label}"')
            if el.test_id:
                parts.append(f'data-testid="{el.test_id}"')
            if el.element_id:
                parts.append(f'id="{el.element_id}"')
            if el.name:
                parts.append(f'name="{el.name}"')
            if el.input_type:
                parts.append(f"type={el.input_type}")
            if el.placeholder:
                parts.append(f'placeholder="{el.placeholder}"')
            if el.visible_text:
                parts.append(f'visible="{el.visible_text}"')
            if el.is_required:
                parts.append("required=true")
            if el.recommended_locator:
                parts.append(f"→ {el.recommended_locator}")
            lines.append("  ".join(parts))

        if self.forms:
            lines.append("")
            lines.append(f"FORMS: {len(self.forms)} form(s) detected")
            for i, form_elements in enumerate(self.forms, 1):
                ids = [
                    el.element_id or el.name or el.label or el.tag
                    for el in form_elements
                ]
                lines.append(f"  Form {i}: {', '.join(str(x) for x in ids if x)}")

        lines.append("")
        lines.append("USE THESE LOCATORS. Do not invent selectors not listed above.")
        lines.append("=" * 60)
        return "\n".join(lines)
```

---

### Locator Priority Helper

```python
def _build_recommended_locator(el_tag: str, el: dict[str, Optional[str]]) -> str:
    """
    Build the best Playwright locator for an element based on priority:
      1. data-testid  → page.get_by_test_id("x")
      2. aria-label   → page.get_by_role("button", name="x")
      3. id           → page.locator("#x")
      4. name         → page.locator("[name='x']")
      5. visible text → page.get_by_text("x")    ← least preferred

    Args:
        el_tag: HTML tag name (input, button, a, etc.)
        el: dict of element attributes

    Returns:
        Playwright locator string
    """
    if el.get("test_id"):
        return f'page.get_by_test_id("{el["test_id"]}")'
    if el.get("label"):
        if el_tag in ("button", "a", "input", "select", "textarea"):
            return f'page.get_by_role("{el_tag}", name="{el["label"]}")'
        return f'page.get_by_label("{el["label"]}")'
    if el.get("element_id"):
        return f'page.locator("#{el["element_id"]}")'
    if el.get("name"):
        return f"page.locator(\"[name='{el['name']}']\")"
    if el.get("visible_text"):
        return f'page.get_by_text("{el["visible_text"]}")'
    return f"page.locator(\"{el_tag}\")"
```

---

### Main Scraper Function

```python
def scrape_page_context(
    url: str,
    timeout_ms: int = 10_000,
) -> tuple[Optional[PageContext], Optional[str]]:
    """
    Visit url with a headless browser and extract interactive elements.

    This function is non-fatal — all errors are caught and returned as
    a human-readable string so the caller can fall back gracefully.

    Args:
        url:        The page URL to scrape
        timeout_ms: Navigation timeout in milliseconds (default 10s)

    Returns:
        (PageContext, None)       on success
        (None, error_message)    on any failure
    """
    start = time.monotonic()

    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            page = browser.new_page()

            try:
                page.goto(url, timeout=timeout_ms, wait_until="domcontentloaded")
            except PWTimeout:
                browser.close()
                return None, f"Timed out connecting to {url} — generating without page context"
            except Exception as e:
                browser.close()
                return None, f"Could not reach {url}: {e} — generating without page context"

            context = _extract_context(page, url)
            browser.close()

        duration_ms = int((time.monotonic() - start) * 1000)
        context.scrape_duration_ms = duration_ms
        context.scraped_at = datetime.now(timezone.utc).isoformat()
        return context, None

    except Exception as e:
        return None, f"Scraper error: {e} — generating without page context"


def _extract_context(page: Page, url: str) -> PageContext:
    """
    Extract page title, H1, and all interactive elements from a loaded page.

    Args:
        page: Playwright Page object (already navigated to URL)
        url:  The URL that was scraped (for context metadata)

    Returns:
        Populated PageContext dataclass
    """
    # Page metadata
    page_title = page.title() or ""
    h1_text: Optional[str] = None
    h1 = page.query_selector("h1")
    if h1:
        h1_text = h1.inner_text().strip() or None

    elements: list[PageElement] = []

    # ── Inputs ────────────────────────────────────────────────────────────
    for handle in page.query_selector_all("input:not([type='hidden'])"):
        attrs = {
            "element_id": handle.get_attribute("id"),
            "name":        handle.get_attribute("name"),
            "label":       handle.get_attribute("aria-label"),
            "test_id":     handle.get_attribute("data-testid"),
            "placeholder": handle.get_attribute("placeholder"),
            "input_type":  handle.get_attribute("type") or "text",
            "visible_text": None,
        }
        # Try to find associated <label> if no aria-label
        if not attrs["label"] and attrs["element_id"]:
            label_el = page.query_selector(f'label[for="{attrs["element_id"]}"]')
            if label_el:
                attrs["label"] = label_el.inner_text().strip() or None

        elements.append(PageElement(
            tag="input",
            role=handle.get_attribute("role"),
            label=attrs["label"],
            test_id=attrs["test_id"],
            element_id=attrs["element_id"],
            name=attrs["name"],
            placeholder=attrs["placeholder"],
            input_type=attrs["input_type"],
            is_required=handle.get_attribute("required") is not None,
            recommended_locator=_build_recommended_locator("input", attrs),
        ))

    # ── Buttons ───────────────────────────────────────────────────────────
    for handle in page.query_selector_all("button, input[type='submit'], input[type='button']"):
        visible = handle.inner_text().strip() or handle.get_attribute("value") or None
        attrs = {
            "element_id":   handle.get_attribute("id"),
            "name":         handle.get_attribute("name"),
            "label":        handle.get_attribute("aria-label") or visible,
            "test_id":      handle.get_attribute("data-testid"),
            "visible_text": visible,
            "input_type":   None,
            "placeholder":  None,
        }
        elements.append(PageElement(
            tag="button",
            role=handle.get_attribute("role") or "button",
            label=attrs["label"],
            test_id=attrs["test_id"],
            element_id=attrs["element_id"],
            name=attrs["name"],
            visible_text=attrs["visible_text"],
            recommended_locator=_build_recommended_locator("button", attrs),
        ))

    # ── Select dropdowns ──────────────────────────────────────────────────
    for handle in page.query_selector_all("select"):
        attrs = {
            "element_id": handle.get_attribute("id"),
            "name":       handle.get_attribute("name"),
            "label":      handle.get_attribute("aria-label"),
            "test_id":    handle.get_attribute("data-testid"),
            "visible_text": None,
            "input_type": None,
            "placeholder": None,
        }
        if not attrs["label"] and attrs["element_id"]:
            label_el = page.query_selector(f'label[for="{attrs["element_id"]}"]')
            if label_el:
                attrs["label"] = label_el.inner_text().strip() or None

        elements.append(PageElement(
            tag="select",
            label=attrs["label"],
            test_id=attrs["test_id"],
            element_id=attrs["element_id"],
            name=attrs["name"],
            recommended_locator=_build_recommended_locator("select", attrs),
        ))

    # ── Textareas ─────────────────────────────────────────────────────────
    for handle in page.query_selector_all("textarea"):
        attrs = {
            "element_id":  handle.get_attribute("id"),
            "name":        handle.get_attribute("name"),
            "label":       handle.get_attribute("aria-label"),
            "test_id":     handle.get_attribute("data-testid"),
            "placeholder": handle.get_attribute("placeholder"),
            "visible_text": None,
            "input_type":  None,
        }
        if not attrs["label"] and attrs["element_id"]:
            label_el = page.query_selector(f'label[for="{attrs["element_id"]}"]')
            if label_el:
                attrs["label"] = label_el.inner_text().strip() or None

        elements.append(PageElement(
            tag="textarea",
            label=attrs["label"],
            test_id=attrs["test_id"],
            element_id=attrs["element_id"],
            name=attrs["name"],
            placeholder=attrs["placeholder"],
            recommended_locator=_build_recommended_locator("textarea", attrs),
        ))

    # ── Forms (group inputs by parent <form>) ─────────────────────────────
    forms: list[list[PageElement]] = []
    for form_handle in page.query_selector_all("form"):
        form_elements: list[PageElement] = []
        for child in form_handle.query_selector_all(
            "input:not([type='hidden']), button, select, textarea"
        ):
            el_id = child.get_attribute("id")
            matched = [e for e in elements if e.element_id and e.element_id == el_id]
            if matched:
                form_elements.extend(matched)
        if form_elements:
            forms.append(form_elements)

    return PageContext(
        url=url,
        page_title=page_title,
        h1_text=h1_text,
        elements=elements,
        forms=forms,
    )
```

---

## Changes to `streamlit_app.py`

### 1. Add import

```python
from src.page_context_scraper import PageContext, scrape_page_context
```

Add this alongside the existing `src` imports at the top.

### 2. Add `page_context` parameter to `generate_test_for_story`

Change the function signature and prompt construction:

```python
def generate_test_for_story(
    prompt_text: str,
    base_url: str,
    llm_client: LLMClient,
    page_context: Optional[PageContext] = None,   # ← new
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

    prompt = f"""{context_block}You are an expert Playwright automation engineer. Generate a complete, runnable Playwright test for the following user story.

USER STORY:
{prompt_text}

BASE URL:
{base_url}

Requirements:
- Use Python and Playwright sync API for web automation
- Use pytest format: def test_name(page: Page):
- Test should cover the main acceptance criteria from the user story
- Use descriptive test names
- Include comments explaining each step
- Include assertions to validate expected outcomes
- DO NOT use async/await or asyncio

IMPORTANT:
- Return ONLY the Python code, no markdown formatting, no explanations
- If PAGE CONTEXT is provided above, use ONLY the locators listed there
- Do not invent selectors that are not in the PAGE CONTEXT

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
```

### 3. Add scraper step in `main()` before generation

Replace this existing block in `main()`:

```python
    if generate_btn and user_story:
        # Clear previous save state before starting new generation
        st.session_state.saved_test_path = None
        st.session_state.test_filename = None
        st.session_state.last_generated_at = None

        # Generate test
        test_code = generate_test_for_story(user_story, base_url, llm_client)
```

With this:

```python
    if generate_btn and user_story:
        # Clear previous save state before starting new generation
        st.session_state.saved_test_path = None
        st.session_state.test_filename = None
        st.session_state.last_generated_at = None

        # Scrape page context if URL provided
        page_context: Optional[PageContext] = None
        if base_url:
            with st.spinner("🔍 Scanning page for elements…"):
                page_context, scrape_error = scrape_page_context(base_url)
            if scrape_error:
                st.warning(f"⚠️ {scrape_error}")
                _log(f"Scraper: {scrape_error}", "warn")
            else:
                assert page_context is not None
                _log(
                    f"Scraped {page_context.element_count()} elements "
                    f"in {page_context.scrape_duration_ms}ms",
                    "ok",
                )

        # Generate test
        test_code = generate_test_for_story(user_story, base_url, llm_client, page_context)
```

### 4. Add `page_context` to `_session_defaults`

Add these two keys to the `_session_defaults` dict:

```python
    "page_context": None,          # PageContext from last scrape
    "scrape_duration_ms": 0,       # How long the last scrape took
```

---

## Unit Tests: `tests/test_page_context_scraper.py`

All tests use pytest sync format, no async.

```python
"""Unit tests for src/page_context_scraper.py

Tests cover:
- PageElement dataclass construction
- PageContext.to_prompt_block() output format
- _build_recommended_locator() priority logic
- scrape_page_context() error handling (mocked — no live browser needed)
"""

import pytest
from unittest.mock import MagicMock, patch
from src.page_context_scraper import (
    PageContext,
    PageElement,
    _build_recommended_locator,
    scrape_page_context,
)


class TestBuildRecommendedLocator:

    def test_prefers_test_id_over_all(self) -> None:
        el = {"test_id": "submit-btn", "label": "Submit", "element_id": "btn1",
              "name": None, "visible_text": None, "input_type": None, "placeholder": None}
        assert _build_recommended_locator("button", el) == 'page.get_by_test_id("submit-btn")'

    def test_prefers_label_over_id(self) -> None:
        el = {"test_id": None, "label": "Driver Name", "element_id": "driverNameInput",
              "name": None, "visible_text": None, "input_type": None, "placeholder": None}
        result = _build_recommended_locator("input", el)
        assert 'get_by_role("input", name="Driver Name")' in result

    def test_falls_back_to_id(self) -> None:
        el = {"test_id": None, "label": None, "element_id": "driverNameInput",
              "name": None, "visible_text": None, "input_type": None, "placeholder": None}
        assert _build_recommended_locator("input", el) == 'page.locator("#driverNameInput")'

    def test_falls_back_to_name(self) -> None:
        el = {"test_id": None, "label": None, "element_id": None,
              "name": "username", "visible_text": None, "input_type": None, "placeholder": None}
        assert _build_recommended_locator("input", el) == "page.locator(\"[name='username']\")"

    def test_falls_back_to_visible_text(self) -> None:
        el = {"test_id": None, "label": None, "element_id": None,
              "name": None, "visible_text": "Add Driver", "input_type": None, "placeholder": None}
        assert _build_recommended_locator("button", el) == 'page.get_by_text("Add Driver")'

    def test_falls_back_to_tag_only(self) -> None:
        el = {"test_id": None, "label": None, "element_id": None,
              "name": None, "visible_text": None, "input_type": None, "placeholder": None}
        result = _build_recommended_locator("button", el)
        assert "button" in result


class TestPageContextToPromptBlock:

    def test_contains_url(self) -> None:
        ctx = PageContext(url="http://localhost:8080", page_title="Test Page", h1_text=None)
        block = ctx.to_prompt_block()
        assert "http://localhost:8080" in block

    def test_contains_page_title(self) -> None:
        ctx = PageContext(url="http://example.com", page_title="My App", h1_text=None)
        block = ctx.to_prompt_block()
        assert "My App" in block

    def test_contains_h1_when_present(self) -> None:
        ctx = PageContext(url="http://example.com", page_title="App", h1_text="Welcome")
        block = ctx.to_prompt_block()
        assert "Welcome" in block

    def test_omits_h1_line_when_none(self) -> None:
        ctx = PageContext(url="http://example.com", page_title="App", h1_text=None)
        block = ctx.to_prompt_block()
        assert "H1" not in block

    def test_contains_element_details(self) -> None:
        el = PageElement(
            tag="input",
            label="Driver Name",
            element_id="driverNameInput",
            input_type="text",
            recommended_locator='page.locator("#driverNameInput")',
        )
        ctx = PageContext(url="http://example.com", page_title="App", h1_text=None, elements=[el])
        block = ctx.to_prompt_block()
        assert "driverNameInput" in block
        assert "Driver Name" in block

    def test_contains_do_not_invent_instruction(self) -> None:
        ctx = PageContext(url="http://example.com", page_title="App", h1_text=None)
        block = ctx.to_prompt_block()
        assert "Do not invent" in block

    def test_empty_elements_still_valid(self) -> None:
        ctx = PageContext(url="http://example.com", page_title="App", h1_text=None)
        block = ctx.to_prompt_block()
        assert "INTERACTIVE ELEMENTS:" in block

    def test_form_count_shown(self) -> None:
        el = PageElement(tag="input", element_id="emailInput")
        ctx = PageContext(
            url="http://example.com",
            page_title="App",
            h1_text=None,
            elements=[el],
            forms=[[el]],
        )
        block = ctx.to_prompt_block()
        assert "1 form" in block


class TestScrapePageContextErrorHandling:

    @patch("src.page_context_scraper.sync_playwright")
    def test_returns_none_and_message_on_timeout(self, mock_pw: MagicMock) -> None:
        from playwright.sync_api import TimeoutError as PWTimeout
        mock_pw.return_value.__enter__.return_value.chromium.launch.return_value \
            .new_page.return_value.goto.side_effect = PWTimeout("timeout")
        ctx, error = scrape_page_context("http://localhost:9999")
        assert ctx is None
        assert error is not None
        assert "generating without page context" in error.lower()

    @patch("src.page_context_scraper.sync_playwright")
    def test_returns_none_and_message_on_connection_error(self, mock_pw: MagicMock) -> None:
        mock_pw.return_value.__enter__.return_value.chromium.launch.return_value \
            .new_page.return_value.goto.side_effect = Exception("Connection refused")
        ctx, error = scrape_page_context("http://localhost:9999")
        assert ctx is None
        assert error is not None

    @patch("src.page_context_scraper.sync_playwright")
    def test_returns_none_on_unexpected_exception(self, mock_pw: MagicMock) -> None:
        mock_pw.side_effect = Exception("Playwright not installed")
        ctx, error = scrape_page_context("http://example.com")
        assert ctx is None
        assert error is not None


class TestPageContextElementCount:

    def test_element_count_empty(self) -> None:
        ctx = PageContext(url="http://example.com", page_title="App", h1_text=None)
        assert ctx.element_count() == 0

    def test_element_count_with_elements(self) -> None:
        elements = [PageElement(tag="input"), PageElement(tag="button")]
        ctx = PageContext(
            url="http://example.com",
            page_title="App",
            h1_text=None,
            elements=elements,
        )
        assert ctx.element_count() == 2
```

---

## Integration Checklist

Work through these in order. Run `pytest -v` after each step before moving on.

- [ ] Create `src/page_context_scraper.py` with all functions above
- [ ] Create `tests/test_page_context_scraper.py` with all tests above
- [ ] Run `pytest tests/test_page_context_scraper.py -v` — all tests green before touching `streamlit_app.py`
- [ ] Add `from src.page_context_scraper import PageContext, scrape_page_context` to `streamlit_app.py`
- [ ] Add `Optional` to the imports if not already present (`from typing import Optional`)
- [ ] Update `generate_test_for_story()` signature and prompt construction
- [ ] Add scraper step in `main()` before the generation call
- [ ] Add `page_context` and `scrape_duration_ms` to `_session_defaults`
- [ ] Run `pytest -v` — all existing tests still green
- [ ] Run `ruff check . && ruff format --check .` — no errors
- [ ] Manual test: start mock site with `bash launch_dev.sh`, generate a test — verify log shows element count
- [ ] Manual test: enter an unreachable URL — verify warning shown and generation still completes
- [ ] Commit

---

## Error Handling Summary

| Scenario | What happens |
|----------|-------------|
| URL unreachable / refused | `scrape_page_context` returns `(None, message)` — warning shown, generation continues |
| Navigation timeout (>10s) | Same as above |
| Playwright not installed | Same as above — caught by outer `except Exception` |
| 401 / 403 / redirect to login | Page loads but elements may be from login form — context still injected, LLM uses what it finds |
| Empty page (no interactive elements) | `PageContext` returned with empty `elements` list — `to_prompt_block()` still valid |
| `base_url` field empty in UI | Scraper step skipped entirely — `page_context=None` passed to generator |

---

## Success Criteria (from spec)

- [ ] Scraper visits a URL and returns a populated `PageContext`
- [ ] `PageContext.to_prompt_block()` produces clean, readable output
- [ ] LLM uses real locators from context instead of inventing them
- [ ] Scraper failure is non-fatal — generation still works without it
- [ ] Generated test for mock insurance site passes without manual locator edits
- [ ] Unit tests for scraper in `tests/test_page_context_scraper.py`
- [ ] Scrape adds < 3 seconds to total generation time

---

*Created: 2026-03-06*
