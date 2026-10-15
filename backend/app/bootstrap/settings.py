from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Настройки из переменных окружения. Имена совпадают с .env.example."""

    # .env лежит в корне репозитория, а бэкенд обычно запускают из каталога backend
    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"), env_file_encoding="utf-8", extra="ignore"
    )

    database_url: str = "postgresql+psycopg://schedules:schedules@localhost:5432/schedules"
    database_echo: bool = False

    redis_url: str = "redis://localhost:6379/0"
    kafka_bootstrap_servers: str = "localhost:9092"

    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minio"
    minio_secret_key: str = "minio123"
    minio_bucket: str = "lessons-schedules"

    jwt_secret: str = "change-me"
    access_token_ttl_minutes: int = 15
    refresh_token_ttl_days: int = 30

    mail_host: str = ""
    mail_port: int = 587
    mail_username: str = ""
    mail_password: str = ""
    mail_from: str = ""
