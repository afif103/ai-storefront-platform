from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/saas_db"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Security
    SECRET_KEY: str = "local-dev-secret-change-me"

    # Cognito
    COGNITO_MOCK: bool = True
    COGNITO_USER_POOL_ID: str = ""
    COGNITO_CLIENT_ID: str = ""
    COGNITO_REGION: str = "me-south-1"

    # S3 / MinIO
    S3_BUCKET: str = ""
    S3_ENDPOINT_URL: str | None = None  # backend→MinIO (e.g. http://minio:9000)
    S3_PUBLIC_ENDPOINT: str | None = None  # browser→MinIO (e.g. http://localhost:9000)
    AWS_REGION: str = "me-south-1"
    AWS_ACCESS_KEY_ID: str | None = None
    AWS_SECRET_ACCESS_KEY: str | None = None

    # CORS
    ALLOWED_ORIGINS: str = "http://localhost:3000,http://localhost:8000"

    # Privacy
    IP_HASH_SALT: str = "change-me-in-production"

    # App
    ENVIRONMENT: str = "development"
    DEBUG: bool = False

    @property
    def allowed_origins_list(self) -> list[str]:
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",") if o.strip()]


settings = Settings()
