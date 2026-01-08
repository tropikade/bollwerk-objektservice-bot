import os
import sqlite3
from datetime import datetime

from aiogram import Bot, Dispatcher, executor, types
from dotenv import load_dotenv

# ================== ENV ==================
load_dotenv()
BOT_TOKEN = os.getenv("8542702168:AAFOPofmRm3R7MLFRTfGxmGL_5YV6Fvhk4I")

if not BOT_TOKEN:
    raise Exception("BOT_TOKEN nicht gefunden. Prüfen Sie die .env Datei.")


# ================== BOT ==================
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)

# ================== DATABASE ==================
conn = sqlite3.connect("worktime.db")
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    vorname TEXT,
    nachname TEXT,
    current_action TEXT
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

# ================== KEYBOARDS ==================
def main_keyboard():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("🟢 Anmeldung", "🔴 Abmeldung")
    return kb

def location_keyboard():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    kb.add(types.KeyboardButton("📍 Standort senden", request_location=True))
    return kb

# ================== START ==================
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
        cursor.execute(
            "INSERT INTO users (user_id) VALUES (?)",
            (message.from_user.id,)
        )
        conn.commit()
        await message.answer("Bitte geben Sie Ihren Vornamen ein:")

# ================== REGISTRATION ==================
@dp.message_handler(lambda m: m.text and not m.text.startswith("/"))
async def registration(message: types.Message):
    user_id = message.from_user.id

    cursor.execute(
        "SELECT vorname, nachname FROM users WHERE user_id = ?",
        (user_id,)
    )
    user = cursor.fetchone()

    if user and not user[0]:
        cursor.execute(
            "UPDATE users SET vorname = ? WHERE user_id = ?",
            (message.text, user_id)
        )
        conn.commit()
        await message.answer("Bitte geben Sie Ihren Nachnamen ein:")
        return

    if user and user[0] and not user[1]:
        cursor.execute(
            "UPDATE users SET nachname = ? WHERE user_id = ?",
            (message.text, user_id)
        )
        conn.commit()
        await message.answer(
            "Registrierung abgeschlossen.",
            reply_markup=main_keyboard()
        )

# ================== BUTTONS ==================
@dp.message_handler(lambda m: m.text in ["🟢 Anmeldung", "🔴 Abmeldung"])
async def action(message: types.Message):
    user_id = message.from_user.id

    cursor.execute("""
    SELECT id FROM worktime
    WHERE user_id = ? AND end_time IS NULL
    """, (user_id,))
    active_shift = cursor.fetchone()

    if message.text == "🟢 Anmeldung":
        if active_shift:
            await message.answer("❌ Sie haben bereits eine aktive Schicht.")
            return

        cursor.execute(
            "UPDATE users SET current_action = 'ANMELDUNG' WHERE user_id = ?",
            (user_id,)
        )
        conn.commit()

        await message.answer(
            "Bitte senden Sie Ihren Standort zum Arbeitsbeginn.",
            reply_markup=location_keyboard()
        )

    elif message.text == "🔴 Abmeldung":
        if not active_shift:
            await message.answer("❌ Keine aktive Schicht gefunden.")
            return

        cursor.execute(
            "UPDATE users SET current_action = 'ABMELDUNG' WHERE user_id = ?",
            (user_id,)
        )
        conn.commit()

        await message.answer(
            "Bitte senden Sie Ihren Standort zum Arbeitsende.",
            reply_markup=location_keyboard()
        )

# ================== LOCATION ==================
@dp.message_handler(content_types=types.ContentType.LOCATION)
async def location_handler(message: types.Message):
    user_id = message.from_user.id

    cursor.execute(
        "SELECT current_action FROM users WHERE user_id = ?",
        (user_id,)
    )
    row = cursor.fetchone()

    if not row or not row[0]:
        await message.answer("❌ Bitte wählen Sie zuerst eine Aktion.")
        return

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if row[0] == "ANMELDUNG":
        cursor.execute("""
        INSERT INTO worktime (user_id, start_time, start_lat, start_lon)
        VALUES (?, ?, ?, ?)
        """, (
            user_id,
            now,
            message.location.latitude,
            message.location.longitude
        ))

    elif row[0] == "ABMELDUNG":
        cursor.execute("""
        UPDATE worktime
        SET end_time = ?, end_lat = ?, end_lon = ?
        WHERE user_id = ? AND end_time IS NULL
        """, (
            now,
            message.location.latitude,
            message.location.longitude,
            user_id
        ))

    cursor.execute(
        "UPDATE users SET current_action = NULL WHERE user_id = ?",
        (user_id,)
    )
    conn.commit()

    await message.answer("✅ Aktion erfolgreich.", reply_markup=main_keyboard())

# ================== RUN ==================
if __name__ == "__main__":
    executor.start_polling(dp)
