import asyncio
import logging
import os
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import WebAppInfo, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiohttp import web

# --- НАСТРОЙКИ ---
# Получаем токен из переменных окружения
BOT_TOKEN = os.environ.get("8986372455:AAEqZjMO8rKRbSyK_RdjbGFpP1wa7OJqdYI")
BOT_TOKEN = ("8986372455:AAEqZjMO8rKRbSyK_RdjbGFpP1wa7OJqdYI")
if not BOT_TOKEN:
    logging.warning("ВНИМАНИЕ: Переменная BOT_TOKEN не найдена в окружении! Используется тестовая заглушка.")
    BOT_TOKEN = "123456789:TEST_TOKEN" # Заглушка, чтобы код не падал

# Выводим первые 5 символов токена в логи для проверки (безопасно)
logging.info(f"Загружен токен (первые 5 символов): {BOT_TOKEN[:5]}...")

WEBAPP_URL = os.environ.get("WEBAPP_URL", "https://example.com")
WEBAPP_PORT = int(os.environ.get("PORT", 8080))

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# --- ВЕБ-СЕРВЕР ДЛЯ ОТДАЧИ HTML ---
async def handle_index(request):
    return web.FileResponse('./index.html')

async def handle_health(request):
    return web.Response(text="Bot is running!")

def create_web_app():
    app = web.Application()
    app.router.add_get('/index.html', handle_index)
    app.router.add_get('/', handle_health) 
    return app

# --- ХЕНДЛЕРЫ БОТА ---
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="🏍️ Открыть Гараж", 
            web_app=WebAppInfo(url=WEBAPP_URL)
        )
    )
    await message.answer(
        "Добро пожаловать в Мото Кейсы! 🏁\n"
        "Нажми на кнопку ниже, чтобы начать собирать свою коллекцию.",
        reply_markup=builder.as_markup()
    )

# --- ЗАПУСК ---
async def main():
    app = create_web_app()
    runner = web.AppRunner(app)
    await runner.setup()
    
    try:
        site = web.TCPSite(runner, '0.0.0.0', WEBAPP_PORT)
        await site.start()
        logging.info(f"Веб-сервер запущен на порту {WEBAPP_PORT}")
    except Exception as e:
        logging.error(f"Не удалось запустить веб-сервер: {e}")

    logging.info("Запуск Telegram-бота...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Бот остановлен")
