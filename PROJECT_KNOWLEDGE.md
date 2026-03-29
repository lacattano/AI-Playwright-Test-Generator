# PROJECT_KNOWLEDGE.md

## Project Overview

**AI Playwright Test Generator** — An AI-powered tool that generates Playwright Python test scripts from user stories and produces Jira-ready evidence bundles.

**Repository:** https://github.com/lacattano/AI-Playwright-Test-Generator

**Current Status:** Active development — CI green. Streamlit UI working, LLM pipeline connected, page context scraper wired in, all report formats generating. AI-002 (user story parser) in progress via Cline.

---

## ⚠️ Known Broken Items

> No critical breaks as of 2026-03-29. BREAK-1 and BREAK-2 were resolved in session 9.
> See **Logged Bugs** in the backlog section for non-blocking issues.

---

## Tech Stack

### Core Technologies
- **Python 3.13+** — Modern Python with full type hint support
- **Playwright** — Browser automation framework (sync API only — never async)
- **pytest** — Professional test framework (pytest-playwright integration)
- **Ollama** — Local LLM serving (model user-configurable; `qwen3.5:27b` recommended)
- **Streamlit** — Non-technical user UI
- **GitHub Actions** — CI/CD pipeline
- **Codecov** — Test coverage tracking
- **uv** — Package manager (NOT pip — always use `uv add` / `uv sync`)

### Key Dependencies
```
playwright>=1.45.0
pytest>=8.0.0
pytest-playwright>=0.4.0
pytest-html
pytest-json-report
ollama>=0.1.0
openai>=1.12.0
python-dotenv>=1.0.0
requests>=2.31.0
streamlit>=1.32.0
```

---

## Architecture Decisions (FINAL)

### ✅ Test Format: Pytest (DECIDED 2026-03-03)
- **Use:** pytest-playwright with sync API
- **Don't use:** Native async/await standalone tests
- **Reason:** Professional standard, better reporting, rich ecosystem
- **Impact:** All generated tests use pytest fixtures, expect() assertions, organised test discovery

### ✅ Screenshot Link Strategy: Multi-Format (DECIDED 2026-03-03)
- **Generate automatically:** 3 formats per evidence bundle
  1. `local.md` — Relative paths for local viewing/sharing
  2. `jira.md` — Jira attachment format (`!filename.png|thumbnail!`)
  3. `standalone.html` — Base64 embedded, fully self-contained
- **Reason:** Each format serves a specific purpose; generating all three is fast

### ✅ LLM Usage: Smart Hybrid Mode (DECIDED 2026-03-03)
- **Default mode:** "Smart" (hybrid regex + LLM)
- **Decision logic:**
  - Try regex parsing first (free, instant)
  - Use LLM only if: >3 criteria found, regex finds nothing, or ambiguous keywords present
  - User-configurable: Lightweight (regex only), Smart (default), Always LLM

### ✅ UI: Streamlit (DECIDED 2026-03-05)
- **Use:** Streamlit for non-technical user interface
- **Don't use:** Flask/Django/React — too much overhead for this use case
- **Entry point:** `streamlit_app.py` — launch with `bash launch_ui.sh`

### ✅ Package Manager: uv (DECIDED 2026-03-05)
- **Use:** `uv add <package>`, `uv sync`, `uv run`
- **Never use:** `pip install` directly
- **Reason:** Project uses uv.lock; pip is not on PATH in this setup

---

## Environment Setup

### Required Environment Variables
```bash
# .env (NEVER COMMIT)
OLLAMA_MODEL=qwen3.5:27b
OLLAMA_TIMEOUT=300
OLLAMA_BASE_URL=http://localhost:11434
```

> ⚠️ `OLLAMA_TIMEOUT` is only respected if `load_dotenv()` is called **before** `LLMClient`
> initialises. This is done at the top of `streamlit_app.py`. If timeout seems ignored,
> check that no module-level `LLMClient()` instantiation happens at import time.

