# FEATURE SPEC — Placeholder Resolver (Session 02)
**Status:** Design
**Scope:** Phase 2 of the Intelligent Scraping Pipeline

## Objective
Implement the "Phase 2" logic: matching extracted placeholders to real locators found during scraping and generating Page Object classes.

## Requirements
1. **Page Object Builder (`src/page_object_builder.py`)**:
    - Input: Scraped `PageContext` (elements, URLs, etc.).
    - Output: A string representing a Python class for the page.
    - Feature: Generate methods (e.g., `click_button`, `fill_input`) based on actual elements found in the scrape.

2. **Placeholder Resolver (`src/placeholder_resolver.py`)**:
    - Input: Skeleton code (with placeholders) + Scraped Page Objects.
    - Logic: 
        - Parse `{{ACTION:description}}` tags.
        - Use fuzzy matching or keyword overlap to find the best matching locator in the Page Object.
        - Replace placeholder with actual Playwright locator (e.g., `page.get_by_role(...)`).
        - If no match is found, replace with a `pytest.skip()` call containing the error details.

3. **Data Structure**: Define how the resolved code and the resulting Page Objects are passed to the next phase or saved.

## Definition of Done
- [ ] Unit test: `tests/test_placeholder_resolver.py` verifies successful replacement of a known tag.
- [ ] Unit test: `tests/test_placeholder_resolver.py` verifies `pytest.skip` generation for missing locators.
- [ ] Unit test: `tests/test_page_object_builder.py` verifies class string generation from raw context.