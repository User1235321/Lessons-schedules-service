from typing import Literal
from uuid import UUID

from pydantic import BaseModel

from app.application.auth.use_cases import AuthTokens, Credentials
from app.domain.auth.user import User


class CredentialsRequest(BaseModel):
    email: str
    password: str

    def to_credentials(self) -> Credentials:
        return Credentials(email=self.email, password=self.password)


class TokensResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: Literal["bearer"] = "bearer"

    @classmethod
    def of(cls, tokens: AuthTokens) -> "TokensResponse":
        return cls(access_token=tokens.access_token, refresh_token=tokens.refresh_token)


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class UserResponse(BaseModel):
    id: UUID
    email: str

    @classmethod
    def of(cls, user: User) -> "UserResponse":
        return cls(id=user.id, email=user.email.value)