### Development Setup
```bash
# 1. Clone repository
git clone https://github.com/lacattano/AI-Playwright-Test-Generator
cd AI-Playwright-Test-Generator

# 2. Create virtual environment and install dependencies
uv sync

# 3. Activate venv (Git Bash / Windows)
source .venv/Scripts/activate

# 4. Install playwright browsers
playwright install chromium

# 5. Configure environment
cp .env.example .env
# Edit .env — set OLLAMA_TIMEOUT=300, OLLAMA_MODEL=qwen3.5:27b

# 6. Start Ollama (in separate terminal)
ollama serve   # if not already running as a service

# 7. Launch UI
bash launch_ui.sh
```

### Running Tests
```bash
# Run all unit tests for the tool itself
pytest tests/ -v

# Run generated tests only
pytest generated_tests/ -v

# Run with headed browser (see the browser)
pytest generated_tests/ --headed -v
```

### Commit Process
```bash
# 1. Lint + type-check
bash fix.sh        # runs ruff + mypy

# 2. Unit tests
pytest tests/ -v

# 3. Stage ALL changes before committing (pre-commit checks staged version)
git add -A
git diff --staged --stat

# 4. Commit (no backticks in message)
git commit -m "your message here"
git push
```

> ⚠️ Always `git add` fixes **before** running pre-commit or committing. pre-commit
> stashes unstaged files and checks the stale staged version — you will commit a broken
> state without realising it.

---

## File Structure

```
AI-Playwright-Test-Generator/
├── .github/workflows/
│   └── ci.yml                          # GitHub Actions CI/CD
├── cli/                                # CLI module
│   ├── config.py
│   ├── evidence_generator.py
│   ├── input_parser.py
│   ├── main.py
│   ├── report_generator.py
│   ├── story_analyzer.py
│   └── test_orchestrator.py
├── generated_tests/                    # Output: tests produced BY the tool
│   ├── mock_insurance_site.html        # Mock test environment
│   └── test_*.py                       # Generated test files
├── screenshots/                        # Screenshot evidence storage
├── src/
│   ├── __init__.py
│   ├── code_validator.py               # PLANNED (B-009) — ast.parse() guard before saving tests
│   ├── file_utils.py                   # save_generated_test, rename_test_file, normalise_code_newlines
│   ├── llm_client.py                   # PROTECTED — Ollama API client
│   ├── page_context_scraper.py         # Headless scraper, returns PageContext (subprocess-based)
│   ├── prompt_utils.py                 # _PAGE_CONTEXT_RULES, prompt assembly helpers
│   ├── pytest_output_parser.py         # parse pytest stdout → RunResult / TestResult
│   ├── report_utils.py                 # generate_local_report, generate_jira_report, generate_html_report
│   ├── test_generator.py               # PROTECTED — Test generation logic
│   └── user_story_parser.py            # IN PROGRESS (AI-002) — parse user stories into criteria
├── tests/                              # Unit tests FOR the tool itself
│   ├── fixtures/
│   │   └── user_stories/               # PLANNED (AI-006) — 10-15 varied user story examples
│   ├── test_file_utils.py
│   ├── test_page_context_scraper.py
│   ├── test_pytest_output_parser.py
│   ├── test_report_utils.py
│   └── test_user_story_parser.py       # IN PROGRESS (AI-002)
├── .env                                # Local config (NEVER COMMIT)
├── .env.example                        # Template for .env
├── .streamlit/
│   └── config.toml                     # Streamlit theme config
├── AGENTS.md                           # LLM coding agent conventions
├── BACKLOG.md                          # Feature and bug backlog
├── fix.sh                              # Runs ruff + mypy
├── launch_dev.sh                       # Start UI + mock server (dev only)
├── launch_ui.sh                        # Start UI only
├── main.py                             # PROTECTED — CLI entry point
├── pytest.ini                          # Pytest configuration
├── pyproject.toml                      # Project deps (managed by uv)
├── streamlit_app.py                    # Streamlit UI (primary working file — NOT protected)
├── uv.lock                             # Dependency lock file
└── PROJECT_KNOWLEDGE.md               # This file
```

---

## Protected Files (DO NOT MODIFY Without Explicit Request)

| File | Reason |
|------|--------|
| `src/llm_client.py` | Ollama API client — working correctly |
| `src/test_generator.py` | Core generation logic — working correctly |
| `main.py` | CLI entry point — referenced in docs as `python -m cli.main` |
| `.github/workflows/ci.yml` | CI/CD configured and working |

