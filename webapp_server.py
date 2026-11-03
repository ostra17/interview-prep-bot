import asyncio
import logging
import time

from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from google import genai
from google.genai import types
from google.genai import errors

from config import GEMINI_API_KEY, MODEL_NAME, POSITIONS, LEVELS
from database import get_random_questions, save_interview_answer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("webapp")

app = FastAPI()
app.mount("/static", StaticFiles(directory="webapp/static"), name="static")

client = genai.Client(api_key=GEMINI_API_KEY)

# Основная модель, затем облегчённая: у них отдельные лимиты и разная загруженность
FALLBACK_MODEL = "gemini-flash-lite-latest"
MODEL_CHAIN = [MODEL_NAME, FALLBACK_MODEL]
ATTEMPTS_PER_MODEL = 2

OVERLOAD_MESSAGE = "⚠️ Сервис оценки сейчас перегружен. Попробуй отправить ответ ещё раз через минуту."

_INSTRUCTIONS_BY_TYPE = {
    "coding": "Это coding-вопрос: оцени корректность решения, читаемость кода и edge cases.",
    "theory": "Это теоретический вопрос: оцени точность и полноту ответа.",
    "behavioral": "Это поведенческий вопрос: оцени структуру и конкретику ответа.",
}


def _build_fast_config() -> types.GenerateContentConfig | None:
    """Gemini 3.x по умолчанию думает на высоком уровне. Для короткой оценки ответа это лишние минуты."""
    try:
        return types.GenerateContentConfig(
            thinking_config=types.ThinkingConfig(thinking_level=types.ThinkingLevel.LOW)
        )
    except (AttributeError, ValueError):
        logger.warning("Установленная версия google-genai не знает thinking_level. Обнови: pip install --upgrade google-genai")
        return None


FAST_CONFIG = _build_fast_config()


def _build_prompt(question_text: str, question_type: str, position: str, level: str, answer_part: str) -> str:
    position_title = POSITIONS.get(position, position)
    level_title = LEVELS.get(level, level)
    instructions = _INSTRUCTIONS_BY_TYPE.get(question_type, _INSTRUCTIONS_BY_TYPE["theory"])
    return (
        f"Ты технический интервьюер на позицию {position_title}, уровень {level_title}. "
        f"Вопрос кандидату: {question_text}\n"
        f"{answer_part}\n"
        f"{instructions}\n"
        f"Дай короткую (2-3 предложения, не более 400 символов) конструктивную оценку на русском языке."
    )


async def _generate_with_fallback(contents) -> str | None:
    """Пробует модели по очереди. 503 — повтор, 429 (лимит) — сразу следующая модель. None — если не вышло."""
    for model in MODEL_CHAIN:
        config = FAST_CONFIG
        for attempt in range(1, ATTEMPTS_PER_MODEL + 1):
            started = time.perf_counter()
            try:
                response = await client.aio.models.generate_content(
                    model=model, contents=contents, config=config
                )
                text = (response.text or "").strip()
                thoughts = getattr(response.usage_metadata, "thoughts_token_count", None)
                logger.info(
                    "Ответила модель %s за %.1f с (попытка %d), токенов на размышления: %s",
                    model, time.perf_counter() - started, attempt, thoughts,
                )
                if text:
                    return text
                logger.warning("Модель %s вернула пустой ответ", model)
            except errors.ServerError:
                logger.warning(
                    "Модель %s перегружена (попытка %d из %d, ждали %.1f с)",
                    model, attempt, ATTEMPTS_PER_MODEL, time.perf_counter() - started,
                )
                if attempt < ATTEMPTS_PER_MODEL:
                    await asyncio.sleep(2 * attempt)
            except errors.ClientError as exc:
                if getattr(exc, "code", None) == 429:
                    logger.warning("У модели %s закончился лимит запросов, пробую следующую", model)
                    break
                if config is not None:
                    # Модель не приняла настройки размышлений — повторяем без них
                    logger.warning("Модель %s отклонила настройки размышлений (%s), повторяю без них", model, exc)
                    config = None
                    continue
                logger.error("Модель %s вернула ошибку: %s", model, exc)
                break
    return None


async def _save(user_id: int, position: str, level: str, question_type: str, question: str, answer: str, evaluation: str) -> None:
    await save_interview_answer(
        user_id=user_id,
        position=POSITIONS.get(position, position),
        level=LEVELS.get(level, level),
        question_type=question_type,
        question=question,
        answer=answer,
        evaluation=evaluation,
    )


@app.get("/", response_class=HTMLResponse)
async def serve_webapp():
    with open("webapp/index.html", "r", encoding="utf-8") as f:
        return f.read()


@app.get("/api/questions")
async def get_questions(position: str, level: str):
    questions = await get_random_questions(position, level, count=4)
    return {
        "questions": questions,
        "position_title": POSITIONS.get(position, position),
        "level_title": LEVELS.get(level, level),
    }


@app.post("/api/answer")
async def submit_voice_answer(
    audio: UploadFile = File(...),
    question_text: str = Form(...),
    question_type: str = Form(...),
    position: str = Form(...),
    level: str = Form(...),
    user_id: int = Form(...),
):
    audio_bytes = await audio.read()
    prompt = _build_prompt(
        question_text, question_type, position, level,
        "Прослушай голосовой ответ кандидата во вложении.",
    )
    contents = [types.Part.from_bytes(data=audio_bytes, mime_type="audio/webm"), prompt]
    logger.info("Голосовой ответ: %d КБ аудио", len(audio_bytes) // 1024)
    evaluation = await _generate_with_fallback(contents)

    if evaluation is None:
        return JSONResponse({"evaluation_text": OVERLOAD_MESSAGE, "failed": True})

    await _save(user_id, position, level, question_type, question_text, "[голосовой ответ]", evaluation)
    return JSONResponse({"evaluation_text": evaluation, "failed": False})


@app.post("/api/answer_code")
async def submit_code_answer(
    code: str = Form(...),
    question_text: str = Form(...),
    question_type: str = Form(...),
    position: str = Form(...),
    level: str = Form(...),
    user_id: int = Form(...),
):
    prompt = _build_prompt(
        question_text, question_type, position, level,
        f"Код кандидата:\n```\n{code[:8000]}\n```",
    )
    logger.info("Ответ кодом: %d символов", len(code))
    evaluation = await _generate_with_fallback(prompt)

    if evaluation is None:
        return JSONResponse({"evaluation_text": OVERLOAD_MESSAGE, "failed": True})

    await _save(user_id, position, level, question_type, question_text, code, evaluation)
    return JSONResponse({"evaluation_text": evaluation, "failed": False})