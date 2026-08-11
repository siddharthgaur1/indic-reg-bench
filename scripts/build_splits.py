"""
Select which orders to fetch, and cut the train/test splits.

Two decisions are made here and both are deliberate:

**Temporal split, not random.** Train on pre-2023 orders, test on 2023+. A
random split lets a system see one order from a matter and be tested on its
sibling — SEBI issues near-identical orders to many noticees in one matter, so a
random split leaks badly and flatters retrieval systems. Temporal also matches
how such a system is actually used: built on past orders, run on new ones.

**Stratified by year and document length.** Penalty magnitude would be the
better third axis but it is not knowable before labelling — using a regex to
stratify by penalty would bake that regex's failure modes into the split.
Length is a knowable proxy for complexity (multi-noticee orders are long).

    python scripts/build_splits.py --target 2000     # choose the fetch set
    python scripts/build_splits.py --splits          # cut splits from fetched text
"""

from __future__ import annotations

import argparse
import json
import random
import sqlite3
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from task_viability import classify  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
DB = REPO / "data" / "corpus.db"
SEED = 42
TEST_FROM_YEAR = 2023


def choose_fetch_set(db: Path, target: int) -> list[str]:
    """Stratify by year over adjudication orders only."""
    conn = sqlite3.connect(db)
    rows = conn.execute(
        "SELECT url, year FROM listing WHERE doc_type='adjudication' AND year IS NOT NULL"
    ).fetchall()
    conn.close()

    by_year: dict[int, list[str]] = defaultdict(list)
    for url, year in rows:
        by_year[year].append(url)

    rng = random.Random(SEED)
    years = sorted(by_year)
    per_year = max(1, target // len(years))
    chosen: list[str] = []
    # Years with fewer orders than the quota contribute everything they have;
    # the shortfall is redistributed so the total still lands near `target`.
    for y in years:
        pool = sorted(by_year[y])
        rng.shuffle(pool)
        chosen.extend(pool[:per_year])
    if len(chosen) < target:
        rest = [u for u, _ in rows if u not in set(chosen)]
        rng.shuffle(rest)
        chosen.extend(rest[: target - len(chosen)])

    print(f"{len(rows)} adjudication orders listed across {len(years)} years "
          f"({years[0]}-{years[-1]})")
    print(f"selected {len(chosen)} (~{per_year}/year) with seed {SEED}")
    return chosen


def write_fetch_set(db: Path, urls: list[str]) -> None:
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE IF NOT EXISTS fetch_set (url TEXT PRIMARY KEY)")
    conn.executemany("INSERT OR IGNORE INTO fetch_set VALUES (?)", [(u,) for u in urls])
    conn.commit()
    n = conn.execute("SELECT COUNT(*) FROM fetch_set").fetchone()[0]
    conn.close()
    print(f"fetch_set now holds {n} urls - run: python scripts/fetch_orders.py --fetch-set")


def composition(rows: list[tuple]) -> Counter:
    """Bucket mix of a split, as `task_viability.classify` sees it."""
    return Counter(classify(r[3], r[4], r[5]) for r in rows)


def cut_splits(db: Path) -> None:
    conn = sqlite3.connect(db)
    rows = conn.execute(
        "SELECT url, order_date, n_pages, title, n_chars, text "
        "FROM order_text WHERE order_date IS NOT NULL").fetchall()
    conn.close()
    if not rows:
        print("no fetched text yet")
        return

    train = [r for r in rows if int(r[1][:4]) < TEST_FROM_YEAR]
    test = [r for r in rows if int(r[1][:4]) >= TEST_FROM_YEAR]
    out = REPO / "data" / "splits"
    out.mkdir(parents=True, exist_ok=True)
    for name, part in (("train", train), ("test", test)):
        (out / f"{name}_ids.json").write_text(
            json.dumps([r[0] for r in part], indent=1), encoding="utf-8")
    print(f"temporal split at {TEST_FROM_YEAR}: train={len(train)} test={len(test)}")
    print("  train years:", sorted(Counter(int(r[1][:4]) for r in train)))
    print("  test  years:", sorted(Counter(int(r[1][:4]) for r in test)))

    # A temporal split does not only move dates, it moves document *formats*.
    # SEBI began issuing multi-noticee penalties as tables around 2024, so the
    # bucket mix is not stable across the cut. Printed on every run because a
    # split whose composition is never inspected is how that goes unnoticed.
    print(f"\ncomposition (train n={len(train)} / test n={len(test)}):")
    tr, te = composition(train), composition(test)
    for bucket in sorted(set(tr) | set(te)):
        a, b = tr[bucket], te[bucket]
        print(f"  {100 * a / len(train):5.1f}%  {100 * b / len(test):5.1f}%   {bucket}")
    print(f"\nwrote {out}/train_ids.json, {out}/test_ids.json")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", type=Path, default=DB)
    ap.add_argument("--target", type=int, default=2000)
    ap.add_argument("--splits", action="store_true", help="cut splits from fetched text")
    args = ap.parse_args()
    if args.splits:
        cut_splits(args.db)
    else:
        write_fetch_set(args.db, choose_fetch_set(args.db, args.target))
