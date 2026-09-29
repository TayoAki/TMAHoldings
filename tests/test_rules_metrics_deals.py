"""Rules parsing, the Monday metrics, and the deal math."""

from __future__ import annotations

import unittest

from holdco import deals, jobs, metrics
from holdco.config import HoldcoError
from holdco.rules import RuleSet, parse_rules, render_rule
from holdco.util import next_id, parse_date, read_json
from tests.helpers import DANA, HUMAN, PASS, REPO, WorkspaceCase

RULES = """# Rules
## R-X-001 · First
- **Applies to:** monthly-close, payroll
- **Scope:** client:acme
- **Rule:** Line one
  continues here.
- **Check:** `{"type": "vendor_category", "match": "A", "category": "B"}`

## R-X-002 · Second
- **Applies to:** all
- **Non-negotiable:** yes
- **Rule:** Always.
"""


class Rules(unittest.TestCase):
    def test_parse(self):
        first, second = parse_rules(RULES, "business")
        self.assertEqual(first.applies_to, ["monthly-close", "payroll"])
        self.assertEqual(first.client, "acme")
        self.assertIn("continues here.", first.text)
        self.assertEqual(first.check["category"], "B")
        self.assertTrue(second.non_negotiable)
        self.assertTrue(second.applies("anything", None))
        self.assertFalse(first.applies("monthly-close", "bluebird"))

    def test_render_roundtrip(self):
        text = render_rule("R-X-009", "Title", {"Applies to": "monthly-close", "Scope": "all", "Rule": "Do it."},
                           {"type": "signoff", "text": "— Dana"})
        (rule,) = parse_rules(text, "business")
        self.assertEqual((rule.id, rule.check["text"]), ("R-X-009", "— Dana"))

    def test_bad_check_and_duplicates_fail_loudly(self):
        with self.assertRaises(HoldcoError):
            parse_rules("## R-X-001 · A\n- **Check:** `{not json}`\n", "business")
        with self.assertRaises(HoldcoError):
            parse_rules("## R-X-001 · A\n- **Rule:** a\n## R-X-001 · B\n- **Rule:** b\n", "business")

    def test_unknown_check_types_fail_loudly(self):
        with self.assertRaisesRegex(HoldcoError, "unknown check type"):
            parse_rules('## R-X-001 · A\n- **Check:** `{"type": "vendor_categroy"}`\n', "business")

    def test_ids_never_reuse_a_deleted_number(self):
        self.assertEqual(next_id("G", ["G-0001", "G-0003"]), "G-0004")
        self.assertEqual(next_id("P", []), "P-0001")

    def test_repo_rule_files_parse(self):
        for path in [REPO / "shared/rules/global-rules.md", *sorted((REPO / "shared/rules/industries").glob("*.md")),
                     REPO / "businesses/demo-bookkeeping/rules.md"]:
            rules = parse_rules(path.read_text(), "x", str(path))
            self.assertTrue(rules, path)


class Metrics(WorkspaceCase):
    def test_retention_and_people(self):
        report = metrics.business_metrics(self.biz, as_of=parse_date("2026-09-28"))
        self.assertEqual((report["retention"]["base"], report["retention"]["retained"]), (3, 2))
        self.assertEqual(report["retention"]["churned"][0]["id"], "northside")
        at_risk = [p["person"] for p in report["people"] if not p["ok"]]
        self.assertEqual(at_risk, ["Ravi Patel"])
        self.assertTrue(any("while clients left" in a for a in report["alerts"]))
        self.assertAlmostEqual(report["margin"]["latest"]["margin"], (40900 - 35210) / 40900)

    def test_a_send_back_counts_as_a_draft_that_needed_fixing(self):
        job = self.to_approval()
        jobs.send_back(self.biz, job["id"], DANA, HUMAN, "Say which receipts you still need", "style")
        self.assertEqual(self.runner().process(job["id"])["job"]["state"], jobs.AWAITING_APPROVAL)
        jobs.approve(self.ws, self.biz, job["id"], DANA, HUMAN, passphrase=PASS, minutes=5)
        current = metrics.business_metrics(self.biz, as_of=parse_date("2026-09-28"))["current"]
        self.assertEqual((current["fix_rate"], current["edits"], current["send_backs"]), (1.0, 0, 1))

    def test_rule_files_in_a_workspace_load_together(self):
        self.assertTrue(RuleSet.for_business(self.ws, self.biz).get("BK-012"))

    def test_no_jobs_no_crash(self):
        text = metrics.format_report(metrics.business_metrics(self.biz, as_of=parse_date("2026-09-28")))
        self.assertIn("Human minutes per job .... n/a", text)

    def test_margin_stops_at_the_as_of_month(self):
        margin = metrics.business_metrics(self.biz, as_of=parse_date("2026-06-30"))["margin"]
        self.assertEqual((margin["latest"]["month"], margin["prior"]["month"]), ("2026-06", "2026-05"))


