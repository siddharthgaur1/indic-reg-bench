"""
The adapter interface: how a system plugs into the benchmark.

You write one file with one class. Nothing in the harness is imported into your
system, and nothing in your system is imported into the harness beyond this
call:

    class System:
        name = "my-rag-pipeline"

        def predict(self, task: str, example: dict) -> object:
            ...

`task` is one of the task ids ("t1_extraction", ...) and `example` is the input
record. Return the output shape that task specifies. Raising is allowed - the
runner records the error and scores that example as a miss rather than dying,
because a system that crashes on 3% of inputs should be visible as such, not
be unrunnable.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Protocol, runtime_checkable


@runtime_checkable
class System(Protocol):
    name: str

    def predict(self, task: str, example: dict) -> object: ...


def load_system(path: str | Path) -> System:
    """Import a .py file and instantiate its `System` class."""
    path = Path(path).resolve()
    if not path.exists():
        raise FileNotFoundError(f"system file not found: {path}")

    spec = importlib.util.spec_from_file_location(f"_irb_system_{path.stem}", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    if not hasattr(module, "System"):
        raise AttributeError(f"{path} defines no `System` class")
    system = module.System()
    if not hasattr(system, "name"):
        system.name = path.stem
    return system
