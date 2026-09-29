"""The job pipeline: intake -> preparer -> reviewer -> a named human -> client.

The transition table below is the whole policy. Agents (intake, preparer,
reviewer) can move work forward or send it back, but there is no row that
lets any agent approve or send. Only the human-only functions at the bottom
of this module create a human actor; each calls guard.require_human first,
and approve/send also need the approver's passphrase to sign (holdco/keys.py).

Job folder layout (businesses/<biz>/jobs/<job-id>/):

    job.json          state, history, input hashes, drafts, reviews, questions, approval
    input/            the documents the job was created with (hashed; changes are refused)
    intake.json       what the intake agent found
    drafts/vN.json    each preparer draft (vN.md is a readable rendering)
    work/             the only place agents write, before a draft is recorded
    approved.json     exactly what the named human approved (signed)
"""

from __future__ import annotations

import copy
import datetime as dt
import shutil
from dataclasses import dataclass
from pathlib import Path

from holdco import checks, corrections, jobtypes, keys
from holdco.config import Business, HoldcoError, Workspace, safe_id
from holdco.diffing import Change, diff
from holdco.guard import ExecutionContext, require_human
from holdco.util import hash_tree, now, now_iso, read_json, sha256_file, sha256_json, write_json

RECEIVED = "received"
WAITING_ON_CLIENT = "waiting_on_client"
READY = "ready"
DRAFTED = "drafted"
BLOCKED = "blocked"
AWAITING_APPROVAL = "awaiting_approval"
NEEDS_HUMAN = "needs_human"
APPROVED = "approved"
SENT = "sent"
SHADOWED = "shadowed"   # shadow mode: compared with the person's own version, never sent
CANCELLED = "cancelled"

STATES = (
    RECEIVED, WAITING_ON_CLIENT, READY, DRAFTED, BLOCKED,
    AWAITING_APPROVAL, NEEDS_HUMAN, APPROVED, SENT, SHADOWED, CANCELLED,
)
TERMINAL = {SENT, SHADOWED, CANCELLED}
AGENT_ROLES = {"intake", "preparer", "reviewer"}
CHASE_COOLDOWN = dt.timedelta(days=3)

# (from, to) -> roles allowed to make that move. Nothing else is possible.
TRANSITIONS: dict[tuple[str, str], set[str]] = {
    (RECEIVED, READY): {"intake"},
    (RECEIVED, WAITING_ON_CLIENT): {"intake"},
    (RECEIVED, NEEDS_HUMAN): {"intake"},
    (WAITING_ON_CLIENT, RECEIVED): {"human", "system"},
    (READY, DRAFTED): {"preparer"},
    (READY, NEEDS_HUMAN): {"preparer"},
    (BLOCKED, DRAFTED): {"preparer"},
    (BLOCKED, NEEDS_HUMAN): {"preparer", "system"},
    (DRAFTED, AWAITING_APPROVAL): {"reviewer"},
    (DRAFTED, BLOCKED): {"reviewer"},
    (DRAFTED, NEEDS_HUMAN): {"reviewer"},
    (AWAITING_APPROVAL, APPROVED): {"human"},
    (AWAITING_APPROVAL, BLOCKED): {"human"},
    (NEEDS_HUMAN, RECEIVED): {"human"},
    (NEEDS_HUMAN, READY): {"human"},
    (NEEDS_HUMAN, BLOCKED): {"human"},
    (NEEDS_HUMAN, DRAFTED): {"human"},
    (APPROVED, SENT): {"human"},
    (DRAFTED, SHADOWED): {"human"},
    (BLOCKED, SHADOWED): {"human"},
    (NEEDS_HUMAN, SHADOWED): {"human"},
    (AWAITING_APPROVAL, SHADOWED): {"human"},
}
for _state in STATES:
    if _state not in TERMINAL:
        TRANSITIONS[(_state, CANCELLED)] = {"human"}


@dataclass(frozen=True)
class Actor:
    role: str
    name: str

    def label(self) -> str:
        return f"{self.role}:{self.name}"


INTAKE = Actor("intake", "intake-agent")
PREPARER = Actor("preparer", "preparer-agent")
REVIEWER = Actor("reviewer", "reviewer-agent")
SYSTEM = Actor("system", "holdco")

SHADOW, ASSISTED = "shadow", "assisted"


def rollout_mode(biz: Business, job_type: str) -> str:
    """shadow: agents run in the background, people keep doing the work by hand and nothing an
    agent drafts can be approved or sent. assisted: agents draft, a person approves and sends.
    New job types start in shadow."""
    return (biz.setting("rollout") or {}).get(job_type, SHADOW)


def _require_assisted(biz: Business, job: dict, action: str) -> None:
    if rollout_mode(biz, job["type"]) != ASSISTED:
        raise HoldcoError(
            f"{job['type']} is in shadow mode at {biz.slug}: agent drafts cannot be {action}. "
            f"Do the work the usual way, then record your version with "
            f"`python3 -m holdco shadow {biz.slug} {job['id']} --by ...` (runbook 02)."
        )


