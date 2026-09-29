"""Scripted stand-ins for the Claude agents, used to test the workflow scripts.

Each role reads the prompt the workflow wrote (on stdin), pulls out the paths and data a
real agent would need, and does the deterministic version of the job with the demo runner
and the real holdco CLI. If a workflow stops giving agents what they need, these fail.

    python3 tests/workflows/mock_agent.py <role>  < prompt

Set MOCK_REVIEWER=lenient to make the reviewer pass everything (to test machine-check vetoes).
"""

from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from holdco import jobs  # noqa: E402
from holdco.checks import run_checks, score, verdict  # noqa: E402
from holdco.config import Workspace  # noqa: E402
from holdco.runners import get_runner  # noqa: E402
from holdco.util import read_json, write_json  # noqa: E402

HEADER = re.compile(r"Workspace root: (\S+?)\. Business: (\S+?)\. (?:Parent job|Job): (\S+?)\.")


def context(prompt: str):
    root, slug, job_id = HEADER.search(prompt).groups()
    ws = Workspace(Path(root))
    biz = ws.business(slug)
    return ws, biz, jobs.load_job(biz, job_id), jobs.job_dir(biz, job_id)


def run_cli(command: str) -> tuple[int, str]:
    result = subprocess.run(shlex.split(command), cwd=REPO, capture_output=True, text=True)
    return result.returncode, (result.stdout + result.stderr).strip()


def intake(prompt: str) -> dict:
    ws, biz, job, folder = context(prompt)
    return get_runner(ws, biz).intake(job["type"], job["client"], folder / "input", job["period"])


def preparer(prompt: str) -> dict:
    ws, biz, job, folder = context(prompt)
    target = re.search(r"Write the deliverable JSON to exactly (\S+?)\. It is", prompt).group(1)
    given = re.search(r"change nothing else:\n(.*?)\n5\. Write", prompt, re.S)
    if given:
        feedback = json.loads(given.group(1))
    else:
        feedback = job["reviews"][-1]["findings"] if job["state"] == jobs.BLOCKED and job["reviews"] else []
    out = get_runner(ws, biz).prepare(job["type"], job["client"], folder / "input", job["period"],
                                      feedback, job["answers"])
    if out.get("status") == "needs_human":
        return {"status": "needs_human", "question": out["question"], "key": out["key"], "context": out["context"]}
    write_json(target, out)
    return {"status": "drafted", "draft_file": str(Path(target).relative_to(folder)), "summary": "drafted",
            "rules_applied": out["rules_applied"]}


def reviewer(prompt: str) -> dict:
    ws, biz, job, folder = context(prompt)
    if os.environ.get("MOCK_REVIEWER") == "lenient":
        return {"verdict": "PASS", "score": 100, "findings": [], "summary": "Looks fine (lenient mock)."}
    if "Chase message:" in prompt:
        missing = json.loads(re.search(r"Missing items \(from intake\): (.*)\n", prompt).group(1))
        message = json.loads(re.search(r"Chase message: (.*)\n", prompt).group(1))
        draft = {"job_type": "document-chase", "client": job["client"], "client_message": message,
                 "data": {"missing": missing, "parent_job": job["id"]}}
        findings = run_checks(ws, biz, "document-chase", job["client"], draft, folder / "input", {})
        return {"verdict": verdict(findings), "score": score(findings), "findings": findings, "summary": "chase checked"}
    draft_path = re.search(r"The draft to review is (\S+?)\. Also", prompt).group(1)
    review = get_runner(ws, biz).review(job["type"], job["client"], folder / "input", read_json(draft_path),
                                        job["answers"])
    return review


