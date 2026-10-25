import os
import threading
import sqlite3
import random
import time
import telebot
from flask import Flask

TOKEN = os.environ.get("BOT_TOKEN")
DB_FILE = "game.db"

# --- БАЗА ДАННЫХ ---
def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            balance INTEGER DEFAULT 0,
            last_claim INTEGER DEFAULT 0,
            base_income INTEGER DEFAULT 10
        )
    ''')
    conn.commit()
    conn.close()

def get_user(user_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT balance, last_claim, base_income FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    
    if not row:
        # Если юзера нет, создаем его
        now = int(time.time())
        cursor.execute("INSERT INTO users (user_id, last_claim) VALUES (?, ?)", (user_id, now))
        conn.commit()
        conn.close()
        return 0, now, 10
        
    conn.close()
    return row[0], row[1], row[2]

def update_balance_and_time(user_id, new_balance, new_time):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET balance = ?, last_claim = ? WHERE user_id = ?", (new_balance, new_time, user_id))
    conn.commit()
    conn.close()

# --- ВЕБ-СЕРВЕР ДЛЯ RENDER ---
app = Flask(__name__)

from flask import render_template

@app.route('/')
def health():
    return render_template('index.html')

def run_web():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

# --- БОТ TELEGRAM ---
bot = telebot.TeleBot(TOKEN)

@bot.message_handler(commands=['start'])
def start(message):
    init_db()
    get_user(message.from_user.id)
    bot.send_message(message.chat.id, "🟢 Терминал подключен!\nЗаходи раз в 4 часа, чтобы забирать доход.")

@bot.message_handler(commands=['claim'])
def claim(message):
    user_id = message.from_user.id
    balance, last_claim, base_income = get_user(user_id)
    
    now = int(time.time())
    seconds_passed = now - last_claim
    hours_passed = seconds_passed / 3600.0
    
    # Ограничение накопления: максимум 4 часа
    hours_passed = min(hours_passed, 4.0)
    
    # Формула дохода
    earned = int(base_income * hours_passed)
    
    if earned < 1:
        bot.send_message(message.chat.id, "⏳ Сеть еще не накопила данные. Подожди немного.")
        return
        
    new_balance = balance + earned
    update_balance_and_time(user_id, new_balance, now)
    
    bot.send_message(message.chat.id, f"💸 Вы забрали {earned} ₽.\nБаланс: {new_balance} ₽")

@bot.message_handler(commands=['profile'])
def profile(message):
    user_id = message.from_user.id
    balance, _, base_income = get_user(user_id)
    bot.send_message(message.chat.id, f"👤 Баланс: {balance} ₽\n📈 Доход: {base_income} ₽/ч")

@bot.message_handler(commands=['case'])
def case(message):
    user_id = message.from_user.id
    balance, last_claim, base_income = get_user(user_id)
    
    if balance < 50:
        bot.send_message(message.chat.id, "❌ Недостаточно средств! Нужно 50 ₽.")
        return
        
    # Списываем 50 кредитов
    new_balance = balance - 50
    update_balance_and_time(user_id, new_balance, last_claim)
    
    items = ["Скрипт 'Червь'", "Троян-невидимка", "Бот-парсер", "Нейросеть 'Оракул'"]
    dropped = random.choice(items)
    
    bot.send_message(message.chat.id, f"📦 Выпало: {dropped}\nСписано: 50 ₽")

threading.Thread(target=run_web, daemon=True).start()

print("Бот запущен...")
bot.infinity_polling()
