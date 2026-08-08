# Corpus findings

Properties of the corpus, computed without reference to any label. Nothing here is a score for any system, and nothing here required the gold set to exist.

Reproduce with `python scripts/corpus_stats.py` and `python scripts/task_viability.py`.

---

## Run of 2026-08-08 — n=2,006 fetched (FINAL), full 10,827-order listing

**The fetch is complete.** Every number in this section is final; nothing here
is provisional any more.

| | |
|---|---|
| Documents fetched | 2,006 |
| Of the 2,000-order benchmark sample | 1,986 |
| Characters | 69,979,073 |
| Pages | min 1, median 13, max 140 |
| Nominal date range | 2005 – 2026 |
| **Effective date range** | **2008 – 2026** |

**On the 14 sample orders not fetched, and the missing early years:** six are
pre-2008, and that is not a fetch failure — SEBI's own listing contains exactly
**7 adjudication orders before 2008** (one in 2004, four in 2005, none in 2006,
two in 2007), against 90 in 2008 alone. The dataset card's "Nov 2004 – Jul 2026"
is true of the *listing index* and misleading about the *corpus*: this is a
2008–2026 benchmark. The other 8 misses are scattered connection failures and
are re-fetchable by re-running the script.

Two Phase 1 decisions were written as measurable conditions rather than
judgements. Both are now measured. **One of them reverses.**

Entity recurrence is computed over the **entire 10,827-order adjudication
listing**, not just fetched documents, because order titles carry the noticee
and the matter.

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
all 1,986 sampled bodies are now fetched. Two caveats that must ship with the task:

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
| `15HA` | 438 | **43.8%** |
| `15HB` | 197 | 19.7% |
| `15A(b)` | 146 | 14.6% |
| `15C` | 59 | 5.9% |
| `15A(a)` | 57 | 5.7% |
| `15A` | 45 | 4.5% |
| others | 59 | 5.9% |

Over 1,001 label instances. The bar for T2 is therefore roughly **44% accuracy,
free**. This confirms the n=105 correction (`15HA` dominates, not `15HB`) and
sharpens it into a threshold the task can be judged against. The cut rule stands
and is now falsifiable.

### Finding 7 — the labelling queue is 96% usable, and an earlier claim here was wrong

An earlier version of `task_viability.py` probed for the operative paragraph with
`hereby impose` and reported that **37.8% of documents have none**, calling them
unlabellable. That number is worthless and the conclusion was wrong. Reading the
documents splits it into four groups, only two of which are waste:

Final, n=2,006:

| Group | Docs | Share | What a labeller does |
|---|---|---|---|
| Operative paragraph in prose | 1,310 | 65.3% | label from text |
| **No penalty imposed** | 368 | 18.3% | label as such — this is an outcome, not a defect |
| Unclassified | 164 | 8.2% | read before labelling |
| Penalty present but table-scrambled | 95 | 4.7% | label from the PDF, not the text |
| No text layer (scanned PDF) | 48 | 2.4% | **waste** — needs OCR |
| Corrigendum | 21 | 1.0% | **waste** — exclude |

**96.6% of the fetched corpus is labellable.**

Two consequences for task design:

1. **`penalty_type` in T1 is a real prediction, not a formality.** SEBI closes
   **18.3%** of adjudications without any monetary penalty — proceedings abated
   on the noticee's death, SCNs "disposed of without imposition of monetary
   penalty", warnings. A system that always answers `monetary` is wrong nearly
   one time in five. Phase 1's schema treated this field as near-constant.
2. **T4 gets a large, free, absence-defined pool.** Phase 1 called T4 the highest
   value task and worried about constructing *plausible* unanswerable questions.
   The corpus supplies **368** of them outright: ask "what penalty was imposed on
   the noticee?" of an order that imposes none, and the gold answer is defined by
   absence, which is exactly the property that makes T4 verifiable by a second
   reader.

Getting the bucket right took four passes over the *documents*, each triggered by
reading the residue rather than by trusting the regex:

| Pass | Added | Unclassified |
|---|---|---|
| 1 | `hereby impose` only | 37.8% "unlabellable" |
| 2 | `without imposition of` (the nominalised form) | 8.9% |
| 3 | `hereby dispose of`, `not liable for … penalty` | 4.5% |
| 4 | `I impose`, `impos… penalty of` (no "hereby") | **8.2%** at n=2,006 |

Pass 4 is the instructive one. At n=1,227 the residue was 4.5% and looked
finished; extending the crawl past 2016 pushed it back up to 10.7%, because
**older orders impose without the word "hereby"** — "I impose a penalty of
Rs. …". That phrasing appears in **251 orders**, every one of which had been
filed as "no operative paragraph". Fixing it moved 251 documents into the
labellable-from-text bucket and cut the apparent table-scrambled share from
14.4% to 4.7% — most of those were never tables at all.

The lesson is not "write a better regex". It is that **the residue has to be
re-read at every corpus size**, because a pattern tuned on recent documents
silently degrades on older ones and reports the degradation as a property of the
corpus. The remaining 8.2% is left unclassified on purpose and shown to the
labeller with a warning; a bucket that admits it does not know is worth more
than one padded out with guesses.

