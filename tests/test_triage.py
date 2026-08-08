"""
Regression tests for corpus triage and title parsing.

Every case here is one that produced a confident wrong number on a real run
against the corpus, not a hypothetical. The comments say which.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from label import operative_window  # noqa: E402
from task_viability import (  # noqa: E402
    CORRIG, NONE_IMPOSED, PROSE, SCANNED, TABLE, classify, matter_key,
    normalise, parse_title,
)


# --- title parsing -----------------------------------------------------------

@pytest.mark.parametrize("title", [
    "Adjudication Order in respect of 4 entities in the matter of X",
    "Adjudication Order in respect of three entities in the matter of Y",
    "Adjudication Order in respect of 12 noticees in the matter of Z",
    "Adjudication Order in respect of several persons in the matter of W",
])
def test_collective_titles_name_no_entity(title):
    """'in respect of 4 entities' is a count, not a name.

    Counting these as entities made '4 entities' look like a single party
    recurring across 27 unrelated matters - the strongest apparent evidence for
    multi-hop viability was an artifact.
    """
    noticee, _ = parse_title(title)
    assert noticee is None


def test_named_entity_is_extracted():
    noticee, matter = parse_title(
        "Adjudication Order in respect of Galaxy Broking Limited "
        "in the matter of M/s. KRBL Ltd")
    assert noticee == "galaxy broking"
    assert matter == "krbl"


def test_matter_names_fold_like_entity_names():
    """Matters are named after companies and carry the same 'M/s'/'Ltd' noise.

    Left unfolded, 'M/s KRBL Ltd' and 'KRBL Ltd' are two matters, and every
    noticee appearing in both reads as cross-matter recurrence.
    """
    assert matter_key("M/s. KRBL Ltd") == matter_key("KRBL Limited")


def test_normalise_folds_corporate_suffixes_and_honorifics():
    assert normalise("M/s. Foo Bar Pvt. Ltd.") == normalise("Foo Bar Limited")
    assert normalise("Shri Arun Panchariya") == normalise("Arun Panchariya")
    assert normalise("Late Ms. Anju Rani") == normalise("Anju Rani")


def test_illiquid_options_spellings_collapse_to_one_matter():
    """Six spellings of one proceeding must not read as six matters.

    Uncollapsed, a noticee appearing twice in the *same* proceeding counts as
    cross-matter recurrence, which is precisely the artifact the multi-hop
    measurement exists to exclude.
    """
    variants = [
        "Illiquid Stock Options on BSE",
        "Illiquid Stock Options at BSE.",
        "trading in Illiquid Stock Options at BSE",
        "dealings in Illiquid Stock Options at the BSE",
        "Illiquid Options on the BSE",
        "Illiquid Stock Options",
    ]
    assert len({matter_key(v) for v in variants}) == 1


def test_distinct_matters_stay_distinct():
    assert matter_key("GHCL Ltd") != matter_key("United Spirits Ltd")


# --- document triage ---------------------------------------------------------

# Anything under 200 characters is treated as a scan with no text layer, so
# fixtures need a plausible body before the disposition or they all classify as
# scanned - which is how four of these tests first failed.
BODY = ("BEFORE THE ADJUDICATING OFFICER, SECURITIES AND EXCHANGE BOARD OF "
        "INDIA. 1. SEBI observed large scale reversal trades in the stock "
        "options segment of BSE and initiated adjudication proceedings against "
        "the Noticee under section 15-I of the SEBI Act, 1992. ")

def test_scanned_pdf_has_no_text_layer():
    """A 17-page scan extracts to a few dozen characters, not zero."""
    assert classify("Adjudication Order in the matter of X", 32, "  \n \x0c ") == SCANNED


def test_corrigendum_excluded_even_when_listing_calls_it_an_adjudication():
    """SEBI's listing metadata types this as 'adjudication'; the title does not."""
    assert classify(
        "Corrigendum Order In the matter of dealings in Illiquid Stock Options",
        1090,
        "BEFORE THE ADJUDICATING OFFICER CORRIGENDUM TO ADJUDICATION ORDER ...",
    ) == CORRIG


def test_prose_penalty_is_labellable_from_text():
    text = (BODY +
            "ORDER 37. ... I, in exercise of powers conferred upon me under "
            "section 15-I, hereby impose a penalty of Rs. 5,00,000/- "
            "(Rupees Five Lakhs only) on the Noticee.")
    assert classify("Adjudication Order in respect of A", len(text), text) == PROSE


@pytest.mark.parametrize("phrasing", [
    "the SCN dated August 31, 2021 is disposed of without imposition of monetary penalty.",
    "the proceedings are disposed of without imposing any monetary penalty.",
    "no penalty is imposed on the Noticee.",
    "proceedings are liable to be abated; the death certificate was furnished.",
])
def test_no_penalty_phrasings_are_recognised(phrasing):
    """`without imposition of` is the nominalised form and the most common one.

    Probing only for `without imposing any` misfiled 194 documents into an
    'unclassified' bucket and inflated the apparent unlabellable share to 38%.
    """
    text = BODY + "ORDER 12. Having considered the facts, " + phrasing
    assert classify("Adjudication Order in respect of A", len(text),
                    text) == NONE_IMPOSED


def test_penalty_in_a_table_is_flagged_for_pdf_labelling():
    """Column-scrambled table: amount, then noticee number, then name."""
    text = (BODY +
            "ORDER 33. Having considered all the facts ... "
            "(d), 4(1) (Rupees Five (PAN: ACPC8962H ) and 4(2)(a) of PFUTP "
            "Regulations Lakhs only) The said penalty is commensurate with the "
            "lapse on the part of the Noticee.")
    assert classify("Adjudication Order in respect of A", len(text), text) == TABLE


# --- the labelling window ----------------------------------------------------

def test_window_on_no_penalty_order_finds_the_disposition_not_the_footer():
    """Before the fix this fell back to the last 1,400 chars: the signature block."""
    text = (
        "1. SEBI observed large scale reversal trades. " + ("filler. " * 400) +
        "11. I am of the view that the proceedings against the Noticee are "
        "liable to be abated and the SCN is disposed of accordingly. "
        "12. In terms of rule 6, a copy of this order is being sent to SEBI. "
        "Date: July 14, 2026 MEDHA SONPAROTE Place: Mumbai ADJUDICATING OFFICER "
        "Page 4 of 4"
    )
    assert "liable to be abated" in operative_window(text, NONE_IMPOSED)


def test_table_window_skips_the_noticees_own_plea():
    """The T5 trap, hit for real while building this.

    A noticee's quoted plea to drop the SCN is the *last* prose disposition
    phrase in a table-scrambled order, so the generic anchor lands on the
    opposite of the operative finding. Table orders anchor on the amount.
    """
    text = (
        "Noticee requested that the SCN be dropped without imposing any "
        "monetary penalty. My client has not violated any provision. "
        + ("filler. " * 300) +
        "ORDER 31. Having considered all the facts and circumstances, "
        "Rs.5,00,000/- (Rupees Five Lakhs only) 2 Omprakash Goenka 15HA"
    )
    window = operative_window(text, TABLE)
    assert "Rupees Five Lakhs only" in window
    assert "SCN be dropped" not in window
