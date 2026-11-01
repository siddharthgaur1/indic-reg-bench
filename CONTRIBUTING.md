# Contributing

## Read this first: there is no gold set yet

The gold set is **0 of a target 150** orders (see [Status](README.md#status)).
Until it exists, `indic-reg-bench evaluate` has nothing real to score against,
the leaderboard is empty, and no system — including the two baselines — has a
score. A system PR can be reviewed and its adapter checked now; its numbers
cannot be published until gold labels land.

Model-generated labels are silver: the harness will score against them, but the
report is bannered `NOT A BENCHMARK RESULT` and they never enter the gold set or
the leaderboard.

## Submitting a system

A system is one `.py` file defining a class named `System`
(contract: [`src/indic_reg_bench/adapter.py`](src/indic_reg_bench/adapter.py)):

```python
class System:
    name = "my-pipeline"      # optional; defaults to the file name
    cost_usd = 0.42           # optional, reported next to accuracy

    def predict(self, task: str, example: dict) -> object:
        ...
```

`task` is one of the ids printed by `indic-reg-bench tasks`
(`t1_extraction`, `t2_charging_section`, `t3_numeric`, `t4_abstention`,
`t5_attribution`); `example["text"]` is the order text. Return the shape that
task specifies in §3 of [`docs/phase1-task-design.md`](docs/phase1-task-design.md#3-tasks-that-survive);
[`baselines/regex_baseline.py`](baselines/regex_baseline.py) is a complete
worked example for all five. Raising is allowed — the example is scored as a
miss.

Check that your adapter runs end to end against the synthetic smoke fixtures
(the scores this prints are meaningless — one or two made-up orders per task):

```bash
pip install -e .
indic-reg-bench evaluate --system path/to/your_system.py --data tests/fixtures/smoke --json out.json
```

Against real data the command is the same with `--data data/splits/test`
(the default), which you build locally — order text is not redistributed; see
[Rebuild the corpus](README.md#rebuild-the-corpus) and
[Evaluate a system](README.md#evaluate-a-system). `--tasks` restricts the run to
a subset.

Before the gold set exists, you can still run a system over the exact orders
that will be labelled, so scoring later is a join rather than a re-run:

```bash
python scripts/run_baseline.py --system path/to/your_system.py --task t1_extraction --limit 150
```

One task per run (`--task`, default `t1_extraction`); output goes to
`predictions/<system>.<task>.jsonl`.

Then open a PR with the adapter file, the `--json` output, and a one-line
description of the system. Results are reproduced before merge.

## Changing the harness

Run what CI runs (`.github/workflows/tests.yml`) before opening a PR:

```bash
pip install -e . pytest
python -m pytest tests/ -q
python scripts/test_fetch_orders.py
indic-reg-bench tasks
```

CI has no network and no corpus by design; tests use captured markup and the
fixtures under `tests/fixtures/`. Don't add a test that needs either.
