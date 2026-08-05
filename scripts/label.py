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
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DB = REPO / "data" / "corpus.db"
LABELS = REPO / "labels"
DECISIONS = LABELS / "decisions.jsonl"


def operative_window(text: str, width: int = 1400) -> str:
    """The paragraph where the penalty is actually imposed.

    Anchored on the last 'hereby impose' - orders quote the noticee's own
    settlement pleas earlier in identical phrasing, so the *last* occurrence is
    the operative one far more often than the first.
    """
    flat = re.sub(r"\s+", " ", text)
    i = flat.lower().rfind("hereby impose")
    if i < 0:
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
    print("\n--- operative window (read it; nothing below is pre-filled) ---")
    print(operative_window(row["text"]))
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

    # In --redo the point is to re-label what was already done, a week later.
    pool = [r for r in rows if (r["url"] in done) == bool(args.redo)]
    if args.redo:
        first = {json.loads(l)["id"] for l in (LABELS / f"{args.task}.jsonl").read_text(
            encoding="utf-8").splitlines() if l.strip()} if (LABELS / f"{args.task}.jsonl").exists() else set()
        pool = [r for r in rows if r["url"] in first and r["url"] not in done]

    print(f"{len(pool)} orders available, {len(done)} already in {out_path.name}")
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
