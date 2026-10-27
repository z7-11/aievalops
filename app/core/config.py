from pydantic_settings import (
    BaseSettings,
    SettingsConfigDict,
)


class Settings(BaseSettings):
    """
    项目配置类。

    配置值会从 .env 文件中读取。
    """

    rag_retriever_type: str = "chroma"
    rag_embedding_model: str = "BAAI/bge-small-zh-v1.5"
    rag_chroma_path: str = "storage/chroma"
    rag_collection_name: str = "customer_service_bge_500_v1"
    rag_chunk_size: int = 500
    rag_chunk_overlap: int = 80
    rag_top_k: int = 3
    rag_vector_min_similarity_score: float = 0.45
    rag_prompt_version: str = "v1"

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
