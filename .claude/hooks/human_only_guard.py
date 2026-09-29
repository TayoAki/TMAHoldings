#!/usr/bin/env python3
"""PreToolUse hook: keep agents out of the human-only parts of the holdco.

It blocks a tool call (exit code 2, reason on stderr) when an agent tries to:

* run a human-only holdco command (approve, send, send-back, answer, cancel, shadow,
  rollout, rules accept/reject, keys add, outbox verify), however it is wrapped
  (bash -c, eval, script -c, env, xargs, python -m holdco.__main__, ...);
* switch off the agent markers the holdco library checks (CLAUDECODE, HOLDCO_AGENT),
  or patch the guard from Python it runs or writes;
* write, move or delete protected state: a job's files outside work/ (job.json,
  approved.json, input/, drafts/), outboxes, golden cases, proposals, the corrections
  and rollout logs, business.json;
* read or change the approval key store (~/.holdco, or HOLDCO_KEYS_DIR);
* change the guard itself (this hook, .claude/settings*.json, holdco/guard.py,
  holdco/keys.py) unless a person started Claude Code with HOLDCO_DEV=1.

Holdco operations agents (agent types named holdco-*) get allow-lists instead: they
write only inside a job's work/ folder (the clerk also /tmp/holdco-*), and run only
agent-safe holdco commands plus a few read-only helpers.

This is a guard rail, not a sandbox. It reads commands as text, so a program that is
determined to cheat can still get around it. The layers that don't depend on it: the
holdco library refuses human-only actions inside an agent session or without a
terminal; approvals and releases are signed with the approver's passphrase; and
`holdco outbox verify` checks what was released. For real client work, run agents
under a separate OS user with no access to businesses/ state or the key store
(runbook 09).
"""

from __future__ import annotations

import fnmatch
import json
import os
import posixpath
import re
import sys

HUMAN_ONLY = {"approve", "send", "send-back", "answer", "cancel", "shadow", "rollout"}
HUMAN_ONLY_PAIRS = {("rules", "accept"), ("rules", "reject"), ("keys", "add"), ("outbox", "verify")}
# What holdco-* operations agents may run. None = any sub-subcommand.
AGENT_SAFE = {
    "status": None, "queue": None, "record": None, "record-run": None, "check": None, "eval": None,
    "metrics": None, "graduation": None, "job": {"list", "show"}, "corrections": {"list", "review"},
    "rules": {"list", "proposals", "propose"}, "golden": {"list", "materialize", "compare"},
    "deal": {"score"}, "model": {"margin"}, "keys": {"list"},
}
AGENT_HELPERS = {"cd", "echo", "printf", "true", "false", "test", "[", "head", "tail", "wc", "grep", "jq", "cat",
                 "ls", "cut"}
MARKERS = ("CLAUDECODE", "HOLDCO_AGENT", "HOLDCO_KEYS_DIR")
STATE_FILES = {"business.json", "corrections-log.jsonl", "rollout-log.jsonl"}
STATE_DIRS = {"outbox", "golden", "proposals"}
# Bare file names treated as protected when their folder can't be worked out.
STATE_NAMES = STATE_FILES | {"job.json", "approved.json", "human-version.json", "intake.json", "manifest.json"}
GUARD_FILES = (".claude/hooks/", ".claude/settings.json", ".claude/settings.local.json", "holdco/guard.py",
               "holdco/keys.py")
UNKNOWN = "?"  # a working directory we can't see (after `cd $X`)

WRAPPERS = {"nice": {"-n"}, "timeout": {"-s", "-k", "--signal", "--kill-after"}, "ionice": {"-c", "-n"},
            "stdbuf": {"-i", "-o", "-e"}, "flock": {"-w", "-E"}, "chronic": set(), "setsid": set(), "nohup": set(),
            "time": set(), "command": set(), "builtin": set(), "sudo": {"-u", "-g", "-C"}, "doas": {"-u"},
            "xargs": {"-I", "-n", "-P", "-d", "-L", "-s", "-a", "-E"}, "watch": {"-n", "-d"}}
SHELLS = {"bash", "sh", "zsh", "dash", "ksh", "fish", "busybox"}
DESTRUCTIVE = {"rm", "rmdir", "unlink", "shred", "truncate", "touch", "chmod", "chown", "chgrp", "chattr",
               "setfacl", "mv", "tee"}
COPIERS = {"cp", "install", "ln", "rsync", "scp"}
IN_PLACE = {"sed", "perl", "ruby"}

