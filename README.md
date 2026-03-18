# 🎭 Telegram РП-Бот с аниме-гифками

Полноценный РП-бот для Telegram с аниме-гифками, кастомными командами и инлайн-режимом.

---

## 🚀 Быстрый старт

### 1. Установка зависимостей

```bash
pip install -r requirements.txt
```

### 2. Настройка токена

Откройте файл `bot.py` и замените значение `BOT_TOKEN` на токен вашего бота:

```python
BOT_TOKEN = "ВАШ_ТОКЕН_ЗДЕСЬ"
```

Токен можно получить у [@BotFather](https://t.me/BotFather).

### 3. Включение инлайн-режима

Обязательно включите инлайн-режим у @BotFather:
1. Напишите `/mybots` → выберите бота
2. `Bot Settings` → `Inline Mode` → `Turn on`

### 4. Запуск

```bash
python bot.py
```

---

## 📋 Команды бота

### Системные команды

| Команда | Описание |
|---------|----------|
| `/start` | Приветственное сообщение |
| `/help` | Справка |
| `/rp` | Список всех РП-команд |
| `/addcmd <команда> <текст>` | Добавить свою РП-команду |
| `/delcmd <команда>` | Удалить свою команду |
| `/mycmds` | Список ваших кастомных команд |

### Встроенные РП-команды (55+ команд)

`/hug` `/kiss` `/slap` `/pat` `/bite` `/cuddle` `/poke` `/tickle` `/bonk` `/baka`
`/blowkiss` `/handhold` `/highfive` `/feed` `/kick` `/punch` `/yeet` `/carry`
`/kabedon` `/shake` `/wave` `/peck` `/stare` `/wink` `/blush` `/smile` `/cry`
`/dance` `/clap` `/nom` `/facepalm` `/handshake` `/lappillow` `/pout` `/nod`
`/salute` `/thumbsup` `/laugh` `/spin` `/run` `/sleep` `/yawn` `/smug` `/think`
`/happy` `/angry` `/shoot` `/lurk` `/confused` `/shrug` `/wag` `/sip` `/teehee`
`/shocked` `/bleh` `/bored` `/nya` `/tableflip`

---

## 💡 Как использовать РП-команды

### Вариант 1: Упоминание пользователя
```
/hug @username
```

### Вариант 2: Ответ на сообщение
Ответь на сообщение пользователя и напиши `/kiss`

### Вариант 3: Без цели
```
/dance
```

---

## ✨ Добавление своих команд

```
/addcmd stab {user} тыкает {target} ножом! 🗡️
/addcmd glomp {user} прыгает на {target}! 🐾
/addcmd headpat {user} гладит {target} по голове ✋
```

Переменные:
- `{user}` — тот, кто вызвал команду
- `{target}` — цель (упомянутый пользователь)

---

## 🔍 Инлайн-режим

В **любом чате** (не только в боте) напиши:

```
@имя_бота hug
@имя_бота kiss @username
@имя_бота pat
```

Появится список с аниме-гифками — выбери нужную!

---

## 🎨 Источник гифок

Бот использует бесплатный API [nekos.best](https://nekos.best/) — высококачественные аниме-гифки без ключа API.

---

## 📁 Структура файлов

```
rp_bot/
├── bot.py                 # Основной код бота
├── requirements.txt       # Зависимости
├── custom_commands.json   # Кастомные команды (создаётся автоматически)
└── README.md              # Эта инструкция
```

---

## 🛠 Запуск как сервис (Linux)

Создайте файл `/etc/systemd/system/rpbot.service`:

```ini
[Unit]
Description=Telegram RP Bot
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/path/to/rp_bot
ExecStart=/usr/bin/python3 bot.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Затем:
```bash
sudo systemctl enable rpbot
sudo systemctl start rpbot
sudo systemctl status rpbot
```
