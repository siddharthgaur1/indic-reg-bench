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
| Evaluation harness | ✅ pip-installable, 72 tests passing in CI, all five tasks exercised end to end |
| Labelling CLI | ✅ T1, T4 and T5; triages each order and keeps corrigenda and scans out of the queue |
| Benchmark sample | ✅ 2,000 orders selected (stratified by year, seed 42) |
| Document text | ✅ 1,986 of 2,000 fetched, 70M characters, 2008–2026 |
| Gold set | ❌ 0 of a target **200** |
| Baselines | ✅ two implemented and runnable — regex floor, and a local LLM via Ollama (free, no key) |
| Baseline scores | ❌ blocked on the gold set |

**The target was 400–600 and is now 200.** That number was set against the whole
corpus, before labelling was restricted to the test split. Test holds 422
orders — 408 after corrigenda and scanned PDFs — so 600 was unreachable and 400
would have been a census of the test set rather than a sample of it, with
nothing left unlabelled to grow into. 200 is roughly half the pool, enough to
separate systems on macro-F1, and leaves room for a v1.1 expansion. The split
itself is unchanged: the reasoning for cutting at 2023 is about leakage and
deployment realism, and neither depends on how many orders get labelled.

At the test split's natural bucket mix, 200 orders is ~130 prose, ~32
table-scrambled and ~29 no-penalty. The 32 are the real cost — §3.2 requires
reading those from the PDF — and they cluster in 2024 and 2026.

**What the corpus already tells you, before any label exists** — measured over
all 2,006 fetched documents, not assumed, and written up in
[`docs/corpus-findings.md`](docs/corpus-findings.md):

- A naive first-currency-amount extractor disagrees with the operative
  paragraph in **48.6%** of orders (567 of 1,166 comparable). That gap is the
  benchmark's reason to exist, and it has held across an 80× increase in
  sample size — 24% at n=25, 47% at n=105, 49% at n=2,006 — and survived two
  bug fixes to the extraction that measures it.
- **18.3% of adjudications impose no monetary penalty at all** — abated on the
  noticee's death, or the SCN disposed of without imposition. Answering
  "monetary" every time is wrong nearly one time in five, so T1's
  `penalty_type` is a real prediction, and T4 gets 368 free, absence-defined
  items.
- **13.4% of single-noticee orders impose more than one penalty**, under more
  than one section. The scoring unit is the `(noticee, penalty, section)`
  triple, not the person.
- **The rupee sign extracts as a backtick** (U+0060) from a quarter of these
  PDFs, and is the *only* currency marker in **10.4%** of them. Those documents
  matched no currency pattern in this repo at all — returning nothing, never
  erroring.
- Multi-hop was cut from v1 on 25 documents and **that decision was wrong**:
  across the full 10,827-order listing, 250 entities recur across genuinely
  unrelated matters, because brokers are repeat players. Reinstated for v1.1.
- **96.6% of the corpus is labellable.** Only corrigenda (1.0%) and scanned
  PDFs with no text layer (2.4%) are waste.
- **The temporal split moves document format, not just dates.** SEBI began
  issuing multi-noticee penalties as tables in 2024: the table-scrambled bucket
  runs 0–6% every year from 2005 to 2023, then **27.7% (2024), 10.5% (2025),
  29.1% (2026)**. Across the cut that is **1.7% of train against 16.1% of
  test** — the hardest layout for penalty attribution, and a system tuned on
  train has barely seen it. This is the benchmark's most demanding property and
  it is deliberate: a regulatory system is built on past orders and run on new
  ones, formats included. `build_splits.py --splits` prints the full
  composition on every run so it stays visible.

## Why these five tasks

Task design was derived from 25 real orders, then re-verified against all 2,006. Four findings shaped it:

1. **`Rs.` ends in a period.** Sentence splitters truncate the operative sentence immediately before the penalty amount.
2. **Penalty tables are column-scrambled** by text extraction — the amount precedes the noticee number, which precedes the name. Nearest-neighbour association mis-attributes penalties.
3. **Orders quote the noticee's own settlement pleas** in phrasing identical to the AO's ruling. The first currency amount differs from the operative one in **48.6%** of orders at full corpus scale (it was 6 of 25 in the pilot).
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

**Before the gold set exists**, `evaluate` has nothing to score against. To run a system over real orders anyway — the same orders, in the same sequence, that `label.py` will serve — use:

```bash
python scripts/run_baseline.py --system baselines/llm_baseline.py --limit 200
```

Predictions land in `predictions/<system>.<task>.jsonl`, keyed by order id, so when labels arrive scoring is a join rather than a re-run. Resumable; the local model runs at roughly 80 s/order on CPU. Predictions are never written to `labels/` and nothing in the labelling path reads them.

To score anything, labels have to be joined to order text — `evaluate` reads `data/splits/<split>/<task>.jsonl`, which carries both:

```bash
python scripts/build_eval_set.py --labels labels/t1.jsonl          # gold
python scripts/build_eval_set.py --labels predictions/<system>.t1_extraction.jsonl   # silver
```

These files embed full order text and are gitignored for the same reason the corpus is: nothing here redistributes SEBI documents. Rebuild them locally.

### Silver labels

A model can label the corpus, and the harness will score against it, but it is marked and it is not a result:

```
!! NOT A BENCHMARK RESULT - labels came from model:ollama-llama3.2
!! Silver labels exercise the harness. They do not measure a system.
```

Every silver example carries `label_source: "model:<system>"`, `RunResult` carries it into `--json`, and the report leads with the banner. Silver exists to exercise the pipeline and to give a human annotator something to correct. Where the labelling model and the system under test are the same model, the comparison measures nothing at all — the leaderboard stays gold-only.

**No overall score is produced.** The tasks measure different things, and averaging them hides which one a system failed.

## Leaderboard

Empty, by design. It gets populated when the gold set exists and baselines are run — trivial floors, frontier APIs, open models, and the maintainer's own `rag-hybrid-search` pipeline, published honestly including where they lose.

Two baselines are already wired and runnable against any gold file:

    indic-reg-bench evaluate --system baselines/regex_baseline.py
    ollama pull llama3.2 && indic-reg-bench evaluate --system baselines/llm_baseline.py

The LLM baseline runs on localhost, so it costs nothing and needs no key. It is a *system under test*, never a source of labels: a model that pre-fills the gold set and then appears on the leaderboard is a benchmark measuring its own annotator.

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
