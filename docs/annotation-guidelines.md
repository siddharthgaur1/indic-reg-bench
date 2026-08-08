# Annotation Guidelines

Rules for labelling the gold set. **This document grows as labelling proceeds** — every rule below exists because a specific order forced a decision, and each is recorded with the order that forced it.

The rules that follow were derived from the 25-order pilot. They are the starting point, not the finished thing. Expect to add to §4 constantly for the first hundred orders; if you stop adding rules, you have probably stopped reading carefully.

---

## 1. Sources of truth

Label from the **PDF text as extracted**, not from the order's title and not from the listing metadata. Titles are unreliable: `Adjudication Order in respect of Jitendra Kumar Nahta HUFin the matter of...` has a missing space, and titles routinely name one noticee when the order penalises seven.

Where extraction has visibly mangled a table (see §3), open the source PDF and label from that. Record `"note": "labelled from PDF, table scrambled in text"`.

---

## 2. Field definitions (T1)

| Field | Definition |
|---|---|
| `name` | The noticee as named in the operative paragraph or penalty table. Strip honorifics only when they are unambiguous; keep the name otherwise as printed. |
| `penalty_inr` | Whole rupees, integer, no separators. `Rs. 4,00,000/-` → `400000`. |
| `charging_section` | The SEBI Act section the penalty is imposed *under* — `15HB`, `15HA`, `15EA`, `15EB`, `15A(a)`. Not the regulation violated. |
| `violated_provisions` | The regulations breached, e.g. `PFUTP 3(a)`, `PIT 4(1)`. Distinct from `charging_section`. |
| `penalty_type` | `monetary`, `debarment`, `warning`, `none`, `other`. |
| `total_penalty_inr` | Sum over all noticees. Computed, but check it against any total the order states itself. |

---

## 3. The traps, and the rule for each

### 3.1 `Rs.` ends a sentence

Sentence-splitting truncates the operative sentence immediately before the number:

> `...hereby impose a penalty of Rs.`

**Rule:** never label from a sentence-segmented view. The labelling CLI shows a 1,400-character window for this reason.

### 3.2 Penalty tables are column-scrambled

Real extraction output, Citrus Check Inns:

> `Noticee Penalty under Name of Noticee Penalty amount no. section Rs.35,00,000/- 2 Omprakash Basantlal Goenka (Rs. Thirty Five Lacs) Rs.25,00,000/- 3 Prakash Ganpat Utekar 15HA of SEBI (Rs. Twenty Five Lacs) Act, 1992`

The amount precedes the noticee number, which precedes the name. Nearest-neighbour reading attributes ₹35,00,000 to Omprakash Basantlal Goenka — which here happens to be **correct**, but the same layout in a different order will not be.

**Rule:** for any order with more than one noticee, open the PDF and read the table visually. Do not label multi-noticee penalty attribution from extracted text. This is the single most error-prone field in the benchmark and the one T1 most needs to be right.

### 3.3 Quoted amounts are not the penalty

Orders quote the noticee's own settlement pleas verbatim, in identical phrasing:

> `my client ... express his sincere willingness to settle the Issue for a minimum penalty of Rs. 1 lacs or 1.20 Lacs under Settlement Scheme.`

Measured over the full corpus: the first currency amount differs from the operative one in **48.6%** of orders (567 of 1,166 comparable). On the 25-order pilot this looked like 24%; it is roughly a coin flip.

**Rule:** the penalty is what appears after `hereby impose` in the AO's own voice, in the final operative paragraph. Amounts inside quotation marks, inside indented submissions, or attributed to a party are never the label. When both a quoted and an imposed figure exist, note it — those orders are T5 examples.

### 3.4 Numerals and words can disagree

Most orders state the amount twice: `Rs. 4,00,000/- (Rupees Four Lakh Only)`.

**Rule:** label the numeral. If the words disagree with it, **do not silently pick one** — record both in `note` and flag the order. A genuine internal contradiction in a SEBI order is a finding, and it belongs in the limitations section, not smoothed over.

### 3.5 A backtick is a rupee sign

Several SEBI PDFs embed ₹ in a font whose glyph extracts as **U+0060 GRAVE ACCENT**:

> `MIL made a preferential allotment of convertible equity warrants for ` 30 crores`

It is the only currency marker in **10.4%** of fetched orders (204 of 1,958 with a text layer), appears alongside `Rs.` in 292 more, and turns up in a quarter of the corpus overall — more often than the actual `₹` character.

**Rule:** treat `` ` `` before a number as ₹. If an order looks like it contains no amounts at all, this is why — check before recording "no penalty". The labelling CLI's span finder already handles it; your eyes are the part that needs telling.

### 3.6 One noticee can owe several penalties

Real order, one noticee, three penalties under three provisions:

