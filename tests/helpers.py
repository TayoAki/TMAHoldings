"""Test helpers: a throwaway workspace with the real shared layer and demo firm."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from holdco import guard, jobs, keys
from holdco.config import Workspace
from holdco.guard import ExecutionContext
from holdco.runners import get_runner
from holdco.util import freeze_clock, reset_clock

REPO = Path(__file__).resolve().parent.parent
BIZ = "demo-bookkeeping"
DANA = "Dana Ruiz"
OWNER = "Morgan Hale"
PASS = "test passphrase for Dana"  # fictional; each test gets its own key store
OWNER_PASS = "test passphrase for Morgan"
HUMAN = ExecutionContext.human_terminal()
REAL_ENVIRONMENT = guard.environment  # tests patch guard.environment; this is the real check
AGENT = ExecutionContext(interactive=False, agent=True)
SCRIPT = ExecutionContext(interactive=False, agent=False)


def as_person_at_terminal(case: unittest.TestCase) -> None:
    """Make the real-environment check see a person at a terminal (tests run inside agent sessions)."""
    patcher = mock.patch("holdco.guard.environment", return_value=(True, False))
    patcher.start()
    case.addCleanup(patcher.stop)


class WorkspaceCase(unittest.TestCase):
    """Each test gets a fresh copy of shared/ and the demo business, and its own key store."""

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="holdco-test-"))
        shutil.copytree(REPO / "shared", self.tmp / "shared")
        shutil.copytree(REPO / "businesses" / BIZ, self.tmp / "businesses" / BIZ)
        shutil.copytree(REPO / "businesses" / "_template", self.tmp / "businesses" / "_template")
        shutil.copytree(REPO / "thesis", self.tmp / "thesis")
        self.ws = Workspace(self.tmp)
        self.biz = self.ws.business(BIZ)
        self.inbox = self.biz.dir / "inbox"
        freeze_clock("2026-09-01T12:00:00")
        env = mock.patch.dict(os.environ, {"HOLDCO_KEYS_DIR": str(self.tmp / "keys")})
        env.start()
        self.addCleanup(env.stop)
        as_person_at_terminal(self)
        keys.add_key(self.biz, DANA, PASS, HUMAN)

    def tearDown(self) -> None:
        reset_clock()
        shutil.rmtree(self.tmp, ignore_errors=True)

    # -- shortcuts

    def set_config(self, **changes) -> None:
        path = self.biz.dir / "business.json"
        config = json.loads(path.read_text())
        config.update(changes)
        path.write_text(json.dumps(config, indent=2))
        self.biz = self.ws.business(BIZ)

    def new_job(self, period: str = "2026-08", inputs: str | None = None) -> dict:
        return jobs.create_job(self.ws, self.biz, "monthly-close", "acme",
                               self.inbox / (inputs or f"{period}-acme"), period=period)

    def runner(self, exclude: set[str] | None = None):
        return get_runner(self.ws, self.biz, "demo", exclude)

    def to_approval(self, period: str = "2026-08") -> dict:
        """Create a clean job and let the demo agents take it to the approval queue."""
        job = self.new_job(period)
        result = self.runner().process(job["id"])
        self.assertEqual(result["job"]["state"], jobs.AWAITING_APPROVAL, result["steps"])
        return result["job"]

    def job(self, job_id: str) -> dict:
        return jobs.load_job(self.biz, job_id)
