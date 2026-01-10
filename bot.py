import os
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from database import init_db, user_exists, add_user
from telegram import ReplyKeyboardMarkup, KeyboardButton
MAIN_MENU = ReplyKeyboardMarkup(
    [["Anmeldung"], ["Abmeldung"]],
    resize_keyboard=True
)

TASK_MENU = ReplyKeyboardMarkup(
    [
        ["Garten", "Sport Training"],
        ["Reinigung"]
    ],
    resize_keyboard=True,
    one_time_keyboard=True
)

LOCATION_BUTTON = ReplyKeyboardMarkup(
    [[KeyboardButton("📍 Standort senden", request_location=True)]],
    resize_keyboard=True,
    one_time_keyboard=True
)
MAIN_MENU = ReplyKeyboardMarkup(
    [["Anmeldung"], ["Abmeldung"]],
    resize_keyboard=True
)

TASK_MENU = ReplyKeyboardMarkup(
    [
        ["Garten", "Sport Training"],
        ["Reinigung"]
    ],
    resize_keyboard=True,
    one_time_keyboard=True
)

LOCATION_BUTTON = ReplyKeyboardMarkup(
    [[KeyboardButton("📍 Standort senden", request_location=True)]],
    resize_keyboard=True,
    one_time_keyboard=True
)
ASK_TASK = 3
ASK_START_LOCATION = 4
ASK_END_LOCATION = 5

# --- ИНИЦИАЛИЗАЦИЯ ---
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not TOKEN:
    raise RuntimeError("TELEGRAM_BOT_TOKEN не задан")

init_db()

# --- СОСТОЯНИЯ ---
ASK_FIRSTNAME = 1
ASK_LASTNAME = 2


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if user_exists(user_id):
        await update.message.reply_text("Вы уже зарегистрированы ✅")
        return

    await update.message.reply_text("Введите имя:")
    context.user_data["state"] = ASK_FIRSTNAME


async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    state = context.user_data.get("state")

    if state == ASK_FIRSTNAME:
        context.user_data["first_name"] = update.message.text
        context.user_data["state"] = ASK_LASTNAME
        await update.message.reply_text("Введите фамилию:")

    elif state == ASK_LASTNAME:
        add_user(
            update.effective_user.id,
            context.user_data["first_name"],
            update.message.text
        )
        context.user_data.clear()
        await update.message.reply_text("Регистрация завершена ✅")

    else:
        await update.message.reply_text("Напишите /start")


def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))

    print("✅ Бот запущен")
    app.run_polling()


if __name__ == "__main__":
    main()
