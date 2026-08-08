"""
Viability checks for the two tasks that Phase 1 left conditional.

Phase 1 deferred multi-hop and put T2 on probation, both on evidence from 25
documents. Both conditions were written as measurable, so they are measured
here rather than argued:

  * multi-hop needs the same noticee to appear across *different matters*.
    Phase 1 measured 9 of 133 entities recurring and found all 9 came from one
    matter family, which is an artifact rather than signal. That is now
    recomputed over the full 11,957-order listing.

  * T2 gets cut if a system cannot beat the majority charging section by a
    wide margin. That needs the label prior, which needs the gold set - but an
    *estimate* of the prior can be read off the operative paragraph, which is
    enough to know whether the task starts out degenerate.

Nothing here is a label or a score. The charging sections read out of the
operative paragraph are a regex estimate of the prior, explicitly not gold,
and are never written to disk as labels.

    python scripts/task_viability.py
"""

from __future__ import annotations

import argparse
import re
import sqlite3
from collections import Counter, defaultdict
from pathlib import Path

DB = Path(__file__).resolve().parent.parent / "data" / "corpus.db"

# "Adjudication Order in respect of <noticee> in the matter of <matter>"
# Both halves are optional: many orders name only the matter.
TITLE = re.compile(
    r"^adjudication\s+order\s*"
    r"(?:in\s+respect\s+of\s+(?P<noticee>.+?))?"
    r"(?:\s*in\s+the\s+matter\s+of\s+(?P<matter>.+?))?\s*$",
    re.I,
)

# The operative paragraph names the charging section within a short window of
# "hereby impose". 15J is the mitigating-factors provision and never a charge.
OPERATIVE = re.compile(r"hereby\s+impose", re.I)
SECTION = re.compile(r"section\s+(15[A-Z]{1,2}(?:\([a-z]\))?)", re.I)

# 321 titles say "in respect of 4 entities" or "in respect of three entities"
# instead of naming anyone. These are not entity names, and counting them as
# such invents recurrence that does not exist - "4 entities" appeared to span
# 27 matters on the first run of this script.
COLLECTIVE = re.compile(
    r"^(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|"
    r"thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty\S*|"
    r"several|various|certain)\s+"
    r"(?:entities|noticees|persons|individuals|companies|firms|others)\b",
    re.I,
)

NOISE = re.compile(r"[^a-z0-9 ]+")
SUFFIXES = (
    " private limited", " pvt ltd", " pvt limited", " limited", " ltd",
    " llp", " inc", " corporation", " company", " co",
)
# Written post-NOISE: 'M/s.' has already become 'm s' by the time these apply,
# so the list must spell it that way or the prefix survives forever.
HONORIFICS = ("mr ", "mrs ", "ms ", "shri ", "sri ", "smt ", "late ", "dr ",
              "m s ", "messrs ")


def normalise(name: str) -> str:
    """Fold an entity name hard enough that 'M/s Foo Pvt. Ltd.' == 'Foo Limited'.

    Deliberately aggressive: this is used to look for recurrence, so the cost of
    over-merging is a *higher* recurrence count. If the count stays near zero
    under aggressive folding, the negative result is solid.

    Both strippers loop to a fixed point. Titles stack these - 'Late Ms. Anju
    Rani' carries two honorifics and 'Foo Pvt Ltd' two suffixes - and a single
    pass leaves whichever one the tuple happened to test first.
    """
    s = NOISE.sub(" ", name.lower())
    s = re.sub(r"\s+", " ", s).strip()
    changed = True
    while changed:
        changed = False
        for h in HONORIFICS:
            if s.startswith(h):
                s, changed = s[len(h):].strip(), True
        for suf in SUFFIXES:
            if s.endswith(suf):
                s, changed = s[: -len(suf)].strip(), True
    return s


def matter_key(matter: str) -> str:
    """Collapse the spelling variants of one matter family into a single key.

    The illiquid-stock-options proceedings alone appear as at least six
    spellings ('Illiquid Stock Options on BSE', 'at BSE', 'dealings in
    Illiquid Stock Options at the BSE', 'Illiquid Options on the BSE', ...).
    Left uncollapsed, one noticee in two spellings of the *same* matter reads
    as cross-matter recurrence, which is the exact artifact this measurement
    exists to avoid. Stopwords go first, then the known family is folded whole.
    """
    s = NOISE.sub(" ", matter.lower())
    s = re.sub(r"\s+", " ", s).strip()
    s = re.sub(r"^(?:trading|dealing|dealings)\s+in\s+", "", s)
    s = re.sub(r"^the\s+", "", s)
    s = re.sub(r"\b(?:at|on|in)\s+the\s+bse\b", "bse", s)
    s = re.sub(r"\b(?:at|on|in)\s+bse\b", "bse", s)
    # One family, one key.
    if "illiquid" in s and ("option" in s or "stock" in s):
        return "illiquid stock options bse"
    # Matters are usually named after a company, so they carry the same 'M/s'
    # and 'Pvt Ltd' variation as noticee names. Without this, 'M/s KRBL Ltd'
    # and 'KRBL Ltd' are two matters and every noticee in both looks
    # cross-matter.
    return normalise(s)


