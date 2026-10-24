from fastapi import APIRouter

from app.api.deps import CurrentUserDep, UseCasesDep
from app.api.schemas.auth import (
    CredentialsRequest,
    RefreshTokenRequest,
    TokensResponse,
    UserResponse,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", status_code=201)
def register(body: CredentialsRequest, use_cases: UseCasesDep) -> TokensResponse:
    return TokensResponse.of(use_cases.register().execute(body.to_credentials()))


@router.post("/login")
def login(body: CredentialsRequest, use_cases: UseCasesDep) -> TokensResponse:
    return TokensResponse.of(use_cases.login().execute(body.to_credentials()))


@router.post("/refresh")
def refresh(body: RefreshTokenRequest, use_cases: UseCasesDep) -> TokensResponse:
    return TokensResponse.of(use_cases.refresh().execute(body.refresh_token))


@router.post("/logout", status_code=204)
def logout(body: RefreshTokenRequest, use_cases: UseCasesDep) -> None:
    use_cases.logout().execute(body.refresh_token)


@router.get("/me")
def me(user_id: CurrentUserDep, use_cases: UseCasesDep) -> UserResponse:
    return UserResponse.of(use_cases.get_current_user().execute(user_id))
