import os
import re
import subprocess
import telebot
from telebot import types

BOT_TOKEN = os.getenv("BOT_TOKEN", "9114458150:AAHpOOt4Hy0BFjVSjRNaC0OdyYHYnUYo4hQ")
bot = telebot.TeleBot(BOT_TOKEN)

MSG_WELCOME = "𝖜𝖊𝖑𝖈𝖔𝖒𝖊 𝖜𝖎𝖙𝖍 𝖘𝖊𝟕𝖊𝖓"
MSG_ASK_CUT = "𝖈𝖚𝖙?"
MSG_ASK_RANGE = "00:00 to 00:17"
MSG_ASK_ACTION = "𝖈𝖍𝖔𝖔𝖘𝖊"
MSG_ASK_COVER = "𝖈𝖔𝖛𝖊𝖗?"
MSG_SEND_COVER = "𝖘𝖊𝖓𝖉 𝖕𝖍𝖔𝖙𝖔"
MSG_ASK_ARTIST = "𝖆𝖗𝖙𝖎𝖘𝖙?"
MSG_SEND_ARTIST = "𝖘𝖊𝖓𝖉 𝖓𝖆𝖒𝖊"
MSG_PROCESSING = "𝖕𝖗𝖔𝖈𝖊𝖘𝖘𝖎𝖓𝖌..."
MSG_DONE = "𝖉𝖔𝖓𝖊 𝖇𝖆𝖇𝖊"
MSG_ERROR = "𝖊𝖗𝖗𝖔𝖗 𝖇𝖆𝖇𝖊"

BTN_YES = "𝖞𝖊𝖘"
BTN_NO = "𝖓𝖔"
BTN_FILTER = "𝖋𝖎𝖑𝖙𝖊𝖗"
BTN_MP3 = "𝖒𝖕3"
BTN_VOICE = "𝖛𝖔𝖎𝖈𝖊"

user_sessions = {}


def parse_time_to_seconds(t_str: str) -> float:
    t_str = t_str.strip()
    if re.fullmatch(r"\d+(\.\d+)?", t_str):
        return float(t_str)
    parts = [float(p) for p in t_str.split(":")]
    if len(parts) == 2:
        minutes, seconds = parts
        return minutes * 60.0 + seconds
    if len(parts) == 3:
        hours, minutes, seconds = parts
        return hours * 3600.0 + minutes * 60.0 + seconds
    raise ValueError("Invalid time format")


def parse_trim_range(text: str):
    match = re.match(r"^\s*(.+?)\s*(?:to|-|–|—|الى|إلى)\s*(.+?)\s*$", text, flags=re.IGNORECASE)
    if not match:
        raise ValueError("Range format mismatch")
    start_sec = parse_time_to_seconds(match.group(1))
    end_sec = parse_time_to_seconds(match.group(2))
    if start_sec < 0 or end_sec <= start_sec:
        raise ValueError("Invalid start/end values")
    return start_sec, end_sec


def cut_keyboard():
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton(BTN_YES, callback_data="cut_yes"),
        types.InlineKeyboardButton(BTN_NO, callback_data="cut_no"),
    )
    return kb


def yes_no_keyboard(prefix: str):
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton(BTN_YES, callback_data=f"{prefix}_yes"),
        types.InlineKeyboardButton(BTN_NO, callback_data=f"{prefix}_no"),
    )
    return kb


def action_keyboard(media_type: str):
    kb = types.InlineKeyboardMarkup(row_width=3)
    if media_type == "video":
        kb.add(
            types.InlineKeyboardButton(BTN_FILTER, callback_data="act_bw"),
            types.InlineKeyboardButton(BTN_MP3, callback_data="act_mp3"),
            types.InlineKeyboardButton(BTN_VOICE, callback_data="act_voice"),
        )
    else:
        kb.add(
            types.InlineKeyboardButton(BTN_MP3, callback_data="act_mp3"),
            types.InlineKeyboardButton(BTN_VOICE, callback_data="act_voice"),
        )
    return kb


def run_ffmpeg(cmd: list):
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(res.stderr[-300:] if res.stderr else "ffmpeg error")