def parse_title(title: str) -> tuple[str | None, str | None]:
    m = TITLE.match(title.strip())
    if not m:
        return None, None
    noticee, matter = m.group("noticee"), m.group("matter")
    if noticee and COLLECTIVE.match(noticee.strip()):
        noticee = None
    return (
        normalise(noticee) if noticee else None,
        matter_key(matter) if matter else None,
    )


def multi_hop_viability(conn: sqlite3.Connection) -> None:
    rows = conn.execute(
        "SELECT title FROM listing WHERE doc_type = 'adjudication'").fetchall()

    matters_by_entity: dict[str, set[str]] = defaultdict(set)
    docs_by_entity: Counter[str] = Counter()
    unparsed = 0

    for (title,) in rows:
        noticee, matter = parse_title(title)
        if not noticee:
            unparsed += 1
            continue
        docs_by_entity[noticee] += 1
        matters_by_entity[noticee].add(matter or "(unspecified)")

    entities = len(docs_by_entity)
    multi_doc = sum(1 for n, c in docs_by_entity.items() if c > 1)
    cross_matter = {n: m for n, m in matters_by_entity.items() if len(m) > 1}

    print("=== multi-hop viability ===")
    print(f"adjudication orders            {len(rows):,}")
    print(f"  titles naming a noticee      {len(rows) - unparsed:,}")
    print(f"  titles naming no one         {unparsed:,}  "
          f"(no 'in respect of', or 'in respect of N entities')")
    print(f"distinct noticees (normalised) {entities:,}")
    print(f"  appearing in >1 order        {multi_doc:,} ({multi_doc / entities:.1%})")
    print(f"  appearing in >1 MATTER       {len(cross_matter):,} "
          f"({len(cross_matter) / entities:.1%})   <- the number that decides the task")
    print()
    print("Recurrence inside a single matter is a formatting artifact: SEBI issues")
    print("near-identical orders per noticee in one proceeding. Only cross-matter")
    print("recurrence supports a multi-hop question with a non-trivial answer.")
    print()
    if cross_matter:
        print("top cross-matter entities:")
        for name, matters in sorted(
                cross_matter.items(), key=lambda kv: -len(kv[1]))[:15]:
            print(f"  {name[:44]:46} {len(matters)} matters, "
                  f"{docs_by_entity[name]} orders")
    print()

    matter_sizes = Counter()
    for matters in matters_by_entity.values():
        for m in matters:
            matter_sizes[m] += 1
    print("largest matter families (distinct noticees):")
    for m, c in matter_sizes.most_common(10):
        print(f"  {m[:56]:58} {c}")
    print()


def t2_prior(conn: sqlite3.Connection) -> None:
    rows = conn.execute(
        "SELECT text FROM order_text WHERE text != ''").fetchall()
    if not rows:
        print("=== T2 prior === no fetched text yet")
        return

    per_doc: Counter[str] = Counter()
    no_operative = no_section = 0

    for (raw,) in rows:
        t = re.sub(r"\s+", " ", raw)
        hits = list(OPERATIVE.finditer(t))
        if not hits:
            no_operative += 1
            continue
        # Last "hereby impose" is the operative one; earlier hits are quoted
        # submissions and cited precedent (the T5 premise, same cause).
        window = t[hits[-1].start(): hits[-1].start() + 600]
        secs = {s.upper() for s in SECTION.findall(window)}
        secs.discard("15J")
        secs = {s for s in secs if not s.startswith("15J")}
        if not secs:
            no_section += 1
            continue
        # A document with two charging sections contributes to both; the prior
        # is over labels, not over documents.
        for s in secs:
            per_doc[s] += 1

    total = sum(per_doc.values())
    print("=== T2 charging-section prior (regex estimate, NOT gold) ===")
    print(f"documents with text            {len(rows):,}")
    print(f"  no 'hereby impose' found     {no_operative:,}")
    print(f"  operative para, no section   {no_section:,}")
    print(f"label instances counted        {total:,}")
    print()
    for s, c in per_doc.most_common(12):
        print(f"  {s:10} {c:5}  ({c / total:.1%})")
    if per_doc:
        top, top_n = per_doc.most_common(1)[0]
        print()
        print(f"majority class {top} at {top_n / total:.1%} of label instances.")
        print("Phase 1's cut rule: if the best system cannot clear majority-class by a")
        print("wide margin, T2 ships as a reported baseline, not as a task.")
    print()