PY_GUARD_PATCH = re.compile(
    r"\b(require_human|environment|isatty|AGENT_ENV_VARS|keys_dir)\s*=(?!=)"
    r"|setattr\s*\(\s*(guard|jobs|keys|corrections|rollout|sys\.std\w+)\b"
    r"|mock\.patch|monkeypatch|importlib\.reload"
    r"|os\.environ\s*\[[^\]]*\]\s*=(?!=)|os\.environ\.(pop|clear|update|setdefault)\s*\(|del\s+os\.environ"
    r"|os\.(unsetenv|putenv)\s*\(|\bpty\.|openpty|pexpect|\benv\s*=\s*\{"
)
# argv for a human-only command, as a Python list: ["approve", ...] or ["rules", "accept", ...]
PY_HUMAN_ONLY_ARGV = re.compile(
    r"""['"](approve|send|send-back|answer|cancel|shadow|rollout)['"]"""
    r"""|['"](rules|keys|outbox)['"]\s*,\s*['"](accept|reject|add|verify)['"]"""
)
# ... or as a command line handed to a process. Text that only mentions one (docs) is fine.
PY_HUMAN_ONLY_LINE = re.compile(r"holdco\s+(approve|send|send-back|answer|cancel|shadow|rollout"
                                r"|rules\s+(accept|reject)|keys\s+add|outbox\s+verify)\b")
# Code that runs a command or the CLI (as opposed to code that only mentions one, like a docs edit).
PY_RUNS = re.compile(r"\bsubprocess\b|os\.(system|popen|exec\w*|spawn\w*)\s*\(|\bPopen\b|\bpty\b|pexpect"
                     r"|\bmain\s*\(|\brunpy\b")
PY_DESTROY = re.compile(r"rmtree|\bmove\s*\(|\.rename\s*\(|os\.(rename|replace|rmdir)\b|\.replace\s*\(\s*(Path|os\.path)")
PY_WRITE = re.compile(
    r"""open\s*\([^)]*,\s*(mode\s*=\s*)?['"][^'"]*[wax+]|\.write_(text|bytes)\s*\(|\.touch\s*\(|\.unlink\s*\("""
    r"""|\.rename\s*\(|\bshutil\.\w+|\bos\.(remove|unlink|rename|replace|rmdir|truncate|chmod|link|symlink)\b"""
    r"""|\.replace\s*\(\s*(Path|os\.path|['"][^'"]*/)"""
)
PY_INTERNAL_WRITERS = re.compile(
    r"\b(save_job|write_json|append_jsonl|_transition|_store_draft|log_correction|append_rule"
    r"|create_case_from_job|add_key|set_rollout|shadow_record|verify_outbox)\s*\("
)
PY_STRING = re.compile(r"""(['"])((?:\\.|(?!\1).)*?)\1""")


class Blocked(Exception):
    pass


# ------------------------------------------------------------------ paths


class Context:
    def __init__(self, cwd: str | None, dev: bool, keys_dir: str | None):
        self.cwd = posixpath.normpath(cwd or os.getcwd())
        self.dev = dev
        self.home = os.path.expanduser("~")
        dirs = {posixpath.join(self.home, ".holdco")}
        if keys_dir:
            dirs.add(posixpath.normpath(os.path.expanduser(keys_dir)))
        self.key_dirs = dirs

    def resolve(self, path: str, cwd: str | None = None) -> str | None:
        """Absolute normalized path. '?/...' when part of it can't be seen (a variable or unknown cwd)."""
        if not path or not path.strip():
            return None
        path = path.strip().replace("\\", "/")
        if path.startswith("~"):
            path = self.home + path[1:]
        if "$" in path or "`" in path:
            tail = re.split(r"[$`][^/]*", path)[-1]
            return UNKNOWN + posixpath.normpath("/" + tail.lstrip("/")) if tail.strip("/") else None
        cwd = self.cwd if cwd is None else cwd
        if not path.startswith("/"):
            if cwd == UNKNOWN:
                return UNKNOWN + posixpath.normpath("/" + path)
            path = posixpath.join(cwd, path)
        return posixpath.normpath(path)

    def in_key_store(self, resolved: str | None) -> bool:
        if not resolved:
            return False
        if resolved.startswith(UNKNOWN):
            return "/.holdco/" in resolved + "/"
        return any(resolved == d or resolved.startswith(d + "/") for d in self.key_dirs)


def _matches(name: str, names: set[str]) -> bool:
    return any(fnmatch.fnmatchcase(candidate, name) for candidate in names)


def classify(resolved: str | None) -> str | None:
    """'state' (never touch), 'container' (a folder holding state), 'work' (a job's work/) or None."""
    if not resolved:
        return None
    unknown = resolved.startswith(UNKNOWN)
    parts = [p for p in resolved[len(UNKNOWN):].split("/") if p] if unknown else [p for p in resolved.split("/") if p]
    if "golden" in parts:  # business cases and the shared, anonymized ones: only people promote or retire them
        rest = parts[len(parts) - parts[::-1].index("golden"):]
        if rest != ["README.md"]:
            return "container" if not rest else "state"
    if "businesses" in parts:
        i = len(parts) - 1 - parts[::-1].index("businesses")
        rest = parts[i + 1:]
        if not rest:
            return "container"
        if len(rest) == 1:
            return None if "." in rest[0] else "container"   # a business folder (slugs have no dots)
        head = rest[1]
        if _matches(head, STATE_FILES) or _matches(head, STATE_DIRS):
            return "state"
        if fnmatch.fnmatchcase("jobs", head):
            if len(rest) <= 3:
                return "container"
            return "work" if rest[3] == "work" else "state"
        return None
    if parts and unknown and _matches(parts[-1], STATE_NAMES):
        return "state"
    return None