def _require_real_job(job: dict, action: str) -> None:
    if job.get("eval_case"):
        raise HoldcoError(f"{job['id']} is an eval job (a re-run of {job['eval_case']}); it can't be {action}.")


# ---------------------------------------------------------------- storage


def job_dir(biz: Business, job_id: str) -> Path:
    return biz.jobs_dir / safe_id(job_id, "Job id")


def load_job(biz: Business, job_id: str) -> dict:
    path = job_dir(biz, job_id) / "job.json"
    if not path.exists():
        raise HoldcoError(f"No job '{job_id}' in {biz.slug}.")
    return read_json(path)


def save_job(biz: Business, job: dict) -> None:
    write_json(job_dir(biz, job["id"]) / "job.json", job)


def list_jobs(biz: Business, state: str | None = None, include_eval: bool = False) -> list[dict]:
    if not biz.jobs_dir.is_dir():
        return []
    jobs = []
    for child in sorted(biz.jobs_dir.iterdir()):
        if (child / "job.json").exists():
            job = read_json(child / "job.json")
            if job.get("eval_case") and not include_eval:
                continue
            if state is None or job["state"] == state:
                jobs.append(job)
    return jobs


def check_transition(job: dict, to: str, actor: Actor) -> None:
    """Raise unless ``actor`` may move ``job`` to ``to``. This table is the whole policy."""
    allowed = TRANSITIONS.get((job["state"], to))
    if allowed is None:
        raise HoldcoError(f"Job {job['id']} cannot go from {job['state']} to {to}.")
    if actor.role not in allowed:
        raise PermissionError(
            f"{actor.role} cannot move job {job['id']} from {job['state']} to {to} "
            f"(allowed: {', '.join(sorted(allowed))})."
        )


def _transition(job: dict, to: str, actor: Actor, note: str | None = None) -> None:
    check_transition(job, to, actor)
    entry = {"at": now_iso(), "from": job["state"], "to": to, "actor": actor.label()}
    if note:
        entry["note"] = note
    job["history"].append(entry)
    job["state"] = to


def _require_agent(actor: Actor, *roles: str) -> None:
    if actor.role not in roles:
        raise PermissionError(f"Only the {'/'.join(roles)} agent can do this (got {actor.role}).")


def _copy_inputs(source: Path, dest: Path) -> list[str]:
    source = Path(source)
    if not source.is_dir():
        raise HoldcoError(f"Inputs folder not found: {source}")
    items = [item for item in sorted(source.iterdir()) if not item.name.startswith(".")]
    if not items:
        raise HoldcoError(f"Inputs folder {source} is empty: nothing was added.")
    dest.mkdir(parents=True, exist_ok=True)
    for item in items:
        target = dest / item.name
        if item.is_dir():
            shutil.copytree(item, target, dirs_exist_ok=True)
        else:
            shutil.copy2(item, target)
    return [item.name for item in items]


def _verify_inputs(biz: Business, job: dict) -> None:
    """Inputs are evidence. They change only through create_job / add_inputs, never in place."""
    recorded = job.get("inputs") or {}
    current = hash_tree(job_dir(biz, job["id"]) / "input")
    changed = sorted(name for name in set(recorded) | set(current) if recorded.get(name) != current.get(name))
    if changed:
        raise HoldcoError(f"Input files for {job['id']} changed outside the holdco CLI: {', '.join(changed)}. "
                          "Nothing was recorded. Add documents with `holdco job add-inputs`.")


def _new_job_record(biz: Business, job_id: str, job_type: str, client: str, period: str | None,
                    parent: str | None, eval_case: str | None) -> dict:
    return {
        "id": job_id,
        "business": biz.slug,
        "type": job_type,
        "client": client,
        "period": period,
        "state": RECEIVED,
        "resume_state": None,
        "created_at": now_iso(),
        "parent": parent,
        "children": [],
        "eval_case": eval_case,
        "inputs": {},
        "drafts": [],
        "reviews": [],
        "questions": [],
        "answers": {},
        "approval": None,
        "sent": None,
        "history": [],
    }


def _unique_id(biz: Business, base: str) -> str:
    candidate, n = safe_id(base, "Job id"), 2
    while job_dir(biz, candidate).exists():
        candidate, n = f"{base}-{n}", n + 1
    return candidate


