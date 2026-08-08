# indic-reg-bench — Phase 1: Task Design

> **Corrected 2026-08-05 by [`corpus-findings.md`](corpus-findings.md) at n=105.** Two claims below are wrong at scale and are superseded there:
> - §2/§3 "majority class = `15HB`" — **`15HA` dominates** (299 mentions vs 112). Never hard-code the majority class; compute it from the gold set.
> - §1.3 "first amount differs from operative in 24%" — the rate is **46.7%** on the larger sample, which strengthens the case for T5.
>
> The task suite and the cuts are unaffected.

> **Corrected again 2026-08-08 at n=1,107 documents / 10,827 listed orders. This round changes a decision, not just a number:**
> - **§4 "multi-hop: cut from v1" is reversed.** §4's evidence was 9 of 133 entities recurring, all inside one matter family. Across the full listing, **250 entities recur across genuinely different matters** — brokers and intermediaries are repeat players, which 25 documents from a single retail-heavy proceeding could not show. `ahilya commercial` appears in 11 unrelated scrips, `galaxy broking` in 9, `arun panchariya` across 7 separate GDR issues. Multi-hop is viable and should ship in **v1.1**, built from document bodies rather than titles — not be written off. See Finding 5.
> - **§2's cut rule for T2 now has a threshold.** The majority-class bar is **`15HA` at 47.2%** of label instances.
> - **§3's T1 schema understates `penalty_type`.** Roughly **one adjudication in six imposes no monetary penalty** — abated on the noticee's death, SCN "disposed of without imposition of monetary penalty", or a warning. The field is a real prediction rather than a near-constant, and those same documents are a ready-made, absence-defined pool for T4. See Finding 7.
> - §5's note on deceased noticees describes a recurring category, not three outliers.
>
> The five-task suite stands. What changed: multi-hop returns for v1.1, and two fields treated as formalities carry signal.

**Status:** proposal for review. Nothing here is a label, a score, or a dataset.
**Evidence base:** 25 SEBI adjudication orders fetched 2026-08-05, 1,476,418 characters, 1–88 pages (median 21). Every quotation below is verbatim from those PDFs.

---

## 0. The blocker you need to read first

**The corpus described in the brief does not exist.**

`sebi-explorer/data/sebi_orders.db` contains **25 rows of listing metadata** (date, title, entity, violation_type, url) and **zero document text**. There were never ~11,000 scraped orders. `scripts/scrape.py` only ever parsed listing pages, and its pagination is broken: `get_next_url()` looks for an `<a>` whose text contains "Next", which SEBI's listing does not render — so every run terminates after page 1, which is exactly the 25 rows in the DB.

I did not design tasks against a corpus I could not see. I wrote `scripts/fetch_orders.py`, which resolves the PDF out of the order page's viewer iframe (`<iframe src='../../../web/?file=<pdf-url>'>` — not an anchor), downloads it, and extracts text with pdfplumber. It is rate-limited at 1.5 s/request and resumable. **All 25 orders are now fetched with real text.** Three failed on transient connection resets on the first pass and succeeded on re-run.

Everything below is derived from those 25 real documents. 25 is enough to design tasks and to kill bad ones. It is **not** enough to build the benchmark — see §7.

---

## 1. What the documents actually look like

Five structural facts drive every design decision that follows.

**1.1 `Rs.` ends in a period, so sentence segmentation cuts exactly at the penalty.**
Every naive sentence splitter truncates the operative sentence at the currency token, immediately before the number:

> `...I, in exercise of powers conferred upon me under section 15-I of the SEBI Act read with rule 5 of the Rules, hereby impose a penalty of Rs.`

The amount (`4,00,000/-`) is in the *next* "sentence". Any harness that chunks by sentence silently loses the answer to the anchor task.

**1.2 Penalty tables are column-scrambled by text extraction.**
Real output from the Citrus Check Inns order:

> `Noticee Penalty under Name of Noticee Penalty amount no. section Rs.35,00,000/- 2 Omprakash Basantlal Goenka (Rs. Thirty Five Lacs) Rs.25,00,000/- 3 Prakash Ganpat Utekar 15HA of SEBI (Rs. Twenty Five Lacs) Act, 1992 Rs.25,00,000/- 4 Venkatraman Nata...`

The amount precedes the noticee number, which precedes the name, and the charging section is stranded mid-column. Nearest-neighbour association gives the *wrong* noticee. This is the single richest source of difficulty in the corpus.

