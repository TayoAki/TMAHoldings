"""When a job type has earned the move from shadow mode to assisted mode.

Shadow: agents draft in the background, people keep doing the work by hand, and
every difference is logged. Assisted: agents draft, a person approves and sends.

A job type graduates when the evidence says so (enough shadow jobs, few
differences, no recent factual errors) AND the GM agrees. The report gives the
evidence; ``set_rollout`` records the person's decision.
"""

from __future__ import annotations

from holdco import corrections, jobs
from holdco.config import Business, HoldcoError
from holdco.guard import ExecutionContext, require_human
from holdco.util import append_jsonl, now_iso, read_json, read_jsonl, write_json

DEFAULT_CRITERIA = {"min_jobs": 20, "max_diff_rate": 0.25, "max_factual_errors_last_10": 0}
MODES = (jobs.SHADOW, jobs.ASSISTED)


def last_change(biz: Business, job_type: str) -> str | None:
    """When this job type's mode last changed (for example a rollback after an incident)."""
    entries = [e for e in read_jsonl(biz.dir / "rollout-log.jsonl") if e["job_type"] == job_type]
    return entries[-1]["at"] if entries else None


def graduation_report(biz: Business, job_type: str, last: int = 20, criteria: dict | None = None) -> dict:
    """Evidence only counts from the latest mode change: after a rollback, graduation starts over."""
    criteria = {**DEFAULT_CRITERIA, **(biz.setting("graduation") or {}), **(criteria or {})}
    since = last_change(biz, job_type)
    window = max(last, int(criteria["min_jobs"]))  # a higher bar (min_jobs 30) needs a window that big
    shadowed = sorted((j for j in jobs.list_jobs(biz) if j["type"] == job_type and j.get("shadow")
                       and (since is None or j["shadow"]["at"] > since)),
                      key=lambda j: j["shadow"]["at"])[-window:]
    ids = {j["id"] for j in shadowed}
    factual_by_job: dict[str, int] = {}
    for entry in corrections.load_corrections(biz):
        if entry["job"] in ids and entry["kind"] == "shadow" and entry["category"] == "factual_error":
            factual_by_job[entry["job"]] = factual_by_job.get(entry["job"], 0) + 1
    with_diffs = [j for j in shadowed if j["shadow"]["changes"] > 0]
    last_10 = shadowed[-10:]
    factual_last_10 = sum(factual_by_job.get(j["id"], 0) for j in last_10)
    minutes = [j["shadow"]["minutes"] for j in shadowed if j["shadow"].get("minutes") is not None]
    diff_rate = len(with_diffs) / len(shadowed) if shadowed else None
    reasons = []
    if len(shadowed) < criteria["min_jobs"]:
        reasons.append(f"only {len(shadowed)} shadow job(s); need {criteria['min_jobs']}")
    if diff_rate is not None and diff_rate > criteria["max_diff_rate"]:
        reasons.append(f"{diff_rate:.0%} of shadow jobs differed from the person's version "
                       f"(max {criteria['max_diff_rate']:.0%})")
    if factual_last_10 > criteria["max_factual_errors_last_10"]:
        reasons.append(f"{factual_last_10} factual error(s) in the last 10 shadow jobs "
                       f"(max {criteria['max_factual_errors_last_10']})")
    return {
        "business": biz.slug, "job_type": job_type, "mode": jobs.rollout_mode(biz, job_type),
        "shadow_jobs": len(shadowed), "diff_rate": diff_rate, "factual_errors_last_10": factual_last_10,
        "manual_minutes_per_job": round(sum(minutes) / len(minutes), 1) if minutes else None,
        "criteria": criteria, "ready": not reasons and bool(shadowed), "blocking": reasons,
    }


def set_rollout(biz: Business, job_type: str, mode: str, by: str, ctx: ExecutionContext, reason: str) -> dict:
    """A person (normally the holdco owner with the GM) decides a job type's mode."""
    require_human(ctx, biz, "rollout", by)
    if mode not in MODES:
        raise HoldcoError(f"Mode must be one of {', '.join(MODES)}.")
    if not reason.strip():
        raise HoldcoError("Say why (for example: 'graduation report ready; GM agrees').")
    path = biz.dir / "business.json"
    config = read_json(path)
    previous = (config.get("rollout") or {}).get(job_type, jobs.SHADOW)
    config.setdefault("rollout", {})[job_type] = mode
    write_json(path, config)
    entry = {"at": now_iso(), "job_type": job_type, "from": previous, "to": mode, "by": by, "reason": reason.strip()}
    append_jsonl(biz.dir / "rollout-log.jsonl", entry)
    biz.config = config
    return entry
