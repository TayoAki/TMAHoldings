#!/usr/bin/env python3
"""PreToolUse hook: keep agents out of the human-only parts of the holdco.

Blocks (exit code 2, reason on stderr) when an agent tries to:
  * run a human-only holdco command (approve, send, send-back, answer, cancel,
    shadow, rollout, rules accept, rules reject);
  * forge a human context in inline Python (ExecutionContext(...), human_terminal(),
    simulated_demo()). Plain calls to approve() etc. need no hook: the library
    itself refuses them when CLAUDECODE is set;
  * switch off the agent marker the CLI relies on (unset CLAUDECODE, env -u ...);
  * write, edit, move or delete protected state: outboxes, approvals, job state,
    corrections and rollout logs, proposals, golden cases, business.json.

This is the second of three layers. The first is the holdco CLI itself, which
refuses human-only actions inside an agent session; the third is the content
hash checked at send time. None of them depends on an agent remembering a rule.
"""

from __future__ import annotations

import json
import re
import shlex
import sys

HUMAN_ONLY = {"approve", "send", "send-back", "answer", "cancel", "shadow", "rollout"}
HUMAN_ONLY_RULES = {"accept", "reject"}
CONTEXT_FORGING = re.compile(r"\b(ExecutionContext|human_terminal|simulated_demo)\b")
INLINE_PYTHON = re.compile(r"python[0-9.]*\s+(-c\b|-\s|-$|<<)")
PROTECTED = re.compile(
    r"(/|^)(outbox/|golden/|proposals/)|(approved\.json|job\.json|human-version\.json|business\.json"
    r"|corrections-log\.jsonl|rollout-log\.jsonl)$"
)
PROTECTED_IN_COMMAND = re.compile(
    r"(outbox/|golden/|proposals/|approved\.json|job\.json|human-version\.json|business\.json"
    r"|corrections-log\.jsonl|rollout-log\.jsonl)"
)
DESTRUCTIVE = {"rm", "mv", "truncate", "touch", "shred", "chmod", "chown", "tee", "dd", "unlink"}
COPYING = {"cp", "rsync", "install", "ln"}
REDIRECT = re.compile(r"(?<![0-9&])>>?\s*([^\s;&|]+)|[0-9]>>?\s*([^\s;&|]+)")
PY_WRITE = re.compile(r"open\([^)]*['\"][wax]|write_text|write_bytes|unlink\(|rmtree|os\.remove")
GUARD_TAMPERING = re.compile(r"unset\s+[^;&|]*\b(CLAUDECODE|HOLDCO_AGENT)\b|env\s+(-\S+\s+)*-u\s*(CLAUDECODE|HOLDCO_AGENT)"
                             r"|\b(CLAUDECODE|HOLDCO_AGENT)=(\s|$|''|\"\")")
SEGMENT_SPLIT = re.compile(r"&&|\|\||;|\||\n")


def _holdco_subcommand(tokens: list[str]) -> tuple[str | None, str | None]:
    """Return (subcommand, next token) if this segment invokes the holdco CLI."""
    for i, tok in enumerate(tokens):
        is_module = tok == "-m" and i + 1 < len(tokens) and tokens[i + 1] == "holdco"
        is_script = tok.endswith(("holdco/cli.py", "holdco/__main__.py")) or tok == "holdco"
        if not (is_module or is_script):
            continue
        j = i + 2 if is_module else i + 1
        while j < len(tokens) and tokens[j].startswith("--root"):
            j += 1 if "=" in tokens[j] else 2
        if j < len(tokens):
            return tokens[j], tokens[j + 1] if j + 1 < len(tokens) else None
    return None, None


def check_bash(command: str) -> str | None:
    if GUARD_TAMPERING.search(command):
        return "Changing CLAUDECODE/HOLDCO_AGENT would disable the human-only guard."
    if "holdco" in command and CONTEXT_FORGING.search(command) and INLINE_PYTHON.search(command):
        return "Building a human ExecutionContext from inline Python would bypass the human-only guard."
    for segment in SEGMENT_SPLIT.split(command):
        try:
            tokens = shlex.split(segment)
        except ValueError:
            tokens = segment.split()
        sub, nxt = _holdco_subcommand(tokens)
        if sub in HUMAN_ONLY or (sub == "rules" and nxt in HUMAN_ONLY_RULES):
            label = f"rules {nxt}" if sub == "rules" else sub
            return f"`holdco {label}` is human-only. Tell the person the exact command to run in their own terminal."
    if PROTECTED_IN_COMMAND.search(command):
        for segment in SEGMENT_SPLIT.split(command):
            if _mutates_protected(segment):
                return ("This command would change protected holdco state (outbox, approvals, job state, logs, "
                        "proposals, golden cases or business.json). Only the holdco CLI and people change those.")
    return None


def _mutates_protected(segment: str) -> bool:
    for groups in REDIRECT.findall(segment):
        target = next((g for g in groups if g), "")
        if PROTECTED_IN_COMMAND.search(target):
            return True
    try:
        tokens = shlex.split(segment)
    except ValueError:
        tokens = segment.split()
    while tokens and ("=" in tokens[0] and not tokens[0].startswith("-") or tokens[0] in ("sudo", "command")):
        tokens = tokens[1:]
    if not tokens:
        return False
    prog = tokens[0].rsplit("/", 1)[-1]
    args = [t for t in tokens[1:] if not t.startswith("-")]
    hits = [a for a in args if PROTECTED_IN_COMMAND.search(a)]
    if prog in DESTRUCTIVE and hits:
        return True
    if prog in COPYING and args and PROTECTED_IN_COMMAND.search(args[-1]):
        return True
    if prog == "sed" and hits and any(t.startswith("-i") or t == "--in-place" for t in tokens[1:]):
        return True
    if prog == "git" and len(tokens) > 1 and tokens[1] in ("rm", "mv", "checkout", "restore", "clean") and hits:
        return True
    if prog.startswith("python") and PY_WRITE.search(segment):
        return True
    return False


def check_path(path: str) -> str | None:
    normalized = path.replace("\\", "/")
    if PROTECTED.search(normalized):
        if "/work/" in normalized and not normalized.endswith(("job.json", "approved.json")):
            return None
        if normalized.endswith("/golden/README.md"):  # documentation about the cases, not a case
            return None
        return (f"{path} is protected holdco state. Agents write drafts only to a job's work/ folder; "
                "approvals, sends, logs and golden cases are written by the holdco CLI for a person.")
    return None


def main() -> int:
    try:
        event = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0
    tool = event.get("tool_name", "")
    data = event.get("tool_input") or {}
    if tool == "Bash":
        reason = check_bash(data.get("command", ""))
    elif tool in ("Write", "Edit", "MultiEdit", "NotebookEdit"):
        reason = check_path(data.get("file_path") or data.get("notebook_path") or "")
    else:
        reason = None
    if reason:
        print(f"Blocked by the holdco human-only guard: {reason}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
