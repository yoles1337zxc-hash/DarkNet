import os
import threading
import sqlite3
import random
import time
import telebot
from flask import Flask, render_template, request, jsonify

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


# --- ВЕБ-СЕРВЕР (API ДЛЯ MINI APP) ---
app = Flask(__name__)

@app.route('/')
def health():
    return render_template('index.html')

@app.route('/api/get_data', methods=['POST'])
def api_get_data():
    data = request.json
    user_id = data.get('user_id')
    
    if not user_id:
        return jsonify({"error": "No user_id"}), 400
        
    balance, last_claim, base_income = get_user(user_id)
    return jsonify({"balance": balance, "income": base_income})

@app.route('/api/claim', methods=['POST'])
def api_claim():
    data = request.json
    user_id = data.get('user_id')
    
    balance, last_claim, base_income = get_user(user_id)
    now = int(time.time())
    
    # Считаем прошедшее время (макс 4 часа)
    seconds_passed = now - last_claim
    hours_passed = min(seconds_passed / 3600.0, 4.0)
    
    earned = int(base_income * hours_passed)
    
    if earned < 1:
        return jsonify({"balance": balance, "earned": 0, "message": "Слишком рано!"})
        
    new_balance = balance + earned
    update_balance_and_time(user_id, new_balance, now)
    
    return jsonify({"balance": new_balance, "earned": earned, "message": "Успех!"})

def run_web():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)


# --- БОТ TELEGRAM ---
bot = telebot.TeleBot(TOKEN)

@bot.message_handler(commands=['start'])
def start(message):
    init_db()
    get_user(message.from_user.id)
    bot.send_message(message.chat.id, "🟢 Терминал подключен! Нажми на кнопку 'Играть' внизу.")

threading.Thread(target=run_web, daemon=True).start()

print("Бот запущен...")
bot.infinity_polling()
