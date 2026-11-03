from telegram import Update
from telegram.ext import ContextTypes

from config import POSITIONS, LEVELS
from keyboards import positions_keyboard, levels_keyboard, mode_keyboard
from evaluator import evaluate_answer
from database import save_interview_answer, save_feedback, get_random_questions
from job_parser import get_job_text, parse_custom_job

CUSTOM_JOB_PROMPT = (
    "Пришли ссылку на вакансию или вставь текст описания вакансии следующим сообщением — "
    "я определю уровень и подготовлю вопросы под неё."
)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Привет! Выбери вакансию, под которую хочешь потренироваться:",
        reply_markup=positions_keyboard(),
    )


async def feedback_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data["awaiting_feedback"] = True
    await update.message.reply_text(
        "Поделись фидбеком о боте или пришли реальный вопрос с собеседования, "
        "который у тебя был — просто напиши текст следующим сообщением."
    )


async def handle_button_click(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    namespace, value = query.data.split(":")

    if namespace == "position":
        if value == "custom":
            context.user_data["awaiting_custom_job"] = True
            await query.edit_message_text(CUSTOM_JOB_PROMPT)
            return

        context.user_data.pop("custom_job", None)
        context.user_data["position"] = value
        position_title = POSITIONS[value]
        await query.edit_message_text(
            f"Вакансия: {position_title}\n\nТеперь выбери уровень:",
            reply_markup=levels_keyboard(),
        )

    elif namespace == "level":
        context.user_data["level"] = value
        level_title = LEVELS[value]
        position_id = context.user_data["position"]
        await query.edit_message_text(
            f"Уровень: {level_title}\n\n"
            f"Выбери язык для текстового режима, или запусти Live-режим ниже:",
            reply_markup=mode_keyboard(position_id, value),
        )

    elif namespace == "lang":
        context.user_data["language"] = value
        context.user_data["question_index"] = 0

        custom_job = context.user_data.get("custom_job")
        if custom_job:
            questions = custom_job["questions"]
        else:
            position_id = context.user_data["position"]
            level_id = context.user_data["level"]
            questions = await get_random_questions(position_id, level_id, count=4)

        context.user_data["questions"] = questions

        if not questions:
            await query.edit_message_text("Для этой вакансии и уровня пока нет вопросов в базе.")
            return

        first_question = questions[0]
        label = "💻 Live-coding" if first_question["type"] == "coding" else "Вопрос"
        await query.edit_message_text(
            f"Начинаем! {label} 1 из {len(questions)}:\n\n{first_question['text']}"
        )


async def handle_text_answer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if context.user_data.get("awaiting_feedback"):
        context.user_data["awaiting_feedback"] = False
        await save_feedback(user_id=update.effective_user.id, content=update.message.text)
        await update.message.reply_text("Спасибо за фидбек! 🙏")
        return

    if context.user_data.get("awaiting_custom_job"):
        context.user_data["awaiting_custom_job"] = False
        await update.message.reply_text("Анализирую вакансию, подожди немного...")

        try:
            job_text = get_job_text(update.message.text)
            parsed = parse_custom_job(job_text)
        except Exception:
            await update.message.reply_text(
                "Не получилось разобрать вакансию 😕 Попробуй вставить текст вакансии напрямую, "
                "а не ссылку, или проверь, что ссылка рабочая."
            )
            return

        context.user_data["custom_job"] = parsed
        level_label = LEVELS.get(parsed["level"], parsed["level"])
        position_id = context.user_data.get("position", "custom")
        await update.message.reply_text(
            f"Определил: {parsed['title']}, уровень {level_label}.\n\n"
            f"Выбери язык для текстового режима, или запусти Live-режим ниже:",
            reply_markup=mode_keyboard(position_id, parsed["level"]),
        )
        return

    if "question_index" not in context.user_data:
        await update.message.reply_text("Нажми /start, чтобы начать интервью.")
        return

    questions = context.user_data["questions"]
    current_index = context.user_data["question_index"]
    current_question = questions[current_index]
    user_answer = update.message.text

    await update.message.reply_text("Оцениваю ответ...")

    custom_job = context.user_data.get("custom_job")
    if custom_job:
        position = custom_job["title"]
        level = LEVELS.get(custom_job["level"], custom_job["level"])
    else:
        position = POSITIONS[context.user_data["position"]]
        level = LEVELS[context.user_data["level"]]

    evaluation = evaluate_answer(
        current_question["text"], user_answer, position, level, current_question["type"]
    )

    await save_interview_answer(
        user_id=update.effective_user.id,
        position=position,
        level=level,
        question_type=current_question["type"],
        question=current_question["text"],
        answer=user_answer,
        evaluation=evaluation,
    )

    next_index = current_index + 1

    if next_index >= len(questions):
        await update.message.reply_text(f"{evaluation}\n\nЭто был последний вопрос! Интервью завершено 🎉")
        del context.user_data["question_index"]
        return

    context.user_data["question_index"] = next_index
    next_question = questions[next_index]
    label = "💻 Live-coding" if next_question["type"] == "coding" else "Вопрос"
    await update.message.reply_text(
        f"{evaluation}\n\n{label} {next_index + 1} из {len(questions)}:\n\n{next_question['text']}"
    )