"""The Monday numbers: five metrics per business, plus the alerts that matter.

1. Profit margin                  financials.csv (month, revenue, costs)
2. Human minutes per job          minutes recorded at approval
3. How often agent drafts need fixing   approvals with at least one edit
4. Client retention               clients.csv (since, status, left_on)
5. Whether key people are happy and staying   pulse.csv (weekly GM check-in)

Metrics serve decisions, not the other way round: a margin that rises while
clients leave is a warning, not a win, so the alerts compare them directly.
"""

from __future__ import annotations

import datetime as dt
from statistics import mean

from holdco import jobs
from holdco.config import Business
from holdco.util import now, parse_date, pct, read_csv


def _approvals(biz: Business, start: dt.date, end: dt.date) -> list[dict]:
    types = set(biz.setting("metric_job_types") or [])
    out = []
    for job in jobs.list_jobs(biz):
        approval = job.get("approval")
        if not approval or (types and job["type"] not in types):
            continue
        if start <= parse_date(approval["at"]) <= end:
            out.append(job)
    return out


def _window_stats(biz: Business, start: dt.date, end: dt.date) -> dict:
    approved = _approvals(biz, start, end)
    minutes = [j["approval"]["minutes"] for j in approved if j["approval"].get("minutes") is not None]
    fixed = [j for j in approved if j["approval"].get("edited")]
    escalations = sum(
        1 for j in approved for q in j.get("questions", []) if q.get("asked_by") in jobs.AGENT_ROLES
    )
    return {
        "jobs": len(approved),
        "minutes_per_job": round(mean(minutes), 1) if minutes else None,
        "fix_rate": (len(fixed) / len(approved)) if approved else None,
        "edits": sum(j["approval"].get("changes", 0) for j in approved),
        "escalations": escalations,
    }


def _shadow_stats(biz: Business, start: dt.date, end: dt.date) -> dict:
    types = set(biz.setting("metric_job_types") or [])
    shadowed = [j for j in jobs.list_jobs(biz) if j.get("shadow") and (not types or j["type"] in types)
                and start <= parse_date(j["shadow"]["at"]) <= end]
    minutes = [j["shadow"]["minutes"] for j in shadowed if j["shadow"].get("minutes") is not None]
    return {"jobs": len(shadowed),
            "manual_minutes_per_job": round(mean(minutes), 1) if minutes else None,
            "agent_matched": (sum(1 for j in shadowed if j["shadow"]["changes"] == 0) / len(shadowed))
            if shadowed else None}


def _margin(biz: Business) -> dict:
    rows = sorted(read_csv(biz.financials_csv), key=lambda r: r["month"])
    series = []
    for row in rows:
        revenue, costs = float(row["revenue"]), float(row["costs"])
        series.append({"month": row["month"], "revenue": revenue, "costs": costs,
                       "margin": (revenue - costs) / revenue if revenue else None})
    return {"series": series, "latest": series[-1] if series else None,
            "prior": series[-2] if len(series) > 1 else None}


def _retention(biz: Business, as_of: dt.date, days: int) -> dict:
    start = as_of - dt.timedelta(days=days)
    base, churned = [], []
    for row in read_csv(biz.clients_csv):
        since = parse_date(row["since"]) if row.get("since") else None
        left = parse_date(row["left_on"]) if row.get("left_on") else None
        if since and since > start:
            continue
        if left and left <= start:
            continue
        base.append(row)
        if left and start < left <= as_of:
            churned.append({"id": row["id"], "name": row["name"], "left_on": row["left_on"],
                            "loyal_to": row.get("loyal_to", "")})
    rate = (len(base) - len(churned)) / len(base) if base else None
    return {"days": days, "base": len(base), "retained": len(base) - len(churned), "rate": rate, "churned": churned}


def _people(biz: Business) -> list[dict]:
    latest: dict[str, dict] = {}
    for row in sorted(read_csv(biz.pulse_csv), key=lambda r: r["date"]):
        if row.get("key", "").lower() in ("yes", "true", "1"):
            latest[row["person"]] = row
    out = []
    for person, row in latest.items():
        happiness = int(row["happiness"])
        risk = row.get("flight_risk", "").lower()
        out.append({"person": person, "role": row.get("role", ""), "date": row["date"], "happiness": happiness,
                    "flight_risk": risk, "note": row.get("note", ""),
                    "ok": happiness >= 4 and risk == "low"})
    return out


