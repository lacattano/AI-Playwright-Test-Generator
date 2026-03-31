"""
Tests for page_context_scraper.py

Tests cover:
- Data class serialization/deserialization
- Locator building logic
- PageContext formatting
- Scraper state management
- Multi-page context aggregation
"""

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from src.page_context_scraper import (
    CredentialProfile,
    JourneyResult,
    MultiPageContext,
    PageContext,
    PageElement,
    ScraperState,
    _build_recommended_locator,
    _extract_context,
    scrape_multiple_pages,
)


class TestPageElement:
    """Tests for PageElement dataclass."""

    def test_page_element_minimal(self) -> None:
        """Test creating a minimal PageElement."""
        element = PageElement(tag="input")
        assert element.tag == "input"
        assert element.role is None
        assert element.label is None
        assert element.recommended_locator is None

    def test_page_element_full(self) -> None:
        """Test creating a fully populated PageElement."""
        element = PageElement(
            tag="input",
            role="textbox",
            label="Email Address",
            test_id="email-input",
            element_id="email",
            name="email",
            placeholder="you@example.com",
            input_type="email",
            is_required=True,
            recommended_locator='page.get_by_test_id("email-input")',
        )
        assert element.tag == "input"
        assert element.role == "textbox"
        assert element.label == "Email Address"
        assert element.is_required is True


class TestPageContext:
    """Tests for PageContext dataclass."""

    def test_element_count(self) -> None:
        """Test element_count method returns correct count."""
        elements = [
            PageElement(tag="input", label="Field 1"),
            PageElement(tag="button", label="Submit"),
        ]
        context = PageContext(
            url="http://example.com",
            page_title="Test Page",
            h1_text="Welcome",
            elements=elements,
        )
        assert context.element_count() == 2

    def test_to_dict(self) -> None:
        """Test serialization to dictionary."""
        element = PageElement(tag="input", label="Test Field", test_id="test-123")
        context = PageContext(
            url="http://example.com",
            page_title="Test Page",
            h1_text="Welcome",
            elements=[element],
            scraped_at="2024-01-01T00:00:00Z",
            scrape_duration_ms=1234,
        )

        data = context.to_dict()

        assert data["url"] == "http://example.com"
        assert data["page_title"] == "Test Page"
        assert len(data["elements"]) == 1
        assert data["elements"][0]["tag"] == "input"

    def test_from_dict(self) -> None:
        """Test deserialization from dictionary."""
        data = {
            "url": "http://example.com",
            "page_title": "Test Page",
            "h1_text": "Welcome",
            "elements": [
                {
                    "tag": "input",
                    "role": "textbox",
                    "label": "Email",
                    "test_id": "email-field",
                    "element_id": None,
                    "name": "email",
                    "placeholder": "Enter email",
                    "visible_text": None,
                    "input_type": "email",
                    "is_required": True,
                    "recommended_locator": 'page.get_by_test_id("email-field")',
                }
            ],
            "forms": [],
            "scraped_at": "2024-01-01T00:00:00Z",
            "scrape_duration_ms": 500,
        }

        context = PageContext.from_dict(data)  # type: ignore[arg-type]

        assert context.url == "http://example.com"
        assert context.page_title == "Test Page"
        assert len(context.elements) == 1
        assert context.elements[0].tag == "input"
        assert context.elements[0].test_id == "email-field"

    def test_from_dict_with_extra_keys(self) -> None:
        """Test that extra keys in dict are safely ignored."""
        data: dict[str, Any] = {
            "url": "http://example.com",
            "page_title": "Test",
            "h1_text": None,
            "elements": [],
            "forms": [],
            "extra_key": "should be ignored",
            "another_extra": 12345,
        }

        context = PageContext.from_dict(data)

        assert context.url == "http://example.com"
        # Extra keys should not cause errors

    def test_to_prompt_block(self) -> None:
        """Test prompt block generation."""
        element = PageElement(
            tag="input",
            label="Username",
            test_id="username",
            input_type="text",
            recommended_locator='page.get_by_test_id("username")',
        )
        context = PageContext(
            url="http://example.com/login",
            page_title="Login",
            h1_text="Sign In",
            elements=[element],
        )

        prompt = context.to_prompt_block()

        assert "=== PAGE CONTEXT" in prompt
        assert "http://example.com/login" in prompt
        assert 'aria-label="Username"' in prompt
        assert 'data-testid="username"' in prompt
        assert "USE THESE LOCATORS" in prompt


