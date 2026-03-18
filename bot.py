"""
Telegram РП-бот с аниме-гифками (nekos.best API)
Автор: Manus AI
"""

import logging
import json
import os
import uuid
import asyncio
import aiohttp
import re

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
CUSTOM_COMMANDS_FILE = "custom_commands.json"
NEKOS_API = "https://nekos.best/api/v2/"

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ─── Встроенные РП-команды ───────────────────────────────────────────────────

BUILTIN_COMMANDS: dict[str, tuple[str, str, str, str, str]] = {
    "hug":       ("hug",       "💞 {user} хочет обнять {target}!",          "💞 {user} обнимает всех вокруг!", "💞 {target} принял обнимашки от {user}!", "💔 {target} не хочет обниматься с {user}..."),
    "kiss":      ("kiss",      "💋 {user} хочет поцеловать {target}!",       "💋 {user} посылает воздушный поцелуй!", "💋 {target} ответил на поцелуй {user}!", "💔 {target} увернулся от поцелуя {user}..."),
    "slap":      ("slap",      "👋 {user} хочет дать пощёчину {target}!",    "👋 {user} бьёт по воздуху!", "👋 {user} дал пощёчину {target}!", "🛡️ {target} заблокировал удар {user}!"),
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

# ─── Русские синонимы для инлайн-поиска ──────────────────────────────────────

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

def get_user_mention(user) -> str:
    if user.username:
        return f"@{user.username}"
    full_name = user.full_name or user.first_name or "Аноним"
    return f"[{full_name}](tg://user?id={user.id})"

def get_target_mention(update: Update) -> str | None:
    msg = update.message
    if not msg: return None
    if msg.reply_to_message and msg.reply_to_message.from_user:
        return get_user_mention(msg.reply_to_message.from_user)
    if msg.entities:
        for entity in msg.entities:
            if entity.type == "mention":
                return msg.text[entity.offset:entity.offset + entity.length]
            elif entity.type == "text_mention" and entity.user:
                return get_user_mention(entity.user)
    return None

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
    keyboard = [
        [
            InlineKeyboardButton("✅ Принять", callback_data=f"accept_{user_id}_{target_id}_{cmd_name}"),
            InlineKeyboardButton("❌ Отклонить", callback_data=f"decline_{user_id}_{target_id}_{cmd_name}"),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

# ─── Обработчики команд ───────────────────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        "👋 *Привет! Я РП-бот @Kelliy0v0bot!*\n\n"
        "Я помогу тебе выразить эмоции с помощью аниме-гифк.\n"
        "Используй кнопки ниже или пиши команды в чат!"
    )
    await update.message.reply_text(text, reply_markup=get_main_menu_keyboard(), parse_mode=ParseMode.MARKDOWN)

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        "📖 *Справка по боту*\n\n"
        "*Как использовать:* `/hug @user` или ответом на сообщение.\n"
        "*Инлайн:* Набери `@Kelliy0v0bot обнять @user` в любом чате.\n"
        "*Свои команды:* `/addcmd <имя> <текст>`\n\n"
        "В инлайн-режиме теперь есть кнопки **Принять** и **Отклонить**!"
    )
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 В меню", callback_data="menu_main")]]), parse_mode=ParseMode.MARKDOWN)

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

async def cmd_del_custom(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args: return
    cmd_name = context.args[0].lower().strip("/")
    custom = load_custom_commands()
    user_id = str(update.effective_user.id)
    if user_id in custom and cmd_name in custom[user_id]:
        del custom[user_id][cmd_name]
        save_custom_commands(custom)
        await update.message.reply_text(f"✅ Удалено.")

# ─── Обработчик Callback (кнопок) ─────────────────────────────────────────────

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    data = query.data
    user = query.from_user
    
    if data.startswith(("accept_", "decline_")):
        parts = data.split("_")
        action = parts[0]
        initiator_id = int(parts[1])
        target_id = int(parts[2])
        cmd_name = parts[3]
        if target_id != 0 and user.id != target_id:
            await query.answer("❌ Это действие направлено не вам!", show_alert=True)
            return
        await query.answer()
        current_text = query.message.caption if query.message.caption else query.message.text
        mentions = re.findall(r"(@\w+|\[.*?\]\(tg://user\?id=\d+\))", current_text)
        initiator_mention = mentions[0] if len(mentions) > 0 else f"ID:{initiator_id}"
        target_mention = mentions[1] if len(mentions) > 1 else get_user_mention(user)
        _, _, _, accepted_tpl, declined_tpl = BUILTIN_COMMANDS[cmd_name]
        new_text = accepted_tpl.format(user=initiator_mention, target=target_mention) if action == "accept" else declined_tpl.format(user=initiator_mention, target=target_mention)
        if query.message.caption:
            await query.edit_message_caption(caption=new_text, parse_mode=ParseMode.MARKDOWN)
        else:
            await query.edit_message_text(text=new_text, parse_mode=ParseMode.MARKDOWN)
        return

    await query.answer()
    user_mention = get_user_mention(user)
    if data == "menu_main":
        await query.edit_message_text("👋 *Главное меню РП-бота*\n\nВыбери действие:", reply_markup=get_main_menu_keyboard(), parse_mode=ParseMode.MARKDOWN)
    elif data == "menu_rp_list":
        await query.edit_message_text("🎭 *Список РП-команд:*\nНажми на кнопку, чтобы выполнить действие!", reply_markup=get_rp_list_keyboard(0), parse_mode=ParseMode.MARKDOWN)
    elif data.startswith("page_"):
        page = int(data.split("_")[1])
        await query.edit_message_text("🎭 *Список РП-команд:*\nНажми на кнопку, чтобы выполнить действие!", reply_markup=get_rp_list_keyboard(page), parse_mode=ParseMode.MARKDOWN)
    elif data.startswith("rp_"):
        cmd_name = data.split("_")[1]
        endpoint, _, text_without, _, _ = BUILTIN_COMMANDS[cmd_name]
        caption = text_without.format(user=user_mention)
        gif_url = await fetch_gif(endpoint)
        if gif_url:
            await query.message.reply_animation(animation=gif_url, caption=caption, parse_mode=ParseMode.MARKDOWN)
        else:
            await query.message.reply_text(caption, parse_mode=ParseMode.MARKDOWN)
    elif data == "menu_help":
        await cmd_help(update, context)
    elif data == "menu_mycmds":
        custom = load_custom_commands()
        user_cmds = custom.get(str(user.id), {})
        text = "🗂 *Ваши команды:*\n" + "\n".join([f"• `/{n}`" for n in user_cmds.keys()]) if user_cmds else "📭 У вас пока нет своих команд."
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 В меню", callback_data="menu_main")]]), parse_mode=ParseMode.MARKDOWN)

# ─── Обработчики РП ──────────────────────────────────────────────────────────

async def handle_rp_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message
    if not msg or not msg.text: return
    cmd_name = msg.text.split()[0].lstrip("/").split("@")[0].lower()
    user_mention = get_user_mention(msg.from_user)
    target_mention = get_target_mention(update)
    if cmd_name in BUILTIN_COMMANDS:
        endpoint, text_with, text_without, _, _ = BUILTIN_COMMANDS[cmd_name]
        caption = text_with.format(user=user_mention, target=target_mention) if target_mention else text_without.format(user=user_mention)
        gif_url = await fetch_gif(endpoint)
        if gif_url:
            await msg.reply_animation(animation=gif_url, caption=caption, parse_mode=ParseMode.MARKDOWN)
        else:
            await msg.reply_text(caption, parse_mode=ParseMode.MARKDOWN)
        return
    custom = load_custom_commands()
    user_cmds = custom.get(str(msg.from_user.id), {})
    if cmd_name in user_cmds:
        template = user_cmds[cmd_name]
        caption = template.format(user=user_mention, target=target_mention or "всех")
        await msg.reply_text(caption, parse_mode=ParseMode.MARKDOWN)

# ─── Инлайн-режим ────────────────────────────────────────────────────────────

async def inline_query(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.inline_query
    query_text = query.query.strip().lower()
    user = query.from_user
    user_mention = get_user_mention(user)
    results = []
    
    parts = query_text.split(None, 1)
    cmd_query = parts[0] if parts else ""
    target_input = parts[1] if len(parts) > 1 else None
    
    # Маппинг русского ввода на английские команды
    mapped_cmd = RUSSIAN_ALIASES.get(cmd_query, cmd_query)
    
    # Поиск подходящих команд
    commands_to_show = [c for c in BUILTIN_COMMANDS if c.startswith(mapped_cmd)][:20] if mapped_cmd else list(BUILTIN_COMMANDS.keys())[:20]
    
    for cmd_name in commands_to_show:
        endpoint, text_with, text_without, _, _ = BUILTIN_COMMANDS[cmd_name]
        reply_markup = None
        target_id = 0
        if target_input:
            caption = text_with.format(user=user_mention, target=target_input)
            match = re.search(r"tg://user\?id=(\d+)", target_input)
            target_id = int(match.group(1)) if match else 0
            reply_markup = get_rp_action_keyboard(user.id, target_id, cmd_name)
        else:
            caption = text_without.format(user=user_mention)
        gif_url = await fetch_gif(endpoint)
        if gif_url:
            results.append(InlineQueryResultGif(id=str(uuid.uuid4()), gif_url=gif_url, thumbnail_url=gif_url, title=f"/{cmd_name}", caption=caption, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN))
    await query.answer(results, cache_time=10)

# ─── Запуск ──────────────────────────────────────────────────────────────────

def main() -> None:
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("rp", lambda u, c: u.message.reply_text("🎭 Список команд:", reply_markup=get_rp_list_keyboard(0))))
    app.add_handler(CommandHandler("addcmd", cmd_add_custom))
    app.add_handler(CommandHandler("delcmd", cmd_del_custom))
    app.add_handler(CallbackQueryHandler(handle_callback))
    for cmd in BUILTIN_COMMANDS:
        app.add_handler(CommandHandler(cmd, handle_rp_command))
    app.add_handler(MessageHandler(filters.COMMAND, handle_rp_command))
    app.add_handler(InlineQueryHandler(inline_query))
    logger.info("Бот с поддержкой русских команд запущен!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