def fixture(resolved: str | None) -> bool:
    """The repo's own sample businesses (businesses/_template, businesses/demo-*)."""
    parts = [p for p in (resolved or "").lstrip(UNKNOWN).split("/") if p]
    if "businesses" not in parts:
        return False
    i = len(parts) - 1 - parts[::-1].index("businesses")
    slug = parts[i + 1] if i + 1 < len(parts) else ""
    return slug == "_template" or slug.startswith("demo-")


def protected_kind(ctx: Context, resolved: str | None) -> str | None:
    """classify(), except that a person developing (HOLDCO_DEV=1) may edit the sample businesses."""
    kind = classify(resolved)
    if kind in ("state", "container") and ctx.dev and fixture(resolved):
        return None
    return kind


def guard_file(resolved: str | None) -> bool:
    if not resolved:
        return False
    path = resolved[len(UNKNOWN):] if resolved.startswith(UNKNOWN) else resolved
    return any(("/" + g) in path + "/" if g.endswith("/") else path.endswith("/" + g) for g in GUARD_FILES)


def protected_path(ctx: Context, target: str, cwd: str | None, what: str) -> None:
    resolved = ctx.resolve(target, cwd)
    if ctx.in_key_store(resolved):
        raise Blocked("The approval key store is off limits to agents.")
    if protected_kind(ctx, resolved) in ("state", "container"):
        raise Blocked(f"{what} would change protected holdco state ({target}). Only the holdco CLI and people "
                      "change it.")
    if guard_file(resolved) and not ctx.dev:
        raise Blocked(f"{target} is part of the guard. A person starts Claude Code with HOLDCO_DEV=1 to change it.")


# ------------------------------------------------------------ tokenizer


OPERATORS = ("&&", "||", ";;", "|&", "&>>", "&>", ">>", "<<<", "<<-", "<<", ">|", "<>", ">&", "<&", ";", "|",
             "&", ">", "<", "(", ")", "\n")
SEPARATORS = {"&&", "||", ";;", "|&", ";", "|", "&", "(", ")", "\n"}
FILE_REDIRECTS = {"&>>", "&>", ">>", ">", ">|", "<>"}


def _closing_paren(text: str, open_index: int) -> int:
    depth, j = 0, open_index
    while j < len(text):
        ch = text[j]
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return j
        elif ch in "'\"":
            k = text.find(ch, j + 1)
            j = len(text) if k < 0 else k
        j += 1
    return len(text)


def tokenize(text: str):
    """Words and operators. Returns (tokens, heredoc bodies, command substitutions)."""
    tokens: list[tuple[str, object]] = []
    heredocs: list[str] = []
    subs: list[str] = []
    pending: list[tuple[str, bool]] = []
    word: list[str] = []
    in_word = False
    i, n = 0, len(text)

    def flush() -> None:
        nonlocal word, in_word
        if in_word:
            tokens.append(("w", "".join(word)))
        word, in_word = [], False

    while i < n:
        c = text[i]
        if c == "\\" and i + 1 < n:
            if text[i + 1] != "\n":
                word.append(text[i + 1])
                in_word = True
            i += 2
            continue
        if c == "'":
            j = text.find("'", i + 1)
            j = n if j < 0 else j
            word.append(text[i + 1:j])
            in_word, i = True, j + 1
            continue
        if c == '"':
            j, buf = i + 1, []
            while j < n and text[j] != '"':
                if text[j] == "\\" and j + 1 < n and text[j + 1] in '"\\$`':
                    buf.append(text[j + 1])
                    j += 2
                elif text.startswith("$(", j):
                    k = _closing_paren(text, j + 1)
                    subs.append(text[j + 2:k])
                    buf.append(text[j:k + 1])
                    j = k + 1
                elif text[j] == "`":
                    k = text.find("`", j + 1)
                    k = n if k < 0 else k
                    subs.append(text[j + 1:k])
                    buf.append(text[j:k + 1])
                    j = k + 1
                else:
                    buf.append(text[j])
                    j += 1
            word.append("".join(buf))
            in_word, i = True, j + 1
            continue
        if text.startswith("$(", i) or c == "`":
            k = _closing_paren(text, i + 1) if c == "$" else text.find("`", i + 1)
            k = n if k < 0 else k
            subs.append(text[i + 2:k] if c == "$" else text[i + 1:k])
            word.append(text[i:k + 1])
            in_word, i = True, k + 1
            continue
        if c == "#" and not in_word:
            j = text.find("\n", i)
            i = n if j < 0 else j
            continue
        if c in " \t\r":
            flush()
            i += 1
            continue
        op = next((o for o in OPERATORS if text.startswith(o, i)), None)
        if op is None:
            word.append(c)
            in_word = True
            i += 1
            continue
        if op in (">", "<", ">>", ">&", "<&", "<>", ">|") and in_word and "".join(word).isdigit():
            word, in_word = [], False  # a file descriptor number, as in 2>&1
        flush()
        if op in ("<<", "<<-"):
            j = i + len(op)
            while j < n and text[j] in " \t":
                j += 1
            m = re.match(r"""(['"]?)([^\s'";|&<>()]+)\1""", text[j:])
            if m:
                pending.append((m.group(2), op == "<<-"))
                tokens.append(("heredoc", len(heredocs) + len(pending) - 1))
                i = j + m.end()
                continue
        if op == "\n" and pending:
            i += 1
            for delim, strip in pending:
                body = []
                while i < n:
                    j = text.find("\n", i)
                    line = text[i:] if j < 0 else text[i:j]
                    i = n if j < 0 else j + 1
                    if (line.lstrip("\t") if strip else line) == delim:
                        break
                    body.append(line)
                heredocs.append("\n".join(body))
            pending = []
            tokens.append(("op", "\n"))
            continue
        tokens.append(("op", op))
        i += len(op)
    flush()
    heredocs.extend("" for _ in pending)
    return tokens, heredocs, subs


