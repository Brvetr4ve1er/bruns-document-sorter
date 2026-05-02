"""Form-side helpers: flatten nested JSON for editable rendering, and write
flat (path, value) pairs back into the nested structure.

The document detail page renders one input per leaf in the extracted JSON.
On save, the form posts back `f.path.to.field=value` pairs which need to be
folded back into a nested dict before re-serialising. These two helpers are
the inverses of each other.

Public API:
    flatten_for_form(obj, prefix='') -> list[tuple[str, scalar]]
    set_nested(target, path, value) -> None  (mutates target in place)
"""
from __future__ import annotations

import re

# Compiled once at module load. Splits "containers[0].size" into
# ["containers", "[0]", "size"].
_PATH_RE = re.compile(r"[^.\[\]]+|\[\d+\]")


def flatten_for_form(obj, prefix: str = "") -> list[tuple[str, object]]:
    """Walk a nested dict/list and yield (path, value) pairs for form rendering.

    Dict keys become dotted paths: {"a": {"b": 1}} -> [("a.b", 1)]
    List entries become indexed paths: {"c": [1, 2]} -> [("c[0]", 1), ("c[1]", 2)]
    Schema-comment keys (those starting with '_') are dropped — they're prompt
    annotations, not real data.
    """
    out: list[tuple[str, object]] = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(k, str) and k.startswith("_"):
                continue
            sub = f"{prefix}.{k}" if prefix else k
            out.extend(flatten_for_form(v, sub))
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            sub = f"{prefix}[{i}]"
            out.extend(flatten_for_form(item, sub))
    else:
        out.append((prefix, obj))
    return out


def set_nested(target: dict, path: str, value) -> None:
    """Set `value` on `target` at the given dotted/indexed path.

    Creates intermediate dicts/lists as needed by looking ahead to the next
    path part: if the next part is "[N]" we create a list, otherwise a dict.
    Mutates `target` in place.

    Examples:
        set_nested(d, "a.b", 1)        -> d == {"a": {"b": 1}}
        set_nested(d, "c[0].x", 2)     -> d == {"c": [{"x": 2}]}
    """
    parts = _PATH_RE.findall(path)
    cur = target
    for i, p in enumerate(parts):
        is_last = (i == len(parts) - 1)
        # Look ahead: the next part determines whether we need a list or dict
        # for the auto-created intermediate container.
        next_is_index = (
            not is_last
            and parts[i + 1].startswith("[")
            and parts[i + 1].endswith("]")
        )

        if p.startswith("[") and p.endswith("]"):
            idx = int(p[1:-1])
            # `cur` MUST be a list here — caller bug if it isn't.
            while isinstance(cur, list) and len(cur) <= idx:
                cur.append({})
            if is_last:
                cur[idx] = value
            else:
                child_needed: object = [] if next_is_index else {}
                if not isinstance(cur[idx], (dict, list)):
                    cur[idx] = child_needed
                cur = cur[idx]
        else:
            if is_last:
                cur[p] = value
            else:
                if p not in cur or not isinstance(cur[p], (dict, list)):
                    cur[p] = [] if next_is_index else {}
                cur = cur[p]
