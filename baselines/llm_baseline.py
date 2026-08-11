"""
A local-LLM baseline, run through Ollama.

The regex baseline is the floor. This is the next rung: a small instruction-
tuned model reading the order and answering directly. It exists so the
leaderboard opens with a spread rather than a single number, and so the
question "does an LLM already solve this?" has a measured answer instead of an
assumed one.

Runs entirely on localhost, so `cost_usd` is genuinely 0.0 and no key is
needed. Cost is wall-clock, which the harness already records.

    ollama pull llama3.2
    indic-reg-bench evaluate --system baselines/llm_baseline.py

    IRB_OLLAMA_MODEL=qwen2.5:7b indic-reg-bench evaluate --system baselines/llm_baseline.py

**This system is not a label source.** Its outputs are predictions scored
against the gold set, never material the gold set is built from. Pre-filling a
human label from a model that then appears on the same leaderboard is how a
benchmark ends up measuring its own annotator - the same failure `label.py`
refuses regex pre-fill to avoid, wearing a better coat.

`urllib` rather than the `ollama` package: one POST to one endpoint does not
justify a dependency, and the baseline must stay installable from the repo's
existing requirements.
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request

from indic_reg_bench.numerals import parse_answer

HOST = os.environ.get("IRB_OLLAMA_HOST", "http://localhost:11434")
MODEL = os.environ.get("IRB_OLLAMA_MODEL", "llama3.2")
TIMEOUT = float(os.environ.get("IRB_OLLAMA_TIMEOUT", "120"))

# Orders run to a median 36,000 characters, past the context window of the
# small models this is meant to run on. The operative paragraph sits at the
# end, before the signature block, so the tail is a crude but honest retrieval
# step - and it is *this system's* choice, not a fixture the harness grants.
# A system that wants the whole document is free to take `example["text"]`
# entire; the truncation is what makes this baseline beatable.
TAIL_CHARS = int(os.environ.get("IRB_TAIL_CHARS", "6000"))

SYSTEM_PROMPT = (
    "You read Indian securities-regulator adjudication orders. "
    "Answer only from the text given. Never guess a number that is not present. "
    "A backtick (`) before a number is a rupee sign. "
    "Amounts quoted from a party's own settlement plea are not the penalty; "
    "the penalty is what the officer imposes in their own voice."
)

TASK_PROMPT = {
    "t1_extraction": (
        'Return JSON: {"noticees":[{"name":str,"penalty_inr":int|null,'
        '"charging_section":str|null}],"violated_provisions":[str],'
        '"penalty_type":"monetary"|"debarment"|"warning"|"none"|"other",'
        '"total_penalty_inr":int}. One entry per (noticee, penalty, section) '
        "triple; repeat a name penalised under two sections. penalty_inr is a "
        "plain integer of rupees, no commas."
    ),
    "t2_charging_section": (
        "Which section is the penalty imposed under? Answer with the section "
        "number alone, one of: 15A(a) 15A(b) 15A(c) 15EA 15EB 15G 15HA 15HB."
    ),
    "t3_numeric": (
        "Answer the question with a single integer or date and nothing else."
    ),
    "t4_abstention": (
        "Answer the question. If the order does not state it anywhere, reply "
        "exactly: not stated"
    ),
    "t5_attribution": (
        "Who put forward the highlighted amount? Reply with exactly one of: "
        "imposed proposed_by_noticee cited_precedent scn_proposed other"
    ),
}


def _ask(prompt: str, want_json: bool) -> str:
    body = {
        "model": MODEL,
        "prompt": prompt,
        "system": SYSTEM_PROMPT,
        "stream": False,
        # Greedy. A baseline that changes its answer between runs cannot be
        # compared against itself, let alone against anything else.
        "options": {"temperature": 0.0, "seed": 42},
    }
    if want_json:
        body["format"] = "json"
    req = urllib.request.Request(
        f"{HOST}/api/generate",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return json.loads(r.read().decode("utf-8")).get("response", "")
    except urllib.error.URLError as e:
        raise RuntimeError(
            f"cannot reach Ollama at {HOST} ({e}). Start it with `ollama serve` "
            f"and `ollama pull {MODEL}`."
        ) from e


def _coerce_int(v: object) -> int | None:
    """Models return '5,00,000', '` 5,00,000/-' and 500000 for the same amount."""
    return parse_answer(v)


class System:
    name = f"ollama-{MODEL}"
    cost_usd = 0.0

    def predict(self, task: str, example: dict) -> object:
        text = re.sub(r"[ \t]+", " ", example.get("text", ""))[-TAIL_CHARS:]
        question = example.get("question", "")
        instruction = TASK_PROMPT[task]

        parts = [instruction, f"\n--- ORDER (final {TAIL_CHARS} characters) ---\n{text}"]
        if question:
            parts.append(f"\n--- QUESTION ---\n{question}")
        if task == "t5_attribution" and example.get("span"):
            parts.append(f"\n--- AMOUNT IN QUESTION ---\n{example['span']}")
        raw = _ask("\n".join(parts), want_json=(task == "t1_extraction")).strip()

        if task == "t1_extraction":
            obj = json.loads(raw)  # a model that cannot emit JSON is an error, not a zero
            noticees = []
            for n in obj.get("noticees") or []:
                if not isinstance(n, dict):
                    continue
                noticees.append({
                    "name": str(n.get("name") or ""),
                    "penalty_inr": _coerce_int(n.get("penalty_inr")),
                    "charging_section": (str(n["charging_section"]).upper()
                                         if n.get("charging_section") else None),
                })
            total = _coerce_int(obj.get("total_penalty_inr"))
            return {
                "noticees": noticees,
                "violated_provisions": [str(p) for p in (obj.get("violated_provisions") or [])],
                "penalty_type": obj.get("penalty_type") or None,
                # Falling back to the sum keeps a model that itemises correctly
                # but cannot add from being scored as if it read nothing.
                "total_penalty_inr": total if total is not None
                else sum(n["penalty_inr"] or 0 for n in noticees),
            }

        # Returned verbatim: the scorer normalises both sides through
        # `parse_answer`, so coercing here would only add a way to lose a
        # correct answer ("45 days") that the scorer handles better.
        if task == "t3_numeric":
            return raw

        # Small models pad single-label answers ("The section is 15HA.").
        if task == "t2_charging_section":
            m = re.search(r"15[A-Z]{1,2}(?:\([a-c]\))?", raw, re.I)
            return m.group(0).upper() if m else raw
        if task == "t5_attribution":
            for label in ("proposed_by_noticee", "cited_precedent", "scn_proposed",
                          "imposed", "other"):
                if label in raw.lower():
                    return label
            return raw

        return raw  # t4: the answer, or "not stated"
