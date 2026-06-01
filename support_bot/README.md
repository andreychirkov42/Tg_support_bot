# Telegram-бот поддержки

Асинхронный бот поддержки на Python 3.11+, aiogram 3.x и SQLite.

## Архитектура

Пользователь общается только с ботом в личном чате: создает обращения, смотрит статусы и добавляет сообщения к тикетам.

Админы работают только в `ADMIN_CHAT_ID`: бот публикует туда карточки тикетов, а операторы управляют ими inline-кнопками и reply-сообщениями.

```text
support_bot/
├── bot.py
├── config.py
├── database.py
├── filters.py
├── keyboards.py
├── states.py
├── handlers/
│   ├── user.py
│   ├── admin_channel.py
│   └── common.py
├── services/
│   ├── ticket_service.py
│   ├── user_service.py
│   └── admin_service.py
└── utils/
    ├── formatting.py
    └── permissions.py
```

## Установка

```bash
cd /home/goga/Proga/Tg_support_bot
python3 -m venv .venv
source .venv/bin/activate
pip install -r support_bot/requirements.txt
```

## Настройка

```bash
cp support_bot/.env.example support_bot/.env
```

Заполните `support_bot/.env`:

```env
BOT_TOKEN=1234567890:telegram_bot_token
ADMIN_CHAT_ID=-1001234567890
ADMIN_IDS=123456789,987654321
```

`BOT_TOKEN` получите у BotFather.

`ADMIN_CHAT_ID` — ID канала, супергруппы или рабочего чата поддержки, куда бот отправляет обращения.

`ADMIN_IDS` — Telegram ID операторов, которым разрешено нажимать админские кнопки.

## Как узнать ADMIN_CHAT_ID

1. Добавьте бота в канал или группу поддержки.
2. Дайте боту права администратора.
3. Временно отправьте в чат любое сообщение и получите ID удобным способом через Telegram API или служебного бота.
4. Впишите ID в `support_bot/.env`.

Для каналов и супергрупп ID обычно выглядит как `-1001234567890`.

## Права бота в ADMIN_CHAT_ID

Боту нужны права:

- отправлять сообщения;
- редактировать свои сообщения;
- читать сообщения, если это группа;
- видеть reply-сообщения.

В канале бот должен быть администратором.

## Запуск

```bash
./run.sh
```

Или вручную:

```bash
source .venv/bin/activate
python -m support_bot.bot
```

SQLite-база создается автоматически: `support_bot/support_bot.sqlite3`.

## Работа админов

Команда `/admin` работает только в `ADMIN_CHAT_ID`.

В личном чате с ботом админ-панель не открывается. Пользовательские админские функции не видны.

Админ может:

- посмотреть новые, рабочие и закрытые обращения;
- открыть историю тикета;
- взять тикет в работу;
- ответить пользователю reply-сообщением;
- закрыть тикет;
- заблокировать или разблокировать пользователя;
- найти тикет по номеру;
- посмотреть статистику.
