"""The corrections log and the weekly review that turns it into rules.

Every time a person changes an agent's work, answers an agent's question,
sends a draft back, or (in shadow mode) does the job differently from the
agent, one line lands in businesses/<biz>/corrections-log.jsonl
with one of four categories:

    factual_error        the agent got something wrong
    client_preference    right in general, wrong for this client
    missing_information  the agent could not have known
    style                wording, tone, format

The weekly review groups corrections by what was changed. Anything that was
fixed in two or more separate jobs becomes a proposed rule. A person accepts
or rejects each proposal; accepting writes the rule and turns the source jobs
into regression tests (original input + accepted output).
"""

from __future__ import annotations

import datetime as dt
import json
import re
from collections import Counter, defaultdict

from holdco.config import Business, HoldcoError, Workspace
from holdco.guard import ExecutionContext, require_human
from holdco.rules import KNOWN_CHECK_TYPES, RuleSet, append_rule, next_rule_id, parse_rules, render_rule
from holdco.util import (append_jsonl, next_id, now, now_iso, parse_date, read_csv, read_json, read_jsonl,
                         write_json)

CATEGORIES = ("factual_error", "client_preference", "missing_information", "style")
CATEGORY_KEYS = {"f": "factual_error", "c": "client_preference", "m": "missing_information", "s": "style"}
NOISE_PREFIXES = ("POS ", "DEBIT ", "PURCHASE ", "CHECKCARD ", "ACH ", "ONLINE TRANSFER TO ", "TRANSFER TO ",
                  "ONLINE PAYMENT TO ", "PAYMENT TO ", "RECURRING ", "SQ *", "TST* ")
TXN_CATEGORY_PATH = re.compile(r"^data\.transactions\[[^\]]+\]\.category$")


def require_category(category: str | None) -> str:
    resolved = CATEGORY_KEYS.get((category or "").lower(), category)
    if resolved not in CATEGORIES:
        raise HoldcoError(f"Category must be one of {', '.join(CATEGORIES)} (got {category!r}).")
    return resolved


def log_correction(biz: Business, record: dict) -> dict:
    existing = read_jsonl(biz.corrections_log)
    entry = {"id": next_id("C", (e["id"] for e in existing)), "at": now_iso(), "business": biz.slug, **record}
    entry["category"] = require_category(entry.get("category"))
    append_jsonl(biz.corrections_log, entry)
    return entry


def load_corrections(biz: Business, since: dt.date | None = None, until: dt.date | None = None) -> list[dict]:
    out = []
    for entry in read_jsonl(biz.corrections_log):
        day = parse_date(entry["at"])
        if (since is None or day >= since) and (until is None or day <= until):
            out.append(entry)
    return out


# -------------------------------------------------------------- grouping


def vendor_key(description: str) -> str:
    """'HOME DEPOT #4410 SALEM' -> 'HOME DEPOT'; 'ONLINE TRANSFER TO J SMITH' -> 'J SMITH'."""
    text = re.sub(r"\s+", " ", description.upper()).strip()
    for prefix in NOISE_PREFIXES:
        if text.startswith(prefix):
            text = text[len(prefix):]
    words = []
    for token in text.split(" "):
        if re.search(r"[\d#*]", token):
            break
        words.append(token)
        if len(words) == 2:
            break
    return " ".join(words) or text


def signature(entry: dict) -> tuple | None:
    """What makes two corrections 'the same fix'. None = free text for the curator agent."""
    context = entry.get("context") or {}
    job_type, client = entry.get("job_type"), entry.get("client")
    if entry["kind"] in ("edit", "shadow", "escalation_answer") and context.get("description") and (
        entry["kind"] == "escalation_answer" or TXN_CATEGORY_PATH.match(entry["path"])
    ):
        return ("txn_category", job_type, client, vendor_key(context["description"]), entry["after"])
    if entry["kind"] not in ("edit", "shadow"):
        return None
    if "#L" in entry["path"]:
        before, after = _norm(entry["before"]), _norm(entry["after"])
        return ("text", job_type, entry["category"], before, after)
    path = re.sub(r"\[[^\]]+\]", "[*]", entry["path"])
    return ("field", job_type, client, path, json.dumps(entry["before"], sort_keys=True),
            json.dumps(entry["after"], sort_keys=True))


