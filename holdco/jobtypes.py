"""What a finished deliverable must look like, per job type.

Every deliverable shares one envelope so the engine can diff, render and send
any of them:

    {
      "job_type": "monthly-close",
      "client": "acme",
      "client_message": {"subject": "...", "body_markdown": "..."},
      "data": { ...job-type specific... },
      "questions_for_client": ["..."],
      "rules_applied": ["BK-003", "R-DEMO-003"],
      "assumptions": ["..."]
    }

Add a job type by registering a JobType with a validator, the "material" view
used by regression tests, and any attachments it renders for the client.
"""

from __future__ import annotations

import copy
from collections import defaultdict
from pathlib import Path

from holdco.util import write_csv


class JobType:
    name = "generic"
    # Fields computed from other fields. They are recomputed on approval and
    # never logged as corrections (fixing a category is one correction, not
    # one per total that moved).
    derived_prefixes: tuple[str, ...] = ()

    def normalize(self, deliverable: dict) -> dict:
        return copy.deepcopy(deliverable)

    def validate(self, deliverable: dict) -> list[str]:
        errors = []
        if not isinstance(deliverable, dict):
            return ["deliverable must be a JSON object"]
        for key in ("job_type", "client", "client_message", "data"):
            if key not in deliverable:
                errors.append(f"missing '{key}'")
        message = deliverable.get("client_message")
        if message is not None:
            if not isinstance(message, dict):
                errors.append("'client_message' must be an object")
            else:
                for key in ("subject", "body_markdown"):
                    if not isinstance(message.get(key), str) or not message.get(key, "").strip():
                        errors.append(f"'client_message.{key}' must be non-empty text")
        if "data" in deliverable and not isinstance(deliverable["data"], dict):
            errors.append("'data' must be an object")
        for key in ("questions_for_client", "rules_applied", "assumptions"):
            if key in deliverable and not isinstance(deliverable[key], list):
                errors.append(f"'{key}' must be a list")
        return errors

    def material_view(self, deliverable: dict) -> dict:
        """The parts a regression test compares. Wording can change; facts cannot."""
        return {"data": deliverable.get("data", {})}

    def render_attachments(self, deliverable: dict, outdir: Path) -> list[str]:
        return []


class MonthlyClose(JobType):
    name = "monthly-close"
    derived_prefixes = ("data.summary", "data.reconciliation.computed_closing",
                        "data.reconciliation.difference", "data.reconciliation.status")

    def normalize(self, deliverable: dict) -> dict:
        out = copy.deepcopy(deliverable)
        data = out.get("data")
        if not isinstance(data, dict) or not isinstance(data.get("transactions"), list):
            return out
        txns = data["transactions"]
        spend: dict[str, float] = defaultdict(float)
        for t in txns:
            if float(t["amount"]) < 0:
                spend[t["category"]] += -float(t["amount"])
        data["summary"] = {
            "income": round(sum(float(t["amount"]) for t in txns if float(t["amount"]) > 0), 2),
            "expenses_by_category": {k: round(v, 2) for k, v in sorted(spend.items(), key=lambda kv: -kv[1])},
            "net": round(sum(float(t["amount"]) for t in txns), 2),
        }
        recon = data.get("reconciliation")
        if isinstance(recon, dict) and "opening_balance" in recon and "closing_balance" in recon:
            computed = round(float(recon["opening_balance"]) + data["summary"]["net"], 2)
            difference = round(float(recon["closing_balance"]) - computed, 2)
            recon.update(computed_closing=computed, difference=difference,
                         status="tied" if abs(difference) < 0.005 else "out_of_balance")
        return out

    def validate(self, deliverable: dict) -> list[str]:
        errors = super().validate(deliverable)
        data = deliverable.get("data") if isinstance(deliverable, dict) else None
        if not isinstance(data, dict):
            return errors
        transactions = data.get("transactions")
        if not isinstance(transactions, list):
            errors.append("'data.transactions' must be a list")
        else:
            for index, txn in enumerate(transactions):
                for key in ("id", "date", "description", "amount", "category"):
                    if not isinstance(txn, dict) or key not in txn:
                        errors.append(f"transaction #{index + 1} is missing '{key}'")
                        break
                else:
                    if not isinstance(txn["amount"], (int, float)):
                        errors.append(f"transaction {txn['id']}: amount must be a number")
        excluded = data.get("excluded", [])
        if not isinstance(excluded, list) or any(
            not isinstance(e, dict) or "id" not in e or not e.get("reason") for e in excluded
        ):
            errors.append("'data.excluded' must be a list of {id, reason}")
        recon = data.get("reconciliation")
        if not isinstance(recon, dict):
            errors.append("'data.reconciliation' must be an object")
        else:
            for key in ("opening_balance", "closing_balance", "computed_closing", "difference", "status"):
                if key not in recon:
                    errors.append(f"'data.reconciliation.{key}' is missing")
            if recon.get("status") not in ("tied", "out_of_balance"):
                errors.append("'data.reconciliation.status' must be 'tied' or 'out_of_balance'")
        if not isinstance(data.get("summary"), dict):
            errors.append("'data.summary' must be an object")
        return errors

    def material_view(self, deliverable: dict) -> dict:
        data = deliverable.get("data", {})
        return {
            "categories": {t["id"]: t["category"] for t in data.get("transactions", [])},
            "excluded": sorted(e["id"] for e in data.get("excluded", [])),
            "reconciliation": data.get("reconciliation", {}).get("status"),
        }

    def render_attachments(self, deliverable: dict, outdir: Path) -> list[str]:
        rows = deliverable.get("data", {}).get("transactions", [])
        write_csv(outdir / "transactions.csv", rows, ["id", "date", "description", "amount", "category"])
        return ["transactions.csv"]


class DocumentChase(JobType):
    name = "document-chase"

    def validate(self, deliverable: dict) -> list[str]:
        errors = super().validate(deliverable)
        data = deliverable.get("data") if isinstance(deliverable, dict) else None
        if isinstance(data, dict):
            missing = data.get("missing")
            if not isinstance(missing, list) or not missing:
                errors.append("'data.missing' must be a non-empty list of {document, reason}")
            elif any(not isinstance(m, dict) or not m.get("document") for m in missing):
                errors.append("every item in 'data.missing' needs a 'document'")
        return errors

    def material_view(self, deliverable: dict) -> dict:
        return {"missing": sorted(m["document"] for m in deliverable.get("data", {}).get("missing", []))}


REGISTRY: dict[str, JobType] = {t.name: t for t in (MonthlyClose(), DocumentChase())}


def get(job_type: str) -> JobType:
    return REGISTRY.get(job_type, JobType())


def validate(job_type: str, deliverable: dict) -> list[str]:
    errors = get(job_type).validate(deliverable)
    if isinstance(deliverable, dict) and deliverable.get("job_type") not in (None, job_type):
        errors.append(f"deliverable says job_type '{deliverable.get('job_type')}' but the job is '{job_type}'")
    return errors


def render_message(deliverable: dict) -> str:
    message = deliverable.get("client_message", {})
    return f"Subject: {message.get('subject', '')}\n\n{message.get('body_markdown', '').rstrip()}\n"
