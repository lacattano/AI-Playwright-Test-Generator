"""Tests for the lightweight HTML scraper."""

from src.scraper import PageScraper


def test_extract_elements_from_html_prefers_specific_selectors() -> None:
    scraper = PageScraper()
    html = """
    <html><body>
      <button id="submit-order">Submit Order</button>
      <a data-testid="view-cart">View Cart</a>
    </body></html>
    """

    elements = scraper._extract_elements_from_html(html)
    selectors = {element["selector"]: element for element in elements}

    assert selectors["#submit-order"]["text"] == "Submit Order"
    assert selectors["#submit-order"]["role"] == "button"
    assert selectors['[data-testid="view-cart"]']["text"] == "View Cart"
    assert selectors['[data-testid="view-cart"]']["role"] == "a"


def test_extract_elements_from_html_uses_href_for_links_when_available() -> None:
    scraper = PageScraper()
    html = """
    <html><body>
      <a href="/view_cart" title="Cart">Cart</a>
    </body></html>
    """

    elements = scraper._extract_elements_from_html(html, base_url="https://example.com/")

    assert elements[0]["selector"] == 'a[href="/view_cart"]'
    assert elements[0]["href"] == "https://example.com/view_cart"
