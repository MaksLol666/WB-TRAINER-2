import random
import re
from dataclasses import dataclass
from pathlib import Path

QUESTION_FILE = Path(__file__).resolve().parent.parent / "voprosi_wb.txt"
DEFAULT_CATEGORY = "Общая работа ПВЗ"
DEFAULT_DIFFICULTY = 1
DEFAULT_TYPE = "Один правильный ответ"
FULL_TEST_LIMIT = 30
CATEGORY_TEST_LIMIT = 30
DIFFICULTY_MAP = {"легкая": 1, "лёгкая": 1, "средняя": 2, "сложная": 3}

@dataclass(frozen=True)
class Question:
    id: str
    category: str
    difficulty: int
    type: str
    text: str
    answers: list[str]
    correct_answers: list[str]
    explanation: str
    weight: int = 1

    @property
    def is_choice(self) -> bool:
        return len(self.answers) >= 2

    @property
    def is_multiple(self) -> bool:
        return len(self.correct_answers) > 1 or "несколько" in self.type.lower() or "множе" in self.type.lower()

    @property
    def correct_indexes(self) -> list[int]:
        result = []
        for ans in self.correct_answers:
            if re.fullmatch(r"[A-ZА-Я]", ans.strip().upper()):
                idx = ord(ans.strip().upper()[0]) - ord("A")
                if 0 <= idx < len(self.answers):
                    result.append(idx)
        return result


def _inline(block: str, label: str) -> str:
    m = re.search(rf"^\s*{re.escape(label)}\s*:\s*(.+)$", block, re.I | re.M)
    return m.group(1).strip() if m else ""


def _section(block: str, labels: tuple[str, ...], stops: tuple[str, ...]) -> str:
    label_re = "|".join(map(re.escape, labels))
    m = re.search(rf"(?:^|\n)\s*(?:{label_re})\s*:?\s*\n?", block, re.I)
    if not m:
        return ""
    rest = block[m.end():]
    if stops:
        stop_re = "|".join(map(re.escape, stops))
        s = re.search(rf"\n\s*(?:{stop_re})\s*:?\s*\n?", rest, re.I)
        if s:
            rest = rest[:s.start()]
    return re.sub(r"\n\s*-{3,}.*", "", rest, flags=re.S).strip()


def _answers(block: str) -> list[str]:
    source = _section(block, ("Варианты",), ("Правильный ответ", "Правильные ответы", "Ответ", "Объяснение")) or block
    pairs = re.findall(r"(?:^|\n)\s*([A-H])\.\s*(.+?)(?=\n\s*[A-H]\.\s|\n\s*(?:Правильный ответ|Правильные ответы|Ответ|Объяснение)\b|\Z)", source, re.S | re.I)
    return [re.sub(r"\s+", " ", text).strip() for _, text in pairs]


def _correct(block: str, answers: list[str]) -> list[str]:
    raw = _section(block, ("Правильный ответ", "Правильные ответы", "Ответ"), ("Объяснение",))
    if not raw:
        return []
    letters = re.findall(r"\b([A-H])\b", raw.upper())
    if answers and letters:
        return sorted(set(letters), key=letters.index)
    return [re.sub(r"\s+", " ", raw).strip()]


def _parse(block: str, fallback_category: str) -> Question | None:
    mid = re.search(r"\bWB-\d{4}\b", block)
    if not mid:
        return None
    category = _inline(block, "Категория") or fallback_category or DEFAULT_CATEGORY
    difficulty = DIFFICULTY_MAP.get((_inline(block, "Сложность") or "").lower(), DEFAULT_DIFFICULTY)
    qtype = _inline(block, "Тип") or DEFAULT_TYPE
    # Tests are intentionally limited to questions answered with buttons.  A
    # sequence requires a separate ordering UI and must not silently degrade to
    # a text answer.
    if "последователь" in qtype.lower():
        return None
    text = _section(block, ("Вопрос",), ("Варианты", "Правильный ответ", "Правильные ответы", "Ответ", "Объяснение"))
    # If no explicit Варианты marker, remove option/correct sections from question text.
    text = re.sub(r"\n\s*[A-H]\.\s.*", "", text, flags=re.S).strip()
    answers = _answers(block)
    correct = _correct(block, answers)
    explanation = _section(block, ("Объяснение",), tuple()) or "Объяснение не указано."
    if not text or len(answers) < 2 or not correct:
        return None
    if not Question("", category, difficulty, qtype, text, answers, correct, explanation).correct_indexes:
        return None
    return Question(mid.group(0), category, difficulty, qtype, re.sub(r"\s+", " ", text).strip(), answers, correct, re.sub(r"\s+", " ", explanation).strip())


def load_questions() -> list[Question]:
    if not QUESTION_FILE.exists():
        return []
    content = QUESTION_FILE.read_text(encoding="utf-8")
    starts = [m.start() for m in re.finditer(r"(?m)^WB-\d{4}\s*$", content)]
    questions, category = [], DEFAULT_CATEGORY
    for i, start in enumerate(starts):
        q = _parse(content[start: starts[i + 1] if i + 1 < len(starts) else len(content)], category)
        if q:
            category = q.category
            questions.append(q)
    return questions


def get_categories() -> list[str]:
    return sorted({q.category for q in load_questions()})


def build_test(category: str | None = None, limit: int = FULL_TEST_LIMIT) -> list[Question]:
    questions = [q for q in load_questions() if category is None or q.category == category]
    random.shuffle(questions)
    return questions[:limit]
