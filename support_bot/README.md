# Telegram-бот поддержки

Асинхронный Telegram-бот службы поддержки на Python 3.11+, aiogram 3.x и SQLite.

## Возможности

- Главное меню через кнопки.
- Создание обращения с выбором категории и предпросмотром.
- Автоответ после отправки.
- Просмотр своих обращений и статуса.
- Добавление сообщений к обращению.
- FAQ с готовыми ответами.
- Быстрое обращение к оператору.
- Админ-панель с просмотром, поиском, ответами и сменой статусов.

## Структура

```text
support_bot/
├── bot.py
├── config.py
├── database.py
├── keyboards.py
├── states.py
├── handlers/
│   ├── user.py
│   ├── admin.py
│   └── common.py
├── services/
│   └── ticket_service.py
├── .env.example
├── requirements.txt
└── README.md
```

## Установка

Перейдите в корень проекта:

```bash
cd d:\von_support_bot
```

Создайте виртуальное окружение:

```bash
python -m venv .venv
```

Активируйте его в PowerShell:

```bash
.\.venv\Scripts\Activate.ps1
```

Установите зависимости:

```bash
pip install -r support_bot/requirements.txt
```

## Настройка .env

Скопируйте пример:

```bash
copy support_bot\.env.example .env
```

Заполните `.env`:

```env
BOT_TOKEN=1234567890:telegram_bot_token
ADMIN_IDS=123456789,987654321
```

`BOT_TOKEN` можно получить у BotFather. `ADMIN_IDS` — это Telegram ID администраторов через запятую.

## Запуск

Запускайте из корня проекта:

```bash
python -m support_bot.bot
```

После первого запуска SQLite-база будет создана автоматически в `support_bot/support_bot.sqlite3`.

## Как добавить админа

1. Узнайте Telegram ID пользователя.
2. Добавьте ID в переменную `ADMIN_IDS` в `.env`.
3. Если админов несколько, укажите их через запятую:

```env
ADMIN_IDS=123456789,987654321
```

4. Перезапустите бота.

Админ-панель открывается командой `/admin`.

