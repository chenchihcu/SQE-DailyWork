from __future__ import annotations

import unittest

from tests.hang_watchdog import (
    DEFAULT_CI_HANG_SECONDS,
    hang_seconds_from_env,
    install_hang_watchdog,
)


class HangWatchdogEnvTests(unittest.TestCase):
    def test_explicit_seconds_win_over_github_actions(self) -> None:
        self.assertEqual(
            90,
            hang_seconds_from_env(
                {"SQE_TEST_HANG_SECONDS": "90", "GITHUB_ACTIONS": "true"}
            ),
        )

    def test_zero_disables_even_on_github_actions(self) -> None:
        self.assertEqual(
            0,
            hang_seconds_from_env(
                {"SQE_TEST_HANG_SECONDS": "0", "GITHUB_ACTIONS": "true"}
            ),
        )

    def test_github_actions_defaults_to_ci_budget(self) -> None:
        self.assertEqual(
            DEFAULT_CI_HANG_SECONDS,
            hang_seconds_from_env({"GITHUB_ACTIONS": "true"}),
        )

    def test_local_default_is_disabled(self) -> None:
        self.assertEqual(0, hang_seconds_from_env({}))

    def test_invalid_seconds_are_disabled(self) -> None:
        self.assertEqual(0, hang_seconds_from_env({"SQE_TEST_HANG_SECONDS": "nope"}))

    def test_install_with_zero_seconds_is_noop(self) -> None:
        self.assertFalse(install_hang_watchdog(seconds=0))