**1.3 Quoted submissions contain penalty figures that are not the penalty.**
From the Jitendra Kumar Nahta HUF order — this is the noticee's own settlement plea, quoted inside the order:

> `...my client prays for a lenient view over the matter and express his sincere willingness to settle the Issue for a minimum penalty of Rs. 1 lacs or 1.20 Lacs under Settlement Scheme. …”`

A regex taking the first currency amount returns `1` here. The imposed penalty is elsewhere. **Measured: the first currency amount in the document differs from the amount in the operative paragraph in 6 of 25 orders (24%).** In the Exfinity order the first amount is `104`; the operative penalty is `₹10,00,000`.

**1.4 Surface conventions vary within the same regulator.**

| Form | Docs (of 25) |
|---|---|
| `Rs.` | 21 |
| `₹` | 5 |
| `Lakh` | 16 |
| `Lakhs` | 9 |
| `Lac` | 2 |
| `Lacs` | 2 |
| `crore` / `Crore` | 19 / 4 |

Amounts use Indian digit grouping (`4,00,000`, `35,00,000`) and are almost always restated in words: `Rs. 4,00,000/- (Rupees Four Lakh Only)`. The words are a genuine second channel — usable for verification, and a place where systems that normalise via Western grouping visibly break.

**1.5 The corpus is dominated by single-noticee orders.**
22 of 25 orders contain no `Noticee No. N` references at all; the remaining three have 3, 4 and 7. Multi-party orders are the interesting case and they are **rare**. Stratified sampling must deliberately oversample them, or the benchmark will measure the easy case.

Observed charging sections: `15HB` (27 mentions), `15HA` (16), `15EA` (9), `15EB` (8), `15G(i)` (3), `15A(a)/(b)/(c)`.
Observed regulation families: PFUTP (154), AIF (114), LODR (49), PIT (43), Stock Brokers (15), SAST (2).
(`15J` at 55 mentions is the mitigating-factors provision, cited in nearly every order — it is not a charging section and must be excluded from any citation label set.)

---

## 2. Verdicts on your proposed suite

| Your task | Verdict | Reason |
|---|---|---|
| Structured extraction | **Keep — anchor**, with 2 fields cut | Two of the six fields are regex-trivial |
| Section-citation retrieval | **Keep, but reframed** | As specified it leaks the answer from the input |
| Multi-hop entity questions | **Cut from v1** | Corpus-infeasible; see §4 |
| Numeric reasoning | **Keep, narrowed** | Pure normalisation is regex-solvable; aggregation is not |
| Faithfulness / abstention | **Keep — highest value per unit of effort** | Cheapest to construct, rarest in the literature |
| *(new)* Attribution: proposed vs imposed | **Add** | The one task the corpus makes hard for free |

Final suite: **five tasks.** T1 extraction, T2 charge prediction, T3 numeric aggregation, T4 abstention, T5 attribution.

---

## 3. Tasks that survive

### T1 — Structured extraction *(anchor)*

**Input:** full order text (plain text, as extracted). **Output:** JSON.

```json
{
  "noticees": [
    {"name": "Omprakash Basantlal Goenka", "noticee_no": 2,
     "penalty_inr": 3500000, "charging_section": "15HA"}
  ],
  "violated_provisions": ["PFUTP Regulations 3(a)", "PFUTP Regulations 4(1)"],
  "penalty_type": "monetary",
  "total_penalty_inr": 8500000
}
```

**Scoring:** micro-F1 over `(noticee_name, penalty_inr, charging_section)` triples, names matched by normalised string equality after honorific/punctuation stripping. Set-F1 for `violated_provisions`. Exact match for `penalty_type`. Report per-field, never a single blended number.

**Fields I cut, and why — both are regex-solvable, and your own rule says cut them:**

- `order_date` — appears as `Date: July 22, 2026` in a fixed signature block, *and* is already present in the listing metadata. Zero information.
- `adjudicating_officer` — the name is the token span between `Date:` and `Place:`, immediately preceding `ADJUDICATING OFFICER`. Verbatim from four different orders:
  > `Date: July 22, 2026 JAI SEBASTIAN Place: Mumbai ADJUDICATING OFFICER`
  > `Date: July 17, 2026 MEDHA SONPAROTE Place: Mumbai ADJUDICATING OFFICER`
  > `DATE: July 15, 2026 MEDHA SONPAROTE PLACE: MUMBAI ADJUDICATING OFFICER`

  A six-line regex solves it. Keep both fields in the *dataset* as metadata — they are useful for slicing results by officer and by year — but do not score them as a task.

