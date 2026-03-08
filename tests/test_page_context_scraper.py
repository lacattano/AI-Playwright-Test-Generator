"""Unit tests for src/page_context_scraper.py

Tests cover:
- PageElement dataclass construction
- PageContext.to_prompt_block() output format
- _build_recommended_locator() priority logic
- scrape_page_context() error handling (mocked — no live browser needed)
"""

from unittest.mock import MagicMock, patch

from src.page_context_scraper import (
    PageContext,
    PageElement,
    _build_recommended_locator,
    scrape_page_context,
)


class TestBuildRecommendedLocator:
    def test_prefers_test_id_over_all(self) -> None:
        el: dict[str, str | None] = {
            "test_id": "submit-btn",
            "label": "Submit",
            "element_id": "btn1",
            "name": None,
            "visible_text": None,
            "input_type": None,
            "placeholder": None,
        }
        assert _build_recommended_locator("button", el) == 'page.get_by_test_id("submit-btn")'

    def test_prefers_label_over_id(self) -> None:
        el: dict[str, str | None] = {
            "test_id": None,
            "label": "Driver Name",
            "element_id": "driverNameInput",
            "name": None,
            "visible_text": None,
            "input_type": None,
            "placeholder": None,
        }
        result = _build_recommended_locator("input", el)
        assert 'get_by_role("input", name="Driver Name")' in result

    def test_falls_back_to_id(self) -> None:
        el: dict[str, str | None] = {
            "test_id": None,
            "label": None,
            "element_id": "driverNameInput",
            "name": None,
            "visible_text": None,
            "input_type": None,
            "placeholder": None,
        }
        assert _build_recommended_locator("input", el) == 'page.locator("#driverNameInput")'

    def test_falls_back_to_name(self) -> None:
        el: dict[str, str | None] = {
            "test_id": None,
            "label": None,
            "element_id": None,
            "name": "username",
            "visible_text": None,
            "input_type": None,
            "placeholder": None,
        }
        assert _build_recommended_locator("input", el) == "page.locator(\"[name='username']\")"

    def test_falls_back_to_visible_text(self) -> None:
        el: dict[str, str | None] = {
            "test_id": None,
            "label": None,
            "element_id": None,
            "name": None,
            "visible_text": "Add Driver",
            "input_type": None,
            "placeholder": None,
        }
        assert _build_recommended_locator("button", el) == 'page.get_by_text("Add Driver")'

    def test_falls_back_to_tag_only(self) -> None:
        el: dict[str, str | None] = {
            "test_id": None,
            "label": None,
            "element_id": None,
            "name": None,
            "visible_text": None,
            "input_type": None,
            "placeholder": None,
        }
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
    @patch("src.page_context_scraper.subprocess.run")
    def test_returns_none_and_message_on_timeout(self, mock_subprocess: MagicMock) -> None:
        mock_subprocess.return_value.returncode = 1
        mock_subprocess.return_value.stderr = "Timed out connecting"
        ctx, error = scrape_page_context("http://localhost:9999")
        assert ctx is None
        assert error is not None
        assert "scraper subprocess failed" in error.lower()

    @patch("src.page_context_scraper.subprocess.run")
    def test_returns_none_and_message_on_connection_error(self, mock_subprocess: MagicMock) -> None:
        mock_subprocess.return_value.returncode = 1
        mock_subprocess.return_value.stderr = "Connection refused"
        ctx, error = scrape_page_context("http://localhost:9999")
        assert ctx is None
        assert error is not None

    @patch("src.page_context_scraper.subprocess.run")
    def test_returns_none_on_subprocess_error(self, mock_subprocess: MagicMock) -> None:
        mock_subprocess.return_value.returncode = 1
        mock_subprocess.return_value.stderr = "Playwright not installed"
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
