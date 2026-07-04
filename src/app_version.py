"""Single source of truth for the application version.

Bump ``__version__`` on each release and add a matching ``CHANGELOG.md`` entry.
The value is surfaced in the main-window title bar and logged at startup so a
build can be identified from a user's bug report / log file.
"""

from __future__ import annotations

__version__ = "1.0.0"

APP_NAME = "SQE DailyWork"
APP_TITLE = f"{APP_NAME} v{__version__} - SQE 工作台"
