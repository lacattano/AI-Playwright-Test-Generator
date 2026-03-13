# BACKLOG.md
## AI Playwright Test Generator

Last updated: 2026-03-07

---

## ✅ Closed Bugs

### B-001 — LLM generates async standalone tests instead of pytest sync
**Fixed:** System prompt updated in `src/llm_client.py` to instruct pytest sync format.
`generate_test_for_story()` prompt also reinforced with explicit pytest format requirements.

### B-002 — LLM output occasionally has all imports on one line (missing newlines)
**Fixed:** `normalise_code_newlines()` added to `src/file_utils.py`, called automatically
after generation in `generate_test_for_story()`.

### B-003 — Generated tests not saved to `generated_tests/` automatically
**Fixed:** Phase A auto-save implemented. `save_generated_test()` called after every
successful generation. Path stored in `session_state.saved_test_path`.

### B-005 — `launch_ui.sh` starts mock server (not appropriate for general use)
**Fixed:** Mock server startup moved to `launch_dev.sh`. `launch_ui.sh` now launches
UI only.

---

## 🔴 Open Bugs

### B-004 — Ambiguous locators when same label exists on multiple forms
**Symptom:** `strict mode violation: get_by_label("Driver Name") resolved to 2 elements`
**Root cause:** Mock site has both a vehicle form (`#driverName`) and an add driver form
(`#driverNameInput`) — both match `get_by_label("Driver Name")`
**Impact:** Test fails immediately on fill step
**Fix (immediate):** Use `page.locator("#driverNameInput")` instead of `get_by_label`
**Fix (long term):** Page context scraper (AI-001, now complete) injects real selectors
into the prompt — the LLM should now use `#driverNameInput` directly
**Priority:** Medium — page context scraper should prevent recurrence on new generations

---

## 🟡 Active Improvements

### AI-002 — User Story Parser Module
**What:** Move criteria extraction out of `streamlit_app.py` into a proper tested module
supporting Jira AC format, Gherkin, bullets, numbered lists, free-form
**Why:** Currently `extract_criteria_from_user_story()` lives in `streamlit_app.py` which
means it cannot be unit tested without triggering `st.set_page_config()`
**New files:** `src/user_story_parser.py`, `tests/test_user_story_parser.py`
**Priority:** High

### AI-003 — Update `.env.example` for OLLAMA_TIMEOUT
**What:** Update `.env.example` and README to show `OLLAMA_TIMEOUT=300` instead of `60`
**Why:** 60 seconds is not enough for `qwen3.5:35b`. New users following the README
will hit timeout failures immediately
**Priority:** Medium — quick fix, high impact for new users

### AI-004 — Phase C Run Now gaps
**What:** Three gaps remain in the Run Now workflow:
1. Environment URL dropdown — allow selecting staging/prod/local before running
2. Re-run failed tests only — filter to failed tests on second run
3. Screenshot viewer — display captured screenshots inline after run
**Priority:** Medium

### AI-005 — Move coverage helpers to `src/coverage_utils.py`
**What:** `TestFunction`, `RequirementCoverage`, `parse_test_functions()`,
`extract_criteria_from_user_story()`, `map_tests_to_criteria()`, `calculate_coverage()`
currently live in `streamlit_app.py`
**Why:** Cannot be unit tested without triggering Streamlit import crash
**New files:** `src/coverage_utils.py`, `tests/test_coverage_utils.py`
**Priority:** Medium — required before proper test coverage of these functions

### AI-006 — Test fixture library for parser and e2e testing
**What:** Create `tests/fixtures/user_stories/` with 10-15 real user story examples
in each supported format (Gherkin, Jira AC bullets, numbered, free-form should/must)
**Why:** Parser regression suite — any format change is caught immediately.
Also pairs with external practice sites for end-to-end testing sessions.
**Priority:** Medium

---

## 🌟 Nice to Have — Future Enhancements

### Cloud LLM Providers
**Goal:** Support OpenRouter, OpenAI, Anthropic as LLM backends alongside Ollama
**Spec:**
- Add `LLM_PROVIDER` env var (ollama, openrouter, openai, anthropic)
- Provider-specific API key configuration in sidebar
- Fallback to Ollama when no API keys configured
**Status:** Deferred — local-first flow must be stable first
**Priority:** Medium (Phase 5+)

### Authenticated Page Scraping
**Goal:** Allow page context scraper to access pages behind login
**Spec:** Cookie injection or credential passing for scraper session
**Status:** Deferred — Phase 4 concern per spec
**Priority:** Low

### n8n Integration
**Goal:** Workflow automation — trigger generation from Jira webhooks, report to Slack
**Requires:** HTTP API layer (`src/api_server.py`, FastAPI)
**Status:** Low priority — Phase 4+ once core generator is stable
**Priority:** Low

---

## 📋 Fix Log (Session 3 — 2026-03-06)

- B-001 closed — pytest sync format enforced in prompt
- B-002 closed — newline normalisation added
- B-003 closed — Phase A auto-save implemented
- B-005 closed — launch scripts split
- Phase A (auto-save + rename UI) complete
- Phase B (coverage analysis + display) complete
- Phase C (run now — core) complete
- AI-004 opened for Phase C gaps
- AI-005 opened for coverage utils extract

## 📋 Fix Log (Session 4 — 2026-03-07)

- AI-001 (page context scraper) implemented — `src/page_context_scraper.py` complete
- Coverage mapping fixed — number-based matching before keyword fallback
- Run output persistence fixed — `last_run_success`/`last_run_output` in session state
- Jira report download added — `_generate_jira_report()` + 4th download button
- High Confidence metric replaced with Tests Generated (more meaningful)
- `sync_playwright` moved to module-level import in `page_context_scraper.py` (mock fix)
- `pytest.ini` testpaths — removed `generated_tests` from CI test run
- Git hygiene — untracked generated files removed, `.gitignore` updated and reformatted
- AI-006 opened for test fixture library

## 📋 Fix Log (Session 5 — 2026-03-10)

- R-003 completed — Report utilities (`src/report_utils.py`) extracted from `streamlit_app.py`
  - `_generate_local_report()` implemented with proper markdown formatting
  - `_generate_jira_report()` extended to include coverage details for failed tests
  - `_generate_html_report()` generates comprehensive HTML reports with optional screenshots
  - `format_coverage_details()` returns formatted string with pass rate percentage
  - All functions fully typed and tested (12 new tests)
- R-003 tests passing: `test_generate_local_report_empty`, `test_generate_jira_report_format`,
  `test_generate_html_report_no_screenshots`, `test_generate_local_report_with_coverage`,
  `test_generate_jira_report_with_coverage`, `test_generate_html_report_with_coverage`,
  `test_generate_html_report_missing_screenshot_dir`, `test_generate_html_report_with_screenshots_in_dir`,
  `test_coverage_with_unknown_status`, plus test data structures
- All code passes ruff and mypy checks before commit
