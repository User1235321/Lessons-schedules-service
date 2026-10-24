from dataclasses import dataclass
from datetime import datetime, timedelta

from app.domain.shared.ids import SessionId, UserId


@dataclass(kw_only=True)
class UserSession:
    """Refresh-сессия пользователя (HLD 8, 9.2).

    Сам refresh-токен не хранится: по утёкшей базе нельзя войти от чужого имени.
    """

    id: SessionId
    user_id: UserId
    refresh_token_hash: str
    created_at: datetime
    expires_at: datetime
    revoked_at: datetime | None = None

    @classmethod
    def open(
        cls,
        *,
        session_id: SessionId,
        user_id: UserId,
        refresh_token_hash: str,
        now: datetime,
        ttl: timedelta,
    ) -> "UserSession":
        return cls(
            id=session_id,
            user_id=user_id,
            refresh_token_hash=refresh_token_hash,
            created_at=now,
            expires_at=now + ttl,
        )

    def is_active(self, now: datetime) -> bool:
        return self.revoked_at is None and now < self.expires_at

    def rotate(self, refresh_token_hash: str) -> None:
        """Меняет refresh-токен на новый, старый перестаёт действовать.

        Срок сессии не продлевается: через ttl после входа нужно войти снова.
        """
        self.refresh_token_hash = refresh_token_hash

    def revoke(self, now: datetime) -> None:
        # Повторный выход ничего не меняет: время первого отзыва сохраняется.
        if self.revoked_at is None:
            self.revoked_at = now
