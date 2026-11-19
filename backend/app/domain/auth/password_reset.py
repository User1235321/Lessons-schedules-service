from dataclasses import dataclass, field
from datetime import datetime

from app.domain.shared.ids import UserId


@dataclass(frozen=True)
class PasswordResetToken:
    user_id: UserId
    token_hash: str = field(repr=False)
    expires_at: datetime
