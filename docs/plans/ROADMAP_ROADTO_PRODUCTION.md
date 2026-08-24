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

**What's done:**
- [x] `src/evidence_index.py` — `EvidenceIndex` class that indexes sidecar metadata into SQLite (`evidence_index` table)
- [x] `src/evidence_export.py` — CSV, NDJSON, and JUnit XML exporters, all respecting the same filter parameters
- [x] Streamlit download buttons for all three export formats (full dataset or filtered subset)
- [x] Full-text search via SQL `LIKE` across test name, condition ref, story ref, URL, and step labels
- [x] Faceted filters: status (passed/failed), URL domain, condition ref prefix
- [x] Search bar + filter row + results list replacing flat `st.selectbox` in EvidenceViewer
- [x] CLI: `python -m cli.evidence_cli search --query "dress"` and `export --format csv --output evidence.csv`
- [x] 73 unit tests (`test_evidence_index.py` + `test_evidence_export.py`)

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
**Status:** `[x]` Shipped 2026-07-20
**Impact:** Eliminates skipped tests caused by unresolvable page-state placeholders like "home page visible"
**Backlog ref:** B-021
**Spec:** `docs/specs/FEATURE_SPEC_URL_ASSERT.md`

**Problem:** When a user story includes page-level assertions ("home page is visible",
"dress products page is loaded"), the `PageStateAssertStrategy` correctly detects these
as non-element descriptions but rejects all DOM candidates, producing `pytest.skip()`.
DOM-element assertions are unreliable for page identity — headings like "AutomationExercise"
appear on multiple pages. The only precise page-identity check is `expect(page).to_have_url(...)`.

**What's done:**
- [x] `PageStateAssertStrategy` returns URL-resolution signal instead of `False`
- [x] `IntentMatcher` propagates URL signal through match chain
- [x] `PlaceholderOrchestrator` branches on URL signal → calls `resolve_url()` → emits `to_have_url()` code
- [x] `PlaceholderResolver.resolve_url()` extended keyword mapping (home page → base URL, products page → /products, etc.)
- [x] Generated code: `expect(page).to_have_url("<url>")` instead of `expect(page.locator(...))`
- [x] Fallback to `pytest.skip()` when URL resolution fails (unknown page reference)
- [x] 20+ unit tests across intent_matcher, placeholder_resolver, placeholder_orchestrator
- [x] No regression on existing element-level ASSERT resolution

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

**What's done:**
- [x] `src/storage.py` — `StorageBackend` Protocol, `LocalStorageBackend`, singleton with `get_storage()` / `init_storage()` / `reset_storage()`
- [x] Workspace-aware paths: `default` workspace maps to repo root (backwards compat); named workspaces → subdirectory
- [x] Migrated 12 consumer files from hardcoded `Path("generated_tests")` / `Path("evidence")` to `get_storage()` calls
- [x] `SQLitePersistence` now passes `get_storage().db_path()`
- [x] CLI: `--workspace` flag; Streamlit: `WORKSPACE` env var
- [x] CI gate: `rg 'Path\("generated_tests"\)' -- '*.py'` returns zero results
- [x] 30 unit tests for `src/storage.py`

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

**Deferred / removed (future sessions):**
- [x] Expand dataset: multi-page mock documents (PDFs, HTML docs) for RAG-ready evaluation — shipped via AI-030 (LV Insurance eval-005, 5 sites total)
- [R] ~~Dual-Tier Awareness: Free vs Paid tier configurations~~ — removed: eval harness should be identical across tiers

**Estimated sessions:** 2-3 (2 used)

---

### 17. AI-043 — Output Artifact Quality Gate (heatmap / Gantt / graph accuracy)

**Priority:** Medium (quality) — visual artifacts are customer-facing evidence; a wrong heatmap or Gantt reads as "the tool doesn't know what it's doing" even when tests passed (demo-blocker class)
**Status:** `[x]` Complete — Layers 1-3 shipped 2026-08-11 (Layer 3 landed 2026-08-11)
**Impact:** Evidence/report artifacts (heatmap overlays, Gantt timelines, run-history graphs) must be truthful to the run that produced them. This is a deterministic rendering problem — a validation harness catches these bugs at zero training cost.

**Problem:** Unit tests validate chart *builders* (fixture sidecar → figure structure), but nothing validates the rendered artifact against source truth. Known failure classes (from production reports):
- Heatmap boxes misaligned with the page — `loc.bounding_box()` returns CSS pixels, Playwright screenshots are image pixels, and **no device-pixel-ratio scaling** is applied between them (DPR>1 displays misalign by construction)
- Heatmap aggregates boxes from *all* steps but picks **one** background screenshot per URL — if the page changed between steps, earlier steps' boxes sit on the wrong frame
- Gantt "all over the place" — hardcoded/zero `duration_s` (B-044 class), unsorted starts, axis not covering entries
- Unreadable charts at report size (overlapping labels, empty/NaN series)

**What's needed:**
- [x] **Layer 1 — deterministic invariants** (offline, CI): `src/artifact_validation.py` — heatmap points are % of document in [0,100] (catches legacy pixel coords); payloads parseable/finite; aggregated counts consistent with statuses; Gantt durations finite & >= 0 (NaN/negative collapses timeline); generic Plotly NaN/None/empty-series checks
- [x] **Layer 2 — golden fixtures**: `fixtures/report_golden/` — good sidecar set (must pass) + legacy-pixel + NaN-duration sets (must fail)
- [x] **Layer 3 — Playwright alignment** (full mode, mock sites): render the heatmap HTML over the live page at the recorded viewport and assert each overlay box's center hits the element it claims — shipped 2026-08-11. `src/heatmap_alignment.py`: `extract_points` → `point_to_document_px` (live doc size) → one locator-scoped evaluate (`elementFromPoint` + ancestor/descendant containment — no DOM handles cross the protocol boundary; this Playwright build serialises node returns as strings). Catches stale locators + wrong-frame drift. Live tests: 3/3 against the ecommerce mock (real chromium, real tracker metadata math); CLI gate via `scripts/validate_report_artifacts.py --full`. 18 offline + 3 live tests.
- [x] Regression tests: legacy pixel-valued `viewport_pct`; NaN/negative Gantt duration (DPR investigated 2026-08-09: % coords cancel device-pixel-ratio — NOT a bug; legacy pixel coords are)
- [x] Wire into gates: `scripts/validate_report_artifacts.py` CLI (exit 1 on errors) + 3 checks in `scripts/smoke.py` Gate 0
- [x] Follow-up fix (2026-08-09, same session): `evidence_tracker._get_element_metadata` now converts viewport-relative bbox to document coordinates (adds scrollX/scrollY) and clamps % to [0,100] — no more negative y / off-page markers. Regression tests: document-relative math, negative-y clamp, scroll-probe failure fallback.

**Verified 2026-08-09:** validator run over all 51 evidence dirs under `generated_tests/` — 5 dirs flagged with negative-y coords (2 errors each), the rest clean; golden fixtures green in smoke + full suite (2399 passed).

**Related:** Phase 5 eval harness (item 9), B-044 (real durations), AI-020 (annotated screenshots), AI-016–022 (evidence chain)

**Estimated sessions:** 2-3

---

## Tier 4 — ML Engineering Roadmap

### 10. Phase 2 — Full Self-Healing Reflection Loops

**Priority:** Medium (portfolio)  
**Status:** `[x]` Shipped 2026-07-26 — iterative reflection loop complete  
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

**Phase 2b shipped (2026-07-26):**
- [x] Rule-based pre-screening: assertion/navigation/other failures skip LLM call entirely (cost optimization)
- [x] Interactive repair fallback: locator failures the LLM can't fix are marked as `interactive_repair_candidates` in HealingReport, flowing seamlessly into the existing interactive locator repair UI
- [x] 46 unit tests total (18 new: pre-screen + interactive candidates + integration)

**What's no longer needed:**
- [R] ~~Merge with interactive locator repair fallback~~ — shipped via `interactive_repair_candidates` in HealingReport
- [R] ~~Reviewer agent that pre-screens fixable vs. unfixable~~ — shipped via `_pre_screen_failure()` rule-based filter

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

**What's done:**
- [x] Vector DB — Milvus Lite local deployment
- [x] Store Playwright documentation chunks for retrieval at resolution time
- [x] Hook into Ingestion Agent (Phase 1) for document parsing
- [x] Upgrade resolver to retrieve relevant patterns before scoring
- [x] Measure: RAG improves resolution accuracy vs. baseline
- [x] Write spec: `docs/specs/FEATURE_SPEC_phase3_rag.md` (shipped 2026-07-21 — Milvus Lite, 4 phases, eval-gated)
- [x] Phase 3a: Vector store — MilvusLiteBackend + RAGStore + SentenceTransformerEmbedder (35 tests)
- [x] Phase 3b: Resolver integration — RAGRetriever → PlaceholderOrchestrator → PlaceholderScorer (16 tests)
- [x] Phase 3c: Ingestion — `scripts/rag_ingest.py` + curated Playwright docs + chunking (15 tests)
- [x] Phase 3d: Measurement — store built (70 entries), 40/40 self-consistency (100%), zero regressions

