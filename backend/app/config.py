from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/active_alpha"
    database_url_sync: str = "postgresql+psycopg2://postgres:postgres@localhost:5432/active_alpha"
    db_pool_size: int = 10
    db_max_overflow: int = 20

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # FMP API
    fmp_api_key: str = ""
    fmp_base_url: str = "https://financialmodelingprep.com/api/v3"
    fmp_max_concurrent: int = 5
    fmp_requests_per_minute: int = 250

    # Pipeline
    pipeline_batch_size: int = 10
    pipeline_max_retries: int = 3
    pipeline_schedule_hour: int = 7
    pipeline_schedule_timezone: str = "US/Eastern"

    # Benchmarks to track
    benchmark_tickers: list[str] = ["SPY", "QQQ", "IWM", "VTI"]

    # Admin
    admin_api_key: str = ""

    # App
    app_name: str = "Active Alpha"
    app_version: str = "0.1.0"
    environment: str = "development"
    log_level: str = "INFO"


settings = Settings()
