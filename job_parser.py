import json
import re

import requests
from bs4 import BeautifulSoup

from llm import generate_text

_URL_PATTERN = re.compile(r"^https?://", re.IGNORECASE)


def _fetch_text_from_url(url: str) -> str:
    """Скачивает страницу вакансии и вытаскивает читаемый текст без тегов/скриптов."""
    response = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()
    return soup.get_text(separator="\n", strip=True)


def get_job_text(user_input: str) -> str:
    """Если юзер прислал ссылку — скачивает и парсит страницу. Иначе считает, что это уже текст вакансии."""
    if _URL_PATTERN.match(user_input.strip()):
        return _fetch_text_from_url(user_input.strip())
    return user_input


_PARSE_PROMPT = """\
Тебе дан текст вакансии. Определи:
1. Название позиции (коротко, например "Python Developer", "AI Engineer")
2. Уровень: junior, middle или senior — исходя из требований к опыту
3. 4 вопроса для подготовки к собеседованию на эту вакансию: минимум 1 обязательно \
должен быть практическим coding-заданием, остальные — теория/поведенческие, подобранные \
под конкретный стек и требования из текста вакансии

Ответь СТРОГО в формате JSON, без пояснений вокруг, без markdown-разметки:
{{
  "title": "...",
  "level": "junior|middle|senior",
  "questions": [
    {{"text": "...", "type": "theory|behavioral|coding"}},
    {{"text": "...", "type": "theory|behavioral|coding"}},
    {{"text": "...", "type": "theory|behavioral|coding"}},
    {{"text": "...", "type": "theory|behavioral|coding"}}
  ]
}}

Текст вакансии:
{job_text}
"""


def parse_custom_job(job_text: str) -> dict:
    """Отправляет текст вакансии в Gemini и получает структурированный разбор + вопросы."""
    prompt = _PARSE_PROMPT.format(job_text=job_text[:6000])
    raw_text = generate_text(prompt)
    if raw_text is None:
        raise RuntimeError("Gemini недоступен")

    raw_text = raw_text.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    return json.loads(raw_text)