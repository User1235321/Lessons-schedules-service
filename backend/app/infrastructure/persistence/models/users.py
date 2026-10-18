from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.auth.user import MAX_EMAIL_LENGTH
from app.infrastructure.persistence.base import Base


class UserRow(Base):
    __tablename__ = "users"
    __table_args__ = (
        # Домен приводит адрес к нижнему регистру, тогда UNIQUE не пропустит
        # Ivan@mail.ru рядом с ivan@mail.ru (F_Auth_3).
        CheckConstraint("email = lower(email)", name="email_lowercase"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(MAX_EMAIL_LENGTH), unique=True)
    password_hash: Mapped[str]
    created_at: Mapped[datetime]


class UserSessionRow(Base):
    __tablename__ = "user_sessions"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    # Сессию находят по хешу присланного refresh-токена
    refresh_token_hash: Mapped[str] = mapped_column(unique=True)
    created_at: Mapped[datetime]
    expires_at: Mapped[datetime]
    revoked_at: Mapped[datetime | None]
