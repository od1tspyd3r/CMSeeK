#!/usr/bin/python3
# -*- coding: utf-8 -*-

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Sequence, Tuple, Union


Path = Tuple[Union[str, int], ...]


@dataclass(frozen=True)
class DiffItem:
    kind: str  # 'added' | 'removed' | 'changed' | 'type_changed'
    path: Path
    old: Any
    new: Any

    @property
    def path_str(self) -> str:
        out = []
        for p in self.path:
            if isinstance(p, int):
                out.append(f"[{p}]")
            else:
                if not out:
                    out.append(str(p))
                else:
                    out.append(f".{p}")
        return "".join(out) if out else "(root)"


def _is_primitive(v: Any) -> bool:
    return v is None or isinstance(v, (str, int, float, bool))


def diff_json(old: Any, new: Any, path: Path = ()) -> List[DiffItem]:
    items: List[DiffItem] = []

    if old is new:
        return items

    if type(old) != type(new):
        items.append(DiffItem(kind="type_changed", path=path, old=old, new=new))
        return items

    if _is_primitive(old) and _is_primitive(new):
        if old != new:
            items.append(DiffItem(kind="changed", path=path, old=old, new=new))
        return items

    if isinstance(old, dict) and isinstance(new, dict):
        old_keys = set(old.keys())
        new_keys = set(new.keys())

        for k in sorted(old_keys - new_keys):
            items.append(DiffItem(kind="removed", path=path + (k,), old=old.get(k), new=None))
        for k in sorted(new_keys - old_keys):
            items.append(DiffItem(kind="added", path=path + (k,), old=None, new=new.get(k)))
        for k in sorted(old_keys & new_keys):
            items.extend(diff_json(old.get(k), new.get(k), path + (k,)))
        return items

    if isinstance(old, list) and isinstance(new, list):
        # Prefer stable diffing for lists of dicts that contain a "name" field (plugins/themes/users, etc).
        def _list_named_map(lst: list) -> Dict[str, Any]:
            m: Dict[str, Any] = {}
            for it in lst:
                if isinstance(it, dict) and isinstance(it.get("name"), str) and it["name"]:
                    m[it["name"]] = it
                else:
                    return {}
            return m

        old_named = _list_named_map(old)
        new_named = _list_named_map(new)
        if old_named and new_named:
            return diff_json(old_named, new_named, path)

        # Fallback: compare by index.
        max_len = max(len(old), len(new))
        for i in range(max_len):
            if i >= len(old):
                items.append(DiffItem(kind="added", path=path + (i,), old=None, new=new[i]))
            elif i >= len(new):
                items.append(DiffItem(kind="removed", path=path + (i,), old=old[i], new=None))
            else:
                items.extend(diff_json(old[i], new[i], path + (i,)))
        return items

    # Fallback for other types (should be rare in JSON)
    if old != new:
        items.append(DiffItem(kind="changed", path=path, old=old, new=new))
    return items


def summarize_diff(items: Sequence[DiffItem]) -> Dict[str, int]:
    out = {"added": 0, "removed": 0, "changed": 0, "type_changed": 0}
    for it in items:
        if it.kind in out:
            out[it.kind] += 1
    return out

