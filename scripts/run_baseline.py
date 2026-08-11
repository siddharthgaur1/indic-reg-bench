"""
Run a system over the labelling queue and record what it predicted.

`indic-reg-bench evaluate` needs gold to score against, so with an empty gold
set there is no way to point a system at a real order at all. This does the
half that does not need gold: it runs the system over the *same* orders, in the
*same* sequence, that `label.py` will serve, and appends each prediction to a
JSONL keyed by order id.

    python scripts/run_baseline.py --system baselines/llm_baseline.py --limit 200

The point is alignment. When the gold set exists, prediction and label meet on
`id`, and scoring is a join rather than a re-run - which for a local model is
the difference between seconds and two hours.

**These are predictions, not labels.** They are written to `predictions/`, never
to `labels/`, and nothing in the labelling path reads them. A model's output
shown to an annotator becomes the annotator's answer; §7 of the annotation
guidelines is what keeps that from happening, and this script staying out of
`labels/` is how it is enforced rather than merely intended.

Resumable: rerun after an interruption and it picks up where it stopped.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from indic_reg_bench.adapter import load_system  # noqa: E402
from label import DB, labelling_queue  # noqa: E402

PREDICTIONS = REPO / "predictions"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--system", required=True)
    ap.add_argument("--task", default="t1_extraction")
    ap.add_argument("--db", type=Path, default=DB)
    ap.add_argument("--split", default="test", choices=["test", "train", "all"])
    ap.add_argument("--limit", type=int, default=200,
                    help="how far down the labelling queue to go (default: the "
                         "gold-set target, so predictions cover exactly the "
                         "orders that will have labels)")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    system = load_system(args.system)
    out = args.out or PREDICTIONS / f"{system.name.replace(':', '-')}.{args.task}.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)

    done: set[str] = set()
    if out.exists():
        done = {json.loads(l)["id"] for l in out.read_text(encoding="utf-8").splitlines()
                if l.strip()}
        print(f"resuming: {len(done)} already predicted in {out.name}")

    queue = labelling_queue(args.db, split=args.split, verbose=True)[: args.limit]
    todo = [r for r in queue if r["url"] not in done]
    print(f"{len(todo)} of {len(queue)} orders to run, system={system.name}")

    errors = 0
    t_start = time.perf_counter()
    with out.open("a", encoding="utf-8") as f:
        for i, row in enumerate(todo, 1):
            t0 = time.perf_counter()
            try:
                pred, err = system.predict(args.task, {"text": row["text"]}), None
            except Exception as e:  # noqa: BLE001 - a crash is a result, not a stop
                pred, err = None, f"{type(e).__name__}: {e}"
                errors += 1
            dt = time.perf_counter() - t0
            f.write(json.dumps({
                "id": row["url"], "task": args.task, "system": system.name,
                "order_date": row["order_date"], "prediction": pred, "error": err,
                "latency_s": round(dt, 3),
                "ts": datetime.now(timezone.utc).isoformat(),
            }, ensure_ascii=False) + "\n")
            f.flush()  # a two-hour run must survive being killed at minute 90
            done_n = len(done) + i
            rate = (time.perf_counter() - t_start) / i
            print(f"  [{done_n}/{len(queue)}] {dt:5.1f}s  "
                  f"eta {rate * (len(todo) - i) / 60:5.1f}m  "
                  f"{'ERR ' + err[:60] if err else row['url'].rsplit('/', 1)[-1][:60]}",
                  flush=True)

    print(f"\n{len(todo) - errors} predicted, {errors} errors -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