def _norm(value) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip().lower()


def _client_name(biz: Business, client: str | None) -> str:
    for row in read_csv(biz.clients_csv):
        if row.get("id") == client:
            return re.sub(r"\s*\(fictional\)\s*", "", row.get("name", client)).strip()
    return client or "all clients"


def _draft_rule(biz: Business, sig: tuple, entries: list[dict]) -> dict:
    kind, job_type = sig[0], sig[1]
    categories = Counter(e["category"] for e in entries)
    jobs = sorted({e["job"] for e in entries})
    people = sorted({e["by"] for e in entries})
    why = (f"Fixed {len(entries)} time(s) across {len(jobs)} job(s) by {', '.join(people)} "
           f"({', '.join(f'{k}: {v}' for k, v in categories.items())}). "
           f"Evidence: {', '.join(e['id'] for e in entries)}.")
    if kind == "txn_category":
        _, _, client, vendor, category = sig
        name = _client_name(biz, client)
        return {
            "title": f"{name}: {vendor.title()} transactions are {category}",
            "rule_text": f'For {name}, categorize any transaction whose description contains "{vendor}" '
                         f'as "{category}".',
            "scope": f"client:{client}" if client else "all",
            "applies_to": job_type,
            "check": {"type": "vendor_category", "match": vendor, "category": category},
            "why": why,
        }
    if kind == "text":
        _, _, _, before, after = sig
        check = {"type": "no_phrases", "phrases": [before]} if before and len(before) <= 60 else None
        text = (f'In client messages, write "{after}" instead of "{before}".' if after
                else f'Do not write "{before}" in client messages.')
        return {"title": f"Style: {'replace' if after else 'drop'} “{before[:40]}”", "rule_text": text,
                "scope": "all", "applies_to": job_type, "check": check, "why": why}
    _, _, client, path, before, after = sig
    return {
        "title": f"{job_type}: {path} should be {after}",
        "rule_text": f"When preparing {job_type} for {_client_name(biz, client)}, {path} should be {after} "
                     f"(agents keep producing {before}). Reword this rule in plain English before accepting.",
        "scope": f"client:{client}" if client else "all",
        "applies_to": job_type,
        "check": None,
        "why": why,
    }


def _existing_rule_for(rules: RuleSet, sig: tuple) -> str | None:
    if sig[0] != "txn_category":
        return None
    _, job_type, client, vendor, category = sig
    for rule in rules.checks(job_type, client, "vendor_category"):
        if rule.check["match"].upper() in vendor or vendor in rule.check["match"].upper():
            if rule.check["category"] == category:
                return rule.id
    return None


def list_proposals(biz: Business, status: str | None = None) -> list[dict]:
    if not biz.proposals_dir.is_dir():
        return []
    out = [read_json(p) for p in sorted(biz.proposals_dir.glob("P-*.json"))]
    return [p for p in out if status is None or p["status"] == status]


