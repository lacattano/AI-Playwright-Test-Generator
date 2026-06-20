# Road to Production — Priorised Implementation Plan

**Created:** 2026-06-03  
**Status:** In Progress  
**Supersedes:** Informal order plan (outdated as of 2026-05)  
**Purpose:** Multi-session roadmap with implementation-relevant details for each item. Use checkboxes to track progress across sessions.

---

## Legend

| Marker | Meaning |
|--------|---------|
| `[ ]` | Not started |
| `[~]` | In progress |
| `[x]` | Complete |
| `[S]` | Shipped (pre-existing) |
| `[R]` | Removed (no longer needed) |

---

## Revised Priority Order

Three items from the original plan are already shipped or fixed:
- **AI-027 Session 4** — Shipped 2026-05-22 (journey selector propagation)
- **AI-023 Locator Repair** — Shipped 2026-05-23 (all 4 sessions)
- **B-013 Journey stops short** — Fixed by AI-027 Session 4

The revised order collapses from 12 items to **10 outstanding items** across 4 tiers.

---

## Tier 1 — Bug Fixes (do these first)

### 1. B-014 — ASSERT Tokens Resolving to Wrong Elements

**Priority:** High  
**Status:** `[x]` Shipped 2026-06-04  
**Impact:** False green — test passes when it should fail. Demo blocker.  
**Backlog ref:** `## 🔴 Open Bugs` → B-014

**Problem:** ASSERT placeholders for "confirmation message" resolve to elements like `.cart_quantity_delete` (delete button) instead of the actual confirmation popup. The resolver matches on shared attributes (e.g., `data-product-id`) rather than assertion intent.

**Solution implemented:**
- `_assert_action_penalty()` in `src/placeholder_scorers.py` — penalises interactive elements (buttons, submit, links with action hrefs) when action is ASSERT with message-like descriptions. Button role: -15, submit role: -15, action link: -10.
- `_assert_message_bonus()` in `src/placeholder_scorers.py` — rewards display/alert/dialog roles for assertions. Dialog role: +15, alert role: +15, aria alertdialog: +12, confirmation text match: +10, aria_label confirmation: +8.
- `_is_message_like_assertion()` — detects message-like assertions using keywords: confirmation, success, popup, notification, alert.
- `SuccessAssertStrategy` in `src/intent_matcher.py` — requires BOTH success AND message keywords to avoid over-claiming generic "confirmation message" assertions.
- 42 unit tests in `tests/test_b014_assert_resolution.py`

**Spec:** `docs/specs/FEATURE_SPEC_B014_assert_resolution.md`

**Verification:** 1043 tests pass, ruff clean, mypy clean

**Estimated sessions:** 1 design + 1-2 implementation  
**Actual sessions:** 1 (completed 2026-06-04)

---

### 2. B-015 — Journey Scraper Picks Wrong Element

**Priority:** Medium  
**Status:** `[x]` Shipped 2026-06-04  
**Impact:** Wrong element selection during journey discovery on single-page apps  
**Backlog ref:** `## 🔴 Open Bugs` → B-015

**Problem:** On single-page apps, the scraper sees all elements across pages. The resolver picks the first match by score, which may be from a different logical page section.

**Solution implemented:**
- Refactored `_discover_selector()` in `src/journey_scraper.py` to use `PlaceholderScorer.compute_element_score()` — the same unified scoring engine as PlaceholderOrchestrator
- Eliminated custom Stage 1 substring match that returned first element whose text appeared in description regardless of semantic fit
- Stage 2 LLM fallback via `self._resolver.rank_candidates()` retained for edge cases
- No new modules needed — leverages existing battle-tested scoring (role bonuses, text overlap, visibility penalties, semantic similarity)

**Spec:** `docs/specs/FEATURE_SPEC_B015_journey_element_selection.md`

**Verification:** ruff clean, mypy clean, 60 journey_scraper tests pass, 1015 total tests pass

**Estimated sessions:** 1  
**Actual sessions:** 1 (completed 2026-06-04)

---

## Tier 2 — Feature Completion

### 3. AI-010 — Page Object Model Generation Toggle

