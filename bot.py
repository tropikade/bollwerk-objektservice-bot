import os
import sqlite3
from datetime import datetime, timedelta
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
    # Добавьте других админов
]

# ================== КЛАВИАТУРЫ ==================
LANG_MENU = ReplyKeyboardMarkup(
    [["Deutsch 🇩🇪", "Русский 🇷🇺", "English 🇬🇧"]],
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

def log_shift(user_id, name, task, event, lat, lon, timestamp=None):
    if not timestamp:
        timestamp = datetime.now()
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
        INSERT INTO shifts (user_id, name, task, event, lat, lon, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (user_id, name, task, event, lat, lon, timestamp.isoformat()))
    conn.commit()
    conn.close()

def fetch_history(limit=50):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
        SELECT user_id, name, task, event, lat, lon, timestamp
        FROM shifts
        ORDER BY timestamp DESC
        LIMIT ?
    """, (limit,))
    rows = c.fetchall()
    conn.close()
    return rows

def calculate_hours(user_id, start_date=None):
    """Считает суммарное время отработанных часов для пользователя с optional start_date"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    if start_date:
        c.execute("""
            SELECT event, timestamp
            FROM shifts
            WHERE user_id=? AND timestamp >= ?
            ORDER BY timestamp
        """, (user_id, start_date.isoformat()))
    else:
        c.execute("""
            SELECT event, timestamp
            FROM shifts
            WHERE user_id=?
            ORDER BY timestamp
        """, (user_id,))
    rows = c.fetchall()
    conn.close()
    total_seconds = 0
    start_time = None
    for event, ts in rows:
        dt = datetime.fromisoformat(ts)
        if event == "Anmeldung":
            start_time = dt
        elif event == "Abmeldung" and start_time:
            total_seconds += (dt - start_time).total_seconds()
            start_time = None
    return round(total_seconds / 3600, 2)  # в часах

# ================== ФУНКЦИИ ==================
def is_admin(user_id):
    return user_id in ADMIN_IDS

async def notify_admins(app, text):
    for admin_id in ADMIN_IDS:
        try:
            await app.bot.send_message(chat_id=admin_id, text=text)
        except Exception as e:
            print(f"Fehler beim Benachrichtigen {admin_id}: {e}")

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
        "choose_task": {
            "de": "Bitte wählen Sie die Aufgabe:",
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
        },
        "not_admin": {
            "de": "❌ Sie sind kein Administrator",
            "ru": "❌ Вы не администратор",
            "en": "❌ You are not an admin"
        },
        "reset_done": {
            "de": "✅ Alle Benutzer wurden zurückgesetzt und benachrichtigt.",
            "ru": "✅ Все пользователи были сброшены и уведомлены.",
            "en": "✅ All users have been reset and notified."
        }
    }
    return texts.get(key, {}).get(lang, texts[key]["en"])

# ================== /start ==================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    context.user_data.clear()
    if not user_exists(user_id):
        await update.message.reply_text(get_text("de", "choose_language"), reply_markup=LANG_MENU)
        context.user_data["state"] = ASK_LANGUAGE
    else:
        await update.message.reply_text(get_text("de", "already_registered"), reply_markup=MAIN_MENU)

# ================== TEXT HANDLER ==================
async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    state = context.user_data.get("state")
    user_id = update.effective_user.id
    user_name = update.effective_user.full_name
    lang = context.user_data.get("lang", "de")

    # --- ЯЗЫК ТОЛЬКО ПРИ РЕГИСТРАЦИИ ---
    if state == ASK_LANGUAGE:
        if text == "Deutsch 🇩🇪":
            context.user_data["lang"] = "de"
        elif text == "Русский 🇷🇺":
            context.user_data["lang"] = "ru"
        elif text == "English 🇬🇧":
            context.user_data["lang"] = "en"
        context.user_data["state"] = ASK_FIRSTNAME
        await update.message.reply_text(get_text(context.user_data["lang"], "choose_name"))
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
        await update.message.reply_text(get_text(lang, "registered"), reply_markup=MAIN_MENU)
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

    # --- Выбор задачи ---
    if state == ASK_TASK:
        context.user_data["task"] = text
        await update.message.reply_text(get_text(lang, "send_start_loc"), reply_markup=LOCATION_BUTTON)
        context.user_data["state"] = ASK_START_LOCATION
        return

    await update.message.reply_text(get_text(lang, "buttons_hint"), reply_markup=MAIN_MENU)

