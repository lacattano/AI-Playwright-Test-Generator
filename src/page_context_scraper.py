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
    options: list[str] | None = None  # Available options for <select> and combobox
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
                options=e.get("options"),
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
                    options=e.get("options"),
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
            if el.options:
                parts.append(f"options={el.options}")
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
        if el_tag in ("button", "a", "input", "select", "textarea", "combobox", "listbox"):
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
    credential_profiles: list["CredentialProfile"] | None = None,
    active_profile_label: str | None = None,
    restart_from_base: bool = False,
    max_attempts_per_page: int = 2,
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

    profiles = credential_profiles or []

    for index, url in enumerate(all_urls, 1):
        # Update progress
        scraper_state.current_page_index = index
        scraper_state.progress_percentage = (index / total_pages) * 100

        if progress_callback:
            try:
                progress_callback(index, total_pages, url)
            except Exception:
                pass  # Don't let callback errors break scraping

        context: PageContext | None = None
        error: str | None = None

        # Base URL still uses direct scrape.
        if index == 1 or not restart_from_base:
            context, error = scrape_page_context(url, timeout_ms)
        else:
            attempt_error: str | None = None
            for _attempt in range(1, max(max_attempts_per_page, 1) + 1):
                auto_steps: list[JourneyStep] = [
                    JourneyStep(step_type="goto", url=base_url, label="Start from base URL")
                ]
                if profiles and active_profile_label:
                    auto_steps.extend(
                        [
                            JourneyStep(
                                step_type="fill",
                                selector="#user-name",
                                value="{{username}}",
                                label="Fill username",
                            ),
                            JourneyStep(
                                step_type="fill",
                                selector="#password",
                                value="{{password}}",
                                label="Fill password",
                            ),
                            JourneyStep(
                                step_type="click",
                                selector="#login-button",
                                label="Submit login",
                            ),
                            JourneyStep(
                                step_type="wait",
                                selector=".inventory_list",
                                label="Wait for post-login page",
                            ),
                        ]
                    )

                auto_steps.extend(
                    [
                        JourneyStep(
                            step_type="auto_nav",
                            url=url,
                            label=f"Navigate to {url}",
                        ),
                        JourneyStep(
                            step_type="capture",
                            capture_label=url,
                            label=f"Capture {url}",
                        ),
                    ]
                )

                journey_result = execute_journey(
                    journey_steps=auto_steps,
                    credential_profiles=profiles,
                    active_profile_label=active_profile_label,
                    timeout_ms=timeout_ms,
                )
                if journey_result.captured_pages:
                    for captured_context in reversed(journey_result.captured_pages):
                        if _urls_match_target(captured_context.url, url):
                            context = captured_context
                            break
                    if context is not None:
                        break
                    attempt_error = (
                        f"Captured page URL did not match target URL {url}; "
                        f"captured {[p.url for p in journey_result.captured_pages]}"
                    )
                    continue
                attempt_error = (
                    journey_result.error_message or "; ".join(journey_result.failed_steps) or "Auto navigation failed"
                )
            if context is None:
                scraper_state.failed_urls.append(f"{url} ({attempt_error or 'Auto navigation failed'})")
                continue

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
# Journey Scraping Data Classes (AI-009 Phase B)
# ============================================================================


@dataclass
class CredentialProfile:
    """A set of credentials for authenticated scraping."""

    label: str
    username: str
    password: str


@dataclass
class JourneyStep:
    """A single step in a scraping journey."""

    step_type: Literal["goto", "click", "fill", "submit", "capture", "wait", "auto_nav"]
    url: str | None = None  # for goto steps
    selector: str | None = None  # CSS selector or role locator
    visible_text: str | None = None  # for click steps — alternative to selector
    value: str | None = None  # for fill steps
    label: str | None = None  # display name shown in UI
    capture_label: str | None = None  # label for captured context (e.g. "Dashboard")


@dataclass
class JourneyResult:
    """Result of executing a scraping journey."""

    success: bool
    captured_pages: list[PageContext]
    failed_steps: list[str]  # human-readable descriptions of failures
    error_message: str | None = None  # top-level error (SSO, MFA, CAPTCHA)
    redirected_urls: list[str] = field(default_factory=list)


