from typing import Literal, Self

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Ключ из .env.example известен всем, кто видел репозиторий: подходит только для разработки
DEV_JWT_SECRET = "dev-only-secret-replace-in-production"


class Settings(BaseSettings):
    """Настройки из переменных окружения. Имена совпадают с .env.example.

    Без APP_ENV сервер считает себя боевым и не стартует с небезопасными настройками.
    Для разработки APP_ENV=development задан в .env.example.
    """

    # .env лежит в корне репозитория, а бэкенд обычно запускают из каталога backend
    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"), env_file_encoding="utf-8", extra="ignore"
    )

    app_env: Literal["development", "production"] = "production"

    database_url: str = "postgresql+psycopg://schedules:schedules@localhost:5432/schedules"
    database_echo: bool = False

    redis_url: str = "redis://localhost:6379/0"
    kafka_bootstrap_servers: str = "localhost:9092"

    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minio"
    minio_secret_key: str = "minio123"
    minio_bucket: str = "lessons-schedules"

    # HS256 требует ключ не короче 32 байт (RFC 7518, 3.2), с коротким PyJWT предупреждает
    jwt_secret: str = Field(DEV_JWT_SECRET, min_length=32)
    access_token_ttl_minutes: int = 15
    refresh_token_ttl_days: int = 30
    # false — только для разработки по http, если браузер не сохраняет Secure-cookie
    refresh_cookie_secure: bool = True

    mail_host: str = ""
    mail_port: int = 587
    mail_username: str = ""
    mail_password: str = ""
    mail_from: str = ""

    @model_validator(mode="after")
    def _refuse_unsafe_production(self) -> Self:
        if self.app_env != "production":
            return self
        if self.jwt_secret == DEV_JWT_SECRET:
            raise ValueError(
                "В production нужен собственный JWT_SECRET (например, openssl rand -hex 32). "
                "Для локальной разработки задайте APP_ENV=development"
            )
        if not self.refresh_cookie_secure:
            raise ValueError("В production REFRESH_COOKIE_SECURE должен быть true")
        return self