def create_job(ws: Workspace, biz: Business, job_type: str, client: str, inputs: Path | None = None,
               period: str | None = None, job_id: str | None = None, parent: str | None = None,
               eval_case: str | None = None) -> dict:
    safe_id(job_type, "Job type")
    safe_id(client, "Client id")
    if period is not None:
        safe_id(period, "Period")
    job_id = safe_id(job_id, "Job id") if job_id else _unique_id(biz, f"{period or now_iso()[:10]}-{client}-{job_type}")
    if job_dir(biz, job_id).exists():
        raise HoldcoError(f"Job {job_id} already exists in {biz.slug}.")
    job = _new_job_record(biz, job_id, job_type, client, period, parent, eval_case)
    job_dir(biz, job_id).mkdir(parents=True)
    (job_dir(biz, job_id) / "work").mkdir()
    copied = _copy_inputs(inputs, job_dir(biz, job_id) / "input") if inputs else []
    job["inputs"] = hash_tree(job_dir(biz, job_id) / "input")
    job["history"].append({"at": now_iso(), "from": None, "to": RECEIVED, "actor": SYSTEM.label(),
                           "note": f"created with inputs: {', '.join(copied) or 'none'}"})
    save_job(biz, job)
    return job


def add_inputs(biz: Business, job_id: str, inputs: Path) -> dict:
    job = load_job(biz, job_id)
    if job["state"] in TERMINAL:
        raise HoldcoError(f"Job {job_id} is {job['state']}; create a new job instead.")
    _verify_inputs(biz, job)
    copied = _copy_inputs(inputs, job_dir(biz, job_id) / "input")
    job["inputs"] = hash_tree(job_dir(biz, job_id) / "input")
    if job["state"] == WAITING_ON_CLIENT:
        _transition(job, RECEIVED, SYSTEM, note=f"client sent: {', '.join(copied)}")
    else:
        job["history"].append({"at": now_iso(), "from": job["state"], "to": job["state"],
                               "actor": SYSTEM.label(), "note": f"inputs added: {', '.join(copied)}"})
    save_job(biz, job)
    return job


# ----------------------------------------------------------------- drafts


def _store_draft(biz: Business, job: dict, deliverable: dict, author: Actor) -> dict:
    version = len(job["drafts"]) + 1
    folder = job_dir(biz, job["id"]) / "drafts"
    write_json(folder / f"v{version}.json", deliverable)
    (folder / f"v{version}.md").write_text(jobtypes.render_message(deliverable), encoding="utf-8")
    record = {"version": version, "file": f"drafts/v{version}.json", "sha256": sha256_json(deliverable),
              "author": author.role, "at": now_iso()}
    job["drafts"].append(record)
    return record


def latest_draft(biz: Business, job: dict) -> dict:
    if not job["drafts"]:
        raise HoldcoError(f"Job {job['id']} has no drafts yet.")
    return read_json(job_dir(biz, job["id"]) / job["drafts"][-1]["file"])


def _verify_draft_integrity(biz: Business, job: dict) -> None:
    record = job["drafts"][-1]
    on_disk = read_json(job_dir(biz, job["id"]) / record["file"])
    if sha256_json(on_disk) != record["sha256"]:
        raise HoldcoError(
            f"Draft v{record['version']} of {job['id']} changed on disk after it was recorded. "
            "Drafts are immutable: record a new version instead."
        )


def _validate(job: dict, deliverable: dict) -> None:
    errors = jobtypes.validate(job["type"], deliverable)
    if isinstance(deliverable, dict) and deliverable.get("client") not in (None, job["client"]):
        errors.append(f"deliverable is for client '{deliverable.get('client')}' but the job is for '{job['client']}'")
    if errors:
        raise HoldcoError(f"Draft for {job['id']} is not valid: " + "; ".join(errors))


def _prepare_deliverable(job: dict, deliverable: dict) -> dict:
    """Validate the parts an agent must provide, then fill in the derived totals."""
    if not isinstance(deliverable, dict):
        raise HoldcoError(f"Draft for {job['id']} is not a JSON object.")
    deliverable = jobtypes.get(job["type"]).normalize(deliverable)
    _validate(job, deliverable)
    return deliverable


def _run_checks(ws: Workspace, biz: Business, job: dict, deliverable: dict) -> list[dict]:
    return checks.run_checks(ws, biz, job["type"], job["client"], deliverable, job_dir(biz, job["id"]) / "input",
                             job.get("answers"), period=job.get("period"))


# ------------------------------------------------------------ agent steps


def _chase_on_record(biz: Business, job: dict) -> str | None:
    """An open chase, or one sent in the last few days, means: don't chase again yet."""
    for child_id in reversed(job["children"]):
        child = load_job(biz, child_id)
        if child["type"] != "document-chase" or child["state"] in (CANCELLED, SHADOWED):
            continue
        if child["state"] != SENT:
            return f"chase {child_id} is still open ({child['state']})"
        sent_at = dt.datetime.fromisoformat(child["sent"]["at"])
        if now() - sent_at < CHASE_COOLDOWN:
            return f"chase {child_id} went out {child['sent']['at'][:10]}; waiting before chasing again"
    return None


