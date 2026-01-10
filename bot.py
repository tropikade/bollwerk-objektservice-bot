import os
import sqlite3
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# ================== НАСТРОЙКИ ==================
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not TOKEN:
    raise RuntimeError("TELEGRAM_BOT_TOKEN не задан")

# Список администраторов (Telegram user_id)
ADMIN_IDS = [
    123456789,  # Админ 1
    987654321,  # Админ 2
]

# ================== КЛАВИАТУРЫ ==================
LANG_MENU = ReplyKeyboardMarkup(
    [["Deutsch 🇩🇪", "Русский 🇷🇺"]],
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

# ================== СОСТОЯНИЯ ==================
ASK_LANGUAGE = 0
ASK_FIRSTNAME = 1
ASK_LASTNAME = 2
ASK_TASK = 3
ASK_START_LOCATION = 4
ASK_END_LOCATION = 5

# ================== АКТИВНЫЕ СМЕНЫ ==================
# user_id: { 'name': str, 'task': str, 'start': (lat, lon) }
active_shifts = {}

# ================== БД ==================
DB_FILE = "bollwerk_bot.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    # Пользователи
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            first_name TEXT,
            last_name TEXT
        )
    """)
    # События смен
    c.execute("""
        CREATE TABLE IF NOT EXISTS shifts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            name TEXT,
            task TEXT,
            event TEXT,
            lat REAL,
            lon REAL,
            timestamp TEXT
        )
    """)
    conn.commit()
    conn.close()

def user_exists(user_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT 1 FROM users WHERE user_id=?", (user_id,))
    exists = c.fetchone() is not None
    conn.close()
    return exists

def add_user(user_id, first_name, last_name):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (user_id, first_name, last_name) VALUES (?, ?, ?)",
              (user_id, first_name, last_name))
    conn.commit()
    conn.close()

def log_shift(user_id, name, task, event, lat, lon):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
        INSERT INTO shifts (user_id, name, task, event, lat, lon, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (user_id, name, task, event, lat, lon, datetime.now().isoformat()))
    conn.commit()
    conn.close()

# ================== ФУНКЦИИ ==================
async def notify_admins(app, text):
    for admin_id in ADMIN_IDS:
        try:
            await app.bot.send_message(chat_id=admin_id, text=text)
        except Exception as e:
            print(f"Ошибка при уведомлении {admin_id}: {e}")

def is_admin(user_id):
    return user_id in ADMIN_IDS

# ================== /start ==================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text(
        "Bitte Sprache wählen / Пожалуйста, выберите язык",
        reply_markup=LANG_MENU
    )
    context.user_data["state"] = ASK_LANGUAGE

# ================== ТЕКСТ ==================
async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    state = context.user_data.get("state")
    user_id = update.effective_user.id
    user_name = update.effective_user.full_name

    # --- ВЫБОР ЯЗЫКА ---
    if state == ASK_LANGUAGE:
        context.user_data["lang"] = "de" if "Deutsch" in text else "ru"
        if user_exists(user_id):
            await update.message.reply_text(
                "Вы уже зарегистрированы ✅",
                reply_markup=MAIN_MENU
            )
            context.user_data.clear()
            return
        await update.message.reply_text("Введите имя:")
        context.user_data["state"] = ASK_FIRSTNAME
        return

    # --- РЕГИСТРАЦИЯ ---
    if state == ASK_FIRSTNAME:
        context.user_data["first_name"] = text
        context.user_data["state"] = ASK_LASTNAME
        await update.message.reply_text("Введите фамилию:")
        return

    if state == ASK_LASTNAME:
        add_user(user_id, context.user_data["first_name"], text)
        context.user_data.clear()
        await update.message.reply_text("Регистрация завершена ✅", reply_markup=MAIN_MENU)
        return

    # --- КНОПКИ ---
    if text == "Anmeldung":
        await update.message.reply_text("Выберите направление:", reply_markup=TASK_MENU)
        context.user_data["state"] = ASK_TASK
        return

    if text == "Abmeldung":
        await update.message.reply_text("Отправьте геолокацию для завершения смены", reply_markup=LOCATION_BUTTON)
        context.user_data["state"] = ASK_END_LOCATION
        return

    # --- ВЫБОР НАПРАВЛЕНИЯ ---
    if state == ASK_TASK:
        context.user_data["task"] = text
        await update.message.reply_text("Отправьте геолокацию для начала смены", reply_markup=LOCATION_BUTTON)
        context.user_data["state"] = ASK_START_LOCATION
        return

    await update.message.reply_text("Используйте кнопки ниже ⬇️", reply_markup=MAIN_MENU)

# ================== ГЕОЛОКАЦИЯ ==================
async def location_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    loc = update.message.location
    state = context.user_data.get("state")
    user_id = update.effective_user.id
    user_name = update.effective_user.full_name
    task = context.user_data.get("task", "-")
    lat, lon = (loc.latitude, loc.longitude) if loc else ("-", "-")

    if state == ASK_START_LOCATION:
        await update.message.reply_text("Смена начата ✅", reply_markup=MAIN_MENU)
        active_shifts[user_id] = {"name": user_name, "task": task, "start": (lat, lon)}
        log_shift(user_id, user_name, task, "Anmeldung", lat, lon)
        await notify_admins(
            context.application,
            f"🟢 Anmeldung\n{user_name}\nНаправление: {task}\n📍 {lat}, {lon}"
        )
        context.user_data.clear()
        return

    if state == ASK_END_LOCATION:
        await update.message.reply_text("Смена завершена ✅", reply_markup=MAIN_MENU)
        log_shift(user_id, user_name, active_shifts.get(user_id, {}).get("task", "-"), "Abmeldung", lat, lon)
        await notify_admins(
            context.application,
            f"🔴 Abmeldung\n{user_name}\n📍 {lat}, {lon}"
        )
        if user_id in active_shifts:
            del active_shifts[user_id]
        context.user_data.clear()
        return

# ================== /status ==================
async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("❌ У вас нет прав администратора")
        return

    if not active_shifts:
        await update.message.reply_text("Никто не находится на смене.")
        return

    msg = "📋 Текущие смены:\n"
    for u_id, info in active_shifts.items():
        task = info.get("task", "-")
        lat, lon = info.get("start", ("-", "-"))
        msg += f"👤 {info['name']}, Направление: {task}, 📍 {lat}, {lon}\n"

    await update.message.reply_text(msg)

# ================== ЗАПУСК ==================
def main():
    init_db()
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(MessageHandler(filters.LOCATION, location_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    print("✅ Бот запущен")
    app.run_polling()

if __name__ == "__main__":
    main()
