"""`indic-reg-bench evaluate --system my_system.py`"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .evaluate import evaluate, format_report, results_to_json
from .scoring import SCORERS

TASKS = list(SCORERS)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="indic-reg-bench")
    sub = ap.add_subparsers(dest="cmd", required=True)

    ev = sub.add_parser("evaluate", help="score a system against the benchmark")
    ev.add_argument("--system", required=True, help="path to a .py defining class System")
    ev.add_argument("--data", type=Path, default=Path("data/splits/test"),
                    help="directory holding <task>.jsonl files")
    ev.add_argument("--tasks", nargs="+", default=TASKS, choices=TASKS)
    ev.add_argument("--json", type=Path, help="also write results as JSON here")

    sub.add_parser("tasks", help="list task ids")

    args = ap.parse_args(argv)

    if args.cmd == "tasks":
        for t in TASKS:
            print(t)
        return 0

    results = evaluate(args.system, args.data, args.tasks)
    if not results:
        print(f"No examples found under {args.data}. The gold set is not built yet - "
              f"see docs/phase1-task-design.md.", file=sys.stderr)
        return 1

    print(format_report(results))
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(results_to_json(results), encoding="utf-8")
        print(f"\nwrote {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
