"""Small shared helpers: JSON files, hashing, and an overridable clock."""

from __future__ import annotations

import csv
import datetime as dt
import hashlib
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any, Callable, Iterable

_clock: Callable[[], dt.datetime] = lambda: dt.datetime.now(dt.timezone.utc)


def now() -> dt.datetime:
    return _clock()


def now_iso() -> str:
    return now().replace(microsecond=0).isoformat()


def set_clock(fn: Callable[[], dt.datetime]) -> None:
    """Override the clock (the demo and tests use a fixed, advancing clock)."""
    global _clock
    _clock = fn


def freeze_clock(iso: str) -> None:
    moment = dt.datetime.fromisoformat(iso)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=dt.timezone.utc)
    set_clock(lambda: moment)


def reset_clock() -> None:
    set_clock(lambda: dt.datetime.now(dt.timezone.utc))


def parse_date(value: str) -> dt.date:
    return dt.date.fromisoformat(value[:10])


def read_json(path: Path | str) -> Any:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def write_json(path: Path | str, data: Any) -> None:
    """Write JSON atomically so a crash never leaves a half-written state file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".tmp-", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, ensure_ascii=False)
            fh.write("\n")
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def append_jsonl(path: Path | str, record: dict) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")


def read_jsonl(path: Path | str) -> list[dict]:
    path = Path(path)
    if not path.exists():
        return []
    out = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def read_csv(path: Path | str) -> list[dict]:
    path = Path(path)
    if not path.exists():
        return []
    with open(path, newline="", encoding="utf-8") as fh:
        return [
            {k.strip(): (v.strip() if isinstance(v, str) else v) for k, v in row.items() if k}
            for row in csv.DictReader(fh)
        ]


def write_csv(path: Path | str, rows: Iterable[dict], fieldnames: list[str]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def canonical_json(data: Any) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_json(data: Any) -> str:
    return hashlib.sha256(canonical_json(data).encode("utf-8")).hexdigest()


def sha256_file(path: Path | str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def hash_tree(folder: Path | str) -> dict:
    """sha256 of every file under a folder, keyed by relative path."""
    folder = Path(folder)
    if not folder.is_dir():
        return {}
    return {p.relative_to(folder).as_posix(): sha256_file(p)
            for p in sorted(folder.rglob("*")) if p.is_file()}


def next_id(prefix: str, existing: Iterable[str], width: int = 4) -> str:
    """PREFIX-NNNN, one more than the highest existing number (safe after deletions)."""
    numbers = [int(m.group(1)) for e in existing if (m := re.match(rf"^{re.escape(prefix)}-(\d+)$", e))]
    return f"{prefix}-{(max(numbers) + 1) if numbers else 1:0{width}d}"


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def money(value: float) -> str:
    sign = "-" if value < 0 else ""
    return f"{sign}${abs(value):,.2f}"


def pct(value: float | None, digits: int = 1) -> str:
    return "n/a" if value is None else f"{value * 100:.{digits}f}%"
