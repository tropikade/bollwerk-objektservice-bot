import os

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

if not TOKEN:
    raise RuntimeError("TELEGRAM_BOT_TOKEN не задан")
import sqlite3
from datetime import datetime
from telegram import ReplyKeyboardMarkup, KeyboardButton, Update
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext
from database import init_db

init_db()
from dotenv import load_dotenv
load_dotenv()

# ====== Настройки ======
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
if not TOKEN:
    raise ValueError("⚠️ Токен не найден! Установите переменную окружения TELEGRAM_BOT_TOKEN")

DB_NAME = "bollwerk.db"

# ====== Работа с базой ======
def get_connection():
    return sqlite3.connect(DB_NAME)

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        first_name TEXT,
        last_name TEXT,
        registered_at TEXT
    )
    """)
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS shifts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        start_time TEXT,
        end_time TEXT,
        start_lat REAL,
        start_lon REAL,
        end_lat REAL,
        end_lon REAL,
        task TEXT,
        active INTEGER DEFAULT 1
    )
    """)
    conn.commit()
    conn.close()

def user_exists(user_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM users WHERE user_id=?", (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result is not None

def add_user(user_id, first_name, last_name):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO users (user_id, first_name, last_name, registered_at) VALUES (?, ?, ?, ?)",
        (user_id, first_name, last_name, datetime.now().isoformat())
    )
    conn.commit()
    conn.close()

def start_shift(user_id, task, lat, lon):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO shifts (user_id, start_time, start_lat, start_lon, task) VALUES (?, ?, ?, ?, ?)",
        (user_id, datetime.now().isoformat(), lat, lon, task)
    )
    conn.commit()
    conn.close()

def end_shift(user_id, lat, lon):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id FROM shifts WHERE user_id=? AND active=1 ORDER BY start_time DESC LIMIT 1",
        (user_id,)
    )
    row = cursor.fetchone()
    if row:
        shift_id = row[0]
        cursor.execute(
            "UPDATE shifts SET end_time=?, end_lat=?, end_lon=?, active=0 WHERE id=?",
            (datetime.now().isoformat(), lat, lon, shift_id)
        )
    conn.commit()
    conn.close()

# ====== Бот ======
user_states = {}  # Временные состояния

def start(update: Update, context: CallbackContext):
    user = update.effective_user
    if user_exists(user.id):
        update.message.reply_text("✅ Вы уже зарегистрированы.")
        show_main_menu(update)
    else:
        user_states[user.id] = {"state": "WAIT_FIRSTNAME"}
        update.message.reply_text("Введите ваше имя:")

def handle_text(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    text = update.message.text.strip()

    # Регистрация
    if user_id in user_states:
        state = user_states[user_id]["state"]
        if state == "WAIT_FIRSTNAME":
            user_states[user_id]["first_name"] = text
            user_states[user_id]["state"] = "WAIT_LASTNAME"
            update.message.reply_text("Введите вашу фамилию:")
            return
        elif state == "WAIT_LASTNAME":
            first_name = user_states[user_id]["first_name"]
            last_name = text
            add_user(user_id, first_name, last_name)
            del user_states[user_id]
            update.message.reply_text(f"✅ Регистрация завершена!\n{first_name} {last_name}")
            show_main_menu(update)
            return

    # Главное меню Anmeldung / Abmeldung
    if text in ["🟢 Anmeldung", "🔴 Abmeldung"]:
        user_states[user_id] = {"state": "WAIT_TASK", "action": text}
        keyboard = ReplyKeyboardMarkup(
            [["garten", "sport", "reinigung"]], resize_keyboard=True, one_time_keyboard=True
        )
        update.message.reply_text("Выберите направление работы:", reply_markup=keyboard)
        return

    # Выбор направления перед сменой
    if user_id in user_states and user_states[user_id]["state"] == "WAIT_TASK":
        user_states[user_id]["task"] = text
        user_states[user_id]["state"] = "WAIT_LOCATION"
        keyboard = ReplyKeyboardMarkup(
            [[KeyboardButton("Отправить геолокацию 📍", request_location=True)]],
            resize_keyboard=True, one_time_keyboard=True
        )
        update.message.reply_text("Отправьте вашу геолокацию:", reply_markup=keyboard)
        return

    update.message.reply_text("Пожалуйста, используйте кнопки меню.")

def handle_location(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    if user_id not in user_states or user_states[user_id]["state"] != "WAIT_LOCATION":
        update.message.reply_text("Пожалуйста, начните смену через главное меню.")
        return

    lat = update.message.location.latitude
    lon = update.message.location.longitude
    task = user_states[user_id]["task"]
    action = user_states[user_id]["action"]

    if action == "🟢 Anmeldung":
        start_shift(user_id, task, lat, lon)
        update.message.reply_text(f"✅ Смена началась! Направление: {task}")
    elif action == "🔴 Abmeldung":
        end_shift(user_id, lat, lon)
        update.message.reply_text(f"✅ Смена завершена! Направление: {task}")

    del user_states[user_id]
    show_main_menu(update)

def show_main_menu(update: Update):
    keyboard = ReplyKeyboardMarkup([["🟢 Anmeldung", "🔴 Abmeldung"]], resize_keyboard=True)
    update.message.reply_text("Выберите действие:", reply_markup=keyboard)

# ====== Запуск ======
def main():
    init_db()
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_text))
    dp.add_handler(MessageHandler(Filters.location, handle_location))

    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
