import os
import threading
import sqlite3
import time
import telebot
from flask import Flask, render_template, request, jsonify
from telebot.types import LabeledPrice, PreCheckoutQuery

TOKEN = os.environ.get("BOT_TOKEN")
DB_FILE = "cat_baron.db"

# ⚠️ ОБЯЗАТЕЛЬНО: Замените этот ID на ваш личный Telegram ID (узнать можно в боте @userinfobot)
ADMIN_ID = 5823816719 

# --- БАЗА ДАННЫХ ---
def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    # Основная таблица пользователей
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
    
    # НОВОЕ: Таблица промокодов
    cursor.execute('''CREATE TABLE IF NOT EXISTS promocodes (
        code TEXT PRIMARY KEY,
        reward_type TEXT,        -- 'coins', 'energy', 'tap_power', 'cat'
        reward_value REAL,       
        max_uses INTEGER DEFAULT 0,   
        used_count INTEGER DEFAULT 0,
        expires_at INTEGER DEFAULT 0  
    )''')
    
    # НОВОЕ: Кто уже активировал
    cursor.execute('''CREATE TABLE IF NOT EXISTS promocode_uses (
        user_id INTEGER,
        code TEXT,
        used_at INTEGER,
        PRIMARY KEY (user_id, code)
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

# --- ЛОГИКА ПРОМОКОДОВ ---
def activate_promo(user_id, code_input):
    code = code_input.strip().upper()
    now = int(time.time())
    
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # 1. Ищем код
    cursor.execute("SELECT reward_type, reward_value, max_uses, used_count, expires_at FROM promocodes WHERE code = ?", (code,))
    promo = cursor.fetchone()
    
    if not promo:
        conn.close()
        return False, "❌ Такого промокода не существует."
    
    reward_type, reward_value, max_uses, used_count, expires_at = promo
    
    # 2. Проверяем срок
    if expires_at != 0 and now > expires_at:
        conn.close()
        return False, "⏰ Срок действия промокода истек."
        
    # 3. Проверяем лимит
    if max_uses != 0 and used_count >= max_uses:
        conn.close()
        return False, "🚫 Лимит активаций исчерпан."
        
    # 4. Проверяем, не активировал ли уже этот юзер
    cursor.execute("SELECT 1 FROM promocode_uses WHERE user_id = ? AND code = ?", (user_id, code))
    if cursor.fetchone():
        conn.close()
        return False, "⚠️ Вы уже активировали этот промокод."
        
    # 5. Выдаем награду
    msg = ""
    if reward_type == "coins":
        cursor.execute("UPDATE users SET coins = coins + ? WHERE user_id = ?", (reward_value, user_id))
        msg = f"💰 Начислено {int(reward_value)} монет!"
        
    elif reward_type == "energy":
        cursor.execute("UPDATE users SET energy = max_energy WHERE user_id = ?", (user_id,))
        msg = f"⚡ Энергия полностью восстановлена!"
        
    elif reward_type == "tap_power":
        cursor.execute("UPDATE users SET tap_power = tap_power + ? WHERE user_id = ?", (reward_value, user_id))
        msg = f"👆 Сила тапа увеличена на {int(reward_value)}!"
        
    elif reward_type == "cat":
        cursor.execute("UPDATE users SET cat_count = cat_count + ? WHERE user_id = ?", (reward_value, user_id))
        msg = f"🐱 В коллекцию добавлено котов: {int(reward_value)}!"
        
    # 6. Записываем использование
    cursor.execute("INSERT INTO promocode_uses (user_id, code, used_at) VALUES (?, ?, ?)", (user_id, code, now))
    cursor.execute("UPDATE promocodes SET used_count = used_count + 1 WHERE code = ?", (code,))
    
    conn.commit()
    conn.close()
    
    return True, f"✅ Промокод активирован!\n{msg}"


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

# НОВОЕ: API для активации промокода из Mini App
@app.route('/api/promo', methods=['POST'])
def api_promo():
    data = request.json
    user_id = data.get('user_id')
    code = data.get('code', '')
    
    if not user_id or not code:
        return jsonify({"success": False, "message": "Ошибка данных"}), 400
        
    success, message = activate_promo(user_id, code)
    return jsonify({"success": success, "message": message})

def run_web():
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))

# --- БОТ ---
bot = telebot.TeleBot(TOKEN)

@bot.message_handler(commands=['start'])
def start(message):
    get_user(message.from_user.id)
    bot.send_message(message.chat.id, "🐱 Добро пожаловать в Кот-Барон!\nЖми кнопку 'Играть' внизу, чтобы начать зарабатывать миллионы.\n\nДоступна команда /promo для ввода кодов!")

@bot.message_handler(commands=['promo'])
def cmd_promo(message):
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        bot.reply_to(message, "ℹ️ Использование: /promo КОД\nПример: /promo KOTIK2024")
        return
        
    code = args[1]
    success, text = activate_promo(message.from_user.id, code)
    bot.reply_to(message, text)

# НОВОЕ: Секретная команда для создания промокодов (только для вас)
@bot.message_handler(commands=['addpromo'])
def cmd_addpromo(message):
    if message.from_user.id != ADMIN_ID:
        return # Игнорируем всех, кроме админа
        
    # Формат: /addpromo КОД ТИП ЗНАЧЕНИЕ ЛИМИТ
    # Пример: /addpromo SUPER2024 coins 10000 100
    args = message.text.split()
    if len(args) < 5:
        bot.reply_to(message, "Формат: /addpromo КОД ТИП ЗНАЧЕНИЕ ЛИМИТ\nТипы: coins, energy, tap_power, cat")
        return
        
    code = args[1].upper()
    r_type = args[2]
    r_value = float(args[3])
    max_uses = int(args[4])
    
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO promocodes (code, reward_type, reward_value, max_uses) 
            VALUES (?, ?, ?, ?)
        """, (code, r_type, r_value, max_uses))
        conn.commit()
        bot.reply_to(message, f"✅ Промокод `{code}` успешно создан!", parse_mode='Markdown')
    except sqlite3.IntegrityError:
        bot.reply_to(message, f"❌ Промокод `{code}` уже существует.", parse_mode='Markdown')
    finally:
        conn.close()

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
