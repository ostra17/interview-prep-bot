from telegram import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from config import POSITIONS, LEVELS, LANGUAGES, WEBAPP_URL


def positions_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(title, callback_data=f"position:{key}")]
        for key, title in POSITIONS.items()
    ]
    buttons.append([InlineKeyboardButton("🔗 Своя вакансия по ссылке", callback_data="position:custom")])
    return InlineKeyboardMarkup(buttons)


def levels_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(title, callback_data=f"level:{key}")]
        for key, title in LEVELS.items()
    ]
    return InlineKeyboardMarkup(buttons)


def mode_keyboard(position_id: str, level_id: str) -> InlineKeyboardMarkup:
    """После выбора уровня — выбор между текстовым режимом и live-режимом с этими же параметрами."""
    live_url = f"{WEBAPP_URL}?position={position_id}&level={level_id}"
    buttons = [
        [InlineKeyboardButton(title, callback_data=f"lang:{key}")]
        for key, title in LANGUAGES.items()
    ]
    buttons.append([InlineKeyboardButton("🎙 Live-режим (бета)", web_app=WebAppInfo(url=live_url))])
    return InlineKeyboardMarkup(buttons)