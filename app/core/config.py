from pydantic_settings import (
    BaseSettings,
    SettingsConfigDict,
)


class Settings(BaseSettings):
    """
    项目配置类。

    配置值会从 .env 文件中读取。
    """

    app_env: str = "development"

    database_url: str

    redis_url: str = "redis://127.0.0.1:6379/0"

    llm_base_url: str = "http://localhost:11434/v1/"

    llm_api_key: str = "ollama"

    llm_model: str = "qwen2.5:7b"

    llm_mock_mode: bool = True

    rag_min_relevance_score: float = 0.08

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
