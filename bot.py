import asyncio
import logging
import os
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import WebAppInfo, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiohttp import web

# --- НАСТРОЙКИ ---
# Если переменной BOT_TOKEN нет в Render, бот упадет с понятной ошибкой
BOT_TOKEN = os.environ.get("8986372455:AAEqZjMO8rKRbSyK_RdjbGFpP1wa7OJqdYI")

# Если WEBAPP_URL не задан, ставим заглушку, чтобы бот не падал при старте
WEBAPP_URL = os.environ.get("https://darknet-a0b2.onrender.com")

# Render автоматически назначает порт. Берем его из переменной PORT
WEBAPP_PORT = int(os.environ.get("PORT", 8080))

logging.basicConfig(level=logging.INFO)

# Проверка на наличие токена перед запуском
if not BOT_TOKEN:
    logging.error("КРИТИЧЕСКАЯ ОШИБКА: Переменная BOT_TOKEN не задана в настройках Render!")
    raise ValueError("BOT_TOKEN environment variable is not set")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# --- ВЕБ-СЕРВЕР ДЛЯ ОТДАЧИ HTML ---
async def handle_index(request):
    # Отдаем файл index.html из корневой папки
    return web.FileResponse('./index.html')

async def handle_health(request):
    # Заглушка для Render (чтобы он видел, что сервис живой)
    return web.Response(text="Bot is running!")

def create_web_app():
    app = web.Application()
    app.router.add_get('/index.html', handle_index)
    app.router.add_get('/', handle_health) # Render пингует этот адрес
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
    # Запускаем веб-сервер
    app = create_web_app()
    runner = web.AppRunner(app)
    await runner.setup()
    
    try:
        site = web.TCPSite(runner, '0.0.0.0', WEBAPP_PORT)
        await site.start()
        logging.info(f"Веб-сервер успешно запущен на порту {WEBAPP_PORT}")
    except Exception as e:
        logging.error(f"Не удалось запустить веб-сервер: {e}")

    # Запускаем бота
    logging.info("Запуск Telegram-бота...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Бот остановлен")
