# Arquitectura

```
        ┌──────────────────────┐
        │ React + shadcn (Vite)│
        │  - Login/Register    │  ← Keycloak.js (PKCE)
        │  - Chat              │
        │  - Documentos        │
        └──────────┬───────────┘
                   │ Bearer JWT
                   ▼
        ┌──────────────────────┐         ┌──────────────┐
        │  FastAPI (REST)      │◄────────│   Keycloak   │
        │  /documents          │  JWKS   │  realm: rag  │
        │  /chat               │         └──────────────┘
        │  /chat/history       │
        └──┬───────────────────┘
           │
           ▼
   ┌────────────────────────────────────┐
   │  LangGraph RAG Agent               │
   │  ─── retrieve (pgvector cosine)    │
   │  ─── grade_documents (LLM)         │
   │  ─── decide (refuse | generate)    │
   │  ─── generate (Llama 3.1)          │
   │  ─── grade_generation (grounding)  │
   │  ─── persist (chat_history)        │
   └──────┬────────────┬────────────────┘
          ▼            ▼
   ┌─────────────┐  ┌───────────┐
   │  Postgres   │  │   Ollama  │
   │  + pgvector │  │  llama3.1 │
   │ (container) │  │(container)│
   └─────────────┘  └───────────┘
```

Todos los servicios viven en la red Docker interna `rag-net`. El frontend (Vite dev
server) corre fuera del compose en desarrollo y dentro de un contenedor nginx para
"producción local".

## Decisiones clave

- **Sin Alembic**: el esquema se crea con `SQLAlchemy Base.metadata.create_all` en el
  `lifespan` de FastAPI. La extensión `vector` se instala vía `db/init.sql` montado en
  `/docker-entrypoint-initdb.d/`.
- **Ollama dockerizado**: trade-off conocido — sin Metal/GPU en Mac la inferencia corre
  en CPU. Se acepta por reproducibilidad de la demo.
- **`pgvector` como vector store**: una sola DB para metadatos relacionales y
  embeddings — menos superficie de fallo.
- **Anti-alucinaciones**: 4 estrategias combinadas (umbral coseno, grading de
  documentos, prompt restrictivo, grading de generación).
