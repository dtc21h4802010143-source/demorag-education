from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "EduChat RAG"
    app_env: str = "dev"
    secret_key: str = "change-me"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24

    database_url: str = "sqlite:///./app.db"

    chroma_persist_dir: str = "./chroma_data"
    chroma_collection: str = "edu_documents"

    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"

    llm_provider: str = "groq"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"

    rag_top_k: int = 4
    rag_chunk_size_words: int = 500
    rag_chunk_overlap_words: int = 50
    rag_candidate_pool: int = 24
    rag_hybrid_alpha: float = 0.55
    rag_enable_hybrid: bool = True
    rag_enable_query_expansion: bool = True
    rag_enable_rerank: bool = False
    rag_reranker_model: str = "cross-encoder/stsb-xlm-r-multilingual"
    rag_query_expansion_limit: int = 2
    rag_min_confidence: float = 0.22
    rag_min_context_count: int = 1
    rag_temperature: float = 0.2
    rag_max_output_tokens: int = 500

    admin_username: str = "admin"
    admin_password: str = "admin123"
    user_username: str = "student"
    user_password: str = "123456"
    anonymous_question_limit: int = 5

    # Email settings for password recovery
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from_email: str = "noreply@educhat.com"
    smtp_from_name: str = "EduChat"
    password_reset_token_expire_minutes: int = 30
    frontend_password_reset_url: str = "http://localhost:5173/reset-password"

    cors_origins: str = "http://localhost:5173"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


@lru_cache
def get_settings() -> Settings:
    return Settings()