def record_intake(ws: Workspace, biz: Business, job_id: str, result: dict, actor: Actor = INTAKE) -> dict:
    """Record what the intake agent found. Missing documents create a chase job (at most one at a time)."""
    _require_agent(actor, "intake")
    job = load_job(biz, job_id)
    _verify_inputs(biz, job)
    status = result.get("status")
    if status not in ("complete", "missing_documents", "needs_human"):
        raise HoldcoError("Intake status must be complete, missing_documents or needs_human.")
    if status == "needs_human" and not (result.get("question") or "").strip():
        raise HoldcoError("Intake asked for a human but gave no question.")
    if status == "missing_documents":
        missing, message = result.get("missing") or [], result.get("chase_message") or {}
        if not missing or not message.get("subject") or not message.get("body_markdown"):
            raise HoldcoError("Missing documents need a non-empty 'missing' list and a chase_message.")
    write_json(job_dir(biz, job_id) / "intake.json", {**result, "recorded_at": now_iso()})
    if status == "complete":
        _transition(job, READY, actor)
    elif status == "needs_human":
        question = result["question"].strip()
        _ask(job, actor, question, result.get("question_key"))
        _transition(job, NEEDS_HUMAN, actor, note=question)
    else:
        on_record = _chase_on_record(biz, job)
        if on_record:
            _transition(job, WAITING_ON_CLIENT, actor, note=f"{len(missing)} document(s) missing; {on_record}")
            save_job(biz, job)
            return job
        _transition(job, WAITING_ON_CLIENT, actor, note=f"{len(missing)} document(s) missing")
        chase = _new_job_record(biz, _unique_id(biz, f"{job_id}-chase"), "document-chase",
                                job["client"], job["period"], job_id, job.get("eval_case"))
        job_dir(biz, chase["id"]).mkdir(parents=True)
        (job_dir(biz, chase["id"]) / "work").mkdir()
        deliverable = {
            "job_type": "document-chase",
            "client": job["client"],
            "client_message": {"subject": message["subject"], "body_markdown": message["body_markdown"]},
            "data": {"missing": missing, "parent_job": job_id},
            "rules_applied": result.get("rules_applied", []),
        }
        _validate(chase, deliverable)
        _store_draft(biz, chase, deliverable, actor)
        chase["state"] = DRAFTED
        chase["history"].append({"at": now_iso(), "from": None, "to": DRAFTED, "actor": actor.label(),
                                 "note": f"chase for {job_id} drafted by intake"})
        save_job(biz, chase)
        job["children"].append(chase["id"])
    save_job(biz, job)
    return job


def record_draft(ws: Workspace, biz: Business, job_id: str, deliverable: dict, actor: Actor = PREPARER) -> dict:
    _require_agent(actor, "preparer")
    job = load_job(biz, job_id)
    if job["state"] not in (READY, BLOCKED):
        raise HoldcoError(f"Can't record a draft while {job_id} is {job['state']}.")
    _verify_inputs(biz, job)
    deliverable = _prepare_deliverable(job, deliverable)
    record = _store_draft(biz, job, deliverable, actor)
    _transition(job, DRAFTED, actor, note=f"draft v{record['version']}")
    save_job(biz, job)
    return job


def record_review(ws: Workspace, biz: Business, job_id: str, review: dict, actor: Actor = REVIEWER) -> dict:
    """Record the reviewer's verdict. The reviewer can pass or block. It cannot approve or send.

    Machine checks run on every draft, whoever reviewed it, and the recorded score is the
    lower of the reviewer's score and the score of all findings, so code can veto a PASS.
    """
    _require_agent(actor, "reviewer")
    job = load_job(biz, job_id)
    if job["state"] != DRAFTED:
        raise HoldcoError(f"Nothing to review: {job_id} is {job['state']}.")
    _verify_draft_integrity(biz, job)
    _verify_inputs(biz, job)
    version = job["drafts"][-1]["version"]
    if review.get("draft_version") not in (None, version):
        raise HoldcoError(f"Review is for draft v{review.get('draft_version')} but the latest is v{version}.")
    verdict = str(review.get("verdict", "")).upper()
    if verdict not in ("PASS", "BLOCK", "NEEDS_HUMAN"):
        raise HoldcoError("Review verdict must be PASS, BLOCK or NEEDS_HUMAN.")
    findings = list(review.get("findings") or [])
    reviewer_score = review.get("score")
    pass_score = biz.setting("review_pass_score", 80)
    machine = _run_checks(ws, biz, job, latest_draft(biz, job))
    seen = {(f.get("rule"), f.get("location"), f.get("issue")) for f in findings}
    findings += [{**f, "source": "machine-check"} for f in machine
                 if (f.get("rule"), f.get("location"), f.get("issue")) not in seen]
    score = checks.score(findings)
    if isinstance(reviewer_score, (int, float)) and not isinstance(reviewer_score, bool):
        score = min(score, reviewer_score)
    note = None
    blockers = [f for f in findings if str(f.get("severity", "")).lower() == "blocker"]
    if verdict == "PASS" and (blockers or score < pass_score):
        verdict, note = "BLOCK", "downgraded from PASS: blocker findings or score below the pass mark"
    entry = {"version": version, "verdict": verdict, "score": score, "reviewer_score": reviewer_score,
             "findings": findings, "summary": review.get("summary", ""), "reviewer": actor.name, "at": now_iso()}
    if note:
        entry["note"] = note
    job["reviews"].append(entry)
    if verdict == "PASS":
        _transition(job, AWAITING_APPROVAL, actor, note=f"v{version} passed review (score {score})")
    elif verdict == "NEEDS_HUMAN":
        question = (review.get("question") or review.get("summary") or "Reviewer needs a person to decide.").strip()
        _ask(job, actor, question, review.get("question_key"))
        _transition(job, NEEDS_HUMAN, actor, note=question)
    else:
        _transition(job, BLOCKED, actor, note=note or f"v{version} blocked: {len(findings)} finding(s)")
        max_drafts = biz.setting("max_drafts", 3)
        if len(job["drafts"]) >= max_drafts:
            question = (f"The reviewer blocked {len(job['drafts'])} drafts in a row. "
                        "Read the findings and tell the preparer how to proceed, or cancel the job.")
            _ask(job, SYSTEM, question, None)
            _transition(job, NEEDS_HUMAN, SYSTEM, note="too many blocked drafts")
    save_job(biz, job)
    return job


