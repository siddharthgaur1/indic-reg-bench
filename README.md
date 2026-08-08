# indic-reg-bench

An open benchmark for Indian regulatory document understanding, built on SEBI enforcement orders.

[![tests](https://github.com/siddharthgaur1/indic-reg-bench/actions/workflows/tests.yml/badge.svg)](https://github.com/siddharthgaur1/indic-reg-bench/actions/workflows/tests.yml)
[![dataset](https://img.shields.io/badge/%F0%9F%A4%97%20dataset-indic--reg--bench-yellow)](https://huggingface.co/datasets/siddharthgaur/indic-reg-bench)
[![license](https://img.shields.io/badge/license-Apache--2.0-blue)](LICENSE)
[![status](https://img.shields.io/badge/status-under%20construction-orange)](#status)

Every LLM evaluation suite for regulatory and financial documents is US/EU-centric: SEC filings, EDGAR, EU regulatory text. Indian regulatory language differs structurally — charging provisions under the SEBI Act, the PFUTP and PIT regulations, Indian digit grouping where `35,00,000` means 3.5 million, and penalty phrasing that matches no Western template.

## Status

**The harness works. The gold set does not exist yet.** There are no scores in this README because scores require hand-labelled gold data, and none has been labelled. Nothing here is a placeholder number.

| | |
|---|---|
| Listing metadata | ✅ 11,957 orders, Nov 2004 – Jul 2026 — [on HuggingFace](https://huggingface.co/datasets/siddharthgaur/indic-reg-bench) |
| Document fetcher | ✅ working, resumable |
| Evaluation harness | ✅ pip-installable, 34 tests passing in CI |
| Labelling CLI | ✅ built; triages each order and keeps corrigenda and scans out of the queue |
| Benchmark sample | ✅ 2,000 orders selected (stratified by year, seed 42) |
| Document text | 🔄 1,107 of 2,000 fetched |
| Gold set | ❌ 0 of a target 400–600 |
| Baseline scores | ❌ blocked on the gold set |

**What the corpus already tells you, before any label exists** — measured, not
assumed, and written up in [`docs/corpus-findings.md`](docs/corpus-findings.md).
Document-level shares are **provisional** while the fetch runs: it goes
newest-first, so each figure drifts as the crawl reaches back toward 2004.

- A naive first-currency-amount extractor disagrees with the operative
  paragraph in **43.7%** of orders (n=661 comparable, of 1,325 fetched). That
  gap is the benchmark's reason to exist, and it has held at 24% → 47% → 44%
  across three sample sizes spanning two orders of magnitude.
- **A large minority of adjudications impose no monetary penalty at all** —
  abated on the noticee's death, or the SCN disposed of without imposition.
  Running at 25% and rising as the crawl reaches older orders. Answering
  "monetary" every time is wrong that often, so T1's `penalty_type` is a real
  prediction and T4 gets a free, absence-defined pool.
- **~11% of orders state the penalty only inside a table** that text extraction
  scrambles into the wrong noticee. Those must be labelled from the PDF, and
  the labelling CLI says so when it shows you one.
- Multi-hop was cut from v1 on 25 documents and **that decision was wrong**:
  across the full 10,827-order listing, 250 entities recur across genuinely
  unrelated matters, because brokers are repeat players. Reinstated for v1.1.
  (This one is already at final scale — it is computed from listing titles,
  not fetched text.)

## Why these five tasks

Task design was derived from 25 real orders, not from assumptions. Four findings shaped it:

1. **`Rs.` ends in a period.** Sentence splitters truncate the operative sentence immediately before the penalty amount.
2. **Penalty tables are column-scrambled** by text extraction — the amount precedes the noticee number, which precedes the name. Nearest-neighbour association mis-attributes penalties.
3. **Orders quote the noticee's own settlement pleas** in phrasing identical to the AO's ruling. The first currency amount differs from the operative one in **6 of 25 orders**.
4. **Two fields were cut for being regex-solvable** — `order_date` and `adjudicating_officer` both sit in a fixed signature block. If a regex solves it, it isn't a task.

| Task | Input → Output | Metric |
|---|---|---|
| **T1** structured extraction | order → JSON of noticees, penalties, sections | per-field F1 (attribution scored separately from names) |
| **T2** charging-section prediction | citation-masked facts → section | macro-F1, published against majority-class |
| **T3** numeric reasoning | order + question → integer/date | exact match |
| **T4** abstention | order + question → answer or `not stated` | answerable-accuracy **and** abstention-rate, never averaged |
| **T5** attribution | order + amount span → who proposed it | macro-F1 |

**Multi-hop was cut from v1.** Only 9 of 133 entities in the pilot appear in more than one order, and all 9 come from a single matter family. It would have been a task with no signal. Full reasoning in [`docs/phase1-task-design.md`](docs/phase1-task-design.md).

## Install

```bash
pip install -e .
indic-reg-bench tasks
```

## Rebuild the corpus

Source documents are **not redistributed here** — this repo ships IDs and a fetch script. See [`DATASET_CARD.md`](DATASET_CARD.md) for the reasoning.

```bash
python scripts/scrape_listing.py          # 479 pages of listing metadata (~12 min)
python scripts/build_splits.py --target 2000   # stratified sample, seed 42
python scripts/fetch_orders.py --fetch-set     # fetch PDFs + extract text
```

Both scrapers are rate-limited to 1.5 s/request and resumable. `sebi.gov.in` drops connections regularly; failed pages are retried.

## Evaluate a system

Write one file with one class:

```python
class System:
    name = "my-pipeline"
    cost_usd = 0.42          # optional, reported next to accuracy

    def predict(self, task: str, example: dict):
        ...
```

```bash
indic-reg-bench evaluate --system baselines/regex_baseline.py --data data/splits/test
```

Cost and latency are reported alongside accuracy. A system that wins by two points at forty times the cost has not won.

**No overall score is produced.** The tasks measure different things, and averaging them hides which one a system failed.

## Leaderboard

Empty, by design. It gets populated when the gold set exists and baselines are run — trivial floors, frontier APIs, open models, and the maintainer's own `rag-hybrid-search` pipeline, published honestly including where they lose.

| System | T1 | T2 | T3 | T4 | T5 | Cost | Latency |
|---|---|---|---|---|---|---|---|
| *(none yet)* | | | | | | | |

### Submitting

Open a PR with your `System` adapter, the harness output JSON, and a one-line description of the system. Results are reproduced before being merged.

## Documents

- [`docs/phase1-task-design.md`](docs/phase1-task-design.md) — the task suite, the evidence behind each decision, and what was cut
- [`docs/annotation-guidelines.md`](docs/annotation-guidelines.md) — field definitions, the four traps, and every resolved ambiguity
- [`DATASET_CARD.md`](DATASET_CARD.md) — provenance, licence, personal-data position, biases

## Limitations

One regulator, one document type, English only, extraction-heavy, single annotator. Agreement is self-agreement across two passes — an upper bound on reliability, not an estimate of it. Full list in the dataset card, and it is meant to be read.

## Licence

Apache-2.0 for the harness, scorers and labels. Order text belongs to SEBI and is not redistributed.
