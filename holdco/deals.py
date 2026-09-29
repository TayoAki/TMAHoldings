"""Deal screening and the math behind "price it on what it makes today".

Two tools:

* ``score_deal``  checks a target against thesis/buy-box.json, works out the
  sources and uses, the debt service and coverage on today's earnings, the
  most you should pay, and what the AI thesis would add on top.
* ``margin_after_ai``  a transparent model of where a 5-10% margin could go
  after agents take over part of the work, and what has to be true for 30-40%.

These are planning calculators, not financial advice. Rates, multiples and
SBA rules change; confirm them with a lender, a broker and a CPA.
"""

from __future__ import annotations

from dataclasses import dataclass

from holdco.config import HoldcoError
from holdco.util import money, pct

DEFAULT_STRUCTURE = {
    "financing": "sba_7a",           # sba_7a | conventional | seller
    "buyer_cash_pct": 0.10,          # of total project cost (price + closing costs + working capital)
    "seller_note_pct": 0.10,         # of price
    "seller_note_rate": 0.07,
    "seller_note_years": 10,         # amortization once payments start
    "seller_note_standby_years": 10, # no payments during standby (SBA: full standby to count as equity)
    "rollover_pct": 0.0,             # of price, seller keeps this share of the equity
    "earnout_pct": 0.0,              # of price, paid later on performance (not allowed with SBA 7(a))
    "loan_rate": 0.10,               # Prime (~7.00% in Sep 2026) + SBA max spread 3.0% over $350k; confirm
    "loan_years": 10,
    "closing_costs_pct": 0.03,
    "working_capital": 0.0,
    "gm_equity_pct": 0.0,            # profits interest / equity pool for the GM
}

# Walk-away rules. thesis/buy-box.json can change them under "hard_fail"; THESIS.md and runbook 08
# list the same ones.
DEFAULT_HARD_FAIL = {
    "industry_not_in_thesis": True,
    "licensing_not_workable": True,    # licensing would make us a passive owner of regulated work
    "min_dscr_today": 1.0,             # coverage on today's earnings below this
    "max_top_client_pct": 0.30,        # one client above this share of revenue
    "no_gm_candidate": True,
    "owner_leaves_at_closing": True,   # owner_transition_months == 0
    "priced_on_ai_upside": True,       # the seller wants to be paid for what we would build
}

DEFAULT_SCENARIOS = [
    {"name": "Stress: 5% churn, no AI gains", "time_savings": 0.0, "capture_cost": 0.0, "capture_growth": 0.0,
     "churn": 0.05, "ai_cost_pct": 0.0},
    {"name": "Conservative", "time_savings": 0.15, "capture_cost": 0.5, "capture_growth": 0.3,
     "churn": 0.05, "ai_cost_pct": 0.02},
    {"name": "Reported pilot (31% time saved)", "time_savings": 0.31, "capture_cost": 0.5, "capture_growth": 0.3,
     "churn": 0.05, "ai_cost_pct": 0.03},
    {"name": "Thesis case", "time_savings": 0.5, "capture_cost": 0.5, "capture_growth": 0.4,
     "churn": 0.05, "ai_cost_pct": 0.03},
]


def pmt(annual_rate: float, years: float, principal: float) -> float:
    """Monthly payment on a fully amortizing loan."""
    n = int(round(years * 12))
    if principal <= 0 or n <= 0:
        return 0.0
    r = annual_rate / 12
    if r == 0:
        return principal / n
    return principal * r / (1 - (1 + r) ** -n)


@dataclass
class MarginResult:
    revenue: float   # per $1 of today's revenue
    labor: float
    other: float
    ai: float
    ebitda: float

    @property
    def margin(self) -> float:
        return self.ebitda / self.revenue if self.revenue else 0.0


