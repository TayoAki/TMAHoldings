"""Machine checks behind the rules.

A rule's plain-English text is what agents read. Its optional ``Check`` is
what code can verify. Machine checks run on every draft that is recorded for
review, whoever wrote it: if any blocker fails, the draft is blocked even if
the reviewer agent said PASS. Code can veto an agent's pass; it can never
approve anything.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from holdco.config import Business, Workspace
from holdco.rules import KNOWN_CHECK_TYPES, Rule, RuleSet
from holdco.util import money, read_csv, read_json

SEVERITY_COST = {"blocker": 40, "major": 10, "minor": 3}
ACCOUNT_NUMBER = re.compile(r"(?<![\d*.,$])\d{8,17}(?![\d.,])")
SSN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")


@dataclass
class CheckContext:
    deliverable: dict
    inputs: Path | None
    answers: dict
    rules: RuleSet
    job_type: str
    client: str | None
    period: str | None = None

    def bank(self) -> list[dict]:
        if not self.inputs or not (self.inputs / "bank.csv").exists():
            return []
        return [{**row, "amount": float(row["amount"])} for row in read_csv(self.inputs / "bank.csv")]

    def statement(self) -> dict:
        if not self.inputs or not (self.inputs / "statement.json").exists():
            return {}
        return read_json(self.inputs / "statement.json")

    def data(self) -> dict:
        return self.deliverable.get("data", {}) or {}

    def message_text(self) -> str:
        message = self.deliverable.get("client_message", {}) or {}
        return f"{message.get('subject', '')}\n{message.get('body_markdown', '')}"

    def questions_text(self) -> str:
        return "\n".join(self.deliverable.get("questions_for_client", []) or []) + "\n" + self.message_text()


def finding(rule: Rule, severity: str, location: str, issue: str, fix: str, **data) -> dict:
    out = {"severity": severity, "rule": rule.id, "check": rule.check["type"] if rule.check else None,
           "location": location, "issue": issue, "fix": fix}
    if data:
        out["data"] = data
    return out


def vendor_match(rules: RuleSet, job_type: str, client: str | None, description: str) -> tuple[str | None, str | None]:
    """First matching vendor rule, most specific layer first."""
    upper = description.upper()
    for rule in rules.for_job(job_type, client):
        check = rule.check or {}
        if check.get("type") == "vendor_category" and check["match"].upper() in upper:
            return check["category"], rule.id
        if check.get("type") == "vendor_map":
            for pattern, category in check["map"].items():
                if pattern.upper() in upper:
                    return category, rule.id
    return None, None


# ------------------------------------------------------------------ checks


def check_reconciliation(rule: Rule, ctx: CheckContext) -> list[dict]:
    data = ctx.data()
    recon, txns = data.get("reconciliation"), data.get("transactions")
    if not isinstance(recon, dict) or not isinstance(txns, list):
        return []
    opening = float(recon.get("opening_balance", 0))
    computed = round(opening + sum(float(t["amount"]) for t in txns), 2)
    closing = float(recon.get("closing_balance", 0))
    statement = ctx.statement()
    out = []
    if statement and abs(float(statement.get("closing_balance", closing)) - closing) >= 0.005:
        out.append(finding(rule, "blocker", "data.reconciliation.closing_balance",
                           "Closing balance does not match the bank statement.",
                           f"Use the statement's closing balance {money(float(statement['closing_balance']))}."))
    difference = round(closing - computed, 2)
    if abs(difference) >= 0.005:
        dupes = _duplicate_pairs(txns)
        explaining = [pair for pair in dupes if abs(abs(pair[1]["amount"]) - abs(difference)) < 0.005]
        if explaining:
            first, second = explaining[0]
            out.append(finding(
                rule, "blocker", "data.reconciliation",
                f"Out of balance by {money(difference)}. {second['id']} looks like a duplicate of {first['id']} "
                f"(same date, description and amount) and exactly explains the gap.",
                f"Exclude {second['id']} as a duplicate, say why, and ask the client to confirm.",
                duplicate_ids=[second["id"]], duplicate_of=first["id"], difference=difference))
        else:
            out.append(finding(rule, "blocker", "data.reconciliation",
                               f"Out of balance by {money(difference)} and no duplicate explains it.",
                               "Stop and ask a human: the bank export or statement may be incomplete.",
                               difference=difference))
    elif recon.get("status") != "tied":
        out.append(finding(rule, "major", "data.reconciliation.status",
                           "The numbers tie but the status does not say so.", "Set status to 'tied'."))
    return out


def _duplicate_pairs(txns: list[dict]) -> list[tuple[dict, dict]]:
    seen: dict[tuple, dict] = {}
    pairs = []
    for txn in txns:
        key = (txn.get("date"), str(txn.get("description", "")).upper(), round(float(txn["amount"]), 2))
        if key in seen:
            pairs.append((seen[key], txn))
        else:
            seen[key] = txn
    return pairs


def check_transactions_match_input(rule: Rule, ctx: CheckContext) -> list[dict]:
    bank = {row["id"]: row for row in ctx.bank()}
    data = ctx.data()
    if not bank or "transactions" not in data:
        return []
    out = []
    listed = set()
    for txn in data.get("transactions", []):
        listed.add(txn["id"])
        source = bank.get(txn["id"])
        if source is None:
            out.append(finding(rule, "blocker", f"data.transactions[{txn['id']}]",
                               f"{txn['id']} is not in the bank export.", "Remove it; never invent transactions."))
        elif abs(source["amount"] - float(txn["amount"])) >= 0.005 or source["date"] != txn.get("date"):
            out.append(finding(rule, "blocker", f"data.transactions[{txn['id']}]",
                               f"{txn['id']} does not match the bank export (amount or date changed).",
                               f"Use {source['date']} and {money(source['amount'])} from the source file."))
    for excluded in data.get("excluded", []):
        listed.add(excluded["id"])
        if excluded["id"] not in bank:
            out.append(finding(rule, "blocker", f"data.excluded[{excluded['id']}]",
                               f"Excluded {excluded['id']} is not in the bank export.", "Remove it."))
    for missing in sorted(set(bank) - listed):
        out.append(finding(rule, "blocker", "data.transactions",
                           f"{missing} from the bank export is missing from the draft (silently dropped).",
                           "Include it, or exclude it with a reason and a client question."))
    return out


def check_exclusions_explained(rule: Rule, ctx: CheckContext) -> list[dict]:
    out = []
    text = ctx.questions_text()
    for excluded in ctx.data().get("excluded", []) or []:
        if not excluded.get("reason"):
            out.append(finding(rule, "blocker", f"data.excluded[{excluded['id']}]",
                               f"{excluded['id']} was excluded without a reason.", "Say why it was excluded."))
        if excluded["id"] not in text:
            out.append(finding(rule, "major", f"data.excluded[{excluded['id']}]",
                               f"The client is not asked to confirm excluding {excluded['id']}.",
                               "Add a question for the client that names the transaction."))
    return out


def check_uncategorized_have_questions(rule: Rule, ctx: CheckContext) -> list[dict]:
    out = []
    text = ctx.questions_text()
    for txn in ctx.data().get("transactions", []) or []:
        if str(txn.get("category", "")).lower().startswith("uncategorized") and txn["id"] not in text:
            out.append(finding(rule, "major", f"data.transactions[{txn['id']}]",
                               f"{txn['id']} is uncategorized and the client is not asked about it.",
                               "Add a question for the client that names the transaction."))
    return out


def check_large_unknown(rule: Rule, ctx: CheckContext) -> list[dict]:
    threshold = float(rule.check.get("amount", 5000))
    out = []
    for txn in ctx.data().get("transactions", []) or []:
        if abs(float(txn["amount"])) < threshold:
            continue
        category, _ = vendor_match(ctx.rules, ctx.job_type, ctx.client, txn["description"])
        if category is None and txn["id"] not in ctx.answers:
            out.append(finding(rule, "blocker", f"data.transactions[{txn['id']}]",
                               f"{txn['id']} ({money(float(txn['amount']))}) matches no rule and nobody answered "
                               "a question about it, so its category is a guess.",
                               "Stop and ask a human what it is before drafting."))
    return out


def check_vendor_category(rule: Rule, ctx: CheckContext) -> list[dict]:
    match, category = rule.check["match"].upper(), rule.check["category"]
    severity = rule.check.get("severity", "blocker")
    out = []
    for txn in ctx.data().get("transactions", []) or []:
        if match in str(txn.get("description", "")).upper() and txn.get("category") != category:
            out.append(finding(rule, severity, f"data.transactions[{txn['id']}].category",
                               f"{txn['id']} ({txn['description']}) is '{txn.get('category')}' but {rule.id} says "
                               f"'{category}'.", f"Set the category to '{category}'.",
                               transaction_id=txn["id"], expected_category=category))
    return out


def check_no_phrases(rule: Rule, ctx: CheckContext) -> list[dict]:
    text = ctx.message_text().lower()
    severity = rule.check.get("severity", "blocker")
    return [finding(rule, severity, "client_message", f"Client message contains '{phrase}'.",
                    f"Remove or rephrase '{phrase}' ({rule.title}).")
            for phrase in rule.check.get("phrases", []) if phrase.lower() in text]


def check_mask_numbers(rule: Rule, ctx: CheckContext) -> list[dict]:
    text = ctx.message_text()
    hits = SSN.findall(text) + ACCOUNT_NUMBER.findall(text)
    return [finding(rule, "blocker", "client_message", f"Unmasked number '{hit}' in the client message.",
                    "Show only the last 4 digits, e.g. ****1234.") for hit in hits]


def check_required_sections(rule: Rule, ctx: CheckContext) -> list[dict]:
    body = (ctx.deliverable.get("client_message", {}) or {}).get("body_markdown", "")
    return [finding(rule, rule.check.get("severity", "major"), "client_message.body_markdown",
                    f"Missing the '{section}' section.", f"Add a '## {section}' section.")
            for section in rule.check.get("sections", [])
            if not re.search(rf"^#+\s*{re.escape(section)}\b", body, flags=re.M | re.I)]


def check_signoff(rule: Rule, ctx: CheckContext) -> list[dict]:
    body = (ctx.deliverable.get("client_message", {}) or {}).get("body_markdown", "")
    text = rule.check.get("text", "")
    if text and text not in body:
        return [finding(rule, rule.check.get("severity", "minor"), "client_message.body_markdown",
                        f"Not signed '{text}'.", f"End the message with '{text}'.")]
    return []


def check_chase_format(rule: Rule, ctx: CheckContext) -> list[dict]:
    body = (ctx.deliverable.get("client_message", {}) or {}).get("body_markdown", "")
    out = []
    for item in ctx.data().get("missing", []) or []:
        label = item.get("label") or item["document"]
        if label not in body:
            out.append(finding(rule, "major", "client_message.body_markdown",
                               f"The message does not name the missing item '{label}'.",
                               "List every missing document by name."))
    max_words = int(rule.check.get("max_words", 180))
    words = len(body.split())
    if words > max_words:
        out.append(finding(rule, "minor", "client_message.body_markdown",
                           f"Chase message is {words} words (limit {max_words}).", "Shorten it."))
    return out


def _stated_amount(body: str, label: str) -> float | None:
    """The amount on a summary line like '- Net: -$1,234.50'."""
    pattern = rf"^\s*[-*]?\s*{re.escape(label)}:\s*(-?)\s*\$?\s*(-?)([\d,]+(?:\.\d+)?)"
    match = re.search(pattern, body, re.I | re.M)
    if not match:
        return None
    value = float(match.group(3).replace(",", ""))
    return -value if (match.group(1) or match.group(2)) else value


def check_message_totals(rule: Rule, ctx: CheckContext) -> list[dict]:
    """The numbers the client reads must be the numbers in the books."""
    txns = ctx.data().get("transactions")
    if not isinstance(txns, list):
        return []
    body = (ctx.deliverable.get("client_message", {}) or {}).get("body_markdown", "")
    amounts = [float(t["amount"]) for t in txns]
    truth = {"Money in": round(sum(a for a in amounts if a > 0), 2),
             "Money out": round(sum(-a for a in amounts if a < 0), 2),
             "Net": round(sum(amounts), 2)}
    out = []
    for label, value in truth.items():
        stated = _stated_amount(body, label)
        if stated is None:
            out.append(finding(rule, "major", "client_message.body_markdown", f"The Summary doesn't state '{label}'.",
                               f"Add '- {label}: {money(value)}'."))
        elif (abs(stated - value) if label == "Net" else abs(abs(stated) - value)) >= 0.005:
            out.append(finding(rule, "blocker", "client_message.body_markdown",
                               f"The message says {label} is {money(stated)} but the books say {money(value)}.",
                               f"Write {money(value)}."))
    ties = re.search(r"ties to your statement:\s*(yes|no)", body, re.I)
    status = (ctx.data().get("reconciliation") or {}).get("status")
    if ties and status and (ties.group(1).lower() == "yes") != (status == "tied"):
        out.append(finding(rule, "blocker", "client_message.body_markdown",
                           f"The message says the bank {'ties' if ties.group(1).lower() == 'yes' else 'does not tie'} "
                           f"but the reconciliation status is '{status}'.", "Make the message match the reconciliation."))
    return out


def check_period_matches(rule: Rule, ctx: CheckContext) -> list[dict]:
    """The books are for the job's month: statement, data and every transaction date agree."""
    period = ctx.period
    out = []
    data_period = ctx.data().get("period")
    statement_period = ctx.statement().get("period")
    for label, value in (("draft", data_period), ("bank statement", statement_period)):
        if period and value and value != period:
            out.append(finding(rule, "blocker", "data.period", f"The job is for {period} but the {label} is for {value}.",
                               "Use the documents for the job's month, or ask a person."))
    month = period or statement_period or data_period
    if month:
        strays = [t["id"] for t in ctx.data().get("transactions", []) or [] if not str(t.get("date", "")).startswith(month)]
        if strays:
            out.append(finding(rule, "blocker", "data.transactions",
                               f"{len(strays)} transaction(s) are dated outside {month}: {', '.join(strays[:5])}.",
                               "Only include the month's transactions, or ask a person."))
    return out


