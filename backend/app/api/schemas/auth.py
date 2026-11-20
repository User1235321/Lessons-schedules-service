from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.application.auth.use_cases import AuthTokens, Credentials
from app.domain.auth.user import User


class CredentialsRequest(BaseModel):
    email: str
    password: str

    def to_credentials(self) -> Credentials:
        return Credentials(email=self.email, password=self.password)


class PasswordResetRequest(BaseModel):
    email: str


class PasswordResetRequested(BaseModel):
    message: str


class PasswordResetConfirmation(BaseModel):
    token: str = Field(repr=False)
    password: str = Field(repr=False)


class AccessTokenResponse(BaseModel):
    """Refresh-токен в тело не попадает: он приходит в httpOnly-cookie."""

    access_token: str
    token_type: Literal["bearer"] = "bearer"

    @classmethod
    def of(cls, tokens: AuthTokens) -> "AccessTokenResponse":
        return cls(access_token=tokens.access_token)


class UserResponse(BaseModel):
    id: UUID
    email: str

    @classmethod
    def of(cls, user: User) -> "UserResponse":
        return cls(id=user.id, email=user.email.value)
