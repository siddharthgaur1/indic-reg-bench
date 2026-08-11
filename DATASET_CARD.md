---
license: apache-2.0
language: [en]
tags: [legal, regulatory, india, sebi, information-extraction, benchmark]
pretty_name: indic-reg-bench
---

# Dataset Card — indic-reg-bench

**Status: under construction. The gold set does not exist yet.** This card describes what is built, what is not, and the decisions taken so far. It will be wrong in places until labelling is finished; it is published early so the construction method is auditable rather than reconstructed afterwards.

## What this is

A benchmark for Indian regulatory document understanding, built on SEBI (Securities and Exchange Board of India) enforcement orders. Five tasks: structured extraction, charging-section prediction, numeric reasoning, abstention, and penalty attribution. See `docs/phase1-task-design.md`.

## What is actually in it right now

| Component | State |
|---|---|
| Listing metadata | 11,957 orders, Nov 2004 – Jul 2026, scraped from sebi.gov.in |
| Benchmark sample | 2,000 orders, stratified by year, seed 42 |
| Fetched document text | **1,986 of 2,000 fetched; 2,006 documents total, 69,979,073 chars** |
| Effective corpus date range | **2008 – 2026** (see note below) |
| Gold labels | **none — 0 examples** |
| Silver labels | none |
| Splits | temporal, defined (train <2023 / test ≥2023); not yet populated |
| Harness | working, pip-installable, 72 tests passing |
| Baselines | regex floor and a local-LLM baseline implemented and runnable; **no scores, because scoring needs gold labels** |

**On the date range.** The listing index spans Nov 2004 – Jul 2026, but the
*corpus* effectively starts in 2008: SEBI's own listing contains only **7
adjudication orders before 2008** (one in 2004, four in 2005, none in 2006, two
in 2007), against 90 in 2008 alone. Treat this as a 2008–2026 benchmark. The
remaining 8 unfetched sample orders are transient connection failures and are
recoverable by re-running the fetch script.

**Known extraction properties**, measured over the full corpus and documented in
`docs/corpus-findings.md` — these matter to anyone building against it:

| | |
|---|---|
| First currency amount ≠ the operative one | **48.6%** of comparable orders |
| Orders imposing no monetary penalty | 18.3% |
| Single-noticee orders with >1 penalty | 13.4% |
| Rupee sign extracted as U+0060 backtick | 25% of orders; the *only* currency marker in 10.4% |
| No text layer (scanned PDFs) | 2.4%, concentrated in 2014–2015 |
| Corrigenda mixed into the adjudication listing | 21 orders |

## Provenance

Source: `https://www.sebi.gov.in/enforcement/orders/...`, the public enforcement-orders section. Listing metadata is collected via the site's own AJAX paging endpoint; each order's PDF is resolved from the viewer iframe on its page and text-extracted with pdfplumber.

Documents were retrieved between 2026-08-05 and 2026-08-08; each row's `fetched_at` carries its own timestamp. SEBI may revise or withdraw orders; a SHA-256 per document is planned so drift is detectable.

sebi.gov.in drops connections frequently, so both scrapers are resumable and a full fetch of the 2,000-order sample takes a few hours. Re-running the script skips what is already stored.

## Redistribution and licence

**The source order text is not redistributed.** This repository ships document IDs, source URLs, and a fetch script. Anyone can rebuild the corpus from SEBI's servers with one command.

This is a deliberately conservative position. SEBI orders are public documents and Indian copyright law treats government works distinctly, but rather than assert a redistribution right I am not qualified to assert, the benchmark keeps SEBI as the authoritative source. The **harness, scorers and labels** are Apache-2.0; the **order text** is SEBI's and is not covered by that licence.

Cost of this choice: reproducibility depends on SEBI keeping URLs live, and a fetch takes hours. That is a real downside and it is accepted knowingly.

## Personal data

SEBI enforcement orders name private individuals and contain, variously, addresses, PAN references, trading account details, and family relationships. The pilot sample includes three orders concerning **deceased persons** (`Late Ms. Anju Rani`, `Late Padma Singhwani`, `Late Sudha V Thakkar`), where proceedings continue against legal heirs who are themselves named.

Consequences, stated plainly:

- Noticee names are the *labels* for T1. A version with names removed would not be a usable extraction benchmark.
- The current intention is to publish names, since they are already public in the source documents. **This decision is not yet final** and is flagged for the maintainer.
- No attempt is made to enrich, cross-reference, or link these individuals to any other dataset, and doing so is out of scope.
- A takedown contact will be published before any HuggingFace release.

This dataset must not be used to profile, score, or make decisions about the named individuals. It exists to measure document-understanding systems.

## Known biases and limitations

- **One regulator, one document type.** SEBI adjudication orders only. Not RBI, not IRDAI, not tribunal judgments. Results do not generalise to Indian regulatory text broadly.
- **Extraction-heavy.** Four of five tasks reward locating and normalising text. Legal reasoning is barely tested.
- **Single annotator.** Agreement will be reported as self-agreement across two passes a week apart. That is an upper bound on reliability: the same reader reproduces their own systematic misreadings and scores them as agreement.
- **English only.** SEBI publishes in English; Indian-language regulatory text is untested.
- **Class imbalance.** Charging sections are dominated by `15HB`; the pilot shows 27 mentions of `15HB` against 16 of `15HA` and 8–9 each of `15EA`/`15EB`. Macro-F1 and a published majority-class baseline are used for this reason.
- **Multi-noticee orders are rare** — 3 of 25 in the pilot. They are the interesting case, so the sample deliberately oversamples them; the resulting distribution is *not* representative of SEBI's output and must not be read as such.
- **Multi-hop is absent from v1.** Only 9 of 133 entities in the pilot recur across documents, and all 9 come from a single matter family. The task was cut rather than shipped degenerate.
- **OCR/extraction noise is real.** Penalty tables are column-scrambled by text extraction; the annotation guidelines require labelling such orders from the source PDF.

## What this benchmark does not measure

Legal correctness. Whether SEBI's reasoning is sound, whether a penalty is proportionate, or whether an order would survive appeal. It measures whether a system can read what an order says.

## Construction method

1. Scrape listing metadata for all 11,957 orders (`scripts/scrape_listing.py`).
2. Select a stratified sample by year, adjudication orders only, seed 42 (`scripts/build_splits.py`).
3. Fetch and text-extract (`scripts/fetch_orders.py`).
4. Hand-label the gold set with `scripts/label.py`, logging every decision to `labels/decisions.jsonl`.
5. Re-label 50 orders after ≥7 days; report self-agreement (`scripts/agreement.py`).
6. Cut temporal splits; run baselines; publish per-task results and a failure taxonomy.

Steps 1–3 are built. Step 4 onward is not started.

## Citation

```bibtex
@misc{indicregbench2026,
  title  = {indic-reg-bench: A Benchmark for Indian Regulatory Document Understanding},
  author = {Gaur, Siddharth},
  year   = {2026},
  url    = {https://github.com/siddharthgaur1/indic-reg-bench}
}
```
