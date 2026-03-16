"""
page_context_scraper.py — Extract interactive elements from a live page.

Uses a headless Playwright browser to visit the target URL and return
a structured PageContext for injection into the LLM prompt.

Supports:
- Single page scraping (Phase A)
- Multi-page scraping (Phase A - multiple static URLs)
- Journey scraping (Phase B - placeholder for navigation-based workflows)
"""

import argparse
import json
import subprocess
import sys
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal

from playwright.sync_api import Page, sync_playwright
from playwright.sync_api import TimeoutError as PWTimeout

# ============================================================================
# Core Data Classes (existing)
# ============================================================================


@dataclass
class PageElement:
    """A single interactive element extracted from the page."""

    tag: str  # input, button, a, select, textarea
    role: str | None = None  # ARIA role
    label: str | None = None  # aria-label or associated <label> text
    test_id: str | None = None  # data-testid value
    element_id: str | None = None  # id attribute
    name: str | None = None  # name attribute
    placeholder: str | None = None  # placeholder text
    visible_text: str | None = None  # innerText (buttons/links)
    input_type: str | None = None  # text, password, email, checkbox, etc.
    is_required: bool = False
    recommended_locator: str | None = None  # pre-built Playwright locator


@dataclass
class PageContext:
    """Structured summary of a page's interactive elements."""

    url: str
    page_title: str
    h1_text: str | None
    elements: list[PageElement] = field(default_factory=list)
    forms: list[list[PageElement]] = field(default_factory=list)
    scraped_at: str = ""
    scrape_duration_ms: int = 0

    def element_count(self) -> int:
        """Return total number of interactive elements found."""
        return len(self.elements)

    def to_dict(self) -> dict[str, Any]:
        """Serialize PageContext to a dictionary."""
        return {
            "url": self.url,
            "page_title": self.page_title,
            "h1_text": self.h1_text,
            "elements": [asdict(e) for e in self.elements],
            "forms": [[asdict(e) for e in f] for f in self.forms],
            "scraped_at": self.scraped_at,
            "scrape_duration_ms": self.scrape_duration_ms,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PageContext":
        """Deserialize PageContext from a dictionary."""
        context = cls(
            url=data["url"],
            page_title=data["page_title"],
            h1_text=data.get("h1_text"),
        )
        # Safely extract elements, ignoring extra keys during dict instantiation
        context.elements = [
            PageElement(
                tag=e.get("tag", "input"),
                role=e.get("role"),
                label=e.get("label"),
                test_id=e.get("test_id"),
                element_id=e.get("element_id"),
                name=e.get("name"),
                placeholder=e.get("placeholder"),
                visible_text=e.get("visible_text"),
                input_type=e.get("input_type"),
                is_required=e.get("is_required", False),
                recommended_locator=e.get("recommended_locator"),
            )
            for e in data.get("elements", [])
        ]
        context.forms = [
            [
                PageElement(
                    tag=e.get("tag", "input"),
                    role=e.get("role"),
                    label=e.get("label"),
                    test_id=e.get("test_id"),
                    element_id=e.get("element_id"),
                    name=e.get("name"),
                    placeholder=e.get("placeholder"),
                    visible_text=e.get("visible_text"),
                    input_type=e.get("input_type"),
                    is_required=e.get("is_required", False),
                    recommended_locator=e.get("recommended_locator"),
                )
                for e in form
            ]
            for form in data.get("forms", [])
        ]
        context.scraped_at = data.get("scraped_at", "")
        context.scrape_duration_ms = data.get("scrape_duration_ms", 0)
        return context

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
                ids = [el.element_id or el.name or el.label or el.tag for el in form_elements]
                lines.append(f"  Form {i}: {', '.join(str(x) for x in ids if x)}")

        lines.append("")
        lines.append("USE THESE LOCATORS. Do not invent selectors not listed above.")
        lines.append("=" * 60)
        return "\n".join(lines)


# ============================================================================
# Multi-Page Scraping Data Classes (AI-010 - Phase A & B future-proofing)
# ============================================================================


@dataclass
class ScraperState:
    """
    Serializable state for multi-page scraper in Streamlit session_state.

    Uses only JSON-serializable types for safe storage.
    """

    status: Literal["idle", "scraping", "complete", "error"]
    current_page_index: int
    total_pages: int
    progress_percentage: float
    completed_urls: list[str]
    failed_urls: list[str]
    error_message: str | None = None
    started_at: str | None = None
    completed_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to JSON-safe dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ScraperState":
        """Deserialize from JSON-safe dictionary."""
        return cls(
            status=data["status"],
            current_page_index=data.get("current_page_index", 0),
            total_pages=data.get("total_pages", 0),
            progress_percentage=data.get("progress_percentage", 0.0),
            completed_urls=data.get("completed_urls", []),
            failed_urls=data.get("failed_urls", []),
            error_message=data.get("error_message"),
            started_at=data.get("started_at"),
            completed_at=data.get("completed_at"),
        )

    @classmethod
    def initial(cls, total_pages: int) -> "ScraperState":
        """Create initial state for a new scraping job."""
        return cls(
            status="idle",
            current_page_index=0,
            total_pages=total_pages,
            progress_percentage=0.0,
            completed_urls=[],
            failed_urls=[],
        )

    @classmethod
    def in_progress(cls, **kwargs: Any) -> "ScraperState":
        """Create state representing active scraping."""
        return cls(
            status="scraping",
            started_at=datetime.now(UTC).isoformat(),
            **kwargs,
        )


@dataclass
class MultiPageContext:
    """
    Collection of page contexts from multi-page scraping.

    Holds multiple PageContexts with summary statistics for prompt injection.
    """

    base_url: str
    pages: list[PageContext] = field(default_factory=list)
    total_elements: int = 0
    total_forms: int = 0
    scrape_duration_ms: int = 0

    def add_page(self, context: PageContext) -> None:
        """Add a successfully scraped page context."""
        self.pages.append(context)

    @property
    def success_count(self) -> int:
        """Number of pages successfully scraped."""
        return len(self.pages)

    @property
    def is_empty(self) -> bool:
        """True if no pages were scraped."""
        return len(self.pages) == 0

    def to_prompt_block(self) -> str:
        """
        Generate combined prompt block for all pages.

        Includes summary header followed by individual page contexts.
        """
        lines: list[str] = []
        lines.append("=" * 70)
        lines.append("MULTI-PAGE CONTEXT INJECTED (AI-010)")
        lines.append(f"Base URL     : {self.base_url}")
        lines.append(f"Pages scraped: {self.success_count}")
        lines.append(f"Total elements found: {self.total_elements}")
        lines.append(f"Total forms detected: {self.total_forms}")
        lines.append("=" * 70)
        lines.append("")

        # Add each page's context
        for i, page_ctx in enumerate(self.pages, 1):
            lines.append(f"--- PAGE {i}: {page_ctx.url} ---")
            lines.append(page_ctx.to_prompt_block())
            lines.append("")

        return "\n".join(lines)


# ============================================================================
# Scraper Functions
# ============================================================================


def _build_recommended_locator(el_tag: str, el: dict[str, str | None]) -> str:
    """
    Build the best Playwright locator for an element based on priority:
      1. data-testid  → page.get_by_test_id("x")             (most explicit)
      2. id           → page.locator("#x")
      3. name         → page.locator("[name='x']")
      4. aria-label   → page.get_by_role("button", name="x") / page.get_by_label("x")
      5. visible text → page.get_by_text("x")                (least preferred)

    test_id is ranked above element_id to align with Playwright's recommended
    testing philosophy: dedicated test hooks are more stable than incidental IDs.

    Args:
        el_tag: HTML tag name (input, button, a, etc.)
        el: dict of element attributes

    Returns:
        Playwright locator string
    """
    # Prefer test IDs over IDs when both are available to align with
    # Playwright's recommended patterns, but fall back to IDs when no
    # dedicated test hook exists.
    if el.get("test_id"):
        return f'page.get_by_test_id("{el["test_id"]}")'
    if el.get("element_id"):
        return f'page.locator("#{el["element_id"]}")'
    if el.get("name"):
        return f"page.locator(\"[name='{el['name']}']\")"
    if el.get("label"):
        if el_tag in ("button", "a", "input", "select", "textarea"):
            return f'page.get_by_role("{el_tag}", name="{el["label"]}")'
        return f'page.get_by_label("{el["label"]}")'
    if el.get("visible_text"):
        return f'page.get_by_text("{el["visible_text"]}")'
    return f'page.locator("{el_tag}")'


def scrape_page_context(
    url: str,
    timeout_ms: int = 10_000,
) -> tuple[PageContext | None, str | None]:
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
        # Run playwright in a completely separate subprocess to bypass Streamlit's
        # background thread quirks with Windows ProactorEventLoop
        result = subprocess.run(
            [sys.executable, __file__, url, "--timeout", str(timeout_ms)],
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode != 0:
            return None, f"Scraper subprocess failed: {result.stderr.strip()}"

        try:
            data = json.loads(result.stdout)
            if "error" in data:
                return None, str(data["error"])

            context = PageContext.from_dict(data["context"])
            duration_ms = int((time.monotonic() - start) * 1000)
            context.scrape_duration_ms = duration_ms
            context.scraped_at = datetime.now(UTC).isoformat()
            return context, None
        except json.JSONDecodeError:
            return None, f"Scraper returned invalid JSON: {result.stdout.strip()[:200]}"

    except Exception as e:
        return None, f"Scraper error: {type(e).__name__}({e}) — generating without page context"


def scrape_multiple_pages(
    base_url: str,
    additional_urls: list[str],
    timeout_ms: int = 10_000,
    progress_callback: Callable[..., Any] | None = None,
) -> tuple[MultiPageContext, ScraperState]:
    """
    Scrape multiple pages (base URL + additional URLs).

    Phase A implementation: scrapes each URL as a static page.
    Phase B placeholder: journey scraping will extend this function.

    Args:
        base_url: The primary page URL (e.g., login page)
        additional_urls: List of additional URLs to scrape (e.g., dashboard, settings)
        timeout_ms: Navigation timeout in milliseconds (default 10s)
        progress_callback: Optional callback(current_index, total) for UI updates

    Returns:
        (MultiPageContext with scraped pages, ScraperState with status)

    Note on Phase B (Journey Scraping):
        Future implementation will add navigation-based workflows where the scraper
        follows links/buttons between pages. This requires extending the function to
        accept a "journey definition" that specifies:
        - Starting URL
        - Navigation steps (click link X, fill form Y, submit)
        - Which pages to capture along the journey
    """
    all_urls = [base_url] + additional_urls
    total_pages = len(all_urls)

    # Initialize scraper state
    scraper_state = ScraperState.initial(total_pages)
    scraper_state.status = "scraping"
    scraper_state.started_at = datetime.now(UTC).isoformat()

    result = MultiPageContext(base_url=base_url, pages=[])

    start_time = time.monotonic()

    for index, url in enumerate(all_urls, 1):
        # Update progress
        scraper_state.current_page_index = index
        scraper_state.progress_percentage = (index / total_pages) * 100

        if progress_callback:
            try:
                progress_callback(index, total_pages, url)
            except Exception:
                pass  # Don't let callback errors break scraping

        context, error = scrape_page_context(url, timeout_ms)

        if context:
            result.add_page(context)
            scraper_state.completed_urls.append(url)
        else:
            scraper_state.failed_urls.append(url)

    # Finalize state
    duration_ms = int((time.monotonic() - start_time) * 1000)
    result.scrape_duration_ms = duration_ms
    result.total_elements = sum(p.element_count() for p in result.pages)
    result.total_forms = sum(len(p.forms) for p in result.pages)

    scraper_state.current_page_index = total_pages
    scraper_state.progress_percentage = 100.0
    scraper_state.completed_at = datetime.now(UTC).isoformat()

    if scraper_state.failed_urls:
        scraper_state.status = "error"
        scraper_state.error_message = (
            f"Completed {result.success_count}/{total_pages} pages. Failed: {', '.join(scraper_state.failed_urls)}"
        )
    else:
        scraper_state.status = "complete"

    return result, scraper_state


# ============================================================================
# Journey Scraper Placeholder (AI-010 Phase B - Future Implementation)
# ============================================================================

# TODO: AI-010 Phase B - Journey Scraping
#
# Design document: FEATURE_SPEC_multi_page_scraping.md
#
# The journey scraper will allow users to define multi-step navigation workflows:
#   1. Start at URL A (login page)
#   2. Fill form with credentials, submit
#   3. Navigate to URL B (dashboard) - capture context
#   4. Click link to URL C (settings) - capture context
#   5. Submit result containing all captured page contexts
#
# Planned implementation:
#   - New JourneyStep dataclass for defining steps
#   - execute_journey(base_url, journey_steps, progress_callback) function
#   - UI updates in streamlit_app.py for visual journey builder
#
# For now, Phase A multi-page scraping (scrape_multiple_pages) handles
# static URL lists without navigation between them.


def _run_playwright_scraper_process(url: str, timeout_ms: int) -> tuple[PageContext | None, str | None]:
    """Helper function to run Playwright in an isolated subprocess context.

    NOTE: Do NOT set WindowsSelectorEventLoopPolicy here!
    SelectorEventLoop does not support _make_subprocess_transport on Windows,
    which Playwright needs to launch the browser. The default ProactorEventLoop
    works correctly in a clean subprocess (main thread).

    NOTE ON METADATA: ``scraped_at`` and ``scrape_duration_ms`` are intentionally
    left at their zero/empty defaults when this function serialises the context via
    ``to_dict()`` in the ``__main__`` block.  The parent process (``scrape_page_context``)
    sets both fields after deserialising the JSON result, where it has access to the
    wall-clock start time.  Do not "fix" this by setting them inside the subprocess —
    the subprocess has no reliable way to measure end-to-end latency including IPC.
    """
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
            return context, None

    except Exception as e:
        return None, f"Playwright error: {type(e).__name__}({e})"


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
    h1_text: str | None = None
    h1 = page.query_selector("h1")
    if h1:
        h1_text = h1.inner_text().strip() or None

    elements: list[PageElement] = []

    # ── Inputs ────────────────────────────────────────────────────────────────
    for handle in page.query_selector_all("input:not([type='hidden'])"):
        if not handle.is_visible():
            continue
        attrs = {
            "element_id": handle.get_attribute("id"),
            "name": handle.get_attribute("name"),
            "label": handle.get_attribute("aria-label"),
            "test_id": handle.get_attribute("data-testid"),
            "placeholder": handle.get_attribute("placeholder"),
            "input_type": handle.get_attribute("type") or "text",
            "visible_text": None,
        }
        # Try to find associated <label> if no aria-label
        if not attrs["label"] and attrs["element_id"]:
            label_el = page.query_selector(f'label[for="{attrs["element_id"]}"]')
            if label_el:
                attrs["label"] = label_el.inner_text().strip() or None

        elements.append(
            PageElement(
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
            )
        )

    # ── Buttons ──────────────────────────────────────────────────────────────
    for handle in page.query_selector_all("button, input[type='submit'], input[type='button']"):
        if not handle.is_visible():
            continue
        visible = handle.inner_text().strip() or handle.get_attribute("value") or None
        attrs = {
            "element_id": handle.get_attribute("id"),
            "name": handle.get_attribute("name"),
            "label": handle.get_attribute("aria-label") or visible,
            "test_id": handle.get_attribute("data-testid"),
            "visible_text": visible,
            "input_type": None,
            "placeholder": None,
        }
        elements.append(
            PageElement(
                tag="button",
                role=handle.get_attribute("role") or "button",
                label=attrs["label"],
                test_id=attrs["test_id"],
                element_id=attrs["element_id"],
                name=attrs["name"],
                visible_text=attrs["visible_text"],
                recommended_locator=_build_recommended_locator("button", attrs),
            )
        )

    # ── Select dropdowns ─────────────────────────────────────────────────────
    for handle in page.query_selector_all("select"):
        if not handle.is_visible():
            continue
        attrs = {
            "element_id": handle.get_attribute("id"),
            "name": handle.get_attribute("name"),
            "label": handle.get_attribute("aria-label"),
            "test_id": handle.get_attribute("data-testid"),
            "visible_text": None,
            "input_type": None,
            "placeholder": None,
        }
        if not attrs["label"] and attrs["element_id"]:
            label_el = page.query_selector(f'label[for="{attrs["element_id"]}"]')
            if label_el:
                attrs["label"] = label_el.inner_text().strip() or None

        elements.append(
            PageElement(
                tag="select",
                label=attrs["label"],
                test_id=attrs["test_id"],
                element_id=attrs["element_id"],
                name=attrs["name"],
                recommended_locator=_build_recommended_locator("select", attrs),
            )
        )

    # ── Textareas ────────────────────────────────────────────────────────────
    for handle in page.query_selector_all("textarea"):
        if not handle.is_visible():
            continue
        attrs = {
            "element_id": handle.get_attribute("id"),
            "name": handle.get_attribute("name"),
            "label": handle.get_attribute("aria-label"),
            "test_id": handle.get_attribute("data-testid"),
            "placeholder": handle.get_attribute("placeholder"),
            "visible_text": None,
            "input_type": None,
        }
        if not attrs["label"] and attrs["element_id"]:
            label_el = page.query_selector(f'label[for="{attrs["element_id"]}"]')
            if label_el:
                attrs["label"] = label_el.inner_text().strip() or None

        elements.append(
            PageElement(
                tag="textarea",
                label=attrs["label"],
                test_id=attrs["test_id"],
                element_id=attrs["element_id"],
                name=attrs["name"],
                placeholder=attrs["placeholder"],
                recommended_locator=_build_recommended_locator("textarea", attrs),
            )
        )

    # ── Forms (group inputs by parent <form>) ────────────────────────────────
    forms: list[list[PageElement]] = []
    for form_handle in page.query_selector_all("form"):
        form_elements: list[PageElement] = []
        for child in form_handle.query_selector_all("input:not([type='hidden']), button, select, textarea"):
            child_id = child.get_attribute("id")
            child_name = child.get_attribute("name")
            matched = [
                e
                for e in elements
                if (e.element_id and child_id and e.element_id == child_id)
                or (e.name and child_name and e.name == child_name)
            ]
            if matched:
                for m in matched:
                    if m not in form_elements:
                        form_elements.append(m)
        if form_elements:
            forms.append(form_elements)

    return PageContext(
        url=url,
        page_title=page_title,
        h1_text=h1_text,
        elements=elements,
        forms=forms,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scrape page context")
    parser.add_argument("url", help="URL to scrape")
    parser.add_argument("--timeout", type=int, default=10000, help="Timeout in ms")
    args = parser.parse_args()

    context, error = _run_playwright_scraper_process(args.url, args.timeout)

    if error:
        print(json.dumps({"error": error}))
        sys.exit(1)

    if context:
        print(json.dumps({"context": context.to_dict()}))
        sys.exit(0)

    print(json.dumps({"error": "Unknown error occurred"}))
    sys.exit(1)
