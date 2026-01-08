import os
import sqlite3
from datetime import datetime

from aiogram import Bot, Dispatcher, executor, types
from dotenv import load_dotenv

load_dotenv()
BOT_TOKEN = os.getenv("")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)

# ================= DATABASE =================
conn = sqlite3.connect("worktime.db")
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    vorname TEXT,
    nachname TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS worktime (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    start_time TEXT,
    start_lat REAL,
    start_lon REAL,
    end_time TEXT,
    end_lat REAL,
    end_lon REAL
)
""")

conn.commit()

# ================= KEYBOARDS =================
def main_keyboard():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("🟢 Anmeldung", "🔴 Abmeldung")
    return kb

def location_keyboard():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    kb.add(types.KeyboardButton("📍 Standort senden", request_location=True))
    return kb

# ================= START =================
@dp.message_handler(commands=["start"])
async def start(message: types.Message):
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (message.from_user.id,))
    user = cursor.fetchone()

    if user:
        await message.answer(
            "Willkommen zurück bei Bollwerk Objektservice.",
            reply_markup=main_keyboard()
        )
    else:
        await message.answer("Willkommen! Bitte geben Sie Ihren Vornamen ein:")

# ================= REGISTRATION =================
@dp.message_handler(lambda m: m.text and not m.text.startswith("/"))
async def registration(message: types.Message):
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (message.from_user.id,))
    user = cursor.fetchone()

    if not user:
        cursor.execute(
            "INSERT OR IGNORE INTO users (user_id, vorname) VALUES (?, ?)",
            (message.from_user.id, message.text)
        )
        conn.commit()
        await message.answer("Danke. Bitte geben Sie jetzt Ihren Nachnamen ein:")
        return

    if user and user[2] is None:
        cursor.execute(
            "UPDATE users SET nachname = ? WHERE user_id = ?",
            (message.text, message.from_user.id)
        )
        conn.commit()
        await message.answer(
            "Registrierung abgeschlossen.",
            reply_markup=main_keyboard()
        )

# ================= ACTIONS =================
@dp.message_handler(lambda m: m.text in ["🟢 Anmeldung", "🔴 Abmeldung"])
async def action(message: types.Message):
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (message.from_user.id,))
    user = cursor.fetchone()

    if not user or not user[2]:
        await message.answer("Bitte registrieren Sie sich zuerst mit Vor- und Nachnamen.")
        return

    await message.answer(
        "Bitte senden Sie Ihren Standort.",
        reply_markup=location_keyboard()
    )
    dp.current_action = message.text

# ================= LOCATION =================
@dp.message_handler(content_types=types.ContentType.LOCATION)
async def location_handler(message: types.Message):
    action = dp.current_action
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if action == "🟢 Anmeldung":
        cursor.execute("""
        INSERT INTO worktime (user_id, start_time, start_lat, start_lon)
        VALUES (?, ?, ?, ?)
        """, (
            message.from_user.id,
            now,
            message.location.latitude,
            message.location.longitude
        ))
        conn.commit()
        await message.answer("✅ Anmeldung erfolgreich.", reply_markup=main_keyboard())

    elif action == "🔴 Abmeldung":
        cursor.execute("""
        SELECT id FROM worktime
        WHERE user_id = ? AND end_time IS NULL
        ORDER BY id DESC LIMIT 1
        """, (message.from_user.id,))
        row = cursor.fetchone()

        if not row:
            await message.answer("❌ Keine aktive Anmeldung gefunden.")
            return

        cursor.execute("""
        UPDATE worktime
        SET end_time = ?, end_lat = ?, end_lon = ?
        WHERE id = ?
        """, (
            now,
            message.location.latitude,
            message.location.longitude,
            row[0]
        ))
        conn.commit()
        await message.answer("✅ Abmeldung erfolgreich.", reply_markup=main_keyboard())

# ================= RUN =================
if __name__ == "__main__":
    executor.start_polling(dp)
