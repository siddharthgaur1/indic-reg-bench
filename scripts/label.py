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
import re
import sqlite3
import sys
import textwrap
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from task_viability import (  # noqa: E402
    NONE_IMPOSED, PROSE, TABLE, UNCLASSIFIED, WASTE, classify,
)

REPO = Path(__file__).resolve().parent.parent
DB = REPO / "data" / "corpus.db"
LABELS = REPO / "labels"
DECISIONS = LABELS / "decisions.jsonl"

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
    r"hereby\s+impose|without\s+impos(?:ing|ition\s+of)|"
    r"(?:stands?|are|is)\s+disposed\s+of|no\s+penalty\s+is\s+(?:being\s+)?impos",
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


def log_decision(rec: dict) -> None:
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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", default="t1", choices=["t1"])
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
    args = ap.parse_args()

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

    for row in pool[: args.limit]:
        rec = label_t1(row, notes)
        if rec == "QUIT":
            break
        if rec is None:
            log_decision({"ts": datetime.now(timezone.utc).isoformat(),
                          "id": row["url"], "action": "skip"})
            continue
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