**Priority:** Medium  
**Status:** `[x]` All Phases Complete — 2026-06-10  
**Impact:** Portfolio differentiator + Engineering Manager persona  
**Backlog ref:** `### AI-010 — Page Object Model Generation Mode`  
**Spec:** `docs/specs/FEATURE_SPEC_AI010_pom_toggle.md` (design session 2026-06-04)

**What's done:**
- [x] Phase 1: Evidence-Aware PageObjectBuilder — `use_evidence_tracker` mode in `src/page_object_builder.py`
- [x] Phase 2: POM Mode in PlaceholderOrchestrator — `pom_mode` flag, POM artifact building, URL mapping, method calls (15 tests)
- [x] Phase 3: Pipeline Configuration — `pom_mode` wired through `orchestrator.py`, `pipeline_models.py`, `pipeline_writer.py` (11 tests)
- [x] Phase 4: UI Toggle — Streamlit sidebar toggle + CLI menu toggle (wired through `ui_pipeline.py`, `ui_renderers.py`, `cli/session.py`, `cli/pipeline_runner.py`, `cli/main.py`)
- [x] Phase 5: Export Stripping — `_strip_evidence_from_pom()` in `src/code_postprocessor.py` (18 tests)
- [x] Full test suite: 1125 passed, 1 skipped, zero regressions

**Estimated sessions:** 2 (2 used)

---

### 4. AI-011 — Run History Chart

**Priority:** Medium  
**Status:** `[x]` Complete — 2026-06-12  
**Impact:** Feeds coverage heatmap (AI-022) story — sprint-over-sprint trends  
**Backlog ref:** `### AI-011 — Test Run History Chart`  
**Spec:** `docs/specs/FEATURE_SPEC_AI011_run_history_chart.md`

**What's done:**
- [x] `src/run_history_chart.py` — Plotly stacked bar chart with pass-rate line overlay (10 tests)
- [x] `src/run_history_cli.py` — ASCII table renderer for CLI (19 tests)
- [x] `src/ui_renderers.py` — Run History tab in EvidenceViewer with scope selector, flaky tests, comparison
- [x] CLI integration verified — `render_run_history_summary()` in `cli/run_results_display.py`
- [x] Export service verified — `run_results/` included in exported packages
- [x] 29 new tests, 1166 total pass, zero regressions

**Estimated sessions:** 1  
**Actual sessions:** 2

---

### 5. AI-026 — CLI Persist and Reload (Finish Step 7)

**Priority:** Medium  
**Status:** `[x]` Step 7 Verified Complete — 2026-06-11  
**Impact:** Completes CLI as standalone tool for power users / CI/CD  
**Spec:** `docs/specs/FEATURE_SPEC_AI026_persist_generated_tests.md`

**What's done:**
- [x] `src/run_result_persistence.py` — full persistence layer
- [x] `persist_run_result()`, `load_run_result()`, `list_run_results()`
- [x] `load_all_run_results()`, `compute_run_history()`, `get_flaky_tests()`
- [x] CLI menu items for reload/rerun
- [x] Step 7: Backwards Compatibility — `find_existing_packages()`, `_reconstruct_manifest()`, `load_package_manifest(reconstruct=True)` in `src/pipeline_artifact_manager.py`
- [x] `scrape_manifest.json` includes all required metadata fields (generated_at, base_url, test_file_path, coverage_summary_path, run_command, pages_scraped, page_requirements, journeys, page_objects, records)
- [x] Old package formats (pre-persistence) load gracefully via `_reconstruct_manifest()` with 22 unit tests

**Verification:** ruff clean, mypy clean, 1137 tests pass, 1 skipped

**Estimated sessions:** 0-1  
**Actual sessions:** 0.25 (verification only)

---

## Tier 3 — Infrastructure

### 6. AI-012 — SQLite Persistence Layer

**Priority:** Medium  
**Status:** `[x]` verified complete — 2026-06-16  
**Impact:** Replaces JSON file persistence with queryable SQLite DB. Foundation for Phase 5 Eval Harness.  
**Backlog ref:** `### AI-012 — SQLite Persistence`  
**Spec:** `docs/specs/FEATURE_SPEC_sqlite_persistence.md`

