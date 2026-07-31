import unittest

from app.questions_bank import _parse


class ParseQuestionTests(unittest.TestCase):
    def test_accepts_question_with_answer_buttons(self):
        question = _parse(
            """WB-9001
Тип: Один правильный ответ
Вопрос
Какой вариант верный?
Варианты
A. Первый
B. Второй
Правильный ответ
B
Объяснение
Проверка кнопочного вопроса.
""",
            "Тест",
        )

        self.assertIsNotNone(question)
        self.assertEqual(question.answers, ["Первый", "Второй"])
        self.assertEqual(question.correct_indexes, [1])

    def test_rejects_open_question(self):
        question = _parse(
            """WB-9002
Вопрос
Напишите ответ.
Ответ
Текстом
""",
            "Тест",
        )

        self.assertIsNone(question)

    def test_rejects_sequence_even_when_it_has_options(self):
        question = _parse(
            """WB-9003
Тип: Последовательность
Вопрос
Выберите порядок.
Варианты
A. Один, два
B. Два, один
Правильный ответ
A
""",
            "Тест",
        )

        self.assertIsNone(question)


if __name__ == "__main__":
    unittest.main()
