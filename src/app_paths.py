"""Single source of truth for writable and runtime root paths.

Source runs resolve the repository root (parent of ``src/``).
Frozen PyInstaller onedir builds resolve the directory containing the
executable so ``data/``, ``Outputs/``, and ``logs/`` remain writable.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def runtime_root() -> Path:
    """Return the writable application root directory."""
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


# Import-time alias for modules that bind once during startup.
PROJECT_ROOT = runtime_root()


def formal_data_dir() -> Path:
    return runtime_root() / "data"


def formal_db_path() -> Path:
    return formal_data_dir() / "sqe_v2.db"


def data_dir() -> Path:
    env_db = os.environ.get("SQE_DB_PATH", "").strip()
    if env_db:
        return Path(env_db).expanduser().resolve().parent
    return formal_data_dir()


def resolve_db_path() -> Path:
    env_db = os.environ.get("SQE_DB_PATH", "").strip()
    if env_db:
        return Path(env_db).expanduser().resolve()
    return formal_db_path()


def outputs_dir() -> Path:
    return runtime_root() / "Outputs"


def logs_dir() -> Path:
    return runtime_root() / "logs"


def anomaly_folder_root() -> Path:
    return outputs_dir() / "ncr number file"


def legacy_db_path() -> Path:
    return resolve_db_path().parent / "sqe.db"


def ncr_legacy_source_db() -> Path:
    return runtime_root() / "ncr" / "data" / "defect.db"