def margin_after_ai(labor_pct: float, other_pct: float, time_savings: float, capture_cost: float,
                    capture_growth: float, churn: float = 0.0, ai_cost_pct: float = 0.0,
                    other_fixed_share: float = 0.6) -> MarginResult:
    """Per $1 of today's revenue.

    time_savings    share of labor hours agents take over (Current reported 31% on tax prep)
    capture_cost    share of freed hours removed from cost (attrition, no backfill)
    capture_growth  share of freed hours resold to new clients at today's prices
    churn           share of revenue lost during the transition
    ai_cost_pct     agents, software and review overhead as a share of revenue
    Freed hours not captured are absorbed (slack, extra review, rework).
    """
    if not 0 <= time_savings < 1:
        raise HoldcoError("time_savings must be between 0 and 1.")
    if capture_cost + capture_growth > 1 + 1e-9:
        raise HoldcoError("capture_cost + capture_growth cannot exceed 1: an hour can only be used once.")
    new_work_per_hour = time_savings / (1 - time_savings)  # $ of new revenue one freed $ of labor can serve
    revenue = 1 + new_work_per_hour * capture_growth - churn
    labor = labor_pct * (1 - time_savings * capture_cost)
    fixed = other_pct * other_fixed_share
    other = fixed + (other_pct - fixed) * revenue
    ai = ai_cost_pct * revenue
    return MarginResult(revenue, labor, other, ai, revenue - labor - other - ai)


def margin_grid(labor_pct: float, other_pct: float, savings: list[float], captures: list[float],
                growth_share: float = 0.4, churn: float = 0.05, ai_cost_pct: float = 0.03) -> list[list[float]]:
    rows = []
    for s in savings:
        row = []
        for c in captures:
            row.append(margin_after_ai(labor_pct, other_pct, s, c * (1 - growth_share), c * growth_share,
                                       churn, ai_cost_pct).margin)
        rows.append(row)
    return rows


# ------------------------------------------------------------------ deals


def _structure(deal: dict) -> dict:
    return {**DEFAULT_STRUCTURE, **deal.get("structure", {})}


def financing(price: float, st: dict) -> dict:
    closing = price * st["closing_costs_pct"]
    uses = price + closing + st["working_capital"]
    buyer_cash = uses * st["buyer_cash_pct"]
    note = price * st["seller_note_pct"]
    rollover = price * st["rollover_pct"]
    earnout = price * st["earnout_pct"]
    loan = uses - buyer_cash - note - rollover - earnout
    if loan < 0:
        raise HoldcoError("Cash, seller note and rollover already cover more than the whole deal.")
    loan_annual = pmt(st["loan_rate"], st["loan_years"], loan) * 12
    standby = st["seller_note_standby_years"]
    note_at_start = note * (1 + st["seller_note_rate"]) ** standby  # interest accrues during standby
    note_annual = pmt(st["seller_note_rate"], st["seller_note_years"], note_at_start) * 12
    year1 = loan_annual + (note_annual if standby == 0 else 0.0)
    overlap = standby < st["loan_years"]
    peak = loan_annual + (note_annual if overlap else 0.0)
    return {"price": price, "closing_costs": closing, "working_capital": st["working_capital"], "uses": uses,
            "buyer_cash": buyer_cash, "seller_note": note, "rollover": rollover, "earnout": earnout, "loan": loan,
            "loan_annual": loan_annual, "note_annual": note_annual, "note_payments_start_year": standby + 1,
            "debt_service_year1": year1, "debt_service_peak": max(year1, peak)}


def _max_price_for_dscr(ebitda: float, min_dscr: float, st: dict) -> float:
    """Debt service is linear in price for a fixed structure, so solve directly."""
    base = financing(0.0, st)["debt_service_peak"]
    per_dollar = financing(1.0, st)["debt_service_peak"] - base
    if per_dollar <= 0:
        return float("inf")
    return max(0.0, (ebitda / min_dscr - base) / per_dollar)


