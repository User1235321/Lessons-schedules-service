from fastapi import APIRouter

from app.api.deps import UseCasesDep
from app.api.schemas.auth import CredentialsRequest, TokensResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", status_code=201)
def register(body: CredentialsRequest, use_cases: UseCasesDep) -> TokensResponse:
    return TokensResponse.of(use_cases.register().execute(body.to_credentials()))


@router.post("/login")
def login(body: CredentialsRequest, use_cases: UseCasesDep) -> TokensResponse:
    return TokensResponse.of(use_cases.login().execute(body.to_credentials()))