**What it does:**
- Replaces `evidence/run_results/*.json` with single `evidence/runs.sqlite`
- SQL-based flaky test detection (replaces in-memory loops)
- ACID-compliant atomic writes
- Ad-hoc query interface for Run History Chart (AI-011)
- **Graph compilation:** CSV-to-SQLite pipeline for `project_sanitizer.py` (nodes.csv/links.csv → SQLite graph store with recursive CTE support)

**Dependencies:** AI-026 (shipped), AI-011 (shipped) — prerequisites met.

**Why before Phase 5:** The Eval Harness needs a queryable history store for baseline comparisons. SQLite provides this without adding external dependencies (stdlib only).

**Estimated sessions:** 2

---

### 7. Phase 5 — Automated Evaluation Harness

**Priority:** High (for ML Engineering portfolio)  
**Status:** `[ ]` Not started  
**Impact:** Regression protection for prompt/model/resolver changes + quantitative baseline for dual-tier comparison

**Problem:** With 800+ tests and complex resolver logic, prompt changes or model swaps can silently degrade output quality. No quantitative quality gate exists.

**Implementation notes:**
- [ ] Define frozen dataset: 10-15 user stories covering saucedemo + automationexercise
- [ ] Expand dataset: include multi-page mock documents (PDFs, HTML docs) for RAG-ready evaluation
- [ ] Record baselines: expected placeholder resolutions, test pass rates
- [ ] Build harness script: `scripts/eval/eval_harness.py`
- [ ] Metrics to track:
  - Placeholder resolution accuracy (% correct matches)
  - Generated test pass rate (% tests passing on first run)
  - False positive rate (% tests passing with wrong assertions)
  - Skeleton generation completeness (% criteria with placeholders)
- [ ] **Dual-Tier Awareness:** Harness must support Free vs Paid tier configurations
  - Free tier: single-model, sequential pipeline (current architecture)
  - Paid tier: multi-agent, LangGraph state machine (Phase 1 architecture)
  - Compare: Monolithic vs Multi-Agent quality metrics side-by-side
- [ ] Run as quality gate before commits affecting pipeline
- [ ] Add to CI as optional job (gate, not break)

**Estimated sessions:** 2-3

---

### 8. Phase 4 — Docker Improvements

**Priority:** Medium  
**Status:** `[~]` Basic exists, needs polish  
**Impact:** "docker compose up" first impression + enterprise GTM  
**Files:** `Dockerfile`, `docker-compose.yml`

**Current state:**
- Basic single-stage Dockerfile using `python:3.13-slim`
- Uses `pip install` (not `uv`)
- No multi-stage build
- `docker-compose.yml` exists but may need service definitions

**Improvements needed:**
- [ ] Multi-stage build: builder stage for deps, runtime stage for app
- [ ] Use `uv` instead of `pip` for faster, lockfile-based installs
- [ ] Use Playwright's official image as runtime base (`mcr.microsoft.com/playwright/python`)
- [ ] Add `uv.lock` copy + `uv sync --frozen` for reproducible builds
- [ ] Ensure `docker-compose.yml` includes Ollama/LM Studio service
- [ ] Test `docker compose up` produces working app

**Estimated sessions:** 1

---

## Tier 4 — ML Engineering Roadmap

### 8. Phase 2 — Full Self-Healing Reflection Loops

**Priority:** Medium (portfolio)  
**Status:** `[ ]` Foundation exists (AI-023 shipped)  
**Impact:** "Self-healing AI automation" marketing message

**Foundation already built:**
- AI-023 (locator repair loop) — shipped
- `src/failure_classifier.py` — classifies failure types
- `src/locator_repair.py` — applies locator patches
- Three-pass resolver with fallback chain

**What's needed:**
- [ ] Full iterative loop: run → parse stderr → route to reviewer agent → fix → re-run
- [ ] Max iterations ceiling (configurable, default 3)
- [ ] Reviewer agent that classifies fixable vs. unfixable failures
- [ ] Integration with `src/pytest_output_parser.py`
- [ ] Write spec: `docs/specs/FEATURE_SPEC_phase2_self_healing.md`

**Estimated sessions:** 2-3

---

### 9. Phase 3 — Enterprise RAG

**Priority:** Medium (portfolio)  
**Status:** `[ ]` Not started  
**Impact:** Token cost reduction + ML Engineering portfolio piece

**Current state:** Resolver uses rule-based scoring + LLM disambiguation only.

