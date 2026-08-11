"""
The evaluation runner.

Records latency and cost next to every accuracy number. A system that wins by
two points at forty times the cost has not won, and the only way to make that
visible is to refuse to report accuracy on its own.
"""

from __future__ import annotations

import json
import random
import statistics
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path

from .adapter import System, load_system
from .scoring import (majority_class_baseline, score_abstention, score_extraction,
                      score_labels, score_numeric)

# Label sets are fixed so macro-F1 is comparable across systems and runs.
CHARGING_SECTIONS = ["15A(a)", "15A(b)", "15A(c)", "15EA", "15EB", "15G", "15HA", "15HB"]
ATTRIBUTION_LABELS = ["imposed", "proposed_by_noticee", "cited_precedent", "scn_proposed", "other"]

SEED = 42


@dataclass
class RunResult:
    system: str
    task: str
    n: int
    metrics: dict
    latency_s: dict
    cost_usd: float | None
    errors: int
    error_examples: list = field(default_factory=list)
    # Where the gold came from. "human" or "model:<system>" - see
    # scripts/build_eval_set.py. Carried on the result so it survives into
    # --json output, not just into the printed report.
    label_source: str = "human"


def _score(task: str, preds: list, golds: list) -> dict:
    if task == "t1_extraction":
        per = [score_extraction(p or {}, g) for p, g in zip(preds, golds)]
        keys = per[0].keys() if per else []
        return {k: round(statistics.fmean([d[k] for d in per]), 4) for k in keys}
    if task == "t2_charging_section":
        p = [str(x) for x in preds]
        g = [str(x) for x in golds]
        out = score_labels(p, g, CHARGING_SECTIONS)
        base = majority_class_baseline(g, CHARGING_SECTIONS)
        out["majority_class_macro_f1"] = base["macro_f1"]
        out["majority_class_accuracy"] = base["accuracy"]
        return out
    if task == "t3_numeric":
        return score_numeric(preds, golds)
    if task == "t4_abstention":
        return score_abstention([str(p) for p in preds], [str(g) for g in golds])
    if task == "t5_attribution":
        return score_labels([str(p) for p in preds], [str(g) for g in golds], ATTRIBUTION_LABELS)
    raise ValueError(f"unknown task: {task}")


def run_task(system: System, task: str, examples: list[dict]) -> RunResult:
    random.seed(SEED)
    preds, golds, lats, errs, err_ex = [], [], [], 0, []

    for ex in examples:
        gold = ex.get("gold")
        t0 = time.perf_counter()
        try:
            pred = system.predict(task, ex)
        except Exception as e:  # noqa: BLE001 - a crashing system is a result, not a stop
            pred, errs = None, errs + 1
            if len(err_ex) < 5:
                err_ex.append({"id": ex.get("id"), "error": f"{type(e).__name__}: {e}"})
        lats.append(time.perf_counter() - t0)
        preds.append(pred)
        golds.append(gold)

    return RunResult(
        system=getattr(system, "name", "unnamed"),
        task=task,
        n=len(examples),
        metrics=_score(task, preds, golds),
        latency_s={
            "mean": round(statistics.fmean(lats), 4) if lats else 0.0,
            "p50": round(statistics.median(lats), 4) if lats else 0.0,
            "total": round(sum(lats), 2),
        },
        cost_usd=getattr(system, "cost_usd", None),
        errors=errs,
        error_examples=err_ex,
        label_source=next((e["label_source"] for e in examples
                           if e.get("label_source", "human") != "human"), "human"),
    )


def load_examples(path: Path, task: str) -> list[dict]:
    f = Path(path) / f"{task}.jsonl"
    if not f.exists():
        return []
    return [json.loads(line) for line in f.read_text(encoding="utf-8").splitlines() if line.strip()]


def evaluate(system_path: str, data_dir: Path, tasks: list[str]) -> list[RunResult]:
    system = load_system(system_path)
    results = []
    for task in tasks:
        examples = load_examples(data_dir, task)
        if not examples:
            print(f"  {task}: no data at {data_dir}/{task}.jsonl - skipped")
            continue
        results.append(run_task(system, task, examples))
    return results


def format_report(results: list[RunResult]) -> str:
    """Per-task, never a single headline number."""
    lines = []
    # Scoring against model-written labels is a pipeline check, not a result -
    # and where the labelling model and the system under test are the same
    # model, it measures nothing at all. The banner is loud on purpose: a
    # number that reaches a README has lost the context it was produced in.
    tainted = sorted({r.label_source for r in results if r.label_source != "human"})
    if tainted:
        lines.append("!! NOT A BENCHMARK RESULT - labels came from " + ", ".join(tainted))
        lines.append("!! Silver labels exercise the harness. They do not measure a system.")
    for r in results:
        lines.append(f"\n{r.task}  (n={r.n}, system={r.system})")
        for k, v in r.metrics.items():
            lines.append(f"    {k:34} {v}")
        lines.append(f"    {'latency_mean_s':34} {r.latency_s['mean']}")
        if r.cost_usd is not None:
            lines.append(f"    {'cost_usd':34} {r.cost_usd}")
        if r.errors:
            lines.append(f"    {'errors':34} {r.errors}  e.g. {r.error_examples[:2]}")
    lines.append("\nNo overall score is reported: the tasks measure different "
                 "things and averaging them would hide which one a system failed.")
    return "\n".join(lines)


def results_to_json(results: list[RunResult]) -> str:
    return json.dumps([asdict(r) for r in results], indent=2)
