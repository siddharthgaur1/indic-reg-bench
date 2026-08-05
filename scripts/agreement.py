"""
Self-agreement between two labelling passes over the same orders.

This is a *weaker* measure than multi-annotator agreement and is reported as
such: the same person a week later shares their own systematic misreadings, so
this number is an upper bound on reliability, not an estimate of it.

    python scripts/agreement.py --task t1
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from indic_reg_bench.scoring import score_extraction

LABELS = Path(__file__).resolve().parent.parent / "labels"


def load(p: Path) -> dict:
    if not p.exists():
        return {}
    return {json.loads(l)["id"]: json.loads(l)["gold"]
            for l in p.read_text(encoding="utf-8").splitlines() if l.strip()}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", default="t1")
    args = ap.parse_args()

    a, b = load(LABELS / f"{args.task}.jsonl"), load(LABELS / f"{args.task}_pass2.jsonl")
    shared = sorted(set(a) & set(b))
    if not shared:
        print(f"no overlap between pass 1 ({len(a)}) and pass 2 ({len(b)}).\n"
              f"Label with --redo after a week to measure self-agreement.")
        return 1

    per_field: dict[str, list[float]] = {}
    exact = 0
    for k in shared:
        s = score_extraction(b[k], a[k])   # pass 2 vs pass 1
        for f, v in s.items():
            per_field.setdefault(f, []).append(v)
        if b[k] == a[k]:
            exact += 1

    print(f"self-agreement over {len(shared)} doubly-labelled orders\n")
    print(f"  {'whole-record exact match':34} {exact}/{len(shared)} "
          f"({exact / len(shared):.1%})")
    for f, vs in sorted(per_field.items()):
        print(f"  {f:34} {sum(vs) / len(vs):.4f}")
    print("\nSingle-annotator self-agreement. Correlated errors are invisible to "
          "it, so treat it as an upper bound on label reliability.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
