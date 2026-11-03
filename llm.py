import logging
import time

from google import genai
from google.genai import errors, types

from config import GEMINI_API_KEY, MODEL_NAME

logger = logging.getLogger(__name__)

client = genai.Client(api_key=GEMINI_API_KEY)

# Основная модель, затем облегчённая: у них отдельные лимиты и разная загруженность
FALLBACK_MODEL = "gemini-flash-lite-latest"
MODEL_CHAIN = [MODEL_NAME, FALLBACK_MODEL]
ATTEMPTS_PER_MODEL = 2


def _build_fast_config() -> types.GenerateContentConfig | None:
    """Gemini 3.x по умолчанию думает на высоком уровне. Для короткого ответа это лишние минуты."""
    try:
        return types.GenerateContentConfig(
            thinking_config=types.ThinkingConfig(thinking_level=types.ThinkingLevel.LOW)
        )
    except (AttributeError, ValueError):
        logger.warning("Версия google-genai не знает thinking_level. Обнови: pip install --upgrade google-genai")
        return None


FAST_CONFIG = _build_fast_config()


def generate_text(contents) -> str | None:
    """Пробует модели по очереди. 503 — повтор, 429 (лимит) — сразу следующая модель.

    Возвращает текст ответа или None, если все модели недоступны.
    """
    for model in MODEL_CHAIN:
        config = FAST_CONFIG
        for attempt in range(1, ATTEMPTS_PER_MODEL + 1):
            started = time.perf_counter()
            try:
                response = client.models.generate_content(model=model, contents=contents, config=config)
                text = (response.text or "").strip()
                if text:
                    if model != MODEL_CHAIN[0]:
                        logger.warning("Основная модель недоступна, ответила запасная: %s", model)
                    return text
                logger.warning("Модель %s вернула пустой ответ", model)
            except errors.ServerError:
                logger.warning(
                    "Модель %s перегружена (попытка %d из %d, ждали %.1f с)",
                    model, attempt, ATTEMPTS_PER_MODEL, time.perf_counter() - started,
                )
                if attempt < ATTEMPTS_PER_MODEL:
                    time.sleep(2 * attempt)
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