"""Offline regression tests for Jarvis dialogue and safe Windows commands."""
import unittest
from unittest.mock import patch

from jarvis.brain import _clean, _is_model_question, _needs_deep_reasoning
from jarvis.pc_control import _normalize, handle_command


class DialogueTests(unittest.TestCase):
    def test_model_question_detection(self):
        self.assertTrue(_is_model_question("Какая модель у тебя установлена?"))
        self.assertTrue(_is_model_question("Какую модель ты используешь?"))
        self.assertFalse(_is_model_question("Какая сегодня погода?"))

    def test_text_cleanup(self):
        self.assertEqual(_clean("  привет\n   Джарвис  "), "привет Джарвис")

    def test_deep_reasoning_for_development_tasks(self):
        self.assertTrue(_needs_deep_reasoning("Исправь ошибку в коде"))
        self.assertFalse(_needs_deep_reasoning("Привет, как дела?"))

    def test_normalization_handles_yo_and_assistant_name(self):
        self.assertEqual(_normalize("Эй, Джарвис! Открой Ёлки"), "открой елки")


class SafeCommandTests(unittest.TestCase):
    def test_task_manager_is_allowlisted(self):
        with patch("jarvis.pc_control.subprocess.Popen") as popen:
            answer = handle_command("Открой диспетчер задач")
        self.assertEqual(answer, "Открываю диспетчер задач.")
        popen.assert_called_once_with(["taskmgr.exe"])

    def test_unknown_shell_command_is_not_executed(self):
        with patch("jarvis.pc_control.subprocess.Popen") as popen:
            answer = handle_command("выполни произвольную команду")
        self.assertIsNone(answer)
        popen.assert_not_called()


if __name__ == "__main__":
    unittest.main()
