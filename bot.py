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

ADMIN_IDS = [
    372822825,  # Админ 1
    # Добавьте других админов через запятую
]

# ================== КЛАВИАТУРЫ ==================
LANG_MENU = ReplyKeyboardMarkup(
    [["Deutsch 🇩🇪", "Русский 🇷🇺", "English 🇬🇧"]],
    resize_keyboard=True,
    one_time_keyboard=True
)

MAIN_MENU = lambda lang: ReplyKeyboardMarkup(
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
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            first_name TEXT,
            last_name TEXT
        )
    """)
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
        "choose_language": {
            "de": "Willkommen! Bitte wählen Sie Ihre Sprache:",
            "ru": "Добро пожаловать! Пожалуйста, выберите язык:",
            "en": "Welcome! Please choose your language:"
        },
        "choose_name": {
            "de": "Введите Ваше имя:",
            "ru": "Введите Ваше имя:",
            "en": "Enter your first name:"
        },
        "choose_lastname": {
            "de": "Введите фамилию:",
            "ru": "Введите фамилию:",
            "en": "Enter your last name:"
        },
        "registered": {
            "de": "Регистрация успешно завершена ✅",
            "ru": "Регистрация успешно завершена ✅",
            "en": "Registration completed ✅"
        },
        "already_registered": {
            "de": "Вы уже зарегистрированы ✅",
            "ru": "Вы уже зарегистрированы ✅",
            "en": "You are already registered ✅"
        },
        "choose_task": {
            "de": "Выберите направление работы:",
            "ru": "Выберите направление работы:",
            "en": "Please choose your task:"
        },
        "send_start_loc": {
            "de": "Отправьте геолокацию для начала смены:",
            "ru": "Отправьте геолокацию для начала смены:",
            "en": "Send location to start your shift:"
        },
        "send_end_loc": {
            "de": "Отправьте геолокацию для завершения смены:",
            "ru": "Отправьте геолокацию для завершения смены:",
            "en": "Send location to end your shift:"
        },
        "shift_started": {
            "de": "Смена начата ✅",
            "ru": "Смена начата ✅",
            "en": "Shift started ✅"
        },
        "shift_ended": {
            "de": "Смена завершена ✅",
            "ru": "Смена завершена ✅",
            "en": "Shift ended ✅"
        },
        "no_anmeldung": {
            "de": "❌ Сначала начните смену (Anmeldung)",
            "ru": "❌ Сначала начните смену (Anmeldung)",
            "en": "❌ Start shift first (Anmeldung)"
        },
        "buttons_hint": {
            "de": "Пожалуйста, используйте кнопки ниже ⬇️",
            "ru": "Пожалуйста, используйте кнопки ниже ⬇️",
            "en": "Please use the buttons below ⬇️"
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

    # --- Смена языка ---
    if text == "🌐 Change Language":
        await update.message.reply_text(get_text(lang, "choose_language"), reply_markup=LANG_MENU)
        context.user_data["state"] = ASK_LANGUAGE
        return

    if text in ["Deutsch 🇩🇪", "Русский 🇷🇺", "English 🇬🇧"]:
        context.user_data["lang"] = {"Deutsch 🇩🇪":"de","Русский 🇷🇺":"ru","English 🇬🇧":"en"}[text]
        lang = context.user_data["lang"]
        # Проверка регистрации
        if user_exists(user_id):
            await update.message.reply_text(get_text(lang, "already_registered"), reply_markup=MAIN_MENU(lang))
            context.user_data.clear()
        else:
            await update.message.reply_text(get_text(lang, "choose_name"), reply_markup=None)
            context.user_data["state"] = ASK_FIRSTNAME
        return

    # --- Регистрация ---
    if state == ASK_FIRSTNAME:
        context.user_data["first_name"] = text
        context.user_data["state"] = ASK_LASTNAME
        await update.message.reply_text(get_text(lang, "choose_lastname"))
        return

    if state == ASK_LASTNAME:
        add_user(user_id, context.user_data["first_name"], text)
        context.user_data.clear()
        await update.message.reply_text(get_text(lang, "registered"), reply_markup=MAIN_MENU(lang))
        return

    # --- Кнопки ---
    if text == "Anmeldung":
        await update.message.reply_text(get_text(lang, "choose_task"), reply_markup=TASK_MENU)
        context.user_data["state"] = ASK_TASK
        return

    if text == "Abmeldung":
        if user_id not in active_shifts:
            await update.message.reply_text(get_text(lang, "no_anmeldung"))
            return
        await update.message.reply_text(get_text(lang, "send_end_loc"), reply_markup=LOCATION_BUTTON)
        context.user_data["state"] = ASK_END_LOCATION
        return

    # --- Выбор направления ---
    if state == ASK_TASK:
        context.user_data["task"] = text
        await update.message.reply_text(get_text(lang, "send_start_loc"), reply_markup=LOCATION_BUTTON)
        context.user_data["state"] = ASK_START_LOCATION
        return

    # --- Подсказка по кнопкам ---
    await update.message.reply_text(get_text(lang, "buttons_hint"), reply_markup=MAIN_MENU(lang))

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
        await update.message.reply_text(get_text(lang, "shift_started"), reply_markup=MAIN_MENU(lang))
        active_shifts[user_id] = {"name": user_name, "task": task, "start": (lat, lon)}
        log_shift(user_id, user_name, task, "Anmeldung", lat, lon)
        await notify_admins(
            context.application,
            f"🟢 Anmeldung\n{user_name}\nTask: {task}\n📍 {lat}, {lon}"
        )
        context.user_data.clear()
        return

    if state == ASK_END_LOCATION:
        await update.message.reply_text(get_text(lang, "shift_ended"), reply_markup=MAIN_MENU(lang))
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