**Estimated sessions:** 3-4

---

### 12. Phase 1 — Multi-Agent Architecture (LangGraph) with Model-Agnostic Providers

**Priority:** High (promoted from Low)  
**Status:** `[x]` Complete 2026-07-31 — BUT **dormant**: not wired into the user-facing pipeline (see BACKLOG "LangGraph Pipeline — Dormant" note 2026-08-01). `run_pipeline_via_graph()` is called only by eval `--use-graph` + unit tests; the UI/CLI/uat use the linear `run_pipeline()`. `langgraph` is a core dependency — graph tests run locally and in CI (71/71 pass).

**Scope note (2026-08-11 audit):** "Complete" covers the LangGraph core + eval + doc-mode (phases 1a-1j). The model-agnostic half of the original scope — per-agent model configuration, cloud providers (Anthropic/Google), per-agent selection UI, named config profiles, fallback chain — was **never built** (verified: no `AGENT_*` envs in code; `src/llm_providers/` ships only Ollama/LMStudio/OpenAI). Items marked **NOT BUILT** below are the open (dormant) scope.
**Impact:** Formal multi-agent pattern for portfolio + enables Phase 3 RAG + complete model flexibility

**Research verified (2026-06-14):**
- LangGraph confirmed as mature framework for multi-agent orchestration (state machines, human-in-the-loop)
- Gemma 4 models verified (released April 2026 by Google, Apache 2.0 licensed)
- **IMPORTANT:** Do NOT use DiffusionGemma — it's weaker on reasoning benchmarks (MMLU Pro: 77.6% vs 82.6%, AIME: 69.1% vs 88.3%)
- Use standard Gemma 4 26B-A4B MoE for all agents

**Proposed agent roles with verified models:**
- [x] **Ingestion Agent:** Gemma 4 26B-A4B MoE (3.8B active params, ~14.4GB at 4-bit) — role shipped (doc-mode, PyMuPDF); model = documented recommendation
- [x] **QA Director:** Gemma 4 31B Dense (~17.5GB at 4-bit) — role shipped; model = documented recommendation
- [x] **Script Synthesizer:** Gemma 4 26B-A4B MoE (~14.4GB at 4-bit) — role shipped; model = documented recommendation

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
- [x] Formal LangGraph state management — `src/agents/pipeline_graph.py` (71/71 tests)
- [x] Define agent roles: Ingestion, QA Director, Script Synthesizer — `src/agents/{ingestion,director,synthesizer,validator,planner}.py`
- [x] Refactor orchestrator to use agent framework — `run_pipeline_via_graph()` in `src/orchestrator.py`
- [ ] Implement per-agent model configuration — **NOT BUILT** (no `AGENT_*` envs; dormant scope)
- [ ] Add cloud providers (Anthropic, Google) — **NOT BUILT** (only Ollama/LMStudio/OpenAI)
- [ ] Configuration UI for model selection — **NOT BUILT**
- [ ] Fallback mechanism implementation — **NOT BUILT**
- [x] Requires Phase 5 eval harness to verify no regression — eval `--use-graph` path
- [x] Write spec: `docs/specs/FEATURE_SPEC_phase1_multi_agent.md`

**Estimated sessions:** 4-5 (increased from 3-4 due to cloud provider integration)

**📄 Document-Driven Input Mode:** Spec'd as §9 of `FEATURE_SPEC_phase1_multi_agent.md` (2026-07-26). Extends the same `PipelineGraph` with PDF/Markdown ingestion, change-delta extraction, persona-aware routing, impact mapping, and consolidated reporting. Parsing front-end starts with PyMuPDF (shipped via AI-030); Unlimited OCR (arXiv:2606.23050) is the upgrade path when GPU infra is available. Adds 3 sessions to Phase 1 total (phases 1f-1j).

---

### 12b. AI-034 — Test Table Generation (COMPLETE 2026-08-01)

**Priority:** High  
**Status:** `[x]` Complete — Phases 1-3 shipped 2026-08-01  
**Spec:** `docs/specs/FEATURE_SPEC_AI034_test_table_preflight.md`  
**Dependency:** Phase 1 Multi-Agent (Ingestion Agent feeds richer input) — met
**Impact:** One focused test row per scenario; tester reviews/edits rows before one skeleton per row is generated

**What's needed:**
- [x] Write spec: `docs/specs/FEATURE_SPEC_AI034_test_table_preflight.md`
- [x] Phase 1: Test Table generation — `src/test_table.py` data model + LLM expansion + CRUD
- [x] Phase 2: Living Test Plan enhancement — "Tests" column + editors in Streamlit AND CLI
- [R] Phase 3: Pre-flight resolution reporting — removed from spec 2026-07-31 (resolver already surfaces failures via `pytest.skip()` + evidence)
- [x] Phase 4: Skeleton generation — one function per test row (via `table_to_conditions()`)
- [x] Test Table editor UI in Streamlit (mirrors Living Test Plan pattern) — shipped 2026-08-01 (🧪 Test Table expander, data_editor + Save/Confirm-All)
- [x] 30+ unit tests (`test_test_table.py`) — 33 tests shipped with Phase 1

**Estimated sessions:** 3-4

---

### 16. AI-042 — Cross-Site Flow Memory (learn navigation/method patterns from passing evidence)

**Priority:** Medium (portfolio + commercial) — faster multi-site onboarding (Phase 8 GTM)
**Status:** `[x]` Complete — learner + store + consumption shipped 2026-08-12; eval holdout measured 2026-08-12 (0 → 3/4 non-home URL asserts resolvable with holdout integrity)
**Impact:** "First passing test on an unseen site" is the value moment for a new customer — locator memory can't transfer (verified: only 3% of learned locator pairs overlap across sites), but navigation/method *shape* does (login→browse→cart→checkout is near-identical across e-commerce sites).

**Problem:** Every test run regenerates flows from scratch. Locators are correctly site-locked (B-047), but method sequences and navigation transitions are thrown away even though they generalize.

**Evidence available today:**
- Sidecars record a `url` per step — the full navigation trace (login → /inventory.html → cart → checkout)
- `_step_to_pattern` deliberately skips `navigate` steps, so flows are learned nowhere
- `src/url_resolver.py` alias groups (cart→cart/basket, login→login/signin/auth) are the only cross-site navigation knowledge — hardcoded, not learned

**What's needed:**
- [x] Flow learner: read passing sidecars → transition tuples (from_url_pattern, action, description, to_url_pattern), aggregated across sites with hit counts + site diversity — `src/flow_memory.py` (`flow_transitions`, `FlowMemoryStore`, shipped 2026-08-12). Seeded from 908 real sidecars → 64 patterns, 6 sites, 4 cross-site (home→cart, home→checkout)
- [x] Site-agnostic generalization via URL *patterns* (normalized route keywords) — never raw URLs (privacy: one-way hashes only, per AI-035 §4) — `normalize_route()`; site identity = sha256(host[:port]); routes are generic vocabulary
- [x] Consumption hook: (b) Phase 2 GOTO / URL-assertion resolution confidence — `flow_resolved_url()` wired as step 2.5 in the orchestrator's GOTO/URL chain + page-state ASSERT fallback (after UrlResolver + resolve_url, before heuristic — site evidence always wins). (a) skeleton guidance not built (prompt changes are regeneration-sensitive — deferred, see notes)
- [x] Guardrails: learn only from passing steps, `min_sites` cross-site filter (2 = ≥2-site-verified only), hit-count ranking, site-specific evidence wins over cross-site flow
- [x] Evaluation: hold out one eval dataset as an "unseen site" and measure first-pass accuracy vs today — **shipped 2026-08-12**: `scripts/eval/flow_holdout_eval.py`. Result: **0 → 3/4 non-home URL asserts resolvable with holdout integrity** (target site's own evidence excluded) after adding route canonicalization (`normalize_route` aliases: view_cart/basket→cart, inventory→products, signin/auth→login — the learned analog of url_resolver's hardcoded groups; exact whole-route match only, step pages stay distinct). automationexercise products/cart asserts resolve via saucedemo + mock flows only; ecommerce cart assert is strict cross-site (2 sites). Baseline 0 (eval_resolver treats ASSERT as element matching). Corpus caveats: 3 home-target goldens are seed-fallback scope (not flow memory); ecommerce checkout excluded (flows co-verified on the target mock port 8781); no GOTO goldens exist yet — a GOTO-flavored dataset would exercise the hook directly
- [x] Unit tests (`tests/test_flow_memory.py`) — 34 tests incl. orchestrator consumption integration (GOTO resolves via cross-site flow when site resolution fails; disabled store is a no-op)

**Related:** AI-035 (self-learning RAG), B-047 (site scoping), AI-040/041 (training corpus — flow-shaped skeleton rows may overlap; check before building a separate runtime path)

