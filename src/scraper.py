"""HTML scraper used by the intelligent pipeline to discover real selectors."""

from __future__ import annotations

from typing import Any
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup
from bs4.element import Tag


class PageScraper:
    """Scrape pages and extract interaction-oriented element metadata."""

    def __init__(self, timeout: float = 30.0) -> None:
        self.timeout = timeout

    async def scrape_url(self, url: str) -> list[dict[str, Any]]:
        """Scrape a single URL and return extracted element metadata."""
        async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
            try:
                response = await client.get(url)
                response.raise_for_status()
                return self._extract_elements_from_html(response.text, base_url=str(response.url))
            except Exception:
                return []

    @staticmethod
    def _normalise_href(base_url: str, href: str) -> str:
        """Return an absolute href when the value looks navigable."""
        cleaned_href = href.strip()
        if not cleaned_href or cleaned_href.startswith(("#", "javascript:", "mailto:", "tel:")):
            return ""
        return urljoin(base_url, cleaned_href)

    @staticmethod
    def _join_classes(tag: Tag) -> str:
        """Return CSS class names as a single space-delimited string."""
        class_value = tag.get("class")
        if isinstance(class_value, list):
            return " ".join(cls for cls in class_value if isinstance(cls, str) and cls)
        if isinstance(class_value, str):
            return class_value.strip()
        return ""

    def _build_selector(self, tag: Tag, href: str) -> str:
        """Return the best available CSS selector for a tag."""
        for attribute in ("data-testid", "data-test", "data-qa", "data-product-id"):
            attribute_value = tag.get(attribute)
            if attribute_value:
                return f'[{attribute}="{attribute_value}"]'

        if tag.get("id"):
            return f"#{tag.get('id')}"
        if tag.get("name"):
            return f'{tag.name}[name="{tag.get("name")}"]'
        if tag.name == "a" and href:
            href_path = urlparse(href).path or href
            return f'a[href="{href_path}"]'

        classes = self._join_classes(tag)
        if classes:
            return "." + ".".join(part for part in classes.split() if part)

        return tag.name

    def _extract_elements_from_html(self, html: str, base_url: str = "") -> list[dict[str, Any]]:
        """Extract likely interactive elements and their best selectors."""
        soup = BeautifulSoup(html, "html.parser")
        elements: list[dict[str, Any]] = []
        interactive_tags = ["button", "a", "input", "select", "textarea"]

        for tag in soup.find_all(interactive_tags):
            href = self._normalise_href(base_url, str(tag.get("href", "")))
            selector = self._build_selector(tag, href)
            text_content = tag.get_text(" ", strip=True)
            role = str(tag.get("role", tag.get("type", tag.name)))
            classes = self._join_classes(tag)

            if text_content or role:
                elements.append(
                    {
                        "selector": selector,
                        "text": text_content,
                        "role": role,
                        "href": href,
                        "title": str(tag.get("title", "")).strip(),
                        "aria_label": str(tag.get("aria-label", "")).strip(),
                        "name": str(tag.get("name", "")).strip(),
                        "id": str(tag.get("id", "")).strip(),
                        "classes": classes,
                        "value": str(tag.get("value", "")).strip(),
                        "placeholder": str(tag.get("placeholder", "")).strip(),
                    }
                )

        return elements

    async def scrape_all(self, urls: list[str]) -> dict[str, list[dict[str, Any]]]:
        """Scrape multiple URLs and return a mapping of URL to extracted elements."""
        return {url: await self.scrape_url(url) for url in urls}
