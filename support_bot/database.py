from pathlib import Path
from typing import Any

import aiosqlite


class Database:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._connection: aiosqlite.Connection | None = None

    async def connect(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = await aiosqlite.connect(self.path)
        self._connection.row_factory = aiosqlite.Row
        await self._connection.execute("PRAGMA foreign_keys = ON")
        await self._connection.commit()

    async def init_schema(self) -> None:
        connection = self._get_connection()
        await connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER NOT NULL UNIQUE,
                username TEXT,
                first_name TEXT,
                is_blocked INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS tickets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                category TEXT NOT NULL,
                text TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'new',
                admin_chat_message_id INTEGER,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_id INTEGER NOT NULL,
                sender_type TEXT NOT NULL,
                sender_id INTEGER NOT NULL,
                text TEXT NOT NULL,
                admin_message_id INTEGER,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (ticket_id) REFERENCES tickets(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS admin_actions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                admin_id INTEGER NOT NULL,
                ticket_id INTEGER NOT NULL,
                action TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS reply_links (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_id INTEGER NOT NULL,
                admin_chat_message_id INTEGER NOT NULL UNIQUE,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                text TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            """
        )
        await self._ensure_column("users", "is_blocked", "INTEGER NOT NULL DEFAULT 0")
        await self._ensure_column("tickets", "admin_chat_message_id", "INTEGER")
        await self._ensure_column("tickets", "updated_at", "TEXT")
        await self._ensure_column("messages", "admin_message_id", "INTEGER")
        await connection.execute(
            """
            UPDATE tickets
            SET updated_at = COALESCE(updated_at, created_at, CURRENT_TIMESTAMP)
            WHERE updated_at IS NULL
            """
        )
        await connection.executescript(
            """
            CREATE INDEX IF NOT EXISTS idx_users_telegram_id ON users(telegram_id);
            CREATE INDEX IF NOT EXISTS idx_users_is_blocked ON users(is_blocked);
            CREATE INDEX IF NOT EXISTS idx_tickets_user_id ON tickets(user_id);
            CREATE INDEX IF NOT EXISTS idx_tickets_status ON tickets(status);
            CREATE INDEX IF NOT EXISTS idx_tickets_admin_message ON tickets(admin_chat_message_id);
            CREATE INDEX IF NOT EXISTS idx_messages_ticket_id ON messages(ticket_id);
            CREATE INDEX IF NOT EXISTS idx_messages_admin_message ON messages(admin_message_id);
            CREATE INDEX IF NOT EXISTS idx_reply_links_message ON reply_links(admin_chat_message_id);
            CREATE INDEX IF NOT EXISTS idx_feedback_user_id ON feedback(user_id);
            """
        )
        await connection.commit()

    async def execute(self, query: str, parameters: tuple[Any, ...] = ()) -> int:
        connection = self._get_connection()
        cursor = await connection.execute(query, parameters)
        await connection.commit()
        lastrowid = cursor.lastrowid
        await cursor.close()
        return int(lastrowid or 0)

    async def fetchone(self, query: str, parameters: tuple[Any, ...] = ()) -> aiosqlite.Row | None:
        connection = self._get_connection()
        cursor = await connection.execute(query, parameters)
        row = await cursor.fetchone()
        await cursor.close()
        return row

    async def fetchall(self, query: str, parameters: tuple[Any, ...] = ()) -> list[aiosqlite.Row]:
        connection = self._get_connection()
        cursor = await connection.execute(query, parameters)
        rows = await cursor.fetchall()
        await cursor.close()
        return rows

    async def close(self) -> None:
        if self._connection is not None:
            await self._connection.close()
            self._connection = None

    async def _ensure_column(self, table: str, column: str, definition: str) -> None:
        connection = self._get_connection()
        cursor = await connection.execute(f"PRAGMA table_info({table})")
        columns = {str(row["name"]) for row in await cursor.fetchall()}
        await cursor.close()
        if column not in columns:
            await connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

    def _get_connection(self) -> aiosqlite.Connection:
        if self._connection is None:
            raise RuntimeError("Database is not connected")
        return self._connection
