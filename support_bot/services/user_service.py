from collections.abc import Mapping

from aiogram.types import User

from ..database import Database


class UserService:
    def __init__(self, database: Database) -> None:
        self.database = database

    async def ensure_user(self, user: User) -> int:
        await self.database.execute(
            """
            INSERT INTO users (telegram_id, username, first_name)
            VALUES (?, ?, ?)
            ON CONFLICT(telegram_id) DO UPDATE SET
                username = excluded.username,
                first_name = excluded.first_name
            """,
            (user.id, user.username, user.first_name),
        )
        row = await self.get_by_telegram_id(user.id)
        if row is None:
            raise RuntimeError("Failed to create or load user")
        return int(row["id"])

    async def get_by_telegram_id(self, telegram_id: int) -> Mapping[str, object] | None:
        return await self.database.fetchone(
            "SELECT * FROM users WHERE telegram_id = ?",
            (telegram_id,),
        )

    async def is_blocked(self, telegram_id: int) -> bool:
        row = await self.get_by_telegram_id(telegram_id)
        return bool(row and row["is_blocked"])

    async def set_blocked(self, telegram_id: int, blocked: bool) -> None:
        await self.database.execute(
            "UPDATE users SET is_blocked = ? WHERE telegram_id = ?",
            (1 if blocked else 0, telegram_id),
        )

    async def count_users(self) -> int:
        row = await self.database.fetchone("SELECT COUNT(*) AS count FROM users")
        return int(row["count"] if row else 0)

    async def count_blocked_users(self) -> int:
        row = await self.database.fetchone("SELECT COUNT(*) AS count FROM users WHERE is_blocked = 1")
        return int(row["count"] if row else 0)