**Research verified (2026-06-14):**
- Milvus/Weaviate confirmed as viable vector DB options for local deployment
- RAG pattern: Ingestion Agent parses PDFs, Word docs, Confluence pages → vector store → retrieval at resolution time
- Requires Phase 5 eval harness first (to measure improvement vs. current baseline)

**What's needed:**
- [ ] Vector DB (Milvus or Weaviate locally) for storing golden locator patterns
- [ ] Store Playwright documentation chunks for retrieval at resolution time
- [ ] Hook into Ingestion Agent (Phase 1) for document parsing
- [ ] Upgrade resolver to retrieve relevant patterns before scoring
- [ ] Measure: does RAG improve resolution accuracy vs. current baseline?
- [ ] Requires Phase 5 eval harness first (to measure improvement)
- [ ] Write spec: `docs/specs/FEATURE_SPEC_phase3_rag.md`

**Estimated sessions:** 3-4

---

### 10. Phase 1 — Multi-Agent Architecture (LangGraph) with Model-Agnostic Providers

**Priority:** High (promoted from Low)  
**Status:** `[ ]` Not started  
**Impact:** Formal multi-agent pattern for portfolio + enables Phase 3 RAG + complete model flexibility

**Research verified (2026-06-14):**
- LangGraph confirmed as mature framework for multi-agent orchestration (state machines, human-in-the-loop)
- Gemma 4 models verified (released April 2026 by Google, Apache 2.0 licensed)
- **IMPORTANT:** Do NOT use DiffusionGemma — it's weaker on reasoning benchmarks (MMLU Pro: 77.6% vs 82.6%, AIME: 69.1% vs 88.3%)
- Use standard Gemma 4 26B-A4B MoE for all agents

**Proposed agent roles with verified models:**
- [ ] **Ingestion Agent:** Gemma 4 26B-A4B MoE (3.8B active params, ~14.4GB at 4-bit) — parses PDFs, Word docs, Confluence pages
- [ ] **QA Director:** Gemma 4 31B Dense (~17.5GB at 4-bit) — routes test criteria to correct agent
- [ ] **Script Synthesizer:** Gemma 4 26B-A4B MoE (~14.4GB at 4-bit) — generates Playwright test code

**Hardware requirements:** ~32GB RAM minimum for dual-model deployment at 4-bit quantization

#### Model-Agnostic Architecture

**Core Principle:** The pipeline is a **model orchestration layer**, not a model lock-in. Users have complete freedom to:
- Choose any provider (local or cloud)
- Choose any model per agent
- Mix and match providers across agents
- Swap models without code changes
- Use their own fine-tuned models

**Existing Foundation:** `src/llm_providers/__init__.py` already implements:
- `LLMProvider` ABC with `complete()`, `list_models()`, `provider_name` interface
- `OllamaProvider`, `LMStudioProvider`, `OpenAIProvider` (cloud + local modes)
- `get_provider()` factory function
- `create_provider_from_env()` from environment variables
- `auto_detect_provider()` probing local ports

**Phase 1 Extends This To:**

1. **Per-Agent Model Selection** — Each agent configures its own provider + model
   ```bash
   # Example: Mixed local + cloud configuration
   AGENT_INGESTION_PROVIDER=ollama
   AGENT_INGESTION_MODEL=my-finetuned-ingestion-model

   AGENT_QA_DIRECTOR_PROVIDER=anthropic
   AGENT_QA_DIRECTOR_MODEL=claude-sonnet-4-20250514

   AGENT_SCRIPT_SYNTHESIZER_PROVIDER=lm-studio
   AGENT_SCRIPT_SYNTHESIZER_MODEL=my-custom-test-generator
   ```

2. **Cloud Provider Support** — Add providers for cloud LLMs
   - [ ] `AnthropicProvider` — for Claude models (Claude Sonnet 4, Opus 4)
   - [ ] `GoogleProvider` — for Gemini models (Gemini 2.5 Pro)
   - [ ] Extend `get_provider()` factory to support all cloud providers
   - [ ] Support API key management per provider

