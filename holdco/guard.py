"""The human approval rule, enforced.

Approving, sending, answering an agent's question, and accepting a rule are
human-only actions. The CLI refuses them when it detects an agent context
(Claude Code sets CLAUDECODE=1 in every shell it runs; other runners should
set HOLDCO_AGENT=1) or when there is no interactive terminal.

This is defense in depth against a mistaken or over-eager agent, not a
cryptographic guarantee: the Claude Code hook in .claude/hooks/ and the
permission deny-list in .claude/settings.json are the other two layers, and
send() re-checks the approved content hash so nothing can change after a
person signs off.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass

from holdco.config import Business

# CLAUDECODE is set by Claude Code; HOLDCO_AGENT is ours for any other runner.
# The last two are best-effort markers other agent CLIs may set in their shells.
AGENT_ENV_VARS = ("CLAUDECODE", "HOLDCO_AGENT", "CODEX_SANDBOX", "GEMINI_CLI")


class HumanOnlyError(PermissionError):
    """Raised when a human-only action is attempted outside a human context."""


@dataclass(frozen=True)
class ExecutionContext:
    interactive: bool
    agent: bool
    simulated: bool = False

    @classmethod
    def detect(cls) -> "ExecutionContext":
        agent = any(os.environ.get(var) for var in AGENT_ENV_VARS)
        interactive = sys.stdin.isatty() and sys.stdout.isatty()
        return cls(interactive=interactive, agent=agent)

    @classmethod
    def human_terminal(cls) -> "ExecutionContext":
        """Used by tests to stand in for a person at a real terminal."""
        return cls(interactive=True, agent=False)

    @classmethod
    def simulated_demo(cls) -> "ExecutionContext":
        """Scripted 'human' for the demo; refused on any business not marked demo."""
        return cls(interactive=False, agent=False, simulated=True)

    @property
    def method(self) -> str:
        if self.simulated:
            return "simulated-demo"
        return "interactive-terminal"


def require_human(ctx: ExecutionContext, biz: Business, action: str, person: str | None = None) -> None:
    if ctx.simulated:
        if not biz.is_demo:
            raise HumanOnlyError(
                f"'{action}' with a simulated human is only allowed on demo businesses; "
                f"'{biz.slug}' is a real business."
            )
    else:
        if ctx.agent:
            raise HumanOnlyError(
                f"'{action}' is human-only and was called from an agent context "
                "(CLAUDECODE/HOLDCO_AGENT is set). Ask a person to run it in their own terminal."
            )
        if not ctx.interactive:
            raise HumanOnlyError(f"'{action}' is human-only and needs an interactive terminal.")
    if person is not None:
        if not person.strip():
            raise HumanOnlyError(f"'{action}' needs the name of the person doing it (--by).")
        approvers = biz.approvers
        if approvers and person not in approvers:
            raise HumanOnlyError(
                f"{person} is not an approver for {biz.slug}. Approvers: {', '.join(approvers)} "
                "(edit business.json to change who can approve)."
            )
