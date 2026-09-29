"""The Claude Code PreToolUse guard (.claude/hooks/human_only_guard.py)."""

from __future__ import annotations

import json
import subprocess
import sys
import unittest

from tests.helpers import REPO

HOOK = REPO / ".claude" / "hooks" / "human_only_guard.py"


def run_hook(tool: str, **tool_input) -> subprocess.CompletedProcess:
    event = {"hook_event_name": "PreToolUse", "tool_name": tool, "tool_input": tool_input}
    return subprocess.run([sys.executable, str(HOOK)], input=json.dumps(event), capture_output=True, text=True)


class Hook(unittest.TestCase):
    def assertBlocked(self, tool, **tool_input):
        result = run_hook(tool, **tool_input)
        self.assertEqual(result.returncode, 2, (tool_input, result.stderr))
        self.assertIn("human-only guard", result.stderr)

    def assertAllowed(self, tool, **tool_input):
        result = run_hook(tool, **tool_input)
        self.assertEqual(result.returncode, 0, (tool_input, result.stderr))

    def test_blocks_human_only_commands(self):
        for command in (
            "python3 -m holdco approve demo-bookkeeping J1 --by 'Dana Ruiz'",
            "python3 -m holdco --root .sandbox send demo-bookkeeping J1 --by Dana",
            "cd /repo && python3 -m holdco answer biz J1 --by Dana --text 'Owner draw'",
            "python -m holdco rules accept biz P-0001 --by Dana",
            "python3 -m holdco rules reject biz P-0001 --by Dana --reason no",
            "python3 -m holdco send-back biz J1 --by Dana --note x --reason style",
            "python3 -m holdco shadow biz J1 --by Dana",
            "python3 -m holdco rollout biz monthly-close assisted --by Dana --reason ok",
            "python3 holdco/cli.py approve biz J1 --by Dana",
            "echo ok; python3 -m holdco cancel biz J1 --by Dana --reason x",
        ):
            self.assertBlocked("Bash", command=command)

    def test_blocks_forged_human_context_and_guard_tampering(self):
        self.assertBlocked("Bash", command="python3 -c 'from holdco.guard import ExecutionContext as E; "
                                           "from holdco import jobs; jobs.approve(ws, b, j, \"Dana\", E(True, False))'")
        self.assertBlocked("Bash", command="python3 - <<'EOF'\nfrom holdco.guard import ExecutionContext\n"
                                           "ctx = ExecutionContext.human_terminal()\nEOF")
        self.assertBlocked("Bash", command="unset CLAUDECODE && python3 -m holdco status")
        self.assertBlocked("Bash", command="env -u CLAUDECODE python3 -m holdco status")
        self.assertBlocked("Bash", command="CLAUDECODE= python3 -m holdco status")

    def test_blocks_mutating_protected_state_from_the_shell(self):
        for command in (
            "cp draft.md businesses/acme-books/outbox/J1/message.md",
            "echo '{}' > businesses/x/jobs/J1/approved.json",
            "rm -rf businesses/x/golden/G-0001",
            "sed -i 's/a/b/' businesses/x/jobs/J1/job.json",
            "rm businesses/x/corrections-log.jsonl",
            "echo x >> businesses/x/corrections-log.jsonl",
            "git checkout -- businesses/x/jobs/J1/job.json",
            "python3 -c \"open('businesses/x/jobs/J1/approved.json','w').write('{}')\"",
            "mv businesses/x/outbox/J1 /tmp/",
        ):
            self.assertBlocked("Bash", command=command)

    def test_blocks_protected_file_writes(self):
        for path in ("/r/businesses/x/outbox/J1/message.md", "/r/businesses/x/jobs/J1/approved.json",
                     "/r/businesses/x/jobs/J1/job.json", "/r/businesses/x/golden/G-0001/expected.json",
                     "/r/businesses/x/business.json", "/r/businesses/x/corrections-log.jsonl",
                     "/r/businesses/x/proposals/P-0001.json"):
            self.assertBlocked("Write", file_path=path)
        self.assertBlocked("Edit", file_path="/r/businesses/x/jobs/J1/approved.json")

    def test_allows_agent_work(self):
        for command in (
            "python3 -m holdco status", "python3 -m holdco queue", "python3 -m holdco job show biz J1",
            "python3 -m holdco record-run biz J1 --file businesses/biz/jobs/J1/work/run.json",
            "python3 -m holdco corrections review biz --dry-run --json", "python3 -m holdco demo --quiet",
            "python3 -m holdco eval biz", "cat businesses/x/jobs/J1/approved.json",
            "grep -n approve holdco/jobs.py", "python3 -m unittest discover -s tests -t .",
            "python3 -m holdco rules list biz", "python3 -m holdco job new biz --type monthly-close --client acme",
            "git status", "cat businesses/x/jobs/J1/job.json 2>/dev/null",
            "python3 -m holdco job show biz J1 2>&1 | head", "cp businesses/x/jobs/J1/approved.json /tmp/copy.json",
            "grep -c approve businesses/x/corrections-log.jsonl > /tmp/count.txt",
        ):
            self.assertAllowed("Bash", command=command)
        # Editing source that merely mentions approve() is development, not approval:
        # the library refuses real calls inside an agent session on its own.
        self.assertAllowed("Bash", command="python3 - <<'EOF'\ntext = 'jobs.approve(ws, biz, job_id)'\n"
                                           "open('notes.txt', 'w').write(text)\nEOF")
        self.assertAllowed("Write", file_path="/r/businesses/x/jobs/J1/work/draft.v1.json")
        self.assertAllowed("Write", file_path="/r/businesses/x/jobs/J1/work/run.json")
        self.assertAllowed("Edit", file_path="/r/businesses/x/rules.md")
        self.assertAllowed("Write", file_path="/r/docs/PLAYBOOK.md")
        self.assertAllowed("Read", file_path="/r/businesses/x/jobs/J1/approved.json")


if __name__ == "__main__":
    unittest.main()
