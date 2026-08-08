"""
Export the listing index for the HuggingFace release.

Exports **metadata only** - url, date, title, doc_type. No order text and no
labels, matching the redistribution position in DATASET_CARD.md: this release
tells you which documents the benchmark covers and how to fetch them, and SEBI
remains the source of the documents themselves.

    python scripts/export_hf.py                 # write release/
    python scripts/export_hf.py --upload        # push to HuggingFace
"""

from __future__ import annotations

import argparse
import csv
import sqlite3
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DB = REPO / "data" / "corpus.db"
OUT = REPO / "release"
HF_REPO = "siddharthgaur/indic-reg-bench"


def export(db: Path) -> tuple[int, int]:
    OUT.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db)

    rows = conn.execute(
        "SELECT url, order_date, year, title, doc_type FROM listing ORDER BY order_date DESC, url"
    ).fetchall()
    with (OUT / "listing.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["url", "order_date", "year", "title", "doc_type"])
        w.writerows(rows)

    fetch_set = conn.execute(
        "SELECT f.url, l.order_date, l.year, l.title FROM fetch_set f "
        "JOIN listing l ON l.url = f.url ORDER BY l.order_date DESC"
    ).fetchall() if conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='fetch_set'").fetchone() else []
    if fetch_set:
        with (OUT / "benchmark_sample.csv").open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["url", "order_date", "year", "title"])
            w.writerows(fetch_set)

    conn.close()
    return len(rows), len(fetch_set)


def build_card(n_listing: int, n_sample: int) -> str:
    card = (REPO / "DATASET_CARD.md").read_text(encoding="utf-8")
    note = (
        "\n\n---\n\n## Files in this release\n\n"
        f"- `listing.csv` — {n_listing:,} SEBI enforcement orders (url, date, year, title, doc_type). "
        "The complete index, Nov 2004 – Jul 2026.\n"
        f"- `benchmark_sample.csv` — the {n_sample:,} adjudication orders stratified by year "
        "(seed 42) that the benchmark is being built from.\n\n"
        "**There is no order text and there are no labels in this release.** "
        "Fetch the documents yourself:\n\n"
        "```bash\n"
        "git clone https://github.com/siddharthgaur1/indic-reg-bench\n"
        "cd indic-reg-bench && pip install -e .\n"
        "python scripts/scrape_listing.py\n"
        "python scripts/fetch_orders.py --fetch-set\n"
        "```\n"
    )
    return card + note


def upload(n_listing: int, n_sample: int) -> None:
    # Imported here so the export half of this script runs without the extra.
    try:
        from huggingface_hub import HfApi
    except ImportError:
        raise SystemExit(
            "uploading needs the optional hf extra:  pip install -e \".[hf]\"")

    api = HfApi()
    api.create_repo(HF_REPO, repo_type="dataset", exist_ok=True)
    (OUT / "README.md").write_text(build_card(n_listing, n_sample), encoding="utf-8")
    api.upload_folder(folder_path=str(OUT), repo_id=HF_REPO, repo_type="dataset",
                      commit_message="Add listing index and benchmark sample (metadata only)")
    print(f"https://huggingface.co/datasets/{HF_REPO}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", type=Path, default=DB)
    ap.add_argument("--upload", action="store_true")
    args = ap.parse_args()
    n_listing, n_sample = export(args.db)
    print(f"listing.csv: {n_listing} rows | benchmark_sample.csv: {n_sample} rows -> {OUT}")
    if args.upload:
        upload(n_listing, n_sample)
