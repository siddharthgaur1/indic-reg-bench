"""Error paths for the benchmark's public surface.

This is the one repo in the portfolio with an external identity: other people
plug their systems in and publish numbers from it. Its failure behaviour is
therefore part of its contract, not an implementation detail -- if a bad
adapter file produces a confusing error, or a crashing system silently scores
as a zero instead of a reported error count, someone else's published result is
wrong and they have no way to see it.

None of these paths had a test before.
"""

from __future__ import annotations

import textwrap

import pytest

from indic_reg_bench.adapter import load_system
from indic_reg_bench.evaluate import run_task


# --- adapter loading: how an outside system plugs in -------------------------

def test_missing_system_file_names_the_path_it_looked_for(tmp_path):
    missing = tmp_path / "nope.py"
    with pytest.raises(FileNotFoundError) as exc:
        load_system(missing)
    # The resolved path must appear, or the user cannot tell a typo from a
    # working-directory problem.
    assert "nope.py" in str(exc.value)


def test_a_file_without_a_System_class_says_so(tmp_path):
    f = tmp_path / "no_class.py"
    f.write_text("x = 1\n", encoding="utf-8")
    with pytest.raises(AttributeError) as exc:
        load_system(f)
    assert "System" in str(exc.value)


def test_an_adapter_that_raises_on_import_propagates_the_real_error(tmp_path):
    """The underlying error must survive, not be flattened into ImportError.

    A adapter with a typo should report the typo.
    """
    f = tmp_path / "broken.py"
    f.write_text("import a_module_that_does_not_exist\n", encoding="utf-8")
    with pytest.raises(ModuleNotFoundError):
        load_system(f)


def test_a_failing_constructor_propagates_its_own_error(tmp_path):
    """The realistic failure: __init__ loads model weights or a key and fails.

    The user's own exception must survive with its message -- being told
    "cannot import" when the real cause is a missing checkpoint sends them to
    the wrong problem.
    """
    f = tmp_path / "bad_init.py"
    f.write_text(
        textwrap.dedent(
            """
            class System:
                def __init__(self):
                    raise RuntimeError('could not load model weights')

                def predict(self, task, example):
                    return None
            """
        ),
        encoding="utf-8",
    )
    with pytest.raises(RuntimeError, match="could not load model weights"):
        load_system(f)


def test_a_system_without_a_name_gets_one_from_the_filename(tmp_path):
    f = tmp_path / "my_pipeline.py"
    f.write_text("class System:\n    def predict(self, task, example):\n        return None\n",
                 encoding="utf-8")
    system = load_system(f)
    assert system.name == "my_pipeline"


# --- the runner's central promise -------------------------------------------

class _AlwaysCrashes:
    name = "always-crashes"

    def predict(self, task, example):
        raise RuntimeError("boom")


class _CrashesOnSome:
    name = "crashes-on-some"

    def predict(self, task, example):
        if example["id"] % 2 == 0:
            raise ValueError("bad input")
        return "not stated"


def _examples(n: int) -> list[dict]:
    return [{"id": i, "gold": "not stated"} for i in range(n)]


def test_a_crashing_system_is_a_result_not_a_stop():
    """The adapter docstring promises this; nothing verified it.

    'a system that crashes on 3% of inputs should be visible as such, not be
    unrunnable' -- so run_task must complete and report the count.
    """
    result = run_task(_AlwaysCrashes(), "t4_abstention", _examples(10))
    assert result.errors == 10
    assert result.n == 10


def test_partial_crashes_are_counted_not_hidden():
    result = run_task(_CrashesOnSome(), "t4_abstention", _examples(10))
    assert result.errors == 5, "half the examples raise; all five must be counted"
    assert result.n == 10


def test_error_examples_carry_the_id_and_the_exception_type():
    """Without these a user sees a number and cannot debug it."""
    result = run_task(_CrashesOnSome(), "t4_abstention", _examples(10))
    assert result.error_examples, "at least one error example must be recorded"
    first = result.error_examples[0]
    assert "id" in first
    assert "ValueError" in first["error"]
    assert "bad input" in first["error"]


def test_error_examples_are_capped_so_a_totally_broken_system_cannot_flood():
    result = run_task(_AlwaysCrashes(), "t4_abstention", _examples(100))
    assert result.errors == 100
    assert len(result.error_examples) <= 5


def test_an_unknown_task_id_is_rejected_by_name():
    with pytest.raises(ValueError) as exc:
        run_task(_AlwaysCrashes(), "t9_does_not_exist", _examples(1))
    assert "t9_does_not_exist" in str(exc.value)