3. **Configuration System** — `model_config.json` or env var pattern
   ```json
   {
     "agents": {
       "ingestion": {
         "provider": "ollama",
         "model": "my-ingestion-model",
         "timeout": 60
       },
       "qa_director": {
         "provider": "anthropic",
         "model": "claude-sonnet-4-20250514",
         "api_key_env": "ANTHROPIC_API_KEY",
         "timeout": 120
       },
       "script_synthesizer": {
         "provider": "lm-studio",
         "model": "my-custom-test-generator",
         "timeout": 300
       }
     },
     "pipeline": {
       "agents": ["ingestion", "qa_director", "script_synthesizer"],
       "fallback_providers": ["ollama", "openai-local"]
     }
   }
   ```

4. **Fallback Mechanism** — If one model fails, try the next in chain
   - Configurable fallback chain per agent
   - Graceful degradation (log warning, continue with fallback)
   - No hard failure on model unavailability

5. **UI/CLI Integration** — Model selection interface
   - [ ] Streamlit: Per-agent model selector in sidebar
   - [ ] CLI: Menu option to configure models per agent
   - [ ] Save/load configurations as named profiles

6. **Default Model Recommendations** — Documented but overridable
   - Gemma 4 26B-A4B for Ingestion (fast, efficient)
   - Gemma 4 31B Dense for QA Director (strong reasoning)
   - Gemma 4 26B-A4B for Script Synthesizer (balanced)
   - Users can override any agent with their preferred model/provider

**What's needed:**
- [ ] Formal LangGraph state management
- [ ] Define agent roles: Ingestion, QA Director, Script Synthesizer
- [ ] Refactor orchestrator to use agent framework
- [ ] Implement per-agent model configuration
- [ ] Add cloud providers (Anthropic, Google)
- [ ] Configuration UI for model selection
- [ ] Fallback mechanism implementation
- [ ] Requires Phase 5 eval harness to verify no regression
- [ ] Write spec: `docs/specs/FEATURE_SPEC_phase1_multi_agent.md`

**Estimated sessions:** 4-5 (increased from 3-4 due to cloud provider integration)

---

## Summary Checklist

| # | Item | Tier | Status | Est. Sessions |
|---|------|------|--------|---------------|
| 1 | B-014 ASSERT resolution | Bug | `[x]` Shipped | 1 |
| 2 | B-015 Journey element | Bug | `[x]` Shipped | 1 |
| 3 | AI-010 POM Toggle | Feature | `[x]` All phases complete | 2 |
| 4 | AI-011 Run History | Feature | `[x]` Complete | 2 |
| 5 | AI-026 CLI Persist finish | Feature | `[x]` Step 7 verified | 0-1 |
| 6 | AI-012 SQLite Persistence | Infra | `[ ]` Draft spec | 2 |
| 7 | Phase 5 Eval Harness | Infra | `[ ]` Open (depends on AI-012) | 2-3 |
| 8 | Phase 4 Docker polish | Infra | `[~]` Basic exists | 1 |
| 9 | Phase 2 Self-Healing | ML | `[ ]` Foundation built | 2-3 |
| 10 | Phase 3 RAG | ML | `[ ]` Not started (depends on AI-012) | 3-4 |
| 11 | Phase 1 Multi-Agent | ML | `[ ]` High (promoted) | 3-4 |

**Total estimated sessions:** 18-27 (+2 for AI-012)

---

## Session Tracking

Update this section after each session:

