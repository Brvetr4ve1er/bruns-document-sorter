"""One-shot import graph scanner. Run from repo root: python tests/_import_scan.py

Walks every .py file under the repo (excluding .venv, _legacy, __pycache__, .git, tests/
itself), parses imports, and prints a flat table of cross-package edges:

    <source_pkg>  ->  <target_pkg>      (count)   [first_file:line]

Used to bootstrap docs/ARCHITECTURE.md and to find any code that still imports the
legacy `logistics_app` / `travel_app` / `components` packages.
"""
from __future__ import annotations
import ast
import os
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Top-level packages we care about for layer rules.
TRACKED_PKGS = {
    "core", "modules", "ui", "config",
    "logistics_app", "travel_app", "components",
    "agents", "parsers", "models", "database_logic", "utils",  # legacy roots
}

EXCLUDE_DIRS = {".venv", ".git", "__pycache__", "_legacy", ".pytest_cache",
                "tessdata", "tesseract_bin", "doc", "trial  files to process",
                ".streamlit", "data", "exports", "node_modules"}


def iter_py_files(root: Path):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS]
        for fn in filenames:
            if fn.endswith(".py"):
                yield Path(dirpath) / fn


def first_segment(name: str) -> str:
    return name.split(".", 1)[0] if name else ""


def file_pkg(path: Path) -> str:
    """Return the top-level package the file belongs to, or '<root>' if at repo root."""
    rel = path.relative_to(ROOT)
    parts = rel.parts
    return parts[0] if len(parts) > 1 else "<root>"


def main():
    edges: dict[tuple[str, str], list[str]] = defaultdict(list)
    files_scanned = 0
    parse_errors = []

    for py in iter_py_files(ROOT):
        try:
            tree = ast.parse(py.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError as e:
            parse_errors.append((py, str(e)))
            continue
        files_scanned += 1
        src_pkg = file_pkg(py)
        rel = py.relative_to(ROOT)

        for node in ast.walk(tree):
            mod = None
            if isinstance(node, ast.Import):
                for alias in node.names:
                    mod = first_segment(alias.name)
                    if mod in TRACKED_PKGS and mod != src_pkg:
                        edges[(src_pkg, mod)].append(f"{rel}:{node.lineno}")
            elif isinstance(node, ast.ImportFrom):
                if node.level == 0 and node.module:
                    mod = first_segment(node.module)
                    if mod in TRACKED_PKGS and mod != src_pkg:
                        edges[(src_pkg, mod)].append(f"{rel}:{node.lineno}")

    print(f"Scanned {files_scanned} .py files under {ROOT}")
    if parse_errors:
        print(f"\n[!] {len(parse_errors)} parse errors:")
        for p, msg in parse_errors:
            print(f"    {p}: {msg}")

    print("\n=== CROSS-PACKAGE IMPORT EDGES ===")
    print(f"{'SOURCE':<22}-> {'TARGET':<22} {'CNT':>4}   FIRST-OCCURRENCE")
    print("-" * 90)
    for (src, tgt), locs in sorted(edges.items()):
        print(f"{src:<22}-> {tgt:<22} {len(locs):>4}   {locs[0]}")

    print("\n=== LEGACY-PKG IMPORTERS (must be fixed before quarantine) ===")
    legacy = {"logistics_app", "travel_app", "components",
              "agents", "parsers", "models", "database_logic", "utils"}
    found_any = False
    for (src, tgt), locs in sorted(edges.items()):
        if tgt in legacy and src not in legacy:
            found_any = True
            print(f"  [{src}] imports legacy [{tgt}] from:")
            for l in locs:
                print(f"      {l}")
    if not found_any:
        print("  (none — safe to quarantine all legacy packages)")


if __name__ == "__main__":
    main()
