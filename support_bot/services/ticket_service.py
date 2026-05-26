from collections.abc import Mapping

from aiogram.types import User

from ..database import Database


class TicketService:
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
        row = await self.database.fetchone("SELECT id FROM users WHERE telegram_id = ?", (user.id,))
        if row is None:
            raise RuntimeError("Failed to create or load user")
        return int(row["id"])

    async def create_ticket(self, user: User, category: str, text: str) -> int:
        user_id = await self.ensure_user(user)
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
        touch_ticket: bool = True,
    ) -> None:
        await self.database.execute(
            """
            INSERT INTO messages (ticket_id, sender_type, sender_id, text)
            VALUES (?, ?, ?, ?)
            """,
            (ticket_id, sender_type, sender_id, text),
        )
        if touch_ticket:
            await self.database.execute(
                "UPDATE tickets SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (ticket_id,),
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

    async def get_ticket(self, ticket_id: int) -> Mapping[str, object] | None:
        return await self.database.fetchone(
            """
            SELECT
                t.*,
                u.telegram_id,
                u.username,
                u.first_name
            FROM tickets t
            JOIN users u ON u.id = t.user_id
            WHERE t.id = ?
            """,
            (ticket_id,),
        )

    async def get_ticket_messages(self, ticket_id: int, limit: int = 10) -> list[Mapping[str, object]]:
        return await self.database.fetchall(
            """
            SELECT *
            FROM messages
            WHERE ticket_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (ticket_id, limit),
        )

    async def get_tickets_by_status(self, status: str, limit: int = 30) -> list[Mapping[str, object]]:
        return await self.database.fetchall(
            """
            SELECT
                t.*,
                u.telegram_id,
                u.username,
                u.first_name
            FROM tickets t
            JOIN users u ON u.id = t.user_id
            WHERE t.status = ?
            ORDER BY t.updated_at DESC, t.id DESC
            LIMIT ?
            """,
            (status, limit),
        )

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
        return stats