def commands(text: str):
    """Simple commands: {words, redirects [(op, target)], heredocs, herestrings, piped_from}."""
    tokens, heredocs, subs = tokenize(text)
    out: list[dict] = []

    def new(piped_from=None) -> dict:
        return {"words": [], "redirects": [], "heredocs": [], "herestrings": [], "piped_from": piped_from}

    current, previous = new(), None
    for kind, value in tokens:
        if kind == "op" and value in SEPARATORS:
            if current["words"] or current["redirects"] or current["heredocs"]:
                out.append(current)
            current = new(out[-1] if value in ("|", "|&") and out else None)
            previous = None
        elif kind == "heredoc":
            current["heredocs"].append(heredocs[value] if value < len(heredocs) else "")
            previous = None
        elif kind == "op":
            previous = value
        else:
            if previous in FILE_REDIRECTS or (previous == ">&" and not str(value).isdigit()):
                current["redirects"].append((previous, value))
            elif previous == "<<<":
                current["herestrings"].append(value)
            elif previous not in ("<", "<&", ">&"):
                current["words"].append(value)
            previous = None
    if current["words"] or current["redirects"] or current["heredocs"]:
        out.append(current)
    return out, subs


# ---------------------------------------------------------------- checks


def _holdco_args(words: list[str]) -> list[str] | None:
    """The arguments after the holdco CLI, if these words run it."""
    if not words:
        return None
    prog = words[0].rsplit("/", 1)[-1]
    if prog == "holdco":
        return words[1:]
    if not re.fullmatch(r"(python|pypy)[0-9.]*", prog):
        return None
    i = 1
    while i < len(words):
        w = words[i]
        if w == "-m":
            return words[i + 2:] if i + 1 < len(words) and words[i + 1].split(".")[0] == "holdco" else None
        if w.startswith("-m"):
            return words[i + 1:] if w[2:].split(".")[0] == "holdco" else None
        if w == "-" or w.startswith("-c"):
            return None
        if w in ("-X", "-W", "-Q"):
            i += 2
            continue
        if w.startswith("-"):
            i += 1
            continue
        return words[i + 1:] if w.rstrip("/").endswith(("holdco/__main__.py", "holdco/cli.py", "holdco")) else None
    return None


def _python_code(words: list[str], cmd: dict) -> str | None:
    """The code a python command runs from its arguments or stdin, if we can see it."""
    args, i = words[1:], 0
    while i < len(args):
        a = args[i]
        if a == "-c":
            return args[i + 1] if i + 1 < len(args) else ""
        if a.startswith("-c"):
            return a[2:]
        if a in ("-X", "-W", "-Q"):
            i += 2
            continue
        if a == "-" or not a.startswith("-"):
            break
        if a.startswith("-m"):
            return None
        i += 1
    rest = args[i:]
    if rest and rest[0] != "-":
        return None  # a script file: we can't see it here (Write/Edit content is checked instead)
    code = "\n".join(cmd["heredocs"] + cmd["herestrings"])
    if not code and cmd["piped_from"]:
        code = _piped_text(cmd["piped_from"])
    return code


def _piped_text(source: dict) -> str:
    words = source["words"]
    if words and words[0].rsplit("/", 1)[-1] in ("echo", "printf", "cat"):
        text = " ".join(w for w in words[1:] if not w.startswith("-"))
        return text.replace("\\n", "\n") + "\n" + "\n".join(source["heredocs"] + source["herestrings"])
    return ""


