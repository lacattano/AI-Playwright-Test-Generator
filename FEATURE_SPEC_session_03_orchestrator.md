# FEATURE SPEC — Pipeline Orchestrator (Session 03)
**Status:** Design
**Scope:** Phase 3 & Integration

## Objective
Implement the "Orchestrator" to tie Phase 1 (Skeleton Generation) and Phase 2 (Placeholder Resolution) into a single, seamless execution flow within the Streamlit UI.

## Requirements
1. **Pipeline Orchestrator (`src/intelligent_pipeline.py`)**:
    - Manage the lifecycle of the request:
        1. Call LLM for Skeleton Generation (Phase 1).
        2. Extract `PAGES_NEEDED` and run Scraper for each URL.
        3. Run Resolver to match placeholders with scraped Page Objects (Phase 2).
        4. Perform optional "Polishing" call (Phase 3) if required.
    - Handle errors at any stage (e.le., scraping failure) by emitting appropriate `pytest.skip()` messages.

2. **Streamlit Integration (`streamlit_app.py`)**:
    - Update the generation workflow to use this new pipeline.
    - Display progress updates: "Generating Skeleton...", "Scraping Pages...", "Resolving Locators...".
    - Present the final output structure (Tests + Page Objects).

3. **Data Persistence/Artifacts**:
    - Ensure `scrape_manifest.json` is generated to track successes and failures.

## Definition of Done
- [ ] Unit test: `tests/test_intelligent_pipeline.py` verifies the end-to-end flow using mocked LLM and Scraper.
- [ ] Integration check: The Streamlit UI successfully triggers the full pipeline without manual intervention between phases.
- [ ] Verification: Check that `generated_tests/` contains both the test file AND the generated Page Object files.