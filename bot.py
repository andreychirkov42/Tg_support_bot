import json
import os
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib import error, request


API_BASE = "https://api.telegram.org/bot{token}/{method}"
ChatId = int | str
CONTENT_FIELDS = {
    "text",
    "photo",
    "document",
    "audio",
    "voice",
    "video",
    "video_note",
    "sticker",
    "animation",
    "contact",
    "location",
    "venue",
    "poll",
    "dice",
}


@dataclass(frozen=True)
class Config:
    token: str
    support_chat_id: int | None
    database_path: Path
    request_timeout: int = 45
    polling_timeout: int = 30


class TelegramError(RuntimeError):
    pass


class TelegramBot:
    def __init__(self, token: str, request_timeout: int) -> None:
        self.token = token
        self.request_timeout = request_timeout

    def call(self, method: str, payload: dict[str, Any]) -> dict[str, Any]:
        url = API_BASE.format(token=self.token, method=method)
        body = json.dumps(payload).encode("utf-8")
        req = request.Request(
            url,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with request.urlopen(req, timeout=self.request_timeout) as response:
                data = json.loads(response.read().decode("utf-8"))
        except error.HTTPError as exc:
            details = exc.read().decode("utf-8", errors="replace")
            raise TelegramError(f"Telegram HTTP {exc.code}: {details}") from exc
        except error.URLError as exc:
            raise TelegramError(f"Telegram request failed: {exc.reason}") from exc

        if not data.get("ok"):
            raise TelegramError(data.get("description", "Telegram API returned ok=false"))

        return data["result"]

    def get_updates(self, offset: int | None, timeout: int) -> list[dict[str, Any]]:
        payload: dict[str, Any] = {
            "timeout": timeout,
            "allowed_updates": ["message", "channel_post"],
        }
        if offset is not None:
            payload["offset"] = offset
        return self.call("getUpdates", payload)

    def send_message(
        self,
        chat_id: ChatId,
        text: str,
        reply_to_message_id: int | None = None,
    ) -> int:
        payload: dict[str, Any] = {
            "chat_id": chat_id,
            "text": text,
            "disable_web_page_preview": True,
        }
        if reply_to_message_id is not None:
            payload["reply_parameters"] = {"message_id": reply_to_message_id}
        result = self.call("sendMessage", payload)
        return int(result["message_id"])

    def copy_message(
        self,
        chat_id: ChatId,
        from_chat_id: ChatId,
        message_id: int,
    ) -> int:
        result = self.call(
            "copyMessage",
            {
                "chat_id": chat_id,
                "from_chat_id": from_chat_id,
                "message_id": message_id,
            },
        )
        return int(result["message_id"])


class MessageStore:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(path)
        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS message_map (
                admin_chat_id INTEGER NOT NULL,
                admin_message_id INTEGER NOT NULL,
                user_chat_id INTEGER NOT NULL,
                user_message_id INTEGER NOT NULL,
                created_at INTEGER NOT NULL,
                PRIMARY KEY (admin_chat_id, admin_message_id)
            )
            """
        )
        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS bot_state (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )
        self.connection.commit()

    def save_mapping(
        self,
        admin_chat_id: int,
        admin_message_id: int,
        user_chat_id: int,
        user_message_id: int,
    ) -> None:
        self.connection.execute(
            """
            INSERT OR REPLACE INTO message_map (
                admin_chat_id,
                admin_message_id,
                user_chat_id,
                user_message_id,
                created_at
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (admin_chat_id, admin_message_id, user_chat_id, user_message_id, int(time.time())),
        )
        self.connection.commit()

    def find_user(
        self,
        admin_chat_id: int,
        admin_message_id: int,
    ) -> tuple[int, int] | None:
        row = self.connection.execute(
            """
            SELECT user_chat_id, user_message_id
            FROM message_map
            WHERE admin_chat_id = ? AND admin_message_id = ?
            """,
            (admin_chat_id, admin_message_id),
        ).fetchone()
        if row is None:
            return None
        return int(row[0]), int(row[1])

    def get_update_offset(self) -> int | None:
        row = self.connection.execute(
            "SELECT value FROM bot_state WHERE key = 'update_offset'"
        ).fetchone()
        if row is None:
            return None
        return int(row[0])

    def save_update_offset(self, offset: int) -> None:
        self.connection.execute(
            """
            INSERT OR REPLACE INTO bot_state (key, value)
            VALUES ('update_offset', ?)
            """,
            (str(offset),),
        )
        self.connection.commit()


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def parse_support_chat_id(value: str) -> int | None:
    value = value.strip()
    if not value:
        return None
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError("SUPPORT_CHAT_ID must be a numeric Telegram chat_id, usually like -1001234567890.") from exc


def load_config() -> Config:
    load_dotenv(Path(".env"))

    token = os.environ.get("BOT_TOKEN", "").strip()
    support_chat_id = parse_support_chat_id(os.environ.get("SUPPORT_CHAT_ID", ""))
    database_path = Path(os.environ.get("DATABASE_PATH", "support_bot.sqlite3"))

    if not token:
        raise ValueError("BOT_TOKEN is empty. Add it to .env or environment variables.")

    return Config(
        token=token,
        support_chat_id=support_chat_id,
        database_path=database_path,
    )


def get_chat_id(message: dict[str, Any]) -> int:
    return int(message["chat"]["id"])


def get_message_id(message: dict[str, Any]) -> int:
    return int(message["message_id"])


def has_content(message: dict[str, Any]) -> bool:
    return any(field in message for field in CONTENT_FIELDS)


def command_name(message: dict[str, Any]) -> str | None:
    text = message.get("text")
    if not isinstance(text, str) or not text.startswith("/"):
        return None
    command = text.split(maxsplit=1)[0].split("@", 1)[0]
    return command.lower()


def user_label(message: dict[str, Any]) -> str:
    user = message.get("from") or {}
    first_name = user.get("first_name", "")
    last_name = user.get("last_name", "")
    full_name = " ".join(part for part in [first_name, last_name] if part).strip()
    username = user.get("username")

    parts = []
    if full_name:
        parts.append(full_name)
    if username:
        parts.append(f"@{username}")
    if not parts:
        parts.append("Без имени")
    return " ".join(parts)


def build_admin_header(message: dict[str, Any]) -> str:
    user = message.get("from") or {}
    chat_id = get_chat_id(message)
    message_id = get_message_id(message)
    language = user.get("language_code") or "-"

    return (
        "Новый вопрос\n"
        f"От: {user_label(message)}\n"
        f"user_id: {user.get('id', '-')}\n"
        f"chat_id: {chat_id}\n"
        f"message_id: {message_id}\n"
        f"language: {language}\n\n"
        "Чтобы ответить клиенту, нажмите Reply на это сообщение или на сообщение ниже."
    )


def handle_start(bot: TelegramBot, config: Config, message: dict[str, Any]) -> None:
    chat_id = get_chat_id(message)
    text = "Здравствуйте! Напишите сюда ваш вопрос, и оператор ответит вам в этом чате."
    if config.support_chat_id is None:
        text += "\n\nКанал поддержки пока не настроен. Добавьте SUPPORT_CHAT_ID в .env."
    bot.send_message(chat_id, text, get_message_id(message))


def handle_myid(bot: TelegramBot, message: dict[str, Any]) -> None:
    chat_id = get_chat_id(message)
    user_id = message.get("from", {}).get("id", "-")
    text = f"chat_id: {chat_id}\nuser_id: {user_id}"
    bot.send_message(chat_id, text, get_message_id(message))


def handle_user_message(
    bot: TelegramBot,
    store: MessageStore,
    config: Config,
    message: dict[str, Any],
) -> None:
    user_chat_id = get_chat_id(message)
    user_message_id = get_message_id(message)

    if config.support_chat_id is None:
        bot.send_message(
            user_chat_id,
            "Оператор пока не настроен. Добавьте SUPPORT_CHAT_ID в .env и перезапустите бота.",
            user_message_id,
        )
        return

    if not has_content(message):
        bot.send_message(user_chat_id, "Я могу передать оператору текст, фото, файлы и другие обычные сообщения.")
        return

    delivered = 0
    try:
        header_id = bot.send_message(config.support_chat_id, build_admin_header(message))
        store.save_mapping(config.support_chat_id, header_id, user_chat_id, user_message_id)

        copied_id = bot.copy_message(config.support_chat_id, user_chat_id, user_message_id)
        store.save_mapping(config.support_chat_id, copied_id, user_chat_id, user_message_id)
        delivered += 1
    except TelegramError as exc:
        print(f"Failed to deliver message {user_message_id} to support channel {config.support_chat_id}: {exc}", flush=True)

    if delivered:
        bot.send_message(
            user_chat_id,
            "Спасибо, вопрос передан оператору. Ответ придет сюда.",
            user_message_id,
        )
    else:
        bot.send_message(
            user_chat_id,
            "Не получилось передать сообщение оператору. Пожалуйста, попробуйте позже.",
            user_message_id,
        )


def handle_channel_post(
    bot: TelegramBot,
    store: MessageStore,
    config: Config,
    message: dict[str, Any],
) -> None:
    channel_chat_id = get_chat_id(message)
    channel_message_id = get_message_id(message)

    command = command_name(message)
    if command == "/myid":
        handle_myid(bot, message)
        return

    if config.support_chat_id is not None and channel_chat_id != config.support_chat_id:
        return

    reply_to = message.get("reply_to_message")

    if not reply_to:
        return

    target = store.find_user(channel_chat_id, int(reply_to["message_id"]))
    if target is None:
        return

    user_chat_id, _ = target
    try:
        bot.copy_message(user_chat_id, channel_chat_id, channel_message_id)
    except TelegramError as exc:
        text = message.get("text") or message.get("caption")
        if not text:
            bot.send_message(
                channel_chat_id,
                f"Не удалось отправить этот тип сообщения клиенту: {exc}",
            )
            return
        try:
            bot.send_message(user_chat_id, text)
        except TelegramError as fallback_exc:
            bot.send_message(
                channel_chat_id,
                f"Не удалось отправить ответ клиенту: {fallback_exc}",
            )
            return


def handle_message(
    bot: TelegramBot,
    store: MessageStore,
    config: Config,
    message: dict[str, Any],
) -> None:
    command = command_name(message)
    if command == "/start":
        handle_start(bot, config, message)
        return
    if command == "/myid":
        handle_myid(bot, message)
        return

    handle_user_message(bot, store, config, message)


def run() -> None:
    config = load_config()
    bot = TelegramBot(config.token, config.request_timeout)
    store = MessageStore(config.database_path)
    offset = store.get_update_offset()

    if config.support_chat_id is None:
        print("Warning: SUPPORT_CHAT_ID is empty. The /myid command works, but client messages will not be delivered.", flush=True)
    print("Support bot is running. Press Ctrl+C to stop.", flush=True)
    while True:
        try:
            updates = bot.get_updates(offset, config.polling_timeout)
            for update in updates:
                offset = int(update["update_id"]) + 1
                message = update.get("message")
                if message:
                    handle_message(bot, store, config, message)
                channel_post = update.get("channel_post")
                if channel_post:
                    handle_channel_post(bot, store, config, channel_post)
                store.save_update_offset(offset)
        except KeyboardInterrupt:
            print("Support bot stopped.", flush=True)
            break
        except Exception as exc:
            print(f"Runtime error: {exc}", flush=True)
            time.sleep(3)


if __name__ == "__main__":
    run()