def clerk(prompt: str) -> dict:
    writes = re.findall(r"(?:to the file|exactly to) (\S+?):\n(\{.*?\n\})\n", prompt, re.S)
    for path, body in writes:
        write_json(path, json.loads(body))
    commands = [line.strip().split(": ", 1)[-1] if "Then run:" in line else re.sub(r"^\d+\.\s*", "", line.strip())
                for line in prompt.splitlines() if "python3 -m holdco" in line]
    outputs = [run_cli(cmd) for cmd in commands]
    if "record-run" in prompt:
        code, output = outputs[0]
        data = json.loads(output) if code == 0 else {}
        review = data.get("last_review") or {}
        return {"ok": code == 0, "state": data.get("state", ""), "last_review_verdict": review.get("verdict", ""),
                "findings": review.get("findings") or [], "open_question": data.get("open_question") or "",
                "output": output}
    if "golden materialize" in prompt:
        cases = re.findall(r"golden materialize \S+ (\S+) --json", prompt)
        return {"jobs": [{"case": c, "job": json.loads(o).get("job", "") if code == 0 else "", "ok": code == 0}
                         for c, (code, o) in zip(cases, outputs)]}
    if "golden compare" in prompt:
        results = []
        for code, output in outputs:
            data = json.loads(output)
            results.append({"case": data["case"], "job": data["job"], "passed": data["passed"],
                            "differences": data["differences"], "output": output})
        return {"results": results}
    titles = re.findall(r'"title": "(.*?)"', prompt)
    return {"results": [{"title": t, "ok": code == 0, "output": o} for t, (code, o) in zip(titles, outputs)]}


def rules_curator(prompt: str) -> dict:
    command = next(line.strip().split("Run: ", 1)[1] for line in prompt.splitlines() if "corrections review" in line)
    code, output = run_cli(command)
    report = json.loads(output)
    return {"counts_by_category": report["by_category"],
            "deterministic_proposals": [p["id"] for p in report["new_proposals"]],
            "rules_not_followed": [r["rule"] for r in report["rule_not_followed"]],
            "proposals": [], "agent_file_fixes": [], "notes": "mock curator: exact repeats only"}


def default(prompt: str) -> dict:
    if "You are a SKEPTIC" in prompt:
        return {"keep": True, "reasons": ["evidence spans two jobs"]}
    if "deal score" in prompt and "Return the key numbers" in prompt:
        command = next(line.strip().split("Run: ", 1)[1] for line in prompt.splitlines() if line.startswith("Run: "))
        _, output = run_cli(command)
        r = json.loads(output)
        return {"verdict": r["verdict"], "fit_score": r["fit_score"], "ebitda_today": r["ebitda_today"],
                "asking_price": r["financing"]["price"], "max_price": r["max_price"], "binding_cap": r["binding_cap"],
                "dscr_year1": r["dscr_year1"], "dscr_peak": r["dscr_peak"],
                "failed_checks": [c["criterion"] for c in r["checks"] if not c["ok"]], "warnings": r["warnings"],
                "scenarios": r["scenarios"]}
    if "Your lens:" in prompt:
        lens = re.search(r"Your lens: ([A-Z ,\-]+):", prompt).group(1)
        return {"lens": lens, "score": 7, "findings": [{"severity": "major", "finding": "Owner handles top 10 clients",
                "evidence": "deal file: owner_transition_months", "diligence_question": "Who else knows them?"}],
                "summary": f"{lens}: workable with diligence."}
    if "red team" in prompt.lower() and "WALKING AWAY" in prompt:
        return {"walk_away_case": "Asking price is above what today's earnings carry.",
                "strongest_reasons": ["price"], "what_would_change_my_mind": ["price at or below max"],
                "verdict_if_forced": "NEGOTIATE"}
    if "decision memo" in prompt:
        path = re.search(r"save it with the Write tool to (\S+?)\.\n", prompt).group(1)
        Path(path).write_text("# Example — decision memo\n\n## Recommendation\nNEGOTIATE\n", encoding="utf-8")
        return {"recommendation": "NEGOTIATE", "max_price": 1080000, "memo_path": path,
                "top_risks": ["price"], "next_steps": ["counter at max price"]}
    raise SystemExit(f"mock default agent has no script for this prompt:\n{prompt[:400]}")


ROLES = {"intake": intake, "preparer": preparer, "reviewer": reviewer, "clerk": clerk,
         "rules-curator": rules_curator, "default": default}

if __name__ == "__main__":
    print(json.dumps(ROLES[sys.argv[1]](sys.stdin.read())))
