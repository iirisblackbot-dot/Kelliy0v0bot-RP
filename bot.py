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

BUILTIN_COMMANDS: dict[str, tuple[str, str, str]] = {
    "hug":       ("hug",       "💞 {user} обнимает {target}!",          "💞 {user} обнимает всех вокруг!"),
    "kiss":      ("kiss",      "💋 {user} целует {target}!",             "💋 {user} посылает воздушный поцелуй!"),
    "slap":      ("slap",      "👋 {user} даёт пощёчину {target}!",      "👋 {user} бьёт по воздуху!"),
    "pat":       ("pat",       "🤗 {user} гладит {target} по голове!",   "🤗 {user} нежно гладит кого-то!"),
    "bite":      ("bite",      "😈 {user} кусает {target}!",             "😈 {user} кусает воздух!"),
    "cuddle":    ("cuddle",    "🥰 {user} прижимается к {target}!",      "🥰 {user} ищет кого обнять!"),
    "poke":      ("poke",      "👉 {user} тыкает {target}!",             "👉 {user} тыкает в воздух!"),
    "tickle":    ("tickle",    "😂 {user} щекочет {target}!",            "😂 {user} щекочет воздух!"),
    "bonk":      ("bonk",      "🔨 {user} бонкает {target}!",            "🔨 {user} бонкает в воздух!"),
    "baka":      ("baka",      "😤 {user} называет {target} бакой!",     "😤 {user} кричит «бака!»"),
    "blowkiss":  ("blowkiss",  "😘 {user} посылает поцелуй {target}!",   "😘 {user} посылает поцелуй в воздух!"),
    "handhold":  ("handhold",  "🤝 {user} берёт {target} за руку!",      "🤝 {user} тянет руку!"),
    "highfive":  ("highfive",  "🙌 {user} даёт пять {target}!",          "🙌 {user} поднимает руку для пятюни!"),
    "feed":      ("feed",      "🍡 {user} кормит {target}!",             "🍡 {user} ест что-то вкусное!"),
    "kick":      ("kick",      "🦵 {user} пинает {target}!",             "🦵 {user} пинает воздух!"),
    "punch":     ("punch",     "👊 {user} бьёт {target} кулаком!",       "👊 {user} бьёт кулаком в воздух!"),
    "yeet":      ("yeet",      "🚀 {user} выкидывает {target}!",         "🚀 {user} выкидывает что-то!"),
    "carry":     ("carry",     "💪 {user} несёт {target} на руках!",     "💪 {user} несёт кого-то!"),
    "kabedon":   ("kabedon",   "😳 {user} делает кабедон {target}!",     "😳 {user} делает кабедон!"),
    "shake":     ("shake",     "🤝 {user} трясёт {target} за плечи!",    "🤝 {user} трясётся!"),
    "wave":      ("wave",      "👋 {user} машет {target}!",              "👋 {user} машет рукой!"),
    "peck":      ("peck",      "😙 {user} чмокает {target} в щёчку!",   "😙 {user} чмокает в воздух!"),
    "stare":     ("stare",     "👀 {user} пристально смотрит на {target}!", "👀 {user} пристально смотрит!"),
    "wink":      ("wink",      "😉 {user} подмигивает {target}!",        "😉 {user} подмигивает!"),
    "blush":     ("blush",     "😊 {user} краснеет из-за {target}!",     "😊 {user} краснеет!"),
    "smile":     ("smile",     "😊 {user} улыбается {target}!",          "😊 {user} улыбается!"),
    "cry":       ("cry",       "😢 {user} плачет из-за {target}!",       "😢 {user} плачет!"),
    "dance":     ("dance",     "💃 {user} танцует с {target}!",          "💃 {user} танцует!"),
    "clap":      ("clap",      "👏 {user} аплодирует {target}!",         "👏 {user} аплодирует!"),
    "nom":       ("nom",       "😋 {user} ест {target}!",                "😋 {user} ест что-то!"),
    "facepalm":  ("facepalm",  "🤦 {user} делает фейспалм из-за {target}!", "🤦 {user} делает фейспалм!"),
    "handshake": ("handshake", "🤝 {user} жмёт руку {target}!",          "🤝 {user} протягивает руку!"),
    "lappillow": ("lappillow", "😴 {user} кладёт голову на колени {target}!", "😴 {user} ищет колени!"),
    "pout":      ("pout",      "😤 {user} дуется на {target}!",          "😤 {user} дуется!"),
    "nod":       ("nod",       "😌 {user} кивает {target}!",             "😌 {user} кивает!"),
    "salute":    ("salute",    "🫡 {user} отдаёт честь {target}!",       "🫡 {user} отдаёт честь!"),
    "thumbsup":  ("thumbsup",  "👍 {user} одобряет {target}!",           "👍 {user} одобряет!"),
    "laugh":     ("laugh",     "😂 {user} смеётся над {target}!",        "😂 {user} смеётся!"),
    "spin":      ("spin",      "🌀 {user} кружит {target}!",             "🌀 {user} кружится!"),
    "run":       ("run",       "🏃 {user} убегает от {target}!",         "🏃 {user} убегает!"),
    "sleep":     ("sleep",     "💤 {user} засыпает рядом с {target}!",   "💤 {user} засыпает!"),
    "yawn":      ("yawn",      "🥱 {user} зевает при {target}!",         "🥱 {user} зевает!"),
    "smug":      ("smug",      "😏 {user} смотрит на {target} с ухмылкой!", "😏 {user} ухмыляется!"),
    "think":     ("think",     "🤔 {user} думает о {target}!",           "🤔 {user} думает!"),
    "happy":     ("happy",     "😄 {user} счастлив рядом с {target}!",  "😄 {user} счастлив!"),
    "angry":     ("angry",     "😠 {user} злится на {target}!",          "😠 {user} злится!"),
    "shoot":     ("shoot",     "🔫 {user} стреляет в {target}!",         "🔫 {user} стреляет!"),
    "lurk":      ("lurk",      "🕵️ {user} следит за {target}!",          "🕵️ {user} наблюдает!"),
    "confused":  ("confused",  "😕 {user} смотрит на {target} с непониманием!", "😕 {user} в замешательстве!"),
    "shrug":     ("shrug",     "🤷 {user} пожимает плечами при {target}!", "🤷 {user} пожимает плечами!"),
    "wag":       ("wag",       "🐾 {user} виляет хвостом перед {target}!", "🐾 {user} виляет хвостом!"),
    "sip":       ("sip",       "☕ {user} пьёт чай, глядя на {target}!", "☕ {user} пьёт чай!"),
    "teehee":    ("teehee",    "🤭 {user} хихикает над {target}!",       "🤭 {user} хихикает!"),
    "shocked":   ("shocked",   "😱 {user} шокирован {target}!",          "😱 {user} шокирован!"),
    "bleh":      ("bleh",      "😛 {user} показывает язык {target}!",    "😛 {user} показывает язык!"),
    "bored":     ("bored",     "😑 {user} скучает рядом с {target}!",    "😑 {user} скучает!"),
    "nya":       ("nya",       "🐱 {user} мяукает на {target}!",         "🐱 {user} мяукает!"),
    "tableflip": ("tableflip", "😤 {user} переворачивает стол из-за {target}!", "😤 {user} переворачивает стол!"),
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
            InlineKeyboardButton("🎭 Все РП-команды", callback_data="menu_rp_list"),
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
    
    # Кнопки команд по 3 в ряд
    for i in range(0, len(current_cmds), 3):
        row = [InlineKeyboardButton(f"/{c}", callback_data=f"rp_{c}") for c in current_cmds[i:i+3]]
        keyboard.append(row)
    
    # Навигация
    nav_row = []
    if total_pages > 1:
        nav_row.append(InlineKeyboardButton("⬅️", callback_data=f"page_{page-1}"))
        nav_row.append(InlineKeyboardButton(f"{page+1}/{total_pages}", callback_data="ignore"))
        nav_row.append(InlineKeyboardButton("➡️", callback_data=f"page_{page+1}"))
        keyboard.append(nav_row)
    
    keyboard.append([InlineKeyboardButton("🔙 Назад в меню", callback_data="menu_main")])
    return InlineKeyboardMarkup(keyboard)

# ─── Обработчики команд ───────────────────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        "👋 *Привет! Я РП-бот @Kelliy0v0bot!*\n\n"
        "Я помогу тебе выразить эмоции с помощью аниме-гифок.\n"
        "Используй кнопки ниже или пиши команды в чат!"
    )
    await update.message.reply_text(
        text, 
        reply_markup=get_main_menu_keyboard(),
        parse_mode=ParseMode.MARKDOWN
    )

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        "📖 *Справка по боту*\n\n"
        "*Как использовать:* `/hug @user` или ответом на сообщение.\n"
        "*Инлайн:* Набери `@Kelliy0v0bot hug` в любом чате.\n"
        "*Свои команды:* `/addcmd <имя> <текст>`\n\n"
        "Выбери раздел ниже для подробностей:"
    )
    await update.message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 В меню", callback_data="menu_main")]]),
        parse_mode=ParseMode.MARKDOWN
    )