**Trivial baseline:** first-currency-amount + first-proper-noun. Cannot be scored yet (no gold labels — see §6), but its failure mode is measured: it disagrees with the operative paragraph on 24% of documents, and on multi-noticee tables it mis-attributes by construction (§1.2).

---

### T2 — Charging-section prediction *(your "section-citation retrieval", reframed)*

**Your version leaks.** "Given the facts of a case, identify the provisions cited" — but SEBI's factual matrix section *names the regulations it is about*. Handing a system the facts section hands it the answer, and you would be scoring string-copying.

**Reframed input:** the factual matrix only (allegations, trading pattern, dates, amounts), with all `regulation`/`section` citation spans masked to `[CITATION]`. **Output:** the charging section(s) under the SEBI Act — `15HA`, `15HB`, `15EA`, `15EB`, `15A(a)`, `15G` — plus the regulation family (PFUTP / PIT / LODR / SAST / AIF / …).

**Scoring:** macro-F1 over the label set (macro, because the distribution is skewed and micro would reward always guessing `15HB`).

**Trivial baseline, and a warning:** majority class = `15HB`, which is 27 of ~65 observed section mentions. A majority-class baseline will be *strong* — likely 30–40% accuracy. This must be published prominently or the task looks more impressive than it is. If, once the gold set is built, the best system cannot clear majority-class by a wide margin, **this task should be cut.** I am flagging that now rather than discovering it in Phase 4.

---

### T3 — Numeric reasoning *(narrowed)*

Pure lakh/crore normalisation **is** a regex, so it is not a task on its own. What survives is aggregation and cross-channel verification:

- Sum penalties across all noticees in a multi-party order (requires solving §1.2 attribution first).
- Reconcile the numeral against the words: `Rs. 4,00,000/- (Rupees Four Lakh Only)`. Disagreement is a real signal.
- Compliance-window arithmetic: `remit / pay the said amount of penalty within 45 days of receipt of this order` → a date, given the order date.

**Input:** order text + a templated question. **Output:** a single integer (rupees) or ISO date. **Scoring:** exact match. No partial credit — a penalty total is either right or wrong.

**Trivial baseline:** sum of all currency amounts in the document. This will be badly wrong, because it sums quoted submissions, precedent citations and trade values along with the penalty. That is the point.

---

### T4 — Faithfulness / abstention

**Keep. This is the highest-value task in the suite and the cheapest to build correctly.**

Constructed, never invented: take a real order, ask about a field the document genuinely does not contain, and the gold answer is `not stated`. Because the answer is defined by absence, it is verifiable by a second reader without judgement calls — which is exactly what makes it robust under a single annotator.

**Input:** order text + question. **Output:** an answer or the literal string `not stated`.
**Scoring:** report **two numbers, never averaged** — accuracy on answerable questions, and abstention rate on unanswerable ones. A system that abstains on everything scores 100% on one and 0% on the other, and the pair makes that immediately visible.

**Design rule:** unanswerable questions must be *plausible*, drawn from fields that appear in other orders but not this one — e.g. asking for a disgorgement amount in an order that imposes only a monetary penalty. Questions about things SEBI orders never contain are trivially rejectable and measure nothing.

---

### T5 — Attribution: proposed vs imposed *(new — I am adding this)*

The corpus hands us a hard task for free. Orders quote, at length: the noticee's own settlement proposals (§1.3), penalties from cited precedent, and SCN-proposed amounts — all in identical currency phrasing to the operative finding. Distinguishing *what the AO actually ordered* from *what somebody asked for* is a discourse-level judgement that no amount of pattern matching reaches.

**Input:** order text + a highlighted currency span. **Output:** one of `imposed` / `proposed_by_noticee` / `cited_precedent` / `scn_proposed` / `other`.
**Scoring:** macro-F1.
**Trivial baseline:** "always `imposed`". Measurably wrong on ≥24% of documents (§1.3) and probably more once every currency span in a document is enumerated rather than just the first.

This task is the reason the benchmark is not solvable by a better regex, and it is where I would expect frontier models to beat open models by the widest margin.

---

## 4. Multi-hop: cut from v1, and the numbers say so

Your instinct is right that multi-hop is where RAG and GraphRAG separate. It is not viable at this corpus size, and I would rather say so than ship a task with no signal.