def business_metrics(biz: Business, as_of: dt.date | None = None, window_days: int = 30,
                     retention_days: int = 90) -> dict:
    as_of = as_of or now().date()
    current = _window_stats(biz, as_of - dt.timedelta(days=window_days - 1), as_of)
    previous = _window_stats(biz, as_of - dt.timedelta(days=2 * window_days - 1),
                             as_of - dt.timedelta(days=window_days))
    shadow = _shadow_stats(biz, as_of - dt.timedelta(days=window_days - 1), as_of)
    margin = _margin(biz)
    retention = _retention(biz, as_of, retention_days)
    people = _people(biz)
    alerts = []
    latest, prior = margin["latest"], margin["prior"]
    if latest and prior and latest["margin"] is not None and prior["margin"] is not None:
        if latest["margin"] > prior["margin"] and retention["churned"]:
            names = ", ".join(c["name"] for c in retention["churned"])
            alerts.append(f"Profit margin is up ({pct(prior['margin'])} -> {pct(latest['margin'])}) while clients "
                          f"left ({names}). Find out why before celebrating.")
        if latest["revenue"] < prior["revenue"] * 0.97:
            alerts.append(f"Revenue fell {pct(1 - latest['revenue'] / prior['revenue'])} month over month.")
    for label, key in (("Human minutes per job", "minutes_per_job"), ("Share of drafts needing fixes", "fix_rate")):
        if current[key] is not None and previous[key] is not None and current[key] > previous[key]:
            alerts.append(f"{label} went up ({previous[key]} -> {current[key]}). Check the corrections log.")
    for person in people:
        if not person["ok"]:
            alerts.append(f"{person['person']} ({person['role']}): happiness {person['happiness']}/5, flight risk "
                          f"{person['flight_risk']}. Raise it on Tuesday's GM call. Note: {person['note']}")
    return {"business": biz.slug, "name": biz.name, "as_of": as_of.isoformat(), "window_days": window_days,
            "margin": margin, "current": current, "previous": previous, "shadow": shadow, "retention": retention,
            "people": people, "alerts": alerts}


def _arrow(now_value, before_value) -> str:
    if now_value is None or before_value is None:
        return ""
    if now_value > before_value:
        return "▲"
    if now_value < before_value:
        return "▼"
    return "="


def format_report(report: dict) -> str:
    c, p = report["current"], report["previous"]
    m, r = report["margin"], report["retention"]
    lines = [f"Monday metrics · {report['name']} · as of {report['as_of']}",
             f"(jobs approved in the last {report['window_days']} days vs the {report['window_days']} before)", ""]
    if m["latest"]:
        prior = f" {_arrow(m['latest']['margin'], m['prior']['margin'])} from {pct(m['prior']['margin'])} ({m['prior']['month']})" if m["prior"] else ""
        lines.append(f"1. Profit margin ............ {pct(m['latest']['margin'])} ({m['latest']['month']}){prior}")
    else:
        lines.append("1. Profit margin ............ n/a (add financials.csv)")
    minutes_now = "n/a" if c["minutes_per_job"] is None else f"{c['minutes_per_job']} min"
    minutes_before = "n/a" if p["minutes_per_job"] is None else f"{p['minutes_per_job']} min"
    lines.append(f"2. Human minutes per job .... {minutes_now} ({c['jobs']} job(s)) "
                 f"{_arrow(c['minutes_per_job'], p['minutes_per_job'])} from {minutes_before}")
    sh = report.get("shadow") or {}
    if sh.get("jobs"):
        lines.append(f"   shadow mode ............. {sh['jobs']} job(s) done by hand; manual baseline "
                     f"{sh['manual_minutes_per_job']} min/job; agent matched the person on {pct(sh['agent_matched'], 0)}")
    lines.append(f"3. Drafts needing fixes ..... {pct(c['fix_rate'], 0)} "
                 f"{_arrow(c['fix_rate'], p['fix_rate'])} from {pct(p['fix_rate'], 0)} · "
                 f"{c['edits']} edit(s), {c['escalations']} agent question(s) this window")
    churn = "; churned: " + ", ".join(f"{x['name']} ({x['left_on']})" for x in r["churned"]) if r["churned"] else ""
    lines.append(f"4. Client retention ......... {pct(r['rate'])} over {r['days']} days "
                 f"({r['retained']}/{r['base']}){churn}")
    people = " · ".join(f"{x['person']} {'OK' if x['ok'] else 'AT RISK'} ({x['happiness']}/5, {x['flight_risk']})"
                        for x in report["people"]) or "n/a (add pulse.csv)"
    lines.append(f"5. Key people ............... {people}")
    lines.append("")
    if report["alerts"]:
        lines.append("Alerts")
        lines.extend(f"  ! {a}" for a in report["alerts"])
    else:
        lines.append("No alerts.")
    return "\n".join(lines)