# ─── Обработчик Callback (кнопок) ─────────────────────────────────────────────

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    
    data = query.data
    user_mention = get_user_mention(query.from_user)

    if data == "menu_main":
        await query.edit_message_text(
            "👋 *Главное меню РП-бота*\n\nВыбери действие:",
            reply_markup=get_main_menu_keyboard(),
            parse_mode=ParseMode.MARKDOWN
        )
    
    elif data == "menu_rp_list":
        await query.edit_message_text(
            "🎭 *Список РП-команд:*\nНажми на кнопку, чтобы выполнить действие!",
            reply_markup=get_rp_list_keyboard(0),
            parse_mode=ParseMode.MARKDOWN
        )
    
    elif data.startswith("page_"):
        page = int(data.split("_")[1])
        await query.edit_message_text(
            "🎭 *Список РП-команд:*\nНажми на кнопку, чтобы выполнить действие!",
            reply_markup=get_rp_list_keyboard(page),
            parse_mode=ParseMode.MARKDOWN
        )

    elif data.startswith("rp_"):
        cmd_name = data.split("_")[1]
        endpoint, _, text_without = BUILTIN_COMMANDS[cmd_name]
        caption = text_without.format(user=user_mention)
        
        gif_url = await fetch_gif(endpoint)
        if gif_url:
            await query.message.reply_animation(
                animation=gif_url,
                caption=caption,
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            await query.message.reply_text(caption, parse_mode=ParseMode.MARKDOWN)

    elif data == "menu_help":
        await cmd_help(update, context) # Можно переписать под edit_message

    elif data == "menu_mycmds":
        # Упрощенный вызов списка своих команд
        custom = load_custom_commands()
        user_id = str(query.from_user.id)
        user_cmds = custom.get(user_id, {})
        if not user_cmds:
            text = "📭 У вас пока нет своих команд. Добавьте их через `/addcmd`!"
        else:
            text = "🗂 *Ваши команды:*\n" + "\n".join([f"• `/{n}`" for n in user_cmds.keys()])
        
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 В меню", callback_data="menu_main")]]),
            parse_mode=ParseMode.MARKDOWN
        )

