import os
import threading
import sqlite3
import time
import telebot
from flask import Flask, render_template, request, jsonify
from telebot.types import LabeledPrice, PreCheckoutQuery

TOKEN = os.environ.get("BOT_TOKEN")
DB_FILE = "cat_baron.db"

# --- БАЗА ДАННЫХ ---
def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY, 
        coins INTEGER DEFAULT 0, 
        energy INTEGER DEFAULT 1000,
        max_energy INTEGER DEFAULT 1000,
        tap_power INTEGER DEFAULT 1,
        tap_level INTEGER DEFAULT 1,
        tap_cost INTEGER DEFAULT 500,
        cat_count INTEGER DEFAULT 0,
        cat_cost INTEGER DEFAULT 2000,
        last_energy_update INTEGER DEFAULT 0
    )''')
    conn.commit()
    conn.close()

def get_user(user_id):
    init_db()
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT coins, energy, max_energy, tap_power, tap_level, tap_cost, cat_count, cat_cost, last_energy_update FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    
    if not row:
        now = int(time.time())
        cursor.execute("INSERT INTO users (user_id, last_energy_update) VALUES (?, ?)", (user_id, now))
        conn.commit()
        conn.close()
        return [0, 1000, 1000, 1, 1, 500, 0, 2000, now]
    
    now = int(time.time())
    last_update = row[8]
    seconds_passed = now - last_update
    energy_regen = seconds_passed // 60
    new_energy = min(row[1] + energy_regen, row[2])
    
    if new_energy != row[1]:
        cursor.execute("UPDATE users SET energy = ?, last_energy_update = ? WHERE user_id = ?", (new_energy, now, user_id))
        conn.commit()
        row = list(row)
        row[1] = new_energy
        row[8] = now
    
    conn.close()
    return row

def update_user(user_id, **kwargs):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    for key, value in kwargs.items():
        cursor.execute(f"UPDATE users SET {key} = ? WHERE user_id = ?", (value, user_id))
    conn.commit()
    conn.close()

# --- ВЕБ-СЕРВЕР ---
app = Flask(__name__)

@app.route('/')
def health():
    return render_template('index.html')

@app.route('/api/get_state', methods=['POST'])
def api_get_state():
    data = request.json
    user_id = data.get('user_id')
    if not user_id: return jsonify({"error": "No user_id"}), 400
    
    coins, energy, max_energy, tap_power, tap_level, tap_cost, cat_count, cat_cost, _ = get_user(user_id)
    
    return jsonify({
        "coins": coins, "energy": energy, "max_energy": max_energy,
        "tap_power": tap_power, "tap_level": tap_level, "tap_cost": tap_cost,
        "cat_count": cat_count, "cat_cost": cat_cost
    })

@app.route('/api/tap', methods=['POST'])
def api_tap():
    user_id = request.json.get('user_id')
    coins, energy, _, tap_power, _, _, _, _, _ = get_user(user_id)
    
    if energy >= 1:
        update_user(user_id, coins=coins + tap_power, energy=energy - 1)
        return jsonify({"success": True})
    return jsonify({"success": False})

@app.route('/api/upgrade_tap', methods=['POST'])
def api_upgrade_tap():
    user_id = request.json.get('user_id')
    coins, _, _, tap_power, tap_level, tap_cost, _, _, _ = get_user(user_id)
    
    if coins >= tap_cost:
        update_user(user_id, coins=coins - tap_cost, tap_power=tap_power + 1, tap_level=tap_level + 1, tap_cost=int(tap_cost * 2.5))
        return jsonify({"success": True})
    return jsonify({"success": False, "message": "Не хватает монет!"})

@app.route('/api/buy_cat', methods=['POST'])
def api_buy_cat():
    user_id = request.json.get('user_id')
    coins, _, _, _, _, _, cat_count, cat_cost, _ = get_user(user_id)
    
    if coins >= cat_cost:
        update_user(user_id, coins=coins - cat_cost, cat_count=cat_count + 1, cat_cost=int(cat_cost * 1.8))
        return jsonify({"success": True})
    return jsonify({"success": False, "message": "Не хватает монет!"})

@app.route('/api/buy_energy', methods=['POST'])
def api_buy_energy():
    user_id = request.json.get('user_id')
    try:
        bot.send_invoice(user_id, "Восстановление энергии", "Мгновенно восстанавливает 1000 энергии для тапов.", "energy_payload", "", "XTR", [LabeledPrice(label="Энергия", amount=5)])
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False})

def run_web():
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))

# --- БОТ ---
bot = telebot.TeleBot(TOKEN)

@bot.message_handler(commands=['start'])
def start(message):
    get_user(message.from_user.id)
    bot.send_message(message.chat.id, "🐱 Добро пожаловать в Кот-Барон!\nЖми кнопку 'Играть' внизу, чтобы начать зарабатывать миллионы.")

@bot.pre_checkout_query_handler(func=lambda query: True)
def checkout(pre_checkout_query: PreCheckoutQuery):
    bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)

@bot.message_handler(content_types=['successful_payment'])
def got_payment(message):
    user_id = message.from_user.id
    user_data = get_user(user_id)
    update_user(user_id, energy=user_data[2]) 
    bot.send_message(user_id, "⚡ Энергия успешно восстановлена! Возвращайся в игру.")

threading.Thread(target=run_web, daemon=True).start()
print("Бот запущен...")
bot.infinity_polling()
