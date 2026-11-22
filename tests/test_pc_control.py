"""Regression tests for safe conversational Windows command routing."""
import unittest
from unittest.mock import patch

from jarvis import pc_control


class CommandRoutingTests(unittest.TestCase):
    @patch("jarvis.pc_control.subprocess.Popen")
    def test_first_person_future_opens_notepad(self, popen):
        answer = pc_control.handle_command("Открою блокнот")
        self.assertEqual(answer, "Открываю блокнот.")
        popen.assert_called_once_with(["notepad.exe"])

    @patch("jarvis.pc_control.subprocess.Popen")
    def test_polite_imperative_opens_calculator(self, popen):
        answer = pc_control.handle_command("Запустите калькулятор")
        self.assertEqual(answer, "Открываю калькулятор.")
        popen.assert_called_once_with(["calc.exe"])

    def test_unknown_app_is_not_executed(self):
        answer = pc_control.handle_command("Открой неизвестную программу")
        self.assertIsNone(answer)


if __name__ == "__main__":
    unittest.main()
