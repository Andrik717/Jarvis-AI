"""Offline regression tests for Jarvis dialogue and safe Windows commands."""
import unittest
from unittest.mock import patch

from jarvis.brain import _clean, _is_model_question, _needs_deep_reasoning
from jarvis.pc_control import _DuckDuckGoParser, _normalize, _is_close_alias, handle_command


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

    def test_obvious_single_word_typo_matches_known_app(self):
        self.assertTrue(_is_close_alias("блакнот", ("блокнот", "notepad")))
        self.assertFalse(_is_close_alias("браузер", ("блокнот", "notepad")))
        self.assertFalse(_is_close_alias("открой блокнот", ("блокнот", "notepad")))


class WebSearchParserTests(unittest.TestCase):
    def test_extracts_search_title_and_snippet(self):
        parser = _DuckDuckGoParser()
        parser.feed(
            '<a class="result__a" href="https://example.com">Example result</a>'
            '<div class="result__snippet">Useful summary text</div>'
        )
        self.assertEqual(parser.results[0]["title"], "Example result")
        self.assertEqual(parser.results[0]["snippet"], "Useful summary text")
        self.assertEqual(parser.results[0]["url"], "https://example.com")


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
