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
    372822825,  # Админ 1
     # Админ 2
]

# ================== КЛАВИАТУРЫ ==================
LANG_MENU = ReplyKeyboardMarkup(
    [["Deutsch 🇩🇪", "Русский 🇷🇺", "English 🇬🇧"]],
    resize_keyboard=True,
    one_time_keyboard=True
)

MAIN_MENU = ReplyKeyboardMarkup(
    [["Anmeldung"], ["Abmeldung"], ["🌐 Change Language"]],
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
    [[KeyboardButton("📍 Send Location", request_location=True)]],
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

def fetch_history(limit=50):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
        SELECT name, task, event, lat, lon, timestamp
        FROM shifts
        ORDER BY timestamp DESC
        LIMIT ?
    """, (limit,))
    rows = c.fetchall()
    conn.close()
    return rows

# ================== ФУНКЦИИ ==================
async def notify_admins(app, text):
    for admin_id in ADMIN_IDS:
        try:
            await app.bot.send_message(chat_id=admin_id, text=text)
        except Exception as e:
            print(f"Ошибка при уведомлении {admin_id}: {e}")

def is_admin(user_id):
    return user_id in ADMIN_IDS

def get_text(lang, key):
    texts = {
        "choose_name": {
            "de": "Bitte geben Sie Ihren Vornamen ein:",
            "ru": "Введите имя:",
            "en": "Please enter your first name:"
        },
        "choose_lastname": {
            "de": "Bitte geben Sie Ihren Nachnamen ein:",
            "ru": "Введите фамилию:",
            "en": "Please enter your last name:"
        },
        "registered": {
            "de": "Registrierung abgeschlossen ✅",
            "ru": "Регистрация завершена ✅",
            "en": "Registration completed ✅"
        },
        "already_registered": {
            "de": "Sie sind bereits registriert ✅",
            "ru": "Вы уже зарегистрированы ✅",
            "en": "You are already registered ✅"
        },
        "choose_direction": {
            "de": "Bitte wählen Sie die Richtung:",
            "ru": "Выберите направление:",
            "en": "Please choose task:"
        },
        "send_start_loc": {
            "de": "Bitte senden Sie Ihren Standort zum Start der Schicht",
            "ru": "Отправьте геолокацию для начала смены",
            "en": "Please send location to start shift"
        },
        "send_end_loc": {
            "de": "Bitte senden Sie Ihren Standort zum Ende der Schicht",
            "ru": "Отправьте геолокацию для завершения смены",
            "en": "Please send location to end shift"
        },
        "shift_started": {
            "de": "Schicht gestartet ✅",
            "ru": "Смена начата ✅",
            "en": "Shift started ✅"
        },
        "shift_ended": {
            "de": "Schicht beendet ✅",
            "ru": "Смена завершена ✅",
            "en": "Shift ended ✅"
        },
        "no_anmeldung": {
            "de": "Bitte starten Sie zuerst die Schicht (Anmeldung)",
            "ru": "❌ Сначала начните смену (Anmeldung)",
            "en": "❌ Start shift first (Anmeldung)"
        },
        "buttons_hint": {
            "de": "Bitte verwenden Sie die untenstehenden Schaltflächen ⬇️",
            "ru": "Используйте кнопки ниже ⬇️",
            "en": "Please use buttons below ⬇️"
        },
        "choose_language": {
            "de": "Bitte Sprache wählen",
            "ru": "Пожалуйста, выберите язык",
            "en": "Please choose language"
        }
    }
    return texts.get(key, {}).get(lang, texts[key]["en"])

# ================== /start ==================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text(get_text("en", "choose_language"), reply_markup=LANG_MENU)
    context.user_data["state"] = ASK_LANGUAGE

# ================== ТЕКСТ ==================
async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    state = context.user_data.get("state")
    user_id = update.effective_user.id
    user_name = update.effective_user.full_name
    lang = context.user_data.get("lang", "en")

    # --- СМЕНА ЯЗЫКА ---
    if text in ["Deutsch 🇩🇪", "Русский 🇷🇺", "English 🇬🇧"] or text == "🌐 Change Language":
        if text == "Deutsch 🇩🇪":
            context.user_data["lang"] = "de"
        elif text == "Русский 🇷🇺":
            context.user_data["lang"] = "ru"
        elif text == "English 🇬🇧":
            context.user_data["lang"] = "en"
        lang = context.user_data["lang"]
        await update.message.reply_text(get_text(lang, "choose_language"), reply_markup=LANG_MENU)
        context.user_data["state"] = ASK_LANGUAGE
        return

    # --- ВЫБОР ЯЗЫКА при старте ---
    if state == ASK_LANGUAGE:
        # Проверка регистрации
        if user_exists(user_id):
            await update.message.reply_text(get_text(lang, "already_registered"), reply_markup=MAIN_MENU)
            context.user_data.clear()
            return
        await update.message.reply_text(get_text(lang, "choose_name"))
        context.user_data["state"] = ASK_FIRSTNAME
        return

    # --- РЕГИСТРАЦИЯ ---
    if state == ASK_FIRSTNAME:
        context.user_data["first_name"] = text
        context.user_data["state"] = ASK_LASTNAME
        await update.message.reply_text(get_text(lang, "choose_lastname"))
        return

    if state == ASK_LASTNAME:
        add_user(user_id, context.user_data["first_name"], text)
        context.user_data.clear()
        await update.message.reply_text(get_text(lang, "registered"), reply_markup=MAIN_MENU)
        return

    # --- КНОПКИ ---
    if text == "Anmeldung":
        await update.message.reply_text(get_text(lang, "choose_direction"), reply_markup=TASK_MENU)
        context.user_data["state"] = ASK_TASK
        return

    if text == "Abmeldung":
        if user_id not in active_shifts:
            await update.message.reply_text(get_text(lang, "no_anmeldung"))
            return
        await update.message.reply_text(get_text(lang, "send_end_loc"), reply_markup=LOCATION_BUTTON)
        context.user_data["state"] = ASK_END_LOCATION
        return

    # --- ВЫБОР НАПРАВЛЕНИЯ ---
    if state == ASK_TASK:
        context.user_data["task"] = text
        await update.message.reply_text(get_text(lang, "send_start_loc"), reply_markup=LOCATION_BUTTON)
        context.user_data["state"] = ASK_START_LOCATION
        return

    await update.message.reply_text(get_text(lang, "buttons_hint"), reply_markup=MAIN_MENU)

# ================== ГЕОЛОКАЦИЯ ==================
async def location_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    loc = update.message.location
    state = context.user_data.get("state")
    user_id = update.effective_user.id
    user_name = update.effective_user.full_name
    task = context.user_data.get("task", "-")
    lat, lon = (loc.latitude, loc.longitude) if loc else ("-", "-")
    lang = context.user_data.get("lang", "en")

    if state == ASK_START_LOCATION:
        await update.message.reply_text(get_text(lang, "shift_started"), reply_markup=MAIN_MENU)
        active_shifts[user_id] = {"name": user_name, "task": task, "start": (lat, lon)}
        log_shift(user_id, user_name, task, "Anmeldung", lat, lon)
        await notify_admins(
            context.application,
            f"🟢 Anmeldung\n{user_name}\nTask: {task}\n📍 {lat}, {lon}"
        )
        context.user_data.clear()
        return

    if state == ASK_END_LOCATION:
        await update.message.reply_text(get_text(lang, "shift_ended"), reply_markup=MAIN_MENU)
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
        await update.message.reply_text("❌ You are not an admin")
        return

    if not active_shifts:
        await update.message.reply_text("No one is currently on shift.")
        return

    msg = "📋 Current shifts:\n"
    for u_id, info in active_shifts.items():
        task = info.get("task", "-")
        lat, lon = info.get("start", ("-", "-"))
        msg += f"👤 {info['name']}, Task: {task}, 📍 {lat}, {lon}\n"

    await update.message.reply_text(msg)

# ================== /history ==================
async def history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("❌ You are not an admin")
        return

    rows = fetch_history(limit=50)
    if not rows:
        await update.message.reply_text("No shift history.")
        return

    msg = "📜 Shift history (last 50):\n"
    for name, task, event, lat, lon, timestamp in rows:
        msg += f"{timestamp} | {event} | {name} | {task} | 📍 {lat}, {lon}\n"

    await update.message.reply_text(msg)

# ================== ЗАПУСК ==================
def main():
    init_db()
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("history", history))
    app.add_handler(MessageHandler(filters.LOCATION, location_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    print("✅ Bot started")
    app.run_polling()

if __name__ == "__main__":
    main()
