import sqlite3
from datetime import datetime

DB_NAME = "bollwerk.db"


def get_connection():
    return sqlite3.connect(DB_NAME)


def init_db():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        first_name TEXT NOT NULL,
        last_name TEXT NOT NULL,
        registered_at TEXT NOT NULL
    )
    """)

    cur.execute("""
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


def user_exists(user_id: int) -> bool:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM users WHERE user_id = ?", (user_id,))
    result = cur.fetchone()
    conn.close()
    return result is not None


def add_user(user_id: int, first_name: str, last_name: str):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO users VALUES (?, ?, ?, ?)",
        (user_id, first_name, last_name, datetime.now().isoformat())
    )
    conn.commit()
    conn.close()
