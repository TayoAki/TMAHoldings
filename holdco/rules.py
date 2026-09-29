"""Plain-English rules with optional machine checks.

Rules live in Markdown so people and agents read the same text:

    ## R-DEMO-003 · Acme: Greenleaf Nursery purchases are Materials (COGS)
    - **Applies to:** monthly-close
    - **Scope:** client:acme
    - **Rule:** Categorize any transaction containing "GREENLEAF NURSERY" as "Materials (COGS)".
    - **Why:** Acme resells plants and materials to its customers.
    - **Check:** `{"type": "vendor_category", "match": "GREENLEAF NURSERY", "category": "Materials (COGS)"}`

Layers, most specific first: client-scoped business rules, business rules,
industry rules, global rules. Non-negotiable rules can never be overridden.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from holdco.config import Business, HoldcoError, Workspace

HEADING = re.compile(r"^##\s+([A-Z][A-Z0-9]*(?:-[A-Z0-9]+)+)\s*(?:·|—|-|:)\s*(.+?)\s*$")
FIELD = re.compile(r"^\s*[-*]\s+\*\*([^*]+?):\*\*\s*(.*)$")
LAYER_ORDER = {"client": 0, "business": 1, "industry": 2, "global": 3}


@dataclass
class Rule:
    id: str
    title: str
    layer: str
    source_file: str
    fields: dict = field(default_factory=dict)
    check: dict | None = None

    @property
    def text(self) -> str:
        return self.fields.get("Rule", "")

    @property
    def applies_to(self) -> list[str]:
        raw = self.fields.get("Applies to", "all")
        return [part.strip().lower() for part in raw.split(",") if part.strip()] or ["all"]

    @property
    def scope(self) -> str:
        return self.fields.get("Scope", "all").strip().lower()

    @property
    def client(self) -> str | None:
        return self.scope.split(":", 1)[1].strip() if self.scope.startswith("client:") else None

    @property
    def non_negotiable(self) -> bool:
        return self.fields.get("Non-negotiable", "").strip().lower() in {"yes", "true"}

    @property
    def precedence(self) -> int:
        return LAYER_ORDER["client"] if self.client else LAYER_ORDER[self.layer]

    def applies(self, job_type: str, client: str | None) -> bool:
        if "all" not in self.applies_to and job_type.lower() not in self.applies_to:
            return False
        if self.client and self.client != (client or "").lower():
            return False
        return True


def parse_rules(text: str, layer: str, source_file: str = "") -> list[Rule]:
    rules: list[Rule] = []
    current: Rule | None = None
    last_field: str | None = None
    for line in text.splitlines():
        heading = HEADING.match(line)
        if heading:
            current = Rule(id=heading.group(1), title=heading.group(2), layer=layer, source_file=source_file)
            rules.append(current)
            last_field = None
            continue
        if line.startswith("#"):
            current, last_field = None, None
            continue
        if current is None:
            continue
        match = FIELD.match(line)
        if match:
            last_field = match.group(1).strip()
            current.fields[last_field] = match.group(2).strip()
        elif last_field and line.strip():
            current.fields[last_field] += "\n" + line.strip()
    for rule in rules:
        raw = rule.fields.get("Check")
        if raw:
            rule.check = _parse_check(rule.id, raw)
    seen: set[str] = set()
    for rule in rules:
        if rule.id in seen:
            raise HoldcoError(f"Duplicate rule id {rule.id} in {source_file or layer} rules.")
        seen.add(rule.id)
    return rules


def _parse_check(rule_id: str, raw: str) -> dict:
    body = raw.strip().strip("`").strip()
    try:
        check = json.loads(body)
    except json.JSONDecodeError as exc:
        raise HoldcoError(f"Rule {rule_id}: the Check field is not valid JSON ({exc}).") from exc
    if not isinstance(check, dict) or "type" not in check:
        raise HoldcoError(f'Rule {rule_id}: the Check field needs an object with a "type".')
    return check


def load_file(path: Path | None, layer: str) -> list[Rule]:
    if path is None or not path.exists():
        return []
    return parse_rules(path.read_text(encoding="utf-8"), layer, str(path))


@dataclass
class RuleSet:
    rules: list[Rule]

    @classmethod
    def for_business(cls, ws: Workspace, biz: Business, exclude: set[str] | None = None) -> "RuleSet":
        rules = (
            load_file(ws.global_rules_file, "global")
            + load_file(ws.industry_rules_file(biz.industry), "industry")
            + load_file(biz.rules_file, "business")
        )
        ids = [r.id for r in rules]
        dupes = {i for i in ids if ids.count(i) > 1}
        if dupes:
            raise HoldcoError(f"Rule ids used in more than one layer: {', '.join(sorted(dupes))}")
        exclude = exclude or set()
        return cls([r for r in rules if r.id not in exclude])

    def for_job(self, job_type: str, client: str | None) -> list[Rule]:
        """Applicable rules, most specific first (stable within a layer)."""
        applicable = [r for r in self.rules if r.applies(job_type, client)]
        return sorted(applicable, key=lambda r: r.precedence)

    def checks(self, job_type: str, client: str | None, check_type: str) -> list[Rule]:
        return [r for r in self.for_job(job_type, client) if r.check and r.check["type"] == check_type]

    def get(self, rule_id: str) -> Rule | None:
        return next((r for r in self.rules if r.id == rule_id), None)


FIELD_ORDER = ["Applies to", "Scope", "Non-negotiable", "Rule", "Why", "Check", "Source", "Added"]


def render_rule(rule_id: str, title: str, fields: dict, check: dict | None = None) -> str:
    lines = [f"## {rule_id} · {title}"]
    merged = dict(fields)
    if check:
        merged["Check"] = f"`{json.dumps(check, ensure_ascii=False)}`"
    for key in FIELD_ORDER + [k for k in merged if k not in FIELD_ORDER]:
        if merged.get(key):
            lines.append(f"- **{key}:** {merged[key]}")
    return "\n".join(lines) + "\n"


def next_rule_id(biz: Business) -> str:
    prefix = biz.setting("rule_prefix") or "R-" + biz.slug.upper().replace("-", "")[:8]
    text = biz.rules_file.read_text(encoding="utf-8") if biz.rules_file.exists() else ""
    numbers = [int(n) for n in re.findall(rf"^##\s+{re.escape(prefix)}-(\d+)", text, flags=re.M)]
    return f"{prefix}-{(max(numbers) + 1) if numbers else 1:03d}"


def append_rule(biz: Business, markdown: str) -> None:
    existing = biz.rules_file.read_text(encoding="utf-8") if biz.rules_file.exists() else f"# Rules — {biz.name}\n"
    if not existing.endswith("\n"):
        existing += "\n"
    biz.rules_file.write_text(existing + "\n" + markdown, encoding="utf-8")
