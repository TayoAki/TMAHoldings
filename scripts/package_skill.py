#!/usr/bin/env python3
"""Package the ai-rollup-holdco skill for upload to claude.ai (Settings > Capabilities > Skills).

    python3 scripts/package_skill.py            # writes dist/ai-rollup-holdco.skill

Inside the repo, the skill reads the canonical files directly (docs/, shared/, thesis/).
The packaged copy bundles those same files under references/ with the same paths, so a
reference like `docs/PLAYBOOK.md` becomes `references/docs/PLAYBOOK.md`.
"""

from __future__ import annotations

import re
import sys
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SKILL = REPO / ".claude" / "skills" / "ai-rollup-holdco"
BUNDLE = [
    "TODO.md",
    "docs/PLAYBOOK.md",
    "docs/VIDEO-REVIEW.md",
    "thesis/THESIS.md",
    "thesis/buy-box.json",
    "thesis/deals/example-target.json",
    "shared/agents/*.md",
    "shared/rules/*.md",
    "shared/rules/industries/*.md",
    "shared/job-types/*.md",
    "shared/runbooks/*.md",
]


def validate(skill_md: Path) -> list[str]:
    """The same checks claude.ai applies on upload (see skill-creator's quick_validate)."""
    text = skill_md.read_text(encoding="utf-8")
    match = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not match:
        return ["SKILL.md needs YAML frontmatter"]
    fields = dict(re.findall(r"^([a-z-]+):\s*(.*)$", match.group(1), re.M))
    errors = []
    unexpected = set(fields) - {"name", "description", "license", "allowed-tools", "metadata", "compatibility"}
    if unexpected:
        errors.append(f"unexpected frontmatter keys: {sorted(unexpected)}")
    name, description = fields.get("name", ""), fields.get("description", "")
    if not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", name) or len(name) > 64:
        errors.append(f"name must be kebab-case and at most 64 characters (got {name!r})")
    if not description or len(description) > 1024:
        errors.append(f"description must be 1-1024 characters (got {len(description)})")
    if "<" in description or ">" in description:
        errors.append("description cannot contain angle brackets")
    return errors


def main() -> int:
    errors = validate(SKILL / "SKILL.md")
    if errors:
        print("Not packaged:\n  " + "\n  ".join(errors))
        return 1
    files: dict[str, Path] = {}
    for path in sorted(SKILL.rglob("*")):
        if path.is_file() and "__pycache__" not in path.parts:
            files[f"{SKILL.name}/{path.relative_to(SKILL).as_posix()}"] = path
    missing = []
    for pattern in BUNDLE:
        matches = sorted(REPO.glob(pattern))
        if not matches:
            missing.append(pattern)
        for path in matches:
            files[f"{SKILL.name}/references/{path.relative_to(REPO).as_posix()}"] = path
    if missing:
        print("Not packaged: missing " + ", ".join(missing))
        return 1
    if sum(1 for name in files if name.endswith("/SKILL.md")) != 1:
        print("Not packaged: a skill must contain exactly one SKILL.md")
        return 1
    out = REPO / "dist" / f"{SKILL.name}.skill"
    out.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, path in files.items():
            zf.write(path, name)
    print(f"Packaged {len(files)} files into {out.relative_to(REPO)}. Upload it in claude.ai under Skills.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
