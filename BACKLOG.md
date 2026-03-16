# BACKLOG.md
## AI Playwright Test Generator

Last updated: 2026-03-16

---

## ✅ Closed Bugs

### B-001 — LLM generates async standalone tests instead of pytest sync
**Fixed:** System prompt updated in `src/llm_client.py`.

### B-002 — LLM output occasionally has all imports on one line
**Fixed:** `normalise_code_newlines()` added to `src/file_utils.py`.

### B-003 — Generated tests not saved to `generated_tests/` automatically
**Fixed:** Phase A auto-save implemented.

### B-005 — `launch_ui.sh` starts mock server (not appropriate for general use)
**Fixed:** Mock server startup moved to `launch_dev.sh`.

---

## 🔴 Blockers (Fix Before Anything Else)

### BREAK-1 — `src/pytest_output_parser.py` missing (CI BLOCKER)
**Symptom:** `pytest tests/ -v` fails with `ModuleNotFoundError: No module named 'src.pytest_output_parser'`  
**Cause:** Implementation file was never committed. `tests/test_pytest_output_parser.py` imports it.  
**Fix:** Create `src/pytest_output_parser.py` — canonical content in `PROJECT_KNOWLEDGE.md` appendix and attached as a file output from Session 9.  
**Impact:** ALL CI tests fail until this is added.

### BREAK-2 — Session state wipe blanks run results panel
**Symptom:** "Run Now" executes but results panel is always blank  
**Cause:** Two lines in `display_run_button()` reset `last_run_success` and `last_run_output` to `None`/`""` immediately after setting them  
**Fix:** Delete the two reset lines in `streamlit_app.py` — see `FIX_PLAN_session9.md`  
**Impact:** Run results never display after execution

---

## 🔴 Open Bugs

### B-004 — Ambiguous locators when same label exists on multiple forms
**Symptom:** `strict mode violation: get_by_label("Driver Name") resolved to 2 elements`  
**Fix (short term):** Use `page.locator("#specificId")` instead of `get_by_label`  
**Fix (long term):** Multi-page scraping (AI-009) injects real selectors  
**Priority:** Medium — AI-009 should prevent recurrence

### B-006 — Parser banner wrong when mix of pass/fail
**Symptom:** Banner reads "All 1 tests passed" when actual result is 1 pass, 3 fail  
**Cause:** `DURATION_RE` in `pytest_output_parser.py` matches `1 passed` from somewhere in  
the output before reaching the final summary line — overwrites the real totals  
**Fix:** Only match the duration line when it appears after `=====` separator, or match  
the last occurrence of the pattern rather than the first  
**Priority:** High — misleads the user about test results

### B-007 — Error panels duplicated in results view
**Symptom:** Failed test error messages appear twice — once above the coverage table,  
once below it  
**Cause:** `display_run_button()` renders errors, then the coverage section renders them  
again independently  
**Fix:** Audit `streamlit_app.py` — error rendering should happen in exactly one place  
**Priority:** Medium — visual noise, confusing

### B-008 — Run Status column shows ⏳ for all rows (never updates)
**Symptom:** Coverage x Run Results table shows pending icon for every row even after  
a completed run  
**Cause:** `RunResult` from `pytest_output_parser` is not being passed to `display_coverage()`  
or the name-matching between `RunResult.results` and `RequirementCoverage.linked_tests` is  
failing silently  
**Fix:** Wire `st.session_state.last_run_result` through to `display_coverage()` and verify  
name matching logic — see FEATURE_SPEC_run_results.md for the intended integration  
**Priority:** High — Coverage x Run Results is the key demo feature

---

## 🟡 Active Improvements (Prioritised)

### AI-009 — Multi-Page Scraping ⭐ CRITICAL
**What:** Allow the scraper to collect elements from multiple pages in a user flow,  
not just the base URL  
**Why:** Single-page scraping means every test step after page 1 uses guessed  
selectors — core value of the tool is broken for any multi-step flow  
**Spec:** `FEATURE_SPEC_multi_page_scraping.md`  
**Phase A (do first):** User provides additional URLs in the UI — scraper visits all  
**Phase B (deferred):** Scraper follows the flow automatically using story-inferred actions  
**New files:** None — extends `src/page_context_scraper.py`  
**Modified:** `src/page_context_scraper.py`, `streamlit_app.py`  
**Priority:** 🔴 Critical — implement after BREAK-1 and BREAK-2 fixed

