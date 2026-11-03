from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters

from config import TELEGRAM_BOT_TOKEN
from handlers import start_command, feedback_command, handle_button_click, handle_text_answer
from database import init_db


async def post_init(application: Application) -> None:
    await init_db()


def main() -> None:
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).post_init(post_init).build()

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("feedback", feedback_command))
    application.add_handler(CallbackQueryHandler(handle_button_click))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_answer))

    print("Бот запущен, жду сообщений...")
    application.run_polling()


if __name__ == "__main__":
    main()