**Follow-ups (optional — not required for the item's completion):**
- [x] **AI-042-F1 — GOTO-flavored golden dataset** — shipped 2026-08-12: `docs/rag_corpus/playwright/04-navigation.md` (curated navigation reference — the corpus previously had one navigation section in 3 files; Playwright's own docs treat navigation as first-class: `page.goto` is core, actionability explicitly exempts navigation), `scripts/eval/dataset/eval-008_goto_navigation.json` (banking mock, 2 GOTO goldens + URL asserts with `expected_page` from-contexts), flow path wired into `eval_resolver._resolve_placeholder` (GOTO/URL/url_assertion resolve via `flow_resolved_url` using `expected_page` as from-context; 3 hermetic tests `tests/test_eval_goto_flow.py`), stateful scraped pages for the banking mock (login-wall index + session-gated pages) — banking_mock resolver accuracy 9/26 → **13/26 (50%)**, overall resolver 32.1% → 35.8%, holdout eval 3/7 → 6/11, static harness gate unchanged at 97.9% (eval-008 is 0/0 without a capture)
- [ ] **AI-042-F2 — Flow stats + prune in Streamlit**: parity with the RAG "Learned Patterns" section — show flow store stats (patterns / sites / cross-site) + a prune button (`FlowMemoryStore.clear()` + `stats()` already exist)
- [x] **AI-042-F2 — Flow stats + prune in Streamlit** — shipped 2026-08-12: `SidebarConfig._render_flow_memory()` in `src/ui/ui_sidebar.py` (parity with the RAG "Learned Patterns" section) — "Flow Memory" subheader with `format_flow_stats_summary()` (patterns / sites / cross-site / suite chains) + two-step prune calling `FlowMemoryStore.clear()` (all flows are learned — no golden/docs tier to keep, unlike RAG); empty store degrades to a hint. Pure `format_flow_stats_summary` helper + 2 stubbed-UI tests (4 new tests, 51 total)
- [x] **AI-042-F3 — Cross-test flow chaining** — shipped 2026-08-12: `chain_suite_transitions()` + `FlowMemoryStore.learn_suite_flows()` chain adjacent fully-passing tests in name order into GOTO transitions (terminal page of test N → entry page of test N+1, description = destination route name; same-site pairs only — a mixed evidence dir never chains; home/no-movement dropped; pre-B-033 sidecars fall back to navigate values). `FlowPattern.source` distinguishes `within_test`/`suite_chain`; `stats()` reports the split. Wired into ALL run paths: `synthesize_stories.py` parent sweep, `PipelineRunService.run_saved_test` (UI + CLI product runs), `scripts/verify_production.py`. Re-seed: **24 new suite-chain patterns** (89 → 113, cross-site 5 → 8) incl. the valuable cart↔checkout↔products chains verified on 2 sites; holdout eval strict cross-site 1/11 → **2/11**. 13 new tests (47 total)
- [ ] **AI-042-F4 — Skeleton guidance (roadmap option (a))**: deliberately deferred — prompt changes are regeneration-sensitive (AI-037 lesson); revisit only if GOTO first-pass accuracy demands it

**Estimated sessions:** 2-3

---

### 18. AI-044 — Visual Grounding: vision-based element location

**Priority:** Low-Medium (portfolio + long-term differentiator) — "sees the page like a tester does"
**Status:** `[ ]` **DEFERRED 2026-08-13** — off-the-shelf open-source GUI-grounding models already solve the core task (verified via tavily 2026-08-13: **UGround** — 10M elements / 1.3M screenshots ~95% web, LLaVA-based, SOTA on ScreenSpot; **OS-Atlas** — 2.23M cross-platform; **UI-TARS**; **GUI-Actor** — attention-map, no coords). Training our own model only pays off as a fine-tune-on-own-sidecars LoRA *after* the eval measures a domain gap. Slim option **AI-044-B** (off-the-shelf integration, ~1-2 sessions) keeps the product value without the training pipeline. Revisit at launch readiness or when a fine-tune is wanted.
**Dependency:** ~~AI-041 training pipeline proven~~ — AI-041 closed FAILED 2026-08-11 (GGUF export physically impossible on 64GB Windows). AI-043 landed (validation to measure it against). Vision inference is CPU-only on this box (ROCm wall, see AI-038).
**Impact:** Solve the resolver's hardest class — elements with no stable id / data-test / accessible name (styling-driven selectors, visual labels) — by locating them from the screenshot. Side effect: heatmaps become trivially correct (boxes come from detected elements, not recorded metadata).

**Problem:** Element location today is DOM/attribute-based (`src/placeholder_scorers.py`). Elements without stable attributes are the known weak spot (AGENTS.md §13: ASSERT placeholders resolving to wrong elements). Screenshots are already captured for every step but never used for location.

**Data (already being collected for free):** every test run writes sidecars with (screenshot, element metadata, bbox) triples — 581 sidecars today, growing every run. Filter to fully-passing steps → verified (image, region, label) pairs with zero labelling effort. This is the training set.

**Design sketch:**
- [ ] Dataset extractor: passing evidence steps → (screenshot, bbox, description) pairs; dedupe, viewport/scroll normalization, versioned in `training_data/`
- [ ] Model: lightweight vision-language (Qwen-VL family — reuses AI-041's Studio path) or detection head (DETR/YOLO-style) on existing embedding infra
- [ ] Integration: vision grounding score into `compute_element_score` (vision as one more signal, not a replacement) or candidate pre-filter
- [ ] Evaluation: extend the eval harness with a localization metric (bbox IoU vs golden element position) — needs AI-043's Playwright-alignment layer to measure truth
- [ ] Guardrails: latency budget at resolve time (vision is slow); privacy unchanged (screenshots stay local, AI-035 §4); fall back to DOM scoring when vision is unavailable/uncertain

**Related:** AI-043 (heatmap accuracy + measurement layer), AI-041 (training infra), AI-035 (RAG), AGENTS.md §13 (ASSERT resolution gap)

**Estimated sessions:** 5-8

---

## Tier 5 — Commercialization

Items required to sell the tool publicly (marketplace, SaaS, CI/CD integration).

### 12c. Upgrade Path — Regenerate Old Packages After Pipeline Changes

**Priority:** Medium (commercial trust)  
**Status:** `[ ]` Not started — added 2026-08-17 (research log: `docs/plans/RESEARCH_SAAS_AND_LAUNCH.md`)  
**Impact:** A customer generates a suite on v1, upgrades TanCat to v2, and the pipeline's prompts/resolver changed. Can they regenerate without breaking? This is the "upgrading the tool doesn't orphan my tests" story — commercial trust for any licensed deployment that lives longer than a month.  

**What transfers (already built):** `PipelineArtifactWriter` save/load, `package_manifest.json` (AI-026), `scrape_manifest.json` full metadata (base_url, page_requirements, journeys, records), `_reconstruct_manifest()` for legacy packages, export stripping, eval harness (to measure regenerated-vs-original drift), self-healing + RAG/flow memory (regenerated locators can re-learn).

**What's new (spec needed):**
- [ ] Package versioning — manifest records the TanCat version + pipeline fingerprint that generated it
- [ ] "Regenerate from saved package" flow — reuse the original story/requirements/scrape metadata, run the current pipeline, diff old vs new generated tests
- [ ] Drift report — which tests changed, which locators moved, which now pass/fail differently (eval-harness-style comparison, not just byte diff)
- [ ] Safety default — regenerate to a *new* package, never overwrite; customer merges/runs the new one
- [ ] Migration policy doc — what counts as a breaking pipeline change vs safe regeneration

**Dependencies:** AI-026 (persist, shipped), Phase 5 eval harness (shipped, for drift measurement), AI-039 naming (manifest format should not change again post-rename — do the manifest versioning *after* the rename decision).

**Estimated sessions:** 2-3

---

### 13. Phase 6 — SaaS Deployment (TWO-PART PLAN — restructured 2026-08-17)

**Priority:** Medium (deferred)  
**Status:** `[ ]` Not started — **Part 1 is the commercialisable v1**; Part 2 deferred until Part 1 is selling  
**Spec:** `docs/specs/FEATURE_SPEC_phase6_saas.md` — **WRITTEN 2026-08-17 (Draft — §9 open questions to grill before 6a/6e build).** Covers: SSRF guard + egress audit (build first — 6a, gates the no-egress pitch), BYO-LLM health check (D1), offline ed25519 license key, per-deployment tiers, runs/credits free tier (**replaces the old "3 generations" number — answered 2026-08-17: meter runs/credits like comparables, `RESEARCH_COMPETITIVE_LANDSCAPE.md` §4.2**), credential policy (D4), team concurrency, + the AI-045 readiness list folded in as the 6a–6i build order.  
**Impact:** Part 1 = per-company deployment (customer's infra, customer's LLM, customer's data) — the enterprise-attractive v1. Part 2 = true multi-tenant SaaS (strangers share our platform) — much bigger isolation build, not required for launch.  

**Part 1 — Per-company deployment ("deploy TanCat, bring your own LLM") — the v1:**
- [ ] Production Docker deployment shape: one shared Streamlit server per company + headless CI driver in one image; team members share one workspace (AI-029 workspace = per-deployment)
- [ ] BYO-LLM onboarding — "check my LLM" first-run health probe (endpoint reachable, key valid, model capable); documented minimum-model recommendations
- [ ] Per-deployment user auth (team members log in to the company's own instance — streamlit-authenticator or equivalent; NOT our central identity)
- [ ] License key: offline-validated signed token (ed25519, expiry, grace period on failure) — works with no internet to our servers; authorises the deployment
- [ ] Usage visibility per deployment (runs, storage, LLM tokens — for the customer's own ops + license tier enforcement)
- [ ] Credential policy shipped: CI reads secrets from the CI platform's secret store via env vars; interactive runs keep credentials in session state; never persisted where avoidable (Fernet `settings.enc` only if unavoidable). **Rule: role scoping is per-story/per-test by declaration — TanCat never selects credentials automatically and never learns which login unlocks which element** (flow memory / RAG learn navigation shape + locators only — no raw URLs, no credential text, no role-to-element maps)
- [x] No-egress verification: audit all runtime outbound HTTP; "no data leaves your deployment" must be literally true (LLM calls go to the customer's endpoint and nothing else) — **6a SHIPPED 2026-08-17/18**: `scripts/audit_egress.py` static gate (143 files / 13 sites / 0 flagged) in smoke Gate 0 + CI; `docs/security/egress-audit.md` published
- [x] Private-IP/SSRF blocklist on scraped URLs (cheap guard + documented warning for internal-network use) — **6a SHIPPED 2026-08-17/18**: `src/url_guard.py` wired into orchestrator intake + all scrapers + `ci_generate.py` (under the Phase 7 danger-zone check)

**Part 2 — True multi-tenant SaaS (DEFERRED — not required for commercial viability):**
- [ ] User auth on OUR platform (OAuth: GitHub/Google, or email/password via Supabase Auth)
- [ ] Per-tenant isolation of the three learned stores (today global per machine): `run_results.sqlite`, RAG vector store (Milvus Lite), flow memory — per-tenant DB files + vector collections + flow stores, or per-tenant containers; process isolation of `get_storage()`/RAG/flow singletons (needs a per-tenant context object — sketch in spec)
- [ ] S3-backed per-tenant storage (AI-029 `StorageBackend` Protocol enables this)
- [ ] Usage metering + free-tier rate limiting on our infra (cost is ~0 — customer's LLM does the work — so the limit is perceived-value, not cost)
- [ ] Full SSRF guard + ToS/legal scope for shared-platform data handling
- [ ] Sandbox ("N free generations in-browser") — a rate-limited instance of Part 2; size decided by spec research (comparable tools' trial limits)

**Dependencies:** AI-029 (shipped — storage/workspace foundation). Part 2 additionally: license model decided, Part 1 shipping, multi-tenant isolation design researched (`RESEARCH_SAAS_AND_LAUNCH.md` §3).

**Estimated sessions:** Part 1: 3-4 · Part 2: 8-12 (isolation dominates)

---

### 14. Phase 7 — CI/CD Integration

**Priority:** Medium-High (deferred)  
**Status:** `[x]` **Complete 2026-08-15** — spec grilled (no open questions) + **7a core + 7a tail + 7b + 7c shipped** (headless driver, fake LLM, ignore list, workspace fix, Docker action + hermetic self-test, generate-and-run, cache, PR comment, slash-commands, verified adaptation, **GitLab parity**). See `docs/ci.md`.
**Spec:** `docs/specs/FEATURE_SPEC_phase7_ci_cd_integration.md` (no open questions remaining)  
**Prerequisite (recorded 2026-08-17):** AI-039 rename must be decided **before first PyPI publish / first launch batch** — the Action owner reference (`<owner>/ai-test-generator@v1`), the PyPI package name, and the repo name are one coordinated decision; publishing under the old name locks it in.  
**Impact:** Enterprise adoption driver — teams don't run tools manually; they want automated test generation in their CI pipeline.  

**What's needed:**
- [x] GitHub Action: `ai-playwright/test-generator@v1` — generate + run tests on PR, post results
- [x] GitLab CI template — same for GitLab users
- [x] PR comment with generated test summary: pass/fail counts, coverage heatmap, flaky test markers
- [x] JUnit XML consumption — AI-028 export feeds this natively
- [x] Configurable: generate-only mode, generate-and-run mode, run-existing mode
- [x] Cache generated tests across CI runs (avoid regenerating unchanged stories)

**Dependencies:** AI-028 (Evidence Export) for JUnit XML; AI-029 (Workspace) for CI workspace isolation.

**Estimated sessions:** 2-3

---

### 15. Phase 8 — GTM Assets

**Priority:** Medium (deferred)  
**Status:** `[~]` In progress — research + domains complete 2026-07-31. **P0 repo/PyPI rename DEFERRED by decision 2026-08-01** — revisit at launch readiness (renaming is disruptive once the package is published). See backlog AI-039.  
**Impact:** Everything customers see before they buy. Landing page, docs, demo, marketplace listings.  

**What's needed:**
- [ ] Public docs site (MkDocs or Docusaurus) — quickstart, API reference, deployment guides, examples
- [ ] Landing page with: product screenshots, feature list, pricing tiers, "Get Started" CTA
- [ ] Demo video (2-3 minutes) — record a real session: story → generate → HTML evidence
- [ ] Interactive sandbox — try the tool in-browser without installing (limited to 3 test generations)
- [ ] AWS Marketplace listing — Docker image / AMI, usage-based billing integration
- [ ] PyPI package — `pip install ai-playwright-generator` (CLI only, free tier)
- [ ] GitHub Marketplace Action listing — thin public `ai-test-generator` repo (`action.yml` + entrypoint + Dockerfile) whose image installs the product from PyPI; requires public repo + semver release tags. Owner reference (`<owner>/ai-test-generator@v1`) is fixed by the AI-039 rename — same launch batch. Spec: `docs/specs/FEATURE_SPEC_phase7_ci_cd_integration.md` §Q4.
- [ ] Case study / testimonial — one real user story to establish credibility

**Dependencies:** Phase 6 (SaaS) for sandbox; AI-028 (Export) for demo footage of evidence viewer.

**Estimated sessions:** 2-3

---

## Tier 6 — Product Expansion (beyond browser E2E)

Long-term directions so the product doesn't become "the web-DOM tester". These
are recorded here (and on the kanban) as planned backlog; none are scheduled
until the mock-site family proves the pipeline generalises across DOM shapes.

**Guardrail for current work:** keep the mid-pipeline layers (discover → resolve
→ emit → execute) as swappable seams rather than welded browser code. When
building each mock in `mock_sites/`, note which layer would change if the
target were an OpenAPI spec or a .NET project.

### FC-02 — API Testing

**Priority:** Future
**Status:** `[ ]` Not started
**Impact:** Opens the tool to backend/test-automation teams; reuses the whole
outer loop (story → conditions → LLM skeleton → evidence → eval harness).

**What transfers (already built):** user-story parsing, condition extraction
(`spec_analyzer`), LLM skeleton generation, evidence tracking, run history,
exports, eval harness.

**What's new:**
- [ ] Discovery: read an OpenAPI/Swagger spec instead of scraping DOM
- [ ] Resolution: endpoint + payload + auth matching instead of locators
- [ ] Executor: httpx/requests instead of Playwright
- [ ] Assertions: status codes, response schemas, headers
- [ ] Mock catalog: add an "API" row — an OpenAPI stub target so the harness
      measures a non-DOM shape (same story→skeleton→evidence loop)

**Estimated sessions:** 1-2

### FC-03 — .NET Testing

**Priority:** Future
**Status:** `[ ]` Not started
**Impact:** Differentiates beyond Python; enterprise .NET shops can generate
tests in their own stack.

**What transfers:** the same outer loop (story → conditions → skeleton →
evidence → eval).

**What's new:**
- [ ] LLM emits C# xUnit/NUnit instead of Python pytest (language seam)
- [ ] Runner: `dotnet test` instead of pytest
- [ ] Evidence: parse trx output or a .NET-side tracker bridge
- [ ] The story→skeleton→evidence loop stays identical

**Estimated sessions:** 2-3

### FC-04 — Dashboard Testing

**Priority:** Future
**Status:** `[ ]` Not started
**Impact:** BI/data teams (Power BI, Tableau, Grafana) — dashboards are web UIs,
so most of the existing browser pipeline applies directly.

**What's new:**
- [ ] Assertion semantics for chart/data values (not just element visibility)
- [ ] Optional API/data-layer verification behind the dashboard
- [ ] Mock catalog: dashboard row (Grafana-style static dashboards with data tables)

**Estimated sessions:** 1-2

---

## Tier 7 — User Documentation & Onboarding

**Priority:** Deferred — gated on the paid/free tier split (Phase 6 SaaS / Phase 8 GTM).
Documentation and option-explanation copy differ between a free consumer tier and a paid
product tier; writing them twice is waste, so this is deliberately **not started** until the
tier split is decided (product naming is already on hold pending launch readiness — decision
2026-08-01, backlog AI-039). Recorded now so the gap stays visible on the kanban.

The product ships with **zero user-facing documentation**: a tester installs, opens the
Streamlit app or CLI, and has to discover what POM mode, consent handling, OCR backends,
workspaces, RAG stats, self-healing, and the export-time fields mean — and which options
exist in which interface.

### UD-01 — "Getting the most out of the product" user guide

**Priority:** Deferred
**Status:** `[ ]` Not started
**Impact:** First-run success + retention — the consumer audience the B-036 work targets
installs once and either "gets it" or churns.

**Deliverables:**
- [ ] A single user-facing guide (docs/ or website): the full pipeline walk
      (story → plan → generate → run → self-heal → export), every option and what it does,
      troubleshooting (LLM empty response, unresolved placeholders, strict-mode, evidence)
- [ ] Option reference table: setting | Streamlit | CLI | default | what it does
- [ ] First-run quickstart for the two personas (UI user / CLI user)

**Scope notes (from the 2026-08-04 consumer-config session):**
- Settings now persist via `~/.ai-test-gen/settings.enc` — the guide must explain what
  persists and how to reset (the UI prune button only clears learned patterns; there is no
  user-facing "reset all settings" lever yet).
- **Streamlit and the CLI genuinely diverge** — inventory during UD:
  - Both: provider/model, consent mode, POM mode, Jira project key
  - Streamlit-only UI: OCR backend selector, workspace field, RAG Store stats + prune
  - CLI-only: `rag_ingest.py --stats / --prune-learned` (power user), interactive repair
  - The CLI cannot currently SET workspace/OCR from the menu (it reads them from the
    store) — either add menu items or document the asymmetry explicitly
- The **model textbox does not auto-update when the provider changes** (Streamlit
  widget-state quirk seen in the Tier-2 walkthrough) — UI-polish item for UD-02.

### UD-02 — Option-explanation UI revisit

**Priority:** Deferred (same gate)
**Status:** `[ ]` Not started
**Impact:** Every widget should answer "what does this do, and what happens if I change it?"
without a docs visit.

**Deliverables:**
- [ ] Audit every sidebar/main widget: does it have `help=` text? is the label
      self-explanatory? (RAG Store stats, workspace, OCR backend, consent modes, POM
      toggle, export mode, Jira key…)
- [ ] Research how comparable tools explain options — Streamlit apps, Playwright/pytest
      tooling, Cypress Studio, Katalon, Testim, Mabl; also LLM-tool UIs. Collect patterns:
      progressive disclosure, inline examples, hover docs vs expanders, "what changed"
      toasts, inline preview of effect
- [ ] Decide one consistent pattern per interface (Streamlit `help=` / CLI inline help /
      `--help` text) and apply it everywhere
- [ ] Surface the Streamlit-vs-CLI difference deliberately (some options are UI-only by
      design — OCR backend is a document-mode setting with no CLI user flow today)

**Estimated sessions:** UD-01: 2-3 · UD-02: 1-2

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
| 10 | Phase 5 Eval Harness | Infra | `[x]` Complete (Dynamic regeneration enabled) | 2-3 |
| 11 | Phase 2 Self-Healing | ML | `[x]` Complete 2026-07-27 | 2-3 |
| 12 | Phase 3 RAG | ML | `[x]` Shipped 2026-07-21 — extended 2026-08-03/04: B-036 consumer config (always-on RAG, bundled golden pack auto-seed, evidence auto-learn, settings store + export-time fields) + AI-035 self-healing write-back — the learning loop is fully closed (generate → execute → fail → self-heal → learn → next generation resolves better). | 3-4 |
| 13 | Phase 1 Multi-Agent | ML | `[x]` Core + doc-mode complete 2026-07-31. All phases (1a-1j): LangGraph core + eval + doc-mode pipeline (PDF/Markdown parsing, change deltas, persona routing, impact mapping, OCR backends, eval dataset). +88 tests, 1900 total. **Per-agent cloud config (Anthropic/Google providers, per-agent model UI, fallback chain) NOT BUILT — dormant scope.** | 3-4 + 3 (doc-mode) |
| 13b | AI-034 Test Table & Pre-flight | ML | `[x]` Complete 2026-08-01. Phases 1-3: `src/test_table.py` (expansion + CRUD), Test Table editors in Streamlit + CLI, LTP "Tests" column, one skeleton per confirmed row. Pre-flight removed from spec (resolver + evidence covers it). UAT: 8 rows → 8 functions 1:1. | 2-3 |
| 14 | Phase 6 SaaS Deployment (TWO-PART — restructured 2026-08-17) | Commercial | `[ ]` Not started. **Part 1 (v1): per-company deployment + BYO-LLM** — customer's infra/LLM/data, team auth on their instance, offline license key, credential policy, no-egress guarantee, SSRF blocklist. **Part 2 (DEFERRED): true multi-tenant SaaS** — our platform, per-tenant isolation of sqlite/RAG/flow stores, S3, sandbox. **Spec: `FEATURE_SPEC_phase6_saas.md` (written 2026-08-17, draft — grill §9).** Research: `RESEARCH_SAAS_AND_LAUNCH.md`. | 7-9 (6a–6i) + 8-12 |
| 15 | Phase 7 CI/CD Integration | Commercial | `[x]` Complete 2026-08-15 (7a + 7b + 7c, one milestone). GitHub Action: headless driver (`scripts/ci_generate.py` + fake-LLM/mock hermetic self-test), three modes (generate-only / generate-and-run / run-existing), idempotent PR comment, `actions/cache` (§7 key), slash-commands (`/adapt` verified adaptation, `/ignore`), verified adaptation engine (locator-only, assertion-gated), Docker action + 39-gate local selftest + GitHub self-test workflow. **GitLab parity (7c)**: `ci/gitlab-ci.template.yml` include template (same three modes + build/compute-key jobs + manual slash job), `ci/platform/gitlab.py` adapter (MR-note comments, PRIVATE-TOKEN, PUT edits, `--latest-command`), protected-environment approvals for the danger zone. See `docs/ci.md`. | 3-4 |
| 15b | Upgrade Path (regenerate old packages) | Commercial | `[ ]` Not started (added 2026-08-17) | 2-3 |
| 16 | Phase 8 GTM Assets | Commercial | `[~]` In progress. Research complete 2026-07-31. Domains acquired; holding co + product name set. **P0 repo/PyPI rename deferred until launch readiness (decision 2026-08-01, backlog AI-039).** | 2-3 |
| 17 | URL-Based Assertions (B-021) | Feature | `[x]` Shipped 2026-07-20 | 1 |
| 18 | State-Dep. Scraping (B-022) | Bug | `[x]` Shipped 2026-07-20 | 1 |
| 19 | Cart Modal (B-023) | Bug | `[x]` Shipped 2026-07-20 | 0.5 |
| 20 | FC-02 API Testing | Expansion | `[ ]` Not started | 1-2 |
| 21 | FC-03 .NET Testing | Expansion | `[ ]` Not started | 2-3 |
| 22 | FC-04 Dashboard Testing | Expansion | `[ ]` Not started | 1-2 |
| 23 | UD-01/02 User Docs & UI Onboarding | Product | `[ ]` Deferred — gated on paid/free tier split (Phase 6/8); see Tier 7 | 3-5 |
| 24 | AI-042 Cross-Site Flow Memory | ML | `[x]` Complete 2026-08-12. `src/flow_memory.py` (learner + store + GOTO/URL-assert consumption), route canonicalization (view_cart/basket→cart, inventory→products — learned analog of url_resolver aliases), 34 tests, seeded from 908 real sidecars → 89 patterns / 6 sites / 5 cross-site. Eval holdout: 0 → 3/4 non-home URL asserts resolvable with target-site evidence excluded. See Tier 4 §16. | 2-3 |
| 25 | AI-043 Output Artifact Quality Gate | Infra | `[x]` Complete 2026-08-11. L1/2 + gates shipped 2026-08-10/11 (`src/artifact_validation.py`, golden fixtures, smoke Gate 0; caught + fixed negative-y bbox bug). L3 shipped 2026-08-11 (`src/heatmap_alignment.py` — live overlay↔page alignment, `validate_report_artifacts.py --full`, 21 tests incl. live mock). See Tier 3 §17. | 2-3 |
| 26 | AI-044 Visual Grounding (vision element location) | ML | `[ ]` **DEFERRED 2026-08-13** — off-the-shelf GUI-grounding models (UGround / OS-Atlas / UI-TARS) cover the core task; AI-041 dependency dead (training failed). Slim AI-044-B (off-the-shelf integration, 1-2 sessions) if wanted. See Tier 4 §18. | 5-8 |

**Total estimated sessions:** 41-60 (+2 for AI-012, +3 for Phase 1 doc-mode, +2-3 for AI-042, +2-3 for AI-043, +5-8 for AI-044)

---

## Session Tracking

Update this section after each session:

| Date | Item Completed | Notes |
|------|---------------|-------|
| 2026-08-24 | **AI-045 #4 — PDF OCR wiring + doc-chunk dedup key** | Two High commercial-readiness gaps (audit §8.2) closed in the production ingest path. **OCR**: `ingest_pdf`/`ingest_pdf_directory` gained a page-scoped `ocr_fallback` hook — image-only pages are sent to the configured OCR backend instead of being silently skipped; `OcrBackend.parse_page` added (UnlimitedOCR rasterises the single page at 300 DPI); `rag_ingest.py --pdfs` consults `get_ocr_backend()`; skipped pages log a WARNING (was silent `info`) when no OCR backend is available. **Dedup**: `DocChunk.dedup_key` = `sha256(source \x00 heading_path \x00 normalised_text)`; `RAGStore.add_docs` returns `(inserted, skipped)` and is idempotent; new `--prune-dupes` CLI flag removes existing duplicate doc rows. 10 new hermetic tests (mocked fitz / fake embedder / in-memory backend, no GPU). Gates: full suite **2750 passed / 1 skipped**, smoke 39/39, ruff + mypy clean (143 files), eval static **97.9% (no regression)**, coverage 69.4% ≥ 65%. Commits `b87426e`…`063a701` (branch `overnight/ai045-4-pdf-ocr-dedup`). Session record: `docs/sessions/2026-08-24_ai045_4_pdf_ocr_dedup.md`. Note: `UnlimitedOCRBackend.parse_page` real GPU path untested (opt-in + GPU-gated by design). |
| 2026-08-23 | **AI-052 shipped (all 6 sessions)** — resolver consumes observed transitions, never guesses | The "wrong-page add-to-cart" class of bug is closed. S1–S3 `2819c0b` (JourneyScraper captures `ObservedTrail`; trail-driven scoping, no all-pages fallback, divergence-aware replay), S4 `9d4c50c` (keyword-URL guessing deleted — evidence-only transitions), S5 `c4685f3` (ARIA role gate in fast passes, penalty-first). **S6 ship gates (2026-08-23):** verify_production both sites — zero different-page locator errors (saucedemo 4P/1F [AI-051]/1S; automationexercise 6/7 [login-gated checkout]); `uat.py --all-sites --run` — automationexercise 12/13 checks, saucedemo 10/13 (3 = designed honest skips + 1 AI-051 execution failure); eval static 97.9% unchanged (A/B 97.9 = 97.9, zero golden regressions); 2735 passed / 1 skipped, smoke 39/39, ruff + mypy clean, CI 9/9 green. UAT evidence: `docs/sessions/uat_ai052_final.json`; records: `docs/sessions/2026-08-23_ai052_session6_ship.md` (+ S1–S5 records). Remaining failures tracked as AI-051 (out of scope) and the login-gated checkout skeleton gap. |
| 2026-08-15 | Phase 7 7c — GitLab parity (milestone complete) | `.gitlab-ci.template.yml` include template (three modes + `ai-testgen:build-image` dind build + `compute-key` dotenv job feeding `cache:key` + manual `slash-command` job with `--latest-command` fetch + protected-env approval gate for the danger zone); `ci/platform/gitlab.py` (MR-note REST: list/find-by-marker/create/PUT-edit, PRIVATE-TOKEN, URL-encoded project paths, injectable base URL, `client_from_env` honoring `CI_*` runner vars + explicit overrides); entrypoint `detect_platform` (explicit `platform` input or `GITLAB_CI` auto-detect) + `post_comment` gitlab branch; `docs/ci.md` (modes, shared-vs-isolated adaptation rule, ignore-list format); selftest 26→39 gates (host-side mock GitLab API: MR note POSTED with §6 shape, PRIVATE-TOKEN header, encoded project path, adapt/ignore replies as notes; cache-hit reuses the GitHub gate's seeded package — no duplicate generation); +14 unit tests (mock GitLab API server). Gates: local selftest 39/39 (~15 min incl. build), full suite 2587 passed / 1 skipped, smoke 38/38, ruff + mypy clean. **Real GitLab.com gate: PASSED 2026-08-15** (14/14 live checks — push pipeline + junit + cache miss, MR §6 note + edited-not-duplicated, cache hit on re-run). Roadmap Phase 7 → `[x]`. | 1 |
| 2026-08-15 | Phase 7 7b — generate-and-run (PR comment, cache, slash-commands, verified adaptation) | `generate-and-run` mode + `action/cache_key.py` (one source of truth for the §7 key) + `ci/platform/github.py` adapter (find-by-marker → edit-not-duplicate) + `action/adapt.py` verified adaptation engine + `action/flaky_history.py` + `scripts/ci_slash_commands.py` + `ci-slash-commands.yml` + selftest 25→26 gates w/ host-side mock GitHub API. 2571 passed / 1 skipped, both GitHub workflows green on dbf1d67. | 1 |
| 2026-08-13 | Phase 7 CI/CD — spec + 7a core | Spec drafted + fully grilled (referee default, verified adaptation post-failure, `.ai-test-ignore.yml` with required-reason anti-rug rule, danger-zone Option C, two-stage Action repo, trigger scope, GitLab parity in 7c). **7a core shipped**: `scripts/ci_generate.py` headless driver (exit codes 0/1/2, `--json`, workspace isolation, danger-zone allow-list), `scripts/fake_llm.py` (OpenAI-compatible, per-condition fragment routing — the production path generates one skeleton per condition), `src/ci_ignore.py`, 28 tests (incl. 1 slow-lane E2E: fake LLM + ecommerce mock → 8 tests, workspace-isolated). **Found + fixed**: `PipelineArtifactWriter` hardcoded `generated_tests` default silently bypassed AI-029 workspaces — now storage-aware. Gates: 2510 passed, smoke 38/38, eval static 97.9%. 7a tail (Docker action + self-test workflow), 7b, 7c pending. **AI-044 deferred** (off-the-shelf GUI grounding covers the task; AI-041 failed). |
| 2026-08-12 | Testing hardening | Coverage gate in CI (`--cov-fail-under=65`, measured 67%). ASSERT flow-fallback tests uncovered a real gap: the sequential B-021 page-state ASSERT branch never used flow memory (URL asserts couldn't be flow-rescued in the real pipeline) — fixed by mirroring the flow fallback into the sequential path. Script-hook static guards for verify_production/synthesize_stories chaining. Learning-loop E2E added to BACKLOG (non-roadmap). 4 new tests (2482 total). |
| 2026-08-12 | AI-042-F3 + F2 (follow-up series complete) | **F3 cross-test flow chaining**: `chain_suite_transitions()` + `learn_suite_flows()` (adjacent passing tests → GOTO transitions; same-site guard, home/no-movement dropped, pre-B-033 value fallback); `FlowPattern.source` split; wired into all run paths (synthesize_stories, `PipelineRunService.run_saved_test` UI+CLI, verify_production). 24 new chains (89→113 patterns, cross-site 5→8); holdout strict cross-site 1/11→2/11. **F2 sidebar**: `SidebarConfig._render_flow_memory()` — Flow Memory stats (patterns/sites/cross-site/suite chains) + two-step prune (`FlowMemoryStore.clear()`), parity with RAG Learned Patterns; `format_flow_stats_summary` helper + 2 stubbed-UI tests. 17 new tests (2477 total). F4 remains deferred (prompt regeneration sensitivity). |
| 2026-08-12 | AI-042 session 2 — eval holdout + route canonicalization | **Measurement**: `scripts/eval/flow_holdout_eval.py` — for each eval dataset's URL-assert/GOTO goldens, checks flow resolution with holdout integrity (target site hash excluded) + from-context reachability (site's known URLs contain the flow's from-route). Finding: without canonicalization 0/7 holdout+context; cross-site flows only transfer when sites share route vocabulary (saucedemo cart.html vs automationexercise view_cart). **Fix**: `_ROUTE_ALIASES` in `normalize_route` (view_cart/basket/shopping_cart→cart, inventory→products, signin/sign-in/auth→login; exact whole-route match only — checkout-step-one/-two stay distinct). Re-seed 908 sidecars → 89 patterns / 5 cross-site (was 64/4). **Result: 0 → 3/4 non-home URL asserts holdout-resolvable with context** (automationexercise products/cart via saucedemo+mock flows; ecommerce cart strict cross-site 2 sites). End-to-end verified: `flow_resolved_url` returns view_cart/products for automationexercise from non-target flows only. Caveats documented: 3 home targets = seed-fallback scope; ecommerce checkout co-verified on target port; no GOTO goldens in datasets. 34 tests, ruff/mypy clean. |
| 2026-08-12 | AI-042 session 1 — flow learner + store + consumption | **Shipped**: `src/flow_memory.py` — `normalize_route` (URL→route keyword, no raw URLs), `flow_transitions` (passed-only, same-page dropped, per-step site identity), `FlowMemoryStore` (JSON, atomic, dedup + site diversity + `min_sites` guardrail), `flow_resolved_url` consumption hook wired as step 2.5 in the GOTO/URL chain + page-state ASSERT fallback (site evidence always wins — runs after UrlResolver/resolve_url). Wired learning into `generated_tests/conftest.py` teardown + `synthesize_stories.py` sweep; `FLOW_MEMORY_ENABLED=0` hermetic gate in tests. 33 tests; seeded from 908 real sidecars → 64 patterns/6 sites/4 cross-site (home→cart, home→checkout). ruff/mypy clean; 125 orchestrator tests + 171 URL-assertion tests pass. **Next**: eval holdout measurement (unseen-site first-pass vs today). |
| 2026-08-11 | AI-043 Layer 3 (heatmap alignment) + doc audit | **Layer 3 shipped**: `src/heatmap_alignment.py` — render suite heatmap, open live page, assert every overlay box centre hits its claimed element (`elementFromPoint` + containment in one locator-scoped evaluate; live doc-size mapping catches wrong-frame drift, `missing/hidden` catches stale locators). `scripts/validate_report_artifacts.py --full` browser gate; 18 offline unit tests + 3 live tests (real chromium vs ecommerce mock, real tracker metadata math). Verified: ruff/mypy clean, smoke 38/38, no-live-network guard passes. **Doc audit**: AI-034 stale boxes ticked; Phase 1 checklist split done vs NOT BUILT (dormant scope); BACKLOG Phase 4 Export TODO cleared. |
| 2026-06-03 | Plan created | Cross-referenced against actual project state |
| 2026-06-04 | B-014 ASSERT resolution | Shipped intent-aware scoring: _assert_action_penalty, _assert_message_bonus, _is_message_like_assertion. SuccessAssertStrategy requires BOTH success+message keywords. 42 tests, 1043 pass. |
| 2026-06-04 | B-015 Journey element selection | Shipped unified scoring: _discover_selector() delegates to PlaceholderScorer.compute_element_score(). Eliminated dual-ranking pipeline. 60 journey tests, 1015 total pass. |
| 2026-06-04 | AI-010 POM Toggle (design) | Design session complete. Spec: FEATURE_SPEC_AI010_pom_toggle.md. Two modes (Simple/POM) via GenerationMode enum. Phase 1: Simple-to-POM conversion + POMWriter. Phase 2: UI/CLI toggle + pipeline wiring. Phase 3: Evidence tracker integration. 17 tests planned. Zero protected file changes. |
| 2026-06-09 | AI-010 Phases 1-3 | Shipped evidence-aware POM builder (Phase 1), POM mode in PlaceholderOrchestrator (Phase 2), pipeline configuration wiring (Phase 3). 26 unit tests. `pom_mode` flows: TestOrchestrator → PlaceholderOrchestrator → PageObjectBuilder → PipelineArtifactSet → package_manifest.json. 1107 tests pass. |
| 2026-06-09 | AI-010 Phase 4 (UI Toggle) | Shipped Streamlit sidebar toggle (`ui_renderers.py`), `pom_mode` in `st.session_state` → `streamlit_app.py` → `ui_pipeline.run_pipeline()`. CLI: `pom_mode` in `Session` dataclass, "POM Mode" menu item in `cli/main.py` with colored feedback, forwarded via `cli/pipeline_runner.py`. ruff clean, mypy clean, 1107 tests pass. Phase 5 (export stripping) remains. |
| 2026-06-10 | AI-010 Phase 5 (Export Stripping) | Shipped `_strip_evidence_from_pom()` in `src/code_postprocessor.py`. Converts evidence-aware POM to clean POM: strips EvidenceTracker import, replaces tracker.click/fill/navigate/assert_visible/get_text/select with page.locator equivalents, adds expect() imports for assertions. 18 unit tests in `tests/test_code_postprocessor_pom_export.py`. ruff clean, mypy clean, 1125 passed, 1 skipped. AI-010 feature complete. |
| 2026-08-10/11 | B-047 residuals + AI-041 (failed) + AI-043 L1/2 | Golden +20 site-scoped (site_hash seeded/stored/enforced + output_fields round-trip fix); RAG learning lock fixed via parent-side sidecar sweep; AI-043 Layer 1+2 shipped (artifact validation module + CLI + golden fixtures + smoke wiring, caught real negative-y bug fixed in evidence_tracker); baseline comparison tool; **AI-041 closed FAILED** (27B trained loss 0.08, GGUF export physically impossible — 16-bit merge walls; see field guide); AI-042/043/044 roadmap items added. 2402 tests pass. |
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
| 2026-07-22 | AI-030 LV Insurance mock site + Ingestion Agent research | Built 7-step LV car insurance quote flow mock site (60KB HTML, 8 regs, premium calc, decline path). Assembled 7-document rag_corpus (3 real LV PDFs + 3 redacted + synthetic underwriting guide). Created eval-005 dataset (10 criteria, 33 placeholders). Researched PDF parsing options (Docling vs PyMuPDF vs Unstructured) and multi-agent vs linear ingestion trade-offs. Phase 1 agent split refined: Synthesizer (dense) + Resolver (MoE) + Ingester (PDF parsing). Eval harness updated (81.4% across 5 stories). |
| 2026-07-26 | AI-030 Ingestion Agent complete | Shipped PDF ingestion: `src/pdf_ingest.py` (PyMuPDF) wired into `rag_ingest.py --pdfs`. 3 LV Insurance policy PDFs ingested → 66 chunks in RAG store (160 total). RAG accuracy 53.7 → 64.2% (+10.5pp), LV Insurance 83.3 → 91.7%. Updated BACKLOG.md (B-027 + AI-030 → Complete), AGENTS.md (backlog sync rule), ship-it SKILL.md (status update step). Installed PyMuPDF dependency. |
| 2026-07-26 | Phase 2 Self-Healing Phase 2b complete | Shipped rule-based pre-screening (`_pre_screen_failure()` skips LLM for assertion/navigation/other failures — cost optimization). Shipped interactive repair fallback (`interactive_repair_candidates` in HealingReport connects auto-heal → interactive repair flow). 18 new tests (46 total). Fixed roadmap checkbox hygiene (AI-028, AI-029, Phase 3 RAG, B-021, Phase 5 dataset expansion). Marked dual-tier eval as `[R]` removed. |
| 2026-07-30 | Pipeline Performance (batching + parallelization) | Shipped ASSERT Pass 3 batching: deferred ASSERTs collected per journey, batch-resolved via `find_best_elements_batch()` in one LLM call instead of N. Resolution phase: 42s → 26s (−38%). Shipped journey discovery parallelization: journeys run concurrently via `asyncio.gather()`, each with own `JourneyScraper`. Discovery phase: 34s → 12s (−65%). Combined pipeline time halved: ~110s → ~51s. Shipped eval DB persistence with pipeline tracking (linear/graph, regenerated/captured, git_commit). Fixed pre-commit mypy version v1.15.0 → v2.3.0. 1788 tests pass, static eval 100%. |
| 2026-07-30 | Phase 1d self-consistency (temperature=0) | Added `temperature` parameter to `LLMProvider.complete()` ABC + all 3 implementations (OpenAI, LMStudio, Ollama). Threaded through `LLMClient._complete_sync()` → `generate()`. Pinned Planner+Generator at `temperature=0`. Skeleton self-consistency: 55.6% → 100% (byte-for-byte identical across runs). 1788 tests pass, static eval 100%, ruff/mypy clean. |
| 2026-07-31 | Phase 1f-1j doc-mode (complete) | Shipped all 5 doc-mode phases: state schema + PDF/markdown parsing node (1f, 20 tests), change delta extraction with heading fallback (1g, 21 tests), persona routing + impact mapping + consolidated report (1h, 24 tests), OCR backend adapter with PyMuPDF + Unlimited OCR support (1i, 15 tests), eval dataset with 3 spec documents + quality gate at ≥90% heading accuracy (1j, 8 tests). +88 total, 1900 passed. Also shipped: journey URL inference fix for saucedemo checkout pages (Phase 1d), mock server stability via ThreadingHTTPServer (Phase 1d), AI-037 LV Insurance gap spec, AI-038 Unlimited OCR AMD test backlog item. |
| 2026-07-31 | Commercial research + domains | Researched Phase 6-8 (SaaS, CI/CD, GTM). Acquired domains: tancat.dev (product, £11/yr), cattanooperations.co.uk + .com (holding company). Renamed product to TanCat, holding company Cat Tan Operations Ltd. Updated AI-034 spec (stripped pre-flight, focus on test table expansion). |
| 2026-07-31 | t-string PromptBuilder + AI-037 diagnostic | Shipped PEP 750 t-string prompt assembly (`src/prompt_builder.py`): structured rendering (trusted static vs untrusted fields), per-field truncation, `to_log_entry()` audit trail. Wired into `TestGenerator._generate_skeleton_single_call` + `Orchestrator._generate_single_condition_fragment` — byte-identical prompts to legacy `.format()` (UAT-verified, 2886 chars). Fixed latent single-condition prompt inconsistency (literal `{{CLICK:...}}` → `{CLICK:...}`). AI-033 resolved (Jinja2 double-brace blocker disproven — t-strings escape `{{`). AI-037 diagnostic: resolver 23/24 (95.8%); 54% regeneration gap = LLM skeleton nondeterminism, not vocabulary — no vocab list needed. 13 new tests, 1913 total, static eval 100%. |
| 2026-07-31 | AI-037 resolver fixes (Phase 1-2) | Shipped 10 structural resolver/scraper fixes: radio label capture, clickable-div-with-id capture (`#productCar`), `<strong>` display capture, synthetic-ARIA marker, radio `input[name][value]` locator format, quote-agnostic locator normalisation, camelCase in `get_words()`, Pass 1 synthetic skip, radio CLICK bonus + synthetic container exclusion, proportional text-content bonus. LV Insurance resolver 23/24 → **24/24 (100%)**; overall resolver 58.2% → 59.7%; regeneration UAT LV 54% → **62.5%**, overall 56.7%. 15 new tests (1928 total). `scripts/eval/refresh_lv_capture.py` reproduces frozen eval data in journey state. Next: AI-037 Phase 3 (skeleton journey-structure guidance) — handover `docs/sessions/2026-07-31_ai037_resolver_fixes.md`. |
| 2026-08-01 | B-028 fixed — journey discovery picks the cart link for product/add-to-cart | **B-028 FIXED + follow-ups shipped**: root cause = discovery passed lowercase actions to the scorer (all action bonuses silently disabled) + hidden-modal penalty crushing real candidates + hallucinated POM locators + non-fillable quantity inputs + missing `tag` field. Fixes: action normalisation, visibility-aware modal penalty, product/category/dismiss context hints, DOM-existence index in generated POMs (`_ELEMENTS`), hidden-element exclusion, `_is_fillable` aligned with IntentMatcher, FILL-quantity stepper fallback, batch fallback searches all scraped pages, EvidenceTracker fast-fail (148s→0.0s) + proactive overlay dismissal, LLM `max_tokens` cap (4096), per-test pytest `--timeout=120`, structural assembler (`src/test_structure_assembler.py`, t-string shells — module-level leaks structurally impossible). Journey reaches product pages + non-empty cart; verify_production execution completes ~65-75s (was 600s timeout), 12/13 gates. Full eval live-regenerate 53.7% → **65.7%**; static 100% unchanged. 2030 tests, ruff/mypy clean. |
| 2026-08-01 | AI-034 Test Table (Phases 1-3) + B-027 re-fix + UI fixes | **AI-034 COMPLETE**: `src/test_table.py` (TestRow/TestTable/CRUD, TestTableExpander with fallback + cap, table_to_conditions), Test Table editors in Streamlit + CLI, LTP "Tests" column, one skeleton per confirmed row. 33 tests + UAT (8 rows → 8 functions 1:1, real LLM). **B-027 re-fixed properly**: naive comma-splitter had been reverted; added SPLITTING RULES prompt, numbered-wrap routing, JSON retry-once + salvage gate, sentence-boundary fallback. Verified: 1 story → 3 conditions. **UI fixes**: `PIPELINE_TEST_TIMEOUT` 300s→600s; run-tests errors now inline in Run section (`run_tests_error`) instead of off-screen `pipeline_error`. **B-028 logged** (journey discovery picks cart link for product/add-to-cart — evidence in BACKLOG). **LangGraph dormant state documented** (graph not wired into user flow; CI skips its tests). AI-039 rename deferred to launch readiness. 1998 tests, static eval 100%. |
| 2026-08-02 | CLI walkthrough + zero-pass pipeline | Shipped `scripts/cli_walkthrough.py` (all CLI buttons: NAV 41/41, FULL 59/59), fixed CLI Load-Existing crash (PermissionError), CLI POM/Consent invisible toggles, and 5 mechanical pipeline bugs (POM selector drop → runtime skips, OneTrust consent pollution, URL trailing-slash, FILL container-div match, evidence-tracker post-navigation hang) + verify_production timeout message/salvage. verify_production 20/26 → 22/26 gates; 2042 tests pass. **Open: the semantic layer** — dialog-role scoping, assertion-state polarity, heading-role asserts, upstream skeleton phrasing for load-conditions ("assert home page title" is an LLM invention; golden key expects `to_have_url`), LLM re-ranking w/ T-strings + bounded retries. Do NOT add site-specific lists — match playwright.dev's ARIA-role vocabulary. See `docs/sessions/2026-08-02_cli_walkthrough_and_zero_pass_pipeline_fixes.md`. |
| 2026-08-03 | Export gate + product expansion tier | Shipped B-031/B-032 (runnable, validated exports — `scripts/export_gate.py`, golden fixture, stub guard, decorator/assert-family stripping, `run_results.sqlite` copy), offline-suite guard test, eval-static CI job, sanitizer `fixtures/` skip. Added **Tier 6 — Product Expansion** (FC-02 API, FC-03 .NET, FC-04 dashboard testing) so the product has an explicit beyond-browser direction; kanban now shows them as planned backlog. See `docs/sessions/2026-08-03_export_gate_and_broken_exports.md`. |

1. **One item per session** — per AGENTS.md §10
2. **Design session first** for B-014 and any item marked "Needs design session"
3. **ruff → mypy → pytest → commit** before marking any item complete
4. **Update this doc** at end of each session with completion status
5. **Update memory bank** with new decisions/patterns discovered
6. **Do not skip the eval harness** (Phase 5) — build it before Phase 2/3/4 so regressions are caught
| 2026-08-04 | Consumer config (B-036 Phase 4) + self-learning RAG (AI-035) + Tier-1/Tier-2 verification | **B-036 Phase 4**: `src/settings_store.py` (Fernet-encrypted `~/.ai-test-gen/settings.enc`, secure_config pattern) — migrated pom_mode/consent/provider/model/workspace (Streamlit sidebar + CLI Session seeding, settings win over env); `JIRA_PROJECT_KEY` env read removed → export-time field; `OCR_BACKEND` → persisted setting (env fallback); `LANGGRAPH_ENABLED` removed; Streamlit "Learned Patterns" section folded in. **AI-035 write-back**: `pattern_from_patch`/`learn_from_patch` (`source=self_healing`, `confidence=1.0`), description from the evidence sidecar, guarded hook in `SelfHealingRunner`, `HealingReport.learned` in CLI+UI. **Live verification**: eval-006 regenerate + execute 8/8; forced locator failure → heal → `fixed:1 learned:1 remaining:0`, store row `CLICK 'Cart link' → a[href="/cart.html"]` (self_healing, conf 1.0), dedup verified. Surfaced + fixed **B-039** (pytest parser dropped `[chromium]` failure headers → error_message always empty; classifier missed the evidence-tracker fast-fail — self-healing was blind to real failures) and the last migration gap (UI now persists base URL + model). 2263 tests; eval static 95.2%. See `docs/sessions/2026-08-04_consumer_config_and_self_learning_rag.md`. |

---

*Last updated: 2026-08-23*
| 2026-08-02 | Semantic layer (page-load, dialog scoping, polarity) + CLI quality + eval harness gap | **Page-load assertions**: "title" no longer vetoes page-state routing (`<page> page title` → `to_have_url`, matches golden encoding); `resolve_url` root-path substring bug (multi-word descriptions no longer collapse to home URL); golden validator `to_have_url` trailing-slash-insensitive; skeleton prompts steer load-conditions to `{{ASSERT:<page> loaded}}`. **Dialog-action scoping (Pass D)**: `{{CLICK:OK}}` no longer picks the hidden CSRF input ("ok" inside "csrfmiddlewareTOKen" short-circuited the fast path at flat 100); CLICK fast-path + pass-2 hygiene + in-modal structural scope (ARIA-based, no site lists). **Polarity**: "popup closed"/"item removed" → `assert_hidden` (was `assert_visible`). **CLI quality (found by running the real CLI — full walkthrough)**: table truncation fixed (wrap to terminal width), `[llm_client]`/`[pipeline]` debug → stderr, export `story_slug` AttributeError, export "Tests: 0" (file→dir path), flat export POM→Playwright conversion; walkthrough gained `reject:` checks. **Eval harness gap**: full-regenerate now persists test files and executes — 33 tests / 17 passed (51.5%). Full-regenerate resolution 65.7-67.2% (best in DB); static 100%; 2081 tests; CLI walkthrough NAV 41/41 + FULL 60/60. **Open next**: LLM re-ranking (T-strings + bounded retries), saucedemo checkout scrape coverage, lv_insurance form-field resolution, consent in exported clean tests. See `docs/sessions/2026-08-02_semantic_layer_and_cli_quality.md`. |
| 2026-08-03 | Saucedemo checkout cluster (13/13 gates PASS) | **Root cause stack**: saucedemo is SPA-on-GitHub-Pages (all `.html` paths = HTTP 404 + app shell, scraper bailed on `status>=400`); credentials never reached the pipeline (login wall → empty cart → no checkout); stateful routing hardcoded to automationexercise paths; URL guessing removed (SPA has no hrefs); B-015 ghost in modal dismissal (clicked saucedemo's cart "Continue Shopping", navigating back to inventory); journey subprocess dropped credentials; dead/redirected candidate pages won resolution; B-024 placeholder-only fields. **Fixes**: soft-404 recovery (`_is_soft_404`), env-overridable saucedemo credentials in verify_production, site-agnostic `is_stateful_cart_checkout_path`, concept-driven same-domain URL candidates re-enabled, credential round-trip + journey login, modal-scoped dismissal (3 places) + modal-close no-op, dead-page + redirect-duplicate filters, placeholder in `normalise_element_text` + B-024g word-subset, navigation-intent GOTO fallback, post-login ASSERT mapping. **Results**: verify_production saucedemo 10/13 → **13/13, 6/6 tests, stable ×4**; automationexercise 3/7 (HEAD) → 4–5/7 (no regression); 2095 tests; static eval 100%. **Open**: automationexercise guest-checkout login gate, cart-link/assert timing races. See `docs/sessions/2026-08-03_saucedemo_checkout_cluster.md`. |
