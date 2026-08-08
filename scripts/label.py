"""
Labelling CLI for the gold set.

Shows one order at a time with the operative paragraph pre-located, takes your
labels, and logs every decision with a timestamp. It **suggests** nothing for
the fields that matter: pre-filling a penalty amount from a regex would bias the
label toward whatever the regex found, which is the exact failure the benchmark
exists to measure. Candidate spans are shown as *context to read*, never as a
default to accept.

    python scripts/label.py --task t1                 # label extraction
    python scripts/label.py --task t1 --redo          # second pass, for agreement
    python scripts/label.py --stats

Every decision is appended to `labels/decisions.jsonl` (never rewritten), so the
annotation guidelines can be reconstructed from what actually happened.
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sqlite3
import sys
import textwrap
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from indic_reg_bench.numerals import CURRENCY  # noqa: E402
from task_viability import (  # noqa: E402
    NONE_IMPOSED, PROSE, TABLE, UNCLASSIFIED, WASTE, classify,
)

REPO = Path(__file__).resolve().parent.parent
DB = REPO / "data" / "corpus.db"
LABELS = REPO / "labels"
DECISIONS = LABELS / "decisions.jsonl"
# Scratch copies of order text for the labeller to search. Order text is not
# redistributed from this repo, so this directory is gitignored.
READING = LABELS / ".reading"

# What each bucket means for the person reading the document. Shown as a banner
# so nobody spends ten minutes hunting for a penalty in an order that imposes
# none, or labels a scrambled table from the text and gets the wrong noticee.
BANNER = {
    PROSE: ("", "Penalty is stated in prose. The window below should contain it."),
    NONE_IMPOSED: (
        "NO PENALTY IMPOSED",
        "This order closes without a monetary penalty - abated on death, or the "
        "SCN disposed of without imposition. That is the label. Record "
        "penalty_type and move on; do not hunt for an amount.",
    ),
    TABLE: (
        "PENALTY IS IN A TABLE - OPEN THE PDF",
        "Text extraction scrambles penalty table columns: the amount lands "
        "before the noticee number, which lands before the name. Labelling "
        "noticee-to-penalty from the text below will attribute it to the wrong "
        "person. Open the source PDF.",
    ),
    UNCLASSIFIED: (
        "UNRECOGNISED DISPOSITION",
        "No operative paragraph matched and no known no-penalty phrasing. Read "
        "the end of the document before labelling, and note what it says - "
        "these are how the classifier gets fixed.",
    ),
}


DISPOSITION = re.compile(
    r"hereby\s+impose|\bI\s+impose\b|"
    r"impos\w+\s+(?:a\s+)?(?:consolidated\s+|monetary\s+|total\s+|combined\s+)?"
    r"penalty\s+of|"
    r"hereby\s+dispose\s+of|without\s+impos(?:ing|ition\s+of)|"
    r"(?:stands?|are|is)\s+disposed\s+of|no\s+penalty\s+is\s+(?:being\s+)?impos|"
    r"not\s+liable\s+(?:for|to)\s+(?:any\s+)?(?:monetary\s+)?penalt",
    re.I,
)


PENALTY_IN_WORDS = re.compile(r"\(\s*Rupees\s+[A-Z]", re.I)


def operative_window(text: str, bucket: str | None = None, width: int = 1400) -> str:
    """The paragraph where the order actually disposes of the proceeding.

    Anchored on the *last* disposition phrase - orders quote the noticee's own
    settlement pleas earlier in identical phrasing, so the last occurrence is
    the operative one far more often than the first.

    Anchoring on `hereby impose` alone missed every order that closes without a
    penalty, which is one document in six, and silently fell back to the last
    1,400 characters - the signature block and page footer. Those documents got
    a window containing nothing relevant at all.

    Table-scrambled orders need a different anchor entirely. Their operative
    text is inside a table, so the last *prose* disposition phrase is usually
    the noticee's own quoted plea to drop the SCN - which reads exactly like a
    disposition and is the opposite of one. For those, anchor on the amount in
    words, which is where the table is.
    """
    flat = re.sub(r"\s+", " ", text)
    if bucket == TABLE:
        hits = list(PENALTY_IN_WORDS.finditer(flat))
        if hits:
            return flat[max(0, hits[0].start() - 700): hits[-1].end() + 700]
    hits = list(DISPOSITION.finditer(flat))
    if hits:
        i = hits[-1].start()
    else:
        i = flat.lower().rfind("penalty of")
    if i < 0:
        return flat[-width:]
    return flat[max(0, i - 200): i + width]


# Set by --dry-run. Exercising this CLI with piped input writes whatever the
# pipe contained into the gold set, and four such rows reached a public commit
# before anyone noticed. A gold set is only worth what its worst row is worth,
# so the smoke-test path must be structurally incapable of writing one.
DRY_RUN = False


def log_decision(rec: dict) -> None:
    if DRY_RUN:
        return
    LABELS.mkdir(parents=True, exist_ok=True)
    with DECISIONS.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def ask(prompt: str, allow_empty: bool = True) -> str:
    try:
        v = input(f"  {prompt}: ").strip()
    except EOFError:
        raise SystemExit("\ninput closed - progress is saved")
    if v == "?" :
        print("     [enter '-' to mark not-stated, 'skip' to defer, 'quit' to stop]")
        return ask(prompt, allow_empty)
    if not v and not allow_empty:
        return ask(prompt, allow_empty)
    return v


def label_t1(row: sqlite3.Row, notes: list[str]) -> dict | None:
    """Structured extraction. Noticee-by-noticee, so multi-party orders are
    labelled as the linked triples they are rather than three flat lists."""
    print("\n" + "=" * 78)
    print(f"  {row['title'][:74]}")
    print(f"  {row['order_date']}   {row['n_pages']}p   {row['url'][:70]}")
    print("=" * 78)

    bucket = classify(row["title"], len(row["text"] or ""), row["text"])
    headline, guidance = BANNER.get(bucket, ("", ""))
    if headline:
        print(f"\n  !! {headline}")
    if guidance:
        for line in textwrap.wrap(guidance, 74):
            print(f"     {line}")

    print("\n--- operative window (read it; nothing below is pre-filled) ---")
    print(operative_window(row["text"], bucket))
    print("--- end window ---\n")

    cmd = ask("[enter]=label  s=skip  q=quit")
    if cmd.lower().startswith("q"):
        return "QUIT"  # type: ignore[return-value]
    if cmd.lower().startswith("s"):
        return None

    # 13.1% of single-noticee orders impose more than one penalty - separate
    # amounts under separate sections on the same person. The scoring unit is
    # the (name, amount, section) triple, so those are several rows for one
    # name, and the prompt has to say so or they get silently collapsed to one.
    print("  one row per (noticee, penalty, section) triple - enter the same")
    print("  name again if the order penalises them under more than one section")
    noticees = []
    while True:
        n = len(noticees) + 1
        name = ask(f"noticee {n} name (blank=done)")
        if not name:
            break
        pen = ask(f"  penalty in rupees, digits only (- if none)")
        sec = ask(f"  charging section e.g. 15HB (- if none)")
        noticees.append({
            "name": name,
            "penalty_inr": None if pen in ("", "-") else int(re.sub(r"[^\d]", "", pen) or 0),
            "charging_section": None if sec in ("", "-") else sec.upper(),
        })

    provisions = [p.strip() for p in ask("violated provisions, comma-separated").split(",") if p.strip()]
    ptype = ask("penalty type [monetary/debarment/warning/none/other]")
    note = ask("note - ambiguity and how you resolved it (blank=none)")
    if note:
        notes.append(f"{row['url']}: {note}")

    total = sum(n["penalty_inr"] or 0 for n in noticees)
    return {
        "id": row["url"],
        "order_date": row["order_date"],
        "gold": {
            "noticees": noticees,
            "violated_provisions": provisions,
            "penalty_type": ptype or None,
            "total_penalty_inr": total,
        },
        "note": note or None,
    }


AMOUNT = re.compile(
    CURRENCY + r"\s?[\d][\d,]*(?:\.\d+)?(?:\s*(?:/-|lakhs?|lacs?|crores?))?",
    re.I,
)

# Cues used ONLY to spread the sample across the label space. They are never
# shown and never written: a labeller told "this one looks like a precedent"
# will agree with it, and T5 exists precisely to measure whether that
# distinction can be made from the discourse rather than from a nearby keyword.
T5_CUES = {
    "disposition": re.compile(
        r"hereby\s+impose|in\s+exercise\s+of\s+(?:the\s+)?powers?|"
        r"impose\s+a\s+penalty\s+of", re.I),
    "submission": re.compile(
        r"noticee\s+(?:has\s+)?(?:submitted|requested|prayed|contended)|"
        r"my\s+client|willingness\s+to\s+settle|settlement\s+(?:scheme|application)|"
        r"lenient\s+view", re.I),
    "precedent": re.compile(
        r"hon.?ble\s+(?:SAT|Supreme\s+Court|High\s+Court)|"
        r"securities\s+appellate\s+tribunal|it\s+was\s+held|"
        r"v(?:s|s\.|\.)\s+SEBI|appeal\s+no", re.I),
    "scn": re.compile(
        r"show\s+cause\s+notice|\bSCN\b|was\s+called\s+upon\s+to\s+show", re.I),
}

T5_CLASSES = {
    "i": "imposed",
    "p": "proposed_by_noticee",
    "c": "cited_precedent",
    "s": "scn_proposed",
    "o": "other",
}


def t5_spans(text: str, per_doc: int, context: int = 380) -> list[dict]:
    """Pick a spread of currency spans from one order, with surrounding context.

    Orders carry a median of 5 currency amounts and a p90 of 34, so labelling
    every span is not on. Sampling the first N is worse than useless: the early
    amounts cluster in the facts section and would make the gold set almost
    entirely one class.

    So spans are grouped by which cue appears near them and sampled
    round-robin across those groups. The grouping is a *sampling* device only
    - it never reaches the labeller, because a displayed guess is a guess the
    labeller will agree with.
    """
    flat = re.sub(r"\s+", " ", text)
    groups: dict[str, list[dict]] = defaultdict(list)

    for m in AMOUNT.finditer(flat):
        lo, hi = max(0, m.start() - context), min(len(flat), m.end() + context)
        window = flat[lo:hi]
        cue = next((name for name, pat in T5_CUES.items() if pat.search(window)),
                   "none")
        groups[cue].append({
            "span": m.group(0).strip(),
            "char_start": m.start(),
            "context": window,
        })

    # Round-robin so every cue group is represented before any is doubled up.
    picked: list[dict] = []
    order = [k for k in ("disposition", "submission", "precedent", "scn", "none")
             if k in groups]
    i = 0
    while len(picked) < per_doc and order:
        cue = order[i % len(order)]
        if groups[cue]:
            picked.append(groups[cue].pop(0))
        else:
            order.remove(cue)
            continue
        i += 1
    return picked


def label_t5(row: sqlite3.Row, notes: list[str], per_doc: int) -> dict | None:
    """Attribution: is this amount what was ordered, or what somebody asked for?

    One record per document holding several labelled spans, so the span's
    position in the order is preserved and a second pass can be compared
    span-by-span.
    """
    spans = t5_spans(row["text"], per_doc)
    if not spans:
        return None

    print("\n" + "=" * 78)
    print(f"  {row['title'][:74]}")
    print(f"  {row['order_date']}   {row['n_pages']}p   {len(spans)} spans to attribute")
    print(f"  {row['url'][:74]}")
    print("=" * 78)

    cmd = ask("[enter]=label  s=skip  q=quit")
    if cmd.lower().startswith("q"):
        return "QUIT"  # type: ignore[return-value]
    if cmd.lower().startswith("s"):
        return None

    labelled = []
    for n, sp in enumerate(spans, 1):
        print(f"\n  --- span {n}/{len(spans)}: {sp['span']} ---")
        for line in textwrap.wrap(sp["context"], 74):
            print(f"    {line}")
        print("\n    i=imposed  p=proposed by noticee  c=cited precedent")
        print("    s=SCN proposed  o=other  x=skip this span")
        while True:
            v = ask("attribution").lower()[:1]
            if v == "x":
                break
            if v in T5_CLASSES:
                labelled.append({
                    "span": sp["span"],
                    "char_start": sp["char_start"],
                    "attribution": T5_CLASSES[v],
                })
                break
            print("     enter one of i / p / c / s / o / x")

    if not labelled:
        return None

    note = ask("note - ambiguity and how you resolved it (blank=none)")
    if note:
        notes.append(f"{row['url']}: {note}")

    return {
        "id": row["url"],
        "order_date": row["order_date"],
        "gold": {"spans": labelled},
        "note": note or None,
    }


# T4 questions are templated, never invented per document, so that whether an
# item is answerable is a property of the order rather than of the question
# writer. Prevalence is measured over 1,290 fetched orders and is what makes an
# unanswerable item *plausible*: a question about disgorgement is a question
# SEBI does answer in one order out of five, so declining it requires reading
# this order rather than knowing the genre.
T4_QUESTIONS = [
    ("penalty_amount", 0.99,
     "What monetary penalty was imposed on the noticee?"),
    ("charging_section", 0.97,
     "Under which section of the SEBI Act was the penalty imposed?"),
    ("payment_deadline", 0.78,
     "Within how many days of receiving this order must the penalty be paid?"),
    ("regulations", 0.70,
     "Which regulations was the noticee found to have violated?"),
    ("recovery_interest", 0.41,
     "What happens if the noticee fails to pay within the stated period?"),
    ("disgorgement", 0.19,
     "What amount was the noticee directed to disgorge?"),
    ("debarment", 0.05,
     "For how long was the noticee debarred from the securities market?"),
]


def t4_questions(url: str, per_doc: int) -> list[tuple[str, float, str]]:
    """Pick a stable, mixed set of questions for one order.

    Deterministic in the document URL so a second labelling pass sees the same
    questions and the two passes stay comparable span-for-span.

    Half the questions come from high-prevalence fields and half from
    low-prevalence ones. Sampling uniformly would make almost every item
    answerable, and a T4 set that is 90% answerable measures nothing about
    abstention. Prevalence is a property of the *field* across the corpus, not
    of this document, so using it to choose questions reveals nothing about
    this order's answers.
    """
    rng = random.Random(url)
    common = [q for q in T4_QUESTIONS if q[1] >= 0.5]
    rare = [q for q in T4_QUESTIONS if q[1] < 0.5]
    rng.shuffle(common)
    rng.shuffle(rare)
    want_rare = max(1, per_doc // 2)
    picked = rare[:want_rare] + common[: per_doc - want_rare]
    rng.shuffle(picked)
    return picked


def label_t4(row: sqlite3.Row, notes: list[str], per_doc: int) -> dict | None:
    """Faithfulness / abstention: does this order answer the question at all?

    The labeller records the answer or marks it absent. Absence is the label,
    which is why a second reader can check it without a judgement call - the
    property being labelled is a fact about the document, not an opinion.
    """
    print("\n" + "=" * 78)
    print(f"  {row['title'][:74]}")
    print(f"  {row['order_date']}   {row['n_pages']}p   {row['url'][:70]}")
    print("=" * 78)
    # T4 labels absence, so a window is actively harmful here: it makes
    # "not stated" easy to answer wrongly. Give the labeller the whole document
    # in something they can search rather than a fragment they can skim.
    reading = READING / (re.sub(r"\W+", "_", row["url"])[-80:] + ".txt")
    if not DRY_RUN:
        READING.mkdir(parents=True, exist_ok=True)
        reading.write_text(re.sub(r"[ \t]+", " ", row["text"]), encoding="utf-8")
        print(f"\n  full text for searching: {reading}")
    print("  An item is 'not stated' only if the WHOLE order is silent on it -")
    print("  search the file above before answering '-'.")

    cmd = ask("[enter]=label  s=skip  q=quit")
    if cmd.lower().startswith("q"):
        return "QUIT"  # type: ignore[return-value]
    if cmd.lower().startswith("s"):
        return None

    items = []
    for key, _prevalence, question in t4_questions(row["url"], per_doc):
        print(f"\n  Q: {question}")
        ans = ask("answer, or '-' if the order does not state it")
        if ans.lower() in ("skip", "x"):
            continue
        answerable = ans.strip() not in ("", "-")
        items.append({
            "field": key,
            "question": question,
            "answerable": answerable,
            "gold_answer": ans.strip() if answerable else "not stated",
        })

    if not items:
        return None

    note = ask("note - ambiguity and how you resolved it (blank=none)")
    if note:
        notes.append(f"{row['url']}: {note}")

    return {
        "id": row["url"],
        "order_date": row["order_date"],
        "gold": {"items": items},
        "note": note or None,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", default="t1", choices=["t1", "t4", "t5"])
    ap.add_argument("--db", type=Path, default=DB)
    ap.add_argument("--redo", action="store_true",
                    help="re-label already-labelled orders (for self-agreement)")
    ap.add_argument("--limit", type=int, default=50)
    ap.add_argument("--stats", action="store_true")
    ap.add_argument("--bucket", default=None,
                    help="only orders whose triage bucket matches this substring, "
                         "e.g. --bucket table  or  --bucket 'no penalty'")
    ap.add_argument("--keep-waste", action="store_true",
                    help="include corrigenda and scanned PDFs (excluded by default)")
    ap.add_argument("--spans-per-doc", type=int, default=4,
                    help="t5 only: currency spans to attribute per order")
    ap.add_argument("--questions-per-doc", type=int, default=3,
                    help="t4 only: questions to ask per order")
    ap.add_argument("--dry-run", action="store_true",
                    help="exercise the interface without writing any label - "
                         "use this for every smoke test")
    args = ap.parse_args()

    global DRY_RUN
    DRY_RUN = args.dry_run
    if DRY_RUN:
        print("DRY RUN - nothing will be written to the gold set")

    if not args.db.exists():
        print(f"no corpus at {args.db} - run scripts/fetch_orders.py first", file=sys.stderr)
        return 1

    out_path = LABELS / (f"{args.task}_pass2.jsonl" if args.redo else f"{args.task}.jsonl")
    done = set()
    if out_path.exists():
        done = {json.loads(l)["id"] for l in out_path.read_text(encoding="utf-8").splitlines() if l.strip()}

    if args.stats:
        print(f"{args.task}: {len(done)} labelled -> {out_path}")
        if DECISIONS.exists():
            print(f"decisions logged: {sum(1 for _ in DECISIONS.open(encoding='utf-8'))}")
        return 0

    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT url, title, order_date, n_pages, text FROM order_text ORDER BY url").fetchall()
    conn.close()

    # Corrigenda and scanned PDFs carry no label and cost the same time to open
    # as a real order. 46 of the first 1,107 fetched are one or the other.
    if not args.keep_waste:
        before = len(rows)
        rows = [r for r in rows
                if classify(r["title"], len(r["text"] or ""), r["text"]) not in WASTE]
        if before != len(rows):
            print(f"skipping {before - len(rows)} corrigenda / scanned PDFs "
                  f"(--keep-waste to include)")

    # In --redo the point is to re-label what was already done, a week later.
    pool = [r for r in rows if (r["url"] in done) == bool(args.redo)]
    if args.redo:
        first = {json.loads(l)["id"] for l in (LABELS / f"{args.task}.jsonl").read_text(
            encoding="utf-8").splitlines() if l.strip()} if (LABELS / f"{args.task}.jsonl").exists() else set()
        pool = [r for r in rows if r["url"] in first and r["url"] not in done]

    if args.bucket:
        pool = [r for r in pool
                if args.bucket.lower() in
                classify(r["title"], len(r["text"] or ""), r["text"]).lower()]
        print(f"filtered to bucket matching {args.bucket!r}")

    print(f"{len(pool)} orders available, {len(done)} already in {out_path.name}")
    if pool:
        dist = Counter(classify(r["title"], len(r["text"] or ""), r["text"])
                       for r in pool)
        for b, c in dist.most_common():
            print(f"  {c:5}  {b}")
    notes: list[str] = []
    written = 0

    labellers = {
        "t1": lambda r: label_t1(r, notes),
        "t4": lambda r: label_t4(r, notes, args.questions_per_doc),
        "t5": lambda r: label_t5(r, notes, args.spans_per_doc),
    }
    for row in pool[: args.limit]:
        rec = labellers[args.task](row)
        if rec == "QUIT":
            break
        if rec is None:
            log_decision({"ts": datetime.now(timezone.utc).isoformat(),
                          "id": row["url"], "action": "skip"})
            continue
        if not DRY_RUN:
            LABELS.mkdir(parents=True, exist_ok=True)
            with out_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        log_decision({"ts": datetime.now(timezone.utc).isoformat(), "id": row["url"],
                      "action": "label", "pass": 2 if args.redo else 1, "gold": rec["gold"],
                      "note": rec["note"]})
        written += 1

    print(f"\n{written} labelled this session -> {out_path}")
    if notes:
        print("\nnotes to fold into docs/annotation-guidelines.md:")
        for n in notes:
            print(f"  - {n}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