def _ask(job: dict, actor: Actor, question: str, key: str | None, context: dict | None = None) -> None:
    job["resume_state"] = job["state"]
    job["questions"].append({"at": now_iso(), "asked_by": actor.role, "question": question, "key": key,
                             "context": context or {}, "answer": None, "answered_by": None,
                             "answered_at": None})


def escalate(biz: Business, job_id: str, question: str, actor: Actor, key: str | None = None,
             context: dict | None = None) -> dict:
    """Any agent can stop and ask a person. That is always allowed."""
    _require_agent(actor, *AGENT_ROLES)
    job = load_job(biz, job_id)
    if not question.strip():
        raise HoldcoError("An escalation needs a question.")
    _ask(job, actor, question.strip(), key, context)
    _transition(job, NEEDS_HUMAN, actor, note=question.strip())
    save_job(biz, job)
    return job


def _round_draft(biz: Business, job: dict, round_: dict) -> dict:
    work = (job_dir(biz, job["id"]) / "work").resolve()
    path = (job_dir(biz, job["id"]) / str(round_["draft_file"])).resolve()
    if work not in path.parents:
        raise HoldcoError(f"draft_file must be inside {job['id']}/work/ (got {round_['draft_file']}).")
    if not path.exists():
        raise HoldcoError(f"Draft file not found: {path}")
    return _prepare_deliverable(job, read_json(path))


def record_run(ws: Workspace, biz: Business, job_id: str, run: dict) -> dict:
    """Apply one agent-workflow run (see .claude/workflows/holdco-process-job.js) in order.

    run = {
      "intake": {...} | null,
      "chase_review": {...} | null,
      "rounds": [{"version": 1, "draft_file": "work/draft.v1.json", "review": {...}},   # draft + review
                 {"version": 2, "review": {...}},                                          # review only (drafted jobs)
                 {"version": 1, "escalation": {"question": "...", "key": "..."}}]         # preparer stops
    }
    Everything is validated before anything is recorded, and an intake that was already
    recorded is skipped, so a failed run can simply be retried.
    """
    job = load_job(biz, job_id)
    summary: list[str] = []
    rounds = run.get("rounds") or []
    drafts = {i: _round_draft(biz, job, r) for i, r in enumerate(rounds)
              if r.get("draft_file") and not r.get("escalation")}
    intake = run.get("intake")
    if intake and job["state"] != RECEIVED:
        if not (job_dir(biz, job_id) / "intake.json").exists():
            raise HoldcoError(f"{job_id} is {job['state']}; an intake result can't be recorded now.")
        summary.append("intake already recorded; skipped")
        intake = None
    if intake:
        children_before = len(job["children"])
        job = record_intake(ws, biz, job_id, intake)
        summary.append(f"intake: {intake['status']}")
        if intake["status"] == "missing_documents":
            new_chases = job["children"][children_before:]
            if not new_chases:
                summary.append("a chase is already open or was just sent; no new chase drafted")
            elif run.get("chase_review"):
                record_review(ws, biz, new_chases[0], run["chase_review"])
                summary.append(f"chase {new_chases[0]}: {load_job(biz, new_chases[0])['state']}")
            return {"job": load_job(biz, job_id), "summary": summary}
        if intake["status"] == "needs_human":
            return {"job": job, "summary": summary}
    elif job["state"] == RECEIVED:
        raise HoldcoError(f"{job_id} is {RECEIVED}; the run must include an intake result.")
    for index, round_ in enumerate(rounds):
        escalation = round_.get("escalation")
        if escalation:
            job = escalate(biz, job_id, escalation["question"], PREPARER, escalation.get("key"),
                           escalation.get("context"))
            summary.append(f"preparer escalated: {escalation['question']}")
            break
        if index in drafts:
            record_draft(ws, biz, job_id, drafts[index])
        review = round_.get("review")
        if not review:
            summary.append("draft recorded; review pending")
            break
        job = record_review(ws, biz, job_id, {**review, "draft_version": load_job(biz, job_id)["drafts"][-1]["version"]})
        summary.append(f"v{job['drafts'][-1]['version']}: {job['reviews'][-1]['verdict']}")
        if job["state"] != BLOCKED:
            break
    return {"job": load_job(biz, job_id), "summary": summary}