class TestBuildRecommendedLocator:
    """Tests for _build_recommended_locator function."""

    def test_prefer_test_id(self) -> None:
        """Test that data-testid is preferred over id."""
        el: dict[str, str | None] = {"test_id": "my-test-id", "element_id": "my-id"}
        locator = _build_recommended_locator("input", el)
        assert locator == 'page.get_by_test_id("my-test-id")'

    def test_fallback_to_element_id(self) -> None:
        """Test fallback to element id when no test_id."""
        el: dict[str, str | None] = {"element_id": "my-id"}
        locator = _build_recommended_locator("button", el)
        assert locator == 'page.locator("#my-id")'

    def test_fallback_to_name(self) -> None:
        """Test fallback to name attribute."""
        el: dict[str, str | None] = {"name": "username"}
        locator = _build_recommended_locator("input", el)
        assert locator == "page.locator(\"[name='username']\")"

    def test_fallback_to_label_for_button(self) -> None:
        """Test fallback to label for button element."""
        el: dict[str, str | None] = {"label": "Submit Button"}
        locator = _build_recommended_locator("button", el)
        assert locator == 'page.get_by_role("button", name="Submit Button")'

    def test_fallback_to_label_for_input(self) -> None:
        """Test fallback to label for input element."""
        el: dict[str, str | None] = {"label": "Email Address"}
        locator = _build_recommended_locator("input", el)
        assert locator == 'page.get_by_role("input", name="Email Address")'

    def test_fallback_to_visible_text(self) -> None:
        """Test fallback to visible text."""
        el: dict[str, str | None] = {"visible_text": "Click me"}
        locator = _build_recommended_locator("a", el)
        assert locator == 'page.get_by_text("Click me")'

    def test_fallback_to_tag(self) -> None:
        """Test final fallback to tag name."""
        el: dict[str, str | None] = {}
        locator = _build_recommended_locator("div", el)
        assert locator == 'page.locator("div")'


class TestScraperState:
    """Tests for ScraperState dataclass."""

    def test_initial_state(self) -> None:
        """Test initial state creation."""
        state = ScraperState.initial(5)
        assert state.status == "idle"
        assert state.total_pages == 5
        assert state.progress_percentage == 0.0
        assert len(state.completed_urls) == 0

    def test_to_dict(self) -> None:
        """Test serialization to dict."""
        state = ScraperState.initial(3)
        data = state.to_dict()
        assert data["status"] == "idle"
        assert data["total_pages"] == 3

    def test_from_dict(self) -> None:
        """Test deserialization from dict."""
        data = {
            "status": "scraping",
            "current_page_index": 2,
            "total_pages": 5,
            "progress_percentage": 40.0,
            "completed_urls": ["http://a.com"],
            "failed_urls": [],
            "error_message": None,
            "started_at": "2024-01-01T00:00:00Z",
            "completed_at": None,
        }
        state = ScraperState.from_dict(data)
        assert state.status == "scraping"
        assert state.current_page_index == 2

    def test_in_progress_state(self) -> None:
        """Test in_progress state factory."""
        state = ScraperState.in_progress(
            current_page_index=1,
            total_pages=3,
            progress_percentage=33.3,
            completed_urls=[],
            failed_urls=[],
        )
        assert state.status == "scraping"
        assert state.started_at is not None


