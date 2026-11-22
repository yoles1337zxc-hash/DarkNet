import asyncio
import logging
import os
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import WebAppInfo, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiohttp import web

# --- НАСТРОЙКИ ДЛЯ RENDER ---
# Берем токен из переменных окружения (Environment Variables) в панели Render
BOT_TOKEN = os.environ.get("8986372455:AAGDbogn60ZJPeGiC626wFOej4isMBHj7_Q")
# Берем URL из переменных (Render сам выдаст вам адрес, скопируйте его сюда)
WEBAPP_URL = os.environ.get("WEBAPP_URL", "https://ваш-сайт.onrender.com/index.html")
WEBAPP_HOST = "0.0.0.0"
# Render сам назначает порт, по умолчанию используем 8080
WEBAPP_PORT = int(os.environ.get("PORT", 8080))

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# --- ВЕБ-СЕРВЕР ДЛЯ ОТДАЧИ HTML ---
async def handle_index(request):
    # Отдаем файл index.html из корневой папки
    return web.FileResponse('./index.html')

def create_web_app():
    app = web.Application()
    app.router.add_get('/index.html', handle_index)
    app.router.add_get('/', handle_index) # Добавил на случай пинга UptimeRobot
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
    site = web.TCPSite(runner, WEBAPP_HOST, WEBAPP_PORT)
    await site.start()
    logging.info(f"Сервер запущен на порту {WEBAPP_PORT}")

    # Запускаем бота
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Бот остановлен")
