# BACKLOG.md
## AI Playwright Test Generator

Last updated: 2026-03-29

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

### B-006 — Parser banner wrong when mix of pass/fail
**Fixed (Session 10):** Current parser implementation correctly uses last summary-line match.
Regression tests added: `test_b006_mixed_pass_fail_banner_correct`, `test_b006_all_fail_banner`.

### B-007 — Error panels duplicated in results view
**Fixed (Session 10):** Removed duplicate error rendering loop from `display_coverage()`. Errors
now render only in `display_run_button()`.

### B-009 — No ast.parse() validation before saving generated test files
**Fixed (Session 11):** `src/code_validator.py` created with `validate_python_syntax()`.
Integrated into `src/file_utils.py` `save_generated_test()` — raises `ValueError` before
writing if code fails syntax check.

### BREAK-1 — `src/pytest_output_parser.py` missing (CI BLOCKER)
**Fixed (Session 9):** `src/pytest_output_parser.py` committed.

### BREAK-2 — Session state wipe blanks run results panel
**Fixed (Session 9):** Reset lines removed from `display_run_button()`.

---

## 🔴 Open Bugs

### B-004 — Ambiguous locators when same label exists on multiple forms
**Symptom:** `strict mode violation: get_by_label("Driver Name") resolved to 2 elements`
**Fix (short term):** Use `page.locator("#specificId")` instead of `get_by_label`
**Fix (long term):** Multi-page scraping (AI-009) injects real selectors
**Priority:** Medium — AI-009 should prevent recurrence

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

### AI-009 — Multi-Page Scraping ⭐ Phase A COMPLETE, Phase B In Progress
**What:** Allow the scraper to collect elements from multiple pages in a user flow,
not just the base URL
**Phase A (complete — Session 10):** Backend `scrape_multiple_pages()`, `MultiPageContext`,
`ScraperState` in `src/page_context_scraper.py`. UI integrated in `streamlit_app.py` with
additional URLs text area, conditional scraping, per-page sidebar feedback.
**Phase B (in progress — Session 11):** Authenticated journey scraping — single browser
session follows user-defined steps (goto, click, fill, capture, wait), credential profiles
in session state, auth redirect detection, SSO/MFA/CAPTCHA explicit errors.
**Spec:** `FEATURE_SPEC_AI009_phase_b.md`
**Priority:** Highest — core value driver

### ✅ AI-002 — User Story Parser Module (COMPLETE)
**What:** Move criteria extraction into `src/user_story_parser.py` with proper
format support: Gherkin, Jira AC bullets, numbered, free-form
**Status:** Complete — Session 11 (2026-03-29)

### AI-005 — Move coverage helpers to `src/coverage_utils.py`
**What:** Extract remaining coverage helpers out of `streamlit_app.py`
**Why:** Cannot be unit tested without triggering Streamlit import crash
**Note:** `src/coverage_utils.py` and `tests/test_coverage_utils.py` already exist with
core functions extracted. Remaining work: verify no coverage logic is still in `streamlit_app.py`
**Priority:** High — also required to properly fix B-008

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

## 🌟 Future Enhancements

> Note: Each of these needs a detailed design session before handing to Cline.
> They are listed here to capture intent — not ready for implementation yet.

---

### AI-010 — Page Object Model Generation Mode
**What:** Add a toggle in the UI — "Simple tests" vs "Page Object Model" — that
changes how the LLM structures its output.

**Why it matters:** Currently generated tests are standalone functions. If the site
changes (e.g. a URL or button label), every test that references it needs updating
individually. Page Object Model (POM) puts all page interactions into a class — one
change in one place fixes all tests that use it. Standard pattern in professional
test suites.

**How it would work:**
- The scraper already collects everything needed (elements, locators, forms per page)
- The prompt instructs the LLM to generate a `class LoginPage:` with locators as
  attributes and interactions as methods, then generate test functions that use it
- One class per scraped page URL
- Tests become short and readable; page logic lives in one maintainable place

**Design session needed:** Yes — prompt structure, file layout (separate file per
page object vs single file), how classes are named from URLs
**Priority:** High — meaningful differentiator for portfolio

---

### AI-011 — Test Run History Chart
**What:** A pass/fail trend chart showing test results over time.

**Why it matters:** A single run result tells you pass/fail now. A history chart
tells you whether things are getting better or worse, and when a regression was
introduced.

**How persistence works:** A local `run_history.json` file in the project root.
Every completed run appends a record: timestamp, story name, passed count, failed
count, total duration. The chart reads from this file on load. File is excluded
from git via `.gitignore` — it's user-specific data, not project code.

**What the chart shows:** Line or bar chart — X axis is time, Y axis is pass rate.
Each point is one run. Colour coded green/amber/red by pass rate threshold.

**Design session needed:** Yes — storage format, chart library (Streamlit has
`st.line_chart` built in which may be sufficient), retention policy (how many
runs to keep)
**Priority:** Medium

---

### AI-012 — Selector Confidence Scores
**What:** Score each locator the scraper found by how likely it is to break,
and surface that score in the UI alongside the generated test.

**Why it matters:** Not all selectors are equally reliable. A test built on
`data-testid` attributes will survive UI redesigns. A test built on button
visible text will break the moment someone rewrites the copy. Users should
know which parts of their generated test are fragile before they find out
the hard way in CI.

**How scoring works — based on locator type, not usage frequency:**

| Locator type | Confidence | Reason |
|---|---|---|
| `data-testid` | High | Explicitly added for testing — won't change accidentally |
| `id` attribute | Medium-High | Stable but sometimes auto-generated |
| `name` attribute | Medium | Reliable for forms |
| `aria-label` / role | Medium | Good but changes with UI copy |
| `visible_text` | Low | Breaks when button label changes |
| Bare tag (`input`) | Very Low | Almost always fragile |

