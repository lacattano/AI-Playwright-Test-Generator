# PROJECT_KNOWLEDGE.md

## Project Overview

**AI Playwright Test Generator** — An AI-powered tool that generates Playwright Python test scripts from user stories and produces Jira-ready evidence bundles.

**Repository:** https://github.com/lacattano/AI-Playwright-Test-Generator

**Current Status:** Active development — Streamlit UI working, LLM pipeline connected, page context scraper wired in, all report formats generating. CI currently failing — see **Known Broken Items** below before starting any session.

---

## ⚠️ Known Broken Items (Fix These First)

These issues were confirmed broken as of the last commit (2026-03-13). Fix in order.

### BREAK-1 — `src/pytest_output_parser.py` is missing (CI BLOCKER)
**Symptom:** `pytest tests/ -v` fails with `ModuleNotFoundError: No module named 'src.pytest_output_parser'`  
**Cause:** `tests/test_pytest_output_parser.py` imports the module, but the implementation file was never committed.  
**Fix:** Copy `src/pytest_output_parser.py` from this document's appendix (or the `fix/` branch) into `src/`.  
**Impact:** Until fixed, ALL tests fail in CI — this is the entire reason the last commit did not pass GitHub Actions.

### BREAK-2 — Session state wipe in `display_run_button()`
**Symptom:** After clicking "Run Now", the results panel is always blank.  
**Cause:** In `streamlit_app.py`, inside `display_run_button()`, there are two lines immediately after the results are saved to session state that set them back to `None` and `""`:
```python
# BROKEN — these two lines must be deleted:
st.session_state.last_run_success = None
st.session_state.last_run_output = ""
```
**Fix:** Delete those two lines. The correct block sets values once and leaves them.  
**Impact:** Run results never display, download buttons appear to do nothing.

---

## Tech Stack

### Core Technologies
- **Python 3.13+** — Modern Python with full type hint support
- **Playwright** — Browser automation framework
- **pytest** — Professional test framework (pytest-playwright integration)
- **Ollama** — Local LLM serving (qwen3.5:35b model)
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

# 3. Stage (excluding debug files and cline_tasks/)
git add -A
git diff --staged --stat

# 4. Commit (no backticks in message)
git commit -m "your message here"
git push
```

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
│   ├── file_utils.py                   # save_generated_test, rename_test_file, normalise_code_newlines
│   ├── llm_client.py                   # PROTECTED — Ollama API client
│   ├── page_context_scraper.py         # Headless scraper, returns PageContext
│   ├── pytest_output_parser.py         # ⚠️ BREAK-1: must exist — parse pytest stdout → RunResult
│   ├── report_utils.py                 # generate_local_report, generate_jira_report, generate_html_report
│   └── test_generator.py              # PROTECTED — Test generation logic
├── tests/                              # Unit tests FOR the tool itself
│   ├── test_file_utils.py
│   ├── test_page_context_scraper.py
│   ├── test_pytest_output_parser.py
│   └── test_report_utils.py
├── .env                                # Local config (NEVER COMMIT)
├── .env.example                        # Template for .env
├── .streamlit/
│   └── config.toml                     # Streamlit theme config
├── fix.sh                              # Runs ruff + mypy
├── launch_dev.sh                       # Start UI + mock server (dev only)
├── launch_ui.sh                        # Start UI only
├── main.py                             # PROTECTED — CLI entry point
├── pytest.ini                          # Pytest configuration
├── pyproject.toml                      # Project deps (managed by uv)
├── streamlit_app.py                    # Streamlit UI (primary working file)
├── uv.lock                             # Dependency lock file
├── BACKLOG.md                          # Feature backlog
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
- `load_dotenv()` is called at startup so `OLLAMA_TIMEOUT` is applied
- Text area (Paste story tab) is live — no intermediate confirm button
- URL is auto-normalised: `www.foo.com` becomes `https://www.foo.com` before scraping
- Scraper result shown in sidebar: success with element count, or warning with error snippet
- Generated code + Coverage tabs persist after any button click (rendered from `session_state`)
- Three download buttons always visible: `local.md`, `jira.md`, `standalone.html`
- ⚠️ **BREAK-2:** Run results panel is blank due to session state wipe — see Known Broken Items