Recorded at this length because it is the third time on this corpus that a
plausible regex has produced a confident wrong number about task viability.

### Finding 8 — scanned orders are a 2014–2022 problem, not an old-orders problem

48 documents (2.4%) extract to under 200 characters from 14–21 page PDFs: they
are scans with no embedded text layer.

**The prediction recorded here at n=1,107 was wrong.** It said this share
"will grow as the crawl reaches back toward 2004" and suggested a date floor on
the benchmark sample. The completed fetch says the opposite:

| Year | Docs | No text layer |
|---|---|---|
| 2008–2013 | 620 | **0 (0%)** |
| 2014 | 101 | 9 (9%) |
| 2015 | 98 | 13 (13%) |
| 2016–2019 | 419 | 16 (4%) |
| 2020–2022 | 345 | 9 (3%) |
| 2023–2026 | 422 | 1 (0.2%) |

Every order from 2008 through 2013 has a clean text layer. The scans cluster in
**2014–2015 (9–13%)** and taper off after. The plausible cause is a change in
SEBI's document workflow in that window rather than age — older orders were
apparently produced digitally from the start.

**So there is no date floor to impose**, and the earlier recommendation is
withdrawn. A text-only benchmark reaches 2008 cleanly. If the 48 scans are ever
worth recovering, it is an OCR pass over a specific two-year window, not a
policy about old documents.

This is the second time in this document that a trend extrapolated from the
newest slice of a newest-first crawl pointed the wrong way.

### Finding 9 — the rupee sign extracts as a backtick, and it hid whole documents

A 31,000-character order containing dozens of amounts matched **zero** currency
regexes. The reason:

> `...MIL had issued capital of 71,50,000 shares of ` 10/- each. On January 4,
> 2010 MIL made a preferential allotment of convertible equity warrants for
> ` 30 crores...`

Those backticks are rupee signs. Several SEBI PDFs embed ₹ in a font whose glyph
maps to **U+0060 GRAVE ACCENT**, so `₹30 crores` extracts as `` ` 30 crores ``.

Final, over the 1,958 documents with a text layer:

| | Docs | Share |
|---|---|---|
| Standard `Rs.` / `₹` / `INR` | 1,495 | 76.4% |
| Backtick-as-rupee | 496 | 25.3% |
| **Backtick only — invisible to every prior pattern** | **204** | **10.4%** |
| No currency amount at all | 259 | 13.2% |

The backtick-only share **doubled** as the corpus grew — it was 4.8% at
n=1,241. One document in ten had every currency amount invisible to this repo's
own extraction. The backtick is also more common overall (25.3% of documents)
than the actual `₹` character (14%).

This is the most dangerous class of bug in a corpus pipeline: it does not fail,
it silently returns nothing, so the affected documents drop out of every
measurement without appearing in any error count. `numerals.CURRENCY` now
carries the backtick, and `corpus_stats.py` and `label.py` both import that one
pattern instead of keeping their own copies — three regexes had drifted apart,
and only one of them was ever going to get fixed by hand.

**The headline number, final.** With the backtick included and the operative
pattern corrected (Finding 7), the first currency amount in a document disagrees
with the operative paragraph in **48.6%** of comparable documents — 567 of
1,166, at n=2,006.

| Sample | Comparable docs | Disagree |
|---|---|---|
| Pilot, n=25 | 25 | 24.0% |
| n=105 | 45 | 46.7% |
| n=1,325 | 661 | 43.7% |
| **Final, n=2,006** | **1,166** | **48.6%** |

The premise the benchmark rests on survived two of its own bug fixes and an
80× increase in sample size. A naive first-amount extractor is wrong on roughly
half of all SEBI adjudication orders, before any multi-noticee mis-attribution
is counted.

### Finding 10 — one noticee can carry several penalties, and the T1 example says otherwise

Real order, single noticee, three separate penalties:

> `Penalty Amount Violation ` 2,50,000/- (Rupees Two Under section 15A(b) of
> SEBI Act for violation Lakh Fifty Thousand Only) of Regulation 7(1) of SAST
> Regulations, 1997. ` 2,50,000/- ... of regulation 13(1) of PIT Regulations,
> 1992. ` 2,00,000/- ... of section 11C(3)...`

Measured over single-noticee orders only, so multi-party orders cannot inflate it:

| | Orders | Share |
|---|---|---|
| Examined (single-noticee, penalty present) | 1,277 | — |
| More than one penalty amount in the operative window | 171 | **13.4%** |
| More than one charging section | 83 | 6.5% |

The rate held almost exactly as the sample grew from 758 to 1,277 orders
(13.1% → 13.4%), so this is a stable property of the corpus rather than a
small-sample artifact.

Phase 1's **scoring** is already right — it specifies micro-F1 over
`(noticee_name, penalty_inr, charging_section)` triples. What is wrong is the
**JSON example**, which shows one penalty and one section per noticee, and the
labelling CLI, which read as one row per person. One noticee in eight owns more
than one triple. The CLI now says so at the prompt; the schema example in the
task design should be updated to show a repeated noticee before anyone labels
at volume.

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
