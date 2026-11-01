"""The test queue, T4/T5 eval rows, label provenance and labelling time.

Everything here is synthetic or read from committed id lists. No order text.
"""

from __future__ import annotations

import builtins
import json
import sqlite3
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import build_eval_set  # noqa: E402
import build_test_queue  # noqa: E402
import label  # noqa: E402
from indic_reg_bench.evaluate import run_task  # noqa: E402

SPLITS = REPO / "data" / "splits"


def committed(name: str) -> list[str]:
    return json.loads((SPLITS / name).read_text(encoding="utf-8"))


def in_family(url: str) -> bool:
    # Plain substrings rather than the builder's own regex, which once matched
    # neither spelling and passed a check written with the same mistake.
    return "illiquid" in url or "ill-liquid" in url


def test_committed_queue_is_what_the_script_builds():
    built = build_test_queue.build_queue(committed("test_ids.json"), build_test_queue.load_titles())
    assert committed("test_queue_ids.json") == built


def test_family_never_exceeds_a_quarter_of_any_prefix():
    flags = [in_family(u) for u in committed("test_queue_ids.json")]
    assert sum(flags) > 0, "the check is measuring nothing"
    for n in range(4, len(flags) + 1):
        assert sum(flags[:n]) / n <= 0.25, n


def test_queue_is_test_split_only_with_no_repeats():
    queue = committed("test_queue_ids.json")
    assert len(set(queue)) == len(queue)
    assert set(queue) <= set(committed("test_ids.json"))
    assert not set(queue) & set(committed("train_ids.json"))
    assert len(queue) >= 150


def test_both_family_spellings_are_capped():
    titles = {"a": "Adjudication Order in the matter of Dealings in Ill-liquid Stock Options at BSE",
              "b": "Adjudication Order in the matter of Illiquid Stock Options"}
    assert build_test_queue.order_matter("a", titles) == build_test_queue.ILLIQUID
    assert build_test_queue.order_matter("b", titles) == build_test_queue.ILLIQUID
    assert build_test_queue.order_matter("x/ill-liquid-options_1.html", {}) == build_test_queue.ILLIQUID


def test_second_order_from_a_matter_waits_for_every_first():
    titles = {u: f"Adjudication Order in the matter of {m} Ltd"
              for u, m in [("a1", "Alpha"), ("a2", "Alpha"), ("b1", "Beta"), ("c1", "Gamma")]}
    queue = build_test_queue.build_queue(list(titles), titles)
    assert {titles[u] for u in queue[:3]} == set(titles.values())


def build(tmp_path, monkeypatch, task, record, order_date="2024-05-01"):
    db = tmp_path / "corpus.db"
    conn = sqlite3.connect(db)
    conn.execute("DROP TABLE IF EXISTS order_text")
    conn.execute("CREATE TABLE order_text (url TEXT, text TEXT, order_date TEXT)")
    conn.execute("INSERT INTO order_text VALUES (?, ?, ?)", (record["id"], "synthetic", order_date))
    conn.commit()
    conn.close()
    labels = tmp_path / "labels.jsonl"
    labels.write_text(json.dumps(record), encoding="utf-8")
    out = tmp_path / "out.jsonl"
    monkeypatch.setattr(sys, "argv", ["x", "--labels", str(labels), "--task", task,
                                      "--db", str(db), "--out", str(out)])
    assert build_eval_set.main() == 0
    return [json.loads(l) for l in out.read_text(encoding="utf-8").splitlines()]


class Echo:
    name = "echo"

    def __init__(self, answers):
        self.answers = answers

    def predict(self, task, example):
        return self.answers[example.get("question") or example.get("span")]


def test_t4_labels_become_scoreable_items(tmp_path, monkeypatch):
    rows = build(tmp_path, monkeypatch, "t4_abstention", {"id": "u", "gold": {"items": [
        {"field": "penalty_amount", "question": "Q1", "answerable": True, "gold_answer": "500000"},
        {"field": "debarment", "question": "Q2", "answerable": False, "gold_answer": "not stated"},
    ]}})
    assert [r["question"] for r in rows] == ["Q1", "Q2"]
    assert all(r["id"] == "u" and r["text"] == "synthetic" for r in rows)
    m = run_task(Echo({"Q1": "5,00,000", "Q2": "not stated"}), "t4_abstention", rows).metrics
    assert (m["answerable_accuracy"], m["abstention_rate"]) == (1.0, 1.0)
    assert (m["n_answerable"], m["n_unanswerable"]) == (1, 1)