CORRIGENDUM = re.compile(r"corrigendum", re.I)
PENALTY_WORDS = re.compile(r"\(\s*Rupees\s+[A-Z]", re.I)
# SEBI closes a proceeding without penalty in at least four phrasings, and the
# nominalised one ("without imposition of") is the most common - missing it put
# 194 documents in an "unclassified" bucket on the previous run.
NO_PENALTY = re.compile(
    r"without\s+impos(?:ing|ition\s+of)\s+(?:any\s+)?(?:monetary\s+)?penalt|"
    r"no\s+penalty\s+is\s+(?:being\s+)?impos|"
    r"not\s+impos\w+\s+any\s+penalt|"
    r"not\s+liable\s+(?:for|to)\s+(?:any\s+)?(?:monetary\s+)?penalt|"
    r"(?:stands?|are|is)\s+disposed\s+of|"
    r"hereby\s+dispose\s+of|"
    r"death\s+certificate|deceased\s+noticee|abate",
    re.I,
)


# Buckets, in the order the classifier tests them. WASTE never reaches a
# labeller; the rest change *how* the document should be read, not whether.
PROSE = "operative paragraph in prose (labellable from text)"
NONE_IMPOSED = "no penalty imposed (a real outcome, not a defect)"
TABLE = "penalty present but table-scrambled (label from PDF)"
UNCLASSIFIED = "unclassified - read before labelling"
SCANNED = "no text layer (scanned PDF, needs OCR)"
CORRIG = "corrigendum (exclude)"
WASTE = (SCANNED, CORRIG)


def classify(title: str, n_chars: int, text: str) -> str:
    """Sort one document by what a labeller can actually do with it.

    Shared with `scripts/label.py`, which uses it to keep waste out of the
    labelling queue and to warn when the penalty is only readable in the PDF.
    """
    t = re.sub(r"\s+", " ", text or "")
    # An image-only PDF extracts to a handful of characters, not zero.
    if n_chars < 200:
        return SCANNED
    if CORRIGENDUM.search(title or "") or CORRIGENDUM.search(t[:400]):
        return CORRIG
    if OPERATIVE.search(t):
        return PROSE
    if PENALTY_WORDS.search(t):
        return TABLE
    if NO_PENALTY.search(t):
        return NONE_IMPOSED
    return UNCLASSIFIED


def triage(conn: sqlite3.Connection) -> None:
    """Report the bucket distribution over everything fetched.

    An earlier version of this script reported "37.8% have no operative
    paragraph" and called them unlabellable. That was wrong twice over. The
    documents are fine; the `hereby impose` probe was not, and "no penalty
    imposed" is a real outcome rather than a defect. Reading the actual
    documents splits that 37.8% into four groups, only two of which are waste.
    """
    rows = conn.execute(
        "SELECT title, n_pages, n_chars, text FROM order_text").fetchall()
    if not rows:
        return

    buckets: Counter[str] = Counter()
    samples: dict[str, list[str]] = defaultdict(list)

    for title, n_pages, n_chars, raw in rows:
        b = classify(title, n_chars, raw)
        buckets[b] += 1
        if len(samples[b]) < 4:
            samples[b].append(f"[{n_pages}p {n_chars:>7,}c] {title[:74]}")

    n = len(rows)
    print("=== what a labeller can do with each fetched document ===")
    print(f"fetched documents              {n:,}")
    for b, c in buckets.most_common():
        print(f"  {b:52} {c:5}  ({c / n:5.1%})")
    print()
    print("Only corrigenda and no-text-layer documents are waste. Table-scrambled")
    print("and no-penalty documents are labellable and carry the most signal:")
    print("the no-penalty group is a ready-made, absence-defined T4 pool, and it")
    print("means `penalty_type` in T1 is a real prediction rather than a constant.")
    print()
    for b in (UNCLASSIFIED, SCANNED):
        if samples.get(b):
            print(f"sample - {b}:")
            for s in samples[b]:
                print(f"  {s}")
            print()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", type=Path, default=DB)
    args = ap.parse_args()

    conn = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    multi_hop_viability(conn)
    t2_prior(conn)
    triage(conn)
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
