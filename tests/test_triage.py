"""
Regression tests for corpus triage and title parsing.

Every case here is one that produced a confident wrong number on a real run
against the corpus, not a hypothetical. The comments say which.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from indic_reg_bench.numerals import parse_amount  # noqa: E402
from label import AMOUNT, operative_window, t5_spans  # noqa: E402
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
    "I impose a penalty of Rs. 5,00,000/- on the Noticee.",
    "I hereby impose a penalty of Rs. 5,00,000/- on the Noticee.",
    "I am imposing a monetary penalty of Rs. 5,00,000/- on the Noticee.",
    "it is a fit case to impose a consolidated penalty of Rs. 5,00,000/-.",
])
def test_operative_phrasings_without_the_word_hereby(phrasing):
    """Older orders impose without saying 'hereby' - 251 of them.

    The gap only surfaced once the crawl reached back past 2016, which is why
    the residue has to be re-read at every corpus size rather than once.
    """
    text = BODY + "ORDER 37. " + phrasing
    assert classify("Adjudication Order in respect of A", len(text), text) == PROSE


def test_the_rules_boilerplate_is_not_an_operative_paragraph():
    """This title appears in nearly every order and must never match.

    It is the reason the operative pattern requires 'penalty of' rather than
    just 'impos... penalt' - the boilerplate says 'Imposing Penalties by
    Adjudicating Officer', with no 'of'.
    """
    text = (BODY + "under the SEBI (Procedure for Holding Inquiry and Imposing "
            "Penalties by Adjudicating Officer) Rules, 1995, the proceedings "
            "are disposed of without imposition of monetary penalty.")
    assert classify("Adjudication Order in respect of A", len(text),
                    text) == NONE_IMPOSED


@pytest.mark.parametrize("phrasing", [
    "the SCN dated August 31, 2021 is disposed of without imposition of monetary penalty.",
    "the proceedings are disposed of without imposing any monetary penalty.",
    "no penalty is imposed on the Noticee.",
    "proceedings are liable to be abated; the death certificate was furnished.",
    # 'hereby dispose of' and 'not liable for' account for another 129
    # documents, found by reading the unclassified bucket a second time.
    "I hereby dispose of the Adjudication Proceedings initiated vide the SCN.",
    "the Noticee is not liable for monetary penalty under Section 15C.",
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


# --- currency extraction -----------------------------------------------------

def test_backtick_is_a_rupee_sign():
    """Many SEBI PDFs render the rupee glyph as U+0060 GRAVE ACCENT.

    It is the only currency marker in 4.8% of fetched orders. A pattern without
    it does not fail on those documents - it silently returns nothing, which is
    how they stayed invisible to every measurement in this repo.
    """
    text = "hereby impose a penalty of ` 2,50,000/- (Rupees Two Lakh Fifty Thousand Only)"
    assert AMOUNT.search(text) is not None
    assert parse_amount(text) == 250_000


def test_standard_currency_forms_still_parse():
    assert parse_amount("a penalty of Rs. 4,00,000/-") == 400_000
    assert parse_amount("₹2,00,000/- (Rupees Two Lakh only)") == 200_000


def test_t5_samples_across_cue_groups_not_just_the_first_amounts():
    """Taking the first N spans returns the facts section every time.

    Here the first three amounts are share values in the facts narrative and the
    imposed penalty is last. A positional sample would never reach it.
    """
    text = (
        "Investigation revealed the company had issued capital of ` 10/- each. "
        "It then allotted warrants for ` 30 crores and split shares of ` 1/- each. "
        + ("filler narrative. " * 60) +
        "The Noticee submitted a willingness to settle for Rs. 1,00,000/-. "
        + ("filler narrative. " * 60) +
        "ORDER 33. I, in exercise of the powers conferred upon me, hereby impose "
        "a penalty of Rs. 5,00,000/- (Rupees Five Lakh Only) on the Noticee."
    )
    spans = t5_spans(text, per_doc=4)
    picked = {s["span"].strip() for s in spans}
    assert any("5,00,000" in p for p in picked), "imposed penalty must be sampled"
    assert any("1,00,000" in p for p in picked), "settlement plea must be sampled"


def test_t5_returns_nothing_when_there_is_no_currency():
    assert t5_spans("An order with no amounts at all.", per_doc=4) == []


# --- split composition -------------------------------------------------------

def test_composition_reads_the_columns_cut_splits_selects():
    """`composition` indexes the row tuple positionally.

    Reordering the SELECT in `cut_splits` would silently feed the title into
    `n_chars` and classify everything as one bucket, which looks like a finding
    rather than a bug. This pins the contract between the two.
    """
    from build_splits import composition

    row = ("url", "2024-01-01", 5, "Adjudication Order in respect of A", 900,
           "ORDER I hereby impose a penalty of Rs. 5,00,000/- on the Noticee.")
    assert composition([row]) == {PROSE: 1}


def test_label_cli_survives_a_cp1252_console(tmp_path):
    """₹ in the operative window used to end the session with a traceback.

    52.7% of the test split hits this - the rupee sign, extraction arrows and
    Symbol-font bullets are all outside cp1252, which is what a Windows console
    defaults to. `fetch_orders.py` already guarded against it after the same
    error killed a crawl at document 1,087; label.py did not.
    """
    import subprocess

    repo = Path(__file__).resolve().parent.parent
    if not (repo / "data" / "corpus.db").exists():
        pytest.skip("needs the fetched corpus")

    env = {**os.environ, "PYTHONIOENCODING": "cp1252"}
    p = subprocess.run(
        [sys.executable, str(repo / "scripts" / "label.py"),
         "--task", "t1", "--dry-run", "--limit", "1"],
        input="q\n", capture_output=True, text=True, env=env, cwd=repo,
    )
    assert "UnicodeEncodeError" not in p.stderr, p.stderr[-600:]
    assert p.returncode == 0


def test_labelling_queue_is_one_sequence_for_every_consumer():
    """Predictions are joined to gold on `id`, so the queue must be stable.

    label.py and run_baseline.py both walk this. If they drew separately -
    two shuffles, two waste filters - a baseline's 200 predictions could cover
    different documents than the 200 labels, and the join would still succeed
    on whatever overlapped. Silent partial misalignment, not an error.
    """
    from label import DB, labelling_queue

    if not DB.exists():
        pytest.skip("needs the fetched corpus")

    a = [r["url"] for r in labelling_queue(DB)]
    b = [r["url"] for r in labelling_queue(DB)]
    assert a == b, "queue is not deterministic"
    assert len(set(a)) == len(a), "queue repeats an order"

    # The split filter must not be a suggestion: the leaderboard scores test.
    dates = [r["order_date"] for r in labelling_queue(DB)]
    assert all(int(d[:4]) >= 2023 for d in dates)
    assert all(int(r["order_date"][:4]) < 2023
               for r in labelling_queue(DB, split="train"))
