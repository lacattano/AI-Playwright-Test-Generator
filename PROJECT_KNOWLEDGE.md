# PROJECT_KNOWLEDGE.md

## Project Overview

**AI Playwright Test Generator** - An AI-powered tool that generates Playwright Python test scripts from user stories and produces Jira-ready evidence bundles.

**Repository:** https://github.com/lacattano/AI-Playwright-Test-Generator

**Current Status:** Active development — Streamlit UI working, LLM pipeline connected, save/coverage/run workflow complete, demo-ready

---

## Tech Stack

### Core Technologies
- **Python 3.13+** - Modern Python with full type hint support
- **Playwright** - Browser automation framework
- **pytest** - Professional test framework (pytest-playwright integration)
- **Ollama** - Local LLM serving (qwen3.5:35b model)
- **Streamlit** - Non-technical user UI
- **GitHub Actions** - CI/CD pipeline
- **Codecov** - Test coverage tracking
- **uv** - Package manager (NOT pip — always use `uv add` / `uv sync`)

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
- **Reason:** Professional standard (90% of QA jobs require pytest), better reporting, rich ecosystem
- **Impact:** All generated tests use pytest fixtures, expect() assertions, organised test discovery

### ✅ Screenshot Link Strategy: Multi-Format (DECIDED 2026-03-03)
- **Generate automatically:** 3 formats per evidence bundle
  1. `report_local.md` - Relative paths for local viewing/sharing
  2. `report_jira.md` - Jira attachment format (`!filename.png|thumbnail!`)
  3. `report.html` - Base64 embedded for email/archive (fully self-contained)
- **Reason:** Each format serves specific purpose, generating all three is fast, no wrong choice possible

### ✅ LLM Usage: Smart Hybrid Mode (DECIDED 2026-03-03)
- **Default mode:** "Smart" (hybrid regex + LLM)
- **Decision logic:**
  - Try regex parsing first (free, instant)
  - Use LLM only if: >3 criteria found, regex finds nothing, ambiguous keywords present
  - User-configurable: Lightweight (regex only), Smart (default), Always LLM

### ✅ UI: Streamlit (DECIDED 2026-03-05)
- **Use:** Streamlit for non-technical user interface
- **Don't use:** Flask/Django/React — too much overhead for this use case
- **Reason:** Pure Python, single file, deployable in one command, fits existing stack
- **Entry point:** `streamlit_app.py` — launch with `bash launch_ui.sh`

### ✅ Package Manager: uv (DECIDED 2026-03-05)
- **Use:** `uv add <package>`, `uv sync`, `uv run`
- **Never use:** `pip install` directly — uv manages the venv and pyproject.toml together
- **Reason:** Project uses uv.lock, pip is not on PATH in this setup

### ✅ Helper Functions Location: `src/` modules (DECIDED 2026-03-06)
- **Rule:** Helper functions that need unit testing must NOT live in `streamlit_app.py`
- **Reason:** Importing `streamlit_app` outside a Streamlit context triggers `st.set_page_config()` and crashes
- **Pattern:** Create `src/module_name.py` → import into `streamlit_app.py` → test via `src.module_name` directly
- **Existing examples:** `src/file_utils.py` (save, rename, normalise), coverage helpers pending move to `src/coverage_utils.py`

---

## Environment Setup

### Required Environment Variables
```bash
# .env (NEVER COMMIT)
OLLAMA_MODEL=qwen3.5:35b
OLLAMA_TIMEOUT=300
OLLAMA_BASE_URL=http://localhost:11434
```

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
# Edit .env — set OLLAMA_TIMEOUT=300

# 6. Start Ollama (in separate terminal)
ollama serve   # if not already running as a service

# 7. Launch UI (your own site)
bash launch_ui.sh

# 7. Launch UI + mock insurance site (development only)
bash launch_dev.sh
```

### Running Tests
```bash
# Run all tests
pytest -v

# Run generated tests only
pytest generated_tests/ -v