### AI-002 — User Story Parser Module
**What:** Move criteria extraction into `src/user_story_parser.py` with proper  
format support: Gherkin, Jira AC bullets, numbered, free-form  
**Why:** Currently lives in `streamlit_app.py` — untestable without Streamlit crash  
**New files:** `src/user_story_parser.py`, `tests/test_user_story_parser.py`  
**Priority:** High — do after AI-009 Phase A

### AI-005 — Move coverage helpers to `src/coverage_utils.py`
**What:** Extract `TestFunction`, `RequirementCoverage`, `parse_test_functions()`,  
`extract_criteria_from_user_story()`, `map_tests_to_criteria()`, `calculate_coverage()`  
out of `streamlit_app.py`  
**Why:** Cannot be unit tested without triggering Streamlit import crash  
**New files:** `src/coverage_utils.py`, `tests/test_coverage_utils.py`  
**Priority:** High — also required to properly fix B-008

### AI-003 — Update `.env.example` for OLLAMA_TIMEOUT
**What:** Set `OLLAMA_TIMEOUT=300` as the default in `.env.example` and README  
**Why:** Default of 60s causes timeout failures on any model larger than 9b.  
New users following the README hit this immediately.  
**Priority:** Medium — 2-minute fix, high impact for new users and the 27b model

### AI-004 — Phase C Run Now gaps
**What:** Three gaps in the Run Now workflow:  
1. Environment URL dropdown (staging / prod / local)  
2. Re-run failed tests only  
3. Screenshot viewer inline after run  
**Priority:** Medium

### AI-006 — Test fixture library
**What:** `tests/fixtures/user_stories/` with 10-15 examples in each format  
**Why:** Parser regression suite  
**Priority:** Medium

### AI-007 — Remove `_generate_test_content()` from CLI orchestrator
**What:** CLI orchestrator has its own generation function duplicating  
`src/test_generator.py` logic  
**Priority:** Low

---

## 🌟 Nice to Have — Future Enhancements

### Cloud LLM Providers
**Goal:** Support OpenRouter, OpenAI, Anthropic alongside Ollama  
**Spec:** `LLM_PROVIDER` env var, provider-specific API keys in sidebar, fallback to Ollama  
**Status:** Deferred — local-first flow must be stable first

### Authenticated Page Scraping (Phase B of AI-009)
**Goal:** Scraper can access pages behind login via credential injection  
**Status:** Deferred — see `FEATURE_SPEC_multi_page_scraping.md` Phase B

### n8n Integration
**Goal:** Trigger generation from Jira webhooks, report to Slack  
**Status:** Low priority — Phase 4+

---

## 📋 Fix Log

### Session 3 (2026-03-06)
- B-001, B-002, B-003, B-005 closed
- Phase A (auto-save), B (coverage), C (run now core) complete

### Session 4 (2026-03-07)
- AI-001 (page context scraper) complete
- Coverage number-based matching fixed
- Run output persistence fixed
- Jira report download added
- `pytest.ini` — removed `generated_tests` from testpaths

### Session 5 (2026-03-10)
- R-003 complete — `src/report_utils.py` extracted and tested

### Session 8 (2026-03-13)
- R-001 through R-006 complete
- Cline loop recovery applied
- load_dotenv fix, URL normalisation, content persistence, download crash fixed

### Session 9 (2026-03-16)
- BREAK-1 identified — `src/pytest_output_parser.py` missing (CI blocker)
- BREAK-2 identified — session state wipe in `display_run_button()`
- B-006 identified — parser banner wrong on mixed pass/fail
- B-007 identified — error panels duplicated
- B-008 identified — Run Status column never populates
- AI-009 (multi-page scraping) added as critical priority
- `FEATURE_SPEC_multi_page_scraping.md` created
- AI-003 confirmed still open (27b model hitting timeout despite .env at 300 — load_dotenv timing issue suspected)
