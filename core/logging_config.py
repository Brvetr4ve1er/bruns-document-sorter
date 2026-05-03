"""Centralised logging configuration for the platform.

Replaces ad-hoc `print()` calls scattered through the codebase with a single
RotatingFileHandler that writes to `data/logs/bruns.log`. Console output is
preserved (StreamHandler) so the operator launcher window still shows live
events.

Usage:
    from core.logging_config import configure_logging
    configure_logging()                       # at app startup, once
    log = logging.getLogger(__name__)         # in each module
    log.info("…"); log.warning("…"); log.error("…", exc_info=True)

Defaults:
    File:    data/logs/bruns.log  (override BRUNS_LOG_DIR)
    Level:   INFO                 (override BRUNS_LOG_LEVEL)
    Rotate:  10 MB × 5 files

Idempotent: calling configure_logging() twice does not double-attach handlers.
"""
from __future__ import annotations

import logging
import logging.handlers
import os
from pathlib import Path

# ROOT-relative path resolution. Without this, `data/logs` is interpreted
# relative to the current working directory — which breaks when the user runs
# `python -m core.api.server` from any directory other than the repo root,
# or when the launcher is invoked from a Windows shortcut whose "Start in"
# field points elsewhere.
_REPO_ROOT = Path(__file__).resolve().parent.parent

_CONFIGURED = False


def configure_logging(
    log_dir: str | None = None,
    level: str | None = None,
    max_bytes: int = 10_000_000,
    backup_count: int = 5,
) -> Path:
    """Configure root logger. Returns the path to the active log file.

    Safe to call multiple times — only the first call attaches handlers.
    Default log dir: <repo>/data/logs/  (override via BRUNS_LOG_DIR env var).
    """
    global _CONFIGURED
    root = logging.getLogger()
    if _CONFIGURED:
        return Path(getattr(configure_logging, "_log_path", ""))

    # Resolve the log directory. Precedence:
    #   1. explicit log_dir kwarg (rare — testing only)
    #   2. BRUNS_LOG_DIR env var
    #   3. <repo>/data/logs/  (the canonical location)
    if log_dir is None:
        env = os.environ.get("BRUNS_LOG_DIR")
        log_dir_path = Path(env) if env else (_REPO_ROOT / "data" / "logs")
    else:
        log_dir_path = Path(log_dir)

    level_name = (level or os.environ.get("BRUNS_LOG_LEVEL") or "INFO").upper()
    log_level = getattr(logging, level_name, logging.INFO)

    log_dir_path.mkdir(parents=True, exist_ok=True)
    log_path = log_dir_path / "bruns.log"

    fmt = logging.Formatter(
        "%(asctime)s %(levelname)-7s %(name)s — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = logging.handlers.RotatingFileHandler(
        log_path, maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8",
    )
    file_handler.setFormatter(fmt)
    file_handler.setLevel(log_level)

    console_handler = logging.StreamHandler()
    # Console gets a terser format — operator launcher windows are narrow.
    console_handler.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
    console_handler.setLevel(log_level)

    # Reset root handlers so we don't pile up if reload-style frameworks
    # call us again.
    for h in list(root.handlers):
        root.removeHandler(h)
    root.addHandler(file_handler)
    root.addHandler(console_handler)
    root.setLevel(log_level)

    # Quiet down libraries that are noisy at INFO.
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("werkzeug").setLevel(logging.WARNING)
    logging.getLogger("chromadb").setLevel(logging.WARNING)

    _CONFIGURED = True
    setattr(configure_logging, "_log_path", str(log_path))
    return log_path