def test_t5_labels_become_scoreable_items(tmp_path, monkeypatch):
    rows = build(tmp_path, monkeypatch, "t5_attribution", {"id": "u", "gold": {"spans": [
        {"span": "Rs. 1,00,000", "char_start": 10, "attribution": "proposed_by_noticee"},
        {"span": "Rs. 5,00,000", "char_start": 90, "attribution": "imposed"},
    ]}})
    assert [r["char_start"] for r in rows] == [10, 90]
    system = Echo({"Rs. 1,00,000": "proposed_by_noticee", "Rs. 5,00,000": "imposed"})
    assert run_task(system, "t5_attribution", rows).metrics["accuracy"] == 1.0


def test_labels_built_for_the_wrong_task_stop_the_build(tmp_path, monkeypatch):
    t4 = {"id": "u", "gold": {"items": []}}
    with pytest.raises(SystemExit, match="does not match"):
        build(tmp_path, monkeypatch, "t1_extraction", t4)
    with pytest.raises(SystemExit, match="does not match"):
        build(tmp_path, monkeypatch, "t5_attribution", t4)


def test_assisted_labels_are_refused_in_test_but_stamped_in_train(tmp_path, monkeypatch):
    rec = {"id": "u", "gold": {"noticees": []}, "provenance": label.ASSISTED}
    with pytest.raises(SystemExit, match="never allowed"):
        build(tmp_path, monkeypatch, "t1_extraction", rec)
    rows = build(tmp_path, monkeypatch, "t1_extraction", rec, order_date="2019-01-01")
    assert rows[0]["label_source"] == label.ASSISTED


def test_scratch_labels_stay_human(tmp_path, monkeypatch):
    rec = {"id": "u", "gold": {"noticees": []}, "provenance": label.SCRATCH}
    assert build(tmp_path, monkeypatch, "t1_extraction", rec)[0]["label_source"] == "human"


@pytest.mark.parametrize("flags", [
    ["--split", "test"],
    ["--split", "all"],
    ["--split", "train", "--task", "t5"],
    ["--split", "train", "--redo"],
])
def test_prefill_is_refused_outside_train_t1(flags, monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["label.py", "--prefill", "p.jsonl", *flags])
    with pytest.raises(SystemExit):
        label.main()
    assert "--prefill is only allowed" in capsys.readouterr().err


def test_prefill_rows_each_take_a_decision(monkeypatch):
    answers = iter(["", "d", "e", "Corrected Name", "300", "15hb"])
    monkeypatch.setattr(builtins, "input", lambda _="": next(answers))
    kept = label.verify_prefill({"noticees": [
        {"name": "Kept", "penalty_inr": 500000, "charging_section": "15ha"},
        {"name": "Deleted", "penalty_inr": 1, "charging_section": "15A(a)"},
        {"name": "Wrong", "penalty_inr": 2, "charging_section": None},
    ]})
    assert kept == [
        {"name": "Kept", "penalty_inr": 500000, "charging_section": "15HA"},
        {"name": "Corrected Name", "penalty_inr": 300, "charging_section": "15HB"},
    ]


def test_prefill_skips_errored_and_empty_predictions(tmp_path):
    p = tmp_path / "pred.jsonl"
    p.write_text("\n".join(json.dumps(r) for r in [
        {"id": "ok", "prediction": {"noticees": []}, "error": None},
        {"id": "err", "prediction": None, "error": "boom"},
    ]), encoding="utf-8")
    assert list(label.load_prefill(p)) == ["ok"]


def scratch(minutes):
    return [{"provenance": label.SCRATCH, "seconds": m * 60, "order_date": "2024-01-01"}
            for m in minutes]


def test_time_box_fires_on_the_first_twenty_only():
    assert label.timing_summary(scratch([16] * 20 + [1] * 100))["cut_target_to_100"] is True
    assert label.timing_summary(scratch([15] * 20))["cut_target_to_100"] is False
    assert label.timing_summary(scratch([16] * 19))["cut_target_to_100"] is False


def test_time_box_ignores_assisted_labels_and_old_rows():
    assert label.timing_summary([{"id": "old"}]) is None
    assert label.timing_summary([{"provenance": label.ASSISTED, "seconds": 99,
                                  "order_date": "2024-01-01"}]) is None


def test_time_box_ignores_scratch_train_labels():
    train = [{"provenance": label.SCRATCH, "seconds": 3600, "order_date": "2019-01-01"}] * 20
    t = label.timing_summary(train + scratch([5] * 20))
    assert (t["n"], t["first_median_min"], t["cut_target_to_100"]) == (20, 5.0, False)
