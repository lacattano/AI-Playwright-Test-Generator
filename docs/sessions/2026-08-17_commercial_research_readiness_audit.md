# 2026-08-17 — Competitive research, commercialisation decisions, and readiness audit

**Docs produced/updated:**
- `docs/plans/RESEARCH_COMPETITIVE_LANDSCAPE.md` (new) — market size, competitor landscape, pricing benchmarks, positioning, business-plan skeleton, open-core-vs-donations decision (§4.4), cross-reference map (§9).
- `docs/plans/RESEARCH_SAAS_AND_LAUNCH.md` — §5 pricing + free-tier + §1 cost-analysis questions now **answered** by market research; "what phones home" escalated to priority; new **§8 commercial-readiness gap audit** (from code reading, not guesses).
- `BACKLOG.md` — **AI-045** added (7-item priority list for Phase 6); kanban.html regenerated.

## What the research concluded (summary)

1. **Market is real**: AI test automation ≈ $8.6–8.8B in 2025, 19–22% CAGR → $35–42B by early 2030s. Capital still flowing (Qodo $70M Series B Mar-2026; Functionize $41M Aug-2025; Testim exited $200M).
2. **The wedge is air-gap/on-prem**: every competitor (testRigor, Mabl, QA Wolf, Functionize, Keploy) is cloud SaaS. **Nobody sells BYO-LLM test generation** — that's the whitespace, and it maps to the insurance/regulated-domain focus already in the codebase.
3. **Revenue model decision: open-core, NOT donations** (recorded in §4.4) — donations poison the compliance pitch; every funded winner is open-core/paid.
4. **Pricing answered**: per-deployment, not per-seat ($99–149 self-serve / $299–499 pro / $1–3k air-gap premium). Free tier = runs/credits framing, NOT "3 generations".
5. **The #1 sales argument is "no data leaves your deployment"** — which is why the SSRF guard + egress audit is priority #1 in AI-045.

## What the code audit found (AI-045, in priority order)

1. **SSRF guard + egress audit** — no private-IP / `169.254.169.254` blocklist exists anywhere; the v1 "warning + cheap blocklist" was promised but never built. Gates the sales claim.
2. **Embedding model stamp + reindex** — `SentenceTransformerEmbedder` model/dim (384) hardcoded; Milvus collection schema fixed at creation; no embedder identity in the store, no `--reindex`. Model change today = silent retrieval corruption.
3. **Team-deployment concurrency** — Milvus Lite is single-writer; D2 team shape risks concurrent writes.
4. **PDF OCR** — image-only pages skipped (scanned insurance PDFs yield nothing); `src/ocr_backends.py` exists but isn't wired in.
5. **Screenshot credential redaction** — unverified whether `fill()`'d password fields are masked.
6. **Latency** — no published E2E number, no SLO, no LLM-call cache.
7. **Multi-site eval dataset** — baseline is 100% but on one site (saucedemo); needs automationexercise + LV mock goldens.

## Open work (next session)

**Kickoff recommendation — ONE feature per session (AGENTS.md rule): write the Phase 6 spec, with the SSRF guard as the first thing it specs.**

The Phase 6 build is gated on `docs/specs/FEATURE_SPEC_phase6_saas.md` (NOT WRITTEN). The prerequisite questions it needed are now answered: BYO-LLM architecture (§1), pricing + free-tier (§5 → answered 2026-08-17), license key design, credential policy (§4), and the readiness gaps (new §8 / AI-045). Suggested session scope:

- **Primary:** `FEATURE_SPEC_phase6_saas.md` — spec Part 1 (per-company deployment) with: BYO-LLM health check, offline signed license key, per-deployment pricing tiers, runs/credits free tier, **SSRF guard** (private-IP + `169.254.169.254` metadata blocklist + URL-scheme restriction), credential policy, and the §8.7 priority list folded in as the build order.
- **Fallback (if spec is too big for one session):** build the **SSRF guard** alone — it's AI-045 #1, small, testable (unit tests + mock-site regression), and it unblocks the "no data leaves your deployment" claim that the whole pitch rests on. Update `src/url_utils.py`/scraper entry points, add the blocklist to config, wire it into the scrape path, verify with `verify_production.py` + `smoke.py`.
- **Do NOT** start multi-tenant (D3), pricing plumbing, or the rename in the same session.

**Also queued (not for this next session):** the air-gap wedge needs validation from 3–5 real buyer conversations (insurer/fintech QA leads) — the highest-value human unknown, from RESEARCH_COMPETITIVE_LANDSCAPE.md §8.
