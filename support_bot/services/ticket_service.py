from collections.abc import Mapping

from aiogram.types import User

from ..database import Database
from .user_service import UserService


class TicketService:
    def __init__(self, database: Database, user_service: UserService) -> None:
        self.database = database
        self.user_service = user_service

    async def create_ticket(self, user: User, category: str, text: str) -> int:
        user_id = await self.user_service.ensure_user(user)
        ticket_id = await self.database.execute(
            """
            INSERT INTO tickets (user_id, category, text, status)
            VALUES (?, ?, ?, 'new')
            """,
            (user_id, category, text),
        )
        await self.add_message(ticket_id, "user", user.id, text, touch_ticket=False)
        return ticket_id

    async def add_message(
        self,
        ticket_id: int,
        sender_type: str,
        sender_id: int,
        text: str,
        *,
        admin_message_id: int | None = None,
        touch_ticket: bool = True,
    ) -> int:
        message_id = await self.database.execute(
            """
            INSERT INTO messages (ticket_id, sender_type, sender_id, text, admin_message_id)
            VALUES (?, ?, ?, ?, ?)
            """,
            (ticket_id, sender_type, sender_id, text, admin_message_id),
        )
        if touch_ticket:
            await self.touch_ticket(ticket_id)
        return message_id

    async def update_message_admin_id(self, message_id: int, admin_message_id: int) -> None:
        await self.database.execute(
            "UPDATE messages SET admin_message_id = ? WHERE id = ?",
            (admin_message_id, message_id),
        )

    async def touch_ticket(self, ticket_id: int) -> None:
        await self.database.execute(
            "UPDATE tickets SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (ticket_id,),
        )

    async def set_admin_message_id(self, ticket_id: int, admin_message_id: int) -> None:
        await self.database.execute(
            "UPDATE tickets SET admin_chat_message_id = ? WHERE id = ?",
            (admin_message_id, ticket_id),
        )

    async def create_reply_link(self, ticket_id: int, admin_chat_message_id: int) -> None:
        await self.database.execute(
            """
            INSERT OR REPLACE INTO reply_links (ticket_id, admin_chat_message_id)
            VALUES (?, ?)
            """,
            (ticket_id, admin_chat_message_id),
        )

    async def resolve_reply_link(self, admin_chat_message_id: int) -> int | None:
        row = await self.database.fetchone(
            "SELECT ticket_id FROM reply_links WHERE admin_chat_message_id = ?",
            (admin_chat_message_id,),
        )
        return int(row["ticket_id"]) if row else None

    async def get_ticket(self, ticket_id: int) -> Mapping[str, object] | None:
        return await self.database.fetchone(
            """
            SELECT
                t.*,
                u.telegram_id,
                u.username,
                u.first_name,
                u.is_blocked
            FROM tickets t
            JOIN users u ON u.id = t.user_id
            WHERE t.id = ?
            """,
            (ticket_id,),
        )

    async def get_ticket_for_user(self, ticket_id: int, telegram_id: int) -> Mapping[str, object] | None:
        return await self.database.fetchone(
            """
            SELECT t.*
            FROM tickets t
            JOIN users u ON u.id = t.user_id
            WHERE t.id = ? AND u.telegram_id = ?
            """,
            (ticket_id, telegram_id),
        )

    async def get_user_tickets(self, telegram_id: int, limit: int = 20) -> list[Mapping[str, object]]:
        return await self.database.fetchall(
            """
            SELECT t.*
            FROM tickets t
            JOIN users u ON u.id = t.user_id
            WHERE u.telegram_id = ?
            ORDER BY t.updated_at DESC, t.id DESC
            LIMIT ?
            """,
            (telegram_id, limit),
        )

    async def get_tickets_by_status(self, status: str, limit: int = 30) -> list[Mapping[str, object]]:
        return await self.database.fetchall(
            """
            SELECT
                t.*,
                u.telegram_id,
                u.username,
                u.first_name,
                u.is_blocked
            FROM tickets t
            JOIN users u ON u.id = t.user_id
            WHERE t.status = ?
            ORDER BY t.updated_at DESC, t.id DESC
            LIMIT ?
            """,
            (status, limit),
        )

    async def get_ticket_messages(self, ticket_id: int, limit: int = 20) -> list[Mapping[str, object]]:
        rows = await self.database.fetchall(
            """
            SELECT *
            FROM messages
            WHERE ticket_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (ticket_id, limit),
        )
        return list(reversed(rows))

    async def update_status(self, ticket_id: int, status: str) -> None:
        await self.database.execute(
            """
            UPDATE tickets
            SET status = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (status, ticket_id),
        )

    async def get_stats(self) -> dict[str, int]:
        rows = await self.database.fetchall(
            """
            SELECT status, COUNT(*) AS count
            FROM tickets
            GROUP BY status
            """
        )
        stats = {"new": 0, "in_progress": 0, "closed": 0, "total": 0}
        for row in rows:
            count = int(row["count"])
            stats[str(row["status"])] = count
            stats["total"] += count
        stats["users"] = await self.user_service.count_users()
        stats["blocked_users"] = await self.user_service.count_blocked_users()
        return stats
