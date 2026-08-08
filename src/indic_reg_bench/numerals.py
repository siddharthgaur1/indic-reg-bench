"""
Indian numeral and currency normalisation.

SEBI orders write amounts in several ways at once, often in the same sentence:

    Rs. 4,00,000/- (Rupees Four Lakh Only)
    ₹2,00,000/- (Rupees Two Lakh only)
    Rs.35,00,000/- (Rs. Thirty Five Lacs)
    a minimum penalty of Rs. 1 lacs or 1.20 Lacs

Digit grouping is Indian (2,2,3 — `35,00,000` is 3.5 million, not 35 million),
the unit is spelled Lakh/Lakhs/Lac/Lacs interchangeably, and the currency symbol
is `Rs.`/`Rs`/`₹`. `parse_amount` handles the numeric form; `words_to_number`
handles the parenthesised words, which exist in most orders and give a second,
independent channel to verify the first against.
"""

from __future__ import annotations

import re

# Indian scale words. Lakh = 1e5, crore = 1e7. Both have several spellings.
SCALES = {
    "thousand": 1_000,
    "lakh": 100_000, "lakhs": 100_000, "lac": 100_000, "lacs": 100_000, "lakhs.": 100_000,
    "crore": 10_000_000, "crores": 10_000_000, "cr": 10_000_000,
    "million": 1_000_000, "billion": 1_000_000_000,
}

UNITS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
    "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16,
    "seventeen": 17, "eighteen": 18, "nineteen": 19, "twenty": 20,
    "thirty": 30, "forty": 40, "fourty": 40, "fifty": 50, "sixty": 60,
    "seventy": 70, "eighty": 80, "ninety": 90,
}

# The backtick is not a typo. Many SEBI PDFs embed the rupee sign in a font
# whose glyph maps to U+0060 GRAVE ACCENT, so `₹30 crores` extracts as
# `` ` 30 crores ``. It is the *only* currency marker in 60 of the first 1,241
# fetched orders (4.8%) and appears alongside `Rs.` in 109 more - so a pattern
# without it silently drops those documents from every measurement rather than
# failing loudly on them.
CURRENCY = r"(?:Rs\.?|₹|INR|`)"

_AMOUNT_RE = re.compile(
    CURRENCY + r"\s*([\d][\d,]*(?:\.\d+)?)\s*(crores?|lakhs?|lacs?|cr\b)?",
    re.IGNORECASE,
)


def parse_amount(text: str) -> int | None:
    """Parse the first `Rs. <number> [scale]` in `text` into whole rupees.

    Returns None when no currency amount is present. Indian grouping is handled
    by stripping separators — `35,00,000` and `3500000` both give 3_500_000.
    """
    m = _AMOUNT_RE.search(text)
    if not m:
        return None
    try:
        value = float(m.group(1).replace(",", ""))
    except ValueError:
        return None
    scale = (m.group(2) or "").lower().rstrip("s").rstrip(".")
    if scale:
        value *= SCALES.get(scale, SCALES.get(scale + "s", 1))
    return int(round(value))


def words_to_number(text: str) -> int | None:
    """Parse 'Rupees Thirty Five Lacs Only' -> 3500000.

    Ignores leading 'Rupees'/'Rs.' and trailing 'Only'. Returns None if no
    number words are found, so callers can distinguish 'absent' from 'zero'.
    """
    tokens = re.findall(r"[a-z]+", text.lower())
    tokens = [t for t in tokens if t not in ("rupees", "rupee", "rs", "only", "and", "inr")]
    if not tokens:
        return None

    total, current, seen = 0, 0, False
    for tok in tokens:
        if tok in UNITS:
            current += UNITS[tok]
            seen = True
        elif tok == "hundred" and current:
            current *= 100
            seen = True
        elif tok in SCALES:
            # A scale word flushes whatever has accumulated: "thirty five lacs".
            current = current or 1
            total += current * SCALES[tok]
            current = 0
            seen = True
    if not seen:
        return None
    return total + current


def amounts_agree(numeric: str, words: str) -> bool | None:
    """Cross-check the numeral against its parenthesised words.

    Returns None when either channel is unparseable — 'unknown', not 'disagree'.
    """
    a, b = parse_amount(numeric), words_to_number(words)
    if a is None or b is None:
        return None
    return a == b