def score_deal(deal: dict, buy_box: dict) -> dict:
    for key in ("name", "industry", "ttm_revenue", "ttm_sde", "asking_price"):
        if key not in deal:
            raise HoldcoError(f"Deal file is missing '{key}'.")
    st = _structure(deal)
    revenue, sde, price = float(deal["ttm_revenue"]), float(deal["ttm_sde"]), float(deal["asking_price"])
    replacement = float(deal.get("replacement_comp", 0))
    ebitda = sde - replacement
    fin = financing(price, st)
    dscr_year1 = ebitda / fin["debt_service_year1"] if fin["debt_service_year1"] else float("inf")
    dscr_peak = ebitda / fin["debt_service_peak"] if fin["debt_service_peak"] else float("inf")
    min_dscr = float(buy_box.get("min_dscr_today", 1.25))
    caps = {"DSCR on today's earnings": _max_price_for_dscr(ebitda, min_dscr, st)}
    if buy_box.get("max_price_to_sde"):
        caps["price / SDE cap"] = float(buy_box["max_price_to_sde"]) * sde
    industry_caps = buy_box.get("max_price_to_revenue", {})
    if isinstance(industry_caps, dict) and deal["industry"] in industry_caps:
        caps["price / revenue cap"] = float(industry_caps[deal["industry"]]) * revenue
    max_price = min(caps.values())
    binding = min(caps, key=caps.get)

    hard_rules = {**DEFAULT_HARD_FAIL, **(buy_box.get("hard_fail") or {})}
    checks: list[dict] = []

    def add(name: str, ok: bool, detail: str, hard: bool = False, warn_only: bool = False) -> None:
        checks.append({"criterion": name, "ok": ok, "detail": detail, "hard": hard and not ok,
                       "warn_only": warn_only})

    add("Industry is in the thesis", deal["industry"] in buy_box.get("industries", []),
        f"{deal['industry']} vs {', '.join(buy_box.get('industries', []))}",
        hard=hard_rules["industry_not_in_thesis"])
    licensing = deal.get("licensing", "none")
    add("Licensing is workable for us", licensing in buy_box.get("licensing_ok", ["none"]),
        f"{licensing} (who can own what: docs/VIDEO-REVIEW.md and runbook 08; CPA attest work needs CPA "
        "majority ownership)", hard=hard_rules["licensing_not_workable"])
    lo, hi = buy_box.get("revenue_min", 0), buy_box.get("revenue_max", float("inf"))
    add("Revenue in range", lo <= revenue <= hi, f"{money(revenue)} (range {money(lo)} to {money(hi)})")
    add("SDE above minimum", sde >= buy_box.get("sde_min", 0),
        f"{money(sde)} (min {money(buy_box.get('sde_min', 0))})")
    years = deal.get("years_in_business")
    if years is not None and buy_box.get("min_years_in_business"):
        add("Years in business", years >= buy_box["min_years_in_business"],
            f"{years} years (min {buy_box['min_years_in_business']})")
    clients = deal.get("clients")
    if clients is not None and buy_box.get("min_clients"):
        add("Number of clients", clients >= buy_box["min_clients"], f"{clients} (min {buy_box['min_clients']})")
    add("Price within max justified", price <= max_price,
        f"asking {money(price)} vs max {money(max_price)} (binding: {binding})")
    floor = float(hard_rules["min_dscr_today"])
    add(f"DSCR on today's earnings >= {min_dscr}", dscr_peak >= min_dscr,
        f"{dscr_peak:.2f}x at peak debt service (year 1: {dscr_year1:.2f}x); under {floor:.2f}x means walk away",
        hard=dscr_peak < floor)
    recurring = deal.get("recurring_revenue_pct")
    if recurring is not None:
        add("Recurring revenue", recurring >= buy_box.get("min_recurring_revenue_pct", 0.6),
            f"{pct(recurring, 0)} (min {pct(buy_box.get('min_recurring_revenue_pct', 0.6), 0)})")
    top = deal.get("top_client_pct")
    if top is not None:
        cap = buy_box.get("max_top_client_pct", 0.15)
        limit = float(hard_rules["max_top_client_pct"])
        add("Client concentration", top <= cap,
            f"top client {pct(top, 0)} of revenue (max {pct(cap, 0)}; over {pct(limit, 0)} means walk away)",
            hard=top > limit)
    if buy_box.get("requires_gm_candidate", True):
        add("A GM candidate already works there", bool(deal.get("gm_candidate")),
            "the person who knows every client, ready to run it with real upside",
            hard=hard_rules["no_gm_candidate"])
    months = deal.get("owner_transition_months")
    if months is not None:
        need = buy_box.get("min_owner_transition_months", 6)
        add("Owner stays long enough to hand over", months >= need,
            f"{months} months (min {need})" + ("; the owner leaves at closing" if months == 0 else ""),
            hard=months == 0 and hard_rules["owner_leaves_at_closing"])
    billing = deal.get("billing_model")
    if billing is not None:
        ok_models = buy_box.get("billing_models_ok", ["fixed_fee", "subscription"])
        warn_models = buy_box.get("billing_models_warn", ["mixed"])
        add("Billing lets us keep the savings", billing in ok_models,
            f"{billing} (ok: {', '.join(ok_models)}): with hourly billing, doing the work faster shrinks revenue "
            "until pricing changes", warn_only=billing in warn_models)
    ai_share = deal.get("ai_addressable_work_pct")
    if ai_share is not None:
        add("Enough of the work is agent-ready", ai_share >= buy_box.get("min_ai_addressable_work_pct", 0.3),
            f"{pct(ai_share, 0)} of hours (min {pct(buy_box.get('min_ai_addressable_work_pct', 0.3), 0)})")
    if deal.get("priced_on_ai_upside") is not None:
        add("Priced on today's earnings", not deal["priced_on_ai_upside"],
            "the seller wants to be paid for the AI upside" if deal["priced_on_ai_upside"]
            else "the seller prices on today's earnings", hard=hard_rules["priced_on_ai_upside"])

    warnings = _financing_warnings(st, fin)
    labor = float(deal.get("labor_cost_pct", 0.55))
    other = max(0.0, 1 - labor - (ebitda / revenue if revenue else 0))
    owner_share = 1 - st["rollover_pct"] - st["gm_equity_pct"]
    scenarios = []
    for sc in deal.get("scenarios") or DEFAULT_SCENARIOS:
        m = margin_after_ai(labor, other, sc["time_savings"], sc["capture_cost"], sc["capture_growth"],
                            sc.get("churn", 0.0), sc.get("ai_cost_pct", 0.0))
        sc_revenue = revenue * m.revenue
        sc_ebitda = revenue * m.ebitda
        after_debt = sc_ebitda - fin["debt_service_peak"]
        scenarios.append({
            "name": sc["name"], "revenue": sc_revenue, "ebitda": sc_ebitda, "margin": m.margin,
            "dscr": sc_ebitda / fin["debt_service_peak"] if fin["debt_service_peak"] else float("inf"),
            "cash_after_debt": after_debt,
            "cash_on_cash": (after_debt * owner_share / fin["buyer_cash"]) if fin["buyer_cash"] else None,
        })

    hard_fails = [c for c in checks if c["hard"]]
    soft = [c for c in checks if not c["warn_only"]]
    fit = round(100 * sum(c["ok"] for c in soft) / len(soft)) if soft else 0
    if hard_fails:
        verdict = "WALK AWAY"
    elif price > max_price:
        verdict = "NEGOTIATE"
    else:
        verdict = "PURSUE"
    return {
        "name": deal["name"], "verdict": verdict, "fit_score": fit, "ebitda_today": ebitda,
        "multiples": {"price_to_sde": price / sde if sde else None,
                      "price_to_ebitda": price / ebitda if ebitda > 0 else None,
                      "price_to_revenue": price / revenue if revenue else None},
        "financing": fin, "dscr_year1": dscr_year1, "dscr_peak": dscr_peak,
        "max_price": max_price, "max_price_caps": caps, "binding_cap": binding,
        "checks": checks, "warnings": warnings, "scenarios": scenarios,
        "assumptions": {"labor_cost_pct": labor, "other_cost_pct": other, "structure": st, "min_dscr": min_dscr},
    }