# ============================================================================
# Journey Scraper Helper Functions (AI-009 Phase B)
# ============================================================================


def _substitute_credentials(value: str | None, profile: CredentialProfile | None) -> str | None:
    """Replace {{username}} and {{password}} placeholders with credential values."""
    if value is None or profile is None:
        return value
    value = value.replace("{{username}}", profile.username)
    value = value.replace("{{password}}", profile.password)
    return value


def _is_auth_redirect_page(page: Page) -> bool:
    """Check if current page is a login/auth redirect page."""
    # Check URL for auth-related terms
    url_lower = page.url.lower()
    auth_keywords = ["login", "sign in", "sign-in", "authenticate", "log in", "session expired"]
    for keyword in auth_keywords:
        if keyword in url_lower:
            return True

    # Check title for auth terms
    title = page.title().lower() if page.title() else ""
    for keyword in auth_keywords:
        if keyword in title:
            return True

    # Check H1 elements for auth terms
    try:
        h1_elements = page.query_selector_all("h1")
        for h1 in h1_elements:
            h1_text = h1.inner_text().lower()
            for keyword in auth_keywords:
                if keyword in h1_text:
                    return True
    except Exception:
        pass

    return False


def _detect_auth_redirect(
    current_url: str, current_page_title: str, current_h1: str | None, base_domain: str
) -> tuple[bool, str | None]:
    """
    Detect if page has redirected to an authentication page.

    Returns:
        (is_auth_redirect, reason) — is_auth_redirect is True if detected,
        reason is a human-readable message explaining why.
    """
    auth_keywords = ["login", "sign in", "sign-in", "authenticate", "log in", "session expired", "authentication"]
    url_lower = current_url.lower()
    for keyword in auth_keywords:
        if keyword in url_lower:
            return True, f"URL contains auth keyword '{keyword}'"

    title_lower = (current_page_title or "").lower()
    for keyword in auth_keywords:
        if keyword in title_lower:
            return True, f"Page title contains auth keyword '{keyword}'"

    if current_h1:
        h1_lower = current_h1.lower()
        for keyword in auth_keywords:
            if keyword in h1_lower:
                return True, f"H1 contains auth keyword '{keyword}'"

    return False, None


def _detect_sso_redirect(current_url: str, base_domain: str) -> bool:
    """Detect if user was redirected to SSO/OAuth provider domain."""
    try:
        from urllib.parse import urlparse

        current_domain = urlparse(current_url).netloc.lower()
        base_domain_clean = base_domain.lower().replace("www.", "")

        # If domain changed and it's not a subdomain of base, likely SSO
        if current_domain != base_domain_clean:
            if not current_domain.endswith("." + base_domain_clean):
                return True
    except Exception:
        pass
    return False


def _auto_navigate_to_target(page: Page, target_url: str, timeout_ms: int) -> bool:
    """Attempt to reach target URL by clicking likely navigation locators on current page."""
    from urllib.parse import urlparse

    target_path = urlparse(target_url).path or "/"
    target_slug = target_path.strip("/").split("/")[-1]
    current_path = urlparse(page.url).path or "/"
    if current_path == target_path:
        return True

    candidate_selectors = [
        f'a[href="{target_path}"]',
        f'a[href$="{target_path}"]',
        f'a[href*="{target_slug}"]' if target_slug else "",
        "#shopping_cart_container a" if "cart" in target_path else "",
        "#checkout" if "checkout" in target_path else "",
    ]

    for selector in [sel for sel in candidate_selectors if sel]:
        locator = page.locator(selector).first
        if locator.count() == 0:
            continue
        try:
            locator.click(timeout=timeout_ms)
            page.wait_for_load_state("domcontentloaded", timeout=timeout_ms)
        except Exception:
            continue
        current_path = urlparse(page.url).path or "/"
        if current_path == target_path:
            return True

    return False


