import os
import telebot

TOKEN = os.environ.get("8986372455:AAFVgPDz3Vcq8RcZ3PBf3hfpNA41eyVXUL8")

bot = telebot.TeleBot(TOKEN)

@bot.message_handler(commands=['start'])
def start(message): bot.send_message(message.chat.id, "🟢 Привет, хакер! Терминал подключен к сети.")
@bot.message_handler(commands=['claim'])
def claim(message): bot.send_message(message.chat.id, "💸 Успешный взлом! Вы забрали 100 ₽.")
@bot.message_handler(commands=['case'])
def case(message): bot.send_message(message.chat.id, "📦 Архив вскрыт! Выпал: Скрипт 'Червь'.")

print("Бот запущен...")
bot.infinity_polling()