# ------------------------------------------------------ human-only steps


def answer(biz: Business, job_id: str, text: str, by: str, ctx: ExecutionContext,
           log_correction: bool = True) -> dict:
    require_human(ctx, biz, "answer", by)
    job = load_job(biz, job_id)
    if job["state"] != NEEDS_HUMAN:
        raise HoldcoError(f"{job_id} has no open question (state: {job['state']}).")
    if not text.strip():
        raise HoldcoError("An answer can't be empty.")
    question = next(q for q in reversed(job["questions"]) if q["answer"] is None)
    question.update(answer=text.strip(), answered_by=by, answered_at=now_iso())
    if question.get("key"):
        job["answers"][question["key"]] = text.strip()
    if log_correction and question["asked_by"] in AGENT_ROLES:
        corrections.log_correction(biz, {
            "job": job_id, "job_type": job["type"], "client": job["client"], "agent": question["asked_by"],
            "draft_version": len(job["drafts"]) or None, "kind": "escalation_answer",
            "category": "missing_information", "path": f"answers.{question.get('key') or 'question'}",
            "before": None, "after": text.strip(),
            "context": {"question": question["question"], **(question.get("context") or {})},
            "note": "", "by": by,
        })
    resume = job.get("resume_state") or RECEIVED
    _transition(job, resume, Actor("human", by), note=f"answered: {text.strip()}")
    job["resume_state"] = None
    save_job(biz, job)
    return job


def send_back(biz: Business, job_id: str, by: str, ctx: ExecutionContext, note: str, category: str) -> dict:
    """A person returns a draft to the preparer with a note. Logged as a correction."""
    require_human(ctx, biz, "send-back", by)
    corrections.require_category(category)
    job = load_job(biz, job_id)
    if job["state"] != AWAITING_APPROVAL:
        raise HoldcoError(f"Only drafts awaiting approval can be sent back ({job_id} is {job['state']}).")
    if not note.strip():
        raise HoldcoError("Say what needs to change (--note).")
    version = job["drafts"][-1]["version"]
    job["reviews"].append({"version": version, "verdict": "SENT_BACK", "score": None, "reviewer": by,
                           "findings": [{"severity": "blocker", "rule": "human", "location": "",
                                         "issue": note.strip(), "fix": note.strip()}],
                           "summary": note.strip(), "at": now_iso()})
    corrections.log_correction(biz, {
        "job": job_id, "job_type": job["type"], "client": job["client"], "agent": job["drafts"][-1]["author"],
        "draft_version": version, "kind": "send_back", "category": category, "path": "draft",
        "before": None, "after": None, "context": {}, "note": note.strip(), "by": by,
    })
    _transition(job, BLOCKED, Actor("human", by), note=f"sent back: {note.strip()}")
    save_job(biz, job)
    return job


