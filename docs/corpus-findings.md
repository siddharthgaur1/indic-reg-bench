# Corpus findings

Properties of the corpus, computed without reference to any label. Nothing here is a score for any system, and nothing here required the gold set to exist.

Reproduce with `python scripts/corpus_stats.py`.

---

## Run of 2026-08-05 — n=105

**This slice is not yet representative.** The fetch runs newest-first, so all 105 documents are from 2026. The stratified 2,000-order sample spans 2004–2026; every number below must be recomputed when the fetch completes. They are recorded now because two of them already change conclusions from the 25-order pilot.

| | |
|---|---|
| Documents | 105 |
| Characters | 4,858,762 |
| Pages | min 1, median 14, max 89 |
| Years | 2026 only (fetch incomplete) |

### Finding 1 — the T5 premise is stronger than the pilot suggested

| Sample | Comparable docs | First amount ≠ operative amount |
|---|---|---|
| Pilot (n=25) | 25 | 6 (24.0%) |
| n=105 | 45 | **21 (46.7%)** |

A naive "first currency amount" extractor disagrees with the operative paragraph in nearly half of the documents where both can be located — and that is *before* counting multi-noticee mis-attribution, which is a separate failure.

This is the single strongest justification for T5 (proposed vs imposed) and for scoring T1's penalty attribution separately from noticee names.

**Caveat, stated because it matters:** only 45 of 105 documents are "comparable" — the remaining 60 contain no `hereby impose` string. Some use different operative phrasing, some impose no penalty at all. The 46.7% therefore describes the subset where the naive heuristic *appears* to work, which is the subset where it is most dangerous. Locating the operative paragraph robustly is itself an unsolved sub-problem, and the harness should not pretend otherwise.

### Finding 2 — correction: `15HB` is not the majority charging section

The pilot showed `15HB` (27 mentions) ahead of `15HA` (16). At n=105 this **reverses**:

| Section | Mentions |
|---|---|
| `15HA` | 299 |
| `15HB` | 112 |
| `15A(b)` | 30 |
| `15JB` | 21 |
| `15EB` | 19 |
| `15A(a)` | 11 |
| `15EA` | 9 |
| `15F` | 9 |

(`15J` at 379 is the mitigating-factors provision cited in nearly every order; it is not a charging section and is excluded from the T2 label set.)

Two consequences:

1. The T2 majority-class baseline must be computed from the gold set at scoring time, never hard-coded. `scoring.majority_class_baseline()` already does this; the Phase 1 document's assertion that "majority class = 15HB" is **wrong at scale** and is corrected here.
2. `15JB`, `15F` and `15H` appear in the corpus but are absent from `evaluate.CHARGING_SECTIONS`. The label set needs revising once the full sample is fetched.

### Finding 3 — multi-noticee orders are rarer than the pilot implied

4 of 105 (3.8%) reference `Noticee No. N`, against 3 of 25 (12%) in the pilot. Multi-party orders are the most interesting case for T1 and among the rarest. The sample must deliberately oversample them, and the dataset card must state that the resulting distribution is not representative of SEBI's output.

### Finding 4 — surface variety is wider than the pilot

| Form | Docs | Share |
|---|---|---|
| `crore` | 93 | 89% |
| `Lakh` | 87 | 83% |
| `Rs.` | 85 | 81% |
| `₹` | 47 | **45%** |
| `Lakhs` | 42 | 40% |
| `Crore` | 17 | 16% |
| `Lac` | 5 | 5% |
| `Lacs` | 4 | 4% |

`₹` appears in 45% of documents here against 20% in the pilot — a system that handles only `Rs.` fails on nearly half the corpus. All eight forms are covered by `indic_reg_bench.numerals` and tested.

---

## Open items this raises

- Recompute everything once the 2,000-order fetch completes; the 2026-only skew makes every figure provisional.
- Revise the T2 label set to include `15JB`, `15F`, `15H`.
- Investigate the 60/105 documents with no `hereby impose`: are they penalty-free orders, or a distinct operative phrasing the labelling CLI should anchor on too?
