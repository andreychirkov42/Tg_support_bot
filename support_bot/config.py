from dataclasses import dataclass
from os import getenv
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

TICKET_STATUSES = {"new", "in_progress", "closed"}

STATUS_LABELS = {
    "new": "Новое",
    "in_progress": "В работе",
    "closed": "Закрыто",
}

STATUS_EMOJI = {
    "new": "🆕",
    "in_progress": "🟡",
    "closed": "✅",
}


def _parse_admin_ids(raw_value: str | None) -> frozenset[int]:
    if not raw_value:
        return frozenset()

    admin_ids: set[int] = set()
    for item in raw_value.split(","):
        value = item.strip()
        if value:
            admin_ids.add(int(value))
    return frozenset(admin_ids)


def _parse_optional_int(raw_value: str | None) -> int | None:
    if raw_value is None or not raw_value.strip():
        return None
    return int(raw_value.strip())


@dataclass(frozen=True)
class Config:
    bot_token: str
    admin_chat_id: int | None
    admin_ids: frozenset[int]
    database_path: Path


def load_config() -> Config:
    bot_token = getenv("BOT_TOKEN", "").strip()
    if not bot_token:
        raise RuntimeError("BOT_TOKEN is empty. Set it in support_bot/.env.")

    return Config(
        bot_token=bot_token,
        admin_chat_id=_parse_optional_int(getenv("ADMIN_CHAT_ID")),
        admin_ids=_parse_admin_ids(getenv("ADMIN_IDS")),
        database_path=BASE_DIR / "support_bot.sqlite3",
    )
