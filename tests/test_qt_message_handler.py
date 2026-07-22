from __future__ import annotations

import logging
import unittest
from unittest.mock import patch

from PySide6.QtCore import QtMsgType

import main


class QtMessageHandlerTests(unittest.TestCase):
    def test_only_warning_critical_and_fatal_are_logged(self) -> None:
        with patch.object(main._logger, "log") as log:
            main._qt_message_handler(QtMsgType.QtDebugMsg, None, "debug")
            main._qt_message_handler(QtMsgType.QtInfoMsg, None, "info")
            main._qt_message_handler(QtMsgType.QtWarningMsg, None, "Unknown property opacity")
            main._qt_message_handler(QtMsgType.QtCriticalMsg, None, "critical")
            main._qt_message_handler(QtMsgType.QtFatalMsg, None, "fatal")

        self.assertEqual(3, log.call_count)
        self.assertEqual(logging.WARNING, log.call_args_list[0].args[0])
        self.assertIn("Unknown property", log.call_args_list[0].args[2])
        self.assertEqual(logging.ERROR, log.call_args_list[1].args[0])
        self.assertEqual(logging.CRITICAL, log.call_args_list[2].args[0])


if __name__ == "__main__":
    unittest.main()
