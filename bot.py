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
    cursor.execute('CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, balance INTEGER DEFAULT 0, last_claim INTEGER DEFAULT 0, base_income INTEGER DEFAULT 10, last_daily INTEGER DEFAULT 0, daily_streak INTEGER DEFAULT 0)')
    
    # Добавляем колонки, если их нет (для старых баз)
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN last_daily INTEGER DEFAULT 0")
        cursor.execute("ALTER TABLE users ADD COLUMN daily_streak INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass # Колонки уже существуют
        
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
    cursor.execute("SELECT item_type, income FROM inventory WHERE user_id = ?", (user_id,))
    rows = cursor.fetchall()
    conn.close()
    if not rows: return 0
    base_inv_income = sum([r[1] for r in rows])
    type_counts = {}
    for r in rows:
        type_counts[r[0]] = type_counts.get(r[0], 0) + 1
    bonus_income = 0
    for t, count in type_counts.items():
        if count >= 3:
            type_income = sum([r[1] for r in rows if r[0] == t])
            bonus_income += type_income * 0.2
    return int(base_inv_income + bonus_income)

def get_inventory(user_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT id, item_name, item_type, rarity, income FROM inventory WHERE user_id = ?", (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return [{"id": row[0], "name": row[1], "type": row[2], "rarity": row[3], "income": row[4]} for row in rows]

# Умная мастерская: ищем, что можно скрафтить
def get_craftable_items(user_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT item_type, rarity, COUNT(*) FROM inventory WHERE user_id = ? GROUP BY item_type, rarity", (user_id,))
    rows = cursor.fetchall()
    conn.close()
    
    craftable = []
    for item_type, rarity, count in rows:
        if count >= 3 and rarity in ["Обычный", "Редкий", "Эпический", "Легендарный"]:
            craftable.append({"type": item_type, "rarity": rarity, "count": count})
    return craftable

def upgrade_rarity(user_id, item_type, current_rarity):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM inventory WHERE user_id = ? AND item_type = ? AND rarity = ? LIMIT 3", (user_id, item_type, current_rarity))
    items = cursor.fetchall()
    
    if len(items) < 3:
        conn.close()
        return False, "Нужно 3 одинаковые детали!"
        
    ids_to_delete = [item[0] for item in items]
    cursor.execute(f"DELETE FROM inventory WHERE id IN ({','.join(['?']*len(ids_to_delete))})", ids_to_delete)
    
    next_rarity = ""
    chance = 0
    new_income = 0
    
    if current_rarity == "Обычный":
        next_rarity, chance, new_income = "Редкий", 60, 25
    elif current_rarity == "Редкий":
        next_rarity, chance, new_income = "Эпический", 40, 100
    elif current_rarity == "Эпический":
        next_rarity, chance, new_income = "Легендарный", 20, 500
    elif current_rarity == "Легендарный":
        next_rarity, chance, new_income = "Мифический", 10, 2000
    else:
        conn.close()
        return False, "Максимальная редкость!"
        
    roll = random.randint(1, 100)
    success = roll <= chance
    
    if success:
        new_name = f"Улучшенный {item_type}"
        cursor.execute("INSERT INTO inventory (user_id, item_name, item_type, rarity, income) VALUES (?, ?, ?, ?, ?)", 
                       (user_id, new_name, item_type, next_rarity, new_income))
        conn.commit()
        conn.close()
        return True, f"УСПЕХ! Вы получили {next_rarity} {item_type}!"
    else:
        conn.commit()
        conn.close()
        return False, "НЕУДАЧА! Детали сгорели."

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
    total_income = base_income + get_total_inventory_income(user_id)
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
    return jsonify({"success": True, "balance": new_balance, "total_income": new_base_income + get_total_inventory_income(user_id), "next_upgrade_cost": new_base_income * 10})

@app.route('/api/claim', methods=['POST'])
def api_claim():
    data = request.json
    user_id = data.get('user_id')
    balance, last_claim, base_income = get_user(user_id)
    total_income = base_income + get_total_inventory_income(user_id)
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
    if balance < 50: return jsonify({"success": False, "message": "Недостаточно средств!"})
    new_balance = balance - 50
    update_user(user_id, balance=new_balance)
    
    # ДОБАВИЛИ КОРПУС И ДРУГИЕ ТИПЫ
    items = [
        {"name": "Корпус Mini-ITX", "type": "Корпус", "rarity": "Обычный", "income": 5},
        {"name": "Кулер 120мм", "type": "Охлаждение", "rarity": "Обычный", "income": 5},
        {"name": "Блок питания 500W", "type": "Питание", "rarity": "Обычный", "income": 10},
        {"name": "Материнская плата B450", "type": "Плата", "rarity": "Обычный", "income": 12},
        {"name": "Процессор i3", "type": "Процессор", "rarity": "Обычный", "income": 15},
        
        {"name": "Корпус ATX RGB", "type": "Корпус", "rarity": "Редкий", "income": 25},
        {"name": "Вентилятор RGB", "type": "Охлаждение", "rarity": "Редкий", "income": 25},
        {"name": "Блок питания 750W", "type": "Питание", "rarity": "Редкий", "income": 30},
        {"name": "Материнская плата X570", "type": "Плата", "rarity": "Редкий", "income": 35},
        {"name": "Видеокарта GTX 1660", "type": "Видеокарта", "rarity": "Редкий", "income": 35},
        
        {"name": "Корпус Server Full-Tower", "type": "Корпус", "rarity": "Эпический", "income": 100},
        {"name": "Водяное охлаждение", "type": "Охлаждение", "rarity": "Эпический", "income": 100},
        {"name": "Процессор i7", "type": "Процессор", "rarity": "Эпический", "income": 100},
        {"name": "Видеокарта RTX 3060", "type": "Видеокарта", "rarity": "Эпический", "income": 150},
        
        {"name": "Процессор i9 Extreme", "type": "Процессор", "rarity": "Легендарный", "income": 500},
        {"name": "Видеокарта RTX 4090", "type": "Видеокарта", "rarity": "Легендарный", "income": 800}
    ]
    dropped_item = random.choice(items)
    add_item_to_inventory(user_id, dropped_item["name"], dropped_item["type"], dropped_item["rarity"], dropped_item["income"])
    return jsonify({"success": True, "item": dropped_item, "balance": new_balance, "total_income": base_income + get_total_inventory_income(user_id)})

@app.route('/api/get_inventory', methods=['POST'])
def api_get_inventory():
    data = request.json
    user_id = data.get('user_id')
    return jsonify({"inventory": get_inventory(user_id)})

@app.route('/api/get_craftable', methods=['POST'])
def api_get_craftable():
    data = request.json
    user_id = data.get('user_id')
    return jsonify({"craftable": get_craftable_items(user_id)})

@app.route('/api/craft', methods=['POST'])
def api_craft():
    data = request.json
    user_id = data.get('user_id')
    item_type = data.get('item_type')
    current_rarity = data.get('rarity')
    success, message = upgrade_rarity(user_id, item_type, current_rarity)
    return jsonify({"success": success, "message": message})

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
    add_item_to_inventory(user_id, "Видеокарта RTX 4090", "Видеокарта", "Легендарный", 800)
    bot.send_message(user_id, f"💎 Оплата прошла! Вы получили 5000 ₽ и Легендарную видеокарту!")

threading.Thread(target=run_web, daemon=True).start()
print("Бот запущен...")
bot.infinity_polling()
