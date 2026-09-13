"""Render docs/orders-by-year.png from the committed release CSVs.

    python scripts/make_readme_chart.py

Counts only: listing.csv (every SEBI order found) vs benchmark_sample.csv
(the 2,000-order stratified sample). No scores - there is no gold set yet.
"""
import csv
from collections import Counter
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def years(name: str) -> Counter:
    with open(ROOT / "release" / name, newline="", encoding="utf-8") as f:
        return Counter(int(r["year"]) for r in csv.DictReader(f) if r["year"])


listing, sample = years("listing.csv"), years("benchmark_sample.csv")
xs = list(range(min(listing), max(listing) + 1))

fig, ax = plt.subplots(figsize=(10, 4), dpi=110)
ax.bar(xs, [listing[x] for x in xs], color="#c7d2fe", label=f"all listed orders ({sum(listing.values()):,})")
ax.bar(xs, [sample[x] for x in xs], color="#4f46e5", width=0.5,
       label=f"benchmark sample ({sum(sample.values()):,}, seed 42)")
ax.set_title("SEBI enforcement orders by year - release/listing.csv vs release/benchmark_sample.csv")
ax.set_ylabel("orders")
ax.set_xticks(xs[::2])
ax.spines[["top", "right"]].set_visible(False)
ax.legend(frameon=False)
fig.tight_layout()
out = ROOT / "docs" / "orders-by-year.png"
fig.savefig(out)
print(f"wrote {out}")
