from collections.abc import Mapping

from aiogram.types import User

from ..database import Database
from .user_service import UserService


class FeedbackService:
    def __init__(self, database: Database, user_service: UserService) -> None:
        self.database = database
        self.user_service = user_service

    async def create_feedback(self, user: User, text: str) -> int:
        user_id = await self.user_service.ensure_user(user)
        return await self.database.execute(
            "INSERT INTO feedback (user_id, text) VALUES (?, ?)",
            (user_id, text),
        )

    async def count_feedback(self) -> int:
        row = await self.database.fetchone("SELECT COUNT(*) AS count FROM feedback")
        return int(row["count"] if row else 0)

    async def get_recent_feedback(self, limit: int = 20) -> list[Mapping[str, object]]:
        return await self.database.fetchall(
            """
            SELECT
                f.*,
                u.telegram_id,
                u.username,
                u.first_name
            FROM feedback f
            JOIN users u ON u.id = f.user_id
            ORDER BY f.id DESC
            LIMIT ?
            """,
            (limit,),
        )