class Deals(unittest.TestCase):
    def setUp(self):
        self.buy_box = read_json(REPO / "thesis/buy-box.json")
        self.deal = read_json(REPO / "thesis/deals/example-target.json")

    def test_pmt_matches_a_known_value(self):
        self.assertAlmostEqual(deals.pmt(0.105, 10, 500_000), 6746.75, places=2)
        self.assertAlmostEqual(deals.pmt(0.0, 10, 120_000), 1000.0)

    def test_max_price_meets_the_coverage_floor_exactly(self):
        report = deals.score_deal(self.deal, self.buy_box)
        cap = report["max_price_caps"]["DSCR on today's earnings"]
        fin = deals.financing(cap, report["assumptions"]["structure"])
        self.assertAlmostEqual(report["ebitda_today"] / fin["debt_service_peak"], 1.25, places=6)
        self.assertLessEqual(report["max_price"], cap)

    def test_example_is_negotiate_and_price_based_on_today(self):
        report = deals.score_deal(self.deal, self.buy_box)
        self.assertEqual(report["verdict"], "NEGOTIATE")
        self.assertEqual(report["ebitda_today"], 250_000)
        self.assertTrue(any("standby" in w for w in report["warnings"]))

    def test_hard_fails_walk_away(self):
        for change in ({"licensing": "cpa"}, {"gm_candidate": False}, {"industry": "restaurants"},
                       {"top_client_pct": 0.31}, {"owner_transition_months": 0}, {"priced_on_ai_upside": True},
                       {"ttm_sde": 200_000}):
            report = deals.score_deal({**self.deal, **change}, self.buy_box)
            self.assertEqual(report["verdict"], "WALK AWAY", change)

    def test_soft_misses_do_not_walk_away(self):
        for change in ({"top_client_pct": 0.2}, {"years_in_business": 6}, {"clients": 60},
                       {"billing_model": "hourly"}, {"owner_transition_months": 3}):
            report = deals.score_deal({**self.deal, **change}, self.buy_box)
            self.assertEqual(report["verdict"], "NEGOTIATE", change)
            self.assertTrue(any(not c["ok"] and not c["hard"] for c in report["checks"]), change)

    def test_walk_away_rules_come_from_the_buy_box(self):
        box = {**self.buy_box, "hard_fail": {**self.buy_box["hard_fail"], "max_top_client_pct": 0.5,
                                             "no_gm_candidate": False}}
        for change in ({"top_client_pct": 0.4}, {"gm_candidate": False}):
            self.assertEqual(deals.score_deal({**self.deal, **change}, box)["verdict"], "NEGOTIATE", change)

    def test_billing_models_come_from_the_buy_box(self):
        mixed = deals.score_deal({**self.deal, "billing_model": "mixed"}, self.buy_box)
        check = next(c for c in mixed["checks"] if c["criterion"].startswith("Billing"))
        self.assertTrue(check["warn_only"])
        box = {**self.buy_box, "billing_models_ok": ["fixed_fee", "hourly"]}
        hourly = deals.score_deal({**self.deal, "billing_model": "hourly"}, box)
        self.assertTrue(next(c for c in hourly["checks"] if c["criterion"].startswith("Billing"))["ok"])

    def test_tax_preparer_credentials_are_workable_licensing(self):
        for licensing, workable in (("efin", True), ("ptin", True), ("cpa-attest", False)):
            report = deals.score_deal({**self.deal, "industry": "tax-prep", "licensing": licensing}, self.buy_box)
            check = next(c for c in report["checks"] if c["criterion"].startswith("Licensing"))
            self.assertEqual(check["ok"], workable, licensing)
            self.assertEqual(report["verdict"] == "WALK AWAY", not workable, licensing)

    def test_rollover_is_flagged_as_unavailable_in_a_control_acquisition(self):
        deal = {**self.deal, "structure": {**self.deal["structure"], "rollover_pct": 0.2}}
        report = deals.score_deal(deal, self.buy_box)
        self.assertTrue(any("not available when you buy control" in w for w in report["warnings"]))

    def test_margin_model(self):
        flat = deals.margin_after_ai(0.55, 0.35, 0.0, 0.0, 0.0)
        self.assertAlmostEqual(flat.margin, 0.10)
        better = deals.margin_after_ai(0.55, 0.35, 0.31, 0.5, 0.3, churn=0.05, ai_cost_pct=0.03)
        self.assertGreater(better.margin, 0.18)
        self.assertLess(better.margin, 0.25)
        with self.assertRaises(HoldcoError):
            deals.margin_after_ai(0.55, 0.35, 0.3, 0.8, 0.5)

    def test_thesis_margin_needs_about_half_the_hours(self):
        grid = deals.margin_grid(0.55, 0.35, [0.31, 0.5], [1.0])
        self.assertLess(grid[0][0], 0.30)   # the reported 31% pilot alone does not get to 30%
        self.assertGreater(grid[1][0], 0.30)  # about half the hours, fully captured, does


if __name__ == "__main__":
    unittest.main()
