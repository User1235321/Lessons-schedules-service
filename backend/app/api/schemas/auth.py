from typing import Literal

from pydantic import BaseModel

from app.application.auth.use_cases import AuthTokens, Credentials


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
