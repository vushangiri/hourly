"""PostgreSQL persistence. Never delete financial history through cascading FKs."""
from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import (String, Text, DateTime, Date, Integer, Numeric, Boolean,
                        ForeignKey, UniqueConstraint, CheckConstraint, Index)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def now():
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = 'users'
    id: Mapped[object] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(254), unique=True)
    phone: Mapped[str] = mapped_column(String(20), unique=True)
    password_hash: Mapped[str] = mapped_column(Text)
    timezone: Mapped[str] = mapped_column(String(80), default='Australia/Sydney')
    session_version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Workplace(Base):
    __tablename__ = 'workplaces'
    id: Mapped[object] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[object] = mapped_column(ForeignKey('users.id'), index=True)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(String(500), default='')
    contact: Mapped[str] = mapped_column(String(200), default='')
    archived: Mapped[bool] = mapped_column(Boolean, default=False)
    revision: Mapped[int] = mapped_column(Integer, default=1)
    # Next local start-date to reconcile; recovery proceeds in bounded batches.
    cursor: Mapped[object] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Schedule(Base):
    __tablename__ = 'schedule_revisions'
    id: Mapped[object] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    workplace_id: Mapped[object] = mapped_column(ForeignKey('workplaces.id'), index=True)
    revision: Mapped[int] = mapped_column(Integer)
    effective_date: Mapped[object] = mapped_column(Date)
    config: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (UniqueConstraint('workplace_id', 'revision'),)


class Shift(Base):
    __tablename__ = 'shifts'
    id: Mapped[object] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    workplace_id: Mapped[object] = mapped_column(ForeignKey('workplaces.id'))
    local_date: Mapped[object] = mapped_column(Date)
    slot: Mapped[str] = mapped_column(String(40), default='scheduled')
    start_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    end_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    timezone: Mapped[str] = mapped_column(String(80))
    break_minutes: Mapped[int] = mapped_column(Integer, default=0)
    net_seconds: Mapped[int] = mapped_column(Integer, default=0)
    rate: Mapped[object] = mapped_column(Numeric(12, 2))
    earnings: Mapped[object] = mapped_column(Numeric(14, 2))
    status: Mapped[str] = mapped_column(String(16))
    origin: Mapped[str] = mapped_column(String(16))
    revision: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (
        UniqueConstraint('workplace_id', 'local_date', 'slot'),
        CheckConstraint("status IN ('manual','auto','off','planned')"),
        CheckConstraint("origin IN ('manual','auto')"),
        CheckConstraint('net_seconds >= 0 AND break_minutes >= 0 AND rate >= 0 AND earnings >= 0'),
        CheckConstraint("status = 'off' OR (end_at > start_at AND start_at IS NOT NULL AND end_at IS NOT NULL)"),
        Index('ix_shift_workplace_date', 'workplace_id', 'local_date'),
    )


class ShiftAudit(Base):
    __tablename__ = 'shift_revisions'
    id: Mapped[int] = mapped_column(primary_key=True)
    shift_id: Mapped[object] = mapped_column(ForeignKey('shifts.id'), index=True)
    actor_id: Mapped[object | None] = mapped_column(ForeignKey('users.id'), nullable=True)
    action: Mapped[str] = mapped_column(String(30))
    snapshot: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Payment(Base):
    __tablename__ = 'payment_confirmations'
    id: Mapped[object] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    workplace_id: Mapped[object] = mapped_column(ForeignKey('workplaces.id'), index=True)
    period_start: Mapped[object] = mapped_column(Date)
    period_end: Mapped[object] = mapped_column(Date)
    paid_date: Mapped[object] = mapped_column(Date)
    actual_amount: Mapped[object | None] = mapped_column(Numeric(14, 2), nullable=True)
    confirmed_estimate: Mapped[object] = mapped_column(Numeric(14, 2))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (UniqueConstraint('workplace_id', 'period_start', 'period_end'),
                     CheckConstraint('period_end >= period_start'),)


class Idempotency(Base):
    __tablename__ = 'idempotency_keys'
    user_id: Mapped[object] = mapped_column(ForeignKey('users.id'), primary_key=True)
    key: Mapped[object] = mapped_column(UUID(as_uuid=True), primary_key=True)
    fingerprint: Mapped[str] = mapped_column(String(64))
    response: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class LoginBucket(Base):
    __tablename__ = 'login_buckets'
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    count: Mapped[int] = mapped_column(Integer)
    expires: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class ResetToken(Base):
    __tablename__ = 'reset_tokens'
    digest: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[object] = mapped_column(ForeignKey('users.id'), index=True)
    expires: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used: Mapped[bool] = mapped_column(Boolean, default=False)