def _financing_warnings(st: dict, fin: dict) -> list[str]:
    """SBA 7(a) points as of SOP 50 10 8 / 8.1 (Oct 2026). Rules change: confirm with the lender."""
    out = []
    if st["financing"] != "sba_7a":
        if fin["loan"] > 0:
            out.append("Non-SBA debt: lenders will set their own equity, coverage and guarantee terms.")
        return out
    equity_needed = 0.10 * fin["uses"]
    eligible_note = 0.0
    if st["seller_note_standby_years"] >= st["loan_years"]:
        eligible_note = min(fin["seller_note"], equity_needed / 2)
    if fin["buyer_cash"] + eligible_note < equity_needed - 0.5:
        out.append(f"Equity injection looks below the SBA 10% minimum for a first acquisition "
                   f"({money(fin['buyer_cash'] + eligible_note)} counted vs {money(equity_needed)} needed). A seller "
                   "note only counts if it is on full standby for the whole loan term, and then for at most half.")
    if 0 < st["seller_note_standby_years"] < st["loan_years"]:
        out.append("The seller note comes off standby before the loan is repaid: it will not count toward the SBA "
                   "equity injection, and debt service steps up when its payments start.")
    if st["rollover_pct"] > 0:
        out.append("The seller keeps equity. That is not available when you buy control with SBA 7(a) money: the "
                   "seller has to exit fully and can stay only as a consultant, and a new holding company owned by "
                   "both buyer and seller is ineligible. If the seller must keep a stake, use a seller note on full "
                   "standby instead, or non-SBA financing, and check the structure with your lender.")
    if st["earnout_pct"] > 0:
        out.append("Seller earnouts are not allowed on SBA 7(a) loans. Use a buyer rebate instead (for example a "
                   "12-month client-retention clawback) that pays down loan principal.")
    if fin["loan"] > 5_000_000:
        out.append(f"The loan ({money(fin['loan'])}) is above the $5M SBA 7(a) maximum.")
    if fin["price"] > 350_000:
        out.append("SBA requires an independent business valuation above a $350k price"
                   + (" and a quality-of-earnings report at $3M or more." if fin["price"] >= 3_000_000 else "."))
    out.append("SBA guarantees at most $3.75M per borrower including affiliates, so every business the holdco "
               "controls shares that cap. Plan deal #2's financing before closing deal #1.")
    return out