> `` ` 2,50,000/- ... under Section 15A(b) ... of Regulation 7(1) of SAST Regulations, 1997. ` 2,50,000/- ... of regulation 13(1) of PIT Regulations, 1992. ` 2,00,000/- ... of section 11C(3) ``

**13.1%** of *single-noticee* orders impose more than one penalty; 5.7% cite more than one charging section.

**Rule:** the unit of a T1 label is the `(noticee, penalty, section)` triple, not the person. Enter the same name once per triple. Collapsing three penalties into one row is a silent labelling error that scoring cannot detect, because a partial answer looks like a confident one.

### 3.7 "No penalty imposed" is a label, not a failed extraction

Roughly a quarter of adjudication orders close without any monetary penalty — proceedings abated on a noticee's death, an SCN "disposed of without imposition of monetary penalty", or a warning. The disposition is phrased at least five ways: `without imposing any penalty`, `without imposition of monetary penalty`, `hereby dispose of`, `not liable for monetary penalty`, `stands disposed of`.

**Rule:** record `penalty_type` as the outcome and leave the amount empty. Do not skip the order, and do not go hunting for an amount that is not there — the labelling CLI flags these with a `NO PENALTY IMPOSED` banner. These orders are also the natural pool for T4 abstention items.

---

## 4. Resolved ambiguities

Append one entry per decision. Format: the order, the question, the rule adopted.

| Order | Question | Rule |
|---|---|---|
| Front Running / Pace Stock Broking (2026-07-22) | Prose says penalty is under `15A(a)`, `15A(c)` and `15HB`; the table beneath lists `15A(a)`, `15A(b)`, `15HB`. Which is authoritative? | **The table.** It is the operative schedule and states per-section amounts. Record the discrepancy in `note`. This is a defect in the source document, not in the extraction. |
| Corrigendum, Illiquid Stock Options (2026-07-15) | 1 page, 1,090 chars, no penalty — corrigenda amend earlier orders. | **Exclude from T1.** v1 scopes to adjudication orders; `doc_type` filtering handles this. Do not label as "penalty: none" — that would teach the benchmark that a real category of order carries no penalty. |
| `Late Ms. Anju Rani`, `Late Padma Singhwani`, `Late Sudha V Thakkar` | Deceased noticee; proceedings continue against legal heirs. Who is the noticee? | **The named deceased person**, as the order names them. Note the heir separately if the order penalises them by name. Do not silently substitute the heir. |
| IDBI Trusteeship (2026-05-27) | Order discusses a `maximum penalty of Rs. ...` for a technical violation, then imposes ₹2,00,000. | The imposed figure is the label. Statutory maxima and the AO's reasoning about range are not penalties. |
| Multi-section orders (Pace Stock Broking) | One noticee, three charging sections, three amounts. | **One entry per (noticee, section) pair**, not one summed entry. `total_penalty_inr` carries the sum. Collapsing loses the section-level signal T1 is meant to test. |

---

## 5. Abstention items (T4)

Build these **by construction, never by invention**:

1. Take a real labelled order.
2. Pick a field that genuinely does not appear in it — a disgorgement amount in a monetary-penalty-only order, a debarment period where none was ordered.
3. Verify the absence by searching the full text, not by memory.
4. Gold answer is the literal string `not stated`.

**Rule:** the question must be plausible for a SEBI order — drawn from a field that appears in *other* orders. "What is the noticee's shoe size" measures nothing. Record which order the field was borrowed from, so plausibility is auditable.

`python scripts/label.py --task t4` implements this. Its questions are **templated, not written per document**, so whether an item is answerable is a property of the order rather than of the question writer. The bank is weighted by measured prevalence across 1,290 orders, and half of each document's questions are drawn from low-prevalence fields — sampling uniformly would make almost every item answerable, and a T4 set that is 90% answerable measures nothing about abstention:

| Field | Present in |
|---|---|
| penalty amount | 99% |
| charging section | 97% |
| payment deadline | 78% |
| regulations violated | 70% |
| recovery on non-payment | 41% |
| **disgorgement** | **19%** |
| **debarment period** | **5%** |

The last two are what make an unanswerable item hard: SEBI *does* order disgorgement in one order out of five, so declining it requires reading this order rather than knowing the genre.

**Rule:** answer `-` only after searching the whole document. The CLI writes each order's full text to a searchable file and prints the path for exactly this reason — a windowed view makes "not stated" far too easy to answer wrongly.

---

## 6. Self-agreement protocol

1. Label 50 orders (pass 1).
2. Wait **at least seven days**. Do not re-read pass-1 labels in the interim.
3. Re-label the same 50 with `python scripts/label.py --task t1 --redo`.
4. Report `python scripts/agreement.py`.

**State this as a limitation, always:** single-annotator self-agreement is an *upper bound* on reliability. A second pass by the same person reproduces that person's systematic misreadings — a misunderstanding of what `15HB` covers will be reproduced perfectly and score 1.0. It measures consistency, not correctness. Two annotators would measure something stronger; this benchmark does not have two annotators, and the dataset card says so.

---

## 7. What must never happen

- **No model-generated label enters the gold set.** Silver-set labels live in separate files, are marked `"source": "silver"`, and are never merged.
- **No label inferred from the title.** Read the order.
- **No amount typed from memory.** Copy it from the text.
- **No skipped `note` on an ambiguous call.** The notes are what makes this document grow, and this document is the most defensible artifact in the project.
- **No label written by exercising the CLI.** Piping input to `label.py` to check that it runs produces rows that are indistinguishable from real labels once written — this has already happened once and reached a public commit. Every smoke test passes `--dry-run`, which makes the write path unreachable.
