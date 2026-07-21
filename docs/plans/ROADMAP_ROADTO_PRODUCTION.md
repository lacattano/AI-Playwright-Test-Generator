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

The revised order collapses from 12 items to **11 outstanding items** across 4 tiers.

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

### 3. B-022 — State-Dependent Page Scraping

**Priority:** High  
**Status:** `[x]` Shipped 2026-07-20 — cart-seeding upgrade fix + dynamic element discovery  
**Impact:** Cart/checkout/order assertions silently corrupt — tests either skip or resolve to empty-state selectors  
**Backlog ref:** `## ✅ Closed Bugs` → B-022

**Problem:** `PageScraper` opens a fresh browser context per URL. Pages like `/view_cart` show
different DOM depending on session state. Elements that only appear with items in cart
("Proceed to checkout", cart table rows, quantity columns) are absent from scraped data.
Tests navigating directly to `/view_cart` either skip or resolve assertions to `#empty_cart`.

**What was done:**
- [x] `_upgrade_stateful_pages()` now always prefers cart-seeded data over static scrapes for `/view_cart` and `/checkout` pages (was: only replaced if more elements, but empty cart pages often have more promotional elements)
- [x] `CartSeedingScraper` uses dynamic element discovery via `_discover_selector()` instead of hardcoded selectors that don't match all sites
- [x] Product URL detection: scrapes category/product URLs from existing data instead of always using `/products`
- [x] UAT verified: 13/13 tests pass (was: 1 fail + 3 skips)

**Verification:** 13 passed, 0 failed on automationexercise.com UAT

**Estimated sessions:** 1-2  
**Actual sessions:** 1

---

### 4. B-023 — Cart Modal Intercepts Clicks During Journey Discovery

**Priority:** Low  
**Status:** `[x]` Shipped 2026-07-20 — `_dismiss_modals()` added to JourneyScraper  
**Impact:** Journey scraper retry noise adds ~20s to UAT runtime. Tests still pass.  
**Backlog ref:** `## 🔴 Open Bugs` → B-023

**Problem:** After adding a product to cart, the "Added to cart" confirmation modal (`#cartModal`)
blocks pointer events on the "Cart" header link during journey discovery. The scraper retries
until timeout (~10s) then navigates directly.

**Fix:** Dismiss confirmation modals before clicking navigation links in journey discovery,
similar to how `CartSeedingScraper` already handles the "Continue Shopping" dismiss.

**Estimated sessions:** 0.5

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

### 6. AI-028 — Evidence Search, Filter & Export

**Priority:** Medium  
**Status:** `[x]` Shipped 2026-07-20  
**Impact:** Export-first approach — users can take their evidence data anywhere (CSV for Excel/Tableau, NDJSON for Splunk/jq, JUnit XML for CI/CD). Search and filter are convenience layers on top of the same index.  
**Spec:** `docs/specs/FEATURE_SPEC_AI028_evidence_search.md`

**Problem:** Evidence data is locked inside the tool (`.evidence.json` sidecars + `run_results.sqlite`). Users can't open results in their own tools, and even within the tool, finding specific tests requires scrolling a flat dropdown of 100+ items.

**What's needed:**
- [ ] `src/evidence_index.py` — `EvidenceIndex` class that indexes sidecar metadata into SQLite (`evidence_index` table)
- [ ] `src/evidence_export.py` — CSV, NDJSON, and JUnit XML exporters, all respecting the same filter parameters
- [ ] Streamlit download buttons for all three export formats (full dataset or filtered subset)
- [ ] Full-text search via SQL `LIKE` across test name, condition ref, story ref, URL, and step labels
- [ ] Faceted filters: status (passed/failed), URL domain, condition ref prefix
- [ ] Replace flat `st.selectbox` in `EvidenceViewer._render_debug_export()` with search bar + filter row + results list
- [ ] CLI: `python -m cli.evidence_cli search --query "dress"` and `export --format csv --output evidence.csv`
- [ ] 30+ unit tests (`test_evidence_index.py` + `test_evidence_export.py`)

**Phases:**
1. Evidence index module + SQLite schema (no UI)
2. Export formats — CSV, NDJSON, JUnit XML (no UI)
3. Search UI + export download buttons + results list
4. CLI integration (search + export subcommands)

**Dependencies:** AI-012 (SQLite Persistence, shipped) — uses existing `evidence/run_results.sqlite`

**Estimated sessions:** 1-2

---

### 7. URL-Based Assertions for Page-State Verification

