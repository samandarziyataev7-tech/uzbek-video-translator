
import os
import asyncio
import tempfile
import subprocess
import requests
import telebot
import edge_tts
import imageio_ffmpeg

from flask import Flask, request
from deep_translator import GoogleTranslator

TOKEN = os.getenv("BOT_TOKEN")
GROQ_KEY = os.getenv("GROQ_API_KEY")
URL = os.getenv("RENDER_EXTERNAL_URL")

if not TOKEN or not GROQ_KEY:
    raise RuntimeError("BOT_TOKEN yoki GROQ_API_KEY topilmadi")

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()


@bot.message_handler(commands=["start"])
def start(message):
    bot.reply_to(
        message,
        "Assalomu alaykum! 🇺🇿\n"
        "Video yuboring. Men ovozini o‘zbekchaga tarjima qilaman."
    )


def transcribe_audio(audio_path):
    with open(audio_path, "rb") as audio:
        response = requests.post(
            "https://api.groq.com/openai/v1/audio/transcriptions",
            headers={"Authorization": f"Bearer {GROQ_KEY}"},
            files={"file": ("audio.mp3", audio, "audio/mpeg")},
            data={
                "model": "whisper-large-v3-turbo",
                "response_format": "json"
            },
            timeout=180
        )

    response.raise_for_status()
    return response.json()["text"]


def translate_text(text):
    translator = GoogleTranslator(source="auto", target="uz")
    chunks = [text[i:i+4000] for i in range(0, len(text), 4000)]
    return " ".join(translator.translate(chunk) for chunk in chunks)


async def make_voice(text, output):
    voice = edge_tts.Communicate(
        text,
        voice="uz-UZ-MadinaNeural"
    )
    await voice.save(output)


def process_video(input_video, output_video, workdir):
    audio_file = os.path.join(workdir, "audio.mp3")
    voice_file = os.path.join(workdir, "voice.mp3")

    subprocess.run([
        FFMPEG, "-y", "-i", input_video,
        "-vn", "-ac", "1", "-b:a", "96k", audio_file
    ], check=True, capture_output=True)

    if os.path.getsize(audio_file) > 24 * 1024 * 1024:
        raise ValueError("Video juda uzun. Kichikroq video yuboring.")

    original_text = transcribe_audio(audio_file)

    if not original_text.strip():
        raise ValueError("Videoda aniqlanadigan nutq topilmadi.")

    uzbek_text = translate_text(original_text)

    if len(uzbek_text) > 10000:
        raise ValueError("Video juda uzun. Qisqaroq video yuboring.")

    asyncio.run(make_voice(uzbek_text, voice_file))

    subprocess.run([
        FFMPEG, "-y",
        "-i", input_video,
        "-i", voice_file,
        "-map", "0:v:0",
        "-map", "1:a:0",
        "-c:v", "copy",
        "-c:a", "aac",
        "-b:a", "128k",
        "-af", "apad",
        "-shortest",
        "-movflags", "+faststart",
        output_video
    ], check=True, capture_output=True)


@bot.message_handler(content_types=["video"])
def video_handler(message):
    status = bot.reply_to(message, "🎬 Video qabul qilindi. Ishlayapman...")

    try:
        file_info = bot.get_file(message.video.file_id)

        if file_info.file_size and file_info.file_size > 20 * 1024 * 1024:
            bot.edit_message_text(
                "Video 20 MB dan kichik bo‘lishi kerak.",
                message.chat.id,
                status.message_id
            )
            return

        with tempfile.TemporaryDirectory() as workdir:
            input_video = os.path.join(workdir, "input.mp4")
            output_video = os.path.join(workdir, "uzbek_video.mp4")

            data = bot.download_file(file_info.file_path)

            with open(input_video, "wb") as f:
                f.write(data)

            bot.edit_message_text(
                "🎙️ Ovoz ajratilmoqda va tarjima qilinmoqda...",
                message.chat.id,
                status.message_id
            )

            process_video(input_video, output_video, workdir)

            with open(output_video, "rb") as f:
                bot.send_video(
                    message.chat.id,
                    f,
                    caption="🇺🇿 O‘zbekcha ovozli video tayyor!"
                )

            bot.delete_message(message.chat.id, status.message_id)

    except Exception as e:
        print("XATO:", repr(e))
        bot.edit_message_text(
            "❌ Tarjimada xatolik yuz berdi. Kichikroq video yuborib ko‘ring.",
            message.chat.id,
            status.message_id
        )


@app.route("/", methods=["GET"])
def home():
    return "Uzbek Video Translator ishlayapti!"


@app.route("/" + TOKEN, methods=["POST"])
def telegram_webhook():
    update = telebot.types.Update.de_json(
        request.get_data().decode("utf-8")
    )
    bot.process_new_updates([update])
    return "OK", 200


if URL:
    bot.remove_webhook()
    bot.set_webhook(url=URL + "/" + TOKEN)

