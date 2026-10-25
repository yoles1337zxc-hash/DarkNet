import os
import threading
import telebot
from flask import Flask

TOKEN = os.environ.get("8986372455:AAFVgPDz3Vcq8RcZ3PBf3hfpNA41eyVXUL8")

app = Flask(name)

@app.route('/')
def health(): 
  return "Bot is running"
def run_web(): # Render сам дает порт в переменной PORT port = int(os.environ.get("PORT", 10000)) app.run(host="0.0.0.0", port=port)

bot = telebot.TeleBot(8986372455:AAFVgPDz3Vcq8RcZ3PBf3hfpNA41eyVXUL8)
@bot.message_handler(commands=['start'])
def start(message): bot.send_message(message.chat.id, "🟢 Привет, хакер! Терминал подключен к сети.")
@bot.message_handler(commands=['claim'])
def claim(message): bot.send_message(message.chat.id, "💸 Успешный взлом! Вы забрали 100 ₽.")
@bot.message_handler(commands=['case'])
def case(message): bot.send_message(message.chat.id, "📦 Архив вскрыт! Выпал: Скрипт 'Червь'.")


threading.Thread(target=run_web, 
daemon=True).start()
print("Бот запущен...") 

bot.infinity_polling()