**Priority:** Medium
**Status:** `[ ]` Not started
**Impact:** Eliminates skipped tests caused by unresolvable page-state placeholders like "home page visible"
**Backlog ref:** B-021
**Spec:** `docs/specs/FEATURE_SPEC_URL_ASSERT.md`

**Problem:** When a user story includes page-level assertions ("home page is visible",
"dress products page is loaded"), the `PageStateAssertStrategy` correctly detects these
as non-element descriptions but rejects all DOM candidates, producing `pytest.skip()`.
DOM-element assertions are unreliable for page identity — headings like "AutomationExercise"
appear on multiple pages. The only precise page-identity check is `expect(page).to_have_url(...)`.

**What's needed:**
- [ ] `PageStateAssertStrategy` returns URL-resolution signal instead of `False`
- [ ] `IntentMatcher` propagates URL signal through match chain
- [ ] `PlaceholderOrchestrator` branches on URL signal → calls `resolve_url()` → emits `to_have_url()` code
- [ ] `PlaceholderResolver.resolve_url()` extended keyword mapping (home page → base URL, products page → /products, etc.)
- [ ] Generated code: `expect(page).to_have_url("<url>")` instead of `expect(page.locator(...))`
- [ ] Fallback to `pytest.skip()` when URL resolution fails (unknown page reference)
- [ ] 20+ unit tests across intent_matcher, placeholder_resolver, placeholder_orchestrator
- [ ] No regression on existing element-level ASSERT resolution

**Phases:**
1. Signal propagation — `PageStateAssertStrategy` → `IntentMatcher` → orchestrator
2. URL resolution + code generation
3. Extended `resolve_url()` keyword mapping
4. Unit tests + UAT validation on automationexercise.com

**Dependencies:** B-014 ASSERT scoring (shipped), B-014 step-context resolution (draft) — step context feeds `known_urls` to `resolve_url()`

**Estimated sessions:** 1

---

## Tier 3 — Infrastructure

### 6. AI-029 — Workspace Isolation & Storage Abstraction

**Priority:** Medium  
**Status:** `[x]` Shipped 2026-07-20  
**Impact:** Centralises all storage path construction through `src/storage.py` and adds workspace isolation (`--workspace` flag). Prevents painful rewrites when adding multi-tenancy (SaaS) or cloud storage (S3). Pure refactoring — no feature behavior changes.  
**Spec:** `docs/specs/FEATURE_SPEC_AI029_workspace_storage.md`

**What's needed:**
- [ ] `src/storage.py` — `StorageBackend` Protocol, `LocalStorageBackend`, singleton with `get_storage()` / `init_storage()` / `reset_storage()`
- [ ] Workspace-aware paths: `default` workspace maps to repo root (backwards compat); named workspaces → subdirectory
- [ ] Migrate ~15 files from hardcoded `Path("generated_tests")` / `Path("evidence")` to `get_storage()` calls
- [ ] `SQLitePersistence` already accepts `db_path` — just pass `get_storage().db_path()`
- [ ] CLI: `--workspace` flag; Streamlit: `WORKSPACE` env var
- [ ] CI gate: `rg 'Path\("generated_tests"\)' -- '*.py'` must return zero results
- [ ] 15+ unit tests for `src/storage.py`

**Dependencies:** None — pure refactoring, no feature dependencies.

**Why now:** Costs ~2 hours. Deferring to after multi-tenancy is built means ETL-ing customer data to new directory layouts.

**Estimated sessions:** 1

---

### 7. AI-012 — SQLite Persistence Layer

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

### 8. Phase 4 — Docker Improvements

**Priority**: Medium  
**Status**: `[x]` Complete  
**Impact**: "docker compose up" first impression + enterprise GTM  
**Files**: `Dockerfile`, `docker-compose.yml`

**Implementation completed**:
- [x] Multi-stage build: builder stage for deps, runtime stage for app
- [x] Use `uv` instead of `pip` for faster, lockfile-based installs
- [x] Use Playwright's official image as runtime base (`mcr.microsoft.com/playwright/python:v1.50.0-jammy`)
- [x] Added `uv.lock` copy + `uv sync --frozen` for reproducible builds
- [x] Updated `docker-compose.yml` to include all provider configuration (Ollama, LM Studio, OpenAI-compatible local servers)
- [x] Fixed volume mounts to only mount user-specific directories (generated_tests, evidence, notebooks, scripts)
- [x] Updated default command to run Streamlit app

**Estimated sessions:** 1

---

### 9. Phase 5 — Automated Evaluation Harness