def approve(ws: Workspace, biz: Business, job_id: str, by: str, ctx: ExecutionContext,
            final: dict | None = None, reasons: dict | None = None, default_reason: str | None = None,
            notes: dict | None = None, minutes: float | None = None, note: str | None = None,
            override_checks: str | None = None, passphrase: str | None = None) -> dict:
    """A named person approves the draft, optionally with edits, and signs the approval.

    Every edit becomes a correction. ``reasons`` maps a change path to one of
    factual_error / client_preference / missing_information / style;
    ``default_reason`` covers any change not listed. The approval is signed with a
    key derived from the approver's passphrase, so it can't be forged.
    """
    require_human(ctx, biz, "approve", by)
    job = load_job(biz, job_id)
    _require_real_job(job, "approved")
    if job["state"] != AWAITING_APPROVAL:
        raise HoldcoError(f"{job_id} is {job['state']}, not awaiting approval.")
    _require_assisted(biz, job, "approved")
    _verify_draft_integrity(biz, job)
    _verify_inputs(biz, job)
    draft = latest_draft(biz, job)
    kind = jobtypes.get(job["type"])
    final = kind.normalize(final if final is not None else draft)
    _validate(job, final)
    changes = pending_changes(job["type"], draft, final)
    # Machine checks run on exactly what will be approved, so a person's edit
    # cannot quietly break a blocker rule either. Overriding needs a reason.
    blockers = [f for f in _run_checks(ws, biz, job, final) if f["severity"] == "blocker"]
    if blockers and not override_checks:
        raise HoldcoError("The version you are approving fails blocker checks: "
                          + "; ".join(f"{f['rule']}: {f['issue']}" for f in blockers)
                          + " Fix it, or approve with --override-checks \"reason\".")
    reasons, notes = dict(reasons or {}), dict(notes or {})
    uncategorized = [c.path for c in changes if not (reasons.get(c.path) or default_reason)]
    if uncategorized:
        raise HoldcoError("Every edit needs a category. Uncategorized: " + ", ".join(uncategorized))
    for change in changes:
        corrections.require_category(reasons.get(change.path) or default_reason)
    key, key_record = keys.unlock(biz, by, passphrase)
    for change in changes:
        corrections.log_correction(biz, {
            "job": job_id, "job_type": job["type"], "client": job["client"], "agent": job["drafts"][-1]["author"],
            "draft_version": job["drafts"][-1]["version"], "kind": "edit",
            "category": reasons.get(change.path) or default_reason,
            "path": change.path, "before": change.before, "after": change.after, "context": change.context,
            "note": notes.get(change.path, ""), "by": by,
        })
    write_json(job_dir(biz, job_id) / "approved.json", final)
    approval = {
        "by": by, "at": now_iso(), "sha256": sha256_json(final), "draft_version": job["drafts"][-1]["version"],
        "edited": bool(changes), "changes": len(changes), "minutes": minutes, "method": ctx.method, "note": note,
        "overrode_checks": ({"reason": override_checks, "findings": blockers} if blockers else None),
        "key_id": key_record["key_id"],
    }
    approval["signature"] = keys.sign(key, keys.approval_payload(biz, job, approval))
    job["approval"] = approval
    _transition(job, APPROVED, Actor("human", by),
                note=f"approved with {len(changes)} edit(s)" if changes else "approved as drafted")
    save_job(biz, job)
    return job


def pending_changes(job_type: str, draft: dict, final: dict) -> list[Change]:
    """Edits a person made, ignoring totals that are recomputed from them."""
    kind = jobtypes.get(job_type)
    return [c for c in diff(kind.normalize(draft), kind.normalize(final))
            if not c.path.startswith(kind.derived_prefixes)]


def send(biz: Business, job_id: str, by: str, ctx: ExecutionContext, passphrase: str | None = None) -> dict:
    """Release exactly what was approved to the outbox, signed. Anything else is refused."""
    require_human(ctx, biz, "send", by)
    job = load_job(biz, job_id)
    _require_real_job(job, "sent")
    if job["state"] != APPROVED or not job.get("approval"):
        raise HoldcoError(f"{job_id} is {job['state']}: only approved work can be sent.")
    _require_assisted(biz, job, "sent")
    approval = job["approval"]
    if by != approval["by"]:
        raise HoldcoError(f"{approval['by']} approved {job_id}, so {approval['by']} releases it "
                          "(the same passphrase signs both).")
    key, _ = keys.unlock(biz, by, passphrase)
    if not keys.verify(key, keys.approval_payload(biz, job, approval), approval.get("signature")):
        raise HoldcoError(f"The approval on {job_id} is not signed with {by}'s key. Nothing was sent. "
                          "Treat this as an incident (runbook 06): something wrote an approval without the passphrase.")
    approved = read_json(job_dir(biz, job_id) / "approved.json")
    if sha256_json(approved) != approval["sha256"]:
        raise HoldcoError(
            f"approved.json for {job_id} changed after {approval['by']} approved it. "
            "Nothing was sent. Send it back and approve again."
        )
    outdir = biz.outbox_dir / job_id
    if outdir.exists():
        raise HoldcoError(f"outbox/{job_id}/ already exists. Nothing was sent; check it with `holdco outbox verify`.")
    outdir.mkdir(parents=True)
    (outdir / "message.md").write_text(jobtypes.render_message(approved), encoding="utf-8")
    write_json(outdir / "data.json", approved.get("data", {}))
    names = ["message.md", "data.json", *jobtypes.get(job["type"]).render_attachments(approved, outdir)]
    manifest = {"job": job_id, "business": biz.slug, "client": job["client"],
                "approved_by": approval["by"], "approved_at": approval["at"], "sha256": approval["sha256"],
                "approval_signature": approval["signature"], "sent_by": by, "sent_at": now_iso(),
                "files": keys.file_hashes(outdir, names), "key_id": approval["key_id"]}
    manifest["release_signature"] = keys.sign(key, keys.release_payload(manifest))
    write_json(outdir / "manifest.json", manifest)
    job["sent"] = {"by": by, "at": manifest["sent_at"], "outbox": f"outbox/{job_id}/", "sha256": manifest["sha256"]}
    _transition(job, SENT, Actor("human", by), note=f"released to outbox/{job_id}/ (signed)")
    save_job(biz, job)
    return job