def format_deal(report: dict) -> str:
    fin = report["financing"]
    mult = report["multiples"]
    lines = [
        f"Deal screen · {report['name']}",
        f"Verdict: {report['verdict']}   (buy-box fit {report['fit_score']}/100)",
        "",
        f"Today's earnings (SDE minus the cost of replacing the owner): {money(report['ebitda_today'])}",
        f"Asking price: {money(fin['price'])} = {mult['price_to_sde']:.2f}x SDE, "
        + (f"{mult['price_to_ebitda']:.2f}x adj. EBITDA, " if mult["price_to_ebitda"] else "")
        + f"{mult['price_to_revenue']:.2f}x revenue",
        f"Most you should pay: {money(report['max_price'])} (binding: {report['binding_cap']})",
        "",
        "Sources and uses",
        f"  uses: price {money(fin['price'])} + closing {money(fin['closing_costs'])} + working capital "
        f"{money(fin['working_capital'])} = {money(fin['uses'])}",
        f"  your cash {money(fin['buyer_cash'])} · seller note {money(fin['seller_note'])} · rollover "
        f"{money(fin['rollover'])} · earnout {money(fin['earnout'])} · loan {money(fin['loan'])}",
        f"  debt service: loan {money(fin['loan_annual'])}/yr; seller note {money(fin['note_annual'])}/yr from year "
        f"{fin['note_payments_start_year']}",
        f"  DSCR on today's earnings: {report['dscr_year1']:.2f}x year 1, {report['dscr_peak']:.2f}x at peak "
        f"(pre-tax, pre-capex; lenders want roughly 1.25x+)",
        "",
        "Buy box",
    ]
    for check in report["checks"]:
        mark = "ok  " if check["ok"] else ("WARN" if check["warn_only"] else ("HARD" if check["hard"] else "miss"))
        lines.append(f"  [{mark}] {check['criterion']}: {check['detail']}")
    if report["warnings"]:
        lines += ["", "Financing notes (SBA SOP 50 10 8.1 from Oct 1, 2026; confirm with your lender)"]
        lines += [f"  ! {w}" for w in report["warnings"]]
    lines += ["", "If the AI thesis works (steady state, same debt)",
              f"  {'scenario':34} {'revenue':>12} {'EBITDA':>11} {'margin':>7} {'DSCR':>6} {'cash/yr':>11}"]
    for sc in report["scenarios"]:
        lines.append(f"  {sc['name'][:34]:34} {money(sc['revenue']):>12} {money(sc['ebitda']):>11} "
                     f"{pct(sc['margin']):>7} {sc['dscr']:>5.2f}x {money(sc['cash_after_debt']):>11}")
    lines += ["", "Price on today's earnings. The scenarios are upside you create, not upside you pay for.",
              "Planning math only: confirm rates, multiples and SBA rules with your lender, broker and CPA."]
    return "\n".join(lines)
