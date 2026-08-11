"""
Join labels to order text and write the files `evaluate` actually reads.

There was no step that did this. `label.py` writes `labels/t1.jsonl`, which
carries the label and the order id but no text - deliberately, since order text
is not redistributed from this repo. `evaluate --data data/splits/test` reads
`data/splits/test/<task>.jsonl`, which must carry both. Nothing built the
second from the first, and `data/splits/` held only id lists. A hand-labelled
gold set would have been unscoreable until someone wrote this, which is a thing
to find now rather than after two weeks of annotation.

    python scripts/build_eval_set.py --labels labels/t1.jsonl
    python scripts/build_eval_set.py --labels labels/silver/t1.jsonl

Also accepts a predictions file from `run_baseline.py`, in which case the
records are model output and every example is stamped
`label_source: "model:<system>"`. That stamp is not decoration: `evaluate`
reads it and refuses to present the run as a benchmark result.

**Silver is not gold.** A model's labels scored against a model's predictions
measures agreement between two runs of the same thing, and where the labelling
model and the system under test are the same model it measures nothing at all.
Silver exists to exercise the pipeline and to give a human annotator something
to correct - not to fill a leaderboard.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_splits import TEST_FROM_YEAR  # noqa: E402
from label import DB  # noqa: E402

HUMAN = "human"


def read_records(path: Path) -> tuple[list[dict], str]:
    """Labels or predictions - the file says which, rather than the filename."""
    rows = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    if not rows:
        raise SystemExit(f"{path} is empty")

    if "gold" in rows[0]:
        source = HUMAN
        if any(r.get("label_source", HUMAN) != HUMAN for r in rows):
            source = next(r["label_source"] for r in rows
                          if r.get("label_source", HUMAN) != HUMAN)
        return [{"id": r["id"], "gold": r["gold"], "source": r.get("label_source", source)}
                for r in rows], source

    if "prediction" in rows[0]:
        system = rows[0].get("system", "unknown")
        source = f"model:{system}"
        kept = [r for r in rows if not r.get("error") and r.get("prediction") is not None]
        if len(kept) != len(rows):
            print(f"dropping {len(rows) - len(kept)} records with errors or no prediction")
        return [{"id": r["id"], "gold": r["prediction"], "source": source}
                for r in kept], source

    raise SystemExit(f"{path}: records have neither 'gold' nor 'prediction'")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--labels", type=Path, required=True)
    ap.add_argument("--task", default="t1_extraction")
    ap.add_argument("--db", type=Path, default=DB)
    ap.add_argument("--out", type=Path, default=None,
                    help="default: data/splits/<split>/<task>.jsonl, split inferred "
                         "from each order's date")
    args = ap.parse_args()

    records, source = read_records(args.labels)
    print(f"{len(records)} labels from {args.labels}  (label_source: {source})")

    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row
    text_by_id = {r["url"]: (r["text"], r["order_date"]) for r in
                  conn.execute("SELECT url, text, order_date FROM order_text")}
    conn.close()

    missing = [r["id"] for r in records if r["id"] not in text_by_id]
    if missing:
        print(f"WARNING: {len(missing)} labelled orders have no fetched text; skipped")

    by_split: dict[str, list[dict]] = {"train": [], "test": []}
    for r in records:
        if r["id"] not in text_by_id:
            continue
        text, order_date = text_by_id[r["id"]]
        split = "test" if int(order_date[:4]) >= TEST_FROM_YEAR else "train"
        by_split[split].append({
            "id": r["id"], "order_date": order_date, "text": text,
            "gold": r["gold"], "label_source": r["source"],
        })

    for split, rows in by_split.items():
        if not rows:
            continue
        out = args.out or (REPO / "data" / "splits" / split / f"{args.task}.jsonl")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n",
                       encoding="utf-8")
        print(f"  {split}: {len(rows)} examples -> {out}")

    if source != HUMAN:
        print(f"\n  These labels came from {source}. `evaluate` will mark any run "
              f"against them as not a benchmark result.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
