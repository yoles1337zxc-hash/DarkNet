import asyncio
import os
import json
import time
import random
import aiosqlite
from aiohttp import web
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo, MenuButtonWebApp
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBAPP_URL = os.getenv("WEBAPP_URL")
PORT = int(os.getenv("PORT", 8080))
DB_PATH = "dropezone.db"

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# --- БАЗА ДАННЫХ ---
async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                balance INTEGER DEFAULT 400000,
                last_collect INTEGER DEFAULT 0,
                daily_day INTEGER DEFAULT 1,
                last_daily INTEGER DEFAULT 0
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS inventory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                item_type TEXT,
                item_name TEXT,
                rarity TEXT,
                income INTEGER DEFAULT 0,
                price INTEGER DEFAULT 0,
                in_garage INTEGER DEFAULT 0
            )
        """)
        await db.execute("INSERT OR IGNORE INTO users (user_id, balance) VALUES (1, 1000000)")
        await db.commit()

# --- ДАННЫЕ ИГРЫ ---
BIKES = [
    {"name": "Минск", "rarity": "D", "price": 50000, "chance": 17.4, "img": "🛵"},
    {"name": "Восход", "rarity": "D", "price": 60000, "chance": 15.1, "img": "🛵"},
    {"name": "ИЖ Планета", "rarity": "D", "price": 70000, "chance": 14.2, "img": "🏍️"},
    {"name": "Ява 350", "rarity": "D", "price": 90000, "chance": 12.2, "img": "🏍️"},
    {"name": "Урал", "rarity": "D", "price": 110000, "chance": 8.5, "img": "🏍️"},
    {"name": "Днепр", "rarity": "D", "price": 120000, "chance": 7.85, "img": "🏍️"},
    {"name": "Honda CB400", "rarity": "C", "price": 350000, "chance": 5.8, "img": "🏍️"},
    {"name": "Yamaha YBR", "rarity": "C", "price": 400000, "chance": 4.2, "img": "🏍️"},
    {"name": "Kawasaki Ninja 300", "rarity": "C", "price": 550000, "chance": 3.2, "img": "🏍️"},
    {"name": "Suzuki GSX-R600", "rarity": "C", "price": 800000, "chance": 2.2, "img": "🏍️"},
    {"name": "Ducati Monster", "rarity": "C", "price": 1000000, "chance": 1.7, "img": "🏍️"},
    {"name": "Yamaha R1", "rarity": "B", "price": 1800000, "chance": 0.9, "img": "🏍️"},
    {"name": "BMW S1000RR", "rarity": "B", "price": 2200000, "chance": 0.6, "img": "🏍️"},
    {"name": "Kawasaki H2", "rarity": "B", "price": 3000000, "chance": 0.3, "img": "🏍️"},
    {"name": "Dodge Tomahawk", "rarity": "A", "price": 8000000, "chance": 0.1, "img": "🏍️"},
    {"name": "MTT Turbine Y2K", "rarity": "A", "price": 10000000, "chance": 0.05, "img": "🏍️"},
]

PARTS = [
    {"name": "Двигатель", "rarity": "D", "chance": 30.0, "price": 5000, "img": "⚙️"},
    {"name": "Турбина", "rarity": "D", "chance": 25.0, "price": 5000, "img": "🌀"},
    {"name": "КПП", "rarity": "C", "chance": 15.0, "price": 15000, "img": "⚙️"},
    {"name": "Выхлоп", "rarity": "C", "chance": 10.0, "price": 15000, "img": "🔧"},
    {"name": "Подвеска", "rarity": "B", "chance": 7.5, "price": 40000, "img": "🔩"},
    {"name": "Диски и шины", "rarity": "B", "chance": 5.0, "price": 40000, "img": "🛞"},
    {"name": "Тормоза", "rarity": "A", "chance": 3.0, "price": 120000, "img": "🛑"},
    {"name": "Обвес", "rarity": "A", "chance": 2.0, "price": 120000, "img": "🛡️"},
    {"name": "Электромотор", "rarity": "S", "chance": 1.0, "price": 500000, "img": "⚡"},
    {"name": "Батарея", "rarity": "S", "chance": 0.5, "price": 500000, "img": "🔋"},
]

DAILY_REWARDS = [
    {"day": 1, "type": "money", "amount": 30000, "text": "30 000 ₽"},
    {"day": 2, "type": "part_case", "amount": 3, "text": "Кейс деталей ×3"},
    {"day": 3, "type": "money", "amount": 80000, "text": "80 000 ₽"},
    {"day": 4, "type": "part_case", "amount": 2, "text": "Кейс деталей ×2"},
    {"day": 5, "type": "bike_case", "amount": 1, "text": "Кейс мотоцикла"},
    {"day": 6, "type": "money", "amount": 200000, "text": "200 000 ₽"},
    {"day": 7, "type": "bike_case", "amount": 1, "text": "Кейс Спортбайк"},
    {"day": 8, "type": "money", "amount": 400000, "text": "400 000 ₽"},
    {"day": 9, "type": "part_case", "amount": 2, "text": "Кейс деталей ×2"},
    {"day": 10, "type": "bike_case", "amount": 1, "text": "Кейс мотоцикла"},
    {"day": 11, "type": "money", "amount": 700000, "text": "700 000 ₽"},
    {"day": 12, "type": "part_case", "amount": 1, "text": "Кейс деталей"},
    {"day": 13, "type": "money", "amount": 1500000, "text": "1.5 млн ₽"},
    {"day": 14, "type": "bike_case", "amount": 1, "text": "Кейс Элита"},
]

def get_random_item(items):
    total_chance = sum(item["chance"] for item in items)
    rand = random.uniform(0, total_chance)
    current = 0
    for item in items:
        current += item["chance"]
        if rand <= current:
            return item
    return items[0]

def get_case_cost(case_type):
    if case_type == 'bike': return 14000
    if case_type == 'part': return 14000
    if case_type == 'plate': return 32000
    return 14000

# --- API ---
async def get_user(request):
    user_id = int(request.match_info.get('user_id', 1))
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT balance, last_collect, daily_day, last_daily FROM users WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            if not row:
                return web.json_response({"error": "User not found"}, status=404)
            
            balance, last_collect, daily_day, last_daily = row
            now = int(time.time())
            
            earned = 0
            time_passed = now - last_collect
            if time_passed > 0:
                async with db.execute("SELECT COUNT(*) FROM inventory WHERE user_id = ? AND item_type = 'bike' AND in_garage = 1", (user_id,)) as c:
                    bikes_count = (await c.fetchone())[0]
                income_per_hour = bikes_count * 1000
                effective_time = min(time_passed, 14400)
                earned = int((effective_time / 3600) * income_per_hour)
                if earned > 0:
                    await db.execute("UPDATE users SET balance = balance + ?, last_collect = ? WHERE user_id = ?", (earned, now, user_id))
                    await db.commit()

        async with db.execute("SELECT id, item_type, item_name, rarity, income, in_garage FROM inventory WHERE user_id = ?", (user_id,)) as cursor:
            inv_rows = await cursor.fetchall()
            inventory = [{"id": r[0], "type": r[1], "name": r[2], "rarity": r[3], "income": r[4], "in_garage": r[5]} for r in inv_rows]

    return web.json_response({
        "balance": balance + earned,
        "inventory": inventory,
        "daily_day": daily_day,
        "last_daily": last_daily,
        "next_reward_time": last_daily + 86400 if last_daily > 0 else 0
    })

async def open_case(request):
    user_id = int(request.match_info.get('user_id', 1))
    data = await request.json()
    case_type = data.get("case_type")
    quantity = data.get("quantity", 1)

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,)) as cursor:
            balance = (await cursor.fetchone())[0]

        cost_per_one = get_case_cost(case_type)
        total_cost = cost_per_one * quantity

        if balance < total_cost:
            return web.json_response({"error": "Недостаточно средств"}, status=400)

        async with db.execute("SELECT COUNT(*) FROM inventory WHERE user_id = ? AND item_type = 'bike'", (user_id,)) as c:
            total_bikes = (await c.fetchone())[0]
        if total_bikes + quantity > 26:
            return web.json_response({"error": "Недостаточно места на складе (макс 26 байков)"}, status=400)

        await db.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (total_cost, user_id))

        items_won = []
        for _ in range(quantity):
            if case_type == 'bike':
                item = get_random_item(BIKES)
                income = item["price"] // 10
                await db.execute("INSERT INTO inventory (user_id, item_type, item_name, rarity, income, price) VALUES (?, 'bike', ?, ?, ?, ?)",
                                 (user_id, item["name"], item["rarity"], income, item["price"]))
            elif case_type == 'part':
                item = get_random_item(PARTS)
                await db.execute("INSERT INTO inventory (user_id, item_type, item_name, rarity, income, price) VALUES (?, 'part', ?, ?, 0, ?)",
                                 (user_id, item["name"], item["rarity"], item["price"]))
            elif case_type == 'plate':
                item = {"name": "Номер 777", "rarity": "C", "img": "🪪"}
                await db.execute("INSERT INTO inventory (user_id, item_type, item_name, rarity, income, price) VALUES (?, 'plate', ?, ?, 0, 16000)",
                                 (user_id, item["name"], item["rarity"]))
            else:
                return web.json_response({"error": "Неверный тип кейса"}, status=400)
            items_won.append(item)

        await db.commit()
    return web.json_response({"items": items_won, "message": "Успех!"})

async def craft(request):
    user_id = int(request.match_info.get('user_id', 1))
    data = await request.json()
    rarity = data.get("rarity")
    
    rarities = ["D", "C", "B", "A", "S"]
    if rarity not in rarities or rarity == "S":
        return web.json_response({"error": "Нельзя скрафтить"}, status=400)

    next_rarity = rarities[rarities.index(rarity) + 1]

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT id FROM inventory WHERE user_id = ? AND item_type = 'part' AND rarity = ? AND in_garage = 0 LIMIT 3", (user_id, rarity)) as c:
            items = await c.fetchall()
            if len(items) < 3:
                return web.json_response({"error": "Нужно 3 запчасти на складе"}, status=400)
            
            ids_to_del = [str(item[0]) for item in items]
            await db.execute(f"DELETE FROM inventory WHERE id IN ({','.join(ids_to_del)})")
            
            valid_parts = [p for p in PARTS if p["rarity"] == next_rarity]
            new_item = random.choice(valid_parts) if valid_parts else {"name": "Деталь", "rarity": next_rarity, "price": 1000}

            await db.execute("INSERT INTO inventory (user_id, item_type, item_name, rarity, income, price) VALUES (?, 'part', ?, ?, 0, ?)",
                             (user_id, new_item["name"], next_rarity, new_item["price"]))
            await db.commit()
    return web.json_response({"message": f"Успешно! Получен {new_item['name']} ранга {next_rarity}"})

async def equip_item(request):
    user_id = int(request.match_info.get('user_id', 1))
    data = await request.json()
    item_id = data.get("item_id")
    
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM inventory WHERE user_id = ? AND item_type = 'bike' AND in_garage = 1", (user_id,)) as c:
            count = (await c.fetchone())[0]
            
        if count >= 6:
            return web.json_response({"error": "Гараж заполнен (макс 6)"}, status=400)
            
        await db.execute("UPDATE inventory SET in_garage = 1 WHERE id = ? AND user_id = ? AND item_type = 'bike'", (item_id, user_id))
        await db.commit()
    return web.json_response({"message": "Мотоцикл в гараже!"})

async def sell_item(request):
    user_id = int(request.match_info.get('user_id', 1))
    data = await request.json()
    item_id = data.get("item_id")
    
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT price FROM inventory WHERE id = ? AND user_id = ?", (item_id, user_id)) as c:
            row = await c.fetchone()
            if not row:
                return web.json_response({"error": "Предмет не найден"}, status=404)
            price = row[0] // 2 
            
            await db.execute("DELETE FROM inventory WHERE id = ?", (item_id,))
            await db.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (price, user_id))
            await db.commit()
    return web.json_response({"message": f"Продано за {price} ₽"})

async def claim_daily(request):
    user_id = int(request.match_info.get('user_id', 1))
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT daily_day, last_daily, balance FROM users WHERE user_id = ?", (user_id,)) as c:
            daily_day, last_daily, balance = await c.fetchone()
            
        now = int(time.time())
        if now - last_daily < 86400:
            return web.json_response({"error": "Бонус еще не доступен"}, status=400)
            
        reward = DAILY_REWARDS[daily_day - 1]
        message = ""
        
        if reward["type"] == "money":
            await db.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (reward["amount"], user_id))
            message = f"Получено: {reward['text']}"
        elif reward["type"] == "part_case":
            for _ in range(reward["amount"]):
                item = get_random_item(PARTS)
                await db.execute("INSERT INTO inventory (user_id, item_type, item_name, rarity, income, price) VALUES (?, 'part', ?, ?, 0, ?)",
                                 (user_id, item["name"], item["rarity"], item["price"]))
            message = f"Получено: {reward['text']}"
        elif reward["type"] == "bike_case":
            for _ in range(reward["amount"]):
                item = get_random_item(BIKES)
                income = item["price"] // 10
                await db.execute("INSERT INTO inventory (user_id, item_type, item_name, rarity, income, price) VALUES (?, 'bike', ?, ?, ?, ?)",
                                 (user_id, item["name"], item["rarity"], income, item["price"]))
            message = f"Получено: {reward['text']}"
        
        next_day = daily_day + 1 if daily_day < 14 else 1
        await db.execute("UPDATE users SET daily_day = ?, last_daily = ? WHERE user_id = ?", (next_day, now, user_id))
        await db.commit()
    return web.json_response({"message": message})

async def handle_index(request):
    path = os.path.join(os.path.dirname(__file__), "index.html")
    return web.FileResponse(path)

def create_web_app():
    app = web.Application()
    app.router.add_get("/", handle_index)
    app.router.add_get("/index.html", handle_index)
    app.router.add_get("/api/user/{user_id}", get_user)
    app.router.add_post("/api/user/{user_id}/case", open_case)
    app.router.add_post("/api/user/{user_id}/craft", craft)
    app.router.add_post("/api/user/{user_id}/equip", equip_item)
    app.router.add_post("/api/user/{user_id}/sell", sell_item)
    app.router.add_post("/api/user/{user_id}/daily", claim_daily)
    return app

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎮 Открыть игру", web_app=WebAppInfo(url=f"{WEBAPP_URL}"))]
    ])
    await message.answer("Привет! Открывай игру и собирай мотоциклы 👇", reply_markup=kb)

async def main():
    await init_db()
    await bot.set_chat_menu_button(menu_button=MenuButtonWebApp(text="🎮 Играть", web_app=WebAppInfo(url=f"{WEBAPP_URL}")))
    
    app = create_web_app()
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
