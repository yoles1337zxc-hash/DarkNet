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

BOT_TOKEN = os.getenv("8986372455:AAEqZjMO8rKRbSyK_RdjbGFpP1wa7OJqdYI")
WEBAPP_URL = os.getenv("https://darknet-a0b2.onrender.com")
PORT = int(os.getenv("PORT", 8080))
DB_PATH = "dropezone.db"

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# --- ИНИЦИАЛИЗАЦИЯ БАЗЫ ДАННЫХ ---
async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                balance INTEGER DEFAULT 400000,
                last_collect INTEGER DEFAULT 0
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS inventory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                item_type TEXT, -- 'bike' или 'part'
                item_name TEXT,
                rarity TEXT,
                income INTEGER DEFAULT 0
            )
        """)
        # Добавляем тестового пользователя для проверки в браузере
        await db.execute("INSERT OR IGNORE INTO users (user_id) VALUES (1)")
        await db.commit()

# --- ДАННЫЕ ИГРЫ ---
# Шансы и цены взяты с твоих скриншотов. Income (доход в час) = 1/10 от цены.
BIKES = [
    {"name": "Ржавый гараж", "rarity": "D", "price": 50000, "chance": 99.6},
    {"name": "Поддержанные", "rarity": "D", "price": 150000, "chance": 95.5},
    {"name": "Городской", "rarity": "C", "price": 500000, "chance": 85.3},
    {"name": "Тюнинг-ателье", "rarity": "B", "price": 1200000, "chance": 37.8},
    {"name": "Спортбайк", "rarity": "A", "price": 2500000, "chance": 67.0},
    {"name": "Премиум", "rarity": "A", "price": 5000000, "chance": 12.5},
    {"name": "Элита", "rarity": "S", "price": 8000000, "chance": 56.3}
]

PARTS = [
    {"name": "Разборка", "rarity": "D", "chance": 85.0},
    {"name": "Тюнинг-ателье", "rarity": "C", "chance": 50.0},
    {"name": "Гоночный цех", "rarity": "B", "chance": 30.0},
    {"name": "Заводской тюнинг", "rarity": "A", "chance": 39.88},
    {"name": "Секретный цех", "rarity": "S", "chance": 9.97}
]

# Функция выбора предмета по шансам
def get_random_item(items):
    total_chance = sum(item["chance"] for item in items)
    rand = random.uniform(0, total_chance)
    current = 0
    for item in items:
        current += item["chance"]
        if rand <= current:
            return item
    return items[0]

# --- API ДЛЯ MINI APP ---
async def get_user(request):
    user_id = int(request.match_info.get('user_id', 1)) # 1 - для теста в браузере
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT balance, last_collect FROM users WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            if not row:
                return web.json_response({"error": "User not found"}, status=404)
            
            balance, last_collect = row
            # Логика гаража: 4 часа = 14400 секунд
            now = int(time.time())
            time_passed = now - last_collect
            max_income_time = 14400
            earned = 0
            
            if time_passed > 0:
                # Считаем доход (упрощенно: 1000 в час за каждый байк)
                async with db.execute("SELECT COUNT(*) FROM inventory WHERE user_id = ? AND item_type = 'bike'", (user_id,)) as c:
                    bikes_count = (await c.fetchone())[0]
                
                income_per_hour = bikes_count * 1000
                # Ограничение в 4 часа
                effective_time = min(time_passed, max_income_time)
                earned = int((effective_time / 3600) * income_per_hour)
                
                # Обновляем время, если прошло больше 0
                if earned > 0:
                    await db.execute("UPDATE users SET balance = balance + ?, last_collect = ? WHERE user_id = ?", (earned, now, user_id))
                    await db.commit()

        # Получаем инвентарь
        async with db.execute("SELECT id, item_type, item_name, rarity, income FROM inventory WHERE user_id = ?", (user_id,)) as cursor:
            inv_rows = await cursor.fetchall()
            inventory = [{"id": r[0], "type": r[1], "name": r[2], "rarity": r[3], "income": r[4]} for r in inv_rows]

    return web.json_response({
        "balance": balance + earned,
        "inventory": inventory
    })

async def open_case(request):
    user_id = int(request.match_info.get('user_id', 1))
    data = await request.json()
    case_type = data.get("case_type") # 'bike' или 'part'

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,)) as cursor:
            balance = (await cursor.fetchone())[0]

        # Списываем деньги
        cost = 14000 if case_type == 'bike' else 14000 # Цены за кейс
        if balance < cost:
            return web.json_response({"error": "Недостаточно средств"}, status=400)

        await db.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (cost, user_id))

        # Выбиваем предмет
        if case_type == 'bike':
            item = get_random_item(BIKES)
            income = item["price"] // 10 # Доход в час
            await db.execute("INSERT INTO inventory (user_id, item_type, item_name, rarity, income) VALUES (?, 'bike', ?, ?, ?)",
                             (user_id, item["name"], item["rarity"], income))
        else:
            item = get_random_item(PARTS)
            await db.execute("INSERT INTO inventory (user_id, item_type, item_name, rarity, income) VALUES (?, 'part', ?, ?, 0)",
                             (user_id, item["name"], item["rarity"]))

        await db.commit()

    return web.json_response({"item": item, "message": "Успех!"})

async def craft(request):
    """Мастерская: 3 предмета одной редкости -> 1 выше"""
    user_id = int(request.match_info.get('user_id', 1))
    data = await request.json()
    rarity = data.get("rarity")
    
    rarities = ["D", "C", "B", "A", "S"]
    if rarity not in rarities or rarity == "S":
        return web.json_response({"error": "Нельзя скрафтить"}, status=400)

    next_rarity = rarities[rarities.index(rarity) + 1]

    async with aiosqlite.connect(DB_PATH) as db:
        # Ищем 3 предмета нужной редкости (запчасти)
        async with db.execute("SELECT id FROM inventory WHERE user_id = ? AND item_type = 'part' AND rarity = ? LIMIT 3", (user_id, rarity)) as c:
            items = await c.fetchall()
            if len(items) < 3:
                return web.json_response({"error": "Нужно 3 запчасти этой редкости"}, status=400)
            
            # Удаляем их
            ids_to_del = [str(item[0]) for item in items]
            await db.execute(f"DELETE FROM inventory WHERE id IN ({','.join(ids_to_del)})", )
            
            # Создаем новую
            item_name = f"Запчасть ранга {next_rarity}"
            await db.execute("INSERT INTO inventory (user_id, item_type, item_name, rarity, income) VALUES (?, 'part', ?, ?, 0)",
                             (user_id, item_name, next_rarity))
            await db.commit()

    return web.json_response({"message": f"Успешно! Получен предмет ранга {next_rarity}"})

# --- РАЗДАЧА HTML ---
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
    return app

# --- ХЕНДЛЕРЫ БОТА ---
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎮 Открыть игру", web_app=WebAppInfo(url=f"{WEBAPP_URL}"))]
    ])
    await message.answer("Привет! Открывай игру и зарабатывай на байках 👇", reply_markup=kb)

# --- ЗАПУСК ---
async def main():
    await init_db() # Создаем БД
    await bot.set_chat_menu_button(menu_button=MenuButtonWebApp(text="🎮 Играть", web_app=WebAppInfo(url=f"{WEBAPP_URL}")))
    
    app = create_web_app()
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    print(f"🌐 Server started on port {PORT}")
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
