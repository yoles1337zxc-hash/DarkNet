import asyncio
import logging
import os
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import WebAppInfo, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiohttp import web

# --- НАСТРОЙКИ ---
BOT_TOKEN = "8986372455:AAGDbogn60ZJPeGiC626wFOej4isMBHj7_Q"  # ЗАМЕНИТЕ НА ВАШ ТОКЕН
WEBAPP_HOST = "0.0.0.0"
WEBAPP_PORT = 8080
# URL, где будет хоститься index.html. 
# Для теста локально можно использовать ngrok (например: https://xxxx.ngrok-free.app)
WEBAPP_URL = f"http://{WEBAPP_HOST}:{WEBAPP_PORT}/index.html" 

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# --- ВЕБ-СЕРВЕР ДЛЯ ОТДАЧИ HTML ---
async def handle_index(request):
    # Отдаем файл index.html из той же папки
    return web.FileResponse('./index.html')

def create_web_app():
    app = web.Application()
    app.router.add_get('/index.html', handle_index)
    return app

# --- ХЕНДЛЕРЫ БОТА ---
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    # Создаем кнопку для запуска Mini App
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
    # Запускаем веб-сервер в фоне
    app = create_web_app()
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, WEBAPP_HOST, WEBAPP_PORT)
    await site.start()
    logging.info(f"Сервер запущен на {WEBAPP_URL}")

    # Запускаем бота
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
