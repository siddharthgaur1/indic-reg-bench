# indic-reg-bench

An open benchmark for Indian regulatory document understanding, built on SEBI enforcement orders.

**Status: Phase 1 — task design. No dataset, no labels, no scores yet.**

Every LLM evaluation suite for regulatory and financial documents is US/EU-centric: SEC filings, EDGAR, EU regulatory text. Indian regulatory language differs structurally — SEBI order formatting, charging provisions under the SEBI Act and the PFUTP/PIT regulations, Indian digit grouping (lakh/crore), and penalty phrasing that matches no Western template.

## Read this first

[`docs/phase1-task-design.md`](docs/phase1-task-design.md) — the proposed five-task suite, the evidence from 25 real orders behind each decision, which proposed tasks were cut and why, and the legal position.

## Source documents are not redistributed here

This repo distributes document IDs, source URLs, and a fetch script — not raw SEBI order text. Rebuild the corpus from SEBI's servers:

```bash
pip install -r requirements.txt
python scripts/fetch_orders.py --limit 25
```

Rate-limited to 1.5 s/request and resumable. See §5 of the Phase 1 document for the reasoning.

## Not yet built

Harness, adapters, baselines, leaderboard, dataset card. See §7 of the Phase 1 document for the critical path — the corpus, not the labelling, is the long pole.
