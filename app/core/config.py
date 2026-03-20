# 환경변수 및 설정
from urllib.parse import quote
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "CodoC-AI"
    VERSION: str = "2.0.0"
    API_PREFIX: str = "/api/v2"

    # --- RabbitMQ 설정 ---
    APP_NOTIFICATION_MQ_ENABLED: bool = False
    RABBITMQ_HOST: str = "localhost"
    RABBITMQ_PORT: int = 5672
    RABBITMQ_USERNAME: str = "guest"
    RABBITMQ_PASSWORD: str = "guest"
    RABBITMQ_VHOST: str = "/"

    @property
    def RABBITMQ_URL(self) -> str:
        vhost = (self.RABBITMQ_VHOST or "/").strip()
        if vhost == "/":
            encoded_vhost = "%2F"
        else:
            encoded_vhost = quote(vhost.lstrip("/"), safe="")
        return (
            f"amqp://{self.RABBITMQ_USERNAME}:{self.RABBITMQ_PASSWORD}"
            f"@{self.RABBITMQ_HOST}:{self.RABBITMQ_PORT}/{encoded_vhost}"
        )

    # --- Vector DB (Qdrant) 설정 ---
    QDRANT_HOST: str = "localhost"
    QDRANT_PORT: int = 6444
    QDRANT_API_KEY: str | None = None

    # --- Postgre 설정 ---
    PG_HOST: str = "localhost"
    PG_PORT: int = 5432
    PG_USER: str = "user"
    PG_PASSWORD: str = "postgres"
    PG_DATABASE: str = "codoc"

    # Report LLM
    REPORT_LLM_BASE_URL: str = "http://localhost:8001/v1"
    REPORT_LLM_API_KEY: str = "EMPTY"
    REPORT_LLM_MODEL: str = "Qwen/Qwen2.5-32B-Instruct-AWQ"
    REPORT_LLM_TIMEOUT_SEC: float = 30.0

    # Recommend LLM
    RECOMMEND_LLM_BASE_URL: str = "http://localhost:8001/v1"
    RECOMMEND_LLM_API_KEY: str = "EMPTY"
    RECOMMEND_LLM_MODEL: str = "Qwen/Qwen2.5-32B-Instruct-AWQ"
    LLM_INPUT_TOKEN_PRICE_PER_MILLION_USD: float = 0.0
    LLM_OUTPUT_TOKEN_PRICE_PER_MILLION_USD: float = 0.0
    RECOMMEND_LLM_TIMEOUT_SEC: float = 20.0
    RECOMMEND_LLM_MAX_CONCURRENCY: int = 8
    RECOMMEND_LLM_ACQUIRE_TIMEOUT_SEC: float = 2.0

    @property
    def QDRANT_URL(self) -> str:
        return f"http://{self.QDRANT_HOST}:{self.QDRANT_PORT}"

    # .env 파일을 읽어오기 위한 설정
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=True, extra="ignore"
    )


settings = Settings()
