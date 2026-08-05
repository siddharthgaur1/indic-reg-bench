"""Check the one piece of non-trivial parsing: pulling the PDF out of the viewer iframe.

    python scripts/test_fetch_orders.py
"""

from fetch_orders import pdf_url_from_page

# Verbatim iframe from https://www.sebi.gov.in/enforcement/orders/jul-2026/
# adjudication-order-in-the-matter-of-eastern-financiers-limited_103018.html
REAL = (
    "<iframe src='../../../web/?file=https://www.sebi.gov.in/sebi_data/attachdocs/"
    "jul-2026/ORDER_1784715566.pdf' width='100%' style='max-height:90%; height:600px;' "
    'title="Adjudication Order in the matter of Eastern Financiers Limited" allowfullscreen>'
)

assert pdf_url_from_page(REAL) == (
    "https://www.sebi.gov.in/sebi_data/attachdocs/jul-2026/ORDER_1784715566.pdf"
)
assert pdf_url_from_page('<iframe src="../../web/?file=http://x/a%20b.pdf">') == "http://x/a b.pdf"
assert pdf_url_from_page("<p>no iframe here</p>") is None
assert pdf_url_from_page('<iframe src="../../web/viewer.html">') is None  # iframe, no ?file=

print("ok")
