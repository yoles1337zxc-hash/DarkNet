import os
import threading
import sqlite3
import random
import telebot
from flask import Flask

# Берем токен из настроек Render
TOKEN = os.environ.get("BOT_TOKEN")

# --- БАЗА ДАННЫХ ---
DB_FILE = "game.db"

def init_db():
    # Создаем таблицу, если её нет
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            balance INTEGER DEFAULT 0,
            last_claim INTEGER DEFAULT 0
        )
    ''')
    conn.commit()
    conn.close()

def get_balance(user_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else 0

def add_balance(user_id, amount):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    # Если пользователя нет - создаем
    cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
    # Добавляем деньги
    cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
    conn.commit()
    conn.close()


# --- ВЕБ-СЕРВЕР ДЛЯ RENDER ---
app = Flask(__name__)

@app.route('/')
def health():
    return "Bot is running"

def run_web():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)


# --- БОТ TELEGRAM ---
bot = telebot.TeleBot(TOKEN)

@bot.message_handler(commands=['start'])
def start(message):
    init_db() # Проверяем базу при старте
    bot.send_message(message.chat.id, "🟢 Привет, хакер! Терминал подключен к сети.\nПиши /claim, чтобы получить кредиты.")

@bot.message_handler(commands=['claim'])
def claim(message):
    user_id = message.from_user.id
    # Даем 100 кредитов
    add_balance(user_id, 100)
    new_bal = get_balance(user_id)
    bot.send_message(message.chat.id, f"💸 Вы забрали 100 ₽.\nВаш баланс: {new_bal} ₽")

@bot.message_handler(commands=['profile'])
def profile(message):
    user_id = message.from_user.id
    bal = get_balance(user_id)
    bot.send_message(message.chat.id, f"👤 Ваш профиль:\nБаланс: {bal} ₽")

@bot.message_handler(commands=['case'])
def case(message):
    user_id = message.from_user.id
    bal = get_balance(user_id)
    
    if bal < 50:
        bot.send_message(message.chat.id, "❌ Недостаточно средств! Нужно 50 ₽. Жми /claim.")
        return
        
    # Списываем 50 кредитов
    add_balance(user_id, -50)
    
    # Выдаем случайный предмет (просто текст для теста)
    items = ["Скрипт 'Червь'", "Троян-невидимка", "Бот-парсер", "Нейросеть 'Оракул'"]
    dropped = random.choice(items)
    
    bot.send_message(message.chat.id, f"📦 Архив вскрыт!\nВыпало: {dropped}\nСписано: 50 ₽")

# Запуск сервера и бота
threading.Thread(target=run_web, daemon=True).start()

print("Бот запущен...")
bot.infinity_polling()
