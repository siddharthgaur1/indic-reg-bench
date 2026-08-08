# Corpus findings

Properties of the corpus, computed without reference to any label. Nothing here is a score for any system, and nothing here required the gold set to exist.

Reproduce with `python scripts/corpus_stats.py` and `python scripts/task_viability.py`.

---

## Run of 2026-08-08 — n=1,107 fetched, full 10,827-order listing

Two Phase 1 decisions were written as measurable conditions rather than
judgements. Both conditions are now measured. **One of them reverses.**

Entity recurrence below is computed over the **entire 10,827-order adjudication
listing**, not just fetched documents, because order titles carry the noticee
and the matter — so this particular finding is already at final scale and will
not move when the fetch completes. Everything computed from document *text* is
at n=1,107 and still climbing.

### Finding 5 — multi-hop is viable, and the Phase 1 deferral was an artifact of n=25

Phase 1 cut multi-hop from v1 on this evidence: 133 distinct entities across 25
orders, 9 recurring, and all 9 traceable to a single matter family (the illiquid
stock options proceedings). The conclusion drawn was that recurrence in this
corpus is a formatting artifact. At full listing scale that is wrong.

| | Phase 1 (n=25 docs) | Now (10,827 orders) |
|---|---|---|
| Distinct noticees | 133 | 6,156 |
| Appearing in >1 order | 9 (6.8%) | 352 (5.7%) |
| Appearing in >1 **matter** | 0 genuine | **250 (4.1%)** |

The rate is similar; the *composition* is not. The recurring entities are
brokers, intermediaries and promoters appearing in genuinely unrelated
proceedings:

| Entity | Matters | Character of the recurrence |
|---|---|---|
| `ahilya commercial` | 11 | eleven unrelated scrips — Blue Print Securities, Brahmanand Himghar, Limtex, Minolta Finance, Oasis Cine, Parbati Holdings, … |
| `galaxy broking` | 9 | nine unrelated scrips — KRBL, Seagull Leafin, Marson's, Nandan Exim, Parsoli, Sarang Chemicals, Today's Writing |
| `arun panchariya` | 7 | seven separate GDR issues (Nakoda, Winsome Yarns, Edserv, Teledata, Zenith, Southern Ispat, Texmo) |
| `crosseas capital services` | 7 | broker across seven proceedings |
| `opg securities` | 5 | Bedmutha, Prakash Constrowell, Ujaas Energy, plus illiquid options |

This is exactly the cross-matter density Phase 1 said was missing, and it has an
obvious cause that 25 documents could not show: **intermediaries are repeat
players.** A broker is named across every scrip it traded. Phase 1 sampled 25
documents dominated by one retail-heavy proceeding and saw none of them.

**Recommendation: reinstate multi-hop for v1.1, not v1.** The existence proof
holds, but the questions must be built from document *bodies*, not titles, and
the bodies are 1,107 of 2,000 fetched. Two caveats that must ship with the task:

- Entity names *and matter names* are normalised aggressively (honorifics,
  `M/s`, `Pvt Ltd`/`Limited` suffixes, punctuation), each folded to a fixed
  point. Over-merging inflates recurrence, so these counts are an upper bound.
  An earlier run of this measurement folded matter names less than entity names,
  which counted `M/s KRBL Ltd` and `KRBL Ltd` as two matters and credited
  Arun Panchariya with 8 rather than 7. Both now use the same folding.
- 4,176 of 10,827 titles (38.6%) name no one — either no `in respect of` clause,
  or `in respect of 4 entities`. Those noticees are recoverable only from the
  document body, so real recurrence is **higher** than 3.7%, not lower.

### Finding 6 — T2's majority-class baseline, now with a number

Phase 1's cut rule for T2 ("cut it if the best system cannot clear majority-class
by a wide margin") could not be applied without knowing the prior. Reading the
charging section out of the operative paragraph gives a regex **estimate** of it
— not gold, never written to disk as a label:

| Section | Instances | Share |
|---|---|---|
| `15HA` | 285 | **47.2%** |
| `15HB` | 126 | 20.9% |
| `15A(b)` | 96 | 15.9% |
| `15A(a)` | 30 | 5.0% |
| `15C` | 16 | 2.7% |
| others | 50 | 8.3% |

The bar for T2 is therefore roughly **47% accuracy, free**. This confirms the
n=105 correction (`15HA` dominates, not `15HB`) and sharpens it into a threshold
the task can be judged against. The cut rule stands and is now falsifiable.

### Finding 7 — the labelling queue is 96% usable, and an earlier claim here was wrong

An earlier version of `task_viability.py` probed for the operative paragraph with
`hereby impose` and reported that **37.8% of documents have none**, calling them
unlabellable. That number is worthless and the conclusion was wrong. Reading the
documents splits it into four groups, only two of which are waste:

| Group | Docs | Share | What a labeller does |
|---|---|---|---|
| Operative paragraph in prose | 668 | 60.3% | label from text |
| **No penalty imposed** | 179 | 16.2% | label as such — this is an outcome, not a defect |
| Penalty present but table-scrambled | 115 | 10.4% | label from the PDF, not the text |
| Unclassified | 99 | 8.9% | read before labelling |
| No text layer (scanned PDF) | 26 | 2.3% | **waste** — needs OCR |
| Corrigendum | 20 | 1.8% | **waste** — exclude |

Two consequences for task design:

1. **`penalty_type` in T1 is a real prediction, not a formality.** SEBI closes
   roughly one adjudication in six without any monetary penalty — proceedings
   abated on the noticee's death, SCNs "disposed of without imposition of
   monetary penalty", warnings. A system that always answers `monetary` is wrong
   ~16% of the time. Phase 1's schema treated this field as near-constant.
2. **T4 gets a large, free, absence-defined pool.** Phase 1 called T4 the highest
   value task and worried about constructing *plausible* unanswerable questions.
   The corpus supplies 179 of them outright: ask "what penalty was imposed on the
   noticee?" of an order that imposes none, and the gold answer is defined by
   absence, which is exactly the property that makes T4 verifiable by a second
   reader.

The phrase that mattered was `without imposition of` — the nominalised form.
Probing only for `without imposing any` left 194 documents misfiled. Recorded
here because it is the second time on this corpus that a plausible regex has
produced a confident wrong number about task viability.

### Finding 8 — 2.3% of orders have no text layer at all

26 documents extract to under 200 characters from 14–21 page PDFs: they are
scans with no embedded text. All are older orders (Baroda Rayon, Jayshree
Petrochemicals, Era Constructions). The fetch runs newest-first, so **this share
will grow as the crawl reaches back toward 2004**, and it puts a real ceiling on
how far back a text-only benchmark can reach. This needs restating once the
fetch completes; it may justify either an OCR pass or an explicit date floor on
the benchmark sample.

### Fixed while measuring — the crawl died on its own progress log

The 2,000-document fetch stopped at 1,087 with
`UnicodeEncodeError: 'charmap' codec can't encode character '\x96'`. An en-dash
in an order title, printed to a Windows cp1252 stream, killed a multi-hour crawl
— the logging, not the data or the network. `scripts/fetch_orders.py` now
reconfigures stdout/stderr to UTF-8 with `errors="replace"`. Resumability meant
nothing was lost, which is the only reason this cost minutes instead of hours.

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
