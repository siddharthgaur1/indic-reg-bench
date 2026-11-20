"""
Fix the order the test split gets labelled in, capped by matter family.

The illiquid stock options proceedings are 238 of the 422 test orders. Labelling
in plain shuffled order would let one family of near-identical orders decide
most of the headline score, so this is a deliberate departure from a uniform
draw, and the dataset card says so:

- The family fills every fourth position, so it never exceeds 25% of any prefix.
- Every other order is drawn round-robin across matters, so a second order from
  one matter only appears after every matter has given its first.

The output is one ordered list rather than a sample of fixed size, because the
gold-set target can move. Any prefix keeps both properties, so cutting from 150
to 100 orders needs no re-draw, and corrigenda or scans that `labelling_queue`
removes cannot break them. It reads committed files only: no corpus, no network,
same output on every machine.

    python scripts/build_test_queue.py
"""

from __future__ import annotations

import csv
import json
import random
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_splits import SEED  # noqa: E402
from task_viability import matter_key, parse_title  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
SPLITS = REPO / "data" / "splits"
TEST_QUEUE = SPLITS / "test_queue_ids.json"
ILLIQUID = "illiquid stock options bse"
FAMILY = re.compile(r"il(?:l[\s-]+)?liquid", re.I)  # SEBI also writes "ill-liquid"
CAP_EVERY = 4


def order_matter(url: str, titles: dict[str, str]) -> str:
    """The order's matter key; an order with no parseable matter stands alone.

    Orders missing from the listing fall back to the words in their URL. The
    family is also matched on the whole text, because a title `parse_title`
    cannot split would otherwise slip past the cap as a one-order matter.
    """
    slug = url.rsplit("/", 1)[-1].rsplit("_", 1)[0].replace("-", " ")
    text = titles.get(url) or slug
    if FAMILY.search(f"{text} {slug}"):
        return ILLIQUID
    _, matter = parse_title(text)
    return matter_key(matter) if matter else url


def build_queue(urls: list[str], titles: dict[str, str]) -> list[str]:
    rng = random.Random(SEED)
    by_matter: dict[str, list[str]] = defaultdict(list)
    for url in sorted(urls):
        by_matter[order_matter(url, titles)].append(url)

    family = by_matter.pop(ILLIQUID, [])
    rng.shuffle(family)
    matters = sorted(by_matter)
    rng.shuffle(matters)
    for m in matters:
        rng.shuffle(by_matter[m])

    others: list[str] = []
    for depth in range(max((len(v) for v in by_matter.values()), default=0)):
        others.extend(by_matter[m][depth] for m in matters if depth < len(by_matter[m]))

    # Ends when the other orders run out: the rest of the family stays unqueued.
    queue: list[str] = []
    others_left, family_left = iter(others), iter(family)
    for position in range(1, len(urls) + 1):
        source = family_left if position % CAP_EVERY == 0 else others_left
        url = next(source, None)
        if url is None:
            break
        queue.append(url)
    return queue


def load_titles() -> dict[str, str]:
    with (REPO / "release" / "listing.csv").open(encoding="utf-8", newline="") as f:
        return {r["url"]: r["title"] for r in csv.DictReader(f)}


def main() -> int:
    urls = json.loads((SPLITS / "test_ids.json").read_text(encoding="utf-8"))
    titles = load_titles()
    queue = build_queue(urls, titles)
    TEST_QUEUE.write_text(json.dumps(queue, indent=1), encoding="utf-8")

    in_family = [order_matter(u, titles) == ILLIQUID for u in queue]
    print(f"{len(queue)} of {len(urls)} test orders queued -> {TEST_QUEUE}")
    for n in (100, 150, len(queue)):
        print(f"  first {n}: {sum(in_family[:n])} illiquid options, "
              f"{len({order_matter(u, titles) for u in queue[:n]})} matters")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
