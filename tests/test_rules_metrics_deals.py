"""Rules parsing, the Monday metrics, and the deal math."""

from __future__ import annotations

import unittest

from holdco import deals, metrics
from holdco.config import HoldcoError
from holdco.rules import parse_rules, render_rule
from holdco.util import parse_date, read_json
from tests.helpers import REPO, WorkspaceCase

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

    def test_no_jobs_no_crash(self):
        text = metrics.format_report(metrics.business_metrics(self.biz, as_of=parse_date("2026-09-28")))
        self.assertIn("Human minutes per job .... n/a", text)


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
                       {"top_client_pct": 0.4}):
            report = deals.score_deal({**self.deal, **change}, self.buy_box)
            self.assertEqual(report["verdict"], "WALK AWAY", change)

    def test_rollover_triggers_the_sba_guarantee_warning(self):
        deal = {**self.deal, "structure": {**self.deal["structure"], "rollover_pct": 0.2}}
        report = deals.score_deal(deal, self.buy_box)
        self.assertTrue(any("guarantee" in w for w in report["warnings"]))

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
