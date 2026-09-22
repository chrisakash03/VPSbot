from __future__ import annotations

from sqlalchemy import inspect, text
from sqlalchemy.engine import Connection


def run_sqlite_migrations(connection: Connection) -> None:
    inspector = inspect(connection)
    if inspector.has_table("reminders"):
        cols = {c["name"] for c in inspector.get_columns("reminders")}
        if "notify_chat_id" not in cols:
            connection.execute(
                text("ALTER TABLE reminders ADD COLUMN notify_chat_id BIGINT")
            )
            connection.execute(
                text("UPDATE reminders SET notify_chat_id = chat_id WHERE notify_chat_id IS NULL")
            )

    if inspector.has_table("pending_reminders"):
        cols = {c["name"] for c in inspector.get_columns("pending_reminders")}
        if "notify_chat_id" not in cols:
            connection.execute(
                text("ALTER TABLE pending_reminders ADD COLUMN notify_chat_id BIGINT")
            )
            connection.execute(
                text(
                    "UPDATE pending_reminders SET notify_chat_id = chat_id "
                    "WHERE notify_chat_id IS NULL"
                )
            )
