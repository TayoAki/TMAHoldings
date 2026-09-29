"""Golden cases: real accepted work used to test the agents every time something changes.

Each case is the original input a job started from plus the output a person
accepted: what they approved or, in shadow mode, the version they did by hand. Running the eval re-does the work with today's agents and rules and
compares the material facts (not the wording) against what was accepted.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from holdco import jobs, jobtypes
from holdco.config import Business, HoldcoError, Workspace
from holdco.diffing import Change, diff
from holdco.util import next_id, now_iso, read_json, sha256_json, write_json


def list_cases(biz: Business) -> list[dict]:
    if not biz.golden_dir.is_dir():
        return []
    return [read_json(p) for p in sorted(biz.golden_dir.glob("G-*/case.json"))]


def accepted_output(biz: Business, job_id: str) -> tuple[dict, Path]:
    """The output a person accepted for a job: what they approved or, in shadow mode, their own version."""
    job = jobs.load_job(biz, job_id)
    folder = jobs.job_dir(biz, job_id)
    if job.get("eval_case"):
        raise HoldcoError(f"{job_id} is an eval job, not accepted work.")
    for record, name in ((job.get("approval"), "approved.json"), (job.get("shadow"), "human-version.json")):
        if record and (folder / name).exists():
            if record.get("sha256") and sha256_json(read_json(folder / name)) != record["sha256"]:
                raise HoldcoError(f"{name} for {job_id} changed after {record['by']} signed off on it; "
                                  "it can't be used as a test (runbook 06).")
            return job, folder / name
    raise HoldcoError(f"{job_id} was never approved or shadow-compared, so it has no accepted output to test "
                      "against yet. Accept the proposal once it is.")


def create_case_from_job(ws: Workspace, biz: Business, job_id: str, rule_ids: list[str]) -> str:
    job, approved = accepted_output(biz, job_id)
    for case in list_cases(biz):
        if case["source_job"] == job_id:
            case["rule_ids"] = sorted(set(case["rule_ids"]) | set(rule_ids))
            write_json(biz.golden_dir / case["id"] / "case.json", case)
            return case["id"]
    case_id = next_id("G", (c["id"] for c in list_cases(biz)))
    folder = biz.golden_dir / case_id
    source_input = jobs.job_dir(biz, job_id) / "input"
    if source_input.is_dir():
        shutil.copytree(source_input, folder / "input")
    else:
        (folder / "input").mkdir(parents=True)
    write_json(folder / "expected.json", read_json(approved))
    write_json(folder / "case.json", {
        "id": case_id, "business": biz.slug, "job_type": job["type"], "client": job["client"],
        "period": job.get("period"), "source_job": job_id, "rule_ids": sorted(rule_ids),
        "answers": job.get("answers", {}), "created_at": now_iso(),
    })
    return case_id


def compare(job_type: str, expected: dict, produced: dict) -> list[Change]:
    kind = jobtypes.get(job_type)
    return diff(kind.material_view(expected), kind.material_view(produced))


def run_eval(ws: Workspace, biz: Business, runner, case_ids: list[str] | None = None) -> dict:
    """Re-run the agent pipeline (up to the approval point) on every golden case."""
    results = []
    for case in list_cases(biz):
        if case_ids and case["id"] not in case_ids:
            continue
        folder = biz.golden_dir / case["id"]
        produced = runner.run_offline(case["job_type"], case["client"], folder / "input",
                                      case.get("period"), case.get("answers", {}))
        if produced.get("status") == "needs_human":
            results.append({"case": case["id"], "source_job": case["source_job"], "passed": False,
                            "differences": [], "reason": f"agent stopped to ask: {produced['question']}"})
            continue
        differences = compare(case["job_type"], read_json(folder / "expected.json"), produced)
        results.append({"case": case["id"], "source_job": case["source_job"], "passed": not differences,
                        "differences": [c.to_dict() for c in differences], "reason": ""})
    return {"business": biz.slug, "cases": results, "passed": sum(r["passed"] for r in results),
            "failed": sum(not r["passed"] for r in results)}


def materialize(ws: Workspace, biz: Business, case_id: str) -> dict:
    """Turn a golden case into an eval job so the real agent workflow can be tested on it."""
    folder = biz.golden_dir / case_id
    if not (folder / "case.json").exists():
        raise HoldcoError(f"No golden case {case_id} in {biz.slug}.")
    case = read_json(folder / "case.json")
    job = jobs.create_job(ws, biz, case["job_type"], case["client"], folder / "input", period=case.get("period"),
                          job_id=jobs._unique_id(biz, f"eval-{case_id}"), eval_case=case_id)
    job["answers"] = dict(case.get("answers", {}))
    jobs.save_job(biz, job)
    # The inputs were complete when a person approved the original job, so skip straight to the preparer.
    return jobs.record_intake(ws, biz, job["id"], {"status": "complete",
                                                   "note": f"eval of {case_id}: inputs known complete"})


def compare_job(ws: Workspace, biz: Business, case_id: str, job_id: str) -> dict:
    case = read_json(biz.golden_dir / case_id / "case.json")
    job = jobs.load_job(biz, job_id)
    produced = jobs.latest_draft(biz, job)
    differences = compare(case["job_type"], read_json(biz.golden_dir / case_id / "expected.json"), produced)
    return {"case": case_id, "job": job_id, "passed": not differences,
            "differences": [c.to_dict() for c in differences]}