def _subcommand(args: list[str]) -> tuple[str | None, str | None, bool]:
    """(command, subcommand, sure): sure is False if an unknown option came first."""
    i, sure = 0, True
    while i < len(args):
        a = args[i]
        if a == "--root":
            i += 2
        elif a.startswith("--root="):
            i += 1
        elif a.startswith("-"):
            sure = False
            i += 1
        else:
            return a, next((x for x in args[i + 1:] if not x.startswith("-")), None), sure
    return None, None, sure


def check_holdco(args: list[str], ops_agent: bool) -> None:
    if any(a in ("-h", "--help") for a in args):
        return
    sub, nxt, sure = _subcommand(args)
    human = sub in HUMAN_ONLY or (sub, nxt) in HUMAN_ONLY_PAIRS
    if not sure and not human:
        human = any(a in HUMAN_ONLY for a in args) or any((a, b) in HUMAN_ONLY_PAIRS for a, b in zip(args, args[1:]))
    if human:
        label = f"{sub} {nxt}" if (sub, nxt) in HUMAN_ONLY_PAIRS else sub
        raise Blocked(f"`holdco {label}` is human-only. Tell the person the exact command to run in their own "
                      "terminal.")
    if ops_agent:
        allowed = AGENT_SAFE.get(sub or "", False)
        if allowed is False or (allowed is not None and nxt not in allowed):
            raise Blocked(f"`holdco {sub or ''} {nxt or ''}`".replace("  ", " ") +
                          " isn't one of the commands holdco agents run.")


def check_python_code(code: str, ctx: Context, cwd: str | None) -> None:
    mentions = "holdco" in code
    if mentions and PY_RUNS.search(code) and (PY_HUMAN_ONLY_ARGV.search(code) or PY_HUMAN_ONLY_LINE.search(code)):
        raise Blocked("Running a human-only holdco command from Python is still human-only.")
    if mentions and not ctx.dev and PY_GUARD_PATCH.search(code):
        raise Blocked("Python that patches the holdco guard or strips the agent markers would bypass the "
                      "human-only rule.")
    if mentions and not ctx.dev and PY_INTERNAL_WRITERS.search(code):
        raise Blocked("Agents change holdco state through the holdco CLI, not its internal writers.")
    if ".holdco/keys" in code or any(d in code for d in ctx.key_dirs):
        raise Blocked("The approval key store is off limits to agents.")
    if PY_WRITE.search(code) and not ctx.dev:  # a person developing writes code full of these paths
        base = UNKNOWN if "chdir" in code else cwd
        for _, literal in PY_STRING.findall(code):
            if "/" not in literal and literal in STATE_NAMES:
                raise Blocked(f"This Python would write protected holdco state ({literal}).")
            resolved = ctx.resolve(literal, base) if literal and len(literal) < 400 and "\n" not in literal else None
            kind = protected_kind(ctx, resolved)
            if kind == "state" or (kind == "container" and PY_DESTROY.search(code)) or ctx.in_key_store(resolved):
                raise Blocked(f"This Python would write protected holdco state ({literal}). Only the holdco CLI "
                              "and people change it.")


def check_content(text: str, path: str, ctx: Context) -> None:
    """A script written now can run later, so it gets the same checks as the command typed inline.

    A person developing the holdco itself (HOLDCO_DEV=1) writes tests that patch the guard, so
    scripts are not checked in dev mode; commands still are.
    """
    if not text or ctx.dev:
        return
    name = path.replace("\\", "/").rsplit("/", 1)[-1]
    first = text.lstrip().splitlines()[0] if text.strip() else ""
    shebang = first if first.startswith("#!") else ""
    if name.endswith((".py", ".pyw")) or ("." not in name and "python" in shebang):
        check_python_code(text, ctx, UNKNOWN)
    elif name.endswith((".sh", ".bash", ".zsh", ".command")) or ("." not in name and re.search(r"\b(ba|z|k|da)?sh\b",
                                                                                              shebang)):
        check_shell(text, ctx, UNKNOWN, False, 1)


