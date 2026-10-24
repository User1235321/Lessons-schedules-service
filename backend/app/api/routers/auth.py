from fastapi import APIRouter, Response

from app.api.cookies import RefreshTokenCookie
from app.api.deps import CurrentUserDep, RefreshCookieDep, UseCasesDep
from app.api.schemas.auth import AccessTokenResponse, CredentialsRequest, UserResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", status_code=201)
def register(
    body: CredentialsRequest, response: Response, use_cases: UseCasesDep, cookie: RefreshCookieDep
) -> AccessTokenResponse:
    tokens = use_cases.register().execute(body.to_credentials())
    cookie.set(response, tokens)
    return AccessTokenResponse.of(tokens)


@router.post("/login")
def login(
    body: CredentialsRequest, response: Response, use_cases: UseCasesDep, cookie: RefreshCookieDep
) -> AccessTokenResponse:
    tokens = use_cases.login().execute(body.to_credentials())
    cookie.set(response, tokens)
    return AccessTokenResponse.of(tokens)


@router.post("/refresh")
def refresh(
    response: Response,
    use_cases: UseCasesDep,
    cookie: RefreshCookieDep,
    refresh_token: RefreshTokenCookie = None,
) -> AccessTokenResponse:
    tokens = use_cases.refresh().execute(refresh_token)
    cookie.set(response, tokens)
    return AccessTokenResponse.of(tokens)


@router.post("/logout", status_code=204)
def logout(
    response: Response,
    use_cases: UseCasesDep,
    cookie: RefreshCookieDep,
    refresh_token: RefreshTokenCookie = None,
) -> None:
    use_cases.logout().execute(refresh_token)
    cookie.clear(response)


@router.get("/me")
def me(user_id: CurrentUserDep, use_cases: UseCasesDep) -> UserResponse:
    return UserResponse.of(use_cases.get_current_user().execute(user_id))
