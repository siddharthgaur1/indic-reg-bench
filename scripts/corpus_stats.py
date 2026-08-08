"""
Corpus-scale checks on the Phase 1 findings.

These are properties of the *corpus*, not scores for any system: every number
here is computed without reference to a label, so it can be reported honestly
before the gold set exists. The point is to confirm at scale what the 25-order
pilot suggested — above all that the naive first-currency-amount heuristic
disagrees with the operative paragraph often enough for T1 and T5 to be real.

    python scripts/corpus_stats.py
"""

from __future__ import annotations

import argparse
import re
import sqlite3
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from indic_reg_bench.numerals import CURRENCY  # noqa: E402
from task_viability import OPERATIVE  # noqa: E402

DB = Path(__file__).resolve().parent.parent / "data" / "corpus.db"
# One currency pattern for the whole repo. It carries the backtick-as-rupee
# case, which this script previously missed - see numerals.CURRENCY.
AMOUNT = re.compile(CURRENCY + r"\s?([\d][\d,]{2,15})")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", type=Path, default=DB)
    args = ap.parse_args()

    conn = sqlite3.connect(args.db)
    rows = conn.execute(
        "SELECT order_date, n_pages, text FROM order_text WHERE text != ''").fetchall()
    conn.close()
    if not rows:
        print("no fetched text")
        return 1

    n = len(rows)
    pages = sorted(r[1] for r in rows)
    print(f"documents        {n}")
    print(f"total characters {sum(len(r[2]) for r in rows):,}")
    print(f"pages            min {pages[0]}  median {pages[n // 2]}  max {pages[-1]}")
    print(f"years            {min(r[0][:4] for r in rows)} - {max(r[0][:4] for r in rows)}")

    disagree = comparable = multi_noticee = 0
    surface = Counter()
    sections = Counter()

    for _, _, raw in rows:
        t = re.sub(r"\s+", " ", raw)
        first = AMOUNT.search(t)
        # Last operative phrase, not the first: orders quote the noticee's own
        # settlement plea earlier in identical wording. Uses the shared pattern
        # so this number cannot drift from the triage in task_viability.py -
        # a literal "hereby impose" here missed every order that imposes
        # without the word, which is 251 of them.
        hits = list(OPERATIVE.finditer(t))
        i = hits[-1].start() if hits else -1
        op = AMOUNT.search(t[i:i + 400]) if i >= 0 else None
        if first and op:
            comparable += 1
            if first.group(1) != op.group(1):
                disagree += 1
        if re.search(r"Noticee[s]?\s*(?:No\.?|Nos\.?)\s*\d", t):
            multi_noticee += 1
        for k in ("₹", "`", "Rs.", "Lakh", "Lakhs", "Lac", "Lacs", "crore", "Crore"):
            if k in t:
                surface[k] += 1
        sections.update(m.upper() for m in re.findall(r"section\s+(15[A-Z]{1,2}(?:\([a-z]\))?)", t, re.I))

    print(f"\n--- the T5 premise: first currency amount vs the operative paragraph ---")
    print(f"comparable documents  {comparable}")
    print(f"they disagree on      {disagree}  ({disagree / comparable:.1%})"
          if comparable else "  n/a")
    print("A naive 'first amount' extractor is wrong at least this often, before "
          "counting multi-noticee mis-attribution.")

    print(f"\n--- multi-noticee orders ---")
    print(f"{multi_noticee}/{n} ({multi_noticee / n:.1%}) reference 'Noticee No. N'")

    print(f"\n--- surface variety (docs containing each form) ---")
    for k, v in surface.most_common():
        print(f"  {k:8} {v:5}  ({v / n:.0%})")

    print(f"\n--- charging sections (mentions; 15J is mitigating factors, not a charge) ---")
    for k, v in sections.most_common(12):
        print(f"  {k:10} {v}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
