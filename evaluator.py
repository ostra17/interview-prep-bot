from llm import generate_text

CODING_INSTRUCTIONS = (
    "Это coding-вопрос: оцени корректность решения, читаемость кода, "
    "учёл ли кандидат edge cases, и есть ли более оптимальный подход."
)
THEORY_INSTRUCTIONS = (
    "Это теоретический вопрос: оцени точность и полноту ответа."
)
BEHAVIORAL_INSTRUCTIONS = (
    "Это поведенческий вопрос: оцени структуру ответа (есть ли конкретика, "
    "результат, выводы), а не только техническую сторону."
)

_INSTRUCTIONS_BY_TYPE = {
    "coding": CODING_INSTRUCTIONS,
    "theory": THEORY_INSTRUCTIONS,
    "behavioral": BEHAVIORAL_INSTRUCTIONS,
}

OVERLOAD_NOTICE = (
    "⚠️ Не получилось получить оценку от ИИ — сервис сейчас перегружен. "
    "Твой ответ сохранён, попробуй продолжить или вернуться позже."
)


def evaluate_answer(question: str, answer: str, position: str, level: str, question_type: str = "theory") -> str:
    type_instructions = _INSTRUCTIONS_BY_TYPE.get(question_type, THEORY_INSTRUCTIONS)
    prompt = (
        f"Ты технический интервьюер на позицию {position}, уровень {level}. "
        f"Вопрос кандидату: {question}\n"
        f"Ответ кандидата: {answer}\n\n"
        f"{type_instructions}\n"
        f"Дай короткую (2-4 предложения) конструктивную оценку ответа на русском языке."
    )
    return generate_text(prompt) or OVERLOAD_NOTICE