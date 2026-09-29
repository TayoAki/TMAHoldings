"""The human approval rule, enforced in layers.

1. Human-only actions (approve, send, answer, shadow, rollout, rules accept, ...)
   refuse to run unless BOTH the caller's context and the real process
   environment say a person is at an interactive terminal outside any agent
   session. Claude Code sets CLAUDECODE=1 in every shell it runs; other runners
   should set HOLDCO_AGENT=1. Passing a made-up context doesn't get past it.
2. Approving and sending also need the approver's passphrase (holdco/keys.py):
   every approval and every release is signed with a key derived from it, and
   `holdco outbox verify` checks those signatures and the released files.
3. The Claude Code hook (.claude/hooks/human_only_guard.py) blocks human-only
   commands and writes to protected state before they run.

What this does not stop: a program running under your own OS account that is
determined to cheat can rewrite this code or your key files. For real client
work, run agents under a separate OS user or container with no write access to
businesses/ and no access to the key store (runbook 09).
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


def environment() -> tuple[bool, bool]:
    """(interactive, agent) for the real process, whatever a caller claims."""
    agent = any(os.environ.get(var) for var in AGENT_ENV_VARS)
    interactive = sys.stdin.isatty() and sys.stdout.isatty()
    return interactive, agent


@dataclass(frozen=True)
class ExecutionContext:
    interactive: bool
    agent: bool
    simulated: bool = False

    @classmethod
    def detect(cls) -> "ExecutionContext":
        interactive, agent = environment()
        return cls(interactive=interactive, agent=agent)

    @classmethod
    def human_terminal(cls) -> "ExecutionContext":
        """What a person at a real terminal looks like (tests patch environment() to match)."""
        return cls(interactive=True, agent=False)

    @classmethod
    def simulated_demo(cls) -> "ExecutionContext":
        """Scripted 'human' for the demo; refused on any business not marked demo."""
        return cls(interactive=False, agent=False, simulated=True)

    @property
    def method(self) -> str:
        return "simulated-demo" if self.simulated else "interactive-terminal"


def allowed_people(biz: Business) -> list[str]:
    """Approvers (client work) plus owners (the holdco owner, who also makes the rule and rollout calls)."""
    return list(dict.fromkeys(biz.approvers + biz.owners))


def require_human(ctx: ExecutionContext, biz: Business, action: str, person: str | None = None) -> None:
    if ctx.simulated:
        if not biz.is_demo:
            raise HumanOnlyError(
                f"'{action}' with a simulated human is only allowed on demo businesses; "
                f"'{biz.slug}' is a real business."
            )
    else:
        interactive, agent = environment()
        if ctx.agent or agent:
            raise HumanOnlyError(
                f"'{action}' is human-only and was called from an agent context "
                "(CLAUDECODE/HOLDCO_AGENT is set). Ask a person to run it in their own terminal."
            )
        if not (ctx.interactive and interactive):
            raise HumanOnlyError(f"'{action}' is human-only and needs an interactive terminal.")
    if person is not None:
        if not person.strip():
            raise HumanOnlyError(f"'{action}' needs the name of the person doing it (--by).")
        people = allowed_people(biz)
        if people and person not in people:
            raise HumanOnlyError(
                f"{person} is not an approver or owner for {biz.slug}. Allowed: {', '.join(people)} "
                "(a person edits business.json to change who can approve)."
            )