**Rule:** Always ask before modifying these files.

> ⚠️ `streamlit_app.py` is **NOT** in the protected list. It is the primary working file
> and is expected to be edited frequently. Some LLM agents have incorrectly treated it as
> protected — this is wrong.

---

## Forbidden Actions (NEVER DO)

- NEVER commit `.env` files — Contains sensitive configuration
- NEVER commit `__pycache__/` — Python bytecode cache
- NEVER use `pip install` — Use `uv add` instead
- NEVER use native async format for tests — pytest sync format is decided
- NEVER remove type hints — Full type annotation is project standard
- NEVER force push to main without explicit request
- NEVER rename `generated_tests/` — Hardcoded in `main.py` and `src/test_generator.py`

---

## Key Implementation Details

### `streamlit_app.py` — Current Behaviour
- Sidebar (Settings) is always visible from page load
- LLM model selector fetches live from `ollama list` via `_get_ollama_models()`
- `load_dotenv()` is called at startup so `OLLAMA_TIMEOUT` is applied before `LLMClient` initialises
- Text area (Paste story tab) is live — no intermediate confirm button
- URL is auto-normalised: `www.foo.com` becomes `https://www.foo.com` before scraping
- Scraper result shown in sidebar: success with element count, or warning with error snippet
- Generated code + Coverage tabs persist after any button click (rendered from `session_state`)
- Three download buttons always visible: `local.md`, `jira.md`, `standalone.html`

