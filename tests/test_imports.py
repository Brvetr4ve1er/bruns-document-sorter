"""Layer-rule enforcement: prevents architectural drift.

This test scans every .py file in the live codebase and checks that no module
imports across a forbidden boundary, per docs/ARCHITECTURE.md.

If this test fails, EITHER fix the import OR — if the layer rules themselves
need to change — update both this test AND docs/ARCHITECTURE.md in the same
commit. Don't silently relax rules.
"""
from __future__ import annotations

import ast
import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

# Forbidden cross-package imports.
#   key   = source top-level package (where the import lives)
#   value = set of target top-level packages it must NOT import
# Layer rules — Streamlit + legacy paths fully decommissioned.
# `core/api/server.py` is now the single UI surface (Flask + HTMX).
#
# Layers (top → bottom):
#   core.api  →  may import modules/, core/, anything below
#   modules   →  may import core/ (excluding core.api)
#   core      →  the engine; may NOT reach modules/ or core.api
FORBIDDEN: dict[str, set[str]] = {
    "core.api": set(),                # top of the stack — no restrictions
    "core":     {"modules"},          # engine cannot reach into domain logic
    "modules":  set(),                # may import core/, plus its own submodules
    "tests":    set(),                # tests may import anything
    "config":   {"modules", "core"},  # config is a leaf
}

# Tags that should never appear anywhere — stale references to deleted folders.
GHOST_TARGETS: set[str] = {
    "streamlit", "logistics_app", "travel_app", "ui", "_legacy", "components",
}

# No special root-file rules anymore — app.py at root is gone.
ROOT_FILE_FORBIDDEN: set[str] = set()

# Directories the scan walks but ignores entirely.
EXCLUDE_DIRS = {
    ".venv", ".git", "__pycache__", ".pytest_cache",
    "tessdata", "tesseract_bin", "doc", "trial_files",
    "data", "exports", "node_modules", "build", "dist",
}


def _first_segment(name: str | None) -> str:
    if not name:
        return ""
    return name.split(".", 1)[0]


def _iter_py_files():
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS]
        for fn in filenames:
            if fn.endswith(".py"):
                yield Path(dirpath) / fn


def _file_top_pkg(path: Path) -> str:
    """Return the layer this file belongs to.

    `core/api/*` is treated as its own layer (the UI/Flask layer), distinct
    from the engine in `core/<other>/*`. This matches docs/ARCHITECTURE.md:
    `core.api` is the top of the stack and may reach into `modules/`, while
    pure engine code under `core/` may not.
    """
    rel = path.relative_to(ROOT)
    parts = rel.parts
    if len(parts) <= 1:
        return "<root>"
    if parts[0] == "core" and len(parts) >= 2 and parts[1] == "api":
        return "core.api"
    return parts[0]


def _imports_in(path: Path):
    """Yield (target_top_pkg, lineno) for every import in the file."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    except SyntaxError:
        return
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield _first_segment(alias.name), node.lineno
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and node.module:
                yield _first_segment(node.module), node.lineno


def test_no_forbidden_imports():
    """Every .py file in live code respects the layer rules in
    docs/ARCHITECTURE.md."""
    violations: list[str] = []

    for py in _iter_py_files():
        src_pkg = _file_top_pkg(py)
        rel = py.relative_to(ROOT)

        if src_pkg == "<root>":
            forbidden = ROOT_FILE_FORBIDDEN
        else:
            forbidden = FORBIDDEN.get(src_pkg, set())

        for target, lineno in _imports_in(py):
            if target in forbidden:
                violations.append(
                    f"{rel}:{lineno}  [{src_pkg}] -> [{target}]  (forbidden)"
                )
            if target in GHOST_TARGETS:
                violations.append(
                    f"{rel}:{lineno}  imports DELETED package [{target}] — clean up the import"
                )

    if violations:
        msg = (
            "Layer-rule violations (see docs/ARCHITECTURE.md):\n  "
            + "\n  ".join(violations)
        )
        pytest.fail(msg)


def test_legacy_folder_is_isolated():
    """Sanity check: _legacy/ may exist but no live file may import it."""
    legacy_root = ROOT / "_legacy"
    if not legacy_root.exists():
        pytest.skip("_legacy/ not yet created")

    bad: list[str] = []
    for py in _iter_py_files():
        rel = py.relative_to(ROOT)
        for target, lineno in _imports_in(py):
            if target == "_legacy":
                bad.append(f"{rel}:{lineno} imports _legacy")
    assert not bad, "Live code imports _legacy:\n  " + "\n  ".join(bad)
