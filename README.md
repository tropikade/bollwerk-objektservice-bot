# Bollwerk Objektservice Bot

Телеграм-бот для регистрации рабочего времени сотрудников.

## Установка

1. Клонировать репозиторий:

git clone https://github.com/ваш-пользователь/bollwerk_bot.git
cd bollwerk_bot

2. Создать локальный `.env` на основе `.env.example` и вставить токен:

cp .env.example .env
# затем открыть .env и вставить BOT_TOKEN

3. Установить зависимости:

pip3 install -r requirements.txt

4. Запустить бота:

python3 bot.py