### `src/page_context_scraper.py` — How It Works
- Runs Playwright in a **subprocess** (bypasses Streamlit's Windows ProactorEventLoop issue)
- Returns `tuple[PageContext | None, str | None]` — always unpack as `ctx, err = scrape_page_context(url)`
- Failure is non-fatal — generation continues without page context if scraper fails
- `PageContext.to_prompt_block()` formats elements as plain text for LLM prompt injection
- **Known limitation:** Single-page only. No session state — authenticated pages redirect to login,
  producing useless repeated context. AI-009 will address this.

### `src/prompt_utils.py` — Locator Rules
- Contains `_PAGE_CONTEXT_RULES` — rules injected into LLM prompt to guide selector generation
- **Planned additions (not yet implemented):**
  - NEVER use bare tag names as locators (e.g., `page.locator("input")`)
  - Selector priority: `data-testid` > `id` > `role+name` > `text` — never bare tags
  - Never reuse the same selector across different pages

### `src/pytest_output_parser.py` — How It Works
- `parse_pytest_output(raw: str) -> RunResult` is the single public entry point
- Parses PASSED/FAILED lines with regex, extracts inline error messages
- Collects totals from the `N passed, M failed in Xs` summary line
- `RunResult.raw_output` preserves the original string for the expander panel in the UI
- **No Streamlit imports** — safe to import in unit tests without triggering `st.set_page_config()`

### `src/report_utils.py` — Report Generators
- `generate_local_report(rows)` → `local.md` with relative screenshot paths
- `generate_jira_report(rows)` → `jira.md` with `!filename.png|thumbnail!` syntax
- `generate_html_report(rows)` → `standalone.html` with base64-embedded images
- All three expect a `list[dict]` built by `_build_report_dicts()` in `streamlit_app.py`

### `src/file_utils.py` — Key Functions
- `save_generated_test(test_code, story_text, base_url)` — saves to `generated_tests/`
- `rename_test_file(old_path, new_stem)` — renames with validation
- `normalise_code_newlines(code)` — normalises `\r\n` and `\r` to `\n`

### Coverage Analysis — How It Works
After generation, `streamlit_app.py`:
1. Extracts test function names with `re.findall(r"^def (test_\w+)", code, re.MULTILINE)`
2. For each criterion, matches by `test_NN_` prefix then falls back to keyword overlap
3. Builds `RequirementCoverage` objects stored in `st.session_state.coverage_analysis`
4. `display_coverage()` renders the Coverage tab from session state

---

## Recurring Bugs to Watch For (Cline / LLM Loop Patterns)

These have appeared multiple times — check for them after any AI-assisted edit:

| Bug | Symptom | Fix |
|-----|---------|-----|
| Ambiguous variable `l` | ruff E741 | Rename to `line` in list comprehensions |
| `tr` redefined in inner loop | mypy error | Use `found` or `match` for inner `run_map.get()` result |
| `scrape_page_context` not unpacked | TypeError | Always use `ctx, err = scrape_page_context(url)` |
| `base_url.split(':')[1]` | list index out of range | Use `re.sub(r"[^\w]", "_", base_url)` for slugs |
| Tabs inside button block | Content disappears on rerun | Render from `session_state` outside button block |
| `import re` inside function body | ruff E402 | Move to top-level imports |
| Invented imports | ModuleNotFoundError | Verify import exists before accepting output |
| Duplicate function definitions | SyntaxError or wrong behaviour | Rebuild from last known-good output |
| Session state wipe pattern | Results blank after button click | Never set state key to None/empty after setting real value |
| LLM "it passed" without explanation | Test passing for wrong reason | Require mechanistic explanation — what exactly matched? |
| B009 linting rule confused with B-009 bug | Wrong plan from LLM | B-009 is the ast.parse validation bug ID; B009 is a flake8-bugbear rule — unrelated |

**Recovery strategy:** When Cline corrupts a file, rebuild from the last known-good output and re-apply changes cleanly. Do not attempt further incremental edits on a corrupted file.

**Cline behaviour:** Add "Stop after that" to prompts and name specific MCP tool calls explicitly. If Cline enters a death spiral: stop immediately → `git reset --hard` to last working commit → resume with scoped task.

---

## Common Issues & Solutions

### LLM Timeout / Empty Response
**Symptoms:** "LLM returned empty response", debug expander shows empty raw response  
**Cause:** `OLLAMA_TIMEOUT` too low (default 60s), or `load_dotenv()` firing after `LLMClient` initialises  
**Solution:** Set `OLLAMA_TIMEOUT=300` in `.env`; confirm `load_dotenv()` is called at the very top of `streamlit_app.py` before any imports that instantiate `LLMClient`

### Generated Tests Fail With Wrong Locators
**Symptoms:** `AssertionError: Locator expected to be visible`, invented element names like `username_input`  
**Cause 1:** Page scraper failed silently because URL was missing `https://` — now auto-added  
**Cause 2:** Scraper only captures the first page. Selectors for pages 2+ are guessed — this is the core limitation AI-009 will fix.  
**Solution short-term:** Check sidebar for scraper warning. Ensure Base URL starts with `https://`.

### venv not activating / wrong environment
```bash
rm -rf .venv
uv sync
source .venv/Scripts/activate
```

### mypy cache corruption
**Symptoms:** mypy reports errors on files that are clean  
**Solution:** `rm -rf .mypy_cache` then re-run

### Port 8501 already in use
```bash
taskkill //F //IM streamlit.exe    # PowerShell
pkill -f streamlit                  # Git Bash
```

### Ollama "address already in use"
Ollama is already running — this is fine, ignore the error.

---

## Models Available Locally

| Model | Size | Architecture | Use |
|-------|------|--------------|-----|
| `qwen3.5:27b` | ~16 GB | Dense — true 27B | **Recommended for code generation** — better quality than 35b on this hardware |
| `qwen3.5:35b` | 23 GB | MoE — ~3B active params per token | Previous default; effective reasoning ~10B dense equivalent |
| `qwen2.5-coder:1.5b-base` | 986 MB | Dense | Fast testing, ~6 sec, simpler output |

> The model is user-configurable in the sidebar via `_get_ollama_models()`. `.env`
> `OLLAMA_MODEL` sets the default. `qwen3.5:27b` is the recommended default for code
> generation quality on AMD Strix Halo (64 GB unified memory).

---

## Implementation Roadmap

### Completed

| Phase | Status |
|-------|--------|
| Phase 0: Setup & Cleanup | Done |
| Phase UI: Streamlit Interface | Done |
| AI-001: Page Context Scraper | Done |
| AI-008: Run Results Parser | Done (BREAK-1 resolved) |
| R-001 to R-006: Feature Recovery | Done (2026-03-13) |
| BREAK-1: `src/pytest_output_parser.py` missing | Fixed |
| BREAK-2: Session state wipe in `display_run_button()` | Fixed |

### R-001 to R-006 Detail

| ID | Feature |
|----|---------|
| R-001 | Ollama model selector in sidebar |
| R-002 | Pipeline log |
| R-003 | `normalise_code_newlines()` on generated code |
| R-004 | Page context scraping wired into generation flow |
| R-005 | Three report download buttons |
| R-006 | Rename test file UI |

### In Progress

| ID | Feature |
|----|---------|
| AI-002 | User story parser (`src/user_story_parser.py`) — TDD with fixtures — **Cline active** |

### Logged Bugs (Non-Blocking)

> Bug IDs **must** be documented here or in BACKLOG.md. An ID that exists only in
> conversation history is invisible to LLMs in future sessions.

| ID | Symptom | Status |
|----|---------|--------|
| B-006 | Parser banner shows wrong result on mixed pass/fail runs | Logged |
| B-007 | Duplicate error panels in run results UI | Logged |
| B-008 | Run Status column never populates in results table | Logged |
| B-009 | No `ast.parse()` validation before saving generated test files — truncated LLM output saved silently | Logged — planned `src/code_validator.py` |

### Backlog (Next — after AI-002)

| ID | Feature | Notes |
|----|---------|-------|
| B-009 | `src/code_validator.py` — `ast.parse()` guard before saving | Follows AGENTS.md Section 9 conventions |
| AI-003 | Update `.env.example` with `OLLAMA_TIMEOUT=300` and `OLLAMA_MODEL=qwen3.5:27b` | Quick |
| AI-004 | Phase C UI gaps (env dropdown, re-run failed, screenshot viewer) | |
| AI-005 | Extract coverage helpers to `src/coverage_utils.py` | |
| AI-006 | Create `tests/fixtures/user_stories/` with 10-15 format examples | Feeds AI-002 validation |
| AI-007 | Remove `_generate_test_content()` from CLI orchestrator | |
| AI-009 Phase A | Multi-page scraping: user-provided URL list | Prerequisite for Phase B |
| AI-009 Phase B | Multi-page scraping: Playwright-driven authenticated flow following | **Core value driver** — see note below |

> **AI-009 is the highest-priority feature.** Without multi-page scraping, all tests beyond
> page one use guessed selectors, undermining the tool's core value regardless of other
> improvements. Graceful failure is required for SSO, MFA, and CAPTCHA (out of scope with
> explicit error messages, not silent failures).

---

## Resources & Links

- **Repository:** https://github.com/lacattano/AI-Playwright-Test-Generator
- **Playwright Docs:** https://playwright.dev/python/
- **pytest Docs:** https://docs.pytest.org/
- **Ollama Docs:** https://ollama.com/docs
- **Streamlit Docs:** https://docs.streamlit.io

---

## Version History

- **2026-03-03:** Initial creation, Phase 1-4 roadmap defined, architecture decisions finalised
- **2026-03-05:** Session 2 — Streamlit UI built, uv adopted, mock site updated, BACKLOG.md created
- **2026-03-12:** Sessions 3-7 — AI-001 page context scraper, coverage mapping, run results parser, multiple bug fixes, feature recovery plan identified
- **2026-03-13:** Session 8 — R-001 through R-006 implemented, Cline loop recovery, load_dotenv fix, URL normalisation, content persistence fix, download crash fix
- **2026-03-16:** Session 9 — BREAK-1/BREAK-2 identified and fixed; `src/pytest_output_parser.py` committed; session state wipe removed from `display_run_button()`
- **2026-03-29:** Docs refresh — PROJECT_KNOWLEDGE.md updated: stale breaks cleared, models table updated (qwen3.5:27b recommended), `src/prompt_utils.py` added to file structure, B-006 through B-009 logged, AI-009 phases documented, streamlit_app.py explicitly noted as non-protected

---

*Last Updated: 2026-03-29*
*Project Status: CI green — AI-002 in progress (Cline)*
*Current Phase: AI-002 → B-009 → AI-009*