def review(ws: Workspace, biz: Business, as_of: dt.date | None = None, days: int = 7,
           lookback_days: int = 90, min_jobs: int = 2, write: bool = True) -> dict:
    """The Wednesday review.

    Looks at this week's corrections (``days``) and, for each kind of fix, how
    many separate jobs needed it in the last ``lookback_days``. Anything fixed
    in ``min_jobs`` or more jobs becomes a proposed rule.
    """
    as_of = as_of or now().date()
    week_start = as_of - dt.timedelta(days=days - 1)
    this_week = load_corrections(biz, week_start, as_of)
    history = load_corrections(biz, as_of - dt.timedelta(days=lookback_days - 1), as_of)
    rules = RuleSet.for_business(ws, biz)
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for entry in history:
        sig = signature(entry)
        if sig:
            groups[sig].append(entry)
    fresh_sigs = {signature(e) for e in this_week} - {None}
    known = {tuple(p["signature"]): p for p in list_proposals(biz)}
    report = {
        "business": biz.slug, "as_of": as_of.isoformat(), "week_start": week_start.isoformat(),
        "this_week": len(this_week),
        "by_category": dict(Counter(e["category"] for e in this_week)),
        "by_agent": dict(Counter(e.get("agent") or "unknown" for e in this_week)),
        "by_kind": dict(Counter(e["kind"] for e in this_week)),
        "new_proposals": [], "already_proposed": [], "rule_not_followed": [], "watch": [],
        "free_text": [e for e in this_week if signature(e) is None],
    }
    taken = [p["id"] for p in list_proposals(biz)]
    for sig in sorted(fresh_sigs, key=str):
        entries = groups[sig]
        jobs = sorted({e["job"] for e in entries})
        if len(jobs) < min_jobs:
            report["watch"].append({"signature": list(sig), "jobs": jobs, "corrections": [e["id"] for e in entries]})
            continue
        if sig in known:
            report["already_proposed"].append({"proposal": known[sig]["id"], "status": known[sig]["status"]})
            continue
        existing = _existing_rule_for(rules, sig)
        if existing:
            report["rule_not_followed"].append({"rule": existing, "corrections": [e["id"] for e in entries],
                                                "action": "The rule exists but agents did not apply it: "
                                                          "fix the agent file or the rule wording, then run eval."})
            continue
        proposal = {
            "id": next_id("P", taken), "status": "proposed", "created_at": now_iso(), "signature": list(sig),
            "kind": sig[0], "job_type": sig[1], "client": sig[2] if sig[0] != "text" else None,
            **_draft_rule(biz, sig, entries),
            "evidence": [e["id"] for e in entries], "evidence_jobs": jobs,
            "categories": dict(Counter(e["category"] for e in entries)),
        }
        taken.append(proposal["id"])
        if write:
            write_json(biz.proposals_dir / f"{proposal['id']}.json", proposal)
        report["new_proposals"].append(proposal)
    return report


def create_proposal(ws: Workspace, biz: Business, draft: dict, source: str = "rules-curator agent") -> dict:
    """Record a proposal written by the rules-curator agent (patterns the exact grouping missed).

    Agents may propose; only a person can accept (``rules accept``).
    """
    from holdco import jobs  # local import: jobs depends on this module

    missing = [k for k in ("title", "applies_to", "scope", "rule_text", "why") if not str(draft.get(k, "")).strip()]
    if missing:
        raise HoldcoError(f"Proposal is missing: {', '.join(missing)}.")
    check = draft.get("check")
    if check is not None and (not isinstance(check, dict) or check.get("type") not in KNOWN_CHECK_TYPES):
        raise HoldcoError(f"Unknown check {check!r}. Use null or one of: {', '.join(sorted(KNOWN_CHECK_TYPES))}.")
    log = read_jsonl(biz.corrections_log)
    evidence = list(draft.get("evidence") or [])
    by_id = {entry["id"]: entry for entry in log}
    unknown = [e for e in evidence if e not in by_id]
    if unknown or not evidence:
        raise HoldcoError(f"Evidence must cite logged corrections (unknown or none: {unknown or 'none given'}).")
    if len({by_id[e]["job"] for e in evidence}) < 2:
        raise HoldcoError("A rule needs the same fix in at least two separate jobs. Once is an anecdote: "
                          "list a single factual error as an agent-file fix instead.")
    evidence_jobs = list(draft.get("golden_candidates") or draft.get("evidence_jobs") or [])
    for job_id in evidence_jobs:
        job = jobs.load_job(biz, job_id)
        if job.get("eval_case") or not (job.get("approval") or job.get("shadow")):
            raise HoldcoError(f"{job_id} was never approved or shadow-compared, so it cannot become a golden case.")
    existing = list_proposals(biz)
    title = draft["title"].strip()
    if any(p["title"].lower() == title.lower() and p["status"] == "proposed" for p in existing):
        raise HoldcoError(f"An open proposal titled {title!r} already exists.")
    scope = draft["scope"].strip()
    proposal = {
        "id": next_id("P", (p["id"] for p in existing)), "status": "proposed", "created_at": now_iso(),
        "signature": ["curated", title.lower()], "kind": "curated", "source": source,
        "job_type": draft["applies_to"].strip(), "client": scope.split(":", 1)[1] if scope.startswith("client:") else None,
        "title": title, "rule_text": draft["rule_text"].strip(), "scope": scope,
        "applies_to": draft["applies_to"].strip(), "check": check, "why": draft["why"].strip(),
        "evidence": evidence, "evidence_jobs": evidence_jobs,
        "categories": dict(Counter(e["category"] for e in log if e["id"] in evidence)),
    }
    write_json(biz.proposals_dir / f"{proposal['id']}.json", proposal)
    return proposal


