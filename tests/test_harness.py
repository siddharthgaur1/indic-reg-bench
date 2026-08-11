"""Checks for the scoring and numeral logic.

Every string marked "real" is verbatim from a fetched SEBI order.

    python -m pytest tests/ -q
"""

import re

import pytest

from indic_reg_bench.numerals import amounts_agree, parse_amount, words_to_number
from indic_reg_bench.scoring import (majority_class_baseline, normalise_name,
                                     normalise_section,
                                     same_answer, score_abstention,
                                     score_extraction, score_labels,
                                     score_numeric)


# ── Indian digit grouping ─────────────────────────────────────────
def test_indian_grouping_is_not_western():
    # real: Eastern Financiers. 4,00,000 is four lakh, NOT four hundred thousand
    # read the Western way (which would give 400,000 too) - the trap is 35,00,000.
    assert parse_amount("Rs. 4,00,000/-") == 400_000
    # real: Citrus Check Inns. Western parsing of "35,00,000" as 3,500,000 is
    # correct only because separators are stripped; 35 million would be wrong.
    assert parse_amount("Rs.35,00,000/-") == 3_500_000
    assert parse_amount("₹2,00,000/-") == 200_000        # real: IDBI Trusteeship
    assert parse_amount("₹10,00,000/-") == 1_000_000     # real: Exfinity


def test_currency_symbol_variants():
    assert parse_amount("Rs. 5,00,000") == 500_000
    assert parse_amount("Rs.5,00,000") == 500_000
    assert parse_amount("₹ 5,00,000") == 500_000
    assert parse_amount("INR 5,00,000") == 500_000
    assert parse_amount("no amount here") is None


def test_scale_words_all_spellings():
    # real: "a minimum penalty of Rs. 1 lacs or 1.20 Lacs"
    assert parse_amount("Rs. 1 lacs") == 100_000
    assert parse_amount("Rs. 1.20 Lacs") == 120_000
    assert parse_amount("Rs. 2 lakh") == 200_000
    assert parse_amount("Rs. 2 Lakhs") == 200_000
    assert parse_amount("Rs. 1 crore") == 10_000_000
    assert parse_amount("Rs. 1.5 Crores") == 15_000_000


def test_words_channel():
    assert words_to_number("Rupees Four Lakh Only") == 400_000        # real
    assert words_to_number("Rs. Thirty Five Lacs") == 3_500_000       # real
    assert words_to_number("Rupees Two Lakh only") == 200_000         # real
    assert words_to_number("Rupees Ten Lakh") == 1_000_000            # real
    assert words_to_number("Rupees Twenty Five Lacs") == 2_500_000    # real
    assert words_to_number("Rupees Only") is None                     # no digits -> unknown


def test_cross_channel_check():
    assert amounts_agree("Rs. 4,00,000/-", "Rupees Four Lakh Only") is True
    assert amounts_agree("Rs. 4,00,000/-", "Rupees Forty Lakh Only") is False
    # unparseable side is 'unknown', never silently 'disagree'
    assert amounts_agree("Rs. 4,00,000/-", "Rupees Only") is None


# ── name folding ──────────────────────────────────────────────────
def test_normalise_name_handles_real_variants():
    assert normalise_name("Late Ms. Anju Rani") == "anju rani"   # real: deceased noticee
    assert normalise_name("Mr. Nitin Agarwal") == "nitin agarwal"
    assert normalise_name("Excel Technovation Pvt Ltd") == "excel technovation"
    assert normalise_name("Excel Technovation Private Limited") == "excel technovation"
    assert normalise_name("M/s. Karuna Cables Ltd") == "karuna cables"


# ── T1 ────────────────────────────────────────────────────────────
def test_extraction_penalty_attribution_catches_swapped_names():
    """The column-scrambling failure mode: right names, right amounts, wrong pairing."""
    gold = {"noticees": [
        {"name": "Omprakash Basantlal Goenka", "penalty_inr": 3_500_000, "charging_section": "15HA"},
        {"name": "Prakash Ganpat Utekar", "penalty_inr": 2_500_000, "charging_section": "15HA"},
    ]}
    swapped = {"noticees": [
        {"name": "Omprakash Basantlal Goenka", "penalty_inr": 2_500_000, "charging_section": "15HA"},
        {"name": "Prakash Ganpat Utekar", "penalty_inr": 3_500_000, "charging_section": "15HA"},
    ]}
    s = score_extraction(swapped, gold)
    assert s["noticee_name_f1"] == 1.0          # names all present
    assert s["penalty_attribution_f1"] == 0.0   # but attributed to the wrong noticee
    assert score_extraction(gold, gold)["full_triple_f1"] == 1.0