class TestMultiPageContext:
    """Tests for MultiPageContext dataclass."""

    def test_add_page(self) -> None:
        """Test adding pages to multi-page context."""
        mp_context = MultiPageContext(base_url="http://example.com")
        page1 = PageContext(
            url="http://example.com/page1",
            page_title="Page 1",
            h1_text="First",
            elements=[PageElement(tag="input")],
        )
        mp_context.add_page(page1)

        assert mp_context.success_count == 1
        assert len(mp_context.pages) == 1

    def test_total_elements(self) -> None:
        """Test total_elements is calculated correctly."""
        mp_context = MultiPageContext(base_url="http://example.com")
        page1 = PageContext(
            url="http://example.com/page1",
            page_title="Page 1",
            h1_text=None,
            elements=[PageElement(tag="input"), PageElement(tag="button")],
        )
        page2 = PageContext(
            url="http://example.com/page2",
            page_title="Page 2",
            h1_text=None,
            elements=[PageElement(tag="select")],
        )
        mp_context.add_page(page1)
        mp_context.add_page(page2)

        assert mp_context.total_elements == 0  # Not auto-calculated in add_page

    def test_is_empty(self) -> None:
        """Test is_empty property."""
        mp_context = MultiPageContext(base_url="http://example.com")
        assert mp_context.is_empty is True

        mp_context.add_page(PageContext(url="http://example.com/page1", page_title="P1", h1_text=None))
        assert mp_context.is_empty is False

    def test_to_prompt_block(self) -> None:
        """Test multi-page prompt block generation."""
        mp_context = MultiPageContext(base_url="http://example.com")
        page = PageContext(
            url="http://example.com/login",
            page_title="Login",
            h1_text="Sign In",
            elements=[PageElement(tag="input", label="Username")],
        )
        mp_context.add_page(page)

        prompt = mp_context.to_prompt_block()

        assert "MULTI-PAGE CONTEXT INJECTED" in prompt
        assert "http://example.com" in prompt
        assert "Pages scraped: 1" in prompt