def accept_proposal(ws: Workspace, biz: Business, proposal_id: str, by: str, ctx: ExecutionContext,
                    title: str | None = None, rule_text: str | None = None) -> dict:
    """A person turns a proposal into a rule and its evidence jobs into regression tests."""
    from holdco import golden  # local import: golden depends on jobs, which depends on this module

    require_human(ctx, biz, "rules accept", by)
    path = biz.proposals_dir / f"{proposal_id}.json"
    if not path.exists():
        raise HoldcoError(f"No proposal {proposal_id} in {biz.slug}.")
    proposal = read_json(path)
    if proposal["status"] != "proposed":
        raise HoldcoError(f"{proposal_id} is already {proposal['status']}.")
    if proposal.get("check") is None and not rule_text and "Reword" in proposal["rule_text"]:
        raise HoldcoError(f"{proposal_id} needs plain-English wording first: pass --text \"...\".")
    # Check everything before writing anything, so a failure never leaves a half-accepted rule.
    for job_id in proposal["evidence_jobs"]:
        golden.accepted_output(biz, job_id)
    rule_id = next_rule_id(biz)
    fields = {
        "Applies to": proposal["applies_to"], "Scope": proposal["scope"],
        "Rule": rule_text or proposal["rule_text"], "Why": proposal["why"],
        "Source": f"weekly corrections review, proposal {proposal_id}",
        "Added": f"{now_iso()[:10]} by {by}",
    }
    markdown = render_rule(rule_id, title or proposal["title"], fields, proposal.get("check"))
    parse_rules(markdown, "business", str(biz.rules_file))
    append_rule(biz, markdown)
    RuleSet.for_business(ws, biz)  # the whole rule set still loads with the new rule in it
    cases = [golden.create_case_from_job(ws, biz, job_id, [rule_id]) for job_id in proposal["evidence_jobs"]]
    proposal.update(status="accepted", rule_id=rule_id, golden_cases=cases, decided_by=by, decided_at=now_iso())
    write_json(path, proposal)
    return proposal


def reject_proposal(biz: Business, proposal_id: str, by: str, ctx: ExecutionContext, reason: str) -> dict:
    require_human(ctx, biz, "rules reject", by)
    path = biz.proposals_dir / f"{proposal_id}.json"
    if not path.exists():
        raise HoldcoError(f"No proposal {proposal_id} in {biz.slug}.")
    proposal = read_json(path)
    if proposal["status"] != "proposed":
        raise HoldcoError(f"{proposal_id} is already {proposal['status']}.")
    proposal.update(status="rejected", reason=reason, decided_by=by, decided_at=now_iso())
    write_json(path, proposal)
    return proposal
