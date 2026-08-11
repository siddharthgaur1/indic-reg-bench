"""
Scoring functions for the five tasks.

All scorers are deterministic and depend only on (prediction, gold) — no model
calls, no randomness, no network. Every scorer returns a dict of named metrics
rather than one blended number, because per-task and per-field breakdowns are
what make the results interpretable; the CLI never averages across tasks.
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter

from .numerals import parse_answer

# ── name normalisation ────────────────────────────────────────────
# Matched *after* punctuation is stripped, so "M/s." has already become "m s".
_HONORIFICS = r"^(?:mr|mrs|ms|shri|smt|sri|m\s+s|dr|late|the)\s+"
_SUFFIXES = r"\s+(?:pvt|private|ltd|limited|llp|inc|huf|co|company)\.?$"


def normalise_name(name: str) -> str:
    """Fold a noticee name for comparison.

    Orders vary honorifics ('Mr.', 'Shri', 'Late'), corporate suffixes
    ('Pvt Ltd' vs 'Private Limited') and spacing. Deceased noticees appear as
    'Late Ms. Anju Rani', so 'late' is stripped as an honorific. Suffixes are
    stripped repeatedly: 'Excel Technovation Pvt Ltd' drops both tokens.
    """
    s = unicodedata.normalize("NFKD", name or "").lower()
    s = re.sub(r"[^\w\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    while True:
        new = re.sub(_HONORIFICS, "", s)
        new = re.sub(_SUFFIXES, "", new).strip()
        if new == s:
            return s
        s = new


def _prf(tp: int, n_pred: int, n_gold: int) -> dict[str, float]:
    p = tp / n_pred if n_pred else 0.0
    r = tp / n_gold if n_gold else 0.0
    f = 2 * p * r / (p + r) if p + r else 0.0
    return {"precision": round(p, 4), "recall": round(r, 4), "f1": round(f, 4)}


def _multiset_tp(pred: list, gold: list) -> int:
    """True positives over multisets - two noticees may share a penalty value."""
    cp, cg = Counter(pred), Counter(gold)
    return sum(min(cp[k], cg[k]) for k in cp)


# ── charging sections ─────────────────────────────────────────────
# The penalising sections of the SEBI Act. Leading \b so "115HA" does not match
# at offset 1; no trailing \b, because after the ")" of "15A(a)" the next
# character is a space and two non-word characters make no boundary - which
# silently truncated "15A(a)" to "15A" and quietly merged two distinct sections.
_SECTION = re.compile(r"\b(15[A-Z]{1,2}(?:\s*\([a-z]\))?)", re.I)


def normalise_section(value: object) -> str:
    """`"15HA"`, `"15HA of the SEBI Act, 1992"` and `"Section 15HA"` are one answer.

    Systems return the section with its statute attached, because that is how
    the order writes it. Folding whitespace and case is not enough - the old
    normalisation turned the second of those into `15HAOFTHESEBIACT,1992` and
    scored it against `15HA` as a miss, which grades the padding rather than
    the reading.

    Anything with no section token in it is returned folded but intact, so a
    genuinely wrong answer ("Section 446(1) of the Companies Act") stays wrong.
    """
    s = str(value or "")
    m = _SECTION.search(s)
    if m:
        return m.group(1).upper().replace(" ", "")
    return s.upper().replace(" ", "")


# ── T1: structured extraction ─────────────────────────────────────
def score_extraction(pred: dict, gold: dict) -> dict[str, float]:
    """Field-level scores. Never blended - a strong name score must not hide a
    weak penalty-attribution score, which is the field that actually matters.
    """
    out: dict[str, float] = {}

    def triples(d):
        return [(normalise_name(n.get("name", "")), n.get("penalty_inr"),
                 normalise_section(n.get("charging_section")))
                for n in d.get("noticees", []) or []]

    tp, tg = triples(pred), triples(gold)
    for label, idx in (("noticee_name", (0,)), ("penalty_attribution", (0, 1)),
                       ("full_triple", (0, 1, 2))):
        p = [tuple(t[i] for i in idx) for t in tp]
        g = [tuple(t[i] for i in idx) for t in tg]
        for k, v in _prf(_multiset_tp(p, g), len(p), len(g)).items():
            out[f"{label}_{k}"] = v

    pp = {str(x).upper().replace(" ", "") for x in pred.get("violated_provisions", []) or []}
    gg = {str(x).upper().replace(" ", "") for x in gold.get("violated_provisions", []) or []}
    for k, v in _prf(len(pp & gg), len(pp), len(gg)).items():
        out[f"provisions_{k}"] = v

    out["penalty_type_exact"] = float(
        (pred.get("penalty_type") or "").lower() == (gold.get("penalty_type") or "").lower())
    out["total_penalty_exact"] = float(pred.get("total_penalty_inr") == gold.get("total_penalty_inr"))
    return out


# ── T2 / T5: label prediction ─────────────────────────────────────
def score_labels(pred: list[str], gold: list[str], label_set: list[str]) -> dict[str, float]:
    """Macro-F1 over a fixed label set.

    Macro, not micro: the charging-section distribution is dominated by 15HB,
    and micro-F1 would reward a system that always guesses the majority class.
    """
    per: dict[str, float] = {}
    for lab in label_set:
        tp = sum(1 for p, g in zip(pred, gold) if p == lab and g == lab)
        fp = sum(1 for p, g in zip(pred, gold) if p == lab and g != lab)
        fn = sum(1 for p, g in zip(pred, gold) if p != lab and g == lab)
        per[lab] = 2 * tp / (2 * tp + fp + fn) if (2 * tp + fp + fn) else 0.0
    macro = sum(per.values()) / len(label_set) if label_set else 0.0
    acc = sum(1 for p, g in zip(pred, gold) if p == g) / len(gold) if gold else 0.0
    return {"macro_f1": round(macro, 4), "accuracy": round(acc, 4),
            **{f"f1_{k}": round(v, 4) for k, v in per.items()}}


def majority_class_baseline(gold: list[str], label_set: list[str]) -> dict[str, float]:
    """The floor T2 must clear. Published alongside every T2 result."""
    if not gold:
        return {"macro_f1": 0.0, "accuracy": 0.0}
    top = Counter(gold).most_common(1)[0][0]
    return score_labels([top] * len(gold), gold, label_set)


# ── T3: numeric ───────────────────────────────────────────────────
def same_answer(pred: object, gold: object) -> bool:
    """Exact match on the *value*, not on the spelling of it.

    T3 and T4 were comparing `str(p).strip() == str(g).strip()`, so a system
    that answered `` ` 5,00,000/- (Rupees Five Lakh only) `` - the operative
    text, verbatim and correct - was scored a miss against a gold of `500000`.
    That is a formatting penalty dressed up as a comprehension one, and it
    would have deflated every entry on the leaderboard in the same direction,
    which is the kind of error that never looks like an error.

    Amount-vs-amount compares as integers. Anything else falls back to
    case-folded string equality, so `not stated` and dates are unaffected.
    """
    if pred is None:
        return False
    p, g = parse_answer(pred), parse_answer(gold)
    if p is not None and g is not None:
        return p == g
    return str(pred).strip().casefold() == str(gold).strip().casefold()


def score_numeric(pred: list, gold: list) -> dict[str, float]:
    """Exact match. A penalty total is right or wrong; partial credit would be
    a made-up quantity."""
    if not gold:
        return {"exact_match": 0.0, "n": 0}
    hits = sum(1 for p, g in zip(pred, gold) if same_answer(p, g))
    return {"exact_match": round(hits / len(gold), 4), "n": len(gold)}


# ── T4: abstention ────────────────────────────────────────────────
ABSTAIN = "not stated"


def score_abstention(pred: list[str], gold: list[str]) -> dict[str, float]:
    """Two numbers, deliberately never averaged.

    A system that abstains on everything scores 1.0 abstention / 0.0 answerable;
    one that never abstains scores the reverse. Reporting a single blended figure
    would hide exactly the behaviour this task exists to measure.
    """
    ans_p = [p for p, g in zip(pred, gold) if g.strip().lower() != ABSTAIN]
    ans_g = [g for g in gold if g.strip().lower() != ABSTAIN]
    unans = [p for p, g in zip(pred, gold) if g.strip().lower() == ABSTAIN]

    acc = (sum(1 for p, g in zip(ans_p, ans_g) if same_answer(p, g))
           / len(ans_g)) if ans_g else 0.0
    abst = (sum(1 for p in unans if p.strip().lower() == ABSTAIN) / len(unans)) if unans else 0.0
    return {"answerable_accuracy": round(acc, 4), "abstention_rate": round(abst, 4),
            "n_answerable": len(ans_g), "n_unanswerable": len(unans)}


SCORERS = {
    "t1_extraction": score_extraction,
    "t2_charging_section": score_labels,
    "t3_numeric": score_numeric,
    "t4_abstention": score_abstention,
    "t5_attribution": score_labels,
}