class TestScrapeMultiplePages:
    """Tests for scrape_multiple_pages function."""

    @patch("src.page_context_scraper.scrape_page_context")
    def test_scrapes_all_urls(self, mock_scrape: MagicMock) -> None:
        """Test that all URLs are scraped."""
        mock_context = PageContext(
            url="http://example.com",
            page_title="Test",
            h1_text=None,
            elements=[PageElement(tag="input")],
        )
        mock_scrape.return_value = (mock_context, None)

        result, state = scrape_multiple_pages(
            base_url="http://example.com/1",
            additional_urls=["http://example.com/2"],
        )

        assert result.success_count == 2
        assert state.status == "complete"
        assert len(state.failed_urls) == 0

    @patch("src.page_context_scraper.scrape_page_context")
    def test_handles_failures(self, mock_scrape: MagicMock) -> None:
        """Test that failures are tracked correctly."""

        call_count = [0]

        def scrape_side_effect(*args: object, **kwargs: object) -> tuple[PageContext | None, str | None]:  # noqa: D103
            call_count[0] += 1
            if call_count[0] == 2:
                return (None, "Connection failed")
            return (
                PageContext(url="http://test", page_title="T", h1_text=None),
                None,
            )

        mock_scrape.side_effect = scrape_side_effect  # type: ignore[arg-type]

        result, state = scrape_multiple_pages(
            base_url="http://example.com/1",
            additional_urls=["http://example.com/2"],
        )

        assert result.success_count == 1
        assert len(state.failed_urls) == 1
        assert state.status == "error"

    @patch("src.page_context_scraper.scrape_page_context")
    def test_calls_progress_callback(self, mock_scrape: MagicMock) -> None:
        """Test that progress callback is called."""

        mock_context = PageContext(url="http://example.com", page_title="Test", h1_text=None)
        mock_scrape.return_value = (mock_context, None)

        callbacks_received: list[tuple[int, int, str]] = []

        def progress_callback(current: int, total: int, url: str) -> None:  # type: ignore[no-untyped-def]
            callbacks_received.append((current, total, url))

        result, state = scrape_multiple_pages(
            base_url="http://example.com/1",
            additional_urls=["http://example.com/2"],
            progress_callback=progress_callback,  # type: ignore[arg-type]
        )

        assert len(callbacks_received) == 2

    @patch("src.page_context_scraper.execute_journey")
    @patch("src.page_context_scraper.scrape_page_context")
    def test_restart_from_base_uses_journey_for_additional_urls(
        self, mock_scrape: MagicMock, mock_execute_journey: MagicMock
    ) -> None:
        """When restart_from_base is enabled, additional URLs use journey execution."""
        base_context = PageContext(url="http://example.com/login", page_title="Login", h1_text=None)
        target_context = PageContext(url="http://example.com/cart", page_title="Cart", h1_text=None)
        mock_scrape.return_value = (base_context, None)
        mock_execute_journey.return_value = JourneyResult(
            success=True,
            captured_pages=[target_context],
            failed_steps=[],
            error_message=None,
            redirected_urls=[],
        )

        result, state = scrape_multiple_pages(
            base_url="http://example.com/login",
            additional_urls=["http://example.com/cart"],
            credential_profiles=[CredentialProfile(label="A", username="u", password="p")],
            active_profile_label="A",
            restart_from_base=True,
            max_attempts_per_page=2,
        )

        assert result.success_count == 2
        assert state.status == "complete"
        assert mock_execute_journey.call_count == 1

    @patch("src.page_context_scraper.execute_journey")
    @patch("src.page_context_scraper.scrape_page_context")
    def test_restart_from_base_retries_failed_navigation(
        self, mock_scrape: MagicMock, mock_execute_journey: MagicMock
    ) -> None:
        """Failed additional-page navigation should retry from base with limited attempts."""
        base_context = PageContext(url="http://example.com/login", page_title="Login", h1_text=None)
        target_context = PageContext(url="http://example.com/checkout", page_title="Checkout", h1_text=None)
        mock_scrape.return_value = (base_context, None)
        mock_execute_journey.side_effect = [
            JourneyResult(
                success=False,
                captured_pages=[],
                failed_steps=["attempt 1 failed"],
                error_message="attempt 1 failed",
                redirected_urls=[],
            ),
            JourneyResult(
                success=True,
                captured_pages=[target_context],
                failed_steps=[],
                error_message=None,
                redirected_urls=[],
            ),
        ]

        result, state = scrape_multiple_pages(
            base_url="http://example.com/login",
            additional_urls=["http://example.com/checkout"],
            restart_from_base=True,
            max_attempts_per_page=2,
        )

        assert result.success_count == 2
        assert state.status == "complete"
        assert mock_execute_journey.call_count == 2

    @patch("src.page_context_scraper.execute_journey")
    @patch("src.page_context_scraper.scrape_page_context")
    def test_restart_from_base_retries_when_captured_url_mismatches_target(
        self, mock_scrape: MagicMock, mock_execute_journey: MagicMock
    ) -> None:
        """Captured context should only be accepted when its URL matches the requested target."""
        base_context = PageContext(url="http://example.com/login", page_title="Login", h1_text=None)
        wrong_context = PageContext(url="http://example.com/inventory", page_title="Inventory", h1_text=None)
        target_context = PageContext(url="http://example.com/checkout", page_title="Checkout", h1_text=None)
        mock_scrape.return_value = (base_context, None)
        mock_execute_journey.side_effect = [
            JourneyResult(
                success=True,
                captured_pages=[wrong_context],
                failed_steps=[],
                error_message=None,
                redirected_urls=[],
            ),
            JourneyResult(
                success=True,
                captured_pages=[target_context],
                failed_steps=[],
                error_message=None,
                redirected_urls=[],
            ),
        ]

        result, state = scrape_multiple_pages(
            base_url="http://example.com/login",
            additional_urls=["http://example.com/checkout"],
            restart_from_base=True,
            max_attempts_per_page=2,
        )

        assert result.success_count == 2
        assert state.status == "complete"
        assert mock_execute_journey.call_count == 2
        assert [page.url for page in result.pages] == [
            "http://example.com/login",
            "http://example.com/checkout",
        ]

    @patch("src.page_context_scraper.execute_journey")
    @patch("src.page_context_scraper.scrape_page_context")
    def test_restart_from_base_fails_when_target_url_never_captured(
        self, mock_scrape: MagicMock, mock_execute_journey: MagicMock
    ) -> None:
        """Additional URL should fail when every attempt captures a different page."""
        base_context = PageContext(url="http://example.com/login", page_title="Login", h1_text=None)
        wrong_context = PageContext(url="http://example.com/inventory", page_title="Inventory", h1_text=None)
        mock_scrape.return_value = (base_context, None)
        mock_execute_journey.return_value = JourneyResult(
            success=True,
            captured_pages=[wrong_context],
            failed_steps=[],
            error_message=None,
            redirected_urls=[],
        )

        result, state = scrape_multiple_pages(
            base_url="http://example.com/login",
            additional_urls=["http://example.com/checkout"],
            restart_from_base=True,
            max_attempts_per_page=2,
        )

        assert result.success_count == 1
        assert state.status == "error"
        assert mock_execute_journey.call_count == 2
        assert state.failed_urls
        assert "did not match target URL" in state.failed_urls[0]