The scraper already builds `recommended_locator` for every element — scoring
is a classification step on top of what already exists.

**What the UI shows:** A confidence indicator per test function, and a summary
panel showing how many locators in the generated test are high/medium/low
confidence. Flags tests that are likely to be brittle before they're even run.

**Design session needed:** Yes — scoring thresholds, UI presentation, whether
low-confidence selectors should trigger a warning at generation time
**Priority:** Medium

---

### AI-013 — Coverage Gap Report with Gap Explanations
**What:** A report showing which acceptance criteria have no linked test, with
an explanation of why the gap exists.

**Why it matters:** Knowing a gap exists is useful. Knowing *why* it exists
tells the user what to fix — is it the user story, the scraper, or the LLM?

**Gap explanations the tool can provide:**

| Gap reason | How detected | What user should do |
|---|---|---|
| No matching elements found on page | Scraper found nothing relevant to this criterion | Add the page to the URL list or check the page loads correctly |
| Criterion too ambiguous | No specific keywords the LLM could act on | Rewrite the criterion to be more specific |
| Page not scraped | Relevant page wasn't in the URL list | Add the URL to the additional pages list |
| LLM skipped this criterion | Criterion in the list but no test function references it | Re-run with Always LLM mode or rewrite the criterion |

**Design session needed:** Yes — how to detect each gap type reliably, how to
present the report in the UI, whether this replaces or extends the current
coverage tab
**Priority:** Medium

---

### AI-014 — Test Execution Time Gantt Chart
**What:** A Gantt-style chart showing each test as a horizontal bar, sized by
execution time, so users can understand total suite duration and identify slow tests.

**Why it matters:** QA leads need to know how long a full regression run takes.
If it takes 45 minutes, that affects how often it can run in CI. Identifying
the slowest tests lets users decide which ones to optimise or run separately.

**How it would work:**
- `pytest_output_parser.py` currently stores duration as `0.0` — individual
  test times are in the pytest output but not yet parsed
- Parsing them is a small regex addition to the parser
- The Gantt chart stacks tests horizontally, total width = total suite time
- Colour coded by status (green = passed, red = failed)
- Clicking a bar could expand the error message for failed tests

**Design session needed:** Yes — parsing individual test durations from pytest
output, chart library choice, whether this lives in the run results tab or a
separate analytics tab
**Priority:** Low-Medium

---

### AI-015 — Test Coverage Heat Map
**What:** A visual grid showing which parts of the application have been tested
and how thoroughly, colour coded from red (untested) to green (fully covered).

**Why it matters:** At a glance a QA lead can see where the coverage gaps are
across the whole application — not just for one user story but across all
generated tests. A standard tool in mature QA workflows.

**How it would work:**
- Each cell in the grid represents a page or feature area
- Colour is determined by: number of tests covering that area, confidence
  scores of those tests, pass/fail rate from run history
- Requires run history (AI-011) and selector confidence (AI-012) to be
  meaningful — depends on those features
- Would live in a dedicated "Coverage" or "Analytics" tab

**Design session needed:** Yes — this is the most complex visualisation on
the list. Depends on AI-011 and AI-012 being in place first.
**Priority:** Low — long term goal, needs other features as prerequisites

---

### Cloud LLM Providers
**Goal:** Support OpenRouter, OpenAI, Anthropic alongside Ollama
**Spec:** `LLM_PROVIDER` env var, provider-specific API keys in sidebar, fallback to Ollama
**Status:** Deferred — local-first flow must be stable first

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

### Session 10 (2026-03-21)
- B-007 fixed — removed duplicate error rendering from `display_coverage()`
- B-006 verified working, 2 regression tests added to `test_pytest_output_parser.py`
- AI-003 closed — `OLLAMA_TIMEOUT=300` added to `.env.example`
- AI-009 Phase A complete — multi-page scraper wired into `streamlit_app.py`
- 121 tests passing, ruff clean, mypy clean

### Session 11 (2026-03-29)
- AI-002 complete — `src/user_story_parser.py`, 23 tests, 100% pass rate
- B-009 fixed — `src/code_validator.py` created, integrated into `file_utils.py`
- AI-003 confirmed complete
- AI-009 Phase B spec written — `FEATURE_SPEC_AI009_phase_b.md`
- BACKLOG.md updated — AI-010 through AI-015 added
- LEARNING_PLAN.md created
- PROJECT_KNOWLEDGE.md refreshed

### Session 12 (2026-03-31)
- Streamlit input mode persistence fixed: "Paste story" selection now survives reruns and login-toggle changes.
- Requirement model consistency improved for no-AC inputs: parsing, criteria count, coverage, and reports now use one derived model.
- Report semantics corrected: pre-run states remain pending/unknown and are no longer counted as failed.
- Run output UX cleaned: noisy/duplicate pytest lines reduced and misleading pytest-cov module coverage removed from UI run flow.
- Prompt/context hardening for generated selectors and URLs: stronger use of scraped locators and context URLs with stricter generation guidance.
- Generation guardrails expanded in `src/code_validator.py` for known flaky SauceDemo patterns:
  - invalid `/checkout.html`
  - invalid checkout title assertions
  - brittle exact base URL assertions pre-login
  - weak negative-only checkout URL assertions
- Multi-page restart-from-base scraping improved:
  - captured page now accepted only when URL matches the requested target
  - mismatch now retries (bounded) and surfaces explicit failure details.
- Credential profile active-selection regressions fixed in Streamlit state handling.
