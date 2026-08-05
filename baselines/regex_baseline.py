"""
Trivial regex baseline. This is the floor.

Its purpose is to prove the tasks are not degenerate. If a system built out of
`re.findall` scores well on a task, that task is measuring string formatting and
should be cut — that rule already removed `order_date` and
`adjudicating_officer` from T1 during task design.

Deliberately naive in the way a first attempt is naive: it takes the *first*
currency amount and the *nearest* name. Both are wrong in known ways, and making
them wrong on purpose is the point.

    indic-reg-bench evaluate --system baselines/regex_baseline.py
"""

from __future__ import annotations

import re
from collections import Counter

from indic_reg_bench.numerals import parse_amount

SECTION_RE = re.compile(r"section\s+(15[A-Z]{1,2}(?:\([a-z]\))?)", re.I)
NAME_RE = re.compile(r"\b(?:Mr\.|Ms\.|M/s\.?|Shri|Smt\.?)\s+([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+){0,3})")
PROVISION_RE = re.compile(r"\b(PFUTP|PIT|SAST|LODR|ICDR|AIF)\b")


class System:
    name = "regex-baseline"
    cost_usd = 0.0

    def predict(self, task: str, example: dict) -> object:
        text = re.sub(r"\s+", " ", example.get("text", ""))

        if task == "t1_extraction":
            name = NAME_RE.search(text)
            return {
                "noticees": [{
                    "name": name.group(1) if name else "",
                    # first amount in the document - wrong whenever the order
                    # quotes a settlement plea or a statutory maximum first
                    "penalty_inr": parse_amount(text),
                    "charging_section": (SECTION_RE.search(text) or [None, None])[1],
                }],
                "violated_provisions": sorted(set(PROVISION_RE.findall(text))),
                "penalty_type": "monetary" if "penalty" in text.lower() else "none",
                "total_penalty_inr": parse_amount(text),
            }

        if task == "t2_charging_section":
            found = SECTION_RE.findall(text)
            # most frequent mention, which is dominated by procedural citations
            return Counter(s.upper() for s in found).most_common(1)[0][0] if found else "15HB"

        if task == "t3_numeric":
            return parse_amount(text)

        if task == "t4_abstention":
            # never abstains: the behaviour T4 exists to catch
            return parse_amount(text) or "unknown"

        if task == "t5_attribution":
            return "imposed"   # always the majority guess

        raise ValueError(f"unsupported task: {task}")
