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
    cursor.execute('CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, balance INTEGER DEFAULT 0, last_claim INTEGER DEFAULT 0, base_income INTEGER DEFAULT 10)')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            item_name TEXT,
            item_type TEXT,
            rarity TEXT,
            income INTEGER DEFAULT 0
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

def update_user(user_id, balance=None, last_claim=None, base_income=None):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    if balance is not None:
        cursor.execute("UPDATE users SET balance = ? WHERE user_id = ?", (balance, user_id))
    if last_claim is not None:
        cursor.execute("UPDATE users SET last_claim = ? WHERE user_id = ?", (last_claim, user_id))
    if base_income is not None:
        cursor.execute("UPDATE users SET base_income = ? WHERE user_id = ?", (base_income, user_id))
    conn.commit()
    conn.close()

def add_item_to_inventory(user_id, item_name, item_type, rarity, income):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO inventory (user_id, item_name, item_type, rarity, income) VALUES (?, ?, ?, ?, ?)", (user_id, item_name, item_type, rarity, income))
    conn.commit()
    conn.close()

def get_total_inventory_income(user_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT SUM(income) FROM inventory WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row[0] else 0

def get_inventory(user_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT item_name, item_type, rarity, income FROM inventory WHERE user_id = ?", (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return [{"name": row[0], "type": row[1], "rarity": row[2], "income": row[3]} for row in rows]

# --- ВЕБ-СЕРВЕР ---
app = Flask(__name__)

@app.route('/')
def health():
    return render_template('index.html')

@app.route('/api/get_data', methods=['POST'])
def api_get_data():
    data = request.json
    user_id = data.get('user_id')
    if not user_id: return jsonify({"error": "No user_id"}), 400
    init_db()
    balance, last_claim, base_income = get_user(user_id)
    inv_income = get_total_inventory_income(user_id)
    total_income = base_income + inv_income
    upgrade_cost = base_income * 10
    return jsonify({"balance": balance, "income": total_income, "base_income": base_income, "upgrade_cost": upgrade_cost})

@app.route('/api/upgrade', methods=['POST'])
def api_upgrade():
    data = request.json
    user_id = data.get('user_id')
    balance, last_claim, base_income = get_user(user_id)
    upgrade_cost = base_income * 10
    if balance < upgrade_cost:
        return jsonify({"success": False, "message": f"Недостаточно средств! Нужно {upgrade_cost} ₽."})
    new_balance = balance - upgrade_cost
    new_base_income = base_income + 5
    update_user(user_id, balance=new_balance, base_income=new_base_income)
    inv_income = get_total_inventory_income(user_id)
    total_income = new_base_income + inv_income
    return jsonify({"success": True, "balance": new_balance, "total_income": total_income, "new_base_income": new_base_income, "next_upgrade_cost": new_base_income * 10})

@app.route('/api/claim', methods=['POST'])
def api_claim():
    data = request.json
    user_id = data.get('user_id')
    balance, last_claim, base_income = get_user(user_id)
    inv_income = get_total_inventory_income(user_id)
    total_income = base_income + inv_income
    now = int(time.time())
    seconds_passed = now - last_claim
    hours_passed = min(seconds_passed / 3600.0, 4.0)
    earned = int(total_income * hours_passed)
    if earned < 1: 
        return jsonify({"balance": balance, "earned": 0, "message": "Слишком рано!", "total_income": total_income})
    new_balance = balance + earned
    update_user(user_id, balance=new_balance, last_claim=now)
    return jsonify({"balance": new_balance, "earned": earned, "message": "Успех!", "total_income": total_income})

@app.route('/api/case', methods=['POST'])
def api_case():
    data = request.json
    user_id = data.get('user_id')
    balance, last_claim, base_income = get_user(user_id)
    if balance < 50: 
        return jsonify({"success": False, "message": "Недостаточно средств!"})
    new_balance = balance - 50
    update_user(user_id, balance=new_balance)
    
    # Новые комплектующие для сервера
    items = [
        {"name": "Кулер 120мм", "type": "Охлаждение", "rarity": "Обычный", "income": 5},
        {"name": "Вентилятор RGB", "type": "Охлаждение", "rarity": "Обычный", "income": 10},
        {"name": "Блок питания 500W", "type": "Питание", "rarity": "Редкий", "income": 25},
        {"name": "Материнская плата B450", "type": "Плата", "rarity": "Редкий", "income": 35},
        {"name": "Процессор Intel i5", "type": "Процессор", "rarity": "Эпический", "income": 100},
        {"name": "Видеокарта RTX 3060", "type": "Видеокарта", "rarity": "Эпический", "income": 150},
        {"name": "Процессор Intel i9 Extreme", "type": "Процессор", "rarity": "Легендарный", "income": 500},
        {"name": "Видеокарта RTX 4090", "type": "Видеокарта", "rarity": "Легендарный", "income": 800}
    ]
    dropped_item = random.choice(items)
    add_item_to_inventory(user_id, dropped_item["name"], dropped_item["type"], dropped_item["rarity"], dropped_item["income"])
    
    inv_income = get_total_inventory_income(user_id)
    total_income = base_income + inv_income
    return jsonify({"success": True, "item": dropped_item, "balance": new_balance, "total_income": total_income})

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
    update_user(user_id, balance=new_balance)
    # За донат даем топовую видеокарту
    add_item_to_inventory(user_id, "Видеокарта RTX 4090", "Видеокарта", "Легендарный", 800)
    bot.send_message(user_id, f"💎 Оплата прошла! Вы получили 5000 ₽ и Легендарную видеокарту!")

threading.Thread(target=run_web, daemon=True).start()
print("Бот запущен...")
bot.infinity_polling()
