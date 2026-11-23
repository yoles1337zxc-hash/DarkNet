import asyncio
import os
import time
import random
import aiosqlite
from aiohttp import web
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo, MenuButtonWebApp
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBAPP_URL = os.getenv("WEBAPP_URL")
PORT = int(os.getenv("PORT", 8080))
DB_PATH = "darknet.db"

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# --- БАЗА ДАННЫХ ---
async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                balance INTEGER DEFAULT 50000,
                last_collect INTEGER DEFAULT 0,
                daily_day INTEGER DEFAULT 1,
                last_daily INTEGER DEFAULT 0,
                referrer_id INTEGER DEFAULT NULL,
                ref_reward_claimed INTEGER DEFAULT 0,
                starter_cases INTEGER DEFAULT 3,
                fast_open INTEGER DEFAULT 0
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
                in_garage INTEGER DEFAULT 0,
                img_url TEXT DEFAULT ''
            )
        """)
        await db.commit()

# --- ДАННЫЕ ---
GARAGES = {
    "rusty": {"name": "Ржавый гараж", "price": 14000, "img": "https://cdn-icons-png.flaticon.com/512/3097/3097180.png", "rarity": "D"},
    "used": {"name": "Поддержанные", "price": 14000, "img": "https://cdn-icons-png.flaticon.com/512/3097/3097180.png", "rarity": "D"},
    "city": {"name": "Городской", "price": 50000, "img": "https://cdn-icons-png.flaticon.com/512/3097/3097180.png", "rarity": "C"},
    "tuning": {"name": "Тюнинг-ателье", "price": 120000, "img": "https://cdn-icons-png.flaticon.com/512/3097/3097180.png", "rarity": "B"},
    "sport": {"name": "Спорткар", "price": 250000, "img": "https://cdn-icons-png.flaticon.com/512/3097/3097180.png", "rarity": "A"},
    "premium": {"name": "Премиум", "price": 500000, "img": "https://cdn-icons-png.flaticon.com/512/3097/3097180.png", "rarity": "A"},
    "elite": {"name": "Элита", "price": 800000, "img": "https://cdn-icons-png.flaticon.com/512/3097/3097180.png", "rarity": "S"}
}

MOTORCYCLES = {
    "rusty": [
        {"name": "Минск", "price": 50000, "chance": 50, "img": "https://cdn-icons-png.flaticon.com/512/3097/3097180.png"},
        {"name": "Восход", "price": 60000, "chance": 30, "img": "https://cdn-icons-png.flaticon.com/512/3097/3097180.png"},
        {"name": "ИЖ Планета", "price": 70000, "chance": 20, "img": "https://cdn-icons-png.flaticon.com/512/3097/3097180.png"},
    ],
    "used": [
        {"name": "Ява 350", "price": 90000, "chance": 40, "img": "https://cdn-icons-png.flaticon.com/512/3097/3097180.png"},
        {"name": "Урал", "price": 110000, "chance": 35, "img": "https://cdn-icons-png.flaticon.com/512/3097/3097180.png"},
        {"name": "Днепр", "price": 120000, "chance": 25, "img": "https://cdn-icons-png.flaticon.com/512/3097/3097180.png"},
    ],
    "city": [
        {"name": "Honda CB400", "price": 350000, "chance": 40, "img": "https://cdn-icons-png.flaticon.com/512/3097/3097180.png"},
        {"name": "Yamaha YBR", "price": 400000, "chance": 35, "img": "https://cdn-icons-png.flaticon.com/512/3097/3097180.png"},
        {"name": "Kawasaki Ninja 300", "price": 550000, "chance": 25, "img": "https://cdn-icons-png.flaticon.com/512/3097/3097180.png"},
    ],
    "tuning": [
        {"name": "Suzuki GSX-R600", "price": 800000, "chance": 40, "img": "https://cdn-icons-png.flaticon.com/512/3097/3097180.png"},
        {"name": "Ducati Monster", "price": 1000000, "chance": 35, "img": "https://cdn-icons-png.flaticon.com/512/3097/3097180.png"},
        {"name": "Yamaha R1", "price": 1800000, "chance": 25, "img": "https://cdn-icons-png.flaticon.com/512/3097/3097180.png"},
    ],
    "sport": [
        {"name": "BMW S1000RR", "price": 2200000, "chance": 40, "img": "https://cdn-icons-png.flaticon.com/512/3097/3097180.png"},
        {"name": "Kawasaki H2", "price": 3000000, "chance": 35, "img": "https://cdn-icons-png.flaticon.com/512/3097/3097180.png"},
        {"name": "Dodge Tomahawk", "price": 8000000, "chance": 25, "img": "https://cdn-icons-png.flaticon.com/512/3097/3097180.png"},
    ],
    "premium": [
        {"name": "MTT Turbine Y2K", "price": 10000000, "chance": 50, "img": "https://cdn-icons-png.flaticon.com/512/3097/3097180.png"},
        {"name": "Lazareth LM847", "price": 12000000, "chance": 30, "img": "https://cdn-icons-png.flaticon.com/512/3097/3097180.png"},
        {"name": "Dodge Tomahawk S", "price": 15000000, "chance": 20, "img": "https://cdn-icons-png.flaticon.com/512/3097/3097180.png"},
    ],
    "elite": [
        {"name": "Kawasaki Ninja H2R", "price": 20000000, "chance": 50, "img": "https://cdn-icons-png.flaticon.com/512/3097/3097180.png"},
        {"name": "Ducati Superleggera", "price": 25000000, "chance": 30, "img": "https://cdn-icons-png.flaticon.com/512/3097/3097180.png"},
        {"name": "Honda RC213V-S", "price": 30000000, "chance": 20, "img": "https://cdn-icons-png.flaticon.com/512/3097/3097180.png"},
    ]
}

PARTS = [
    {"name": "Двигатель", "rarity": "D", "chance": 40, "price": 5000, "img": "⚙️"},
    {"name": "Турбина", "rarity": "D", "chance": 30, "price": 5000, "img": "🌀"},
    {"name": "КПП", "rarity": "C", "chance": 15, "price": 15000, "img": "⚙️"},
    {"name": "Выхлоп", "rarity": "C", "chance": 10, "price": 15000, "img": "🔧"},
    {"name": "Подвеска", "rarity": "B", "chance": 5, "price": 40000, "img": "🔩"},
    {"name": "Тормоза", "rarity": "A", "chance": 2, "price": 120000, "img": "🛑"},
    {"name": "Обвес", "rarity": "A", "chance": 1, "price": 120000, "img": "🛡️"},
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

# --- API ---
async def get_user(request):
    user_id = int(request.match_info.get('user_id', 1))
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT balance, last_collect, daily_day, last_daily, referrer_id, ref_reward_claimed, starter_cases, fast_open FROM users WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            if not row:
                await db.execute("INSERT INTO users (user_id) VALUES (?)", (user_id,))
                await db.commit()
                return web.json_response({"balance": 50000, "inventory": [], "daily_day": 1, "last_daily": 0, "starter_cases": 3, "ref_reward": False, "fast_open": 0, "pending_income": 0})
            
            balance, last_collect, daily_day, last_daily, referrer_id, ref_reward_claimed, starter_cases, fast_open = row
            now = int(time.time())
            
            earned = 0
            time_passed = now - last_collect
            if time_passed > 0:
                async with db.execute("SELECT COUNT(*) FROM inventory WHERE user_id = ? AND item_type = 'bike' AND in_garage = 1", (user_id,)) as c:
                    bikes_count = (await c.fetchone())[0]
                income_per_hour = bikes_count * 1000
                effective_time = min(time_passed, 14400)
                earned = int((effective_time / 3600) * income_per_hour)

        async with db.execute("SELECT id, item_type, item_name, rarity, income, in_garage, img_url FROM inventory WHERE user_id = ?", (user_id,)) as cursor:
            inv_rows = await cursor.fetchall()
            inventory = [{"id": r[0], "type": r[1], "name": r[2], "rarity": r[3], "income": r[4], "in_garage": r[5], "img_url": r[6]} for r in inv_rows]

    return web.json_response({
        "balance": balance,
        "pending_income": earned,
        "inventory": inventory,
        "daily_day": daily_day,
        "last_daily": last_daily,
        "starter_cases": starter_cases,
        "ref_reward": bool(ref_reward_claimed),
        "referrer_id": referrer_id,
        "fast_open": bool(fast_open)
    })

async def collect_income(request):
    user_id = int(request.match_info.get('user_id', 1))
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT balance, last_collect FROM users WHERE user_id = ?", (user_id,)) as c:
            balance, last_collect = await c.fetchone()
        now = int(time.time())
        time_passed = now - last_collect
        if time_passed <= 0: return web.json_response({"message": "Пока нечего забирать"})
        
        async with db.execute("SELECT COUNT(*) FROM inventory WHERE user_id = ? AND item_type = 'bike' AND in_garage = 1", (user_id,)) as c:
            bikes_count = (await c.fetchone())[0]
        income_per_hour = bikes_count * 1000
        effective_time = min(time_passed, 14400)
        earned = int((effective_time / 3600) * income_per_hour)
        
        if earned > 0:
            await db.execute("UPDATE users SET balance = balance + ?, last_collect = ? WHERE user_id = ?", (earned, now, user_id))
            await db.commit()
    return web.json_response({"message": f"Вы забрали {earned} ₽!"})

async def toggle_fast_open(request):
    user_id = int(request.match_info.get('user_id', 1))
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT fast_open FROM users WHERE user_id = ?", (user_id,)) as c:
            current = (await c.fetchone())[0]
        new_val = 1 if current == 0 else 0
        await db.execute("UPDATE users SET fast_open = ? WHERE user_id = ?", (new_val, user_id))
        await db.commit()
    return web.json_response({"fast_open": bool(new_val)})

async def open_case(request):
    user_id = int(request.match_info.get('user_id', 1))
    data = await request.json()
    case_type = data.get("case_type")
    garage_key = data.get("garage_key", "rusty")
    quantity = data.get("quantity", 1)
    is_starter = data.get("is_starter", False)

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT balance, starter_cases FROM users WHERE user_id = ?", (user_id,)) as cursor:
            balance, starter_cases = await cursor.fetchone()

        if is_starter:
            if starter_cases < quantity: return web.json_response({"error": "Недостаточно стартовых кейсов"}, status=400)
            cost_per_one = 0
            await db.execute("UPDATE users SET starter_cases = starter_cases - ? WHERE user_id = ?", (quantity, user_id))
        else:
            cost_per_one = GARAGES[garage_key]["price"]
            total_cost = cost_per_one * quantity
            if balance < total_cost: return web.json_response({"error": "Недостаточно средств"}, status=400)
            await db.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (total_cost, user_id))

        async with db.execute("SELECT COUNT(*) FROM inventory WHERE user_id = ? AND item_type = 'bike'", (user_id,)) as c:
            total_bikes = (await c.fetchone())[0]
        if total_bikes + quantity > 26: return web.json_response({"error": "Недостаточно места на складе"}, status=400)

        items_won = []
        pool = MOTORCYCLES["rusty"] if is_starter else MOTORCYCLES[garage_key]
        
        for _ in range(quantity):
            if case_type == 'bike':
                item = get_random_item(pool)
                income = item["price"] // 10
                await db.execute("INSERT INTO inventory (user_id, item_type, item_name, rarity, income, price, img_url) VALUES (?, 'bike', ?, ?, ?, ?, ?)",
                                 (user_id, item["name"], GARAGES["rusty"]["rarity"] if is_starter else GARAGES[garage_key]["rarity"], income, item["price"], item["img"]))
                items_won.append({**item, "rarity": GARAGES["rusty"]["rarity"] if is_starter else GARAGES[garage_key]["rarity"]})
            elif case_type == 'part':
                item = get_random_item(PARTS)
                await db.execute("INSERT INTO inventory (user_id, item_type, item_name, rarity, income, price, img_url) VALUES (?, 'part', ?, ?, 0, ?, ?)",
                                 (user_id, item["name"], item["rarity"], item["price"], item["img"]))
                items_won.append(item)

        await db.commit()
    return web.json_response({"items": items_won, "message": "Успех!"})

async def craft_item(request):
    user_id = int(request.match_info.get('user_id', 1))
    data = await request.json()
    rarity = data.get("rarity")
    
    rarities = ["D", "C", "B", "A", "S"]
    if rarity not in rarities or rarity == "S": return web.json_response({"error": "Нельзя скрафтить"}, status=400)
    next_rarity = rarities[rarities.index(rarity) + 1]

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT id, item_name FROM inventory WHERE user_id = ? AND item_type = 'part' AND rarity = ? LIMIT 3", (user_id, rarity)) as c:
            items = await c.fetchall()
            if len(items) < 3: return web.json_response({"error": "Нужно 3 детали"}, status=400)
            
            ids_to_del = [str(i[0]) for i in items]
            await db.execute(f"DELETE FROM inventory WHERE id IN ({','.join(ids_to_del)})")
            
            valid_parts = [p for p in PARTS if p["rarity"] == next_rarity]
            new_item = random.choice(valid_parts) if valid_parts else PARTS[0]
            
            await db.execute("INSERT INTO inventory (user_id, item_type, item_name, rarity, income, price, img_url) VALUES (?, 'part', ?, ?, 0, ?, ?)",
                             (user_id, new_item["name"], next_rarity, new_item["price"], new_item["img"]))
            await db.commit()
    return web.json_response({"message": f"Успешно! Получен {new_item['name']} ранга {next_rarity}"})

async def equip_item(request):
    user_id = int(request.match_info.get('user_id', 1))
    data = await request.json()
    item_id = data.get("item_id")
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM inventory WHERE user_id = ? AND item_type = 'bike' AND in_garage = 1", (user_id,)) as c:
            count = (await c.fetchone())[0]
        if count >= 6: return web.json_response({"error": "Гараж заполнен"}, status=400)
        await db.execute("UPDATE inventory SET in_garage = 1 WHERE id = ? AND user_id = ?", (item_id, user_id))
        await db.commit()
    return web.json_response({"message": "В гараже!"})

async def sell_item(request):
    user_id = int(request.match_info.get('user_id', 1))
    data = await request.json()
    item_id = data.get("item_id")
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT price FROM inventory WHERE id = ? AND user_id = ?", (item_id, user_id)) as c:
            row = await c.fetchone()
            if not row: return web.json_response({"error": "Не найдено"}, status=404)
            price = row[0] // 2 
            await db.execute("DELETE FROM inventory WHERE id = ?", (item_id,))
            await db.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (price, user_id))
            await db.commit()
    return web.json_response({"message": f"Продано за {price} ₽"})

async def claim_daily(request):
    user_id = int(request.match_info.get('user_id', 1))
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT daily_day, last_daily FROM users WHERE user_id = ?", (user_id,)) as c:
            daily_day, last_daily = await c.fetchone()
        now = int(time.time())
        if now - last_daily < 86400: return web.json_response({"error": "Еще не доступно"}, status=400)
        await db.execute("UPDATE users SET daily_day = ?, last_daily = ? WHERE user_id = ?", (daily_day + 1 if daily_day < 14 else 1, now, user_id))
        await db.commit()
    return web.json_response({"message": "Награда получена!"})

async def handle_index(request):
    path = os.path.join(os.path.dirname(__file__), "index.html")
    return web.FileResponse(path)

def create_web_app():
    app = web.Application()
    app.router.add_get("/", handle_index)
    app.router.add_get("/index.html", handle_index)
    app.router.add_get("/api/user/{user_id}", get_user)
    app.router.add_post("/api/user/{user_id}/collect", collect_income)
    app.router.add_post("/api/user/{user_id}/toggle_fast", toggle_fast_open)
    app.router.add_post("/api/user/{user_id}/case", open_case)
    app.router.add_post("/api/user/{user_id}/craft", craft_item)
    app.router.add_post("/api/user/{user_id}/equip", equip_item)
    app.router.add_post("/api/user/{user_id}/sell", sell_item)
    app.router.add_post("/api/user/{user_id}/daily", claim_daily)
    return app

@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
        await db.commit()
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🎮 Открыть игру", web_app=WebAppInfo(url=f"{WEBAPP_URL}"))]])
    ref_link = f"https://t.me/{(await bot.get_me()).username}?start=ref_{user_id}"
    await message.answer(f"Привет! Открывай игру 👇\nТвоя ссылка:\n<code>{ref_link}</code>", reply_markup=kb)

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