# Run with headed browser (see the browser)
pytest generated_tests/ --headed -v
```

---

## File Structure

### Current Structure
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
│   ├── file_utils.py                   # Save, rename, normalise helpers
│   ├── llm_client.py                   # ✅ PROTECTED - Ollama API client
│   └── test_generator.py              # ✅ PROTECTED - Test generation logic
├── tests/                              # Unit tests FOR the tool itself
│   ├── test_file_utils.py              # Tests for src/file_utils.py
│   ├── test_llm_client.py              # Tests for src/llm_client.py
│   ├── test_normalise_code_newlines.py # Tests for B-002 fix
│   └── test_test_generator.py          # Tests for src/test_generator.py
├── .env                                # Local config (NEVER COMMIT)
├── .env.example                        # Template for .env
├── .streamlit/
│   └── config.toml                     # Streamlit theme config
├── launch_dev.sh                       # Start UI + mock site (dev only)
├── launch_ui.sh                        # Start UI only (general use)
├── main.py                             # ✅ PROTECTED - CLI entry point
├── pytest.ini                          # Pytest configuration
├── pyproject.toml                      # Project deps (managed by uv)
├── streamlit_app.py                    # Streamlit UI
├── uv.lock                             # Dependency lock file
├── BACKLOG.md                          # Feature backlog
├── FEATURE_SPEC_page_context_scraper.md # AI-001 feature spec
└── PROJECT_KNOWLEDGE.md               # This file
```

---

## Protected Files (DO NOT MODIFY Without Explicit Request)

- `src/llm_client.py` - ✅ Working correctly, handles Ollama API
- `src/test_generator.py` - ✅ Working correctly, generates and saves tests
- `main.py` - ✅ Working CLI interface
- `.github/workflows/ci.yml` - ✅ CI/CD configured and working

**Rule:** Always ask before modifying these files. If a bug is in one of these files, note it in BACKLOG.md and confirm the fix explicitly before editing.

---

## Forbidden Actions (NEVER DO)

- ❌ **NEVER commit `.env` files** - Contains sensitive configuration
- ❌ **NEVER commit `__pycache__/` directories** - Python bytecode cache
- ❌ **NEVER use `pip install`** - Use `uv add` instead
- ❌ **NEVER use native async format for tests** - pytest sync format is decided
- ❌ **NEVER remove type hints** - Project standard is full type annotation
- ❌ **NEVER force push to main** without explicit request
- ❌ **NEVER put testable helper functions in `streamlit_app.py`** - put them in `src/` instead

---

## Common Issues & Solutions

### Issue: venv not activating / wrong environment
**Symptoms:** `(vs-projects)` shown instead of `(playwright-test-generator)`, pip not found
**Cause:** Old venv from renamed project, or wrong terminal
**Solution:**
```bash
rm -rf .venv
uv sync
source .venv/Scripts/activate   # Git Bash / Windows
```

### Issue: LLM Timeout / Empty Response
**Symptoms:** "LLM returned empty response" in pipeline log
**Cause:** OLLAMA_TIMEOUT too low (default 60s), or .env not loading
**Solution:**
- Set `OLLAMA_TIMEOUT=300` in `.env`
- Confirm `.env` is in project root
- `load_dotenv()` must be called before LLMClient initialises

### Issue: Generated Tests Have SyntaxError on Import Lines
**Symptoms:** `SyntaxError` on line 1, imports concatenated e.g. `from playwright.sync_api import Pageimport pytest`
**Cause:** LLM response has newlines stripped in the extraction pipeline (B-002)
**Solution:** Fixed — `normalise_code_newlines()` now applied automatically after generation

### Issue: Locator Resolves to Multiple Elements
**Symptoms:** `strict mode violation: get_by_label("X") resolved to 2 elements`
**Cause:** Same label exists on multiple forms (e.g. vehicle form + add driver form)
**Solution:** Use specific ID locator: `page.locator("#specificId")` instead of `get_by_label`
**Long-term fix:** AI-001 page context scraper will detect ambiguous labels before generation

### Issue: Pre-commit fails with "files were modified by this hook"
**Symptoms:** ruff or ruff-format modifies files then commit aborts
**Cause:** Pre-commit auto-fixes the files but can't commit mid-run
**Solution:** `git add -A` then `git commit` again — the fixes are already applied

### Issue: mypy `no-redef` error on type annotation
**Symptoms:** `error: Name "x" already defined on line N`
**Cause:** Variable annotated inside a `try` block then re-annotated outside it
**Solution:** Declare the variable with the wider type (`str | None = None`) before the `try` block

### Issue: Last 2 Criteria Get No Tests
**Symptoms:** User story with 4+ acceptance criteria — only first 2-3 tests generated, last 2-3 criteria have no tests
**Cause:** LLM truncation of response or failure to iterate through all criteria
**Solution:** Fixed in `streamlit_app.py` — `generate_test_for_story()` now includes explicit prompt:
- Criteria enumerated with line numbers: `1. Criterion 1`, `2. Criterion 2`, etc.
- Clear instruction: "generate ONE test per criterion"
- Total count displayed: "(Total: N criteria)"
- Critical requirement section: "DO NOT skip, combine, or omit any criteria"
- Final warning: "DO NOT skip the last criteria — all N criteria must have tests"

