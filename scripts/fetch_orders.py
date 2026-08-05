"""
Fetch SEBI enforcement-order PDFs and extract their text.

Reads listing metadata (order_date, title, url) from an existing sebi-explorer
DB, downloads each order's PDF, extracts text with pdfplumber, and stores it in
an `order_text` table. Resumable: already-fetched URLs are skipped.

    python scripts/fetch_orders.py --limit 25
    python scripts/fetch_orders.py --db D:/corpora/sebi.db      # keep bulk out of the repo

Order pages embed the PDF in an <iframe src="../../../web/?file=<pdf-url>">,
not an anchor, so the href has to be pulled out of the iframe's query string.
"""

import argparse
import re
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urljoin, urlparse

import pdfplumber
import requests

REPO = Path(__file__).resolve().parent.parent
LISTING_DB = REPO.parent / "sebi-explorer" / "data" / "sebi_orders.db"
BASE_URL = "https://www.sebi.gov.in"
DEFAULT_DB = REPO / "data" / "corpus.db"
HEADERS = {"User-Agent": "indic-reg-bench/0.1 (research; contact via github.com/siddharthgaur1)"}
DELAY_S = 1.5  # polite crawl delay


def init_db(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS order_text (
            url         TEXT PRIMARY KEY,
            pdf_url     TEXT,
            order_date  TEXT,
            title       TEXT,
            n_pages     INTEGER,
            n_chars     INTEGER,
            text        TEXT,
            fetched_at  TEXT
        );
    """)
    return conn


def pdf_url_from_page(html: str) -> str | None:
    """Pull the PDF out of the viewer iframe: <iframe src='../../web/?file=<pdf>'>.

    Recent orders put an absolute URL in `file=`; orders from around 2020 and
    earlier put a site-relative path (`/sebi_data/attachdocs/...`), so the result
    is resolved against the site root either way.
    """
    m = re.search(r"<iframe[^>]+src=['\"]([^'\"]*\?file=[^'\"]+)['\"]", html, re.I)
    if not m:
        return None
    qs = parse_qs(urlparse(m.group(1)).query)
    pdf = qs.get("file", [None])[0]
    return urljoin(BASE_URL, pdf) if pdf else None


def extract_text(pdf_bytes: bytes) -> tuple[str, int]:
    import io

    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        pages = [p.extract_text() or "" for p in pdf.pages]
    return "\n\n".join(pages), len(pages)


def fetch(db_path: Path, limit: int | None, use_fetch_set: bool = False) -> None:
    conn = init_db(db_path)

    # Prefer this repo's own `listing` table (scrape_listing.py); fall back to
    # the sebi-explorer DB, which is all that existed before it.
    has_listing = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='listing'").fetchone()
    if has_listing:
        has_set = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='fetch_set'").fetchone()
        if use_fetch_set and has_set:
            rows = conn.execute(
                "SELECT l.url, l.order_date, l.title FROM listing l "
                "JOIN fetch_set f ON f.url = l.url ORDER BY l.order_date DESC").fetchall()
        else:
            rows = conn.execute(
                "SELECT url, order_date, title FROM listing "
                "WHERE doc_type='adjudication' ORDER BY order_date DESC").fetchall()
    elif LISTING_DB.exists():
        listing = sqlite3.connect(LISTING_DB)
        rows = listing.execute(
            "SELECT url, order_date, title FROM orders ORDER BY order_date DESC").fetchall()
        listing.close()
    else:
        raise SystemExit("no listing available - run scripts/scrape_listing.py first")
    done = {r[0] for r in conn.execute("SELECT url FROM order_text")}
    todo = [r for r in rows if r[0] not in done][: limit or len(rows)]
    print(f"{len(rows)} listed, {len(done)} already fetched, {len(todo)} to fetch")

    session = requests.Session()
    session.headers.update(HEADERS)
    ok = 0

    for i, (url, order_date, title) in enumerate(todo, 1):
        print(f"[{i}/{len(todo)}] {title[:60]}...", end=" ", flush=True)
        try:
            page = session.get(url, timeout=40)
            page.raise_for_status()
            pdf_url = pdf_url_from_page(page.text)
            if not pdf_url:
                print("NO PDF IFRAME")
                continue
            time.sleep(DELAY_S)
            blob = session.get(pdf_url, timeout=90)
            blob.raise_for_status()
            text, n_pages = extract_text(blob.content)
        except Exception as e:  # noqa: BLE001 - one bad order must not end the run
            print(f"FAILED: {type(e).__name__}: {e}")
            time.sleep(DELAY_S)
            continue

        conn.execute(
            "INSERT OR REPLACE INTO order_text VALUES (?,?,?,?,?,?,?,?)",
            (url, pdf_url, order_date, title, n_pages, len(text), text,
             datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()
        ok += 1
        print(f"{n_pages}p {len(text)}ch")
        time.sleep(DELAY_S)

    total = conn.execute("SELECT COUNT(*) FROM order_text").fetchone()[0]
    conn.close()
    print(f"\nDone. +{ok} fetched | {total} documents in {db_path}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", type=Path, default=DEFAULT_DB)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--fetch-set", action="store_true",
                    help="fetch only the stratified sample from build_splits.py")
    args = ap.parse_args()
    fetch(args.db, args.limit, args.fetch_set)
