"""Find Python modules that nothing imports.

A module is "orphan" if no other live .py file references it (by full path or
short name). Run from repo root:
    python tests/_dead_code_scan.py
"""
from __future__ import annotations
import ast
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXCLUDE = {".venv", ".git", "__pycache__", ".pytest_cache",
           "tessdata", "tesseract_bin", "doc", "trial_files",
           "data", "exports", "node_modules", "build", "dist",
           "tests/fixtures"}


def iter_py(root: Path):
    for dp, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in EXCLUDE]
        for fn in files:
            if fn.endswith(".py"):
                yield Path(dp) / fn


def module_name(p: Path) -> str:
    """Convert a file path into a Python module path (slash → dot)."""
    rel = p.relative_to(ROOT)
    parts = list(rel.parts)
    if parts[-1] == "__init__.py":
        parts = parts[:-1]
    else:
        parts[-1] = parts[-1][:-3]  # strip .py
    return ".".join(parts) if parts else ""


def main():
    files = list(iter_py(ROOT))
    file_to_mod = {p: module_name(p) for p in files}
    short_names = {p: p.stem for p in files if p.stem != "__init__"}

    # Collect every (importer, target) pair
    edges: list[tuple[Path, str]] = []
    for p in files:
        try:
            tree = ast.parse(p.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:
            continue
        for n in ast.walk(tree):
            if isinstance(n, ast.Import):
                for a in n.names:
                    edges.append((p, a.name))
            elif isinstance(n, ast.ImportFrom) and n.module and n.level == 0:
                edges.append((p, n.module))

    targets_referenced = {t for _, t in edges}

    # Orphans = files whose mod path or short stem isn't referenced anywhere
    orphans = []
    for p, mod in file_to_mod.items():
        if not mod:
            continue
        # Skip entry points (server.py is the runtime entry)
        if mod in {"core.api.server"}:
            continue
        # Skip __init__.py — they're loaded by package import
        if p.name == "__init__.py":
            continue
        # If any importer references this module path or any prefix,
        # it's used.
        used = False
        if mod in targets_referenced:
            used = True
        else:
            # Check if any importer references a longer path that includes us
            for tgt in targets_referenced:
                if tgt == mod or tgt.startswith(mod + "."):
                    used = True
                    break
            # Also check short-name imports (from x import name)
            stem = p.stem
            if stem in {tgt.split(".")[-1] for tgt in targets_referenced}:
                used = True
        if not used:
            orphans.append((p, mod))

    if not orphans:
        print("[CLEAN] No orphan modules found.")
        return

    print(f"Found {len(orphans)} orphan module(s) — nothing imports them:")
    for p, mod in sorted(orphans):
        try:
            size = p.stat().st_size
        except OSError:
            size = 0
        print(f"  {p.relative_to(ROOT)}  ({size}b, mod={mod})")


if __name__ == "__main__":
    main()
