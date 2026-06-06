"""Compatibility entrypoint for v2 migration."""

import sys
from pathlib import Path

_repo_root = Path(__file__).resolve().parent
for _path in (_repo_root / "src", _repo_root):
    _path_text = str(_path)
    if _path_text not in sys.path:
        sys.path.insert(0, _path_text)

from scripts.migrate_to_v2 import main


if __name__ == "__main__":
    raise SystemExit(main())
