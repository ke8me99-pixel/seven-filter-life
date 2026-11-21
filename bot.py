import os
import subprocess
import telebot

BOT_TOKEN = os.getenv("BOT_TOKEN", "9114458150:AAHpOOt4Hy0BFjVSjRNaC0OdyYHYnUYo4hQ")
bot = telebot.TeleBot(BOT_TOKEN)

MSG_WELCOME = "𝖜𝖊𝖑𝖈𝖔𝖒𝖊 𝖜𝖎𝖙𝖍 𝖘𝖊𝟕𝖊𝖓"
MSG_PROCESSING = "𝖕𝖗𝖔𝖈𝖊𝖘𝖘𝖎𝖓𝖌..."
MSG_DONE = "𝖉𝖔𝖓𝖊 𝖇𝖆𝖇𝖊"
MSG_ERROR = "𝖊𝖗𝖗𝖔𝖗 𝖇𝖆𝖇𝖊"

@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, MSG_WELCOME)

@bot.message_handler(content_types=['video'])
def handle_video(message):
    msg = bot.reply_to(message, MSG_PROCESSING)
    file_info = bot.get_file(message.video.file_id)
    downloaded_file = bot.download_file(file_info.file_path)

    input_path = f"input_{message.chat.id}.mp4"
    output_path = f"bw_{message.chat.id}.mp4"

    try:
        with open(input_path, 'wb') as f:
            f.write(downloaded_file)

        command = [
            "ffmpeg", "-y", "-i", input_path,
            "-vf", "hue=s=0",
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "24",
            "-c:a", "aac", "-b:a", "128k",
            output_path
        ]
        result = subprocess.run(command, capture_output=True, text=True)

        if result.returncode != 0 or not os.path.exists(output_path):
            raise RuntimeError("ffmpeg failed")

        with open(output_path, 'rb') as video_out:
            bot.send_video(message.chat.id, video_out, caption=MSG_DONE)

        bot.delete_message(message.chat.id, msg.message_id)

    except Exception:
        bot.edit_message_text(MSG_ERROR, message.chat.id, msg.message_id)

    finally:
        for path in (input_path, output_path):
            if os.path.exists(path):
                os.remove(path)

bot.infinity_polling(skip_pending=True)