def mutation_targets(words: list[str]) -> list[str]:
    """Paths a command would create, change or delete."""
    prog, args = words[0].rsplit("/", 1)[-1], words[1:]
    plain = [a for a in args if not a.startswith("-")]
    if prog in DESTRUCTIVE:
        return plain
    if prog in COPIERS:
        for k, a in enumerate(args):
            if a in ("-t", "--target-directory") and k + 1 < len(args):
                return [args[k + 1]]
            if a.startswith("--target-directory="):
                return [a.split("=", 1)[1]]
        targets = plain[-1:] if len(plain) >= 2 or (prog == "ln" and plain) else []
        if prog == "rsync" and "--remove-source-files" in args:
            targets += plain[:-1]
        return targets
    if prog in IN_PLACE:
        in_place = any(a == "--in-place" or a.startswith("--in-place=")
                       or (re.fullmatch(r"-[A-Za-z]+(\.\w*)?", a) and "i" in a[1:].split(".")[0]) for a in args)
        return plain if in_place else []
    if prog in ("awk", "gawk"):
        return plain if "inplace" in args else []
    if prog == "dd":
        return [a[3:] for a in args if a.startswith("of=")]
    if prog in ("curl", "wget"):
        return [args[k + 1] for k, a in enumerate(args[:-1]) if a in ("-o", "-O", "--output", "--output-document")]
    if prog == "tar":
        cluster = args[0] if args and not args[0].startswith("--") else ""
        extracting = "--extract" in args or "-x" in args or ("x" in cluster)
        directories = [args[k + 1] for k, a in enumerate(args[:-1]) if a in ("-C", "--directory")]
        directories += [a.split("=", 1)[1] for a in args if a.startswith("--directory=")]
        return (directories or ["."]) if extracting else []
    if prog == "unzip":
        return [args[k + 1] for k, a in enumerate(args[:-1]) if a == "-d"] or ["."]
    if prog == "find":
        if "-delete" in args or any(a in ("-exec", "-execdir", "-ok", "-okdir") for a in args):
            first = next((k for k, a in enumerate(args) if a.startswith("-") or a in ("(", "!")), len(args))
            names = [args[k + 1] for k, a in enumerate(args[:-1]) if a in ("-name", "-iname", "-path", "-wholename")]
            # A name pattern could match state in any folder under the start points.
            return (args[:first] or ["."]) + ["${FOUND}/" + n.rsplit("/", 1)[-1] for n in names]
    return []


def check_git(args: list[str], ctx: Context, cwd: str | None) -> None:
    while args and args[0] in ("-C", "-c"):
        args = args[2:]
    if not args:
        return
    sub, rest = args[0], args[1:]
    flags = "".join(a[1:] for a in rest if re.fullmatch(r"-[A-Za-z]+", a))
    if sub == "clean" and ("x" in flags or "X" in flags):
        raise Blocked("`git clean -x` deletes ignored files, which is where every business's jobs, outbox and "
                      "logs live.")
    if sub == "stash" and ("a" in flags or "--all" in rest):
        raise Blocked("`git stash --all` would move every business's ignored state out of the workspace.")
    paths = [a for a in rest if not a.startswith("-")]
    protected = [p for p in paths if protected_kind(ctx, ctx.resolve(p, cwd)) in ("state", "container")]
    if not protected:
        return
    if sub in ("rm", "mv"):
        raise Blocked(f"`git {sub}` on protected holdco state ({protected[0]}).")
    if sub == "restore" and any(a.startswith(("--source", "-s")) for a in rest):
        raise Blocked("Restoring protected holdco state from another revision would rewrite it.")
    if sub == "checkout":
        before = rest[:rest.index("--")] if "--" in rest else rest[:1]
        if [a for a in before if not a.startswith("-") and a not in protected]:
            raise Blocked("Checking out protected holdco state from another revision would rewrite it.")


def _strip_prefixes(words: list[str], ctx: Context, cwd: str | None, ops_agent: bool, depth: int) -> list[str]:
    """Drop assignments and wrappers (env, sudo, timeout, xargs, ...), checking what they change."""
    while words:
        m = re.fullmatch(r"([A-Za-z_][A-Za-z0-9_]*)=(.*)", words[0], re.S)
        if m:
            if m.group(1) in MARKERS:
                raise Blocked(f"Setting {m.group(1)} would switch off the human-only guard.")
            words = words[1:]
            continue
        prog = words[0].rsplit("/", 1)[-1]
        if prog == "env":
            rest = words[1:]
            while rest:
                opt = rest[0]
                if opt == "--":
                    rest = rest[1:]
                    break
                if opt in ("-u", "--unset") or opt.startswith(("--unset=", "-u")):
                    name = opt.split("=", 1)[1] if "=" in opt else (opt[2:] if len(opt) > 2 and opt[1] == "u"
                                                                   else (rest[1] if len(rest) > 1 else ""))
                    if name in MARKERS:
                        raise Blocked(f"Unsetting {name} would switch off the human-only guard.")
                    rest = rest[2:] if opt in ("-u", "--unset") else rest[1:]
                    continue
                if opt in ("-i", "--ignore-environment", "-") or re.fullmatch(r"-[a-zA-Z]*i[a-zA-Z]*", opt):
                    raise Blocked("`env -i` clears the agent markers the human-only guard relies on.")
                if opt in ("-S", "--split-string") and len(rest) > 1:
                    check_shell(rest[1], ctx, cwd, ops_agent, depth + 1)
                    rest = rest[2:]
                    continue
                if opt in ("-C", "--chdir"):
                    rest = rest[2:]
                    continue
                if opt.startswith("-"):
                    rest = rest[1:]
                    continue
                m = re.fullmatch(r"([A-Za-z_][A-Za-z0-9_]*)=(.*)", opt, re.S)
                if not m:
                    break
                if m.group(1) in MARKERS:
                    raise Blocked(f"Setting {m.group(1)} would switch off the human-only guard.")
                rest = rest[1:]
            words = rest
            continue
        if prog == "exec":
            rest = words[1:]
            while rest and rest[0].startswith("-"):
                if "c" in rest[0]:
                    raise Blocked("`exec -c` clears the agent markers the human-only guard relies on.")
                rest = rest[2:] if rest[0] == "-a" else rest[1:]
            words = rest
            continue
        if prog in WRAPPERS:
            rest = words[1:]
            while rest and rest[0].startswith("-"):
                rest = rest[2:] if rest[0] in WRAPPERS[prog] else rest[1:]
            if prog in ("timeout", "flock") and rest:
                rest = rest[1:]  # the duration, or the lock file
            words = rest
            continue
        if prog in ("uv", "poetry", "pipenv", "pdm", "hatch", "rye") and len(words) > 1 and words[1] == "run":
            words = words[2:]
            continue
        break
    return words