# ================== LOCATION HANDLER ==================
async def location_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    loc = update.message.location
    state = context.user_data.get("state")
    user_id = update.effective_user.id
    user_name = update.effective_user.full_name
    task = context.user_data.get("task", "-")
    lat, lon = (loc.latitude, loc.longitude) if loc else ("-", "-")
    lang = context.user_data.get("lang", "de")

    if state == ASK_START_LOCATION:
        await update.message.reply_text(get_text(lang, "shift_started"), reply_markup=MAIN_MENU)
        active_shifts[user_id] = {"name": user_name, "task": task, "start": (lat, lon)}
        log_shift(user_id, user_name, task, "Anmeldung", lat, lon)
        await notify_admins(context.application, f"🟢 Anmeldung\n{user_name}\nTask: {task}\n📍 {lat}, {lon}")
        context.user_data.clear()
        return

    if state == ASK_END_LOCATION:
        await update.message.reply_text(get_text(lang, "shift_ended"), reply_markup=MAIN_MENU)
        log_shift(user_id, user_name, active_shifts.get(user_id, {}).get("task", "-"), "Abmeldung", lat, lon)
        await notify_admins(context.application, f"🔴 Abmeldung\n{user_name}\n📍 {lat}, {lon}")
        if user_id in active_shifts:
            del active_shifts[user_id]
        context.user_data.clear()
        return

# ================== /status ==================
async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = "de"
    if not is_admin(user_id):
        await update.message.reply_text(get_text(lang, "not_admin"))
        return
    if not active_shifts:
        await update.message.reply_text("📋 Keine aktiven Schichten.")
        return

    msg = "📋 Aktive Schichten:\n"
    for u_id, info in active_shifts.items():
        task = info.get("task", "-")
        lat, lon = info.get("start", ("-", "-"))
        hours = calculate_hours(u_id)
        msg += f"👤 {info['name']}, Task: {task}, 📍 {lat}, {lon}, ⏱ {hours} h\n"
    await update.message.reply_text(msg)

# ================== /history ==================
async def history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = "de"
    if not is_admin(user_id):
        await update.message.reply_text(get_text(lang, "not_admin"))
        return

    rows = fetch_history(limit=50)
    if not rows:
        await update.message.reply_text("Keine Schichten in der Historie.")
        return

    msg = "📜 Schichten Historie (letzte 50):\n"
    for u_id, name, task, event, lat, lon, timestamp in rows:
        dt = datetime.fromisoformat(timestamp).strftime("%d.%m.%Y %H:%M")
        hours = calculate_hours(u_id)
        msg += f"{dt} | {event} | {name} | {task} | 📍 {lat},{lon} | ⏱ {hours} h\n"
    await update.message.reply_text(msg)

# ================== /weekly_hours ==================
async def weekly_hours(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = "de"
    if not is_admin(user_id):
        await update.message.reply_text(get_text(lang, "not_admin"))
        return

    start_week = datetime.now() - timedelta(days=datetime.now().weekday())  # Пн этой недели
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT DISTINCT user_id, name FROM shifts")
    users = c.fetchall()
    conn.close()

    if not users:
        await update.message.reply_text("Keine Stunden für diese Woche.")
        return

    msg = "⏱ Stunden diese Woche:\n"
    for u_id, name in users:
        hours = calculate_hours(u_id, start_date=start_week)
        msg += f"👤 {name} | {hours} h\n"

    await update.message.reply_text(msg)

# ================== /reset_users ==================
async def reset_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = "de"
    if not is_admin(user_id):
        await update.message.reply_text(get_text(lang, "not_admin"))
        return

    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT user_id FROM users")
    all_users = [row[0] for row in c.fetchall()]
    c.execute("DELETE FROM users")
    c.execute("DELETE FROM shifts")
    conn.commit()
    conn.close()

    active_shifts.clear()

    for uid in all_users:
        try:
            await context.bot.send_message(
                chat_id=uid,
                text="⚠️ Das System wurde aktualisiert. Bitte starten Sie /start erneut, um sich zu registrieren."
            )
        except Exception as e:
            print(f"Fehler beim Benachrichtigen von {uid}: {e}")

    await update.message.reply_text(get_text(lang, "reset_done"))

# ================== ЗАПУСК ==================
def main():
    init_db()
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("history", history))
    app.add_handler(CommandHandler("weekly_hours", weekly_hours))
    app.add_handler(CommandHandler("reset_users", reset_users))
    app.add_handler(MessageHandler(filters.LOCATION, location_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    print("✅ Bot gestartet")
    app.run_polling()

if __name__ == "__main__":
    main()