**Priority:** High (for ML Engineering portfolio)  
**Status:** `[x]` Core Complete (Phases 1-5)  
**Impact:** Regression protection for prompt/model/resolver changes + quantitative baseline for dual-tier comparison

**Problem:** With 800+ tests and complex resolver logic, prompt changes or model swaps can silently degrade output quality. No quantitative quality gate exists.

**What's done (Phases 1-5):**
- [x] Frozen dataset: 4 stories across 4 demo sites (saucedemo, automationexercise, demoqa, theinternet)
- [x] Golden answer keys: `scripts/eval/dataset/` — 43 golden placeholders with tolerance_selectors
- [x] Pipeline captures: `scripts/eval/captures/` — generated code from all 4 sites
- [x] `scripts/eval/eval_metrics.py` — metric computation (accuracy, pass rate, FP rate, skeleton completeness)
- [x] `scripts/eval/golden_validator.py` — code parsing, golden key loading, validation engine
- [x] `scripts/eval/eval_runner.py` — orchestration, static + full modes, SQLite persistence
- [x] `scripts/eval/eval_harness.py` — standalone CLI: `run`, `baseline`, `compare`, `dataset`
- [x] `scripts/eval/ci_summary.py` — CI markdown summary generator
- [x] `.github/workflows/eval-harness.yml` — `workflow_dispatch` CI job (manual trigger)
- [x] `scripts/eval/README.md` — usage guide
- [x] SQLite: new `eval_runs` table in `evidence/run_results.sqlite` with history tracking
- [x] Unit tests: 60 tests across 3 test files, 100% pass
- [x] Baseline accuracy: **79.1%** (34/43 placeholders correct)
- [x] Quality gates: ruff clean, mypy clean, 1366/1367 main tests pass (0 regressions)

**Deferred (future sessions):**
- [ ] Expand dataset: multi-page mock documents (PDFs, HTML docs) for RAG-ready evaluation
- [ ] **Dual-Tier Awareness:** Harness must support Free vs Paid tier configurations (Track B)

**Estimated sessions:** 2-3 (2 used)

---

## Tier 4 — ML Engineering Roadmap

### 10. Phase 2 — Full Self-Healing Reflection Loops

**Priority:** Medium (portfolio)  
**Status:** `[~]` Core loop shipped 2026-07-20 (Streamlit integration done). Iterative reflection loop remaining.  
**Impact:** "Self-healing AI automation" marketing message

**Foundation already built:**
- AI-023 (locator repair loop) — shipped
- `src/failure_classifier.py` — classifies failure types
- `src/locator_repair.py` — applies locator patches
- Three-pass resolver with fallback chain

**What's done:**
- [x] `src/self_healing.py` — SelfHealingRunner, HealingReport, AppliedPatch
- [x] LLM reviewer with structured JSON response parsing
- [x] Four repair strategies: replace_locator, add_navigation, add_wait, skip_test
- [x] Streamlit "🩹 Self-Heal Failed Tests" button + healing results display
- [x] CLI: `self_heal_cli()` + "Self-Heal Failed Tests" menu item
- [x] 28 unit tests (extract_test_function, format_elements, parse_response, apply_patch, heal integration)

**What's needed:**
- [ ] Merge with interactive locator repair fallback (Phase 2b)
- [ ] Reviewer agent that pre-screens fixable vs. unfixable before LLM call (cost optimization)

**Estimated sessions:** 2-3

---

### 11. Phase 3 — Enterprise RAG

**Priority:** Medium (portfolio)  
**Status:** `[x]` Shipped 2026-07-21 — all 4 phases complete  
**Impact:** Token cost reduction + ML Engineering portfolio piece  
**Spec:** `docs/specs/FEATURE_SPEC_phase3_rag.md`

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
- [x] Write spec: `docs/specs/FEATURE_SPEC_phase3_rag.md` (shipped 2026-07-21 — Milvus Lite, 4 phases, eval-gated)
- [x] Phase 3a: Vector store — MilvusLiteBackend + RAGStore + SentenceTransformerEmbedder (35 tests)
- [x] Phase 3b: Resolver integration — RAGRetriever → PlaceholderOrchestrator → PlaceholderScorer (16 tests)
- [x] Phase 3c: Ingestion — `scripts/rag_ingest.py` + curated Playwright docs + chunking (15 tests)
- [x] Phase 3d: Measurement — store built (70 entries), 40/40 self-consistency (100%), zero regressions

**Estimated sessions:** 3-4

---

### 12. Phase 1 — Multi-Agent Architecture (LangGraph) with Model-Agnostic Providers

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

## Tier 5 — Commercialization

