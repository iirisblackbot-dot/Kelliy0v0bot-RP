"""
Telegram РП-бот с аниме-гифками (nekos.best API)
Автор: Manus AI
Версия: 3.3 (Имена вместо юзернеймов + Исправленные кнопки)
"""

import logging
import json
import os
import uuid
import asyncio
import aiohttp
import re
import sqlite3
from datetime import datetime

from telegram import (
    Update,
    InlineQueryResultGif,
    InlineQueryResultArticle,
    InputTextMessageContent,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    Application,
    CommandHandler,
    InlineQueryHandler,
    ContextTypes,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)
from telegram.constants import ParseMode

# ─── Конфигурация ────────────────────────────────────────────────────────────

BOT_TOKEN = "8730392854:AAFPgevHMNIKg-9K0Ow54OAQfvPY3ehoLAU" # @Kelliy0v0bot
DB_FILE = "bot_data.db"
CUSTOM_COMMANDS_FILE = "custom_commands.json"
NEKOS_API = "https://nekos.best/api/v2/"

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ─── База данных ─────────────────────────────────────────────────────────────

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS profiles (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            full_name TEXT,
            xp INTEGER DEFAULT 0,
            level INTEGER DEFAULT 1,
            rp_count INTEGER DEFAULT 0,
            partner_id INTEGER DEFAULT 0,
            marriage_date TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS last_targets (
            user_id INTEGER,
            target_id INTEGER,
            target_name TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (user_id)
        )
    ''')
    conn.commit()
    conn.close()

def get_profile(user_id, username=None, full_name=None):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM profiles WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    if not row:
        cursor.execute("INSERT INTO profiles (user_id, username, full_name) VALUES (?, ?, ?)", (user_id, username, full_name))
        conn.commit()
        cursor.execute("SELECT * FROM profiles WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
    elif username or full_name:
        cursor.execute("UPDATE profiles SET username = ?, full_name = ? WHERE user_id = ?", (username, full_name, user_id))
        conn.commit()
    conn.close()
    return {
        "user_id": row[0], "username": row[1], "full_name": row[2],
        "xp": row[3], "level": row[4], "rp_count": row[5],
        "partner_id": row[6], "marriage_date": row[7]
    }

def update_last_target(user_id, target_id, target_name):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("REPLACE INTO last_targets (user_id, target_id, target_name, timestamp) VALUES (?, ?, ?, CURRENT_TIMESTAMP)", (user_id, target_id, target_name))
    conn.commit()
    conn.close()

def get_last_target(user_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT target_id, target_name FROM last_targets WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return row if row else (0, None)

def add_xp(user_id, amount=10):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("UPDATE profiles SET xp = xp + ?, rp_count = rp_count + 1 WHERE user_id = ?", (amount, user_id))
    cursor.execute("SELECT xp, level FROM profiles WHERE user_id = ?", (user_id,))
    xp, level = cursor.fetchone()
    new_level = int(xp ** 0.5 / 5) + 1
    if new_level > level:
        cursor.execute("UPDATE profiles SET level = ? WHERE user_id = ?", (new_level, user_id))
        conn.commit()
        conn.close()
        return True, new_level
    conn.commit()
    conn.close()
    return False, level

def set_marriage(user1_id, user2_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    date = datetime.now().strftime("%Y-%m-%d")
    cursor.execute("UPDATE profiles SET partner_id = ?, marriage_date = ? WHERE user_id = ?", (user2_id, date, user1_id))
    cursor.execute("UPDATE profiles SET partner_id = ?, marriage_date = ? WHERE user_id = ?", (user1_id, date, user2_id))
    conn.commit()
    conn.close()

def divorce(user_id):
    profile = get_profile(user_id)
    partner_id = profile["partner_id"]
    if partner_id == 0: return False
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("UPDATE profiles SET partner_id = 0, marriage_date = NULL WHERE user_id = ?", (user_id,))
    cursor.execute("UPDATE profiles SET partner_id = 0, marriage_date = NULL WHERE user_id = ?", (partner_id,))
    conn.commit()
    conn.close()
    return True

# ─── Встроенные РП-команды ───────────────────────────────────────────────────

BUILTIN_COMMANDS: dict[str, tuple[str, str, str, str, str]] = {
    "hug":       ("hug",       "💞 {user} хочет обнять {target}!",          "💞 {user} обнимает всех вокруг!", "💞 {target} принял обнимашки от {user}!", "💔 {target} не хочет обниматься с {user}..."),
    "kiss":      ("kiss",      "💋 {user} хочет поцеловать {target}!",       "💋 {user} посылает воздушный поцелуй!", "💋 {target} ответил на поцелуй {user}!", "💔 {target} увернулся от поцелуя {user}..."),
    "slap":      ("slap",      "👋 {user} хочет дать пощёчину {target}!",    "👋 {user} бьёт по воздуху!", "👋 {user} получил пощёчину от {target}!", "🛡️ {target} заблокировал удар {user}!"),
    "pat":       ("pat",       "🤗 {user} хочет погладить {target}!",       "🤗 {user} нежно гладит кого-то!", "🤗 {target} довольно мурчит от поглаживаний {user}!", "🚫 {target} не дает {user} себя гладить."),
    "bite":      ("bite",      "😈 {user} хочет укусить {target}!",         "😈 {user} кусает воздух!", "😈 {user} укусил {target}!", "🛡️ {target} не дал {user} себя укусить!"),
    "cuddle":    ("cuddle",    "🥰 {user} хочет прижаться к {target}!",      "🥰 {user} ищет кого обнять!", "🥰 {target} прижался к {user} в ответ!", "💔 {target} отошел от {user}..."),
    "poke":      ("poke",      "👉 {user} хочет тыкнуть {target}!",         "👉 {user} тыкает в воздух!", "👉 {user} тыкнул {target}!", "🛡️ {target} перехватил палец {user}!"),
    "tickle":    ("tickle",    "😂 {user} хочет пощекотать {target}!",      "😂 {user} щекочет воздух!", "😂 {target} смеется от щекотки {user}!", "🚫 {target} не дает {user} себя щекотать."),
    "bonk":      ("bonk",      "🔨 {user} хочет бонкнуть {target}!",        "🔨 {user} бонкает в воздух!", "🔨 {user} бонкнул {target}!", "🛡️ {target} увернулся от бонка {user}!"),
    "baka":      ("baka",      "😤 {user} называет {target} бакой!",       "😤 {user} кричит «бака!»", "😤 {target} обиделся на {user}!", "😏 {target} проигнорировал {user}."),
    "blowkiss":  ("blowkiss",  "😘 {user} посылает поцелуй {target}!",     "😘 {user} посылает поцелуй в воздух!", "😘 {target} поймал поцелуй {user}!", "💨 Поцелуй {user} пролетел мимо {target}..."),
    "handhold":  ("handhold",  "🤝 {user} хочет взять {target} за руку!",    "🤝 {user} тянет руку!", "🤝 {target} взял {user} за руку!", "💔 {target} не дал {user} свою руку..."),
    "highfive":  ("highfive",  "🙌 {user} хочет дать пять {target}!",        "🙌 {user} поднимает руку для пятюни!", "🙌 {user} и {target} дали пять!", "💨 {user} остался с поднятой рукой..."),
    "feed":      ("feed",      "🍡 {user} хочет покормить {target}!",       "🍡 {user} ест что-то вкусное!", "😋 {target} съел угощение от {user}!", "🤢 {target} отказался от еды {user}."),
    "kick":      ("kick",      "🦵 {user} хочет пнуть {target}!",           "🦵 {user} пинает воздух!", "🦵 {user} пнул {target}!", "🛡️ {target} заблокировал пинок {user}!"),
    "punch":     ("punch",     "👊 {user} хочет ударить {target}!",         "👊 {user} бьёт кулаком в воздух!", "👊 {user} ударил {target}!", "🛡️ {target} увернулся от удара {user}!"),
    "yeet":      ("yeet",      "🚀 {user} хочет выкинуть {target}!",       "🚀 {user} выкидывает что-то!", "🚀 {user} выкинул {target}!", "🛡️ {target} крепко держится!"),
    "carry":     ("carry",     "💪 {user} хочет взять {target} на руки!",   "💪 {user} несёт кого-то!", "💪 {user} несет {target} на руках!", "🚫 {target} не хочет на ручки к {user}."),
    "kabedon":   ("kabedon",   "😳 {user} делает кабедон {target}!",       "😳 {user} делает кабедон!", "😳 {target} покраснел от кабедона {user}!", "😏 {target} просто пролез под рукой {user}."),
    "shake":     ("shake",     "🤝 {user} трясёт {target} за плечи!",      "🤝 {user} трясётся!", "🤝 {user} трясет {target}!", "🚫 {target} оттолкнул {user}."),
    "wave":      ("wave",      "👋 {user} машет {target}!",                "👋 {user} машет рукой!", "👋 {target} помахал {user} в ответ!", "😑 {target} проигнорировал {user}."),
    "peck":      ("peck",      "😙 {user} хочет чмокнуть {target}!",       "😙 {user} чмокает в воздух!", "😙 {user} чмокнул {target} в щечку!", "🛡️ {target} закрылся рукой!"),
    "stare":     ("stare",     "👀 {user} пристально смотрит на {target}!", "👀 {user} пристально смотрит!", "👀 {target} и {user} играют в гляделки!", "🙈 {target} отвернулся от {user}."),
    "wink":      ("wink",      "😉 {user} подмигивает {target}!",          "😉 {user} подмигивает!", "😉 {target} подмигнул {user} в ответ!", "😑 {target} сделал вид, что не заметил."),
    "blush":     ("blush",     "😊 {user} краснеет из-за {target}!",       "😊 {user} краснеет!", "😊 {user} и {target} оба покраснели!", "😏 {target} ухмыляется над {user}."),
    "smile":     ("smile",     "😊 {user} улыбается {target}!",            "😊 {user} улыбается!", "😊 {target} улыбнулся {user} в ответ!", "😑 {target} сохраняет серьезность."),
    "cry":       ("cry",       "😢 {user} плачет из-за {target}!",         "😢 {user} плачет!", "🫂 {target} утешает {user}!", "😑 {target} холодно смотрит на {user}."),
    "dance":     ("dance",     "💃 {user} приглашает {target} на танец!",    "💃 {user} танцует!", "💃 {user} и {target} танцуют вместе!", "🚫 {target} отказался танцевать с {user}."),
    "clap":      ("clap",      "👏 {user} аплодирует {target}!",           "👏 {user} аплодирует!", "👏 {target} кланяется {user}!", "😑 {target} проигнорировал овации {user}."),
    "nom":       ("nom",       "😋 {user} хочет укусить {target}!",         "😋 {user} ест что-то!", "😋 {user} кусает {target}! Ням!", "🛡️ {target} не дал себя съесть!"),
    "facepalm":  ("facepalm",  "🤦 {user} делает фейспалм из-за {target}!", "🤦 {user} делает фейспалм!", "🤦 {target} тоже делает фейспалм!", "😏 {target} смеется над {user}."),
    "handshake": ("handshake", "🤝 {user} протягивает руку {target}!",     "🤝 {user} протягивает руку!", "🤝 {user} и {target} пожали руки!", "🚫 {target} не пожал руку {user}."),
    "lappillow": ("lappillow", "😴 {user} хочет лечь на колени {target}!",  "😴 {user} ищет колени!", "😴 {user} уснул на коленях {target}!", "🚫 {target} скинул {user} с колен!"),
    "pout":      ("pout",      "😤 {user} дуется на {target}!",            "😤 {user} дуется!", "🫂 {target} пытается развеселить {user}!", "😏 {target} дразнит {user} еще больше."),
    "nod":       ("nod",       "😌 {user} кивает {target}!",               "😌 {user} кивает!", "😌 {target} кивнул {user} в ответ!", "😑 {target} не согласен с {user}."),
    "salute":    ("salute",    "🫡 {user} отдает честь {target}!",         "🫡 {user} отдает честь!", "🫡 {target} отдал честь {user}!", "😑 {target} не заметил приветствия."),
    "thumbsup":  ("thumbsup",  "👍 {user} одобряет действия {target}!",     "👍 {user} одобряет!", "🤝 {target} и {user} договорились!", "👎 {target} не согласен с {user}."),
    "laugh":     ("laugh",     "😂 {user} смеется над {target}!",          "😂 {user} смеется!", "😂 {target} смеется вместе с {user}!", "😠 {target} обиделся на смех {user}."),
    "spin":      ("spin",      "🌀 {user} хочет закружить {target}!",       "🌀 {user} кружится!", "🌀 {user} кружит {target}!", "🤢 {target} стало плохо от кружения!"),
    "run":       ("run",       "🏃 {user} убегает от {target}!",           "🏃 {user} убегает!", "🏃 {target} догнал {user}!", "💨 {user} скрылся из виду!"),
    "sleep":     ("sleep",     "💤 {user} хочет уснуть рядом с {target}!",  "💤 {user} засыпает!", "💤 {user} и {target} спят вместе!", "🚫 {target} выгнал {user} из кровати!"),
    "yawn":      ("yawn",      "🥱 {user} зевает при {target}!",           "🥱 {user} зевает!", "🥱 {target} тоже зевнул!", "😑 {target} смотрит на сонного {user}."),
    "smug":      ("smug",      "😏 {user} ухмыляется {target}!",           "😏 {user} ухмыляется!", "😏 {target} ухмыляется в ответ!", "😑 {target} не понимает шутки."),
    "think":     ("think",     "🤔 {user} думает о {target}!",             "🤔 {user} думает!", "🤔 {target} тоже задумался!", "😑 {target} прервал мысли {user}."),
    "happy":     ("happy",     "😄 {user} счастлив рядом с {target}!",    "😄 {user} счастлив!", "😄 {target} тоже рад видеть {user}!", "😑 {target} испортил настроение {user}."),
    "angry":     ("angry",     "😠 {user} злится на {target}!",            "😠 {user} злится!", "😠 {target} злится в ответ!", "🫂 {target} пытается успокоить {user}."),
    "shoot":     ("shoot",     "🔫 {user} целится в {target}!",            "🔫 {user} стреляет!", "🔫 {user} попал в {target}!", "🛡️ {target} увернулся от выстрела!"),
    "lurk":      ("lurk",      "🕵️ {user} следит за {target}!",            "🕵️ {user} наблюдает!", "😱 {target} заметил слежку {user}!", "😏 {user} остался незамеченным."),
    "confused":  ("confused",  "😕 {user} не понимает {target}!",          "😕 {user} в замешательстве!", "😕 {target} тоже ничего не понимает!", "💡 {target} все объяснил {user}."),
    "shrug":     ("shrug",     "🤷 {user} пожимает плечами при {target}!", "🤷 {user} пожимает плечами!", "🤷 {target} тоже не знает, что сказать.", "💡 {target} нашел решение!"),
    "wag":       ("wag",       "🐾 {user} виляет хвостом перед {target}!", "🐾 {user} виляет хвостом!", "😊 {target} погладил {user}!", "😑 {target} проигнорировал {user}."),
    "sip":       ("sip",       "☕ {user} пьёт чай с {target}!",           "☕ {user} пьёт чай!", "☕ {target} и {user} мило беседуют за чаем.", "🚫 {target} отказался от чая."),
    "teehee":    ("teehee",    "🤭 {user} хихикает над {target}!",         "🤭 {user} хихикает!", "🤭 {target} хихикает вместе с {user}!", "😠 {target} не видит ничего смешного."),
    "shocked":   ("shocked",   "😱 {user} в шоке от {target}!",            "😱 {user} шокирован!", "😱 {target} тоже в шоке!", "😏 {target} ожидал такой реакции."),
    "bleh":      ("bleh",      "😛 {user} показывает язык {target}!",      "😛 {user} показывает язык!", "😛 {target} показал язык в ответ!", "😑 {target} считает {user} ребенком."),
    "bored":     ("bored",     "😑 {user} скучает с {target}!",            "😑 {user} скучает!", "💡 {target} придумал развлечение!", "💤 {user} и {target} оба уснули от скуки."),
    "nya":       ("nya",       "🐱 {user} мяукает на {target}!",           "🐱 {user} мяукает!", "🐱 {target} мяукнул в ответ!", "😑 {target} не любит кошек."),
    "tableflip": ("tableflip", "😤 {user} переворачивает стол из-за {target}!", "😤 {user} переворачивает стол!", "😤 {target} перевернул еще один стол!", "🛡️ {target} поймал стол!"),
}

RUSSIAN_ALIASES: dict[str, str] = {
    "обнять": "hug", "обнимашки": "hug", "обнял": "hug",
    "поцеловать": "kiss", "чмок": "kiss", "поцелуй": "kiss",
    "ударить": "slap", "пощечина": "slap", "врезать": "slap",
    "погладить": "pat", "гладить": "pat",
    "укусить": "bite", "кусь": "bite",
    "прижаться": "cuddle", "обнимать": "cuddle",
    "тыкнуть": "poke", "тык": "poke",
    "щекотать": "tickle", "щекотка": "tickle",
    "бонк": "bonk", "ударить_битой": "bonk",
    "бака": "baka", "дурак": "baka",
    "воздушный_поцелуй": "blowkiss",
    "взять_за_руку": "handhold", "рука": "handhold",
    "дать_пять": "highfive", "пять": "highfive",
    "покормить": "feed", "еда": "feed",
    "пнуть": "kick", "пинок": "kick",
    "ударить_кулаком": "punch", "удар": "punch",
    "выкинуть": "yeet", "полет": "yeet",
    "на_ручки": "carry", "нести": "carry",
    "кабедон": "kabedon", "прижать_к_стене": "kabedon",
    "трясти": "shake",
    "помахать": "wave", "привет": "wave",
    "чмокнуть": "peck",
    "смотреть": "stare", "взгляд": "stare",
    "подмигнуть": "wink",
    "покраснеть": "blush", "смущение": "blush",
    "улыбнуться": "smile", "улыбка": "smile",
    "плакать": "cry", "слезы": "cry",
    "танцевать": "dance", "танец": "dance",
    "хлопать": "clap", "аплодисменты": "clap",
    "ням": "nom", "кушать": "nom",
    "фейспалм": "facepalm", "рукалицо": "facepalm",
    "рукопожатие": "handshake",
    "на_колени": "lappillow",
    "дуться": "pout", "обидеться": "pout",
    "кивнуть": "nod",
    "честь": "salute", "салют": "salute",
    "лайк": "thumbsup", "класс": "thumbsup",
    "смеяться": "laugh", "смех": "laugh",
    "кружиться": "spin",
    "бежать": "run", "убежать": "run",
    "спать": "sleep", "сон": "sleep",
    "зевать": "yawn",
    "ухмылка": "smug",
    "думать": "think",
    "радость": "happy", "счастье": "happy",
    "злиться": "angry", "злость": "angry",
    "стрелять": "shoot", "выстрел": "shoot",
    "следить": "lurk",
    "не_понимать": "confused",
    "хз": "shrug", "пожать_плечами": "shrug",
    "хвост": "wag",
    "чай": "sip", "пить": "sip",
    "хихикать": "teehee",
    "шок": "shocked",
    "язык": "bleh",
    "скука": "bored",
    "мяу": "nya",
    "стол": "tableflip",
}

# ─── Утилиты ─────────────────────────────────────────────────────────────────

def load_custom_commands() -> dict:
    if os.path.exists(CUSTOM_COMMANDS_FILE):
        with open(CUSTOM_COMMANDS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_custom_commands(data: dict) -> None:
    with open(CUSTOM_COMMANDS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

async def fetch_gif(endpoint: str) -> str | None:
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{NEKOS_API}{endpoint}", timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    results = data.get("results", [])
                    if results:
                        return results[0].get("url")
    except Exception as e:
        logger.warning(f"Ошибка при получении гифки ({endpoint}): {e}")
    return None

def get_user_name(user) -> str:
    """Возвращает Имя (Full Name) пользователя в виде ссылки."""
    full_name = user.full_name or user.first_name or "Аноним"
    # Экранируем спецсимволы Markdown
    full_name = full_name.replace("[", "\[").replace("]", "\]").replace("*", "\*").replace("_", "\_")
    return f"[{full_name}](tg://user?id={user.id})"

def get_target_info(update: Update) -> tuple[str | None, int]:
    """Возвращает (Имя_цели, ID_цели)."""
    msg = update.message
    if not msg: return None, 0
    
    if msg.reply_to_message and msg.reply_to_message.from_user:
        target = msg.reply_to_message.from_user
        name = get_user_name(target)
        update_last_target(msg.from_user.id, target.id, name)
        return name, target.id
        
    if msg.entities:
        for entity in msg.entities:
            if entity.type == "text_mention" and entity.user:
                name = get_user_name(entity.user)
                update_last_target(msg.from_user.id, entity.user.id, name)
                return name, entity.user.id
            elif entity.type == "mention":
                mention = msg.text[entity.offset:entity.offset + entity.length]
                update_last_target(msg.from_user.id, 0, mention)
                return mention, 0
    return None, 0

# ─── Меню и Кнопки ───────────────────────────────────────────────────────────

def get_main_menu_keyboard():
    keyboard = [
        [
            InlineKeyboardButton("💞 Обнять", callback_data="rp_hug"),
            InlineKeyboardButton("💋 Поцеловать", callback_data="rp_kiss"),
        ],
        [
            InlineKeyboardButton("👋 Пощёчина", callback_data="rp_slap"),
            InlineKeyboardButton("🤗 Погладить", callback_data="rp_pat"),
        ],
        [
            InlineKeyboardButton("🎭 Все РП-команд", callback_data="menu_rp_list"),
        ],
        [
            InlineKeyboardButton("✨ Инлайн-режим", switch_inline_query_current_chat=""),
        ],
        [
            InlineKeyboardButton("👤 Профиль", callback_data="menu_profile"),
            InlineKeyboardButton("💍 Свадьбы", callback_data="menu_marry_help"),
        ],
        [
            InlineKeyboardButton("📖 Помощь", callback_data="menu_help"),
            InlineKeyboardButton("⚙️ Мои команды", callback_data="menu_mycmds"),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_rp_list_keyboard(page=0):
    cmds = sorted(BUILTIN_COMMANDS.keys())
    per_page = 12
    total_pages = (len(cmds) - 1) // per_page + 1
    page = page % total_pages
    current_cmds = cmds[page*per_page : (page+1)*per_page]
    keyboard = []
    for i in range(0, len(current_cmds), 3):
        row = [InlineKeyboardButton(f"/{c}", callback_data=f"rp_{c}") for c in current_cmds[i:i+3]]
        keyboard.append(row)
    nav_row = []
    if total_pages > 1:
        nav_row.append(InlineKeyboardButton("⬅️", callback_data=f"page_{page-1}"))
        nav_row.append(InlineKeyboardButton(f"{page+1}/{total_pages}", callback_data="ignore"))
        nav_row.append(InlineKeyboardButton("➡️", callback_data=f"page_{page+1}"))
        keyboard.append(nav_row)
    keyboard.append([InlineKeyboardButton("🔙 Назад в меню", callback_data="menu_main")])
    return InlineKeyboardMarkup(keyboard)

def get_rp_action_keyboard(user_id, target_id, cmd_name):
    # Используем уникальный ID для каждой сессии кнопки, чтобы избежать конфликтов
    session_id = str(uuid.uuid4())[:8]
    keyboard = [
        [
            InlineKeyboardButton("✅ Принять", callback_data=f"acc_{user_id}_{target_id}_{cmd_name}_{session_id}"),
            InlineKeyboardButton("❌ Отклонить", callback_data=f"dec_{user_id}_{target_id}_{cmd_name}_{session_id}"),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

# ─── Обработчики команд ───────────────────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    get_profile(user.id, user.username, user.full_name)
    text = (
        f"👋 *Привет, {user.first_name}! Я РП-бот @Kelliy0v0bot!*\n\n"
        "Я помогу тебе выразить эмоции с помощью аниме-гифк.\n"
        "Используй кнопки ниже или пиши команды в чат!"
    )
    await update.message.reply_text(text, reply_markup=get_main_menu_keyboard(), parse_mode=ParseMode.MARKDOWN)

async def cmd_profile(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    p = get_profile(user.id, user.username, user.full_name)
    partner_text = "Нет"
    if p["partner_id"] != 0:
        partner = get_profile(p["partner_id"])
        partner_text = f"{partner['full_name']} (с {p['marriage_date']})"
    
    text = (
        f"👤 *Профиль: {p['full_name']}*\n\n"
        f"📊 *Уровень:* {p['level']}\n"
        f"✨ *Опыт:* {p['xp']}\n"
        f"🎭 *РП-действий:* {p['rp_count']}\n"
        f"💍 *В браке с:* {partner_text}"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

async def cmd_marry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    msg = update.message
    if not msg.reply_to_message or msg.reply_to_message.from_user.id == user.id:
        await msg.reply_text("❌ Ответьте на сообщение того, кому хотите сделать предложение!")
        return
    
    target = msg.reply_to_message.from_user
    if target.is_bot:
        await msg.reply_text("❌ Нельзя жениться на ботах!")
        return
    
    p1 = get_profile(user.id, user.username, user.full_name)
    p2 = get_profile(target.id, target.username, target.full_name)
    
    if p1["partner_id"] != 0:
        await msg.reply_text("❌ Вы уже в браке! Сначала разведитесь.")
        return
    if p2["partner_id"] != 0:
        await msg.reply_text("❌ Этот пользователь уже в браке!")
        return
    
    keyboard = [[
        InlineKeyboardButton("✅ Согласен", callback_data=f"m_acc_{user.id}_{target.id}"),
        InlineKeyboardButton("❌ Отказ", callback_data=f"m_dec_{user.id}_{target.id}")
    ]]
    await msg.reply_text(
        f"💍 {get_user_name(user)} делает предложение {get_user_name(target)}!\n\nВы согласны?",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN
    )

async def cmd_divorce(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if divorce(user.id):
        await update.message.reply_text("💔 Вы развелись... Теперь вы свободны.")
    else:
        await update.message.reply_text("❌ Вы не состоите в браке.")

async def cmd_add_custom(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if len(context.args) < 2:
        await update.message.reply_text("❌ `/addcmd <команда> <текст>`")
        return
    cmd_name = context.args[0].lower().strip("/")
    cmd_text = " ".join(context.args[1:])
    if cmd_name in BUILTIN_COMMANDS:
        await update.message.reply_text("❌ Команда уже существует!")
        return
    custom = load_custom_commands()
    user_id = str(update.effective_user.id)
    if user_id not in custom: custom[user_id] = {}
    custom[user_id][cmd_name] = cmd_text
    save_custom_commands(custom)
    await update.message.reply_text(f"✅ Команда `/{cmd_name}` добавлена!")

# ─── Обработчик Callback (кнопок) ─────────────────────────────────────────────

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    data = query.data
    user = query.from_user
    
    if data.startswith(("acc_", "dec_")):
        parts = data.split("_")
        action = parts[0]
        initiator_id = int(parts[1])
        target_id = int(parts[2])
        cmd_name = parts[3]
        
        # Если target_id == 0, значит цель не была указана, принять может любой
        if target_id != 0 and user.id != target_id:
            await query.answer("❌ Это действие направлено не вам!", show_alert=True)
            return
        
        await query.answer()
        
        # Получаем инициатора
        try:
            initiator = await context.bot.get_chat(initiator_id)
            initiator_name = get_user_name(initiator)
        except:
            initiator_name = "Пользователь"
            
        target_name = get_user_name(user)
        
        _, _, _, accepted_tpl, declined_tpl = BUILTIN_COMMANDS[cmd_name]
        new_text = accepted_tpl.format(user=initiator_name, target=target_name) if action == "acc" else declined_tpl.format(user=initiator_name, target=target_name)
        
        if action == "acc":
            add_xp(initiator_id, 15)
            add_xp(user.id, 5)
            
        if query.message.caption:
            await query.edit_message_caption(caption=new_text, parse_mode=ParseMode.MARKDOWN, reply_markup=None)
        else:
            await query.edit_message_text(text=new_text, parse_mode=ParseMode.MARKDOWN, reply_markup=None)
        return

    if data.startswith(("m_acc_", "m_dec_")):
        parts = data.split("_")
        action = parts[1]
        proposer_id = int(parts[2])
        target_id = int(parts[3])
        
        if user.id != target_id:
            await query.answer("❌ Это предложение не вам!", show_alert=True)
            return
        
        await query.answer()
        try:
            proposer = await context.bot.get_chat(proposer_id)
            proposer_name = get_user_name(proposer)
        except:
            proposer_name = "Пользователь"
            
        if action == "acc":
            set_marriage(proposer_id, target_id)
            await query.edit_message_text(f"🎉 Поздравляем! {proposer_name} и {get_user_name(user)} теперь в браке! 💍", parse_mode=ParseMode.MARKDOWN)
        else:
            await query.edit_message_text(f"💔 {get_user_name(user)} отклонил предложение {proposer_name}...", parse_mode=ParseMode.MARKDOWN)
        return

    await query.answer()
    if data == "menu_main":
        await query.edit_message_text("👋 *Главное меню РП-бота*\n\nВыбери действие:", reply_markup=get_main_menu_keyboard(), parse_mode=ParseMode.MARKDOWN)
    elif data == "menu_profile":
        p = get_profile(user.id, user.username, user.full_name)
        partner_text = "Нет"
        if p["partner_id"] != 0:
            partner = get_profile(p["partner_id"])
            partner_text = f"{partner['full_name']}"
        text = (
            f"👤 *Профиль: {p['full_name']}*\n\n"
            f"📊 *Уровень:* {p['level']}\n"
            f"✨ *Опыт:* {p['xp']}\n"
            f"🎭 *РП-действий:* {p['rp_count']}\n"
            f"💍 *В браке с:* {partner_text}"
        )
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 В меню", callback_data="menu_main")]]), parse_mode=ParseMode.MARKDOWN)
    elif data == "menu_rp_list":
        await query.edit_message_text("🎭 *Список РП-команд:*\nНажми на кнопку, чтобы выполнить действие!", reply_markup=get_rp_list_keyboard(0), parse_mode=ParseMode.MARKDOWN)
    elif data.startswith("page_"):
        page = int(data.split("_")[1])
        await query.edit_message_text("🎭 *Список РП-команд:*\nНажми на кнопку, чтобы выполнить действие!", reply_markup=get_rp_list_keyboard(page), parse_mode=ParseMode.MARKDOWN)
    elif data.startswith("rp_"):
        cmd_name = data.split("_")[1]
        endpoint, _, text_without, _, _ = BUILTIN_COMMANDS[cmd_name]
        caption = text_without.format(user=get_user_name(user))
        gif_url = await fetch_gif(endpoint)
        add_xp(user.id, 10)
        if gif_url:
            await query.message.reply_animation(animation=gif_url, caption=caption, parse_mode=ParseMode.MARKDOWN)
        else:
            await query.message.reply_text(caption, parse_mode=ParseMode.MARKDOWN)
    elif data == "menu_marry_help":
        await query.edit_message_text("💍 *Свадьбы*\n\nЧтобы сделать предложение, ответьте на сообщение пользователя командой `/marry`.\nЧтобы развестись, напишите `/divorce`.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 В меню", callback_data="menu_main")]]), parse_mode=ParseMode.MARKDOWN)

# ─── Обработчики РП ──────────────────────────────────────────────────────────

async def handle_rp_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message
    if not msg or not msg.text: return
    cmd_name = msg.text.split()[0].lstrip("/").split("@")[0].lower()
    user = msg.from_user
    user_name = get_user_name(user)
    target_name, target_id = get_target_info(update)
    
    get_profile(user.id, user.username, user.full_name)
    
    if cmd_name in BUILTIN_COMMANDS:
        endpoint, text_with, text_without, _, _ = BUILTIN_COMMANDS[cmd_name]
        caption = text_with.format(user=user_name, target=target_name) if target_name else text_without.format(user=user_name)
        gif_url = await fetch_gif(endpoint)
        leveled_up, new_level = add_xp(user.id, 10)
        if leveled_up:
            await msg.reply_text(f"🆙 {user_name}, твой уровень повышен до **{new_level}**!", parse_mode=ParseMode.MARKDOWN)
        
        if gif_url:
            await msg.reply_animation(animation=gif_url, caption=caption, parse_mode=ParseMode.MARKDOWN)
        else:
            await msg.reply_text(caption, parse_mode=ParseMode.MARKDOWN)
        return
    
    custom = load_custom_commands()
    user_cmds = custom.get(str(user.id), {})
    if cmd_name in user_cmds:
        template = user_cmds[cmd_name]
        caption = template.format(user=user_name, target=target_name or "всех")
        add_xp(user.id, 5)
        await msg.reply_text(caption, parse_mode=ParseMode.MARKDOWN)

# ─── Инлайн-режим ────────────────────────────────────────────────────────────

async def inline_query(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.inline_query
    query_text = query.query.strip().lower()
    user = query.from_user
    user_name = get_user_name(user)
    results = []
    
    parts = query_text.split(None, 1)
    cmd_query = parts[0] if parts else ""
    target_input = parts[1] if len(parts) > 1 else None
    
    mapped_cmd = RUSSIAN_ALIASES.get(cmd_query, cmd_query)
    
    # Авто-определение ника
    last_target_id, last_target_name = get_last_target(user.id)
    
    commands_to_show = [c for c in BUILTIN_COMMANDS if c.startswith(mapped_cmd)][:10] if mapped_cmd else list(BUILTIN_COMMANDS.keys())[:10]
    
    for cmd_name in commands_to_show:
        endpoint, text_with, text_without, _, _ = BUILTIN_COMMANDS[cmd_name]
        gif_url = await fetch_gif(endpoint)
        if not gif_url: continue
        
        # 1. Вариант БЕЗ цели
        results.append(InlineQueryResultGif(
            id=f"{cmd_name}_all_{uuid.uuid4()}",
            gif_url=gif_url,
            thumbnail_url=gif_url,
            title=f"/{cmd_name} (для всех)",
            caption=text_without.format(user=user_name),
            reply_markup=get_rp_action_keyboard(user.id, 0, cmd_name),
            parse_mode=ParseMode.MARKDOWN
        ))
        
        # 2. Вариант с АВТО-подстановкой
        if last_target_name and not target_input:
            results.append(InlineQueryResultGif(
                id=f"{cmd_name}_auto_{uuid.uuid4()}",
                gif_url=gif_url,
                thumbnail_url=gif_url,
                title=f"/{cmd_name} для {last_target_name} (авто)",
                caption=text_with.format(user=user_name, target=last_target_name),
                reply_markup=get_rp_action_keyboard(user.id, last_target_id, cmd_name),
                parse_mode=ParseMode.MARKDOWN
            ))
        
        # 3. Вариант с РУЧНЫМ вводом
        if target_input:
            results.append(InlineQueryResultGif(
                id=f"{cmd_name}_manual_{uuid.uuid4()}",
                gif_url=gif_url,
                thumbnail_url=gif_url,
                title=f"/{cmd_name} для {target_input}",
                caption=text_with.format(user=user_name, target=target_input),
                reply_markup=get_rp_action_keyboard(user.id, 0, cmd_name),
                parse_mode=ParseMode.MARKDOWN
            ))
            
    await query.answer(results, cache_time=1, is_personal=True)

# ─── Запуск ──────────────────────────────────────────────────────────────────

def main() -> None:
    init_db()
    app = Application.builder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("profile", cmd_profile))
    app.add_handler(CommandHandler("marry", cmd_marry))
    app.add_handler(CommandHandler("divorce", cmd_divorce))
    app.add_handler(CommandHandler("addcmd", cmd_add_custom))
    app.add_handler(CallbackQueryHandler(handle_callback))
    
    for cmd in BUILTIN_COMMANDS:
        app.add_handler(CommandHandler(cmd, handle_rp_command))
    
    app.add_handler(MessageHandler(filters.COMMAND, handle_rp_command))
    app.add_handler(InlineQueryHandler(inline_query))
    
    logger.info("Бот v3.3 запущен!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