def test_extraction_partial_recall():
    gold = {"noticees": [{"name": "A Ltd", "penalty_inr": 100, "charging_section": "15HB"},
                         {"name": "B Ltd", "penalty_inr": 200, "charging_section": "15HB"}]}
    pred = {"noticees": [{"name": "A Ltd", "penalty_inr": 100, "charging_section": "15HB"}]}
    s = score_extraction(pred, gold)
    assert s["full_triple_precision"] == 1.0
    assert s["full_triple_recall"] == 0.5


# ── T2 ────────────────────────────────────────────────────────────
def test_macro_f1_does_not_reward_majority_guessing():
    labels = ["15HA", "15HB", "15EA"]
    gold = ["15HB"] * 8 + ["15HA"] + ["15EA"]
    always = score_labels(["15HB"] * 10, gold, labels)
    assert always["accuracy"] == 0.8          # micro would look strong
    assert always["macro_f1"] < 0.35          # macro exposes it
    assert majority_class_baseline(gold, labels)["macro_f1"] == always["macro_f1"]


# ── T3 ────────────────────────────────────────────────────────────
def test_numeric_is_exact_match_only():
    assert score_numeric([400_000, 200_000], [400_000, 200_000])["exact_match"] == 1.0
    assert score_numeric([400_001], [400_000])["exact_match"] == 0.0   # no partial credit
    assert score_numeric([None], [400_000])["exact_match"] == 0.0


# ── T4 ────────────────────────────────────────────────────────────
def test_abstention_reports_both_sides_separately():
    gold = ["Rs. 4,00,000", "not stated", "not stated"]
    always_abstain = score_abstention(["not stated"] * 3, gold)
    assert always_abstain["abstention_rate"] == 1.0
    assert always_abstain["answerable_accuracy"] == 0.0   # the cost is visible

    never_abstain = score_abstention(["Rs. 4,00,000", "guess", "guess"], gold)
    assert never_abstain["answerable_accuracy"] == 1.0
    assert never_abstain["abstention_rate"] == 0.0


# --- T3/T4 answer normalisation ----------------------------------------------

@pytest.mark.parametrize("pred,gold", [
    (500000, 500000),
    ("500000", 500000),
    ("5,00,000", 500000),
    ("` 5,00,000/-", 500000),
    ("Rs. 5,00,000/- (Rupees Five Lakh only)", 500000),
    ("not stated", "Not Stated"),
    ("March 27, 2025", "march 27, 2025"),
])
def test_same_answer_ignores_how_the_amount_is_written(pred, gold):
    """llama3.2 answered '` 5,00,000/-(Rupees Five Lakh only)' - the operative
    text, verbatim and correct - and scored 0 against a gold of 500000.

    Every system would have been deflated the same way, which is why it would
    never have looked like a bug.
    """
    assert same_answer(pred, gold)


@pytest.mark.parametrize("pred,gold", [
    (500000, 100000),          # the settlement plea, not the penalty
    (None, 500000),
    ("", 500000),
    ("not stated", 500000),    # abstaining is not a right answer
    (500000, "not stated"),    # nor is answering an unanswerable
    ("45 days", 45),           # a unit is part of the answer
    ("March 27, 2025", "March 28, 2025"),
])
def test_same_answer_does_not_grade_on_a_curve(pred, gold):
    """Normalisation must not become partial credit."""
    assert not same_answer(pred, gold)


@pytest.mark.parametrize("value,expect", [
    ("15HA", "15HA"),
    ("15ha", "15HA"),
    ("15HA of the SEBI Act, 1992", "15HA"),      # real llama3.2 output
    ("Section 15A(a) of the SEBI Act", "15A(A)"),
    ("15A (b)", "15A(B)"),
    (None, ""),
])
def test_normalise_section_finds_the_section_inside_the_citation(value, expect):
    assert normalise_section(value) == expect


@pytest.mark.parametrize("value", [
    "Section 446(1) of the Companies Act, 1956",   # real, and genuinely wrong
    "Regulations 3(a), (b), (c) and (d) of PFUTP Regulations",
])
def test_normalise_section_leaves_a_wrong_answer_wrong(value):
    """Normalisation must not launder a non-section into a section."""
    assert normalise_section(value) != "15HA"
    assert not re.fullmatch(r"15[A-Z]{1,2}(\([A-Z]\))?", normalise_section(value))


def test_t1_section_padding_is_not_scored_as_a_misread():
    """llama3.2 returned '15HA of the SEBI Act, 1992' on a real order.

    Under the old fold that became '15HAOFTHESEBIACT,1992' and missed against
    '15HA' - the same formatting-as-comprehension error as T3/T4, one layer in.
    """
    gold = {"noticees": [{"name": "Acme Traders Pvt Ltd", "penalty_inr": 500000,
                          "charging_section": "15HA"}]}
    pred = {"noticees": [{"name": "Acme Traders", "penalty_inr": 500000,
                          "charging_section": "15HA of the SEBI Act, 1992"}]}
    assert score_extraction(pred, gold)["full_triple_f1"] == 1.0