Items required to sell the tool publicly (marketplace, SaaS, CI/CD integration).

### 13. Phase 6 — SaaS Deployment

**Priority:** Medium (deferred)  
**Status:** `[ ]` Not started  
**Impact:** Enables hosted SaaS offering — users sign up, log in, and generate tests in their browser without installing anything.  

**What's needed:**
- [ ] Production Streamlit deployment (gunicorn + Nginx, or Streamlit Community Cloud Pro)
- [ ] User auth (OAuth: GitHub/Google, or email/password via Supabase Auth)
- [ ] Per-user isolation — each user gets their own workspace (AI-029 provides the foundation)
- [ ] S3-backed storage for generated tests + evidence (AI-029 `StorageBackend` Protocol enables this)
- [ ] Usage metering — track test runs, LLM tokens consumed, storage per user
- [ ] License key management — generate, validate, expire keys; tier enforcement (Free vs Pro)
- [ ] HTTPS, session affinity, rate limiting

**Dependencies:** AI-029 (Workspace & Storage) — the storage abstraction and workspace concept are prerequisites.

**Estimated sessions:** 3-4

---

### 14. Phase 7 — CI/CD Integration

**Priority:** Medium-High (deferred)  
**Status:** `[ ]` Not started  
**Impact:** Enterprise adoption driver — teams don't run tools manually; they want automated test generation in their CI pipeline.  

**What's needed:**
- [ ] GitHub Action: `ai-playwright/test-generator@v1` — generate + run tests on PR, post results
- [ ] GitLab CI template — same for GitLab users
- [ ] PR comment with generated test summary: pass/fail counts, coverage heatmap, flaky test markers
- [ ] JUnit XML consumption — AI-028 export feeds this natively
- [ ] Configurable: generate-only mode, generate-and-run mode, run-existing mode
- [ ] Cache generated tests across CI runs (avoid regenerating unchanged stories)

**Dependencies:** AI-028 (Evidence Export) for JUnit XML; AI-029 (Workspace) for CI workspace isolation.

**Estimated sessions:** 2-3

---

### 15. Phase 8 — GTM Assets

**Priority:** Medium (deferred)  
**Status:** `[ ]` Not started  
**Impact:** Everything customers see before they buy. Landing page, docs, demo, marketplace listings.  

**What's needed:**
- [ ] Public docs site (MkDocs or Docusaurus) — quickstart, API reference, deployment guides, examples
- [ ] Landing page with: product screenshots, feature list, pricing tiers, "Get Started" CTA
- [ ] Demo video (2-3 minutes) — record a real session: story → generate → HTML evidence
- [ ] Interactive sandbox — try the tool in-browser without installing (limited to 3 test generations)
- [ ] AWS Marketplace listing — Docker image / AMI, usage-based billing integration
- [ ] PyPI package — `pip install ai-playwright-generator` (CLI only, free tier)
- [ ] Case study / testimonial — one real user story to establish credibility

**Dependencies:** Phase 6 (SaaS) for sandbox; AI-028 (Export) for demo footage of evidence viewer.

**Estimated sessions:** 2-3

---

## Future Considerations

Items worth investigating but not on the active roadmap.

### FC-01 — HTTP QUERY Method (RFC 10008) for Test Search API

**Status:** `[ ]` Future consideration  
**Date noted:** 2026-07-15  
**Ref:** https://www.rfc-editor.org/rfc/rfc10008 (June 2026)

RFC 10008 defines the HTTP QUERY method: safe, idempotent, cacheable requests with a body.
Currently not applicable — our project uses local Python → SQLite, no HTTP API layer.

**Becomes relevant if:** We expose a REST API for searching/filtering test history or eval results.
QUERY would be the correct method for "search tests with complex filters" — avoids URL query param
limits, is cacheable, and safe for retries.

**Trigger to revisit:** Any feature that adds an HTTP endpoint for querying test/run data.

---

## Summary Checklist

