from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/active_alpha"
    redis_url: str = "redis://localhost:6379/0"
    fmp_api_key: str = ""
    environment: str = "development"
    log_level: str = "INFO"

    # Pipeline schedule
    pipeline_hour: int = 7  # 7 AM ET
    pipeline_minute: int = 0

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