VARIABLE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}|\$([A-Za-z_][A-Za-z0-9_]*)")
ASSIGNMENT = re.compile(r"([A-Za-z_][A-Za-z0-9_]*)=(.*)", re.S)


def expand(word: str, variables: dict) -> str:
    """Substitute variables set earlier in the same command line (B=businesses/x && rm -rf $B)."""
    return VARIABLE.sub(lambda m: variables.get(m.group(1) or m.group(2), m.group(0)), word)


def check_command(cmd: dict, ctx: Context, cwd: str | None, ops_agent: bool, depth: int,
                  variables: dict | None = None) -> str | None:
    """Raise Blocked if this simple command crosses a line. Returns the working directory after it."""
    variables = {} if variables is None else variables
    cmd = dict(cmd, words=[expand(w, variables) for w in cmd["words"]],
               redirects=[(op, expand(t, variables)) for op, t in cmd["redirects"]])
    plain_words = [w for w in cmd["words"] if w not in ("export", "local", "readonly")]
    if plain_words and all(ASSIGNMENT.fullmatch(w) for w in plain_words):
        for w in plain_words:
            name, value = ASSIGNMENT.fullmatch(w).groups()
            if name not in MARKERS:
                variables[name] = value
    for _, target in cmd["redirects"]:
        if ops_agent and target not in ("/dev/null", "/dev/stdout", "/dev/stderr"):
            raise Blocked("holdco agents don't redirect output to files; write files with the Write tool.")
        protected_path(ctx, target, cwd, "Writing to it")
        for body in cmd["heredocs"] + cmd["herestrings"]:
            check_content(body, target, ctx)
    for word in cmd["words"]:
        if " " in word or "\n" in word:
            continue  # text, not a path
        if "/.holdco/" in "/" + word + "/" or ctx.in_key_store(ctx.resolve(word, cwd)):
            raise Blocked("The approval key store is off limits to agents.")
    words = _strip_prefixes(list(cmd["words"]), ctx, cwd, ops_agent, depth)
    if not words:
        return cwd
    prog, args = words[0].rsplit("/", 1)[-1], words[1:]

    if prog in SHELLS or prog in ("eval", "script", "su", "runuser"):
        if ops_agent:
            raise Blocked("holdco agents run holdco commands directly, not through another shell.")
        nested: list[str] = []
        if prog == "eval":
            nested.append(" ".join(args))
        else:
            for k, a in enumerate(args):
                if prog in SHELLS and re.fullmatch(r"-[a-zA-Z]*c[a-zA-Z]*", a) and k + 1 < len(args):
                    nested.append(args[k + 1])
                    break
                if prog == "script" and (a in ("-c", "--command") or re.fullmatch(r"-[a-zA-Z]*c", a)) and k + 1 < len(args):
                    nested.append(args[k + 1])
                elif prog == "script" and a.startswith("--command="):
                    nested.append(a.split("=", 1)[1])
                elif prog in ("su", "runuser") and a in ("-c", "--command") and k + 1 < len(args):
                    nested.append(args[k + 1])
            if prog in SHELLS:
                nested += cmd["heredocs"] + cmd["herestrings"]
                if cmd["piped_from"]:
                    nested.append(_piped_text(cmd["piped_from"]))
        for text in nested:
            check_shell(text, ctx, cwd, ops_agent, depth + 1)
        return cwd
    if prog == "unset":
        for name in args:
            if name in MARKERS:
                raise Blocked(f"Unsetting {name} would switch off the human-only guard.")
        return cwd
    if prog in ("export", "declare", "typeset", "local", "readonly"):
        for a in args:
            if a.split("=", 1)[0] in MARKERS:
                raise Blocked(f"Changing {a.split('=', 1)[0]} would switch off the human-only guard.")
        return cwd
    if prog in ("cd", "pushd"):
        if not args or args[0] == "-":
            return UNKNOWN if args else ctx.home
        resolved = ctx.resolve(next((a for a in args if not a.startswith("-")), "~"), cwd)
        return UNKNOWN if not resolved or resolved.startswith(UNKNOWN) else resolved

    holdco = _holdco_args(words)
    if holdco is not None:
        check_holdco(holdco, ops_agent)
        return cwd
    if ops_agent:
        if prog not in AGENT_HELPERS:
            raise Blocked(f"holdco agents run only holdco commands (and read-only helpers), not `{prog}`.")
        return cwd
    if re.fullmatch(r"(python|pypy)[0-9.]*", prog):
        code = _python_code(words, cmd)
        if code:
            check_python_code(code, ctx, cwd)
        return cwd
    if prog == "git":
        check_git(args, ctx, cwd)
        return cwd
    for target in mutation_targets(words):
        protected_path(ctx, target, cwd, f"`{prog}`")
    if prog == "tee":
        for target in args:
            for body in cmd["heredocs"] + cmd["herestrings"]:
                check_content(body, target, ctx)
    return cwd