| Date | Item Completed | Notes |
|------|---------------|-------|
| 2026-06-03 | Plan created | Cross-referenced against actual project state |
| 2026-06-04 | B-014 ASSERT resolution | Shipped intent-aware scoring: _assert_action_penalty, _assert_message_bonus, _is_message_like_assertion. SuccessAssertStrategy requires BOTH success+message keywords. 42 tests, 1043 pass. |
| 2026-06-04 | B-015 Journey element selection | Shipped unified scoring: _discover_selector() delegates to PlaceholderScorer.compute_element_score(). Eliminated dual-ranking pipeline. 60 journey tests, 1015 total pass. |
| 2026-06-04 | AI-010 POM Toggle (design) | Design session complete. Spec: FEATURE_SPEC_AI010_pom_toggle.md. Two modes (Simple/POM) via GenerationMode enum. Phase 1: Simple-to-POM conversion + POMWriter. Phase 2: UI/CLI toggle + pipeline wiring. Phase 3: Evidence tracker integration. 17 tests planned. Zero protected file changes. |
| 2026-06-09 | AI-010 Phases 1-3 | Shipped evidence-aware POM builder (Phase 1), POM mode in PlaceholderOrchestrator (Phase 2), pipeline configuration wiring (Phase 3). 26 unit tests. `pom_mode` flows: TestOrchestrator → PlaceholderOrchestrator → PageObjectBuilder → PipelineArtifactSet → package_manifest.json. 1107 tests pass. |
| 2026-06-09 | AI-010 Phase 4 (UI Toggle) | Shipped Streamlit sidebar toggle (`ui_renderers.py`), `pom_mode` in `st.session_state` → `streamlit_app.py` → `ui_pipeline.run_pipeline()`. CLI: `pom_mode` in `Session` dataclass, "POM Mode" menu item in `cli/main.py` with colored feedback, forwarded via `cli/pipeline_runner.py`. ruff clean, mypy clean, 1107 tests pass. Phase 5 (export stripping) remains. |
| 2026-06-10 | AI-010 Phase 5 (Export Stripping) | Shipped `_strip_evidence_from_pom()` in `src/code_postprocessor.py`. Converts evidence-aware POM to clean POM: strips EvidenceTracker import, replaces tracker.click/fill/navigate/assert_visible/get_text/select with page.locator equivalents, adds expect() imports for assertions. 18 unit tests in `tests/test_code_postprocessor_pom_export.py`. ruff clean, mypy clean, 1125 passed, 1 skipped. AI-010 feature complete. |
| 2026-06-08 | Phase 4 Export (core) | Shipped `ExportMode` enum, `ExportService.export()`, `strip_evidence_from_test_code()`, `strip_evidence_from_pom()`. 28 unit tests in `tests/test_phase4_export.py`. 1068 tests pass. **TODO:** Streamlit export panel + CLI export menu option. |
| 2026-06-11 | AI-026 Step 7 (Backwards Compatibility) | Verified Step 7 complete: `find_existing_packages()`, `_reconstruct_manifest()`, `load_package_manifest(reconstruct=True)` all implemented in `src/pipeline_artifact_manager.py`. 22 unit tests cover legacy package loading. `scrape_manifest.json` includes all required metadata fields. Old package formats load gracefully. 1137 tests pass. |
| 2026-06-12 | AI-011 Run History Chart | Shipped complete feature: `src/run_history_chart.py` (10 tests, Plotly stacked bar + pass-rate line), `src/run_history_cli.py` (19 tests, ASCII tables), Streamlit Run History tab in EvidenceViewer with scope selector + flaky test panel + run comparison, CLI `render_run_history_summary()` wired into `cli/pipeline_runner.py` (2 call sites), `run_results/` copy added to `src/export_service.py` exports. 29 new tests, 1166 total pass, zero regressions. |
| 2026-06-14 | Research Session | Verified Gemma 4 models (released April 2026, Apache 2.0). Confirmed LangGraph for multi-agent orchestration. Researched RAG patterns (Milvus/Weaviate). Updated ROADMAP with dual-tier eval harness metrics, verified model specs for Phase 1 agents, promoted Phase 1 to High priority. Key finding: DiffusionGemma weaker on reasoning (MMLU Pro 77.6% vs 82.6%) — use standard Gemma 4 26B-A4B MoE. |
| 2026-06-14 | AI-012 SQLite Persistence (design) | Draft spec complete: FEATURE_SPEC_sqlite_persistence.md. 4 phases (core module, API compat, export integration, query interface). 28 tests planned. Zero new deps (sqlite3 stdlib). Graph compilation for project_sanitizer.py (CSV→SQLite with recursive CTEs). Added to Tier 3 Infra before Phase 5 Eval Harness. Neo4j research: GPL v3 copyleft risk — recommended Apache AGE for dev-time graph tooling instead. |

---

## Rules for Implementation

1. **One item per session** — per AGENTS.md §10
2. **Design session first** for B-014 and any item marked "Needs design session"
3. **ruff → mypy → pytest → commit** before marking any item complete
4. **Update this doc** at end of each session with completion status
5. **Update memory bank** with new decisions/patterns discovered
6. **Do not skip the eval harness** (Phase 5) — build it before Phase 2/3/4 so regressions are caught

---

*Last updated: 2026-06-14*
