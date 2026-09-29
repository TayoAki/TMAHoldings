"""Deterministic intake / preparer / reviewer for the bookkeeping demo.

These follow the same job descriptions as the Claude agents in shared/agents/
and read the same rule files, but make no judgment calls: they apply machine
checks and nothing else. Their job is to prove the mechanics, not to be smart.
"""

from __future__ import annotations

import datetime as dt
from collections import defaultdict
from pathlib import Path

from holdco import jobs
from holdco.checks import run_checks, score, vendor_match, verdict
from holdco.config import Business, HoldcoError, Workspace
from holdco.rules import RuleSet
from holdco.util import money, read_csv, read_json

DOC_LABELS = {
    "bank.csv": "Bank transactions export (CSV) for the month",
    "statement.json": "Bank statement showing the opening and closing balance",
}
FOLLOWED_CHECKS = {
    "reconciliation_tied", "transactions_match_input", "exclusions_explained", "uncategorized_have_questions",
    "no_phrases", "mask_numbers", "required_sections", "signoff", "large_unknown_escalation",
}


class DemoBookkeepingRunner:
    name = "demo"
    job_types = {"monthly-close", "document-chase"}

    def __init__(self, ws: Workspace, biz: Business, exclude_rules: set[str] | None = None):
        if biz.industry != "bookkeeping":
            raise HoldcoError(f"The demo runner only handles bookkeeping businesses ({biz.slug} is {biz.industry}).")
        self.ws, self.biz = ws, biz
        self.rules = RuleSet.for_business(ws, biz, exclude=exclude_rules)
        self.clients = {row["id"]: row for row in read_csv(biz.clients_csv)}

    # ---------------------------------------------------------- helpers

    @staticmethod
    def _bank(inputs: Path) -> list[dict]:
        return [{**row, "amount": float(row["amount"])} for row in read_csv(inputs / "bank.csv")]

    def _contact(self, client: str) -> str:
        return self.clients.get(client, {}).get("contact_name") or "there"

    def _signoff(self, job_type: str, client: str) -> str:
        for rule in self.rules.checks(job_type, client, "signoff"):
            return rule.check["text"]
        return f"— {(self.biz.gm or 'The team').split()[0]}"

    @staticmethod
    def _month(period: str | None) -> str:
        if not period:
            return "this month's"
        return dt.date.fromisoformat(f"{period}-01").strftime("%B %Y")

    # ----------------------------------------------------------- intake

    def intake(self, job_type: str, client: str, inputs: Path, period: str | None) -> dict:
        missing, applied = [], set()
        for rule in self.rules.checks(job_type, client, "document_checklist"):
            applied.add(rule.id)
            for doc in rule.check["documents"]:
                if not (inputs / doc).exists():
                    missing.append({"document": doc, "label": DOC_LABELS.get(doc, doc),
                                    "reason": f"needed to close the month ({rule.id})"})
        if (inputs / "bank.csv").exists():
            receipts = read_csv(inputs / "receipts.csv")
            for rule in self.rules.checks(job_type, client, "receipt_threshold"):
                applied.add(rule.id)
                threshold = float(rule.check["amount"])
                exempt = [p.upper() for p in rule.check.get("exempt_patterns", [])]
                for txn in self._bank(inputs):
                    if txn["amount"] >= 0 or abs(txn["amount"]) <= threshold:
                        continue
                    if any(p in txn["description"].upper() for p in exempt):
                        continue
                    if not any(r.get("date") == txn["date"] and abs(float(r.get("amount") or 0) - abs(txn["amount"])) < 0.005
                               for r in receipts):
                        missing.append({
                            "document": f"receipt:{txn['id']}",
                            "label": f"Receipt for {txn['description']} on {txn['date']} ({money(abs(txn['amount']))})",
                            "reason": f"receipts are required for expenses over {money(threshold)} ({rule.id})",
                            "transaction_id": txn["id"],
                        })
        found = sorted(p.name for p in inputs.iterdir()) if inputs.is_dir() else []
        if not missing:
            return {"status": "complete", "documents_found": found, "missing": [], "rules_applied": sorted(applied)}
        return {"status": "missing_documents", "documents_found": found, "missing": missing,
                "chase_message": self._chase_message(client, period, missing), "rules_applied": sorted(applied)}

    def _chase_message(self, client: str, period: str | None, missing: list[dict]) -> dict:
        count = len(missing)
        items = "item" if count == 1 else "items"
        body = "\n".join([
            f"Hi {self._contact(client)},",
            "",
            f"We're closing your {self._month(period)} books and need {count} more {items} before we can finish:",
            "",
            *[f"- {m['label']}" for m in missing],
            "",
            "A photo or PDF is fine. Just reply to this email.",
            "",
            "Thank you!",
            self._signoff("document-chase", client),
        ])
        return {"subject": f"Quick request: {count} {items} for your {self._month(period)} books", "body_markdown": body}

    # --------------------------------------------------------- preparer

    def prepare(self, job_type: str, client: str, inputs: Path, period: str | None,
                feedback: list[dict], answers: dict) -> dict:
        if job_type != "monthly-close":
            raise HoldcoError(f"The demo preparer only drafts monthly-close jobs, not {job_type}.")
        bank = self._bank(inputs)
        statement = read_json(inputs / "statement.json")
        exclude: dict[str, str] = {}
        overrides: dict[str, str] = {}
        for item in feedback:
            data = item.get("data") or {}
            for dup in data.get("duplicate_ids", []):
                exclude[dup] = (f"Duplicate of {data.get('duplicate_of')} in the bank export (same date, description "
                                "and amount). The statement balance only ties without it.")
            if data.get("transaction_id") and data.get("expected_category"):
                overrides[data["transaction_id"]] = data["expected_category"]
        large = next(iter(self.rules.checks(job_type, client, "large_unknown_escalation")), None)
        txns, questions, applied = [], [], set()
        for row in bank:
            if row["id"] in exclude:
                continue
            if row["id"] in overrides:
                category, rule_id = overrides[row["id"]], None
            else:
                category, rule_id = vendor_match(self.rules, job_type, client, row["description"])
            if category is None and row["id"] in answers:
                category = answers[row["id"]]
            if category is None:
                if large and abs(row["amount"]) >= float(large.check["amount"]):
                    return {
                        "status": "needs_human",
                        "question": (f"{row['id']} on {row['date']}: \"{row['description']}\" for {money(row['amount'])} "
                                     "matches no rule. What is it? Reply with the category "
                                     "(for example Owner's Draw, Loan Repayment, Contractor)."),
                        "key": row["id"],
                        "context": {"description": row["description"], "amount": row["amount"], "date": row["date"]},
                        "rule": large.id,
                    }
                category = "Uncategorized"
                questions.append(f"What was {row['id']} ({money(abs(row['amount']))} to {row['description']} "
                                 f"on {row['date']}) for?")
            if rule_id:
                applied.add(rule_id)
            txns.append({"id": row["id"], "date": row["date"], "description": row["description"],
                         "amount": row["amount"], "category": category})
        for txn_id in exclude:
            questions.append(f"We left out {txn_id} because it looks like a duplicate line in the bank export. "
                             "Please confirm there was only one purchase.")
        income = round(sum(t["amount"] for t in txns if t["amount"] > 0), 2)
        spend: dict[str, float] = defaultdict(float)
        for t in txns:
            if t["amount"] < 0:
                spend[t["category"]] += -t["amount"]
        expenses = {k: round(v, 2) for k, v in sorted(spend.items(), key=lambda kv: -kv[1])}
        net = round(sum(t["amount"] for t in txns), 2)
        opening, closing = float(statement["opening_balance"]), float(statement["closing_balance"])
        computed = round(opening + net, 2)
        difference = round(closing - computed, 2)
        status = "tied" if abs(difference) < 0.005 else "out_of_balance"
        for rule in self.rules.for_job(job_type, client):
            if rule.check and rule.check["type"] in FOLLOWED_CHECKS:
                applied.add(rule.id)
        return {
            "job_type": job_type,
            "client": client,
            "client_message": self._close_message(client, period, income, expenses, net, status, questions),
            "data": {
                "period": period,
                "transactions": txns,
                "excluded": [{"id": i, "reason": r} for i, r in exclude.items()],
                "summary": {"income": income, "expenses_by_category": expenses, "net": net},
                "reconciliation": {"opening_balance": opening, "closing_balance": closing,
                                   "computed_closing": computed, "difference": difference, "status": status},
            },
            "questions_for_client": questions,
            "rules_applied": sorted(applied),
            "assumptions": [],
        }

    def _close_message(self, client: str, period: str | None, income: float, expenses: dict, net: float,
                       status: str, questions: list[str]) -> dict:
        month = self._month(period)
        lines = [
            f"Hi {self._contact(client)},",
            "",
            f"Your {month} books are closed. Here's the short version.",
            "",
            "## Summary",
            f"- Money in: {money(income)}",
            f"- Money out: {money(sum(expenses.values()))}",
            f"- Net: {money(net)}",
            f"- Bank balance ties to your statement: {'yes' if status == 'tied' else 'NO, we are still checking'}",
            "",
            "## Questions",
            *([f"{i}. {q}" for i, q in enumerate(questions, 1)] or ["None this month."]),
            "",
            "The full categorized list is attached.",
            "",
            self._signoff("monthly-close", client),
        ]
        return {"subject": f"Your {month} books are ready for review", "body_markdown": "\n".join(lines)}

    # --------------------------------------------------------- reviewer

    def review(self, job_type: str, client: str, inputs: Path, deliverable: dict, answers: dict,
               period: str | None = None) -> dict:
        findings = run_checks(self.ws, self.biz, job_type, client, deliverable, inputs, answers, self.rules, period)
        result = verdict(findings, self.biz.setting("review_pass_score", 80))
        blockers = sum(f["severity"] == "blocker" for f in findings)
        summary = ("All checks passed." if not findings else
                   f"{len(findings)} finding(s), {blockers} blocker(s): " + "; ".join(f["issue"] for f in findings[:3]))
        return {"verdict": result, "score": score(findings), "findings": findings, "summary": summary}

    # ----------------------------------------------------- orchestration

    def process(self, job_id: str) -> dict:
        """Take a job as far as agents may: the approval queue, a client chase, or a question."""
        job = jobs.load_job(self.biz, job_id)
        inputs = jobs.job_dir(self.biz, job_id) / "input"
        steps: list[str] = []
        if job["type"] not in self.job_types:
            raise HoldcoError(f"The demo runner does not handle {job['type']} jobs.")
        if job["type"] == "document-chase":
            if job["state"] == jobs.DRAFTED:
                review = self.review(job["type"], job["client"], inputs, jobs.latest_draft(self.biz, job), {},
                                     job["period"])
                job = jobs.record_review(self.ws, self.biz, job_id, review)
                steps.append(f"reviewer checked chase {job_id}: {job['reviews'][-1]['verdict']} "
                             f"(score {review['score']})")
            return {"job": job, "steps": steps}
        if job["state"] == jobs.RECEIVED:
            result = self.intake(job["type"], job["client"], inputs, job["period"])
            job = jobs.record_intake(self.ws, self.biz, job_id, result)
            if result["status"] == "missing_documents":
                steps.append(f"intake: {len(result['missing'])} item(s) missing -> chase drafted")
                chase = self.process(job["children"][-1])
                return {"job": jobs.load_job(self.biz, job_id), "steps": steps + chase["steps"]}
            steps.append("intake: all documents present")
        while job["state"] in (jobs.READY, jobs.BLOCKED):
            feedback = job["reviews"][-1]["findings"] if job["state"] == jobs.BLOCKED and job["reviews"] else []
            draft = self.prepare(job["type"], job["client"], inputs, job["period"], feedback, job["answers"])
            if draft.get("status") == "needs_human":
                job = jobs.escalate(self.biz, job_id, draft["question"], jobs.PREPARER, draft["key"], draft.get("context"))
                steps.append(f"preparer stopped to ask a human: {draft['question']}")
                break
            job = jobs.record_draft(self.ws, self.biz, job_id, draft)
            review = self.review(job["type"], job["client"], inputs, draft, job["answers"], job["period"])
            job = jobs.record_review(self.ws, self.biz, job_id, review)
            last = job["reviews"][-1]
            detail = "" if last["verdict"] == "PASS" else ": " + "; ".join(f["issue"] for f in last["findings"][:2])
            steps.append(f"draft v{last['version']}: reviewer {last['verdict']} (score {last['score']}){detail}")
        return {"job": job, "steps": steps}

    def run_offline(self, job_type: str, client: str, inputs: Path, period: str | None, answers: dict) -> dict:
        """Prepare -> review -> revise without touching job state (used by the golden-case eval)."""
        feedback: list[dict] = []
        draft: dict = {}
        for _ in range(self.biz.setting("max_drafts", 3)):
            draft = self.prepare(job_type, client, inputs, period, feedback, answers)
            if draft.get("status") == "needs_human":
                return draft
            review = self.review(job_type, client, inputs, draft, answers, period)
            if review["verdict"] == "PASS":
                return draft
            feedback = review["findings"]
        return draft
