
import os
import telebot

TOKEN = os.getenv("BOT_TOKEN")

bot = telebot.TeleBot(TOKEN)

@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(
        message,
        "Assalomu alaykum! 🎬\n"
        "Video tarjimon botiga xush kelibsiz!\n\n"
        "Menga video yuboring. "
        "Men uni o'zbek tiliga tarjima qilaman."
    )

@bot.message_handler(content_types=['video'])
def video(message):
    bot.reply_to(
        message,
        "Videongiz qabul qilindi! 🎥\n"
        "Tarjima tizimi hozir sozlanmoqda."
    )

bot.infinity_polling()
