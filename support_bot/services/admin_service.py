from ..database import Database


class AdminService:
    def __init__(self, database: Database) -> None:
        self.database = database

    async def log_action(self, admin_id: int, ticket_id: int, action: str) -> None:
        await self.database.execute(
            """
            INSERT INTO admin_actions (admin_id, ticket_id, action)
            VALUES (?, ?, ?)
            """,
            (admin_id, ticket_id, action),
        )