Measured over the 25 orders: **133 distinct person/entity mentions, of which 9 appear in more than one document.** Those 9 are not independent — they come from a single matter family (the Illiquid Stock Options at BSE proceedings, which generated several near-identical single-noticee orders plus a corrigendum cross-referencing them). A "which entities appear in more than one PFUTP order" question over this corpus has **essentially one answer, and it is a formatting artifact of one matter.**

Multi-hop needs cross-*matter* entity recurrence, which needs enough documents for the same broker, promoter or fund to appear in genuinely unrelated proceedings. My estimate is **≥2,000 orders spanning ≥5 years** before the task carries signal.

**Recommendation:** ship v1 with five tasks. Add multi-hop in v1.1 once the corpus supports it. Say plainly in the dataset card that it was deferred for lack of cross-document entity density, and give the 9/133 number. Naming this is more credible than shipping a degenerate task.

This also means: **`corpgraph-rag` cannot be meaningfully evaluated by v1 of this benchmark.** The task where it should earn its complexity is the one that isn't ready. Worth knowing before you plan Phase 4.

---

## 5. Legal position (implemented, not just stated)

SEBI orders are public documents, but they contain substantial personal data — named individuals, PAN references, addresses, and in this sample several deceased persons (`Late Ms. Anju Rani`, `Late Padma Singhwani`, `Late Sudha V Thakkar`), whose legal heirs are named as noticees.

**Position taken: distribute document IDs, source URLs, and the fetch script — not raw order text.** `.gitignore` already excludes `data/*.db`. Anyone can reconstruct the corpus byte-identically from SEBI's own servers with one command. This sidesteps redistribution questions entirely, keeps SEBI as the authoritative source, and means the dataset card does not have to make a claim about Indian copyright in government works that I am not qualified to make.

Cost: reproducibility depends on SEBI keeping URLs live. Mitigation: publish a SHA-256 per document so drift is detectable.

Open question for you: **the gold labels themselves contain personal data** (noticee names are literally the labels for T1). Distributing labels means distributing names. My recommendation is to publish them — they are already public, and a benchmark with hashed names is useless — but state it explicitly in the card and provide a takedown contact.

---

## 6. What I did not do

- **No labels.** Not one. Your constraint says you hand-label the gold set; I have not pre-empted that, and nothing in this document is a label.
- **No baseline scores.** Scores require gold labels. I report only what is measurable without them: the 24% first-vs-operative disagreement, the 9/133 entity overlap, the surface-form counts. Those are properties of the corpus, not of any system.
- **No mass scrape.** I fetched exactly the 25 orders already in your listing DB (~50 requests). Expanding the corpus means hours of crawling a government site — your call, not mine to make while you're away.

---

## 7. Critical path

The gold set is not the long pole. **The corpus is.**

1. **Fix listing pagination** in `scrape.py` — SEBI drives paging through a `searchFormNewsList('n', <page>)` JS call, not a Next anchor. Needs the POST/param form reverse-engineered.
2. **Decide crawl scope.** 400–600 gold examples needs ~1,500–2,000 fetched orders to stratify across year, order type and penalty magnitude, and to find enough multi-noticee orders (currently 3 in 25 ≈ 12%). At 1.5 s/request × 2 requests/order that is **~2 hours of crawling and several hundred MB.** Needs your go-ahead and a `--db` path outside the repo.
3. **Filter by document type.** The listing mixes corrigenda and settlement orders with adjudication orders. One corrigendum is already in the sample (1 page, 1,090 chars) — it has no penalty and would poison T1 as an unlabellable outlier. Adjudication orders only for v1.
4. Then Phase 2: labelling CLI, annotation guidelines, gold set.

**Recommended sequence:** fix pagination → crawl ~2,000 → stratify → build labelling CLI → hand-label 50 → *revise these task definitions against what labelling actually teaches you* → label the rest. Task definitions written before anyone has labelled 50 examples are always wrong somewhere; the cheap time to find out is at 50, not at 500.

---

## 8. Open questions for you

1. **Crawl scope** — go-ahead for ~2,000 orders, and where should the DB live?
2. **Personal data in labels** — publish noticee names (my recommendation) or pseudonymise?
3. **Multi-hop deferral** — accept cutting it from v1, or expand the corpus first and keep six tasks?
4. **T2 survival condition** — do you accept the rule that charging-section prediction gets cut if it can't beat majority-class by a clear margin?
