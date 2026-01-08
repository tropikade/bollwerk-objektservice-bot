import os
import sqlite3
from datetime import datetime
import pandas as pd

from aiogram import Bot, Dispatcher, types, executor
from dotenv import load_dotenv

# ================== LOAD TOKEN ==================
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise Exception("BOT_TOKEN nicht gefunden. Prüfen Sie die .env Datei.")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)

# ================== DATABASE ==================
# ================== DATABASE ==================
import sqlite3

# ================== DATABASE ==================
conn = sqlite3.connect("worktime.db")
cursor = conn.cursor()

# Таблица пользователей
cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    vorname TEXT,
    nachname TEXT,
    language TEXT,
    current_action TEXT
)
""")

# Таблица рабочих смен
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

# ================== MESSAGES ==================
MESSAGES = {
    "choose_language": {
        "de": "Bitte wählen Sie Ihre Sprache:",
        "ru": "Пожалуйста, выберите язык:",
        "en": "Please select your language:",
        "uk": "Будь ласка, виберіть мову:"
    },
    "enter_first_name": {
        "de": "Bitte geben Sie Ihren Vornamen ein:",
        "ru": "Пожалуйста, введите имя:",
        "en": "Please enter your first name:",
        "uk": "Будь ласка, введіть ім'я:"
    },
    "enter_last_name": {
        "de": "Bitte geben Sie Ihren Nachnamen ein:",
        "ru": "Пожалуйста, введите фамилию:",
        "en": "Please enter your last name:",
        "uk": "Будь ласка, введіть прізвище:"
    },
    "registration_complete": {
        "de": "Registrierung abgeschlossen.",
        "ru": "Регистрация завершена.",
        "en": "Registration completed.",
        "uk": "Реєстрацію завершено."
    },
    "welcome_back": {
        "de": "Willkommen zurück bei Bollwerk Objektservice.",
        "ru": "С возвращением в Bollwerk Objektservice.",
        "en": "Welcome back to Bollwerk Objektservice.",
        "uk": "Ласкаво просимо в Bollwerk Objektservice."
    },
    "send_location_start": {
        "de": "Bitte senden Sie Ihren Standort zum Arbeitsbeginn.",
        "ru": "Пожалуйста, отправьте ваше местоположение для начала работы.",
        "en": "Please send your location to start work.",
        "uk": "Будь ласка, надішліть своє місцезнаходження для початку роботи."
    },
    "send_location_end": {
        "de": "Bitte senden Sie Ihren Standort zum Arbeitsende.",
        "ru": "Пожалуйста, отправьте ваше местоположение для окончания работы.",
        "en": "Please send your location to end work.",
        "uk": "Будь ласка, надішліть своє місцезнаходження для закінчення роботи."
    },
    "already_active": {
        "de": "❌ Sie haben bereits eine aktive Schicht.",
        "ru": "❌ У вас уже есть активная смена.",
        "en": "❌ You already have an active shift.",
        "uk": "❌ У вас вже є активна зміна."
    },
    "no_active_shift": {
        "de": "❌ Keine aktive Schicht gefunden.",
        "ru": "❌ Активная смена не найдена.",
        "en": "❌ No active shift found.",
        "uk": "❌ Активну зміну не знайдено."
    },
    "action_success": {
        "de": "✅ Aktion erfolgreich.",
        "ru": "✅ Действие выполнено успешно.",
        "en": "✅ Action completed successfully.",
        "uk": "✅ Дія виконана успішно."
    }
}

# ================== KEYBOARDS ==================
def language_keyboard():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    kb.add("Deutsch", "Русский", "English", "Українська")
    return kb

def main_keyboard():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("🟢 Anmeldung", "🔴 Abmeldung")
    kb.add("📊 Monatsbericht")
    return kb

def location_keyboard():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    kb.add(types.KeyboardButton("📍 Standort senden", request_location=True))
    return kb

# ================== START ==================
@dp.message_handler(commands=["start"])
async def start(message: types.Message):
    user_id = message.from_user.id
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()

    if user:
        lang = user[3] if user[3] else "de"
        await message.answer(MESSAGES["welcome_back"][lang], reply_markup=main_keyboard())
    else:
        await message.answer(MESSAGES["choose_language"]["de"], reply_markup=language_keyboard())
        cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
        conn.commit()

# ================== LANGUAGE SELECTION ==================
@dp.message_handler(lambda m: m.text in ["Deutsch", "Русский", "English", "Українська"])
async def set_language(message: types.Message):
    user_id = message.from_user.id
    lang_map = {"Deutsch":"de","Русский":"ru","English":"en","Українська":"uk"}
    lang = lang_map.get(message.text, "de")
    cursor.execute("UPDATE users SET language = ? WHERE user_id = ?", (lang, user_id))
    conn.commit()
    await message.answer(MESSAGES["enter_first_name"][lang])

# ================== REGISTRATION ==================
@dp.message_handler(lambda m: m.text and m.text not in ["🟢 Anmeldung", "🔴 Abmeldung", "📊 Monatsbericht",
                                                      "Deutsch","Русский","English","Українська"])
async def registration(message: types.Message):
    user_id = message.from_user.id
    cursor.execute("SELECT vorname, nachname, language FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()
    if not user:
        return

    lang = user[2] if user[2] else "de"

    if not user[0]:
        cursor.execute("UPDATE users SET vorname = ? WHERE user_id = ?", (message.text, user_id))
        conn.commit()
        await message.answer(MESSAGES["enter_last_name"][lang])
    elif not user[1]:
        cursor.execute("UPDATE users SET nachname = ? WHERE user_id = ?", (message.text, user_id))
        conn.commit()
        await message.answer(MESSAGES["registration_complete"][lang], reply_markup=main_keyboard())

# ================== BUTTONS ==================
@dp.message_handler(lambda m: m.text in ["🟢 Anmeldung", "🔴 Abmeldung", "📊 Monatsbericht"])
async def buttons(message: types.Message):
    user_id = message.from_user.id
    cursor.execute("SELECT language FROM users WHERE user_id = ?", (user_id,))
    lang = cursor.fetchone()[0] if cursor.fetchone() else "de"

    cursor.execute("""
    SELECT id FROM worktime
    WHERE user_id = ? AND end_time IS NULL
    """, (user_id,))
    active_shift = cursor.fetchone()

    if message.text == "🟢 Anmeldung":
        if active_shift:
            await message.answer(MESSAGES["already_active"][lang])
            return
        cursor.execute("UPDATE users SET current_action='ANMELDUNG' WHERE user_id = ?", (user_id,))
        conn.commit()
        await message.answer(MESSAGES["send_location_start"][lang], reply_markup=location_keyboard())

    elif message.text == "🔴 Abmeldung":
        if not active_shift:
            await message.answer(MESSAGES["no_active_shift"][lang])
            return
        cursor.execute("UPDATE users SET current_action='ABMELDUNG' WHERE user_id = ?", (user_id,))
        conn.commit()
        await message.answer(MESSAGES["send_location_end"][lang], reply_markup=location_keyboard())

    elif message.text == "📊 Monatsbericht":
        await generate_report(message, lang)

# ================== LOCATION HANDLER ==================
@dp.message_handler(content_types=types.ContentType.LOCATION)
async def location_handler(message: types.Message):
    user_id = message.from_user.id
    cursor.execute("SELECT current_action, language FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    if not row or not row[0]:
        await message.answer("❌ Bitte wählen Sie zuerst eine Aktion.")
        return

    action, lang = row
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if action == "ANMELDUNG":
        cursor.execute("""
        INSERT INTO worktime (user_id, start_time, start_lat, start_lon)
        VALUES (?, ?, ?, ?)
        """, (user_id, now, message.location.latitude, message.location.longitude))
    elif action == "ABMELDUNG":
        cursor.execute("""
        UPDATE worktime
        SET end_time=?, end_lat=?, end_lon=?
        WHERE user_id=? AND end_time IS NULL
        """, (now, message.location.latitude, message.location.longitude, user_id))

    cursor.execute("UPDATE users SET current_action=NULL WHERE user_id=?", (user_id,))
    conn.commit()
    await message.answer(MESSAGES["action_success"][lang], reply_markup=main_keyboard())

# ================== REPORT GENERATION ==================
async def generate_report(message, lang="de"):
    # Берём текущий месяц
    month_str = datetime.now().strftime("%Y-%m")
    df = pd.read_sql_query(f"""
    SELECT u.vorname, u.nachname, w.start_time, w.start_lat, w.start_lon,
           w.end_time, w.end_lat, w.end_lon
    FROM worktime w
    JOIN users u ON u.user_id = w.user_id
    WHERE strftime('%Y-%m', w.start_time) = '{month_str}'
    """, conn)

    csv_file = f"work_report_{month_str}.csv"
    excel_file = f"work_report_{month_str}.xlsx"
    df.to_csv(csv_file, index=False)
    df.to_excel(excel_file, index=False)
    await message.answer(f"📊 Bericht für {month_str} erstellt:\nCSV: {csv_file}\nExcel: {excel_file}")

# ================== RUN ==================
if __name__ == "__main__":
    executor.start_polling(dp)