def check_shell(text: str, ctx: Context, cwd: str | None, ops_agent: bool, depth: int = 0) -> None:
    if depth > 8:
        raise Blocked("Too many nested shells to check.")
    cmds, subs = commands(text)
    if ops_agent and subs:
        raise Blocked("holdco agents don't use command substitution.")
    for sub in subs:
        check_shell(sub, ctx, cwd, ops_agent, depth + 1)
    variables: dict = {}
    for cmd in cmds:
        if ops_agent and cmd["heredocs"]:
            raise Blocked("holdco agents write files with the Write tool, not heredocs.")
        cwd = check_command(cmd, ctx, cwd, ops_agent, depth, variables)


# ---------------------------------------------------------------- tools


def check_write(path: str, content: str, ctx: Context, agent_type: str) -> None:
    resolved = ctx.resolve(path)
    if ctx.in_key_store(resolved):
        raise Blocked("The approval key store is off limits to agents.")
    kind = protected_kind(ctx, resolved)
    if agent_type.startswith("holdco-"):
        clerk_tmp = agent_type == "holdco-clerk" and bool(resolved) and fnmatch.fnmatchcase(resolved, "/tmp/holdco-*")
        if classify(resolved) != "work" and not clerk_tmp:
            raise Blocked(f"{agent_type} writes only inside a job's work/ folder, not {path}.")
    if kind in ("state", "container"):
        raise Blocked(f"{path} is protected holdco state. Agents write drafts only to a job's work/ folder; "
                      "approvals, sends, logs and golden cases are written by the holdco CLI for a person.")
    if guard_file(resolved) and not ctx.dev:
        raise Blocked(f"{path} is part of the guard. A person starts Claude Code with HOLDCO_DEV=1 to change it.")
    check_content(content, path, ctx)


def check_read(path: str, ctx: Context, searching: bool = False) -> None:
    resolved = ctx.resolve(path) if path else ctx.cwd
    if ctx.in_key_store(resolved):
        raise Blocked("The approval key store is off limits to agents.")
    if searching and resolved and not resolved.startswith(UNKNOWN):
        inside = resolved.rstrip("/") + "/"
        if any(d.startswith(inside) for d in ctx.key_dirs):
            raise Blocked("That search would cover the approval key store, which is off limits to agents.")


def evaluate(event: dict, environ=None) -> str | None:
    environ = os.environ if environ is None else environ
    ctx = Context(event.get("cwd") or environ.get("CLAUDE_PROJECT_DIR"), environ.get("HOLDCO_DEV") == "1",
                  environ.get("HOLDCO_KEYS_DIR"))
    tool = event.get("tool_name", "")
    data = event.get("tool_input") or {}
    agent_type = str(event.get("agent_type") or "")
    try:
        if tool == "Bash":
            check_shell(str(data.get("command", "")), ctx, ctx.cwd, agent_type.startswith("holdco-"))
        elif tool in ("Write", "Edit", "MultiEdit", "NotebookEdit"):
            if tool == "MultiEdit":
                content = "\n".join(str(e.get("new_string", "")) for e in data.get("edits") or [])
            else:
                content = str(data.get("content") or data.get("new_string") or data.get("new_source") or "")
            check_write(str(data.get("file_path") or data.get("notebook_path") or ""), content, ctx, agent_type)
        elif tool == "Read":
            check_read(str(data.get("file_path", "")), ctx)
        elif tool in ("Grep", "Glob"):
            check_read(str(data.get("path") or ""), ctx, searching=True)
    except Blocked as exc:
        return str(exc)
    return None


def main() -> int:
    try:
        event = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0
    reason = evaluate(event)
    if reason:
        print(f"Blocked by the holdco human-only guard: {reason}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
