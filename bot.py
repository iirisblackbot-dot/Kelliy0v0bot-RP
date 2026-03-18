
"""
Telegram РП-бот с аниме-гифками (nekos.best API)
Автор: Manus AI
Версия: 4.0 (Исправление ошибок и оптимизация)
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
    error as telegram_error,
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
    with sqlite3.connect(DB_FILE) as conn:
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

def get_profile(user_id, username=None, full_name=None):
    with sqlite3.connect(DB_FILE) as conn:
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
        return {
            "user_id": row[0], "username": row[1], "full_name": row[2],
            "xp": row[3], "level": row[4], "rp_count": row[5],
            "partner_id": row[6], "marriage_date": row[7]
        }

def update_last_target(user_id, target_id, target_name):
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("REPLACE INTO last_targets (user_id, target_id, target_name, timestamp) VALUES (?, ?, ?, CURRENT_TIMESTAMP)", (user_id, target_id, target_name))
        conn.commit()

def get_last_target(user_id):
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT target_id, target_name FROM last_targets WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        return row if row else (0, None)

def add_xp(user_id, amount=10):
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE profiles SET xp = xp + ?, rp_count = rp_count + 1 WHERE user_id = ?", (amount, user_id))
        cursor.execute("SELECT xp, level FROM profiles WHERE user_id = ?", (user_id,))
        xp, level = cursor.fetchone()
        new_level = int(xp ** 0.5 / 5) + 1
        if new_level > level:
            cursor.execute("UPDATE profiles SET level = ? WHERE user_id = ?", (new_level, user_id))
            conn.commit()
            return True, new_level
        conn.commit()
        return False, level

def set_marriage(user1_id, user2_id):
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        date = datetime.now().strftime("%Y-%m-%d")
        cursor.execute("UPDATE profiles SET partner_id = ?, marriage_date = ? WHERE user_id = ?", (user2_id, date, user1_id))
        cursor.execute("UPDATE profiles SET partner_id = ?, marriage_date = ? WHERE user_id = ?", (user1_id, date, user2_id))
        conn.commit()

def divorce(user_id):
    profile = get_profile(user_id)
    partner_id = profile["partner_id"]
    if partner_id == 0: return False
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE profiles SET partner_id = 0, marriage_date = NULL WHERE user_id = ?", (user_id,))
        cursor.execute("UPDATE profiles SET partner_id = 0, marriage_date = NULL WHERE user_id = ?", (partner_id,))
        conn.commit()
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
    "lappillow": ("lappillow", "😴 {user} хочет лечь на колени {target}!",  "😴 {user} ищет колени!", "😴 {user} уснул на коленях {target}!", "🚫 {target} сбросил {user} с колен."),
    "pout":      ("pout",      "😠 {user} дуется на {target}!",            "😠 {user} дуется!", "😊 {target} пытается развеселить {user}!", "😑 {target} проигнорировал {user}."),
    "nod":       ("nod",       "頷 {user} кивает {target}!",               "頷 {user} кивает!", "頷 {target} кивает {user} в ответ!", "😑 {target} не понял кивка {user}."),
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
    "snuggle":   ("snuggle",   "🧸 {user} уютно прижимается к {target}!",   "🧸 {user} ищет уюта!", "🧸 {target} и {user} мило обнимаются!", "💔 {target} отодвинулся от {user}."),
    "shout":     ("shout",     "📢 {user} кричит на {target}!",            "📢 {user} кричит!", "📢 {target} кричит в ответ на {user}!", "😑 {target} заткнул уши."),
    "scared":    ("scared",    "😨 {user} боится {target}!",               "😨 {user} дрожит от страха!", "🫂 {target} успокаивает {user}!", "😈 {target} пугает {user} еще сильнее!"),
    "lick":      ("lick",      "👅 {user} хочет лизнуть {target}!",         "👅 {user} облизывается!", "👅 {user} лизнул {target}!", "🤢 {target} оттолкнул {user}!"),
    "glare":     ("glare",     "😠 {user} сердито смотрит на {target}!",    "😠 {user} сердито смотрит!", "😠 {target} смотрит в ответ!", "😑 {target} отвел взгляд."),
    "sex":       ("kiss",      "🔞 {user} хочет заняться сексом с {target}!", "🔞 {user} ищет партнера!", "🔞 {user} и {target} занялись бурным сексом! 🔥", "🚫 {target} отказал {user} в близости."),
    "blowjob":   ("lick",      "🔞 {user} хочет сделать минет {target}!",   "🔞 {user} облизывается!", "🔞 {user} сделал минет {target}! 💦", "🚫 {target} оттолкнул {user}."),
    "strip":     ("blush",     "🔞 {user} хочет раздеть {target}!",         "🔞 {user} раздевается!", "🔞 {user} раздел {target}! 😳", "🚫 {target} не дал себя раздеть!"),
    "spank":     ("slap",      "🍑 {user} хочет отшлепать {target}!",       "🍑 {user} шлепает воздух!", "🍑 {user} отшлепал {target}!", "🛡️ {target} увернулся от шлепка!"),
    "crunch":    ("poke",      "🦴 {user} хочет хрустнуть {target}!",       "🦴 {user} хрустит костями!", "🦴 {user} хрустнул {target}!", "🛡️ {target} увернулся!"),
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
    "уют": "snuggle", "прильнуть": "snuggle",
    "кричать": "shout", "крик": "shout",
    "бояться": "scared", "испуг": "scared",
    "лизнуть": "lick", "лизать": "lick",
    "злой_взгляд": "glare", "сердиться": "glare",
    "трахнуть": "sex", "секс": "sex",
    "отсосать": "blowjob", "минет": "blowjob",
    "раздеть": "strip",
    "отшлепать": "spank", "шлепок": "spank",
    "хрусть": "crunch",
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
                else:
                    logger.warning(f"Nekos.best API вернул статус {resp.status} для {endpoint}")
                    return None
    except aiohttp.ClientError as e:
        logger.error(f"Ошибка HTTP при получении гифки ({endpoint}): {e}")
    except asyncio.TimeoutError:
        logger.error(f"Таймаут при получении гифки ({endpoint})")
    except json.JSONDecodeError:
        logger.error(f"Ошибка декодирования JSON от Nekos.best API ({endpoint})")
    except Exception as e:
        logger.error(f"Неизвестная ошибка при получении гифки ({endpoint}): {e}")
    return None

def get_user_name(user) -> str:
    """Возвращает Имя (Full Name) пользователя в виде ссылки."""
    full_name = user.full_name or user.first_name or "Аноним"
    # Экранирование символов для MarkdownV2
    full_name = full_name.replace("[", "\\[").replace("]", "\\]").replace("(", "\\(").replace(")", "\\)").replace("~", "\\~").replace("`", "\\`").replace(">", "\\>").replace("#", "\\#").replace("+", "\\+").replace("-", "\\-").replace("=", "\\=").replace("|", "\\|").replace("{", "\\{").replace("}", "\\}").replace(".", "\\.").replace("!", "\\!")
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
                # Для упоминаний @username без ID, сохраняем как есть
                update_last_target(msg.from_user.id, 0, mention)
                return mention, 0
    return None, 0

# ─── Меню и Кнопки ───────────────────────────────────────────────────────────

def get_main_menu_keyboard():
    keyboard = [
        [
            InlineKeyboardButton("💞 Обнять", callback_data="rp_hug"),
            InlineKeyboardButton("💋 Поцеловать", callback_data="rp_kiss"),
            InlineKeyboardButton("👋 Пощёчина", callback_data="rp_slap"),
        ],
        [
            InlineKeyboardButton("🤗 Погладить", callback_data="rp_pat"),
            InlineKeyboardButton("😈 Укусить", callback_data="rp_bite"),
            InlineKeyboardButton("🥰 Прижаться", callback_data="rp_cuddle"),
        ],
        [
            InlineKeyboardButton("🎭 Все РП-команды", callback_data="show_rp_commands_0"),
            InlineKeyboardButton("✨ Инлайн-режим", switch_inline_query_current_chat=""),
        ],
        [
            InlineKeyboardButton("⚙️ Мои команды", callback_data="my_commands"),
            InlineKeyboardButton("👤 Мой профиль", callback_data="my_profile"),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_rp_commands_keyboard(page=0):
    commands_per_page = 6
    all_commands = sorted(list(BUILTIN_COMMANDS.keys()) + list(load_custom_commands().keys()))
    total_pages = (len(all_commands) + commands_per_page - 1) // commands_per_page
    
    start_index = page * commands_per_page
    end_index = min(start_index + commands_per_page, len(all_commands))
    
    keyboard_buttons = []
    for i in range(start_index, end_index):
        cmd = all_commands[i]
        display_name = RUSSIAN_ALIASES.get(cmd, cmd) if cmd in BUILTIN_COMMANDS else cmd
        keyboard_buttons.append([InlineKeyboardButton(f"/{display_name.capitalize()}", callback_data=f"rp_{cmd}")])
        
    navigation_buttons = []
    if page > 0:
        navigation_buttons.append(InlineKeyboardButton("⬅️ Назад", callback_data=f"show_rp_commands_{page-1}"))
    if page < total_pages - 1:
        navigation_buttons.append(InlineKeyboardButton("Вперед ➡️", callback_data=f"show_rp_commands_{page+1}"))
        
    if navigation_buttons:
        keyboard_buttons.append(navigation_buttons)
        
    keyboard_buttons.append([InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu")])
    
    return InlineKeyboardMarkup(keyboard_buttons)

# ─── Обработчики команд ──────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not user: return
    
    # Обновляем профиль пользователя при старте
    get_profile(user.id, user.username, user.full_name)
    
    await update.message.reply_html(
        f"Привет, {get_user_name(user)}! Я РП-бот с аниме-гифками. "
        "Используй команды или инлайн-режим для взаимодействия!",
        reply_markup=get_main_menu_keyboard()
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    help_text = (
        "Я РП-бот с аниме-гифками! Вот что я умею:\n\n"
        "**Основные команды:**\n"
        "`/start` - Главное меню\n"
        "`/help` - Показать это сообщение\n"
        "`/profile` - Показать ваш РП-профиль\n"
        "`/marry` (ответом на сообщение) - Сделать предложение\n"
        "`/divorce` - Развестись\n        "`/addcmd <название> <текст>` - Добавить свою команду (текст: {user}, {target}, {gif})\n"
        "`/mycmds` - Показать свои команды\n"
        "`/delcmd <название>` - Удалить свою команду\n\n"
        "**РП-команды:**\n"
        "Используйте `/hug`, `/kiss`, `/slap` и т.д. (более 100 команд!)\n"
        "- Ответом на сообщение: `/hug`\n"
        "- Упоминанием: `/hug @username`\n"
        "- Без цели: `/hug`\n\n"
        "**Инлайн-режим:**\n"
        "В любом чате напишите `@{context.bot.username} <команда>` (например, `@Kelliy0v0bot обнять`)"
        "- Бот предложит гифки с кнопками 'Принять/Отклонить'.\n"
        "- Бот автоматически подставит ник последнего собеседника.\n"
    )
    await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN_V2)

async def profile(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not user: return
    
    profile_data = get_profile(user.id, user.username, user.full_name)
    
    partner_info = "Нет" 
    if profile_data["partner_id"] != 0:
        partner_profile = get_profile(profile_data["partner_id"])
        partner_info = f"{partner_profile['full_name']} ({profile_data['marriage_date']})".replace("[", "\\[").replace("]", "\\]")

    profile_text = (
        f"**👤 Профиль {get_user_name(user)}**\n"
        f"Уровень: {profile_data['level']}\n"
        f"Опыт: {profile_data['xp']}\n"
        f"РП-действий: {profile_data['rp_count']}\n"
        f"В браке с: {partner_info}\n"
    )
    await update.message.reply_text(profile_text, parse_mode=ParseMode.MARKDOWN_V2)

async def marry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not user or not update.message or not update.message.reply_to_message or not update.message.reply_to_message.from_user: 
        await update.message.reply_text("Чтобы сделать предложение, ответьте на сообщение пользователя командой /marry.")
        return
    
    target_user = update.message.reply_to_message.from_user
    if user.id == target_user.id:
        await update.message.reply_text("Вы не можете жениться/выйти замуж за самого себя!")
        return
        
    user_profile = get_profile(user.id)
    target_profile = get_profile(target_user.id)
    
    if user_profile["partner_id"] != 0:
        await update.message.reply_text(f"{get_user_name(user)}, вы уже в браке!")
        return
    if target_profile["partner_id"] != 0:
        await update.message.reply_text(f"{get_user_name(target_user)} уже в браке!")
        return
        
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Принять", callback_data=f"marry_accept_{user.id}_{target_user.id}")],
        [InlineKeyboardButton("❌ Отклонить", callback_data=f"marry_decline_{user.id}_{target_user.id}")]
    ])
    
    await update.message.reply_text(
        f"{get_user_name(user)} делает предложение {get_user_name(target_user)}! "
        "{get_user_name(target_user)}, вы согласны?",
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN_V2
    )

async def divorce(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not user: return
    
    profile_data = get_profile(user.id)
    if profile_data["partner_id"] == 0:
        await update.message.reply_text("Вы не состоите в браке.")
        return
        
    partner_profile = get_profile(profile_data["partner_id"])
    if divorce(user.id):
        await update.message.reply_text(
            f"{get_user_name(user)} и {get_user_name(partner_profile)} теперь разведены. "
            "Как жаль... 💔",
            parse_mode=ParseMode.MARKDOWN_V2
        )
    else:
        await update.message.reply_text("Произошла ошибка при разводе.")

async def add_custom_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not user or not context.args or len(context.args) < 2:
        await update.message.reply_text("Использование: /addcmd <название> <текст>. "
                                       "В тексте можно использовать {user}, {target}, {gif}.")
        return
    
    cmd_name = context.args[0].lower()
    cmd_text = " ".join(context.args[1:])
    
    custom_commands = load_custom_commands()
    custom_commands[cmd_name] = cmd_text
    save_custom_commands(custom_commands)
    
    await update.message.reply_text(f"Команда /{cmd_name} добавлена!")

async def my_custom_commands(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    custom_commands = load_custom_commands()
    if not custom_commands:
        await update.message.reply_text("У вас пока нет своих команд.")
        return
        
    text = "**Ваши команды:**\n"
    for cmd, desc in custom_commands.items():
        text += f"`/{cmd}`: {desc}\n"
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN_V2)

async def delete_custom_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args or len(context.args) < 1:
        await update.message.reply_text("Использование: /delcmd <название>")
        return
        
    cmd_name = context.args[0].lower()
    custom_commands = load_custom_commands()
    
    if cmd_name in custom_commands:
        del custom_commands[cmd_name]
        save_custom_commands(custom_commands)
        await update.message.reply_text(f"Команда /{cmd_name} удалена!")
    else:
        await update.message.reply_text(f"Команда /{cmd_name} не найдена.")

async def handle_rp_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not user or not update.message: return
    
    command = update.message.text.split()[0].lstrip('/')
    
    # Проверяем, является ли команда встроенной или кастомной
    rp_command_data = BUILTIN_COMMANDS.get(command)
    is_custom = False
    if not rp_command_data:
        custom_commands = load_custom_commands()
        if command in custom_commands:
            rp_command_data = ("custom", custom_commands[command], custom_commands[command], custom_commands[command], custom_commands[command]) # Используем один текст для всех случаев
            is_custom = True
        else:
            return # Неизвестная команда

    endpoint = rp_command_data[0] if not is_custom else "hug" # Для кастомных команд используем 'hug' как заглушку для гифки
    
    target_name, target_id = get_target_info(update)
    
    if target_name and target_id != 0:
        # С целью
        text = rp_command_data[1].format(user=get_user_name(user), target=target_name)
        callback_data = f"rp_accept_{command}_{user.id}_{target_id}"
    else:
        # Без цели
        text = rp_command_data[2].format(user=get_user_name(user))
        callback_data = f"rp_accept_{command}_{user.id}_0"
        
    gif_url = await fetch_gif(endpoint)
    if not gif_url:
        await update.message.reply_text("Не удалось получить гифку. Попробуйте позже.")
        return
        
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Принять", callback_data=callback_data)],
        [InlineKeyboardButton("❌ Отклонить", callback_data=f"rp_decline_{command}_{user.id}_{target_id if target_id != 0 else 0}")]
    ])
    
    try:
        await update.message.reply_animation(
            animation=gif_url,
            caption=text,
            reply_markup=keyboard,
            parse_mode=ParseMode.MARKDOWN_V2
        )
        # Добавляем XP только если это не кастомная команда (чтобы не было спама XP)
        if not is_custom:
            new_level, level = add_xp(user.id)
            if new_level:
                await update.message.reply_text(f"Поздравляем, {get_user_name(user)}! Вы достигли {level} уровня! 🎉", parse_mode=ParseMode.MARKDOWN_V2)
    except telegram_error.TelegramError as e:
        logger.error(f"Ошибка Telegram при отправке РП-команды: {e}")
        await update.message.reply_text("Произошла ошибка при отправке РП-действия.")

# ─── Инлайн-режим ────────────────────────────────────────────────────────────

async def inline_query(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.inline_query.query.lower()
    user = update.effective_user
    if not user: return

    results = []
    
    # Авто-определение цели
    target_id, target_name = get_last_target(user.id)
    auto_target_user_name = target_name if target_id != 0 else None
    
    # Если запрос пустой, показываем последние цели или основные команды
    if not query:
        if auto_target_user_name:
            # Предлагаем РП с последней целью
            for cmd_name, (endpoint, text_target, text_no_target, text_accept, text_decline) in BUILTIN_COMMANDS.items():
                if endpoint == "custom": continue # Пропускаем кастомные заглушки
                title = f"/{cmd_name.capitalize()} для {auto_target_user_name.replace('\\[', '[').replace('\\]', ']')}"
                description = text_target.format(user="Вы", target=auto_target_user_name.replace('\\[', '[').replace('\\]', ']')).replace('**', '')
                
                # Создаем уникальный callback_data для каждой кнопки
                callback_accept = f"rp_accept_{cmd_name}_{user.id}_{target_id}"
                callback_decline = f"rp_decline_{cmd_name}_{user.id}_{target_id}"
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("✅ Принять", callback_data=callback_accept)],
                    [InlineKeyboardButton("❌ Отклонить", callback_data=callback_decline)]
                ])
                
                gif_url = await fetch_gif(endpoint)
                if gif_url:
                    results.append(
                        InlineQueryResultGif(
                            id=str(uuid.uuid4()),
                            gif_url=gif_url,
                            thumbnail_url=gif_url,
                            title=title,
                            caption=text_target.format(user=get_user_name(user), target=auto_target_user_name),
                            parse_mode=ParseMode.MARKDOWN_V2,
                            reply_markup=keyboard
                        )
                    )
            if results: # Если есть результаты с авто-целью, показываем их первыми
                await update.inline_query.answer(results, cache_time=5, is_personal=True)
                return
        
        # Если нет авто-цели или результатов, показываем общие команды
        for cmd_name, (endpoint, text_target, text_no_target, text_accept, text_decline) in BUILTIN_COMMANDS.items():
            if endpoint == "custom": continue
            title = f"/{cmd_name.capitalize()} (без цели)"
            description = text_no_target.format(user="Вы").replace('**', '')
            
            callback_accept = f"rp_accept_{cmd_name}_{user.id}_0"
            callback_decline = f"rp_decline_{cmd_name}_{user.id}_0"
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Принять", callback_data=callback_accept)],
                [InlineKeyboardButton("❌ Отклонить", callback_data=callback_decline)]
            ])
            
            gif_url = await fetch_gif(endpoint)
            if gif_url:
                results.append(
                    InlineQueryResultGif(
                        id=str(uuid.uuid4()),
                        gif_url=gif_url,
                        thumbnail_url=gif_url,
                        title=title,
                        caption=text_no_target.format(user=get_user_name(user)),
                        parse_mode=ParseMode.MARKDOWN_V2,
                        reply_markup=keyboard
                    )
                )
        
        await update.inline_query.answer(results, cache_time=5, is_personal=True)
        return

    # Обработка запроса с командой и/или целью
    parts = query.split(' ', 1)
    cmd_alias = parts[0]
    target_query = parts[1] if len(parts) > 1 else None

    # Определяем команду
    command = RUSSIAN_ALIASES.get(cmd_alias, cmd_alias)
    rp_command_data = BUILTIN_COMMANDS.get(command)
    
    if not rp_command_data:
        # Проверяем кастомные команды
        custom_commands = load_custom_commands()
        if command in custom_commands:
            rp_command_data = ("custom", custom_commands[command], custom_commands[command], custom_commands[command], custom_commands[command])
        else:
            await update.inline_query.answer([], cache_time=0)
            return

    endpoint = rp_command_data[0] if rp_command_data[0] != "custom" else "hug" # Для кастомных используем 'hug' как заглушку
    
    # Определяем цель из запроса
    target_user_id = 0
    target_user_name_str = None
    if target_query:
        # Пытаемся найти пользователя по @username или имени
        # Это упрощенная логика, в реальном боте нужна более сложная система поиска пользователей в чатах
        # Для инлайн-режима мы можем только отобразить текст, без реального ID цели из-за ограничений Telegram
        target_user_name_str = target_query.strip()
        # Экранирование для MarkdownV2
        target_user_name_str = target_user_name_str.replace("[", "\\[").replace("]", "\\]").replace("(", "\\(").replace(")", "\\)").replace("~", "\\~").replace("`", "\\`").replace(">", "\\>").replace("#", "\\#").replace("+", "\\+").replace("-", "\\-").replace("=", "\\=").replace("|", "\\|").replace("{", "\\{").replace("}", "\\}").replace(".", "\\.").replace("!", "\\!")

    if target_user_name_str:
        # С целью из запроса
        text = rp_command_data[1].format(user=get_user_name(user), target=target_user_name_str)
        title = f"/{command.capitalize()} для {target_user_name_str.replace('\\[', '[').replace('\\]', ']')}"
        description = rp_command_data[1].format(user="Вы", target=target_user_name_str.replace('\\[', '[').replace('\\]', ']') ).replace('**', '')
        callback_accept = f"rp_accept_{command}_{user.id}_{target_user_id}_{target_user_name_str}"
        callback_decline = f"rp_decline_{command}_{user.id}_{target_user_id}_{target_user_name_str}"
    else:
        # Без цели
        text = rp_command_data[2].format(user=get_user_name(user))
        title = f"/{command.capitalize()} (без цели)"
        description = rp_command_data[2].format(user="Вы").replace('**', '')
        callback_accept = f"rp_accept_{command}_{user.id}_0_None"
        callback_decline = f"rp_decline_{command}_{user.id}_0_None"

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Принять", callback_data=callback_accept)],
        [InlineKeyboardButton("❌ Отклонить", callback_data=callback_decline)]
    ])
    
    gif_url = await fetch_gif(endpoint)
    if gif_url:
        results.append(
            InlineQueryResultGif(
                id=str(uuid.uuid4()),
                gif_url=gif_url,
                thumbnail_url=gif_url,
                title=title,
                caption=text,
                parse_mode=ParseMode.MARKDOWN_V2,
                reply_markup=keyboard
            )
        )
    
    await update.inline_query.answer(results, cache_time=5, is_personal=True)

# ─── Обработчик Callback-кнопок ──────────────────────────────────────────────

async def button_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user = query.from_user
    if not user: return
    
    await query.answer() # Отвечаем на callback, чтобы убрать 