def _urls_match_target(current_url: str, target_url: str) -> bool:
    """Return True when the current URL matches the expected target URL path/domain."""
    from urllib.parse import urlparse

    parsed_current = urlparse(current_url)
    parsed_target = urlparse(target_url)

    current_path = (parsed_current.path or "/").rstrip("/") or "/"
    target_path = (parsed_target.path or "/").rstrip("/") or "/"
    if current_path != target_path:
        return False

    if parsed_target.netloc:
        return parsed_current.netloc.lower() == parsed_target.netloc.lower()
    return True


def _detect_mfa_prompt(page: Page) -> bool:
    """Check if page is requesting 2FA/MFA verification."""
    try:
        # Look for tel inputs (phone verification)
        tel_inputs = page.query_selector_all('input[type="tel"]')
        if tel_inputs:
            return True

        # Look for labels containing verification keywords
        mfa_keywords = ["verification code", "authenticator", "one-time", "otp", "two-factor"]
        labels = page.query_selector_all("label")
        for label in labels:
            label_text = label.inner_text().lower()
            if any(keyword in label_text for keyword in mfa_keywords):
                return True

        return False
    except Exception:
        return False


def _detect_captcha(page: Page) -> bool:
    """Check if page contains CAPTCHA elements."""
    try:
        # Look for CAPTCHA iframes from known providers
        captcha_providers = ["recaptcha", "hcaptcha", "turnstile", "recaptcha.net", "hcaptcha.com"]
        iframes = page.query_selector_all("iframe")
        for iframe in iframes:
            src = iframe.get_attribute("src") or ""
            if any(provider in src.lower() for provider in captcha_providers):
                return True

        # Look for elements with captcha-related IDs/classes
        captcha_selectors = ["captcha", "recaptcha", "hcaptcha", "turnstile"]
        for selector in captcha_selectors:
            elements = page.query_selector_all(f"[id*='{selector}'], [class*='{selector}']")
            if elements:
                return True

        return False
    except Exception:
        return False


