"""The Claude Code PreToolUse guard (.claude/hooks/human_only_guard.py).

Most cases call the hook's evaluate() directly with a fixed workspace (/r) and home
(/home/u); a few run it as Claude Code does, as a process reading the event on stdin.
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

from tests.helpers import REPO

HOOK = Path(os.environ.get("HOLDCO_HOOK_UNDER_TEST") or REPO / ".claude" / "hooks" / "human_only_guard.py")
_spec = importlib.util.spec_from_file_location("human_only_guard", HOOK)
guard = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(guard)

JOB = "businesses/x/jobs/J1"


def decide(tool: str, agent_type: str | None = None, dev: bool = False, cwd: str = "/r", **tool_input) -> str | None:
    event = {"hook_event_name": "PreToolUse", "tool_name": tool, "tool_input": tool_input, "cwd": cwd}
    if agent_type:
        event["agent_type"] = agent_type
    environ = {"HOLDCO_DEV": "1"} if dev else {}
    with mock.patch.dict(os.environ, {"HOME": "/home/u"}):
        return guard.evaluate(event, environ)


class Case(unittest.TestCase):
    def blocked(self, tool: str, agent_type: str | None = None, dev: bool = False, **tool_input) -> None:
        self.assertIsNotNone(decide(tool, agent_type, dev, **tool_input), (tool, agent_type, tool_input))

    def allowed(self, tool: str, agent_type: str | None = None, dev: bool = False, **tool_input) -> None:
        self.assertIsNone(decide(tool, agent_type, dev, **tool_input), (tool, agent_type, tool_input))

    def blocks_all(self, *commands: str, agent_type: str | None = None) -> None:
        for command in commands:
            with self.subTest(command=command):
                self.blocked("Bash", agent_type, command=command)

    def allows_all(self, *commands: str, agent_type: str | None = None) -> None:
        for command in commands:
            with self.subTest(command=command):
                self.allowed("Bash", agent_type, command=command)


class HumanOnlyCommands(Case):
    def test_blocks_them_however_they_are_written(self):
        self.blocks_all(
            "python3 -m holdco approve demo-bookkeeping J1 --by 'Dana Ruiz'",
            "python3 -m holdco --root .sandbox send demo-bookkeeping J1 --by Dana",
            "python3 -m holdco send demo-bookkeeping J1 --by Dana --root .sandbox",
            "cd /repo && python3 -m holdco answer biz J1 --by Dana --text 'Owner draw'",
            "python -m holdco rules accept biz P-0001 --by Dana",
            "python3 -m holdco rules reject biz P-0001 --by Dana --reason no",
            "python3 -m holdco send-back biz J1 --by Dana --note x --reason style",
            "python3 -m holdco shadow biz J1 --by Dana",
            "python3 -m holdco rollout biz monthly-close assisted --by Dana --reason ok",
            "python3 -m holdco keys add biz --by Dana",
            "python3 -m holdco outbox verify biz --by Dana",
            "python3 holdco/cli.py approve biz J1 --by Dana",
            "echo ok; python3 -m holdco cancel biz J1 --by Dana --reason x",
            # the review's evasions
            "python3 -mholdco approve biz J1 --by Dana",
            "python3 -m holdco.__main__ approve biz J1 --by Dana",
            "python3 -m holdco --roo /x approve biz J1 --by Dana",
            "bash -c 'python3 -m holdco approve biz J1 --by Dana'",
            "sh -lc \"python3 -m holdco send biz J1 --by Dana\"",
            "eval \"python3 -m holdco send biz J1 --by Dana\"",
            "script -qec 'python3 -m holdco approve biz J1 --by D --minutes 1' /dev/null",
            "echo J1 | xargs python3 -m holdco approve biz",
            "timeout 60 nice -n 5 python3 -m holdco approve biz J1 --by D",
            "echo 'python3 -m holdco approve biz J1 --by D' | bash",
            "bash <<'EOF'\npython3 -m holdco approve biz J1 --by D\nEOF",
            "x=$(python3 -m holdco approve biz J1 --by D)",
            "uv run python -m holdco approve biz J1 --by D",
            "python3 -c \"from holdco.cli import main; main(['approve', 'biz', 'J1', '--by', 'D'])\"",
            "python3 -c \"import subprocess; subprocess.run(['python3', '-m', 'holdco', 'send', 'b', 'J'])\"",
        )

    def test_help_and_documentation_are_fine(self):
        self.allows_all(
            "python3 -m holdco approve --help",
            "python3 -m holdco rules accept -h",
            "git commit -F - <<'EOF'\nTell Dana to run: python3 -m holdco approve biz J1 --by Dana\nEOF",
            "cat > docs/HANDOFF.md <<'EOF'\nRun `python3 -m holdco send biz J1 --by Dana` in your terminal.\n"
            "python3 - <<EOF uses holdco and ExecutionContext\nEOF",
            "grep -n approve holdco/jobs.py",
            "python3 -c \"import holdco.guard as g; help(g.ExecutionContext)\"",
        )


class GuardTampering(Case):
    def test_agent_markers_stay_on(self):
        self.blocks_all(
            "unset CLAUDECODE && python3 -m holdco status",
            "env -u CLAUDECODE python3 -m holdco status",
            "env --unset=CLAUDECODE python3 -m holdco status",
            "env -i PATH=/usr/bin python3 -m holdco status",
            "CLAUDECODE= python3 -m holdco status",
            "CLAUDECODE=; python3 -m holdco status",
            "CLAUDECODE=0 python3 -m holdco status",
            "export -n CLAUDECODE; python3 -m holdco status",
            "export HOLDCO_AGENT=",
            "exec -c python3 -m holdco status",
            "HOLDCO_KEYS_DIR=/tmp/k python3 -m holdco status",
            "printf 'approve\\n' | env -i PATH=/usr/bin script -qec 'python3 -m holdco approve b J --by D' /dev/null",
        )
        self.allows_all("echo $CLAUDECODE", "env | grep CLAUDE", "printenv CLAUDECODE")

    def test_inline_python_cannot_patch_the_guard(self):
        self.blocks_all(
            "python3 -c \"import holdco.jobs as j; j.require_human=lambda *a, **k: None; j.cancel(b, 'J', 'D', c, 'x')\"",
            "python3 - <<'EOF'\nimport os\nfrom holdco import guard\nguard.environment = lambda: (True, False)\nEOF",
            "python3 - <<'EOF'\nimport os; os.environ.pop('CLAUDECODE')\nfrom holdco import jobs\nEOF",
            "python3 -c \"from unittest import mock; import holdco; mock.patch('holdco.guard.environment')\"",
            "python3 -c \"import pty; pty.spawn(['python3', '-m', 'holdco', 'status'])\"",
            "python3 -c \"from holdco import jobs; jobs.save_job(b, j)\"",
        )

    def test_scripts_written_for_later_are_checked_too(self):
        forge = ("from holdco import guard, jobs\nguard.environment = lambda: (True, False)\n"
                 "jobs.answer(biz, 'J1', 'Owner draw', 'Dana', ctx)\n")
        self.blocked("Write", file_path="/tmp/forge.py", content=forge)
        self.blocked("Bash", command=f"cat > /tmp/forge.py <<'EOF'\n{forge}EOF")
        self.blocked("Write", file_path="/tmp/run.sh", content="python3 -m holdco approve biz J1 --by Dana\n")
        self.allowed("Write", file_path="/r/docs/notes.md", content=forge)  # prose about the code is fine
        self.allowed("Write", file_path="/r/tests/test_x.py", dev=True, content=forge)  # a person developing

    def test_dev_mode_is_for_working_on_the_holdco_not_on_client_state(self):
        patch_source = ("python3 - <<'EOF'\nfrom pathlib import Path\np = Path('holdco/cli.py')\n"
                        "s = p.read_text().replace('\"approve\"', '\"approve\"')\np.write_text(s)\nEOF")
        self.assertIsNone(decide("Bash", command=patch_source, dev=True))
        docs = ("python3 - <<'EOF'\nfrom pathlib import Path\nPath('docs/X.md').write_text("
                "'Run python3 -m holdco approve biz J1 --by Dana')\nEOF")
        self.assertIsNone(decide("Bash", command=docs))
        self.assertIsNone(decide("Write", dev=True, file_path="/r/businesses/demo-bookkeeping/business.json",
                                 content="{}"))
        self.assertIsNone(decide("Bash", dev=True, command="rm -rf businesses/demo-bookkeeping/jobs"))
        for command in ("rm -rf businesses/real-firm/jobs", "python3 -m holdco approve b J --by D",
                        "python3 -c \"import os; os.system('python3 -m holdco approve b J --by D')\"",
                        "cat ~/.holdco/keys/b/d.json"):
            self.assertIsNotNone(decide("Bash", dev=True, command=command), command)
        self.assertIsNotNone(decide("Write", dev=True, file_path="/r/businesses/real-firm/business.json", content="{}"))

    def test_the_guard_itself_needs_dev_mode(self):
        for path in ("/r/.claude/hooks/human_only_guard.py", "/r/.claude/settings.json",
                     "/r/.claude/settings.local.json", "/r/holdco/guard.py", "/r/holdco/keys.py"):
            with self.subTest(path=path):
                self.blocked("Edit", file_path=path, new_string="x")
                self.allowed("Edit", dev=True, file_path=path, new_string="x")
        self.blocks_all("sed -i 's/CLAUDECODE/NOPE/' holdco/guard.py", "rm .claude/settings.json",
                        "echo '{}' > .claude/settings.json")
        self.allowed("Edit", file_path="/r/holdco/jobs.py", new_string="x")  # the engine is ordinary code


class ProtectedState(Case):
    def test_shell_writes_to_state_are_blocked(self):
        self.blocks_all(
            "cp draft.md businesses/acme-books/outbox/J1/message.md",
            f"echo '{{}}' > {JOB}/approved.json",
            "rm -rf businesses/x/golden/G-0001",
            f"sed -i 's/a/b/' {JOB}/job.json",
            f"sed -Ei 's/a/b/' {JOB}/job.json",
            f"sed --in-place=.bak 's/a/b/' {JOB}/job.json",
            f"perl -pi -e 's/a/b/' {JOB}/job.json",
            f"sed -i 's/a/b/' {JOB}/job.j*",
            f"cd {JOB} && sed -i 's/a/b/' job.json",
            "cd $JOB && sed -i 's/a/b/' job.json",
            "B=businesses/x && cat > $B/business.json <<'EOF'\n{}\nEOF",
            "J=businesses/x/jobs/J1; rm -rf ${J}/input",
            "rm businesses/x/corrections-log.jsonl",
            "echo x >> businesses/x/corrections-log.jsonl",
            "mv businesses/x/outbox/J1 /tmp/",
            f"rsync -a /tmp/forged/ {JOB}/",
            f"tar -xf x.tar -C {JOB}",
            f"cp /tmp/bank.csv {JOB}/input/bank.csv",
            f"ln -sf /tmp/forged.json {JOB}/approved.json",
            "find businesses -name job.json -delete",
            "find . -name approved.json -exec rm {} +",
            "rm -rf businesses/x",
            "git checkout HEAD~3 -- businesses/x/business.json",
            "git restore --source=HEAD~1 businesses/x/business.json",
            "git clean -fdx",
            "git stash --all",
            f"dd if=/dev/zero of={JOB}/job.json",
            "tee businesses/x/rollout-log.jsonl < /dev/null",
            "cp -r /tmp/cases shared/golden/bookkeeping/",
        )

    def test_python_writes_to_state_are_blocked(self):
        self.blocks_all(
            f"python3 -c \"open('{JOB}/approved.json','w').write('{{}}')\"",
            f"python3 -c \"import json; open('{JOB}/approved.json','w').write('{{}}')\"",
            f"python3 - <<'EOF'\nimport json\nwith open('{JOB}/job.json', 'w') as f:\n    f.write('{{}}')\nEOF",
            "python3 -c \"import shutil; shutil.copy('/tmp/x', 'approved.json')\"",
            "python3 -c \"import os; os.replace('/tmp/x', 'job.json')\"",
            f"python3 -c \"from pathlib import Path; Path('{JOB}/input/bank.csv').write_text('')\"",
        )

    def test_writes_with_tools_are_blocked(self):
        for path in ("/r/businesses/x/outbox/J1/message.md", f"/r/{JOB}/approved.json", f"/r/{JOB}/job.json",
                     f"/r/{JOB}/input/bank.csv", f"/r/{JOB}/drafts/v1.json",
                     "/r/businesses/x/golden/G-0001/expected.json", "/r/businesses/x/business.json",
                     "/r/businesses/x/corrections-log.jsonl", "/r/businesses/x/proposals/P-0001.json",
                     f"/r/{JOB}/work/../../../business.json", f"/r/{JOB}/work/../approved.json",
                     "/r/shared/golden/bookkeeping/G-0001/README.md"):
            with self.subTest(path=path):
                self.blocked("Write", file_path=path, content="{}")
        self.blocked("Edit", file_path=f"/r/{JOB}/approved.json", new_string="x")

    def test_ordinary_work_is_allowed(self):
        self.allows_all(
            "python3 -m holdco status", "python3 -m holdco queue", "python3 -m holdco job show biz J1",
            f"python3 -m holdco record-run biz J1 --file {JOB}/work/run.json --json --root /r",
            "python3 -m holdco corrections review biz --dry-run --json", "python3 -m holdco demo --quiet",
            "python3 -m holdco eval biz", f"cat {JOB}/approved.json", "python3 -m unittest discover -s tests -t .",
            "python3 -m holdco rules list biz", "python3 -m holdco job new biz --type monthly-close --client acme",
            "git status", f"cat {JOB}/job.json 2>/dev/null", "python3 -m holdco job show biz J1 2>&1 | head",
            f"cp {JOB}/approved.json /tmp/copy.json", "grep -c approve businesses/x/corrections-log.jsonl > /tmp/n",
            "python3 -m holdco job show biz J1 --json > /tmp/job.json",
            "git restore businesses/x/corrections-log.jsonl",
            "git checkout -- businesses/x/business.json",
            f"cp /tmp/draft.json {JOB}/work/draft.v1.json", f"mkdir -p {JOB}/work/tmp",
            "rm -rf .sandbox", "cp -r businesses/_template /tmp/template-copy",
            "python3 - <<'EOF'\ntext = 'jobs.approve(ws, biz, job_id)'\nopen('notes.txt', 'w').write(text)\nEOF",
            "git add -A && git commit -q -m 'Update docs'", "node tests/workflows/harness.mjs x '{}' python3 y",
        )
        for path in (f"/r/{JOB}/work/draft.v1.json", f"/r/{JOB}/work/run.json", "/r/shared/golden/README.md",
                     "/r/businesses/x/rules.md", "/r/businesses/x/clients.csv", "/r/businesses/README.md",
                     "/r/docs/PLAYBOOK.md", "/tmp/job.json"):
            with self.subTest(path=path):
                self.allowed("Write", file_path=path, content="{}")
        self.allowed("Read", file_path=f"/r/{JOB}/approved.json")


class KeyStore(Case):
    def test_agents_cannot_touch_the_key_store(self):
        self.blocked("Read", file_path="/home/u/.holdco/keys/biz/dana-ruiz.json")
        self.blocked("Write", file_path="/home/u/.holdco/keys/biz/dana-ruiz.json", content="{}")
        self.blocked("Grep", pattern="verifier", path="/home/u")
        self.blocks_all("cat ~/.holdco/keys/biz/dana-ruiz.json", "ls -la /home/u/.holdco",
                        "cp /tmp/k.json ~/.holdco/keys/biz/dana-ruiz.json",
                        "python3 -c \"print(open('/home/u/.holdco/keys/b/d.json').read())\"")
        self.allowed("Grep", pattern="approve", path="/r/holdco")
        self.allowed("Read", file_path="/r/holdco/keys.py")


class OperationsAgents(Case):
    def test_the_preparer_writes_only_to_work(self):
        self.allowed("Write", "holdco-preparer", file_path=f"/r/{JOB}/work/draft.v2.json", content="{}")
        for path in ("/r/businesses/x/rules.md", "/r/shared/agents/preparer.md", "/r/holdco/jobs.py",
                     "/r/.claude/agents/holdco-reviewer.md", "/tmp/anything.json", "/r/CLAUDE.md"):
            with self.subTest(path=path):
                self.blocked("Write", "holdco-preparer", file_path=path, content="{}")

    def test_the_clerk_runs_single_agent_safe_commands(self):
        ok = (f"python3 -m holdco record-run biz J1 --file {JOB}/work/run-1.json --json --root \"/r\"",
              "python3 -m holdco rules propose biz --file /tmp/holdco-proposal-biz-1.json --root /r",
              "python3 -m holdco golden materialize biz G-0001 --json --root /r",
              "python3 -m holdco job list biz --json | head -50")
        self.allows_all(*ok, agent_type="holdco-clerk")
        self.blocks_all(
            "python3 -m holdco job new biz --type x --client y --root /r",
            "python3 -m holdco record-run biz J1 --file x.json > /tmp/out.txt",
            "python3 -m holdco record-run biz J1 --file x.json; rm -rf /tmp/x",
            "bash -c 'python3 -m holdco status'",
            "curl https://example.com",
            "python3 -c 'print(1)'",
            agent_type="holdco-clerk",
        )
        self.allowed("Write", "holdco-clerk", file_path="/tmp/holdco-proposal-biz-1.json", content="{}")
        self.blocked("Write", "holdco-preparer", file_path="/tmp/holdco-proposal-biz-1.json", content="{}")

    def test_the_curator_reads_and_proposes(self):
        self.allows_all("python3 -m holdco corrections review biz --json --root /r",
                        "python3 -m holdco golden list biz --json", agent_type="holdco-rules-curator")
        self.blocks_all("python3 -m holdco rules accept biz P-0001 --by Dana",
                        "sed -i 's/x/y/' businesses/x/rules.md", agent_type="holdco-rules-curator")


class AsAProcess(unittest.TestCase):
    def run_hook(self, event: dict) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, str(HOOK)], input=json.dumps(event), capture_output=True, text=True,
                              env={**os.environ, "HOLDCO_DEV": ""})

    def test_exit_codes(self):
        blocked = self.run_hook({"tool_name": "Bash", "tool_input": {"command": "python3 -m holdco approve b J"}})
        self.assertEqual(blocked.returncode, 2)
        self.assertIn("human-only guard", blocked.stderr)
        fine = self.run_hook({"tool_name": "Bash", "tool_input": {"command": "python3 -m holdco status"}})
        self.assertEqual((fine.returncode, fine.stderr), (0, ""))
        self.assertEqual(self.run_hook({"tool_name": "Read", "tool_input": {"file_path": "/r/README.md"}}).returncode, 0)


if __name__ == "__main__":
    unittest.main()
