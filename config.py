import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
MODEL_NAME = "gemini-flash-latest"

POSITIONS = {
    "ai_engineer": "AI Engineer",
    "python_developer": "Python Developer",
}

LEVELS = {
    "junior": "Junior",
    "middle": "Middle",
    "senior": "Senior",
}

LANGUAGES = {
    "ru": "Русский",
    "en": "English",
}
WEBAPP_URL = os.getenv("WEBAPP_URL")