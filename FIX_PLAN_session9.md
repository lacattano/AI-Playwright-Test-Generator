# FIX PLAN — Session 9 (2026-03-16)
## Restore CI + Test Generator

**Time estimate:** ~45 minutes  
**Scope:** Two isolated fixes, no feature work, no refactoring

---

## Context

The last commit (Session 8, 2026-03-13) closed R-001 through R-006 but left two
live breakages that block everything else:

| ID | Severity | Description |
|----|----------|-------------|
| BREAK-1 | 🔴 CI Blocker | `src/pytest_output_parser.py` was never committed — all tests fail with ImportError |
| BREAK-2 | 🟡 UX Bug | Run results wiped immediately in `display_run_button()` — results panel always blank |

---

## Step 1 — Confirm the failure (2 min)

```bash
cd AI-Playwright-Test-Generator
source .venv/Scripts/activate
pytest tests/ -v
```

Expected output (before fix):
```
ERROR tests/test_pytest_output_parser.py - ModuleNotFoundError: No module named 'src.pytest_output_parser'
```

---

## Step 2 — Fix BREAK-1: add the missing file (5 min)

Copy `src/pytest_output_parser.py` from the appendix of `PROJECT_KNOWLEDGE.md`
into the repo at `src/pytest_output_parser.py`.

The file content is also attached to this session as a file output.

Verify it imports cleanly:
```bash
python -c "from src.pytest_output_parser import parse_pytest_output, RunResult, TestResult; print('OK')"
```

---

## Step 3 — Run tests to confirm BREAK-1 resolved (5 min)

```bash
pytest tests/ -v
```

Expected: All tests in `tests/test_pytest_output_parser.py` now run and pass.
Any remaining failures are pre-existing (check `ISSUES_FOUND_AND_FIXES.md`).

---

## Step 4 — Fix BREAK-2: session state wipe (5 min)

Open `streamlit_app.py` and find the function `display_run_button()`.

Search for these two lines (around line 591-594 per the spec):
```python
st.session_state.last_run_success = None
st.session_state.last_run_output = ""
```

**Delete both lines.** Do not change anything else in that function.

The block should end up looking like:
```python
st.session_state.last_run_success = success
st.session_state.last_run_output = output
# (nothing else — no reset lines)
```

---

## Step 5 — Full quality check (5 min)

```bash
bash fix.sh          # ruff + mypy
pytest tests/ -v     # all unit tests
```

Both must pass clean before committing.

---

## Step 6 — Smoke test the UI (10 min)

```bash
bash launch_ui.sh
```

Verify:
1. App loads without error
2. Generate a test with a user story
3. Click "Run Now" — confirm results appear and persist when clicking download buttons
4. Download all three report formats (`local.md`, `jira.md`, `standalone.html`)

---

## Step 7 — Commit (3 min)

```bash
git add -A
git diff --staged --stat
git commit -m "fix: add missing pytest_output_parser module and fix run results session state wipe"
git push
```

Wait for GitHub Actions to complete. Both jobs (lint + test) should now be green.

---

## What NOT to do in this session

- Do not start any backlog items (AI-002 through AI-007)
- Do not refactor `streamlit_app.py` beyond the two-line delete
- Do not rename any files
- Do not modify protected files (`src/llm_client.py`, `src/test_generator.py`, `main.py`)

---

## After this fix — what's next

Once CI is green, the project is demo-ready again. Recommended next backlog items:

1. **AI-003** — Update `.env.example` with `OLLAMA_TIMEOUT=300` (2-minute change, high impact for new users)
2. **AI-002** — `src/user_story_parser.py` with proper TDD and fixtures (the largest remaining structural improvement)
3. **AI-005** — Extract coverage helpers to `src/coverage_utils.py` (unblocks proper unit test coverage of that logic)