### Issue: Run/Download Buttons Clear Page
**Symptoms:** After generating test, clicking "Run Now" or download buttons causes page to clear, shows only user story input
**Cause:** Button click triggers `st.rerun()` without preserving test output from local variables
**Solution:** Fixed — output section now reads from `st.session_state` using `.get()` method:
```python
test_code = st.session_state.get("generated_test")
saved_path = st.session_state.get("saved_test_path")
story_for_coverage = st.session_state.get("last_story", "")
```
This persists data across reruns, preventing page clearing.

### Issue: Pre-commit fails with "files were modified by this hook"
- [x] Verify the prompt fix actually addresses "last 2 criteria get no tests"
- [x] Read streamlit_app.py sections about the generate function and prompt
- [x] Confirm main() output rendering changes are correct
- [x] Update PROJECT_KNOWLEDGE.md with relevant information about the fixes
</task_progress>

### Issue: `bash` command not found
**Symptoms:** Running `bash launch_ui.sh` fails
**Cause:** You're in PowerShell, not Git Bash
**Solution:** Switch terminal to Git Bash, or run `uv run streamlit run streamlit_app.py`

### Issue: Port 8501 already in use
**Symptoms:** `Port 8501 is not available`
**Cause:** Previous Streamlit instance still running
**Solution:** `taskkill //F //IM streamlit.exe` (PowerShell) or `pkill -f streamlit` (Git Bash)

### Issue: Ollama "address already in use"
**Symptoms:** `Error: listen tcp 127.0.0.1:11434: bind: Only one usage`
**Cause:** Ollama is already running — this is fine, ignore the error

---

## Models Available Locally
| Model | Size | Use |
|-------|------|-----|
| `qwen3.5:35b` | 23 GB | Best quality output, ~2 min response |
| `qwen2.5-coder:1.5b-base` | 986 MB | Fast testing, ~6 sec response, simpler output |

---

## Implementation Roadmap

### ✅ Phase 0: Setup & Cleanup (Complete — 2026-03-05)
- venv issues resolved, uv adopted as package manager
- pytest.ini configured with playwright settings
- CI/CD working

### ✅ Phase UI: Streamlit Interface (Complete — 2026-03-05)
- `streamlit_app.py` built and running
- Dynamic Ollama model list from `ollama list`
- URL validation, pipeline log, all 3 report tabs, ZIP download
- `.env` loading fixed with explicit path

### ✅ Phase Save/Review/Run: Workflow (Complete — 2026-03-06)
- **Phase A:** Auto-save to `generated_tests/` with timestamped slug filename, rename UI
- **Phase B:** Test function parser, criteria extractor, keyword-based coverage mapping, coverage metrics table with colour-coded status badges
- **Phase C:** `run_playwright_test()` via pytest subprocess, pass/fail display, collapsible output
- **Bug fixes:** B-001 (async→sync), B-002 (newline normalisation), B-003 (auto-save), B-005 (launch scripts split)

### 🚧 Phase 2: Page Context Scraper (Next — AI-001)
**Goal:** Visit target URL before generation, inject real DOM selectors into LLM prompt
**Spec:** See `FEATURE_SPEC_page_context_scraper.md`
**Files to Create:**
- `src/page_context_scraper.py`
- `tests/test_page_context_scraper.py`

### 🚧 Phase 1: Input Format Flexibility (AI-002)
**Goal:** Move criteria extraction out of `streamlit_app.py` into a proper tested module
**Files to Create:**
- `src/user_story_parser.py`
- `tests/test_user_story_parser.py`

### 🚧 Coverage Utils Extract (AI-005)
**Goal:** Move coverage dataclasses and helpers from `streamlit_app.py` to `src/coverage_utils.py`
**Files to Create:**
- `src/coverage_utils.py`
- `tests/test_coverage_utils.py`

### 🚧 Phase 3: Evidence Collection
- `src/screenshot_manager.py`
- `reports/jira_reporter.py`
- `reports/evidence_bundle_generator.py`

### 🚧 Phase 4: Test Orchestration
- `src/test_suite_executor.py`
- `src/result_aggregator.py`

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
- **2026-03-05:** Session 2 — Streamlit UI built and connected, venv issues resolved, uv adopted, mock site updated with Add Driver form, pytest.ini updated, BACKLOG.md created
- **2026-03-06:** Session 3 — Save/Review/Run workflow (Phases A/B/C), B-001/002/003/005 closed, launch scripts split, pre-commit issues resolved

---

*Last Updated: 2026-03-06*
*Project Status: Active Development*
*Current Phase: Page Context Scraper (AI-001) next*
