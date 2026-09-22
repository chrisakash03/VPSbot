from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from sqlalchemy import BigInteger, Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from vpsbot.db.types import UTCDateTime


class Base(DeclarativeBase):
    pass


class RecurrenceKind(StrEnum):
    NONE = "none"
    DAILY = "daily"
    WEEKLY = "weekly"
    FORTNIGHTLY = "fortnightly"
    MONTHLY = "monthly"
    YEARLY = "yearly"
    INTERVAL = "interval"


class PendingReminder(Base):
    __tablename__ = "pending_reminders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    chat_id: Mapped[int] = mapped_column(BigInteger)
    notify_chat_id: Mapped[int] = mapped_column(BigInteger)
    spec_json: Mapped[str] = mapped_column(Text)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime(), index=True)


class Reminder(Base):
    __tablename__ = "reminders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, index=True)
    notify_chat_id: Mapped[int] = mapped_column(BigInteger, index=True)
    message: Mapped[str] = mapped_column(Text)
    next_fire_at: Mapped[datetime] = mapped_column(UTCDateTime(), index=True)
    recurrence: Mapped[str] = mapped_column(String(32), default=RecurrenceKind.NONE.value)
    recurrence_rule: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime())
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class Feed(Base):
    __tablename__ = "feeds"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    url: Mapped[str] = mapped_column(String(2048), unique=True)
    title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    last_seen_id: Mapped[str | None] = mapped_column(String(512), nullable=True)
    last_seen_published: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)


class RssQueueItem(Base):
    __tablename__ = "rss_queue"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    feed_id: Mapped[int] = mapped_column(ForeignKey("feeds.id"), index=True)
    guid: Mapped[str] = mapped_column(String(512))
    link: Mapped[str] = mapped_column(String(2048))
    title: Mapped[str] = mapped_column(String(1024))
    published_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    collected_at: Mapped[datetime] = mapped_column(UTCDateTime(), index=True)
    digested: Mapped[bool] = mapped_column(Boolean, default=False, index=True)

    feed: Mapped[Feed] = relationship()


class DigestSubscriber(Base):
    __tablename__ = "digest_subscribers"

    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    chat_id: Mapped[int] = mapped_column(BigInteger)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class DigestGroupState(Base):
    __tablename__ = "digest_group_state"

    group_chat_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)


class SchedulerAuditLog(Base):
    __tablename__ = "scheduler_audit"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[str] = mapped_column(String(128), index=True)
    reminder_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    scheduled_for: Mapped[datetime] = mapped_column(UTCDateTime())
    fired_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    event: Mapped[str] = mapped_column(String(64))
