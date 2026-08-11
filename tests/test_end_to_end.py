"""
End-to-end plumbing check: adapter loading -> runner -> scoring -> report.

The fixture below is SYNTHETIC and exists only to exercise the harness. It is
written to a temp directory, never to data/, and is not benchmark data. No score
produced here means anything about any system.
"""

import json
from pathlib import Path

from indic_reg_bench.adapter import load_system
from indic_reg_bench.evaluate import format_report, run_task

SYSTEM_SRC = '''
class System:
    name = "fixture-system"
    cost_usd = 0.25

    def predict(self, task, example):
        if example.get("boom"):
            raise RuntimeError("synthetic failure")
        return example["echo"]
'''


def _write_system(tmp_path):
    p = tmp_path / "fixture_system.py"
    p.write_text(SYSTEM_SRC, encoding="utf-8")
    return load_system(p)


def test_adapter_loads_and_runs(tmp_path):
    system = _write_system(tmp_path)
    assert system.name == "fixture-system"

    examples = [
        {"id": "a", "echo": "15HB", "gold": "15HB"},
        {"id": "b", "echo": "15HA", "gold": "15HA"},
    ]
    r = run_task(system, "t2_charging_section", examples)
    assert r.n == 2
    assert r.errors == 0
    assert r.metrics["accuracy"] == 1.0
    assert r.cost_usd == 0.25
    assert r.latency_s["mean"] >= 0


def test_a_crashing_system_is_a_result_not_a_stop(tmp_path):
    """A system that dies on some inputs must still produce a scoreable run."""
    system = _write_system(tmp_path)
    examples = [
        {"id": "a", "echo": "15HB", "gold": "15HB"},
        {"id": "b", "boom": True, "gold": "15HA"},
    ]
    r = run_task(system, "t2_charging_section", examples)
    assert r.errors == 1
    assert r.error_examples[0]["id"] == "b"
    assert r.metrics["accuracy"] == 0.5


def test_report_refuses_a_single_headline_number(tmp_path):
    system = _write_system(tmp_path)
    r = run_task(system, "t2_charging_section",
                 [{"id": "a", "echo": "15HB", "gold": "15HB"}])
    report = format_report([r])
    assert "majority_class_macro_f1" in report
    assert "No overall score is reported" in report


def test_regex_baseline_runs_on_real_text():
    """The shipped baseline must at least execute on real order text."""
    import sqlite3
    from pathlib import Path

    db = Path(__file__).resolve().parent.parent / "data" / "corpus.db"
    if not db.exists():
        return  # corpus is rebuilt locally; skip when absent

    conn = sqlite3.connect(db)
    row = conn.execute("SELECT text FROM order_text LIMIT 1").fetchone()
    conn.close()
    if not row:
        return

    system = load_system(Path(__file__).resolve().parent.parent / "baselines" / "regex_baseline.py")
    out = system.predict("t1_extraction", {"text": row[0]})
    assert "noticees" in out
    assert json.dumps(out)  # serialisable


def test_every_task_scores_end_to_end_on_the_smoke_fixture():
    """The harness had never been run across all five tasks at once.

    The gold set is empty, so `evaluate` had nothing to walk and the wiring
    between adapter, runner and the five scorers was unexercised. This fixture
    is synthetic and tiny - it proves the path, it measures nothing.
    """
    from indic_reg_bench.evaluate import evaluate
    from indic_reg_bench.scoring import SCORERS

    repo = Path(__file__).resolve().parent.parent
    results = evaluate(str(repo / "baselines" / "regex_baseline.py"),
                       repo / "tests" / "fixtures" / "smoke", list(SCORERS))

    assert [r.task for r in results] == list(SCORERS)
    assert all(r.errors == 0 for r in results), [r.error_examples for r in results]
    assert all(r.metrics for r in results)
    # The floor must stay a floor: the regex baseline takes the first amount in
    # the document, which the fixture makes the noticee's settlement plea.
    t3 = next(r for r in results if r.task == "t3_numeric")
    assert t3.metrics["exact_match"] == 0.0


def test_llm_baseline_does_not_shred_a_string_into_characters():
    """`format: json` guarantees valid JSON, not the shape you asked for.

    llama3.2 returned violated_provisions as "PFUTP, PIT" on real orders, and
    the adapter iterated it into ['P','F','U','T','P',...] - a provisions list
    that scores near zero and reads as a comprehension failure rather than a
    type mismatch.
    """
    import sys

    repo = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(repo / "baselines"))
    import llm_baseline

    system = llm_baseline.System()
    payload = json.dumps({
        "noticees": [{"name": "A Trader", "penalty_inr": "5,00,000",
                      "charging_section": "15ha"}],
        "violated_provisions": "PFUTP, PIT",
        "penalty_type": "monetary",
        "total_penalty_inr": None,
    })
    original = llm_baseline._ask
    llm_baseline._ask = lambda prompt, want_json: payload
    try:
        out = system.predict("t1_extraction", {"text": "irrelevant"})
    finally:
        llm_baseline._ask = original

    assert out["violated_provisions"] == ["PFUTP", "PIT"]
    assert out["noticees"][0]["penalty_inr"] == 500000
    assert out["noticees"][0]["charging_section"] == "15HA"
    # total was null; itemised penalties must still add up rather than vanish
    assert out["total_penalty_inr"] == 500000


def test_silver_labels_cannot_be_reported_as_a_benchmark_result(tmp_path):
    """The stamp has to be load-bearing, not decorative.

    build_eval_set.py marks model-written labels `model:<system>`. If the
    report did not act on that, a silver run would print numbers formatted
    exactly like a real result, and the context would be lost the moment
    someone pasted them into a README.
    """
    from indic_reg_bench.evaluate import format_report, run_task

    system = _write_system(tmp_path)
    examples = [{"id": "x", "echo": 500000, "gold": 500000,
                 "label_source": "model:ollama-llama3.2"}]
    report = format_report([run_task(system, "t3_numeric", examples)])
    assert "NOT A BENCHMARK RESULT" in report
    assert "model:ollama-llama3.2" in report

    human = [{"id": "x", "echo": 500000, "gold": 500000}]
    assert "NOT A BENCHMARK" not in format_report([run_task(system, "t3_numeric", human)])
