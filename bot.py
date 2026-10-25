import os
import threading
import telebot
from flask import Flask

TOKEN = os.environ.get("BOT_TOKEN")

app = Flask(__name__)

@app.route('/')
def health():
    return "Bot is running"

def run_web():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

bot = telebot.TeleBot(TOKEN)

@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(message.chat.id, "🟢 Привет, хакер!")

@bot.message_handler(commands=['claim'])
def claim(message):
    bot.send_message(message.chat.id, "💸 Вы забрали 100 ₽.")

@bot.message_handler(commands=['case'])
def case(message):
    bot.send_message(message.chat.id, "📦 Выпал Скрипт!")

threading.Thread(target=run_web, daemon=True).start()

print("Бот запущен...")
bot.infinity_polling()
