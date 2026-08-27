"""Per-test hang abort for unittest (CI / SQE_TEST_HANG_SECONDS).

GitHub Actions Full/Coverage previously sat in `unittest discover` with no new
dots after `test_partial_statistics_failure_is_not_rendered_as_empty_data`
until the 120-minute job timeout. Default unittest is not verbose, so the hung
test name never appears. This watchdog prints the active test, dumps all-thread
tracebacks, and exits 3 instead of waiting for the runner timeout.
"""

from __future__ import annotations

import faulthandler
import os
import sys
import threading
import unittest
from collections.abc import Mapping

DEFAULT_CI_HANG_SECONDS = 180

_installed = False
_lock = threading.Lock()
_timer: threading.Timer | None = None


def hang_seconds_from_env(env: Mapping[str, str] | None = None) -> int:
    """Return per-test hang seconds. ``0`` disables the watchdog.

    ``SQE_TEST_HANG_SECONDS`` wins when set (including ``0``). Otherwise
    GitHub Actions defaults to ``DEFAULT_CI_HANG_SECONDS``.
    """
    source = os.environ if env is None else env
    raw = str(source.get("SQE_TEST_HANG_SECONDS", "") or "").strip()
    if raw:
        try:
            return max(0, int(raw))
        except ValueError:
            return 0
    github = str(source.get("GITHUB_ACTIONS", "") or "").strip().lower()
    if github in {"1", "true", "yes", "on"}:
        return DEFAULT_CI_HANG_SECONDS
    return 0


def _dump_and_abort(test_id: str, seconds: int) -> None:
    message = (
        f"\nSQE test hang watchdog: {test_id} exceeded {seconds}s; "
        "dumping traceback (not visual evidence)\n"
    )
    sys.stderr.write(message)
    sys.stderr.flush()
    faulthandler.dump_traceback(file=sys.stderr, all_threads=True)
    os._exit(3)


def _arm(test: unittest.TestCase, seconds: int) -> None:
    global _timer
    with _lock:
        if _timer is not None:
            _timer.cancel()
        test_id = str(test)
        timer = threading.Timer(seconds, _dump_and_abort, args=(test_id, seconds))
        timer.daemon = True
        timer.start()
        _timer = timer


def _disarm() -> None:
    global _timer
    with _lock:
        if _timer is not None:
            _timer.cancel()
            _timer = None


def install_hang_watchdog(*, seconds: int | None = None) -> bool:
    """Monkeypatch ``unittest.TestResult`` start/stop. Idempotent.

    Returns True when the watchdog is armed.
    """
    global _installed
    if seconds is None:
        seconds = hang_seconds_from_env()
    if seconds <= 0:
        return False
    if _installed:
        return True

    faulthandler.enable(all_threads=True)
    original_start = unittest.TestResult.startTest
    original_stop = unittest.TestResult.stopTest

    def startTest(self, test):  # noqa: N802 — unittest API
        _arm(test, seconds)
        return original_start(self, test)

    def stopTest(self, test):  # noqa: N802 — unittest API
        _disarm()
        return original_stop(self, test)

    unittest.TestResult.startTest = startTest  # type: ignore[method-assign]
    unittest.TestResult.stopTest = stopTest  # type: ignore[method-assign]
    _installed = True
    sys.stderr.write(
        f"SQE test hang watchdog armed at {seconds}s per test; not visual evidence.\n"
    )
    sys.stderr.flush()
    return True