def verify_outbox(biz: Business, by: str, ctx: ExecutionContext, passphrase: str | None) -> list[dict]:
    """Check every item a person released: valid signature, files unchanged, nothing extra.

    Run it before emailing anything from the outbox. An item that fails was not released
    by `holdco send` with this person's passphrase, or was changed afterwards.
    """
    require_human(ctx, biz, "outbox verify", by)
    key, _ = keys.unlock(biz, by, passphrase)
    results = []
    folders = sorted(p for p in biz.outbox_dir.iterdir() if p.is_dir()) if biz.outbox_dir.is_dir() else []
    for folder in folders:
        manifest_path = folder / "manifest.json"
        if not manifest_path.exists():
            results.append({"item": folder.name, "ok": False, "problems": ["no manifest: not released by holdco send"]})
            continue
        manifest = read_json(manifest_path)
        if manifest.get("sent_by") != by:
            results.append({"item": folder.name, "ok": None,
                            "problems": [f"released by {manifest.get('sent_by')}: they verify their own items"]})
            continue
        problems = []
        try:
            payload = keys.release_payload(manifest)
        except KeyError:
            payload = None
        if payload is None or not keys.verify(key, payload, manifest.get("release_signature")):
            problems.append("release signature does not verify")
        listed = manifest.get("files") or {}
        for name, digest in listed.items():
            path = folder / name
            if not path.exists():
                problems.append(f"{name} is missing")
            elif sha256_file(path) != digest:
                problems.append(f"{name} changed after release")
        extra = sorted(p.name for p in folder.iterdir() if p.is_file() and p.name not in listed and p.name != "manifest.json")
        problems.extend(f"{name} was not part of the release" for name in extra)
        results.append({"item": folder.name, "ok": not problems, "problems": problems})
    return results


def shadow_record(ws: Workspace, biz: Business, job_id: str, by: str, ctx: ExecutionContext,
                  human_version: dict, reasons: dict | None = None, default_reason: str | None = None,
                  notes: dict | None = None, minutes: float | None = None) -> dict:
    """Shadow mode: log how the agent draft differs from what a person did by hand.

    Nothing is approved or sent. Each difference becomes a correction (kind
    'shadow'), and the person's minutes become the manual baseline for the
    Monday numbers. This is how agents earn the right to go live (runbook 03).
    """
    require_human(ctx, biz, "shadow", by)
    job = load_job(biz, job_id)
    _require_real_job(job, "shadowed")
    if job["state"] not in (DRAFTED, BLOCKED, NEEDS_HUMAN, AWAITING_APPROVAL) or not job["drafts"]:
        raise HoldcoError(f"{job_id} has no agent draft to compare (state: {job['state']}).")
    _verify_draft_integrity(biz, job)
    _verify_inputs(biz, job)
    draft = latest_draft(biz, job)
    kind = jobtypes.get(job["type"])
    human_version = kind.normalize(human_version)
    _validate(job, human_version)
    changes = pending_changes(job["type"], draft, human_version)
    reasons, notes = dict(reasons or {}), dict(notes or {})
    uncategorized = [c.path for c in changes if not (reasons.get(c.path) or default_reason)]
    if uncategorized:
        raise HoldcoError("Every difference needs a category. Uncategorized: " + ", ".join(uncategorized))
    for change in changes:
        corrections.log_correction(biz, {
            "job": job_id, "job_type": job["type"], "client": job["client"], "agent": job["drafts"][-1]["author"],
            "draft_version": job["drafts"][-1]["version"], "kind": "shadow",
            "category": reasons.get(change.path) or default_reason, "path": change.path, "before": change.before,
            "after": change.after, "context": change.context, "note": notes.get(change.path, ""), "by": by,
        })
    write_json(job_dir(biz, job_id) / "human-version.json", human_version)
    job["shadow"] = {"by": by, "at": now_iso(), "minutes": minutes, "changes": len(changes),
                     "sha256": sha256_json(human_version),
                     "draft_version": job["drafts"][-1]["version"],
                     "review_verdict": job["reviews"][-1]["verdict"] if job["reviews"] else None}
    _transition(job, SHADOWED, Actor("human", by),
                note=f"shadow compare: {len(changes)} difference(s) from the person's version")
    save_job(biz, job)
    return job


def cancel(biz: Business, job_id: str, by: str, ctx: ExecutionContext, reason: str) -> dict:
    require_human(ctx, biz, "cancel", by)
    job = load_job(biz, job_id)
    _transition(job, CANCELLED, Actor("human", by), note=reason or "cancelled")
    save_job(biz, job)
    return job
