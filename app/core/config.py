# 환경변수 및 설정

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
    RABBITMQ_EXCHANGE: str = "custom.problem.exchange"
    RABBITMQ_CONSUME_QUEUE: str = "custom.problem.request"
    RABBITMQ_PUBLISH_ROUTING_KEY: str = "custom.problem.response"

    # --- Vector DB (Qdrant) 설정 ---
    QDRANT_HOST: str = "localhost"
    QDRANT_PORT: int = 6333
    QDRANT_API_KEY: str | None = None

    # Report LLM
    REPORT_LLM_BASE_URL: str = "http://localhost:8001/v1"
    REPORT_LLM_API_KEY: str = "EMPTY"
    REPORT_LLM_MODEL: str = "Qwen/Qwen2.5-32B-Instruct-AWQ"

    # Recommend LLM
    RECOMMEND_LLM_BASE_URL: str = "http://localhost:8001/v1"
    RECOMMEND_LLM_API_KEY: str = "EMPTY"
    RECOMMEND_LLM_MODEL: str = "Qwen/Qwen2.5-32B-Instruct-AWQ"

    # OCR LLM
    OCR_LLM_BASE_URL: str = "http://localhost:8001/v1"
    OCR_LLM_API_KEY: str = "EMPTY"
    OCR_LLM_MODEL: str = "Qwen/Qwen2.5-VL-7B-Instruct"
    
    

    @property
    def QDRANT_URL(self) -> str:
        return f"http://{self.QDRANT_HOST}:{self.QDRANT_PORT}"

    # .env 파일을 읽어오기 위한 설정
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=True, extra="ignore"
    )


settings = Settings()
