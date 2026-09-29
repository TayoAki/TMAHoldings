"""Agent runners.

Real client work runs through Claude Code agents (see .claude/workflows/
holdco-process-job.js), which record their output with ``holdco record-run``.

The ``demo`` runner is a deterministic stand-in for the bookkeeping demo. It
reads the same rule files the Claude agents read, so it proves the operating
loop (pipeline, approval gate, corrections, rules, regression tests) without
an API key.
"""

from __future__ import annotations

from holdco.config import Business, HoldcoError, Workspace


def get_runner(ws: Workspace, biz: Business, name: str = "demo", exclude_rules: set[str] | None = None):
    if name == "demo":
        from holdco.runners.demo_bookkeeping import DemoBookkeepingRunner

        return DemoBookkeepingRunner(ws, biz, exclude_rules)
    raise HoldcoError(
        f"Unknown runner '{name}'. Real work runs through Claude Code: "
        "use the holdco-process-job workflow, then `python3 -m holdco record-run`."
    )
