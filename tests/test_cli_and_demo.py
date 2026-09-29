"""The CLI as an agent would call it, and the full demo."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests.helpers import REPO, WorkspaceCase


def cli(*args: str, root: Path, agent: bool = True, stdin: str | None = None) -> subprocess.CompletedProcess:
    env = {k: v for k, v in os.environ.items() if k not in ("CLAUDECODE", "HOLDCO_AGENT")}
    if agent:
        env["CLAUDECODE"] = "1"
    return subprocess.run([sys.executable, "-m", "holdco", "--root", str(root), *args], cwd=REPO, env=env,
                          input=stdin, capture_output=True, text=True, timeout=60)


class Cli(WorkspaceCase):
    def test_human_only_commands_refuse_inside_an_agent(self):
        job = self.to_approval()
        for args in (["approve", "demo-bookkeeping", job["id"], "--by", "Dana Ruiz"],
                     ["send", "demo-bookkeeping", job["id"], "--by", "Dana Ruiz"],
                     ["answer", "demo-bookkeeping", job["id"], "--by", "Dana Ruiz", "--text", "x"],
                     ["cancel", "demo-bookkeeping", job["id"], "--by", "Dana Ruiz", "--reason", "x"],
                     ["rules", "accept", "demo-bookkeeping", "P-0001", "--by", "Dana Ruiz"]):
            result = cli(*args, root=self.tmp)
            self.assertEqual(result.returncode, 3, (args, result.stdout, result.stderr))
            self.assertIn("REFUSED", result.stderr)
        self.assertEqual(self.job(job["id"])["state"], "awaiting_approval")

    def test_human_only_commands_refuse_without_a_terminal_even_outside_an_agent(self):
        job = self.to_approval()
        result = cli("approve", "demo-bookkeeping", job["id"], "--by", "Dana Ruiz", root=self.tmp, agent=False,
                     stdin="approve\n")
        self.assertEqual(result.returncode, 3, result.stderr)
        self.assertIn("interactive terminal", result.stderr)

    def test_agent_safe_commands_work(self):
        new = cli("job", "new", "demo-bookkeeping", "--type", "monthly-close", "--client", "acme",
                  "--inputs", str(self.inbox / "2026-08-acme"), "--period", "2026-08", root=self.tmp)
        self.assertEqual(new.returncode, 0, new.stderr)
        run = cli("run", "demo-bookkeeping", "2026-08-acme-monthly-close", root=self.tmp)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertIn("awaiting_approval", run.stdout)
        for args in (["queue"], ["status"], ["job", "list", "--json"], ["check", "demo-bookkeeping",
                     "2026-08-acme-monthly-close"], ["job", "show", "demo-bookkeeping", "2026-08-acme-monthly-close"],
                     ["metrics", "demo-bookkeeping", "--as-of", "2026-09-28"], ["rules", "list", "demo-bookkeeping"],
                     ["corrections", "review", "demo-bookkeeping", "--dry-run"],
                     ["deal", "score", str(self.tmp / "thesis/deals/example-target.json")], ["model", "margin"]):
            result = cli(*args, root=self.tmp)
            self.assertEqual(result.returncode, 0, (args, result.stderr))
        self.assertIn("APPROVE", cli("queue", root=self.tmp).stdout)

    def test_new_business_from_template(self):
        result = cli("new-business", "harbor-books", "--name", "Harbor Books", "--industry", "bookkeeping",
                     "--gm", "Pat Lee", root=self.tmp)
        self.assertEqual(result.returncode, 0, result.stderr)
        biz = self.ws.business("harbor-books")
        self.assertEqual((biz.gm, biz.approvers, biz.is_demo), ("Pat Lee", ["Pat Lee"], False))


class Demo(unittest.TestCase):
    def test_demo_proofs_all_hold(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = {k: v for k, v in os.environ.items()}
            result = subprocess.run([sys.executable, "-m", "holdco", "demo", "--quiet", "--workspace",
                                     str(Path(tmp) / "ws")], cwd=REPO, env=env, capture_output=True, text=True,
                                    timeout=120)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("PROOF SUMMARY: 20/20 held", result.stdout)


if __name__ == "__main__":
    unittest.main()