### `src/page_context_scraper.py` — How It Works
- Runs Playwright in a **subprocess** (bypasses Streamlit's Windows ProactorEventLoop issue)
- Returns `tuple[PageContext | None, str | None]` — always unpack as `ctx, err = scrape_page_context(url)`
- Failure is non-fatal — generation continues without page context if scraper fails
- `PageContext.to_prompt_block()` formats elements as plain text for LLM prompt injection

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

**Recovery strategy:** When Cline corrupts a file, rebuild from the last known-good output and re-apply changes cleanly. Do not attempt further incremental edits on a corrupted file.

---

## Common Issues & Solutions

### LLM Timeout / Empty Response
**Symptoms:** "LLM returned empty response", debug expander shows empty raw response  
**Cause:** `OLLAMA_TIMEOUT` too low (default 60s), or `.env` not loaded  
**Solution:** Set `OLLAMA_TIMEOUT=300` in `.env`; confirm `load_dotenv()` is called before `LLMClient` initialises

### Generated Tests Fail With Wrong Locators
**Symptoms:** `AssertionError: Locator expected to be visible`, invented element names like `username_input`  
**Cause:** Page scraper failed silently because URL was missing `https://`  
**Solution:** Ensure Base URL starts with `https://` — the app now auto-adds it. Check sidebar for scraper warning.

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

| Model | Size | Use |
|-------|------|-----|
| `qwen3.5:35b` | 23 GB | Best quality output, ~2 min response |
| `qwen2.5-coder:1.5b-base` | 986 MB | Fast testing, ~6 sec, simpler output |

---

## Implementation Roadmap

### Completed

| Phase | Status |
|-------|--------|
| Phase 0: Setup & Cleanup | Done |
| Phase UI: Streamlit Interface | Done |
| AI-001: Page Context Scraper | Done |
| AI-008: Run Results Parser | ⚠️ Partial — test file exists, impl missing (BREAK-1) |
| R-001 to R-006: Feature Recovery | Done (2026-03-13) |

### R-001 to R-006 Detail

| ID | Feature |
|----|---------|
| R-001 | Ollama model selector in sidebar |
| R-002 | Pipeline log |
| R-003 | `normalise_code_newlines()` on generated code |
| R-004 | Page context scraping wired into generation flow |
| R-005 | Three report download buttons |
| R-006 | Rename test file UI |

### Immediate Fixes Required

| ID | Fix | Effort |
|----|-----|--------|
| BREAK-1 | Add `src/pytest_output_parser.py` | ~30 min |
| BREAK-2 | Delete 2-line session state wipe in `display_run_button()` | 2 min |

### Backlog (Next — after breaks fixed)

| ID | Feature |
|----|---------|
| AI-002 | User story parser (`src/user_story_parser.py`) — TDD with fixtures |
| AI-003 | Update `.env.example` with `OLLAMA_TIMEOUT=300` |
| AI-004 | Phase C UI gaps (env dropdown, re-run failed, screenshot viewer) |
| AI-005 | Extract coverage helpers to `src/coverage_utils.py` |
| AI-006 | Create `tests/fixtures/user_stories/` with 10-15 format examples |
| AI-007 | Remove `_generate_test_content()` from CLI orchestrator |

---

## Appendix — `src/pytest_output_parser.py` (canonical source)

If the file is missing, create it with this exact content:

```python
"""
pytest_output_parser.py — Parse raw pytest stdout into structured data.

Converts verbose pytest -v output into typed RunResult / TestResult objects
that the Streamlit UI can render as a readable results table.

No Streamlit imports — fully unit testable in isolation.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


_PASSED_RE = re.compile(r"(\S+\.py)::(\S+)\s+PASSED")
_FAILED_RE = re.compile(r"(\S+\.py)::(\S+)\s+FAILED")
_DURATION_RE = re.compile(
    r"(\d+) passed(?:,\s*(\d+) failed)? in ([\d.]+)s"
)
_ERROR_RE = re.compile(r"FAILED \S+::(\S+) - (.+)")


@dataclass
class TestResult:
    name: str
    status: str          # "passed" | "failed" | "error"
    duration: float      # seconds; 0.0 when not available
    error_message: str
    file_path: str


@dataclass
class RunResult:
    results: list[TestResult] = field(default_factory=list)
    total: int = 0
    passed: int = 0
    failed: int = 0
    errors: int = 0
    duration: float = 0.0
    raw_output: str = ""


def parse_pytest_output(raw: str) -> RunResult:
    run = RunResult(raw_output=raw)
    results_by_name: dict[str, TestResult] = {}

    for line in raw.splitlines():
        passed_match = _PASSED_RE.search(line)
        if passed_match:
            file_path, name = passed_match.group(1), passed_match.group(2)
            results_by_name[name] = TestResult(
                name=name, status="passed", duration=0.0,
                error_message="", file_path=file_path,
            )
            continue

        failed_match = _FAILED_RE.search(line)
        if failed_match:
            file_path, name = failed_match.group(1), failed_match.group(2)
            results_by_name[name] = TestResult(
                name=name, status="failed", duration=0.0,
                error_message="", file_path=file_path,
            )
            continue

        error_match = _ERROR_RE.search(line)
        if error_match:
            name, message = error_match.group(1), error_match.group(2)
            if name in results_by_name:
                results_by_name[name].error_message = message
            continue

        duration_match = _DURATION_RE.search(line)
        if duration_match:
            run.passed = int(duration_match.group(1))
            run.failed = int(duration_match.group(2) or 0)
            run.duration = float(duration_match.group(3))

    run.results = list(results_by_name.values())
    run.total = len(run.results)

    if run.passed + run.failed == 0 and run.total > 0:
        run.passed = sum(1 for r in run.results if r.status == "passed")
        run.failed = sum(1 for r in run.results if r.status == "failed")

    return run
```

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
- **2026-03-16:** Session 9 — BREAK-1/BREAK-2 identified: `src/pytest_output_parser.py` missing (CI blocker), session state wipe bug located in `display_run_button()`

---

*Last Updated: 2026-03-16*
*Project Status: CI broken — BREAK-1 and BREAK-2 must be fixed before any backlog work*
*Current Phase: Fix CI, then backlog AI-002 through AI-007*
