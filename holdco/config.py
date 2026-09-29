"""Where things live: the holdco workspace, its shared layer, and each business."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from holdco.util import read_json

TEMPLATE_SLUG = "_template"
SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,120}$")


class HoldcoError(Exception):
    """A problem the operator can fix (bad input, missing file, wrong state)."""


def safe_id(value: str, what: str) -> str:
    """Ids become folder names: letters, digits, dot, dash, underscore; no path tricks."""
    if not isinstance(value, str) or not SAFE_ID.match(value) or ".." in value:
        raise HoldcoError(f"{what} {value!r} is not allowed: use letters, digits, '.', '-' or '_' "
                          "(no slashes, no leading dot, no '..').")
    return value


def find_root(start: Path | None = None) -> Path:
    """Locate the workspace: --root / HOLDCO_ROOT, else walk up to a dir with shared/ and businesses/."""
    env = os.environ.get("HOLDCO_ROOT")
    if env:
        return Path(env).resolve()
    here = (start or Path.cwd()).resolve()
    for candidate in [here, *here.parents]:
        if (candidate / "shared").is_dir() and (candidate / "businesses").is_dir():
            return candidate
    return here


@dataclass
class Business:
    slug: str
    dir: Path
    config: dict = field(default_factory=dict)

    @property
    def name(self) -> str:
        return self.config.get("name", self.slug)

    @property
    def industry(self) -> str | None:
        return self.config.get("industry")

    @property
    def is_demo(self) -> bool:
        return bool(self.config.get("demo"))

    @property
    def gm(self) -> str | None:
        return self.config.get("gm")

    @property
    def approvers(self) -> list[str]:
        return list(self.config.get("approvers", []))

    @property
    def owners(self) -> list[str]:
        return list(self.config.get("owners", []))

    @property
    def jobs_dir(self) -> Path:
        return self.dir / "jobs"

    @property
    def outbox_dir(self) -> Path:
        return self.dir / "outbox"

    @property
    def golden_dir(self) -> Path:
        return self.dir / "golden"

    @property
    def proposals_dir(self) -> Path:
        return self.dir / "proposals"

    @property
    def corrections_log(self) -> Path:
        return self.dir / "corrections-log.jsonl"

    @property
    def rules_file(self) -> Path:
        return self.dir / "rules.md"

    @property
    def clients_csv(self) -> Path:
        return self.dir / "clients.csv"

    @property
    def pulse_csv(self) -> Path:
        return self.dir / "pulse.csv"

    @property
    def financials_csv(self) -> Path:
        return self.dir / "financials.csv"

    def setting(self, key: str, default=None):
        return self.config.get(key, default)


@dataclass
class Workspace:
    root: Path

    def __post_init__(self) -> None:
        self.root = Path(self.root).resolve()

    @property
    def businesses_dir(self) -> Path:
        return self.root / "businesses"

    @property
    def shared_dir(self) -> Path:
        return self.root / "shared"

    @property
    def global_rules_file(self) -> Path:
        return self.shared_dir / "rules" / "global-rules.md"

    def industry_rules_file(self, industry: str | None) -> Path | None:
        if not industry:
            return None
        return self.shared_dir / "rules" / "industries" / f"{industry}.md"

    @property
    def buy_box_file(self) -> Path:
        return self.root / "thesis" / "buy-box.json"

    def business(self, slug: str) -> Business:
        directory = self.businesses_dir / safe_id(slug, "Business")
        config_path = directory / "business.json"
        if not config_path.exists():
            known = ", ".join(b.slug for b in self.list_businesses()) or "none yet"
            raise HoldcoError(f"No business '{slug}' in {self.businesses_dir} (known: {known}).")
        return Business(slug=slug, dir=directory, config=read_json(config_path))

    def list_businesses(self) -> list[Business]:
        if not self.businesses_dir.is_dir():
            return []
        out = []
        for child in sorted(self.businesses_dir.iterdir()):
            if child.name.startswith((".", "_")) or not (child / "business.json").exists():
                continue
            out.append(Business(slug=child.name, dir=child, config=read_json(child / "business.json")))
        return out