| # | Item | Tier | Status | Est. Sessions |
|---|------|------|--------|---------------|
| 1 | B-014 ASSERT resolution | Bug | `[x]` Shipped | 1 |
| 2 | B-015 Journey element | Bug | `[x]` Shipped | 1 |
| 3 | B-022 State-dependent scraping | Bug | `[x]` Shipped 2026-07-20 | 1-2 |
| 4 | B-023 Cart modal interception | Bug | `[x]` Shipped 2026-07-20 | 0.5 |
| 5 | AI-010 POM Toggle | Feature | `[x]` All phases complete | 2 |
| 5 | AI-011 Run History | Feature | `[x]` Complete | 2 |
| 6 | AI-026 CLI Persist finish | Feature | `[x]` Step 7 verified | 0-1 |
| 6 | AI-028 Evidence Search & Export | Feature | `[x]` Shipped 2026-07-20 | 2 |
| 7 | AI-029 Workspace & Storage | Infra | `[x]` Shipped 2026-07-20 | 1 |
| 8 | AI-012 SQLite Persistence | Infra | `[x]` Complete | 2 |
| 9 | Phase 4 Docker polish | Infra | `[x]` Complete | 1 |
| 10 | Phase 5 Eval Harness | Infra | `[x]` Complete | 2-3 |
| 11 | Phase 2 Self-Healing | ML | `[~]` Core shipped | 2-3 |
| 12 | Phase 3 RAG | ML | `[x]` Shipped 2026-07-21 | 3-4 |
| 13 | Phase 1 Multi-Agent | ML | `[ ]` High (promoted) | 3-4 |
| 14 | Phase 6 SaaS Deployment | Commercial | `[ ]` Not started | 3-4 |
| 15 | Phase 7 CI/CD Integration | Commercial | `[ ]` Not started | 2-3 |
| 16 | Phase 8 GTM Assets | Commercial | `[ ]` Not started | 2-3 |
| 17 | URL-Based Assertions (B-021) | Feature | `[x]` Shipped 2026-07-20 | 1 |
| 18 | State-Dep. Scraping (B-022) | Bug | `[x]` Shipped 2026-07-20 | 1 |
| 19 | Cart Modal (B-023) | Bug | `[x]` Shipped 2026-07-20 | 0.5 |

**Total estimated sessions:** 29-43 (+2 for AI-012)

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
| 2026-07-13 | Phase 5 Eval Harness (dataset + metrics) | Grilling session: defined design decisions (two-track, 4 sites, JSON golden keys). Spec written. Captured pipeline outputs for 4 sites. Golden keys hand-validated and committed. Baseline accuracy: 79.1% (34/43). `eval_metrics.py` + `golden_validator.py` with 48 tests. |
| 2026-07-15 | Phase 5 Eval Harness (runner + CLI) | `eval_runner.py` — static validation, test execution, SQLite persistence. `eval_harness.py` — standalone CLI with 4 subcommands (run, baseline, compare, dataset). Both --static and --full modes. 60 eval tests, 1366 main tests pass. ruff clean, mypy clean. HTTP QUERY (RFC 10008) noted as future consideration FC-01. |
| 2026-07-15 | Phase 5 Eval Harness (CI integration) | `.github/workflows/eval-harness.yml` — workflow_dispatch job with mode + min_accuracy inputs. `ci_summary.py` — markdown summary generator. `scripts/eval/README.md` — usage guide. Phase 5 spec complete. |
| 2026-07-19 | AI-029 Workspace & Storage | Shipped `src/storage.py` — StorageBackend Protocol + LocalStorageBackend + singleton. Migrated 12 consumer files from hardcoded Path("generated_tests")/Path("evidence") to get_storage(). Default workspace preserves repo-root layout. Streamlit init_storage() at startup. CI gates: zero hardcoded path hits. 30 new tests, 1457 total. |
| 2026-07-20 | AI-028 Evidence Search, Filter & Export | Shipped all 4 phases: EvidenceIndex (SQLite-backed metadata index with incremental mtime refresh, 42 tests), evidence_export.py (CSV/NDJSON/JUnit XML, 31 tests), UI (search bar + filter row + download buttons replacing flat selectbox), CLI (search/detail/rerun/export subcommands with timestamps and step-level inspection). 73 new tests, 1530 total. |
| 2026-07-21 | Phase 3 RAG (all 4 phases) | Shipped complete RAG pipeline: Milvus Lite vector store (35 tests), resolver integration via RAGRetriever → orchestrator → scorer (16 tests), ingestion CLI + 3 curated Playwright docs + chunking (15 tests), measurement (40/40 self-consistency = 100%, zero regressions). 1625 total pass. `RAG_ENABLED=1` enables at runtime. |

---

## Rules for Implementation

1. **One item per session** — per AGENTS.md §10
2. **Design session first** for B-014 and any item marked "Needs design session"
3. **ruff → mypy → pytest → commit** before marking any item complete
4. **Update this doc** at end of each session with completion status
5. **Update memory bank** with new decisions/patterns discovered
6. **Do not skip the eval harness** (Phase 5) — build it before Phase 2/3/4 so regressions are caught

---

*Last updated: 2026-07-20*
