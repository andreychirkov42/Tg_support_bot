from dataclasses import dataclass
from os import getenv
from pathlib import Path

from dotenv import load_dotenv


load_dotenv()

BASE_DIR = Path(__file__).resolve().parent

STATUS_LABELS = {
    "new": "Новое",
    "in_progress": "В работе",
    "closed": "Закрыто",
}

STATUS_EMOJI = {
    "new": "🆕",
    "in_progress": "🔄",
    "closed": "✅",
}


def _parse_admin_ids(raw_value: str | None) -> frozenset[int]:
    if not raw_value:
        return frozenset()

    admin_ids: set[int] = set()
    for item in raw_value.split(","):
        item = item.strip()
        if item:
            admin_ids.add(int(item))
    return frozenset(admin_ids)


@dataclass(frozen=True)
class Config:
    bot_token: str
    admin_ids: frozenset[int]
    database_path: Path


def load_config() -> Config:
    bot_token = getenv("BOT_TOKEN", "").strip()
    if not bot_token:
        raise RuntimeError("BOT_TOKEN is empty. Create .env from .env.example and set your bot token.")

    return Config(
        bot_token=bot_token,
        admin_ids=_parse_admin_ids(getenv("ADMIN_IDS")),
        database_path=BASE_DIR / "support_bot.sqlite3",
    )