def prepare_trimmed_input(session: dict, chat_id: int) -> str:
    src_path = session["raw_path"]
    ext = session["ext"]
    trim = session.get("trim")
    if not trim:
        return src_path

    start_sec, end_sec = trim
    trimmed_path = f"trim_{chat_id}{ext}"
    cmd = [
        "ffmpeg", "-y",
        "-ss", str(start_sec),
        "-to", str(end_sec),
        "-i", src_path,
    ]
    if session["media_type"] == "video":
        cmd += ["-c:v", "libx264", "-preset", "ultrafast", "-crf", "24", "-c:a", "aac", "-b:a", "128k"]
    elif session["media_type"] == "audio":
        cmd += ["-c:a", "libmp3lame", "-b:a", "192k"]
    else:
        cmd += ["-c:a", "libopus", "-b:a", "64k"]

    cmd.append(trimmed_path)
    run_ffmpeg(cmd)
    session["extra_files"].append(trimmed_path)
    return trimmed_path


def process_and_send(chat_id: int, status_msg_id=None):
    session = user_sessions.get(chat_id)
    if not session:
        return

    if status_msg_id is None:
        s_msg = bot.send_message(chat_id, MSG_PROCESSING)
        status_msg_id = s_msg.message_id
    else:
        try:
            bot.edit_message_text(MSG_PROCESSING, chat_id, status_msg_id)
        except Exception:
            pass

    try:
        active_input = prepare_trimmed_input(session, chat_id)
        action = session["action"]

        if action == "act_bw":
            out_path = f"out_bw_{chat_id}.mp4"
            session["extra_files"].append(out_path)
            cmd = [
                "ffmpeg", "-y", "-i", active_input,
                "-vf", "hue=s=0",
                "-c:v", "libx264", "-preset", "ultrafast", "-crf", "24",
                "-c:a", "aac", "-b:a", "128k",
                out_path,
            ]
            run_ffmpeg(cmd)
            with open(out_path, "rb") as f:
                bot.send_video(chat_id, f, caption=MSG_DONE)

        elif action == "act_voice":
            out_path = f"out_voice_{chat_id}.ogg"
            session["extra_files"].append(out_path)
            cmd = [
                "ffmpeg", "-y", "-i", active_input,
                "-vn", "-c:a", "libopus", "-b:a", "64k",
                out_path,
            ]
            run_ffmpeg(cmd)
            with open(out_path, "rb") as f:
                bot.send_voice(chat_id, f, caption=MSG_DONE)

        elif action == "act_mp3":
            out_path = f"out_audio_{chat_id}.mp3"
            session["extra_files"].append(out_path)
            cover_path = session.get("cover_path")
            artist = session.get("artist")

            if cover_path and os.path.exists(cover_path):
                cmd = [
                    "ffmpeg", "-y",
                    "-i", active_input,
                    "-i", cover_path,
                    "-map", "0:a",
                    "-map", "1:v",
                    "-c:a", "libmp3lame", "-b:a", "192k",
                    "-c:v", "mjpeg",
                    "-disposition:v:0", "attached_pic",
                ]
            else:
                cmd = [
                    "ffmpeg", "-y",
                    "-i", active_input,
                    "-vn",
                    "-c:a", "libmp3lame", "-b:a", "192k",
                ]

            if artist:
                cmd += ["-metadata", f"artist={artist}", "-metadata", f"album_artist={artist}"]

            cmd.append(out_path)
            run_ffmpeg(cmd)

            thumb_arg = None
            if cover_path and os.path.exists(cover_path):
                thumb_arg = open(cover_path, "rb")

            try:
                with open(out_path, "rb") as f:
                    bot.send_audio(
                        chat_id,
                        f,
                        caption=MSG_DONE,
                        performer=artist if artist else None,
                        thumb=thumb_arg,
                    )
            finally:
                if thumb_arg:
                    thumb_arg.close()

        try:
            bot.delete_message(chat_id, status_msg_id)
        except Exception:
            pass

    except Exception:
        try:
            bot.edit_message_text(MSG_ERROR, chat_id, status_msg_id)
        except Exception:
            bot.send_message(chat_id, MSG_ERROR)

    finally:
        cleanup_session(chat_id)


def cleanup_session(chat_id: int):
    session = user_sessions.pop(chat_id, None)
    if not session:
        return
    for p in session.get("extra_files", []):
        if p and os.path.exists(p):
            try:
                os.remove(p)
            except Exception:
                pass
    raw_p = session.get("raw_path")
    if raw_p and os.path.exists(raw_p):
        try:
            os.remove(raw_p)
        except Exception:
            pass
    cov_p = session.get("cover_path")
    if cov_p and os.path.exists(cov_p):
        try:
            os.remove(cov_p)
        except Exception:
            pass


def start_media_flow(message, file_id: str, media_type: str, ext: str):
    chat_id = message.chat.id
    cleanup_session(chat_id)

    file_info = bot.get_file(file_id)
    downloaded = bot.download_file(file_info.file_path)
    raw_path = f"raw_{chat_id}{ext}"
    with open(raw_path, "wb") as f:
        f.write(downloaded)

    user_sessions[chat_id] = {
        "step": "ask_cut",
        "media_type": media_type,
        "ext": ext,
        "raw_path": raw_path,
        "extra_files": [],
        "trim": None,
        "action": None,
        "cover_path": None,
        "artist": None,
    }
    bot.reply_to(message, MSG_ASK_CUT, reply_markup=cut_keyboard())


@bot.message_handler(commands=["start"])
def send_welcome(message):
    bot.reply_to(message, MSG_WELCOME)


@bot.message_handler(content_types=["video"])
def on_video(message):
    start_media_flow(message, message.video.file_id, "video", ".mp4")


@bot.message_handler(content_types=["audio"])
def on_audio(message):
    ext = os.path.splitext(message.audio.file_name or "")[1].lower() or ".mp3"
    start_media_flow(message, message.audio.file_id, "audio", ext)


@bot.message_handler(content_types=["voice"])
def on_voice(message):
    start_media_flow(message, message.voice.file_id, "voice", ".ogg")


@bot.message_handler(content_types=["photo"])
def on_photo(message):
    chat_id = message.chat.id
    session = user_sessions.get(chat_id)
    if not session or session.get("step") != "waiting_cover":
        return

    file_id = message.photo[-1].file_id
    file_info = bot.get_file(file_id)
    downloaded = bot.download_file(file_info.file_path)
    cover_path = f"cover_{chat_id}.jpg"
    with open(cover_path, "wb") as f:
        f.write(downloaded)

    session["cover_path"] = cover_path
    session["step"] = "ask_artist"
    bot.send_message(chat_id, MSG_ASK_ARTIST, reply_markup=yes_no_keyboard("art"))


@bot.message_handler(func=lambda m: True, content_types=["text"])
def on_text(message):
    chat_id = message.chat.id
    session = user_sessions.get(chat_id)
    if not session:
        return

    step = session.get("step")
    text = (message.text or "").strip()

    if step == "waiting_range":
        try:
            session["trim"] = parse_trim_range(text)
            session["step"] = "choose_action"
            bot.send_message(chat_id, MSG_ASK_ACTION, reply_markup=action_keyboard(session["media_type"]))
        except Exception:
            bot.send_message(chat_id, MSG_ERROR)

    elif step == "waiting_artist":
        if not text:
            bot.send_message(chat_id, MSG_ERROR)
            return
        session["artist"] = text
        session["step"] = "processing"
        process_and_send(chat_id)


@bot.callback_query_handler(func=lambda call: True)
def on_callback(call):
    chat_id = call.message.chat.id
    data = call.data
    session = user_sessions.get(chat_id)

    if not session:
        bot.answer_callback_query(call.id, MSG_ERROR)
        return

    bot.answer_callback_query(call.id)

    if data == "cut_yes":
        session["step"] = "waiting_range"
        bot.send_message(chat_id, MSG_ASK_RANGE)

    elif data == "cut_no":
        session["trim"] = None
        session["step"] = "choose_action"
        bot.send_message(chat_id, MSG_ASK_ACTION, reply_markup=action_keyboard(session["media_type"]))

    elif data in ("act_bw", "act_mp3", "act_voice"):
        session["action"] = data
        if data == "act_mp3":
            session["step"] = "ask_cover"
            bot.send_message(chat_id, MSG_ASK_COVER, reply_markup=yes_no_keyboard("cov"))
        else:
            session["step"] = "processing"
            process_and_send(chat_id)

    elif data == "cov_yes":
        session["step"] = "waiting_cover"
        bot.send_message(chat_id, MSG_SEND_COVER)

    elif data == "cov_no":
        session["cover_path"] = None
        session["step"] = "ask_artist"
        bot.send_message(chat_id, MSG_ASK_ARTIST, reply_markup=yes_no_keyboard("art"))

    elif data == "art_yes":
        session["step"] = "waiting_artist"
        bot.send_message(chat_id, MSG_SEND_ARTIST)

    elif data == "art_no":
        session["artist"] = None
        session["step"] = "processing"
        process_and_send(chat_id)


bot.infinity_polling(skip_pending=True)
