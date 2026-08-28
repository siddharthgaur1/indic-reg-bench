# Changelog

All notable changes to indic-reg-bench, grouped by work period. Commit hashes refer to `siddharthgaur1/indic-reg-bench`.

## 2026-08-28 — Baseline run complete

- Completed the llama3.2 baseline run over the full 200-order labelling queue (`ab38e69`).

## 2026-08-22 — Portfolio integration

- Linked back to the maintainer's GitHub profile from the README (`9c4c61e`).

## 2026-08-11 — Baselines, silver labels, and the bugs they found

Running real systems over the labelling queue — before any gold label existed — surfaced defects the harness's own tests had missed.

- Added a second baseline and the scoring bug it exposed (`a8a9001`); fixed two further baseline defects found the same way (`cf6e83d`).
- Fixed T1 scoring the padding around a charging section instead of the section itself (`99a9cd0`).
- Added `run_baseline.py` to run any system over real orders ahead of gold labels, keyed for a later join (`d963d04`, `3e79637`).
- Added `build_eval_set.py` to build eval sets from labels and mark which ones came from a model, not a human (`3b34d85`).
- Fixed the labelling CLI crashing on the rupee sign — on the first order it serves (`9c89173`).
- Fixed the gold set sampler nearly stratifying by the spelling of "April" (`7e56e2b`).
- Re-derived the gold-set target from 400–600 down to 200, sized against the actual test-split pool rather than the whole corpus (`cd5e0d2`).
- Documented that the temporal train/test split moves document format, not just dates (`ebc21d9`).

## 2026-08-08 — Corpus complete at n=2,006

- Fetched the full corpus: 2,006 orders, final numbers, two corrections to earlier claims (`2411efe`).
- Added corpus triage and measured the two task decisions that had been conditional on scale (`3535e00`).
- Reversed the multi-hop cut after measuring entity recurrence across the full listing; recorded in the task design and README (`b62e4d3`).
- Added the T5 labelling path; fixed a currency pattern that had hidden 60 documents (`36fc495`).
- Recognised two more no-penalty phrasings, cutting the unclassified rate to 4.5% (`6efe5f9`).
- Recomputed the headline first-amount-vs-operative-amount gap after the rupee-sign/backtick fix (`15f1cb7`).
- Added annotation guidelines documenting the three traps found at corpus scale (`31f19e4`).
- Fixed `export_hf` raising a raw sqlite error instead of telling the user how to build the corpus (`abc02a1`); declared the missing `huggingface_hub` dependency (`5c78803`).
- Removed labels a smoke test had written into the real label store, and made that impossible to repeat (`e70040a`).
- Added error-path test coverage the benchmark previously had none of (`66e52f9`).

## 2026-08-05 – 2026-08-06 — Initial harness

- Phase 1 task design and the order-text fetcher (`0e790fc`).
- Evaluation harness, scorers, and listing pagination (`bb74e01`).
- Labelling CLI, inter-annotator agreement script, stratified splits, and a regex baseline (`3300dc9`).
- Dataset card and README with an (initially empty) leaderboard, licensed Apache-2.0 (`2a941e2`).
- CI running the test suite on Python 3.10 and 3.12 (`a9f611e`).
- Initial HuggingFace release of the listing metadata (`aa353dc`).
- Corrected two Phase 1 claims once corpus-scale data was available (`f73a9c9`).
- Fixed PDF path resolution for pre-2020 orders (`c8f3d8d`).
- Added a social preview card (`c0e7e79`).
