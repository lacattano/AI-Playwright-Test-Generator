# FEATURE SPEC — Skeleton Engine (AI-016, Phase 1)

**Status:** Design — not yet implemented  
**Author:** Louis + Claude, Session 13  
**Priority:** Highest — replaces the current broken single-page scrape → hallucinate model

---

## Problem

The current pipeline scrapes only the base URL (homepage), hands those locators to the LLM, and asks it to generate tests for a full user journey. The LLM has no locators for product pages, cart pages, or checkout pages — so it invents them. Invented locators cause 30-second timeouts when the tests run.

**Root cause:** The LLM is being asked to do two jobs at once — write test logic AND know what elements exist on pages it has never seen. It can only do the first job reliably.

---

## Proposed Solution: Two-Phase Pipeline with Page Object Model

Split the work clearly:

- **LLM job:** Write test logic, structure, and assertions. Name what it needs but don't guess selectors.
- **Scraper job:** Find real locators on real pages. Never invented.
- **Page Object Model:** Cache scraped locators per page so every test re-uses the same real data.

---

## Phase 1 — Skeleton Generation (LLM Call 1)

**Input:** User story + acceptance criteria  
**Output:** Test skeletons with named placeholders instead of real locators

### What the LLM produces

A Python test file where every locator is a named placeholder tag:

```python
def test_01_add_items_to_cart(page: Page):
    """Criterion 1: user can add items to cart"""
    home = HomePage(page)
    home.goto()
    product_page = home.{{GOTO:product_listing_page}}
    product_page.{{CLICK:add_to_cart_button}}
    expect(page).to_have_url({{URL:cart_page}})
```

And a structured list of pages needed:

```python
# PAGES_NEEDED:
# - https://automationexercise.com/           (homepage)
# - https://automationexercise.com/products   (product listing)
# - https://automationexercise.com/cart.html  (cart)
```

### Placeholder format

`{{ACTION:description}}` where ACTION is one of:

| Tag | Meaning | Example |
|-----|---------|---------|
| `{{CLICK:description}}` | A clickable element needed | `{{CLICK:add_to_cart_button}}` |
| `{{FILL:description}}` | An input field to fill | `{{FILL:email_input}}` |
| `{{GOTO:description}}` | Navigation to a page | `{{GOTO:product_page}}` |
| `{{URL:description}}` | A URL for assertion | `{{URL:cart_page}}` |
| `{{ASSERT:description}}` | An element to assert visibility | `{{ASSERT:success_message}}` |

### Prompt rules for Phase 1

- Write complete test logic and assertions — do not omit any criterion.
- Use placeholders everywhere a real locator or URL would go.
- Include a `# PAGES_NEEDED:` comment block listing every URL the tests will visit.
- Generate Page Object class stubs (empty methods) for each page in `PAGES_NEEDED`.
- **LLM calls must use LLMClient from src/llm_client.py via the provider abstraction — not direct HTTP calls.**

---

## Phase 2 — Scraping Loop + Placeholder Resolution

**Input:** Skeleton file + PAGES_NEEDED list  
**Output:** Completed Page Object classes + filled test file

### Algorithm

```
pages_to_scrape = extract PAGES_NEEDED from skeleton
page_objects = {}

FOR each url IN pages_to_scrape:
    context = scrape_page_context(url)
    page_objects[url] = build_page_object(context)

FOR each placeholder IN skeleton:
    matching_locator = find_best_match(placeholder.description, page_objects)
    IF matching_locator found:
        replace placeholder with real locator
    ELSE:
        replace placeholder with:
            pytest.skip(f"Locator for '{placeholder.description}' not found — "
                       f"scraped {url} but element was not present. "
                       f"Try adding the correct page URL to 'Add more pages'.")
```

### Page Object structure

For each scraped page, generate a class:

```python
class ProductPage:
    """Page Object for https://automationexercise.com/products
    Scraped: 2026-04-06T10:30:00
    Elements found: 42
    """
    URL = "https://automationexercise.com/products"

    def __init__(self, page: Page) -> None:
        self.page = page

    def goto(self) -> None:
        self.pageto.goto(self.URL)

    def add_to_cart(self) -> None:
        self.page.get_by_role("button", name="Add to Cart").first.click()

    def view_product(self, index: int = 0) -> None:
        self.page.get_by_role("a", name="View Product").nth(index).click()
```

Methods are only generated for locators the scraper actually found.

### Placeholder matching

Match placeholder descriptions to scraped locators using:

1. **Exact label match** — placeholder says `add_to_cart_button`, locator label is `Add to Cart` → match
2. **Keyword overlap** — 2+ shared meaningful words $\rightarrow$ match
3. **No match** $\rightarrow$ emit `pytest.skip()` with page URL and description

---

## Phase 3 — Final Assembly (LLM Call 2, optional)

**Input:** Completed Page Objects + test file with all placeholders resolved  
**Output:** Polished, runnable test file

### Implementation Details
- **LLM calls must use LLMClient from src/llm_client.py via the provider abstraction — not direct HTTP calls.**
- **The polishing call is conditional: Skip if no placeholders were successfully resolved (i.e., all placeholders resulted in `pytest.skip()`).**

---

## Output Structure

```
generated_tests/
  test_20260406_110000/
    pages/
      home_page.py          ← Page Object for homepage
      product_page.py       ← Page Object for /products
      cart_page.py          ← Page Object for /cart.html
    test_user_can_shop.py   ← Tests importing from pages/
    scrape_manifest.json    ← Which pages were scraped, element counts, unresolved placeholders
```

## Failure Reporting

`scrape_manifest.json` records:

```json
{
  "pages_scraped": [
    {"url": "https://automationexercise.com/", "elements": 59},
    {"url": "https://automationexercise.com/products", "elements": 41}
  ],
  "unresolved_placeholders": [
    {
      "placeholder": "{{CLICK:proceed_to_checkout_button}}",
      "page_needed": "https://automationexercise.com/cart.html",
      "reason": "Page was not in scrape list — add it to 'Add more pages'",
      "test": "test_04_go_to_checkout"
    }
  ]
}
```

The Streamlit UI surfaces unresolved placeholders as warnings with actionable messages.