CHECKS: dict[str, Callable[[Rule, CheckContext], list[dict]]] = {
    "reconciliation_tied": check_reconciliation,
    "transactions_match_input": check_transactions_match_input,
    "exclusions_explained": check_exclusions_explained,
    "uncategorized_have_questions": check_uncategorized_have_questions,
    "large_unknown_escalation": check_large_unknown,
    "vendor_category": check_vendor_category,
    "no_phrases": check_no_phrases,
    "mask_numbers": check_mask_numbers,
    "required_sections": check_required_sections,
    "signoff": check_signoff,
    "chase_message_format": check_chase_format,
    "message_totals": check_message_totals,
    "period_matches": check_period_matches,
}
# Check types used by other stages (intake, preparer defaults) rather than review.
NON_REVIEW_CHECKS = {"document_checklist", "receipt_threshold", "vendor_map"}
assert set(CHECKS) | NON_REVIEW_CHECKS == KNOWN_CHECK_TYPES, "keep rules.KNOWN_CHECK_TYPES in step with CHECKS"


def run_checks(ws: Workspace, biz: Business, job_type: str, client: str | None, deliverable: dict,
               inputs: Path | None, answers: dict | None = None, rules: RuleSet | None = None,
               period: str | None = None) -> list[dict]:
    rules = rules or RuleSet.for_business(ws, biz)
    ctx = CheckContext(deliverable, inputs, answers or {}, rules, job_type, client, period)
    findings: list[dict] = []
    for rule in rules.for_job(job_type, client):
        check_type = (rule.check or {}).get("type")
        if check_type in CHECKS:
            findings.extend(CHECKS[check_type](rule, ctx))
    return findings


def score(findings: list[dict]) -> int:
    return max(0, 100 - sum(SEVERITY_COST.get(f.get("severity", "minor"), 3) for f in findings))


def verdict(findings: list[dict], pass_score: int = 80) -> str:
    if any(f.get("severity") == "blocker" for f in findings) or score(findings) < pass_score:
        return "BLOCK"
    return "PASS"
