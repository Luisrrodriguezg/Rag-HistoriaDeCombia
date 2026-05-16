"""Centralised application settings, loaded from environment variables.

`Settings` is instantiated once (cached via `lru_cache`) and injected wherever
configuration is needed. Field defaults match `.env.example`, so the app boots
even if no env file is mounted — useful for unit tests.
"""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── Service identity ────────────────────────────────────
    app_name: str = "rag-historia-colombia-backend"
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    # ── Database ────────────────────────────────────────────
    database_url: str = Field(
        default="postgresql+asyncpg://rag:rag@db:5432/rag",
        alias="DATABASE_URL",
    )

    # ── Keycloak ────────────────────────────────────────────
    keycloak_realm: str = Field(default="rag", alias="KEYCLOAK_REALM")
    keycloak_client_id: str = Field(default="rag-frontend", alias="KEYCLOAK_CLIENT_ID")
    keycloak_internal_issuer: str = Field(
        default="http://keycloak:8080/realms/rag",
        alias="KEYCLOAK_INTERNAL_ISSUER",
    )
    keycloak_internal_jwks_url: str = Field(
        default="http://keycloak:8080/realms/rag/protocol/openid-connect/certs",
        alias="KEYCLOAK_INTERNAL_JWKS_URL",
    )
    # The `iss` claim issued by Keycloak reflects the browser-facing URL
    # (localhost), not the container-internal hostname.
    keycloak_external_issuer: str = Field(
        default="http://localhost:8080/realms/rag",
        alias="KEYCLOAK_EXTERNAL_ISSUER",
    )

    # ── Ollama ──────────────────────────────────────────────
    ollama_base_url: str = Field(default="http://ollama:11434", alias="OLLAMA_BASE_URL")
    ollama_llm_model: str = Field(default="llama3.1:8b", alias="OLLAMA_LLM_MODEL")
    ollama_embed_model: str = Field(default="nomic-embed-text", alias="OLLAMA_EMBED_MODEL")

    # ── RAG tuning ──────────────────────────────────────────
    rag_similarity_threshold: float = Field(default=0.65, alias="RAG_SIMILARITY_THRESHOLD")
    rag_top_k: int = Field(default=5, alias="RAG_TOP_K")
    rag_chunk_size: int = Field(default=800, alias="RAG_CHUNK_SIZE")
    rag_chunk_overlap: int = Field(default=120, alias="RAG_CHUNK_OVERLAP")

    # ── HTTP / CORS ─────────────────────────────────────────
    backend_cors_origins: str = Field(
        default="http://localhost:5173",
        alias="BACKEND_CORS_ORIGINS",
    )
    docs_storage_path: str = Field(default="/data/docs", alias="DOCS_STORAGE_PATH")

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.backend_cors_origins.split(",") if o.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
