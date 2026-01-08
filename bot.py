from aiogram import Bot, Dispatcher, executor, types
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from datetime import datetime
import sqlite3

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
