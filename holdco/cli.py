"""Command line for the holdco.

Agents may run anything here except the human-only commands (approve,
send-back, send, answer, cancel, shadow, rollout, rules accept, rules reject),
which refuse to run inside an agent session or without an interactive terminal.

    python3 -m holdco --help
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

from holdco import corrections, deals, golden, jobs, jobtypes, metrics, rollout
from holdco.checks import run_checks
from holdco.config import TEMPLATE_SLUG, HoldcoError, Workspace, find_root
from holdco.diffing import coerce_value, set_path
from holdco.guard import ExecutionContext, HumanOnlyError, require_human
from holdco.rules import RuleSet
from holdco.runners import get_runner
from holdco.util import money, parse_date, pct, read_json, slugify, write_json

REPO_ROOT = Path(__file__).resolve().parent.parent


def _load_json_arg(value: str):
    if value == "-":
        return json.load(sys.stdin)
    return read_json(value)


def _print_json(data) -> None:
    print(json.dumps(data, indent=2, ensure_ascii=False, default=str))


def _ws(args) -> Workspace:
    return Workspace(Path(args.root).resolve() if args.root else find_root())


# ------------------------------------------------------------------ setup


def cmd_new_business(args) -> int:
    ws = _ws(args)
    slug = slugify(args.slug)
    target = ws.businesses_dir / slug
    template = ws.businesses_dir / TEMPLATE_SLUG
    if target.exists():
        raise HoldcoError(f"{target} already exists.")
    if not template.is_dir():
        raise HoldcoError(f"No template at {template}.")
    shutil.copytree(template, target)
    config = read_json(target / "business.json")
    config.update(name=args.name, industry=args.industry, gm=args.gm, approvers=[args.gm],
                  rule_prefix="R-" + slug.upper().replace("-", "")[:8], demo=False)
    write_json(target / "business.json", config)
    print(f"Created {target}. Next: fill in README.md, clients.md/csv, people.md and rules.md "
          f"(runbook: shared/runbooks/01-day-one-takeover.md).")
    if ws.industry_rules_file(args.industry) and not ws.industry_rules_file(args.industry).exists():
        print(f"Note: no industry rules yet at {ws.industry_rules_file(args.industry)}; copy bookkeeping.md as a start.")
    return 0


def cmd_sandbox(args) -> int:
    target = Path(args.path).resolve()
    if target.exists() and any(target.iterdir()):
        raise HoldcoError(f"{target} is not empty.")
    target.mkdir(parents=True, exist_ok=True)
    shutil.copytree(REPO_ROOT / "shared", target / "shared")
    shutil.copytree(REPO_ROOT / "businesses" / "demo-bookkeeping", target / "businesses" / "demo-bookkeeping")
    shutil.copytree(REPO_ROOT / "thesis", target / "thesis")
    print(f"Sandbox ready at {target}. Use --root {args.path} (or HOLDCO_ROOT={args.path}) with any command.")
    return 0


def cmd_demo(args) -> int:
    from holdco.demo import run_demo

    return run_demo(REPO_ROOT, Path(args.workspace).resolve() if args.workspace else None, args.quiet)


def cmd_status(args) -> int:
    ws = _ws(args)
    businesses = ws.list_businesses()
    if not businesses:
        print(f"No businesses under {ws.businesses_dir}.")
        return 0
    for biz in businesses:
        all_jobs = jobs.list_jobs(biz)
        counts: dict[str, int] = {}
        for job in all_jobs:
            counts[job["state"]] = counts.get(job["state"], 0) + 1
        pending = corrections.list_proposals(biz, "proposed")
        print(f"{biz.name} [{biz.slug}]{' (demo)' if biz.is_demo else ''} · GM {biz.gm or '-'}")
        print("  jobs: " + (", ".join(f"{k} {v}" for k, v in sorted(counts.items())) or "none"))
        print(f"  proposed rules waiting for a decision: {len(pending)}")
    return cmd_queue(args)


def cmd_queue(args) -> int:
    ws = _ws(args)
    rows = []
    for biz in ws.list_businesses():
        for job in jobs.list_jobs(biz):
            if job["state"] == jobs.AWAITING_APPROVAL:
                review = job["reviews"][-1] if job["reviews"] else {}
                rows.append(f"  APPROVE  {biz.slug} {job['id']}  (v{job['drafts'][-1]['version']}, "
                            f"review {review.get('verdict')} {review.get('score')})")
            elif job["state"] == jobs.NEEDS_HUMAN:
                question = next((q for q in reversed(job["questions"]) if q["answer"] is None), {})
                rows.append(f"  ANSWER   {biz.slug} {job['id']}  {question.get('question', '')[:90]}")
            elif job["state"] == jobs.APPROVED:
                rows.append(f"  SEND     {biz.slug} {job['id']}  (approved by {job['approval']['by']})")
    print("Waiting on a person:" if rows else "Nothing is waiting on a person.")
    print("\n".join(rows))
    return 0


# ------------------------------------------------------------------- jobs


def cmd_job_new(args) -> int:
    ws = _ws(args)
    biz = ws.business(args.business)
    job = jobs.create_job(ws, biz, args.type, args.client, Path(args.inputs) if args.inputs else None,
                          period=args.period, job_id=args.id)
    print(f"Created {job['id']} ({job['type']} for {job['client']}) in state {job['state']}.")
    return 0


def cmd_job_add_inputs(args) -> int:
    ws = _ws(args)
    job = jobs.add_inputs(ws.business(args.business), args.job, Path(args.inputs))
    print(f"{job['id']} is now {job['state']}.")
    return 0


def cmd_job_list(args) -> int:
    ws = _ws(args)
    businesses = [ws.business(args.business)] if args.business else ws.list_businesses()
    out = []
    for biz in businesses:
        for job in jobs.list_jobs(biz, args.state, include_eval=args.all):
            out.append({"business": biz.slug, "id": job["id"], "type": job["type"], "client": job["client"],
                        "state": job["state"], "drafts": len(job["drafts"])})
    if args.json:
        _print_json(out)
    else:
        for row in out:
            print(f"{row['business']:22} {row['id']:40} {row['type']:16} {row['state']:18} drafts {row['drafts']}")
        if not out:
            print("No jobs.")
    return 0


def cmd_job_show(args) -> int:
    ws = _ws(args)
    biz = ws.business(args.business)
    job = jobs.load_job(biz, args.job)
    if args.json:
        _print_json(job)
        return 0
    print(f"{job['id']} · {job['type']} · client {job['client']} · state {job['state'].upper()}")
    for entry in job["history"][-6:]:
        print(f"  {entry['at']}  {entry['from'] or '-'} -> {entry['to']}  [{entry['actor']}] {entry.get('note', '')}")
    open_q = [q for q in job["questions"] if q["answer"] is None]
    for q in open_q:
        print(f"\n  OPEN QUESTION (from {q['asked_by']}): {q['question']}")
        print(f"  Answer with: python3 -m holdco answer {biz.slug} {job['id']} --by \"<you>\" --text \"...\"")
    if job["drafts"]:
        draft = jobs.latest_draft(biz, job)
        print(f"\n--- Draft v{job['drafts'][-1]['version']} by {job['drafts'][-1]['author']} ---")
        print(jobtypes.render_message(draft))
        for txn in draft.get("data", {}).get("transactions", []) or []:
            print(f"  {txn['id']}  {txn['date']}  {txn['description'][:28]:28} {money(float(txn['amount'])):>12}  "
                  f"{txn['category']}")
        for excluded in draft.get("data", {}).get("excluded", []) or []:
            print(f"  EXCLUDED {excluded['id']}: {excluded['reason']}")
    if job["reviews"]:
        review = job["reviews"][-1]
        print(f"\n--- Review of v{review['version']}: {review['verdict']} (score {review['score']}) ---")
        for f in review["findings"]:
            print(f"  [{f.get('severity')}] {f.get('rule')}: {f.get('issue')}  Fix: {f.get('fix')}")
    if job["state"] == jobs.AWAITING_APPROVAL:
        print(f"\nTo approve: python3 -m holdco approve {biz.slug} {job['id']} --by \"<you>\" --minutes <n> "
              "[--set 'data.transactions[T-1].category=...' --reason client_preference]")
    return 0


def cmd_job_export(args) -> int:
    ws = _ws(args)
    biz = ws.business(args.business)
    write_json(args.to, jobs.latest_draft(biz, jobs.load_job(biz, args.job)))
    print(f"Wrote the latest draft to {args.to}. Edit it, then approve with --final {args.to}.")
    return 0


# ------------------------------------------------------------ agent steps


def cmd_run(args) -> int:
    ws = _ws(args)
    biz = ws.business(args.business)
    result = get_runner(ws, biz, args.runner).process(args.job)
    for line in result["steps"]:
        print(f"- {line}")
    print(f"{args.job} is now {result['job']['state']}.")
    return 0


def cmd_record(args) -> int:
    ws = _ws(args)
    biz = ws.business(args.business)
    if args.what == "escalation":
        actor = {"intake": jobs.INTAKE, "preparer": jobs.PREPARER, "reviewer": jobs.REVIEWER}[args.agent]
        job = jobs.escalate(biz, args.job, args.question, actor, args.key)
    else:
        payload = _load_json_arg(args.file)
        fn = {"intake": jobs.record_intake, "draft": jobs.record_draft, "review": jobs.record_review}[args.what]
        job = fn(ws, biz, args.job, payload)
    print(f"Recorded {args.what}. {job['id']} is now {job['state']}.")
    return 0


def cmd_record_run(args) -> int:
    ws = _ws(args)
    result = jobs.record_run(ws, ws.business(args.business), args.job, _load_json_arg(args.file))
    for line in result["summary"]:
        print(f"- {line}")
    print(f"{args.job} is now {result['job']['state']}.")
    return 0


def cmd_check(args) -> int:
    ws = _ws(args)
    biz = ws.business(args.business)
    job = jobs.load_job(biz, args.job)
    findings = run_checks(ws, biz, job["type"], job["client"], jobs.latest_draft(biz, job),
                          jobs.job_dir(biz, args.job) / "input", job.get("answers"))
    if args.json:
        _print_json(findings)
    elif not findings:
        print("All machine checks passed.")
    else:
        for f in findings:
            print(f"[{f['severity']}] {f['rule']}: {f['issue']}  Fix: {f['fix']}")
    return 1 if any(f["severity"] == "blocker" for f in findings) else 0


# ------------------------------------------------------------ human steps


def _confirm(prompt: str, expected: str) -> None:
    typed = input(f"{prompt} Type '{expected}' to confirm: ").strip()
    if typed != expected:
        raise HoldcoError("Not confirmed. Nothing changed.")


def cmd_approve(args) -> int:
    ws = _ws(args)
    biz = ws.business(args.business)
    ctx = ExecutionContext.detect()
    require_human(ctx, biz, "approve", args.by)
    job = jobs.load_job(biz, args.job)
    if job["state"] != jobs.AWAITING_APPROVAL:
        raise HoldcoError(f"{args.job} is {job['state']}, not awaiting approval.")
    jobs._require_assisted(biz, job, "approved")
    draft = jobs.latest_draft(biz, job)
    final = _edits_from_args(args, draft)
    changes = jobs.pending_changes(job["type"], draft, final)
    default_reason = corrections.require_category(args.reason) if args.reason else None
    if changes:
        print(f"{len(changes)} change(s) vs the agent's draft v{job['drafts'][-1]['version']}:")
    reasons, notes = _categorize(changes, default_reason)
    review = job["reviews"][-1] if job["reviews"] else {}
    _confirm(f"Approve {args.job} for {job['client']} (review {review.get('verdict')}, score {review.get('score')})"
             f" as {args.by}?", "approve")
    job = jobs.approve(ws, biz, args.job, args.by, ctx, final=final, reasons=reasons, default_reason=default_reason,
                       notes=notes or None, minutes=args.minutes, note=args.note, override_checks=args.override_checks)
    print(f"Approved by {args.by} ({job['approval']['changes']} edit(s) logged). "
          f"Send it with: python3 -m holdco send {biz.slug} {args.job} --by \"{args.by}\"")
    return 0


def _edits_from_args(args, draft: dict) -> dict:
    final = _load_json_arg(args.final) if args.final else draft
    if getattr(args, "human_csv", None):
        from holdco.util import read_csv

        for row in read_csv(args.human_csv):
            final = set_path(final, f"data.transactions[{row['id']}].category", row["category"])
    for item in args.set or []:
        if "=" not in item:
            raise HoldcoError(f"--set needs PATH=VALUE (got {item!r}).")
        path, value = item.split("=", 1)
        final = set_path(final, path.strip(), coerce_value(value))
    return final


def _categorize(changes, default_reason) -> tuple[dict, dict]:
    reasons, notes = {}, {}
    for i, change in enumerate(changes, 1):
        print(f"  {i}. {change.describe()}")
        if not default_reason:
            key = input("     Why? [f]actual error / [c]lient preference / [m]issing info / [s]tyle: ").strip()
            reasons[change.path] = corrections.require_category(key)
            notes[change.path] = input("     Note (optional): ").strip()
    return reasons, notes


def cmd_shadow(args) -> int:
    ws = _ws(args)
    biz = ws.business(args.business)
    ctx = ExecutionContext.detect()
    require_human(ctx, biz, "shadow", args.by)
    job = jobs.load_job(biz, args.job)
    draft = jobs.latest_draft(biz, job)
    human_version = _edits_from_args(args, draft)
    changes = jobs.pending_changes(job["type"], draft, human_version)
    default_reason = corrections.require_category(args.reason) if args.reason else None
    print(f"{len(changes)} difference(s) between the agent's draft and what you did:")
    reasons, notes = _categorize(changes, default_reason)
    job = jobs.shadow_record(ws, biz, args.job, args.by, ctx, human_version, reasons=reasons,
                             default_reason=default_reason, notes=notes or None, minutes=args.minutes)
    print(f"Logged {job['shadow']['changes']} difference(s). Nothing was sent. "
          f"Graduation: python3 -m holdco graduation {biz.slug} {job['type']}")
    return 0


def cmd_graduation(args) -> int:
    ws = _ws(args)
    report = rollout.graduation_report(ws.business(args.business), args.job_type, last=args.last)
    if args.json:
        _print_json(report)
        return 0
    print(f"{report['job_type']} at {report['business']}: currently {report['mode'].upper()}")
    print(f"  shadow jobs: {report['shadow_jobs']} · differed from the person: {pct(report['diff_rate'], 0)} · "
          f"factual errors in last 10: {report['factual_errors_last_10']} · manual baseline: "
          f"{report['manual_minutes_per_job'] or 'n/a'} min/job")
    if report["ready"]:
        print(f"  READY: evidence supports assisted mode. If the GM agrees: python3 -m holdco rollout "
              f"{report['business']} {report['job_type']} assisted --by \"<you>\" --reason \"...\"")
    else:
        print("  NOT READY: " + "; ".join(report["blocking"]))
    return 0


def cmd_rollout(args) -> int:
    ws = _ws(args)
    biz = ws.business(args.business)
    ctx = ExecutionContext.detect()
    require_human(ctx, biz, "rollout", args.by)
    _confirm(f"Set {args.job_type} at {biz.slug} to {args.mode}?", args.mode)
    entry = rollout.set_rollout(biz, args.job_type, args.mode, args.by, ctx, args.reason)
    print(f"{args.job_type}: {entry['from']} -> {entry['to']} (logged in rollout-log.jsonl).")
    return 0


def cmd_send_back(args) -> int:
    ws = _ws(args)
    biz = ws.business(args.business)
    job = jobs.send_back(biz, args.job, args.by, ExecutionContext.detect(), args.note, args.reason)
    print(f"{job['id']} sent back to the preparer ({job['state']}).")
    return 0


def cmd_send(args) -> int:
    ws = _ws(args)
    biz = ws.business(args.business)
    ctx = ExecutionContext.detect()
    require_human(ctx, biz, "send", args.by)
    job = jobs.load_job(biz, args.job)
    _confirm(f"Release {args.job} to {job['client']}'s outbox as {args.by}?", "send")
    job = jobs.send(biz, args.job, args.by, ctx)
    print(f"Released to {biz.dir / job['sent']['outbox']}. Deliver it from your normal email or portal.")
    return 0


def cmd_answer(args) -> int:
    ws = _ws(args)
    job = jobs.answer(ws.business(args.business), args.job, args.text, args.by, ExecutionContext.detect())
    print(f"Answer recorded. {job['id']} is back to {job['state']}; run the agents again.")
    return 0


def cmd_cancel(args) -> int:
    ws = _ws(args)
    job = jobs.cancel(ws.business(args.business), args.job, args.by, ExecutionContext.detect(), args.reason)
    print(f"{job['id']} cancelled.")
    return 0


# ------------------------------------------------------ improvement loop


def cmd_corrections_list(args) -> int:
    ws = _ws(args)
    entries = corrections.load_corrections(ws.business(args.business),
                                           parse_date(args.since) if args.since else None)
    if args.json:
        _print_json(entries)
        return 0
    for e in entries:
        print(f"{e['id']} {e['at'][:10]} {e['job']:32} {e['category']:20} {e['path']}: "
              f"{json.dumps(e['before'])} -> {json.dumps(e['after'])} ({e['by']})")
    if not entries:
        print("No corrections logged.")
    return 0


def cmd_corrections_review(args) -> int:
    ws = _ws(args)
    biz = ws.business(args.business)
    report = corrections.review(ws, biz, as_of=parse_date(args.as_of) if args.as_of else None, days=args.days,
                                lookback_days=args.lookback, min_jobs=args.min_jobs, write=not args.dry_run)
    if args.json:
        _print_json(report)
        return 0
    print(f"Corrections review · {biz.name} · week {report['week_start']} to {report['as_of']}")
    print(f"  {report['this_week']} correction(s): {report['by_category'] or 'none'} · by agent {report['by_agent'] or '-'}")
    for p in report["new_proposals"]:
        print(f"\n  NEW {p['id']}: {p['title']}\n    Rule: {p['rule_text']}\n    Why: {p['why']}")
        print(f"    Accept: python3 -m holdco rules accept {biz.slug} {p['id']} --by \"<you>\"")
    for item in report["rule_not_followed"]:
        print(f"\n  RULE NOT FOLLOWED {item['rule']}: {item['action']} ({', '.join(item['corrections'])})")
    for item in report["watch"]:
        print(f"  watch: {item['signature']} seen in {len(item['jobs'])} job(s)")
    if report["free_text"]:
        print(f"\n  {len(report['free_text'])} free-text correction(s) need a person or the rules-curator agent:")
        for e in report["free_text"]:
            print(f"    {e['id']} [{e['category']}] {e.get('note') or e['path']}")
    return 0


def cmd_rules_list(args) -> int:
    ws = _ws(args)
    biz = ws.business(args.business)
    rules = RuleSet.for_business(ws, biz)
    selected = rules.for_job(args.job_type, args.client) if args.job_type else rules.rules
    for rule in selected:
        flags = " [non-negotiable]" if rule.non_negotiable else ""
        check = f" check={rule.check['type']}" if rule.check else ""
        print(f"{rule.id:12} {rule.layer:8} {rule.scope:14} {rule.title}{flags}{check}")
    return 0


def cmd_rules_proposals(args) -> int:
    ws = _ws(args)
    for p in corrections.list_proposals(ws.business(args.business), args.status):
        print(f"{p['id']} [{p['status']}] {p['title']}  evidence: {', '.join(p['evidence'])}")
    return 0


def cmd_rules_propose(args) -> int:
    ws = _ws(args)
    proposal = corrections.create_proposal(ws, ws.business(args.business), _load_json_arg(args.file))
    print(f"Recorded {proposal['id']}: {proposal['title']}. A person decides with: "
          f"python3 -m holdco rules accept {args.business} {proposal['id']} --by \"<you>\"")
    return 0


def cmd_rules_accept(args) -> int:
    ws = _ws(args)
    biz = ws.business(args.business)
    ctx = ExecutionContext.detect()
    require_human(ctx, biz, "rules accept", args.by)
    _confirm(f"Add proposal {args.proposal} as a rule for {biz.slug}?", "accept")
    proposal = corrections.accept_proposal(ws, biz, args.proposal, args.by, ctx, args.title, args.text)
    print(f"Added {proposal['rule_id']} to {biz.rules_file}. Golden cases: {', '.join(proposal['golden_cases'])}. "
          f"Now run: python3 -m holdco eval {biz.slug}")
    return 0


def cmd_rules_reject(args) -> int:
    ws = _ws(args)
    corrections.reject_proposal(ws.business(args.business), args.proposal, args.by, ExecutionContext.detect(),
                                args.reason)
    print(f"{args.proposal} rejected.")
    return 0


def cmd_golden_list(args) -> int:
    ws = _ws(args)
    cases = golden.list_cases(ws.business(args.business))
    if args.json:
        _print_json(cases)
        return 0
    if not cases:
        print("No golden cases yet. They are created when a person accepts a proposed rule.")
    for case in cases:
        print(f"{case['id']} {case['job_type']:14} {case['client']:10} from {case['source_job']} "
              f"rules {', '.join(case['rule_ids'])}")
    return 0


def cmd_golden_materialize(args) -> int:
    ws = _ws(args)
    job = golden.materialize(ws, ws.business(args.business), args.case)
    print(f"Created eval job {job['id']} from {args.case}. Run the agents on it, then: "
          f"python3 -m holdco golden compare {args.business} {args.case} --job {job['id']}")
    return 0


def cmd_golden_compare(args) -> int:
    ws = _ws(args)
    result = golden.compare_job(ws, ws.business(args.business), args.case, args.job)
    _print_json(result) if args.json else print(
        f"{args.case} vs {args.job}: {'PASS' if result['passed'] else 'FAIL'}"
        + "".join(f"\n  {d['path']}: expected {d['before']!r}, got {d['after']!r}" for d in result["differences"]))
    return 0 if result["passed"] else 1


def cmd_eval(args) -> int:
    ws = _ws(args)
    biz = ws.business(args.business)
    report = golden.run_eval(ws, biz, get_runner(ws, biz, args.runner, set(args.without or [])))
    if args.json:
        _print_json(report)
    else:
        for r in report["cases"]:
            print(f"{'PASS' if r['passed'] else 'FAIL'} {r['case']} (from {r['source_job']}) {r['reason']}")
            for d in r["differences"]:
                print(f"     {d['path']}: expected {d['before']!r}, got {d['after']!r}")
        print(f"{report['passed']}/{len(report['cases'])} golden cases pass.")
    return 0 if report["failed"] == 0 else 1


# ----------------------------------------------------------------- holdco


def cmd_metrics(args) -> int:
    ws = _ws(args)
    businesses = [ws.business(args.business)] if args.business else ws.list_businesses()
    reports = [metrics.business_metrics(b, as_of=parse_date(args.as_of) if args.as_of else None,
                                        window_days=args.window) for b in businesses]
    if args.json:
        _print_json(reports)
    else:
        print("\n\n".join(metrics.format_report(r) for r in reports) or "No businesses.")
    return 0


def cmd_deal_score(args) -> int:
    ws = _ws(args)
    buy_box = read_json(args.buy_box) if args.buy_box else read_json(ws.buy_box_file)
    report = deals.score_deal(read_json(args.file), buy_box)
    _print_json(report) if args.json else print(deals.format_deal(report))
    return 0


def cmd_model_margin(args) -> int:
    base_margin = 1 - args.labor - args.other
    savings = [0.1, 0.2, 0.31, 0.4, 0.5, 0.6]
    captures = [0.25, 0.5, 0.75, 1.0]
    grid = deals.margin_grid(args.labor, args.other, savings, captures, args.growth_share, args.churn, args.ai_cost)
    print(f"Margin after agents · today: labor {pct(args.labor, 0)}, other costs {pct(args.other, 0)}, "
          f"margin {pct(base_margin)}")
    print(f"Assumes {pct(args.churn, 0)} of revenue lost in transition, agents cost {pct(args.ai_cost, 0)} of revenue,"
          f" and {pct(args.growth_share, 0)} of captured hours are resold to new clients (the rest not backfilled).")
    print("\nrows = share of labor hours agents take over; columns = share of freed hours you actually capture")
    print("time saved " + "".join(f"{f'capture {int(c * 100)}%':>14}" for c in captures))
    for s, row in zip(savings, grid):
        print(f"{pct(s, 0):>10} " + "".join(f"{pct(m):>14}" for m in row))
    print("\nHours you save but do not capture (no attrition, no new clients) become slack, not margin.")
    return 0


# ----------------------------------------------------------------- parser


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="holdco", description="TMA Holdings operating system.")
    p.add_argument("--root", help="workspace root (default: HOLDCO_ROOT or the nearest folder with shared/ + businesses/)")
    sub = p.add_subparsers(dest="command", required=True)

    s = sub.add_parser("status", help="overview of every business and what is waiting on a person")
    s.set_defaults(fn=cmd_status)
    s = sub.add_parser("queue", help="what is waiting on a person (approve, answer, send)")
    s.set_defaults(fn=cmd_queue)
    s = sub.add_parser("demo", help="run the end-to-end proof on the fictional bookkeeping firm")
    s.add_argument("--workspace", help="folder to run in (default: a new temp folder)")
    s.add_argument("--quiet", action="store_true", help="print only the proof summary")
    s.set_defaults(fn=cmd_demo)
    s = sub.add_parser("sandbox", help="copy the shared layer + demo firm into a scratch workspace")
    s.add_argument("path", nargs="?", default=".sandbox")
    s.set_defaults(fn=cmd_sandbox)
    s = sub.add_parser("new-business", help="create a business folder from businesses/_template")
    s.add_argument("slug")
    s.add_argument("--name", required=True)
    s.add_argument("--industry", required=True)
    s.add_argument("--gm", required=True, help="the GM's name (first approver)")
    s.set_defaults(fn=cmd_new_business)

    job = sub.add_parser("job", help="create and inspect jobs").add_subparsers(dest="job_cmd", required=True)
    s = job.add_parser("new")
    s.add_argument("business")
    s.add_argument("--type", required=True)
    s.add_argument("--client", required=True)
    s.add_argument("--inputs", help="folder of documents for this job")
    s.add_argument("--period", help="e.g. 2026-09")
    s.add_argument("--id", help="custom job id")
    s.set_defaults(fn=cmd_job_new)
    s = job.add_parser("add-inputs")
    s.add_argument("business")
    s.add_argument("job")
    s.add_argument("--inputs", required=True)
    s.set_defaults(fn=cmd_job_add_inputs)
    s = job.add_parser("list")
    s.add_argument("business", nargs="?")
    s.add_argument("--state")
    s.add_argument("--all", action="store_true", help="include eval jobs")
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_job_list)
    s = job.add_parser("show")
    s.add_argument("business")
    s.add_argument("job")
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_job_show)
    s = job.add_parser("export")
    s.add_argument("business")
    s.add_argument("job")
    s.add_argument("--to", required=True)
    s.set_defaults(fn=cmd_job_export)

    s = sub.add_parser("run", help="run the deterministic demo agents on a job")
    s.add_argument("business")
    s.add_argument("job")
    s.add_argument("--runner", default="demo")
    s.set_defaults(fn=cmd_run)
    s = sub.add_parser("record", help="record one agent's output (used by the Claude workflow clerk)")
    s.add_argument("what", choices=["intake", "draft", "review", "escalation"])
    s.add_argument("business")
    s.add_argument("job")
    s.add_argument("--file", default="-", help="JSON file, or - for stdin")
    s.add_argument("--question")
    s.add_argument("--key")
    s.add_argument("--agent", choices=["intake", "preparer", "reviewer"], default="preparer")
    s.set_defaults(fn=cmd_record)
    s = sub.add_parser("record-run", help="record a whole holdco-process-job workflow run")
    s.add_argument("business")
    s.add_argument("job")
    s.add_argument("--file", default="-")
    s.set_defaults(fn=cmd_record_run)
    s = sub.add_parser("check", help="run machine checks on a job's latest draft")
    s.add_argument("business")
    s.add_argument("job")
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_check)

    s = sub.add_parser("approve", help="HUMAN ONLY: approve the latest draft (with optional edits)")
    s.add_argument("business")
    s.add_argument("job")
    s.add_argument("--by", required=True)
    s.add_argument("--final", help="edited JSON (from `job export`)")
    s.add_argument("--set", action="append", metavar="PATH=VALUE",
                   help="quick edit, e.g. 'data.transactions[T-0602].category=Materials (COGS)'")
    s.add_argument("--reason", help="category for every edit: factual_error|client_preference|missing_information|style")
    s.add_argument("--minutes", type=float, help="minutes of your time this job took (Monday metric)")
    s.add_argument("--note")
    s.add_argument("--override-checks", metavar="REASON", help="approve despite failing blocker checks, with a reason")
    s.set_defaults(fn=cmd_approve)
    s = sub.add_parser("shadow", help="HUMAN ONLY: shadow mode, log how the agent draft differs from your own work")
    s.add_argument("business")
    s.add_argument("job")
    s.add_argument("--by", required=True)
    s.add_argument("--final", help="your version as deliverable JSON")
    s.add_argument("--human-csv", help="monthly-close: CSV of id,category as you booked it")
    s.add_argument("--set", action="append", metavar="PATH=VALUE")
    s.add_argument("--reason", help="category for every difference")
    s.add_argument("--minutes", type=float, help="minutes the job took you by hand (manual baseline)")
    s.set_defaults(fn=cmd_shadow)
    s = sub.add_parser("graduation", help="is a job type ready to move from shadow to assisted?")
    s.add_argument("business")
    s.add_argument("job_type")
    s.add_argument("--last", type=int, default=20)
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_graduation)
    s = sub.add_parser("rollout", help="HUMAN ONLY: set a job type to shadow or assisted mode")
    s.add_argument("business")
    s.add_argument("job_type")
    s.add_argument("mode", choices=["shadow", "assisted"])
    s.add_argument("--by", required=True)
    s.add_argument("--reason", required=True)
    s.set_defaults(fn=cmd_rollout)
    s = sub.add_parser("send-back", help="HUMAN ONLY: return a draft to the preparer with a note")
    s.add_argument("business")
    s.add_argument("job")
    s.add_argument("--by", required=True)
    s.add_argument("--note", required=True)
    s.add_argument("--reason", required=True)
    s.set_defaults(fn=cmd_send_back)
    s = sub.add_parser("send", help="HUMAN ONLY: release approved work to the outbox")
    s.add_argument("business")
    s.add_argument("job")
    s.add_argument("--by", required=True)
    s.set_defaults(fn=cmd_send)
    s = sub.add_parser("answer", help="HUMAN ONLY: answer an agent's question")
    s.add_argument("business")
    s.add_argument("job")
    s.add_argument("--by", required=True)
    s.add_argument("--text", required=True)
    s.set_defaults(fn=cmd_answer)
    s = sub.add_parser("cancel", help="HUMAN ONLY: cancel a job")
    s.add_argument("business")
    s.add_argument("job")
    s.add_argument("--by", required=True)
    s.add_argument("--reason", required=True)
    s.set_defaults(fn=cmd_cancel)

    corr = sub.add_parser("corrections", help="the corrections log").add_subparsers(dest="corr_cmd", required=True)
    s = corr.add_parser("list")
    s.add_argument("business")
    s.add_argument("--since")
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_corrections_list)
    s = corr.add_parser("review", help="the Wednesday review: propose rules for repeated fixes")
    s.add_argument("business")
    s.add_argument("--as-of")
    s.add_argument("--days", type=int, default=7)
    s.add_argument("--lookback", type=int, default=90)
    s.add_argument("--min-jobs", type=int, default=2)
    s.add_argument("--dry-run", action="store_true")
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_corrections_review)

    rules = sub.add_parser("rules", help="rules and proposals").add_subparsers(dest="rules_cmd", required=True)
    s = rules.add_parser("list")
    s.add_argument("business")
    s.add_argument("--job-type")
    s.add_argument("--client")
    s.set_defaults(fn=cmd_rules_list)
    s = rules.add_parser("proposals")
    s.add_argument("business")
    s.add_argument("--status")
    s.set_defaults(fn=cmd_rules_proposals)
    s = rules.add_parser("propose", help="record a proposal written by the rules-curator agent")
    s.add_argument("business")
    s.add_argument("--file", default="-", help="proposal JSON, or - for stdin")
    s.set_defaults(fn=cmd_rules_propose)
    s = rules.add_parser("accept", help="HUMAN ONLY: add a proposed rule and its regression tests")
    s.add_argument("business")
    s.add_argument("proposal")
    s.add_argument("--by", required=True)
    s.add_argument("--title")
    s.add_argument("--text", help="plain-English rule text (overrides the proposal's)")
    s.set_defaults(fn=cmd_rules_accept)
    s = rules.add_parser("reject", help="HUMAN ONLY: reject a proposed rule")
    s.add_argument("business")
    s.add_argument("proposal")
    s.add_argument("--by", required=True)
    s.add_argument("--reason", required=True)
    s.set_defaults(fn=cmd_rules_reject)

    gold = sub.add_parser("golden", help="golden cases (accepted work used as tests)").add_subparsers(
        dest="golden_cmd", required=True)
    s = gold.add_parser("list")
    s.add_argument("business")
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_golden_list)
    s = gold.add_parser("materialize", help="turn a golden case into an eval job for the Claude agents")
    s.add_argument("business")
    s.add_argument("case")
    s.set_defaults(fn=cmd_golden_materialize)
    s = gold.add_parser("compare", help="compare an eval job's latest draft to the accepted output")
    s.add_argument("business")
    s.add_argument("case")
    s.add_argument("--job", required=True)
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_golden_compare)
    s = sub.add_parser("eval", help="re-run the agents on every golden case")
    s.add_argument("business")
    s.add_argument("--runner", default="demo")
    s.add_argument("--without", action="append", metavar="RULE_ID", help="drop a rule to see what breaks")
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_eval)

    s = sub.add_parser("metrics", help="the Monday five metrics and alerts")
    s.add_argument("business", nargs="?")
    s.add_argument("--as-of")
    s.add_argument("--window", type=int, default=30)
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_metrics)

    deal = sub.add_parser("deal", help="screen an acquisition target").add_subparsers(dest="deal_cmd", required=True)
    s = deal.add_parser("score")
    s.add_argument("file")
    s.add_argument("--buy-box", help="default: thesis/buy-box.json")
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_deal_score)

    model = sub.add_parser("model", help="planning models").add_subparsers(dest="model_cmd", required=True)
    s = model.add_parser("margin", help="where margins go when agents take over part of the work")
    s.add_argument("--labor", type=float, default=0.55, help="labor cost as a share of revenue")
    s.add_argument("--other", type=float, default=0.35, help="all other costs as a share of revenue")
    s.add_argument("--churn", type=float, default=0.05)
    s.add_argument("--ai-cost", type=float, default=0.03)
    s.add_argument("--growth-share", type=float, default=0.4)
    s.set_defaults(fn=cmd_model_margin)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.fn(args)
    except HumanOnlyError as exc:
        print(f"REFUSED (human-only): {exc}", file=sys.stderr)
        return 3
    except PermissionError as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 3
    except HoldcoError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except (EOFError, KeyboardInterrupt):
        print("\nCancelled. Nothing changed.", file=sys.stderr)
        return 130