# ─── Остальные обработчики (без изменений логики) ─────────────────────────────

async def cmd_rp_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("🎭 Список команд:", reply_markup=get_rp_list_keyboard(0))

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

async def handle_rp_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message
    if not msg or not msg.text: return
    cmd_name = msg.text.split()[0].lstrip("/").split("@")[0].lower()
    user_mention = get_user_mention(msg.from_user)
    target_mention = get_target_mention(update)

    if cmd_name in BUILTIN_COMMANDS:
        endpoint, text_with, text_without = BUILTIN_COMMANDS[cmd_name]
        caption = text_with.format(user=user_mention, target=target_mention) if target_mention else text_without.format(user=user_mention)
        gif_url = await fetch_gif(endpoint)
        if gif_url:
            await msg.reply_animation(animation=gif_url, caption=caption, parse_mode=ParseMode.MARKDOWN)
        else:
            await msg.reply_text(caption, parse_mode=ParseMode.MARKDOWN)
        return

    custom = load_custom_commands()
    user_id = str(msg.from_user.id)
    user_cmds = custom.get(user_id, {})
    if cmd_name in user_cmds:
        template = user_cmds[cmd_name]
        caption = template.format(user=user_mention, target=target_mention or "всех")
        await msg.reply_text(caption, parse_mode=ParseMode.MARKDOWN)

async def inline_query(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query_text = update.inline_query.query.strip().lower()
    user = update.inline_query.from_user
    user_mention = get_user_mention(user)
    results = []
    
    commands_to_show = [c for c in BUILTIN_COMMANDS if c.startswith(query_text)][:20] if query_text else list(BUILTIN_COMMANDS.keys())[:20]

    for cmd_name in commands_to_show:
        endpoint, text_with, text_without = BUILTIN_COMMANDS[cmd_name]
        parts = query_text.split(None, 1)
        target_text = parts[1] if len(parts) > 1 else None
        caption = text_with.format(user=user_mention, target=target_text) if target_text else text_without.format(user=user_mention)
        gif_url = await fetch_gif(endpoint)
        if gif_url:
            results.append(InlineQueryResultGif(id=str(uuid.uuid4()), gif_url=gif_url, thumbnail_url=gif_url, title=f"/{cmd_name}", caption=caption, parse_mode=ParseMode.MARKDOWN))
    await update.inline_query.answer(results, cache_time=10)

# ─── Запуск ──────────────────────────────────────────────────────────────────

def main() -> None:
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("rp", cmd_rp_list))
    app.add_handler(CommandHandler("addcmd", cmd_add_custom))
    app.add_handler(CommandHandler("delcmd", cmd_del_custom))
    app.add_handler(CallbackQueryHandler(handle_callback))
    
    for cmd in BUILTIN_COMMANDS:
        app.add_handler(CommandHandler(cmd, handle_rp_command))
    
    app.add_handler(MessageHandler(filters.COMMAND, handle_rp_command))
    app.add_handler(InlineQueryHandler(inline_query))
    
    logger.info("Бот с меню запущен!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
