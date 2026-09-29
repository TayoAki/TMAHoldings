"""Field-level diffs between an agent draft and the version a person approved.

Every difference becomes one candidate correction. Lists of objects that carry
an ``id`` are matched by id, so ``data.transactions[T-0602].category`` stays
stable no matter how the list is ordered. Long text is split into line hunks
so each edit can be categorized on its own.
"""

from __future__ import annotations

import copy
import difflib
import json
import re
from dataclasses import dataclass, field
from typing import Any

from holdco.config import HoldcoError

TOKEN = re.compile(r"([^.\[\]]+)|\[([^\]]+)\]")


@dataclass
class Change:
    path: str
    before: Any
    after: Any
    context: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"path": self.path, "before": self.before, "after": self.after, "context": self.context}

    def describe(self) -> str:
        where = self.path
        if self.context:
            bits = [str(self.context[k]) for k in ("description", "date", "amount") if k in self.context]
            if bits:
                where += f"  ({', '.join(bits)})"
        return f"{where}: {_short(self.before)} -> {_short(self.after)}"


def _short(value: Any, limit: int = 70) -> str:
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    text = text.replace("\n", " / ")
    return text if len(text) <= limit else text[: limit - 3] + "..."


def _id_keyed(items: list) -> bool:
    return bool(items) and all(isinstance(i, dict) and "id" in i for i in items)


def _equal(a: Any, b: Any) -> bool:
    if isinstance(a, (int, float)) and isinstance(b, (int, float)) and not isinstance(a, bool):
        return abs(a - b) < 1e-9
    return a == b


def _item_context(item: dict) -> dict:
    return {k: v for k, v in item.items() if isinstance(v, (str, int, float, bool)) or v is None}


def diff(before: Any, after: Any, path: str = "") -> list[Change]:
    changes: list[Change] = []
    if isinstance(before, dict) and isinstance(after, dict):
        for key in list(before) + [k for k in after if k not in before]:
            sub = f"{path}.{key}" if path else str(key)
            if key not in before:
                changes.append(Change(sub, None, after[key]))
            elif key not in after:
                changes.append(Change(sub, before[key], None))
            else:
                changes.extend(diff(before[key], after[key], sub))
    elif isinstance(before, list) and isinstance(after, list):
        if _id_keyed(before) or _id_keyed(after):
            if not all(isinstance(i, dict) and "id" in i for i in before + after):
                return [Change(path, before, after)] if before != after else []
            b = {str(i["id"]): i for i in before}
            a = {str(i["id"]): i for i in after}
            for key in list(b) + [k for k in a if k not in b]:
                sub = f"{path}[{key}]"
                if key not in b:
                    changes.append(Change(sub, None, a[key], _item_context(a[key])))
                elif key not in a:
                    changes.append(Change(sub, b[key], None, _item_context(b[key])))
                else:
                    for change in diff(b[key], a[key], sub):
                        change.context = change.context or _item_context(b[key])
                        changes.append(change)
        elif len(before) == len(after) and any(isinstance(i, (dict, list)) for i in before + after):
            for index, (x, y) in enumerate(zip(before, after)):
                changes.extend(diff(x, y, f"{path}[{index}]"))
        elif before != after:
            changes.append(Change(path, before, after))
    elif isinstance(before, str) and isinstance(after, str) and ("\n" in before or "\n" in after):
        changes.extend(_text_hunks(before, after, path))
    elif not _equal(before, after):
        changes.append(Change(path, before, after))
    return changes


def _text_hunks(before: str, after: str, path: str) -> list[Change]:
    b_lines, a_lines = before.splitlines(), after.splitlines()
    out = []
    matcher = difflib.SequenceMatcher(a=b_lines, b=a_lines, autojunk=False)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        out.append(
            Change(
                f"{path}#L{i1 + 1}",
                "\n".join(b_lines[i1:i2]) or None,
                "\n".join(a_lines[j1:j2]) or None,
            )
        )
    return out


def parse_path(path: str) -> list[tuple[str, str]]:
    tokens = []
    for name, selector in TOKEN.findall(path.split("#", 1)[0]):
        tokens.append(("key", name) if name else ("sel", selector))
    if not tokens:
        raise HoldcoError(f"Empty path: {path!r}")
    return tokens


def _select(container: Any, token: tuple[str, str], path: str) -> Any:
    kind, value = token
    if kind == "key":
        if not isinstance(container, dict) or value not in container:
            raise HoldcoError(f"Path {path!r}: no field {value!r}.")
        return container[value]
    if not isinstance(container, list):
        raise HoldcoError(f"Path {path!r}: [{value}] used on something that is not a list.")
    for item in container:
        if isinstance(item, dict) and str(item.get("id")) == value:
            return item
    if value.isdigit() and int(value) < len(container):
        return container[int(value)]
    raise HoldcoError(f"Path {path!r}: no item with id {value!r}.")


def set_path(data: Any, path: str, value: Any) -> Any:
    """Return a copy of ``data`` with ``path`` set to ``value`` (used by approve --set)."""
    result = copy.deepcopy(data)
    tokens = parse_path(path)
    target = result
    for token in tokens[:-1]:
        target = _select(target, token, path)
    kind, last = tokens[-1]
    if kind == "key":
        if not isinstance(target, dict):
            raise HoldcoError(f"Path {path!r}: cannot set a field on a non-object.")
        target[last] = value
    else:
        raise HoldcoError(f"Path {path!r}: must end in a field name, not [{last}].")
    return result


def get_path(data: Any, path: str) -> Any:
    target = data
    for token in parse_path(path):
        target = _select(target, token, path)
    return target


def coerce_value(raw: str) -> Any:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw
