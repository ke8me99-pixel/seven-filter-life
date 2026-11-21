import json
import os
import re
import subprocess
import telebot
from telebot import types

BOT_TOKEN = os.getenv("BOT_TOKEN", "9114458150:AAHpOOt4Hy0BFjVSjRNaC0OdyYHYnUYo4hQ")
ALLOWED_USER_ID = 1343392055

# مفاتيح/روابط خدمات خارجية اختيارية في Railway (تُضاف في Variables عند الحاجة)
STT_API_URL = os.getenv("STT_API_URL", "").strip()
SONG_RECOGNIZE_API_URL = os.getenv("SONG_RECOGNIZE_API_URL", "").strip()
VOCALS_API_URL = os.getenv("VOCALS_API_URL", "").strip()
LYRICS_API_URL = os.getenv("LYRICS_API_URL", "").strip()

bot = telebot.TeleBot(BOT_TOKEN)

MSG_WELCOME = "𝖜𝖊𝖑𝖈𝖔𝖒𝖊 𝖜𝖎𝖙𝖍 𝖘𝖊𝟕𝖊𝖓"
MSG_ASK_CUT = "𝖈𝖚𝖙?"
MSG_ASK_RANGE = "00:00 to 00:17"
MSG_ASK_ACTION = "𝖈𝖍𝖔𝖔𝖘𝖊"
MSG_ASK_COVER = "𝖈𝖔𝖛𝖊𝖗"
MSG_SEND_COVER = "𝖘𝖊𝖓𝖉 𝖕𝖍𝖔𝖙𝖔"
MSG_ASK_ARTIST = "𝖆𝖗𝖙𝖎𝖘𝖙"
MSG_SEND_ARTIST = "𝖘𝖊𝖓𝖉 𝖓𝖆𝖒𝖊"
MSG_ASK_RENAME = "𝖗𝖊𝖓𝖆𝖒𝖊?"
MSG_SEND_FILENAME = "𝖘𝖊𝖓𝖉 𝖋𝖎𝖑𝖊 𝖓𝖆𝖒𝖊"
MSG_PROCESSING = "𝖕𝖗𝖔𝖈𝖊𝖘𝖘𝖎𝖓𝖌..."
MSG_DONE = "𝖉𝖔𝖓𝖊 𝖇𝖆𝖇𝖊"
MSG_ERROR = "𝖊𝖗𝖗𝖔𝖗 𝖇𝖆𝖇𝖊"

BTN_YES = "𝖞𝖊𝖘"
BTN_NO = "𝖓𝖔"
BTN_CUT_ONLY = "𝖈𝖚𝖙 𝖔𝖓𝖑𝖞"
BTN_FILTER = "𝖋𝖎𝖑𝖙𝖊𝖗"
BTN_MP3 = "𝖒𝖕3"
BTN_VOICE = "𝖛𝖔𝖎𝖈𝖊"

BTN_STT = "𝖘𝖙𝖙"
BTN_FIND_SONG = "𝖋𝖎𝖓𝖉"
BTN_VOCALS_ONLY = "𝖛𝖔𝖈𝖆𝖑𝖘"
BTN_LYRICS_ONLY = "𝖑𝖞𝖗𝖎𝖈𝖘"

BTN_KEEP = "𝖐𝖊𝖊𝖕"
BTN_CHANGE = "𝖈𝖍𝖆𝖓𝖌𝖊"
BTN_REMOVE = "𝖗𝖊𝖒𝖔𝖛𝖊"

user_sessions = {}


def is_allowed(user_id) -> bool:
    return user_id == ALLOWED_USER_ID


def sanitize_filename(name: str) -> str:
    cleaned = re.sub(r'[\\/*?:"<>|\r\n]+', "_", name).strip()
    cleaned = re.sub(r"\.(mp3|m4a|ogg|aac|wav|mp4)$", "", cleaned, flags=re.IGNORECASE).strip()
    return cleaned or "audio"


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
    kb = types.InlineKeyboardMarkup(row_width=3)
    kb.add(
        types.InlineKeyboardButton(BTN_YES, callback_data="cut_yes"),
        types.InlineKeyboardButton(BTN_NO, callback_data="cut_no"),
        types.InlineKeyboardButton(BTN_CUT_ONLY, callback_data="cut_only"),
    )
    return kb


def yes_no_keyboard(prefix: str):
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton(BTN_YES, callback_data=f"{prefix}_yes"),
        types.InlineKeyboardButton(BTN_NO, callback_data=f"{prefix}_no"),
    )
    return kb


def keep_change_remove_keyboard(prefix: str):
    kb = types.InlineKeyboardMarkup(row_width=3)
    kb.add(
        types.InlineKeyboardButton(BTN_KEEP, callback_data=f"{prefix}_keep"),
        types.InlineKeyboardButton(BTN_CHANGE, callback_data=f"{prefix}_change"),
        types.InlineKeyboardButton(BTN_REMOVE, callback_data=f"{prefix}_remove"),
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

    kb.add(
        types.InlineKeyboardButton(BTN_STT, callback_data="act_stt"),
        types.InlineKeyboardButton(BTN_FIND_SONG, callback_data="act_find"),
    )
    kb.add(
        types.InlineKeyboardButton(BTN_VOCALS_ONLY, callback_data="act_vocals"),
        types.InlineKeyboardButton(BTN_LYRICS_ONLY, callback_data="act_lyrics"),
    )
    return kb


def run_ffmpeg(cmd: list):
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(res.stderr[-300:] if res.stderr else "ffmpeg error")


def probe_tags_and_cover(src_path: str, chat_id: int):
    meta = {"artist": None, "title": None, "extracted_cover": None}
    try:
        probe = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", src_path],
            capture_output=True,
            text=True,
        )
        if probe.returncode == 0 and probe.stdout:
            data = json.loads(probe.stdout)
            tags = (data.get("format") or {}).get("tags") or {}
            lower_tags = {k.lower(): v for k, v in tags.items()}
            meta["artist"] = lower_tags.get("artist") or lower_tags.get("album_artist")
            meta["title"] = lower_tags.get("title")
    except Exception:
        pass

    cov_out = f"orig_cov_{chat_id}.jpg"
    ext_res = subprocess.run(
        ["ffmpeg", "-y", "-i", src_path, "-an", "-c:v", "mjpeg", "-frames:v", "1", cov_out],
        capture_output=True,
        text=True,
    )
    if ext_res.returncode == 0 and os.path.exists(cov_out) and os.path.getsize(cov_out) > 0:
        meta["extracted_cover"] = cov_out
    else:
        if os.path.exists(cov_out):
            try:
                os.remove(cov_out)
            except Exception:
                pass
    return meta


def trim_media_file(src_path: str, dst_path: str, media_type: str, start_sec: float, end_sec: float, preserve_meta: bool = False):
    cmd = [
        "ffmpeg", "-y",
        "-i", src_path,
        "-ss", str(start_sec),
        "-to", str(end_sec),
    ]
    if preserve_meta:
        cmd += ["-map_metadata", "0"]

    if media_type == "video":
        cmd += ["-c:v", "libx264", "-preset", "ultrafast", "-crf", "24", "-c:a", "aac", "-b:a", "128k"]
    elif media_type == "voice":
        cmd += ["-c:a", "libopus", "-b:a", "64k"]
    else:
        if preserve_meta:
            cmd += ["-map", "0:a", "-map", "0:v?"]
        if dst_path.lower().endswith(".ogg"):
            cmd += ["-c:a", "libopus", "-b:a", "64k"]
        elif dst_path.lower().endswith(".m4a") or dst_path.lower().endswith(".aac"):
            cmd += ["-c:a", "aac", "-b:a", "192k"]
        else:
            cmd += ["-c:a", "libmp3lame", "-b:a", "192k"]
        if preserve_meta:
            cmd += ["-c:v", "mjpeg", "-disposition:v:0", "attached_pic"]

    cmd.append(dst_path)
    run_ffmpeg(cmd)


def extract_temp_mp3(src_path: str, dst_mp3: str):
    cmd = [
        "ffmpeg", "-y",
        "-i", src_path,
        "-vn",
        "-c:a", "libmp3lame", "-b:a", "192k",
        dst_mp3,
    ]
    run_ffmpeg(cmd)


def handle_text_feature(chat_id: int, action: str, active_input: str, session: dict):
    # يحضّر ملف صوتي مؤقت إذا احتاجت الخدمة الصوت مباشرة
    temp_audio = f"feat_{chat_id}.mp3"
    extract_temp_mp3(active_input, temp_audio)
    session["extra_files"].append(temp_audio)

    if action == "act_stt":
        if not STT_API_URL:
            raise RuntimeError("STT_API_URL not configured")
        raise RuntimeError("STT endpoint not wired")

    elif action == "act_find":
        if not SONG_RECOGNIZE_API_URL:
            raise RuntimeError("SONG_RECOGNIZE_API_URL not configured")
        raise RuntimeError("Song recognition endpoint not wired")

    elif action == "act_vocals":
        if not VOCALS_API_URL:
            raise RuntimeError("VOCALS_API_URL not configured")
        raise RuntimeError("Vocals extraction endpoint not wired")

    elif action == "act_lyrics":
        if not LYRICS_API_URL:
            raise RuntimeError("LYRICS_API_URL not configured")
        raise RuntimeError("Lyrics endpoint not wired")


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
        raw_path = session["raw_path"]
        media_type = session["media_type"]
        ext = session["ext"]
        action = session["action"]
        trim = session.get("trim")
        custom_name = session.get("custom_name")

        orig_meta = probe_tags_and_cover(raw_path, chat_id)
        if orig_meta.get("extracted_cover"):
            session["extra_files"].append(orig_meta["extracted_cover"])

        orig_artist = session.get("orig_performer") or orig_meta.get("artist")
        orig_title = session.get("orig_title") or orig_meta.get("title")
        orig_cover = orig_meta.get("extracted_cover")

        if action == "cut_only":
            if not trim:
                raise ValueError("Missing trim range")
            start_sec, end_sec = trim
            base_out = f"cut_only_{chat_id}{ext}"
            trim_media_file(raw_path, base_out, media_type, start_sec, end_sec, preserve_meta=True)
            session["extra_files"].append(base_out)

            final_path = base_out
            if custom_name:
                final_path = f"{custom_name}{ext}"
                os.replace(base_out, final_path)
                session["extra_files"].append(final_path)

            thumb_arg = open(orig_cover, "rb") if (orig_cover and os.path.exists(orig_cover)) else None
            try:
                with open(final_path, "rb") as f:
                    if media_type == "video":
                        bot.send_video(chat_id, f, caption=MSG_DONE)
                    elif media_type == "voice":
                        bot.send_voice(chat_id, f, caption=MSG_DONE)
                    else:
                        bot.send_audio(
                            chat_id,
                            f,
                            caption=MSG_DONE,
                            title=custom_name if custom_name else orig_title,
                            performer=orig_artist,
                            thumb=thumb_arg,
                        )
            finally:
                if thumb_arg:
                    thumb_arg.close()

        else:
            active_input = raw_path
            if trim:
                start_sec, end_sec = trim
                trimmed_path = f"trim_{chat_id}{ext}"
                trim_media_file(raw_path, trimmed_path, media_type, start_sec, end_sec, preserve_meta=(media_type == "audio"))
                session["extra_files"].append(trimmed_path)
                active_input = trimmed_path

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
                if custom_name:
                    renamed_path = f"{custom_name}.mp4"
                    os.replace(out_path, renamed_path)
                    session["extra_files"].append(renamed_path)
                    out_path = renamed_path
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
                if custom_name:
                    renamed_path = f"{custom_name}.ogg"
                    os.replace(out_path, renamed_path)
                    session["extra_files"].append(renamed_path)
                    out_path = renamed_path
                with open(out_path, "rb") as f:
                    bot.send_voice(chat_id, f, caption=MSG_DONE)

            elif action == "act_mp3":
                temp_mp3 = f"out_audio_{chat_id}.mp3"
                session["extra_files"].append(temp_mp3)

                cover_mode = session.get("cover_mode", "keep")
                cover_path = session.get("cover_path")
                artist_mode = session.get("artist_mode", "keep")
                artist_name = session.get("artist_name")

                effective_cover = None
                if cover_mode == "change" and cover_path and os.path.exists(cover_path):
                    effective_cover = cover_path
                elif cover_mode == "keep" and orig_cover and os.path.exists(orig_cover):
                    effective_cover = orig_cover

                if effective_cover:
                    cmd = [
                        "ffmpeg", "-y",
                        "-i", active_input,
                        "-i", effective_cover,
                        "-map", "0:a",
                        "-map", "1:v",
                        "-map_metadata", "0",
                        "-c:a", "libmp3lame", "-b:a", "192k",
                        "-c:v", "mjpeg",
                        "-disposition:v:0", "attached_pic",
                    ]
                else:
                    cmd = [
                        "ffmpeg", "-y",
                        "-i", active_input,
                        "-vn",
                        "-map_metadata", "0",
                        "-c:a", "libmp3lame", "-b:a", "192k",
                    ]

                final_artist = None
                if artist_mode == "change" and artist_name:
                    final_artist = artist_name
                    cmd += ["-metadata", f"artist={final_artist}", "-metadata", f"album_artist={final_artist}"]
                elif artist_mode == "keep" and orig_artist:
                    final_artist = orig_artist
                    cmd += ["-metadata", f"artist={final_artist}", "-metadata", f"album_artist={final_artist}"]
                elif artist_mode == "remove":
                    final_artist = None
                    cmd += ["-metadata", "artist=", "-metadata", "album_artist="]

                final_title = custom_name if custom_name else orig_title
                if final_title:
                    cmd += ["-metadata", f"title={final_title}"]

                cmd.append(temp_mp3)
                run_ffmpeg(cmd)

                final_mp3 = temp_mp3
                if custom_name:
                    final_mp3 = f"{custom_name}.mp3"
                    os.replace(temp_mp3, final_mp3)
                    session["extra_files"].append(final_mp3)

                thumb_arg = open(effective_cover, "rb") if effective_cover else None

                try:
                    with open(final_mp3, "rb") as f:
                        bot.send_audio(
                            chat_id,
                            f,
                            caption=MSG_DONE,
                            title=final_title,
                            performer=final_artist,
                            thumb=thumb_arg,
                        )
                finally:
                    if thumb_arg:
                        thumb_arg.close()

            elif action in ("act_stt", "act_find", "act_vocals", "act_lyrics"):
                handle_text_feature(chat_id, action, active_input, session)

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


def start_media_flow(message, file_id: str, media_type: str, ext: str, orig_performer=None, orig_title=None):
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
        "cover_mode": "keep",
        "cover_path": None,
        "artist_mode": "keep",
        "artist_name": None,
        "custom_name": None,
        "orig_performer": orig_performer,
        "orig_title": orig_title,
    }
    bot.reply_to(message, MSG_ASK_CUT, reply_markup=cut_keyboard())


@bot.message_handler(commands=["start"])
def send_welcome(message):
    if not message.from_user or not is_allowed(message.from_user.id):
        return
    bot.reply_to(message, MSG_WELCOME)


@bot.message_handler(content_types=["video"])
def on_video(message):
    if not message.from_user or not is_allowed(message.from_user.id):
        return
    start_media_flow(message, message.video.file_id, "video", ".mp4")


@bot.message_handler(content_types=["audio"])
def on_audio(message):
    if not message.from_user or not is_allowed(message.from_user.id):
        return
    ext = os.path.splitext(message.audio.file_name or "")[1].lower() or ".mp3"
    start_media_flow(
        message,
        message.audio.file_id,
        "audio",
        ext,
        orig_performer=message.audio.performer,
        orig_title=message.audio.title,
    )


@bot.message_handler(content_types=["voice"])
def on_voice(message):
    if not message.from_user or not is_allowed(message.from_user.id):
        return
    start_media_flow(message, message.voice.file_id, "voice", ".ogg")


@bot.message_handler(content_types=["photo"])
def on_photo(message):
    if not message.from_user or not is_allowed(message.from_user.id):
        return
    chat_id = message.chat.id
    session = user_sessions.get(chat_id)
    
