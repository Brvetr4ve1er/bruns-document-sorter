"""Find every third-party top-level package the LIVE codebase actually imports.
Run from repo root: python tests/_third_party_scan.py
"""
from __future__ import annotations
import ast
import os
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXCLUDE = {".venv", ".git", "__pycache__", "_legacy", ".pytest_cache",
           "tessdata", "tesseract_bin", "doc", "trial  files to process",
           ".streamlit", "data", "exports", "node_modules", "build", "dist",
           "tests"}
INTERNAL = {"core", "modules", "ui", "config", "app", "tests"}
STDLIB = set(sys.stdlib_module_names)

counts = Counter()
locs: dict[str, list[str]] = {}

for dp, dirs, files in os.walk(ROOT):
    dirs[:] = [d for d in dirs if d not in EXCLUDE]
    for fn in files:
        if not fn.endswith(".py"):
            continue
        p = Path(dp) / fn
        try:
            tree = ast.parse(p.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:
            continue
        rel = p.relative_to(ROOT)
        for node in ast.walk(tree):
            mod = None
            if isinstance(node, ast.Import):
                for alias in node.names:
                    mod = alias.name.split(".", 1)[0]
                    if mod and mod not in STDLIB and mod not in INTERNAL:
                        counts[mod] += 1
                        locs.setdefault(mod, []).append(f"{rel}:{node.lineno}")
            elif isinstance(node, ast.ImportFrom):
                if node.level == 0 and node.module:
                    mod = node.module.split(".", 1)[0]
                    if mod and mod not in STDLIB and mod not in INTERNAL:
                        counts[mod] += 1
                        locs.setdefault(mod, []).append(f"{rel}:{node.lineno}")

print(f"{'PACKAGE':<25} {'COUNT':>5}   FIRST USE")
print("-" * 80)
for mod, cnt in sorted(counts.items()):
    print(f"{mod:<25} {cnt:>5}   {locs[mod][0]}")
