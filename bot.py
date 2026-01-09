from database import init_db
from telegram.ext import CommandHandler, MessageHandler, Filters
dp = updater.dispatcher
from aiogram import Bot, Dispatcher, executor, types
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from datetime import datetime
import sqlite3
from database import init_db
from database import user_exists, add_user
dp.add_handler(CommandHandler("start", start))
dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_text))
updater = Updater(TOKEN, use_context=True)
dp = updater.dispatcher

dp.add_handler(CommandHandler("start", start))
dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_text))

updater.start_polling()
updater.idle()

def start(update, context):
    user = update.effective_user

    if user_exists(user.id):
        update.message.reply_text(
            "✅ Вы уже зарегистрированы.\nВыберите действие:"
        )
        show_main_menu(update, context)
    else:
        context.user_data["state"] = "WAIT_FIRSTNAME"
        update.message.reply_text("Введите ваше *Имя*:", parse_mode="Markdown")

init_db()
from telegram import ReplyKeyboardMarkup

def show_main_menu(update, context):
    keyboard = [
        ["🟢 Anmeldung (Начать смену)"],
        ["🔴 Abmeldung (Завершить смену)"]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    update.message.reply_text("Выберите действие:", reply_markup=reply_markup)

# database.py
import sqlite3
def handle_text(update, context):
    state = context.user_data.get("state")
    text = update.message.text.strip()

    if state == "WAIT_FIRSTNAME":
        context.user_data["first_name"] = text
        context.user_data["state"] = "WAIT_LASTNAME"
        update.message.reply_text("Введите вашу *Фамилию*:", parse_mode="Markdown")
        return

    if state == "WAIT_LASTNAME":
        first_name = context.user_data.get("first_name")
        last_name = text
        user_id = update.effective_user.id

        add_user(user_id, first_name, last_name)

        context.user_data.clear()

        update.message.reply_text(
            f"✅ Регистрация завершена!\n"
            f"{first_name} {last_name}\n\n"
            f"Теперь вы можете начать смену."
        )
        show_main_menu(update, context)
        return

DB_NAME = "bollwerk.db"

def get_connection():
    return sqlite3.connect(DB_NAME)

def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        first_name TEXT NOT NULL,
        last_name TEXT NOT NULL,
        registered_at TEXT NOT NULL
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS shifts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        start_time TEXT,
        end_time TEXT,
        start_lat REAL,
        start_lon REAL,
        end_lat REAL,
        end_lon REAL,
        task TEXT,
        active INTEGER DEFAULT 1,
        FOREIGN KEY(user_id) REFERENCES users(user_id)
    )
    """)

    conn.commit()
    conn.close()

BOT_TOKEN = "ВАШ_ТОКЕН"

bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# База данных
conn = sqlite3.connect("worktime.db")
cursor = conn.cursor()
cursor.execute("""
CREATE TABLE IF NOT EXISTS logs (
    user_id INTEGER,
    name TEXT,
    action TEXT,
    datetime TEXT,
    latitude REAL,
    longitude REAL
)
""")
conn.commit()

# Состояния
class WorkState(StatesGroup):
    waiting_for_location = State()

# Клавиатуры
def main_keyboard():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("🟢 Anmeldung", "🔴 Abmeldung")
    return kb

def location_keyboard():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    kb.add(types.KeyboardButton("📍 Отправить геолокацию", request_location=True))
    return kb

# Старт
@dp.message_handler(commands=["start"])
async def start(message: types.Message):
    await message.answer(
        "Добро пожаловать в Bollwerk Objektservice!\nВыберите действие:",
        reply_markup=main_keyboard()
    )

# Обработка кнопок Anmeldung/Abmeldung
@dp.message_handler(lambda m: m.text in ["🟢 Anmeldung", "🔴 Abmeldung"])
async def action_handler(message: types.Message):
    user_id = message.from_user.id
    action = "Anmeldung" if message.text == "🟢 Anmeldung" else "Abmeldung"
    
    # Проверка логики
    if action == "Abmeldung":
        cursor.execute("SELECT * FROM logs WHERE user_id=? AND action='Anmeldung' ORDER BY datetime DESC", (user_id,))
        last_login = cursor.fetchone()
        if not last_login:
            await message.answer("❌ Вы не можете сделать Abmeldung без предыдущего Anmeldung.", reply_markup=main_keyboard())
            return

    # Сохраняем действие в состоянии
    await WorkState.waiting_for_location.set()
    await dp.current_state(user=user_id).update_data(action=action)
    await message.answer("Пожалуйста, отправьте вашу геолокацию:", reply_markup=location_keyboard())

# Обработка геолокации
@dp.message_handler(content_types=types.ContentType.LOCATION, state=WorkState.waiting_for_location)
async def location_handler(message: types.Message, state: types.Dispatcher):
    data = await state.get_data()
    action = data.get("action")
    cursor.execute(
        "INSERT INTO logs VALUES (?, ?, ?, ?, ?, ?)",
        (
            message.from_user.id,
            message.from_user.full_name,
            action,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            message.location.latitude,
            message.location.longitude
        )
    )
    conn.commit()
    await message.answer(f"✅ {action} зафиксирована", reply_markup=main_keyboard())
    await state.finish()

# Просмотр логов (для админа)
@dp.message_handler(commands=["logs"])
async def admin_logs(message: types.Message):
    admin_ids = [ВАШ_TELEGRAM_ID]  # Добавьте свои ID для админ-доступа
    if message.from_user.id not in admin_ids:
        await message.answer("❌ У вас нет доступа")
        return

    cursor.execute("SELECT * FROM logs ORDER BY datetime DESC")
    records = cursor.fetchall()
    if not records:
        await message.answer("Нет записей")
        return

    text = "📝 Логи сотрудников:\n\n"
    for r in records:
        text += f"{r[1]} | {r[2]} | {r[3]} | {r[4]}, {r[5]}\n"
    await message.answer(text)

if __name__ == "__main__":
    executor.start_polling(dp)
from telegram.ext import Updater

updater = Updater(TOKEN, use_context=True)
dp = updater.dispatcher

# handlers где-то тут

updater.start_polling()
updater.idle()
