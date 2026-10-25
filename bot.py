import os
import threading
import sqlite3
import random
import time
import telebot
from flask import Flask, render_template, request, jsonify
from telebot.types import LabeledPrice, PreCheckoutQuery

TOKEN = os.environ.get("BOT_TOKEN")
DB_FILE = "game.db"

# --- БАЗА ДАННЫХ ---
def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    # Таблица пользователей
    cursor.execute('CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, balance INTEGER DEFAULT 0, last_claim INTEGER DEFAULT 0, base_income INTEGER DEFAULT 10)')
    # Новая таблица для инвентаря
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            item_name TEXT,
            rarity TEXT
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

def add_item_to_inventory(user_id, item_name, rarity):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO inventory (user_id, item_name, rarity) VALUES (?, ?, ?)", (user_id, item_name, rarity))
    conn.commit()
    conn.close()

def get_inventory(user_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT item_name, rarity FROM inventory WHERE user_id = ?", (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return [{"name": row[0], "rarity": row[1]} for row in rows]

# --- ВЕБ-СЕРВЕР ---
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
        
    init_db() # Проверяем, что таблицы существуют
    
    # Эта функция сама создаст юзера, если его нет
    balance, last_claim, base_income = get_user(user_id) 
    
    return jsonify({"balance": balance, "income": base_income})

@app.route('/api/claim', methods=['POST'])
def api_claim():
    data = request.json
    user_id = data.get('user_id')
    balance, last_claim, base_income = get_user(user_id)
    now = int(time.time())
    seconds_passed = now - last_claim
    hours_passed = min(seconds_passed / 3600.0, 4.0)
    earned = int(base_income * hours_passed)
    if earned < 1: return jsonify({"balance": balance, "earned": 0, "message": "Слишком рано!"})
    new_balance = balance + earned
    update_balance_and_time(user_id, new_balance, now)
    return jsonify({"balance": new_balance, "earned": earned, "message": "Успех!"})

@app.route('/api/case', methods=['POST'])
def api_case():
    data = request.json
    user_id = data.get('user_id')
    balance, last_claim, base_income = get_user(user_id)
    if balance < 50: return jsonify({"success": False, "message": "Недостаточно средств!"})
    
    new_balance = balance - 50
    update_balance_and_time(user_id, new_balance, last_claim)
    
    items = [
        {"name": "Скрипт 'Червь'", "rarity": "Обычный"},
        {"name": "Троян-невидимка", "rarity": "Обычный"},
        {"name": "Бот-парсер", "rarity": "Редкий"},
        {"name": "Нейросеть 'Оракул'", "rarity": "Эпический"},
        {"name": "Абсолютный Бэкдор", "rarity": "Легендарный"}
    ]
    dropped_item = random.choice(items)
    
    # СОХРАНЯЕМ ПРЕДМЕТ В БАЗУ
    add_item_to_inventory(user_id, dropped_item["name"], dropped_item["rarity"])
    
    return jsonify({"success": True, "item": dropped_item, "balance": new_balance})

@app.route('/api/get_inventory', methods=['POST'])
def api_get_inventory():
    data = request.json
    user_id = data.get('user_id')
    inv = get_inventory(user_id)
    return jsonify({"inventory": inv})

@app.route('/api/buy_premium_case', methods=['POST'])
def api_buy_premium_case():
    data = request.json
    user_id = data.get('user_id')
    try:
        bot.send_invoice(user_id, "Премиум Взлом", "Гарантированный предмет", "premium_payload", "", "XTR", [LabeledPrice(label="Премиум", amount=15)])
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "message": "Ошибка"})

def run_web():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

# --- БОТ ---
bot = telebot.TeleBot(TOKEN)

@bot.message_handler(commands=['start'])
def start(message):
    init_db()
    get_user(message.from_user.id)
    bot.send_message(message.chat.id, "🟢 Терминал подключен! Нажми на кнопку 'Играть' внизу.")

@bot.pre_checkout_query_handler(func=lambda query: True)
def checkout(pre_checkout_query: PreCheckoutQuery):
    bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)

@bot.message_handler(content_types=['successful_payment'])
def got_payment(message):
    user_id = message.from_user.id
    balance, last_claim, base_income = get_user(user_id)
    new_balance = balance + 5000
    update_balance_and_time(user_id, new_balance, last_claim)
    # Выдаем легендарку за донат
    add_item_to_inventory(user_id, "Абсолютный Бэкдор", "Легендарный")
    bot.send_message(user_id, f"💎 Оплата прошла! Вы получили 5000 ₽ и Легендарный предмет в инвентарь!")

threading.Thread(target=run_web, daemon=True).start()
print("Бот запущен...")
bot.infinity_polling()
