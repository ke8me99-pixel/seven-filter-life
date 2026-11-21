import os
import subprocess
import telebot

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("Set the BOT_TOKEN environment variable before starting the bot.")

bot = telebot.TeleBot(BOT_TOKEN)

BOT_BRAND = "𝖘𝖊𝟕𝖊𝖓 𝖋𝖎𝖑𝖙𝖊𝖗 𝖑𝖎𝖋𝖊"

@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(
        message,
        f"أهلاً بك في *{BOT_BRAND}* 🎬\nأرسل لي مقطع فيديو وسأرجعه لك بفلتر أبيض وأسود.",
        parse_mode="Markdown"
    )

@bot.message_handler(content_types=['video'])
def handle_video(message):
    msg = bot.reply_to(message, f"جاري تحويل المقطع عبر {BOT_BRAND}...")
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
            "-c:a", "copy",
            output_path
        ]
        subprocess.run(command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        with open(output_path, 'rb') as video_out:
            bot.send_video(message.chat.id, video_out, caption=f"تم التحويل بواسطة {BOT_BRAND}")

        bot.delete_message(message.chat.id, msg.message_id)

    except Exception as e:
        bot.edit_message_text(f"حدث خطأ أثناء المعالجة: {e}", message.chat.id, msg.message_id)

    finally:
        for path in (input_path, output_path):
            if os.path.exists(path):
                os.remove(path)

bot.infinity_polling()