def _capture_page_context_from_page(page: Page, current_url: str) -> PageContext:
    """
    Extract page context from a Playwright Page object.

    This mirrors the logic in _extract_context but handles page navigation context.

    Args:
        page: Playwright Page object (already navigated)
        current_url: The URL that was just navigated to

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

    # ── Inputs ────
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

    # ── Buttons ──
    for handle in page.query_selector_all("button, input[type='submit'], input[type='button']"):
        if not handle.is_visible():
            continue
        visible = handle.inner_text().strip() or handle.get_attribute("value") or None
        actual_tag = str(handle.evaluate("el => el.tagName.toLowerCase()"))

        attrs = {
            "element_id": handle.get_attribute("id"),
            "name": handle.get_attribute("name"),
            "label": handle.get_attribute("aria-label") or visible,
            "test_id": handle.get_attribute("data-testid"),
            "visible_text": visible,
            "input_type": handle.get_attribute("type") if actual_tag == "input" else None,
            "placeholder": None,
        }
        elements.append(
            PageElement(
                tag=actual_tag,
                role=handle.get_attribute("role") or "button",
                label=attrs["label"],
                test_id=attrs["test_id"],
                element_id=attrs["element_id"],
                name=attrs["name"],
                visible_text=attrs["visible_text"],
                input_type=attrs["input_type"],
                recommended_locator=_build_recommended_locator(actual_tag, attrs),
            )
        )

    # ── Select dropdowns ──
    for handle in page.query_selector_all("select"):
        if not handle.is_visible():
            continue

        options = []
        for opt in handle.query_selector_all("option"):
            opt_text = opt.inner_text().strip()
            if opt_text:
                options.append(opt_text)

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
                options=options if options else None,
                recommended_locator=_build_recommended_locator("select", attrs),
            )
        )

    # ── Custom Dropdowns (Combobox / Listbox) ──
    for handle in page.query_selector_all("[role='combobox'], [role='listbox']"):
        if not handle.is_visible():
            continue

        options = []
        for opt in handle.query_selector_all("[role='option']"):
            opt_text = opt.inner_text().strip()
            if opt_text:
                options.append(opt_text)

        controls_id = handle.get_attribute("aria-controls")
        if not options and controls_id:
            controls_el = page.query_selector(f"#{controls_id}")
            if controls_el:
                for opt in controls_el.query_selector_all("[role='option']"):
                    opt_text = opt.inner_text().strip()
                    if opt_text:
                        options.append(opt_text)

        attrs = {
            "element_id": handle.get_attribute("id"),
            "name": handle.get_attribute("name"),
            "label": handle.get_attribute("aria-label"),
            "test_id": handle.get_attribute("data-testid"),
            "visible_text": handle.inner_text().strip() or None,
            "input_type": None,
            "placeholder": handle.get_attribute("placeholder"),
        }
        if not attrs["label"] and attrs["element_id"]:
            label_el = page.query_selector(f'label[for="{attrs["element_id"]}"]')
            if label_el:
                attrs["label"] = label_el.inner_text().strip() or None

        el_tag = handle.get_attribute("role") or "combobox"
        elements.append(
            PageElement(
                tag=el_tag,
                role=el_tag,
                label=attrs["label"],
                test_id=attrs["test_id"],
                element_id=attrs["element_id"],
                name=attrs["name"],
                visible_text=attrs["visible_text"],
                placeholder=attrs["placeholder"],
                options=options if options else None,
                recommended_locator=_build_recommended_locator(el_tag, attrs),
            )
        )

    # ── Textareas ──
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

    # ── Forms (group inputs by parent <form>) ──
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
        url=current_url,
        page_title=page_title,
        h1_text=h1_text,
        elements=elements,
        forms=forms,
    )


def _execute_journey_process(
    steps_json: str,
    base_domain: str,
    credential_profiles: list[dict],
    active_profile_label: str | None,
    timeout_ms: int = 10_000,
) -> JourneyResult:
    """
    Execute a scraping journey in a subprocess.

    This is the core subprocess function that runs Playwright logic to navigate
    through a defined journey of steps, capturing page context at each capture step.

    Args:
        steps_json: JSON string of journey steps
        base_domain: Base domain for SSO detection
        credential_profiles: List of credential profile dicts
        active_profile_label: Label of active profile for credential substitution
        timeout_ms: Timeout per navigation step

    Returns:
        JourneyResult with captured pages and error information
    """
    import json

    # Parse steps from JSON
    steps_data = json.loads(steps_json)
    steps = [
        JourneyStep(
            step_type=s["step_type"],
            url=s.get("url"),
            selector=s.get("selector"),
            visible_text=s.get("visible_text"),
            value=s.get("value"),
            label=s.get("label"),
            capture_label=s.get("capture_label"),
        )
        for s in steps_data
    ]

    # Build credential profiles
    profiles = [
        CredentialProfile(label=p["label"], username=p["username"], password=p["password"]) for p in credential_profiles
    ]

    # Find active profile
    active_profile = None
    if active_profile_label:
        active_profile = next((p for p in profiles if p.label == active_profile_label), None)

    captured_pages: list[PageContext] = []
    failed_steps: list[str] = []
    redirected_urls: list[str] = []
    error_message: str | None = None

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        context_obj = browser.new_context()
        page = context_obj.new_page()

        for step_idx, step in enumerate(steps):
            step_label = step.label or f"Step {step_idx + 1}"

            try:
                if step.step_type == "goto":
                    page.goto(step.url or "", wait_until="load", timeout=timeout_ms)
                    # Check for auth redirect
                    if _is_auth_redirect_page(page):
                        failed_steps.append(f"{step_label}: Page redirected to login")
                        redirected_urls.append(page.url)
                        continue
                    # Check for SSO redirect
                    if _detect_sso_redirect(page.url, base_domain):
                        error_message = "SSO/OAuth redirect detected — automated login not supported for this provider"
                        break
                    # Check for CAPTCHA after navigation
                    if _detect_captcha(page):
                        error_message = "CAPTCHA detected — automated login not supported"
                        break

                elif step.step_type == "click":
                    if step.visible_text:
                        page.get_by_text(step.visible_text).click(timeout=timeout_ms)
                    elif step.selector:
                        page.locator(step.selector).click(timeout=timeout_ms)
                    else:
                        failed_steps.append(f"{step_label}: No selector or visible_text provided")
                        continue

                    # Check for MFA after click
                    if _detect_mfa_prompt(page):
                        error_message = "MFA prompt detected — automated login not supported"
                        break

                    # Check for CAPTCHA after click
                    if _detect_captcha(page):
                        error_message = "CAPTCHA detected — automated login not supported"
                        break

                    # Check for auth redirect
                    if _is_auth_redirect_page(page):
                        failed_steps.append(f"{step_label}: Clicked element led to login page")
                        redirected_urls.append(page.url)
                        continue

                elif step.step_type == "fill":
                    if step.selector and step.value:
                        # Substitute credentials if placeholders present
                        filled_value = (
                            _substitute_credentials(step.value, active_profile) if active_profile else step.value
                        )
                        if filled_value:  # Type guard for str | None -> str
                            page.locator(step.selector).fill(filled_value)
                        else:
                            failed_steps.append(f"{step_label}: Fill value was empty after substitution")
                            continue
                    else:
                        failed_steps.append(f"{step_label}: Missing selector or value")
                        continue

                elif step.step_type == "submit":
                    if step.selector:
                        page.locator(step.selector).click(timeout=timeout_ms)
                    else:
                        # Submit the form containing filled fields
                        page.keyboard.press("Enter")

                    # Check for auth redirect after submit
                    if _is_auth_redirect_page(page):
                        failed_steps.append(f"{step_label}: Submit led to login page")
                        redirected_urls.append(page.url)
                        continue

                elif step.step_type == "capture":
                    # Capture page context
                    context_data = _capture_page_context_from_page(page, page.url)
                    if context_data:
                        captured_pages.append(context_data)

                elif step.step_type == "wait":
                    if step.selector:
                        page.locator(step.selector).wait_for(timeout=timeout_ms)
                    else:
                        page.wait_for_timeout(min(timeout_ms // 1000, 5))

                elif step.step_type == "auto_nav":
                    if not step.url:
                        failed_steps.append(f"{step_label}: Missing target URL for auto navigation")
                        continue
                    reached = _auto_navigate_to_target(page, step.url, timeout_ms)
                    if not reached:
                        failed_steps.append(f"{step_label}: Could not navigate to {step.url} from current page")
                        continue

                # After goto and capture, check for auth redirect (additional safety)
                if step.step_type in ["goto", "capture", "auto_nav"]:
                    if _is_auth_redirect_page(page):
                        # Only add if not already added
                        if page.url not in redirected_urls:
                            failed_steps.append(f"{step_label}: Auth redirect detected after step")
                            redirected_urls.append(page.url)

            except Exception as e:
                failed_steps.append(f"{step_label}: {str(e)}")
                # Continue with next step unless critical error
                continue

        browser.close()

    success = error_message is None and len(captured_pages) > 0

    return JourneyResult(
        success=success,
        captured_pages=captured_pages,
        failed_steps=failed_steps,
        error_message=error_message,
        redirected_urls=redirected_urls,
    )


def _journey_result_to_json(result: JourneyResult) -> str:
    """Serialize JourneyResult to JSON for stdout."""
    from dataclasses import asdict

    return json.dumps(asdict(result))


def execute_journey(
    journey_steps: list[JourneyStep],
    credential_profiles: list[CredentialProfile],
    active_profile_label: str | None = None,
    timeout_ms: int = 10_000,
    progress_callback: Callable[..., Any] | None = None,
) -> JourneyResult:
    """
    Execute a scraping journey and capture page contexts.

    This function spawns a subprocess to avoid Streamlit's ProactorEventLoop issue
    when using Playwright. The subprocess receives the journey definition as JSON,
    executes it in a fresh browser session, and returns the result.

    Args:
        journey_steps: Ordered list of steps to execute
        credential_profiles: List of credential profiles for placeholder substitution
        active_profile_label: Label of profile to use for {{username}}/{{password}} placeholders
        timeout_ms: Timeout per navigation step in milliseconds
        progress_callback: Optional callback(status_msg, progress) for UI updates

    Returns:
        JourneyResult with captured pages, failed steps, and error information

    Raises:
        subprocess.TimeoutExpired: If journey execution exceeds timeout
        FileNotFoundError: If subprocess cannot be spawned
    """
    import json
    import subprocess
    import sys
    import tempfile
    from dataclasses import asdict
    from pathlib import Path
    from urllib.parse import urlparse

    def _serialize_journey() -> str:
        """Serialize journey to JSON string."""
        return json.dumps([asdict(step) for step in journey_steps])

    def _deserialize_result(json_str: str) -> JourneyResult:
        """Deserialize JourneyResult from JSON."""
        data = json.loads(json_str)
        return JourneyResult(
            success=data["success"],
            captured_pages=[PageContext.from_dict(page_data) for page_data in data["captured_pages"]],
            failed_steps=data["failed_steps"],
            error_message=data["error_message"],
            redirected_urls=data["redirected_urls"],
        )

    # Get base domain from first goto step or construct from credential info
    base_domain = "example.com"
    for step in journey_steps:
        if step.step_type == "goto" and step.url:
            base_domain = urlparse(step.url).netloc
            break

    # Serialize journey and credentials for subprocess
    steps_json = json.dumps([asdict(step) for step in journey_steps])
    credential_profiles_json = json.dumps([asdict(p) for p in credential_profiles])

    # Spawn subprocess
    try:
        with tempfile.TemporaryDirectory():
            result = subprocess.run(
                [
                    sys.executable,
                    __file__,
                    "--journey",
                    steps_json,
                    "--base-domain",
                    base_domain,
                    "--credentials",
                    credential_profiles_json,
                    "--active-profile",
                    active_profile_label or "",
                    "--timeout",
                    str(timeout_ms),
                ],
                capture_output=True,
                text=True,
                timeout=120,  # Overall subprocess timeout
                cwd=str(Path(__file__).parent.parent),
            )

            if result.returncode != 0:
                error_msg = f"Subprocess failed: {result.stderr}"
                return JourneyResult(
                    success=False,
                    captured_pages=[],
                    failed_steps=[error_msg],
                    error_message=error_msg,
                )

            try:
                result_obj = _deserialize_result(result.stdout)
                return result_obj
            except Exception as e:
                return JourneyResult(
                    success=False,
                    captured_pages=[],
                    failed_steps=[f"Failed to deserialize result: {str(e)}"],
                    error_message=str(e),
                )
    except subprocess.TimeoutExpired:
        return JourneyResult(
            success=False,
            captured_pages=[],
            failed_steps=["Journey execution timed out"],
            error_message="Journey execution timed out",
        )
    except Exception as e:
        return JourneyResult(
            success=False,
            captured_pages=[],
            failed_steps=[f"Failed to execute journey: {type(e).__name__}({e})"],
            error_message=str(e),
        )


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
        actual_tag = str(handle.evaluate("el => el.tagName.toLowerCase()"))

        attrs = {
            "element_id": handle.get_attribute("id"),
            "name": handle.get_attribute("name"),
            "label": handle.get_attribute("aria-label") or visible,
            "test_id": handle.get_attribute("data-testid"),
            "visible_text": visible,
            "input_type": handle.get_attribute("type") if actual_tag == "input" else None,
            "placeholder": None,
        }
        elements.append(
            PageElement(
                tag=actual_tag,
                role=handle.get_attribute("role") or "button",
                label=attrs["label"],
                test_id=attrs["test_id"],
                element_id=attrs["element_id"],
                name=attrs["name"],
                visible_text=attrs["visible_text"],
                input_type=attrs["input_type"],
                recommended_locator=_build_recommended_locator(actual_tag, attrs),
            )
        )

    # ── Select dropdowns ─────────────────────────────────────────────────────
    for handle in page.query_selector_all("select"):
        if not handle.is_visible():
            continue

        # Extract <option> texts
        options = []
        for opt in handle.query_selector_all("option"):
            opt_text = opt.inner_text().strip()
            if opt_text:
                options.append(opt_text)

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
                options=options if options else None,
                recommended_locator=_build_recommended_locator("select", attrs),
            )
        )

    # ── Custom Dropdowns (Combobox / Listbox) ────────────────────────────────
    for handle in page.query_selector_all("[role='combobox'], [role='listbox']"):
        if not handle.is_visible():
            continue

        # Try to gracefully grab visible child options if present (without clicking)
        options = []
        for opt in handle.query_selector_all("[role='option']"):
            opt_text = opt.inner_text().strip()
            if opt_text:
                options.append(opt_text)

        # Some custom dropdowns connect to their listbox via aria-controls
        controls_id = handle.get_attribute("aria-controls")
        if not options and controls_id:
            controls_el = page.query_selector(f"#{controls_id}")
            if controls_el:
                for opt in controls_el.query_selector_all("[role='option']"):
                    opt_text = opt.inner_text().strip()
                    if opt_text:
                        options.append(opt_text)

        attrs = {
            "element_id": handle.get_attribute("id"),
            "name": handle.get_attribute("name"),
            "label": handle.get_attribute("aria-label"),
            "test_id": handle.get_attribute("data-testid"),
            "visible_text": handle.inner_text().strip() or None,
            "input_type": None,
            "placeholder": handle.get_attribute("placeholder"),
        }
        if not attrs["label"] and attrs["element_id"]:
            label_el = page.query_selector(f'label[for="{attrs["element_id"]}"]')
            if label_el:
                attrs["label"] = label_el.inner_text().strip() or None

        el_tag = handle.get_attribute("role") or "combobox"
        elements.append(
            PageElement(
                tag=el_tag,
                role=el_tag,
                label=attrs["label"],
                test_id=attrs["test_id"],
                element_id=attrs["element_id"],
                name=attrs["name"],
                visible_text=attrs["visible_text"],
                placeholder=attrs["placeholder"],
                options=options if options else None,
                recommended_locator=_build_recommended_locator(el_tag, attrs),
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


# __main__: subprocess entry point for scraper
# Supports both legacy single-page mode and journey mode
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scrape page context")
    parser.add_argument("url", nargs="?", help="URL to scrape (required for single-page mode)")
    parser.add_argument("--timeout", type=int, default=10000, help="Timeout in ms")
    parser.add_argument("--journey", type=str, help="Journey steps JSON (journey mode)")
    parser.add_argument("--base-domain", type=str, help="Base domain for journey mode")
    parser.add_argument("--credentials", type=str, help="Credential profiles JSON for journey mode")
    parser.add_argument("--active-profile", type=str, help="Active profile label for journey mode")
    args = parser.parse_args()

    # Determine mode based on arguments
    if args.journey:
        # Journey mode: execute scraping journey with navigation steps
        try:
            from dataclasses import asdict

            credential_profiles = json.loads(args.credentials) if args.credentials else []
            result = _execute_journey_process(
                args.journey,
                args.base_domain or "example.com",
                credential_profiles,
                args.active_profile if hasattr(args, "active_profile") else None,
                args.timeout,
            )

            output = _journey_result_to_json(result)
            print(output)

            if result.success:
                sys.exit(0)
            else:
                sys.exit(1)
        except Exception as e:
            print(json.dumps({"error": str(e)}))
            sys.exit(1)
    else:
        # Legacy single-page mode: scrape a single URL
        if not args.url:
            print(json.dumps({"error": "No URL provided. Usage: page_context_scraper.py URL --timeout X"}))
            sys.exit(1)

        context, error = _run_playwright_scraper_process(args.url, args.timeout)

        if error:
            print(json.dumps({"error": error}))
            sys.exit(1)

        if context:
            print(json.dumps({"context": context.to_dict()}))
            sys.exit(0)

        print(json.dumps({"error": "Unknown error occurred"}))
        sys.exit(1)
