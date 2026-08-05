"""
Scrape the full SEBI enforcement-order listing (date, title, url).

The public listing page renders only page 1. Paging is driven by an AJAX POST
to /sebiweb/ajax/home/getnewslistinfo.jsp (see js/entry.js, searchFormNewsList):
`doDirect` carries the requested page and the response is two HTML fragments
joined by "#@#" — the listing table is the first. A session cookie from the
listing page is required; without it the endpoint returns page 1 regardless.

    python scripts/scrape_listing.py            # all 479 pages (~12 min)
    python scripts/scrape_listing.py --pages 5

Resumable and idempotent: rows are keyed on url.
"""

import argparse
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

REPO = Path(__file__).resolve().parent.parent
DEFAULT_DB = REPO / "data" / "corpus.db"
LIST_URL = "https://www.sebi.gov.in/sebiweb/home/HomeAction.do?doListing=yes&sid=2&ssid=9&smid=6"
AJAX_URL = "https://www.sebi.gov.in/sebiweb/ajax/home/getnewslistinfo.jsp"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0 Safari/537.36"
DELAY_S = 1.5


def init_db(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS listing (
            url        TEXT PRIMARY KEY,
            order_date TEXT,
            year       INTEGER,
            title      TEXT,
            doc_type   TEXT,
            page       INTEGER,
            scraped_at TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_listing_year ON listing(year);
        CREATE INDEX IF NOT EXISTS idx_listing_type ON listing(doc_type);
    """)
    return conn


def classify_doc_type(title: str) -> str:
    """v1 scopes to adjudication orders; the listing mixes in several other kinds."""
    t = title.lower()
    if t.startswith("corrigendum") or "corrigendum" in t[:40]:
        return "corrigendum"
    if "settlement order" in t:
        return "settlement"
    if "adjudication order" in t:
        return "adjudication"
    if "recovery certificate" in t or "attachment" in t:
        return "recovery"
    return "other"


def new_session() -> requests.Session:
    s = requests.Session()
    s.headers.update({
        "User-Agent": UA,
        "Referer": LIST_URL,
        "X-Requested-With": "XMLHttpRequest",
    })
    s.get(LIST_URL, timeout=40)  # seed the jsessionid cookie
    return s


def fetch_page(session: requests.Session, n: int) -> str:
    payload = {
        "nextValue": n, "next": "n", "search": "", "fromDate": "", "toDate": "",
        "fromYear": "", "toYear": "", "deptId": "", "sid": "2", "ssid": "9",
        "smid": "6", "ssidhidden": "9", "intmid": "-1", "sText": "Enforcement",
        "ssText": "Orders", "smText": "Orders", "doDirect": n,
    }
    resp = session.post(AJAX_URL, data=payload, timeout=40)
    resp.raise_for_status()
    return resp.text.split("#@#")[0]


def parse_rows(html: str, page: int) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    out = []
    for tr in soup.select("tr"):
        tds = tr.find_all("td")
        if len(tds) < 2:
            continue
        link = tds[1].find("a")
        if not link or not link.get("href"):
            continue
        title = link.get_text(" ", strip=True)
        order_date, year = None, None
        try:
            dt = datetime.strptime(tds[0].get_text(strip=True), "%b %d, %Y")  # noqa: DTZ007
            order_date, year = dt.date().isoformat(), dt.year
        except ValueError:
            pass
        out.append({
            "url": link["href"], "order_date": order_date, "year": year,
            "title": title, "doc_type": classify_doc_type(title), "page": page,
            "scraped_at": datetime.now(timezone.utc).isoformat(),
        })
    return out


def scrape(db_path: Path, max_pages: int) -> None:
    conn = init_db(db_path)
    session = new_session()
    added = 0
    failed: list[int] = []

    # sebi.gov.in drops connections regularly; a failed page is retried once at
    # the end rather than abandoned, otherwise the corpus has silent holes.
    queue = list(range(1, max_pages + 1))
    while queue:
        retry_pass = len(queue) < max_pages
        for n in queue[:]:
            queue.remove(n)
            try:
                rows = parse_rows(fetch_page(session, n), n)
            except Exception as e:  # noqa: BLE001 - one bad page must not end the run
                print(f"page {n}: FAILED {type(e).__name__}: {e}")
                time.sleep(DELAY_S * 2)
                session = new_session()  # session may have expired
                if not retry_pass:
                    failed.append(n)
                continue

            if not rows:
                print(f"page {n}: 0 rows - stopping")
                queue.clear()
                break

            before = conn.execute("SELECT COUNT(*) FROM listing").fetchone()[0]
            conn.executemany(
                "INSERT OR IGNORE INTO listing VALUES "
                "(:url,:order_date,:year,:title,:doc_type,:page,:scraped_at)", rows)
            conn.commit()
            added += conn.execute("SELECT COUNT(*) FROM listing").fetchone()[0] - before

            if n % 25 == 0 or n == 1 or retry_pass:
                print(f"page {n}/{max_pages}: {len(rows)} rows, {added} new so far")
            time.sleep(DELAY_S)

        if failed:
            print(f"\nretrying {len(failed)} failed pages: {failed}")
            queue, failed = failed, []

    total = conn.execute("SELECT COUNT(*) FROM listing").fetchone()[0]
    by_type = conn.execute(
        "SELECT doc_type, COUNT(*) FROM listing GROUP BY doc_type ORDER BY 2 DESC").fetchall()
    conn.close()
    print(f"\nDone. +{added} new | {total} listed")
    for t, c in by_type:
        print(f"  {t:14} {c}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", type=Path, default=DEFAULT_DB)
    ap.add_argument("--pages", type=int, default=479)
    args = ap.parse_args()
    scrape(args.db, args.pages)