class TestExtractContext:
    """Tests for _extract_context function (requires mock Playwright page)."""

    @pytest.fixture
    def mock_page(self) -> MagicMock:
        """Create a mock Playwright page object."""
        mock = MagicMock()
        mock.title.return_value = "Mock Page Title"
        return mock

    @pytest.fixture
    def mock_input_element(self) -> MagicMock:
        """Create a mock input element."""
        mock = MagicMock()
        mock.is_visible.return_value = True
        attrs: dict[str, str | None] = {
            "id": "email-field",
            "name": "email",
            "aria-label": "Email Address",
            "data-testid": "email-input",
            "placeholder": "Enter your email",
            "type": "email",
            "required": "true",
            "role": None,
        }
        mock.get_attribute.side_effect = lambda attr: attrs.get(attr)
        return mock

    def test_extract_context_with_mock_page(self, mock_page: MagicMock, mock_input_element: MagicMock) -> None:
        """Test context extraction with mocked Playwright objects."""
        # Mock H1 element
        mock_h1 = MagicMock()
        mock_h1.inner_text.return_value = "Welcome to the Site"
        mock_page.query_selector.return_value = mock_h1

        mock_page.query_selector_all.return_value = [mock_input_element]

        context = _extract_context(mock_page, "http://example.com/form")

        assert context.page_title == "Mock Page Title"
        assert context.h1_text == "Welcome to the Site"
        assert len(context.elements) > 0

    def test_extract_options_from_select_and_combobox(self, mock_page: MagicMock) -> None:
        """Test that options are extracted from <select> and [role='combobox']."""
        # Mock <select> element
        mock_select = MagicMock()
        mock_select.is_visible.return_value = True
        mock_select.get_attribute.side_effect = lambda attr: "my-select" if attr == "id" else None

        # Mock <option> elements inside <select>
        opt1 = MagicMock()
        opt1.inner_text.return_value = "Option 1"
        opt2 = MagicMock()
        opt2.inner_text.return_value = "Option 2"
        mock_select.query_selector_all.return_value = [opt1, opt2]

        # Mock combobox element
        mock_combo = MagicMock()
        mock_combo.is_visible.return_value = True

        def combo_attr(attr: str) -> str | None:
            if attr == "role":
                return "combobox"
            if attr == "id":
                return "my-combo"
            return None

        mock_combo.get_attribute.side_effect = combo_attr
        mock_combo.inner_text.return_value = "Custom Dropdown"

        # Mock <div role="option"> inside combobox
        opt3 = MagicMock()
        opt3.inner_text.return_value = "Apple"
        opt4 = MagicMock()
        opt4.inner_text.return_value = "Banana"
        mock_combo.query_selector_all.return_value = [opt3, opt4]

        def mock_query_all(selector: str) -> list[MagicMock]:
            if selector == "select":
                return [mock_select]
            elif selector == "[role='combobox'], [role='listbox']":
                return [mock_combo]
            return []

        mock_page.query_selector_all.side_effect = mock_query_all

        context = _extract_context(mock_page, "http://example.com")

        # Verify select
        select_el = next((e for e in context.elements if e.tag == "select"), None)
        assert select_el is not None
        assert select_el.options == ["Option 1", "Option 2"]

        # Verify combobox
        combo_el = next((e for e in context.elements if e.tag == "combobox"), None)
        assert combo_el is not None
        assert combo_el.options == ["Apple", "Banana"]
