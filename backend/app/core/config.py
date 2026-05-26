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
    ollama_llm_model: str = Field(default="qwen2.5:14b-instruct-q4_K_M", alias="OLLAMA_LLM_MODEL")
    ollama_embed_model: str = Field(default="bge-m3", alias="OLLAMA_EMBED_MODEL")
    # Explicit context window: Ollama's default (2048) silently truncates when
    # the 5-chunk RAG context + system prompt overflows it.
    ollama_num_ctx: int = Field(default=8192, alias="OLLAMA_NUM_CTX")
    # Keep the model resident in VRAM between requests so the first call after
    # idle doesn't pay the model-load tax.
    ollama_keep_alive: str = Field(default="30m", alias="OLLAMA_KEEP_ALIVE")

    # ── RAG tuning ──────────────────────────────────────────
    # bge-m3 cosine scores cluster lower than nomic-embed-text — 0.55 is a safer
    # default. Tune empirically against a held-out Q/A set.
    rag_similarity_threshold: float = Field(default=0.55, alias="RAG_SIMILARITY_THRESHOLD")
    rag_top_k: int = Field(default=5, alias="RAG_TOP_K")
    rag_chunk_size: int = Field(default=800, alias="RAG_CHUNK_SIZE")
    rag_chunk_overlap: int = Field(default=120, alias="RAG_CHUNK_OVERLAP")
    # If every retrieved chunk scores above this, skip the LLM grading call.
    rag_grading_skip_threshold: float = Field(default=0.85, alias="RAG_GRADING_SKIP_THRESHOLD")
    # Number of prior (question, answer) pairs to inject into classify/generate
    # prompts so the LLM can resolve follow-ups like "y cuándo nació?". Note:
    # retrieval still embeds only the current question — history affects
    # interpretation, not what chunks are pulled.
    chat_history_turns: int = Field(default=3, alias="CHAT_HISTORY_TURNS")

    # ── DB lifecycle ────────────────────────────────────────
    # One-shot toggle: when set, init_db drops the chunks table + IVFFlat index
    # before recreating them. Used when changing embedding dimensionality.
    rag_reset_vectors: bool = Field(default=False, alias="RAG_RESET_VECTORS")

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
