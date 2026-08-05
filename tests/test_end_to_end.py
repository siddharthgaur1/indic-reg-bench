"""
End-to-end plumbing check: adapter loading -> runner -> scoring -> report.

The fixture below is SYNTHETIC and exists only to exercise the harness. It is
written to a temp directory, never to data/, and is not benchmark data. No score
produced here means anything about any system.
"""

import json

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
