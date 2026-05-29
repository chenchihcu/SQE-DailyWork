"""Compatibility entrypoint for v2 migration."""

from scripts.migrate_to_v2 import main


if __name__ == "__main__":
    raise SystemExit(main())
