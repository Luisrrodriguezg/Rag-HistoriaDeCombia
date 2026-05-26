# Arquitectura

```
        ┌──────────────────────┐
        │ React + shadcn (Vite)│
        │  - Login/Register    │  ← Keycloak.js (PKCE)
        │  - Chat (SSE stream) │
        │  - Documentos        │
        └──────────┬───────────┘
                   │ Bearer JWT
                   ▼
        ┌──────────────────────┐         ┌──────────────┐
        │  FastAPI (REST + SSE)│◄────────│   Keycloak   │
        │  /documents          │  JWKS   │  realm: rag  │
        │  /chat               │         └──────────────┘
        │  /chat/stream  (SSE) │
        │  /chat/history       │
        └──┬───────────────────┘
           │
           ▼
   ┌────────────────────────────────────────────┐
   │  LangGraph RAG Agent                       │
   │   START → retrieve → classify              │
   │            ├── (is_relevant) → generate    │
   │            └── (¬relevant)   → refuse_+_topics
   │   Cada nodo emite node_start / node_end    │
   │   por SSE → trazabilidad en UI             │
   └──┬─────────────────────────┬───────────────┘
      ▼                         ▼
   ┌─────────────┐         ┌─────────────────────────┐
   │  Postgres   │         │ Ollama  (host, Metal/GPU)│
   │ + pgvector  │         │  - qwen2.5:14b-q5_K_M    │
   │  VECTOR(1024)│        │  - bge-m3 (embeddings)   │
   └─────────────┘         └─────────────────────────┘
```

Cuatro contenedores (`db`, `keycloak`, `backend`, `frontend`) viven en la red Docker
interna `rag-net`. **Ollama corre fuera de Docker, en el host**, para aprovechar la
GPU de Apple Silicon vía Metal; el backend lo alcanza por `host.docker.internal:11434`.

## Decisiones clave

- **Sin Alembic**: el esquema se crea con `SQLAlchemy Base.metadata.create_all` en el
  `lifespan` de FastAPI. La extensión `vector` se instala vía `db/init.sql` montado en
  `/docker-entrypoint-initdb.d/`.
- **Ollama en host (rama `metal`)**: trade-off conocido a favor de la GPU. Inferencia
  100 % en Metal con `qwen2.5:14b-q5_K_M`; el modelo permanece caliente entre
  peticiones gracias a `OLLAMA_KEEP_ALIVE=30m`.
- **`pgvector` como vector store**: una sola DB para metadatos relacionales y
  embeddings (1024-dim, `bge-m3`) — menos superficie de fallo.
- **Una única compuerta LLM (`classify`)**: el grafo se simplificó de cinco a tres
  nodos efectivos. El `classify` decide *en una sola llamada* si el contexto es
  relevante y, si no lo es, extrae los temas del corpus para sugerirlos al usuario.
- **Streaming SSE con trazabilidad**: el endpoint `/chat/stream` emite eventos
  `node_start` / `node_end` / `token` / `done` que el frontend renderiza como una
  lista de pasos en vivo junto a la respuesta.
