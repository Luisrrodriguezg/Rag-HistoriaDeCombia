# Rag — Historia de Colombia

Agente inteligente con arquitectura **RAG** (Retrieval-Augmented Generation) sobre el dominio
de **Historia de Colombia**, construido con **LangChain + LangGraph**, modelo local
**Llama 3.1** (vía Ollama), base vectorial **Postgres + pgvector**, autenticación con
**Keycloak**, API **FastAPI** y frontend **React + shadcn/ui**. Todo orquestado con
**Docker Compose**.

> Trabajo final de la asignatura **Implementación de Software**.
> **Autores:** Luis Rodríguez · Simón Gómez

## Stack

| Capa | Tecnología |
|---|---|
| Frontend | React 18 + Vite + TypeScript + Tailwind + shadcn/ui + keycloak-js |
| Backend | FastAPI + SQLAlchemy 2 (async) + Pydantic v2 |
| Agente | LangChain + LangGraph (grafo con grading y grounding) |
| LLM | Ollama · `llama3.1:8b` |
| Embeddings | Ollama · `nomic-embed-text` (768 dim) |
| Vector store | PostgreSQL 16 + extensión `pgvector` |
| Auth | Keycloak 25 (OIDC + PKCE) |
| Orquestación | Docker Compose |

## Arquitectura

Ver `docs/arquitectura.md` (y `docs/arquitectura.png` cuando esté disponible).

## Ejecución rápida

```bash
cp .env.example .env
docker compose up -d --build
# Esperar a que ollama-init descargue los modelos (~5-10 min la primera vez):
docker compose logs -f ollama-init
```

Abrir:

- Frontend: http://localhost:5173
- API:      http://localhost:8000/docs
- Keycloak: http://localhost:8080  (admin / admin)

## Estructura

```
rag-historia-colombia/
├── backend/         FastAPI + LangGraph agent
├── frontend/        React + shadcn/ui
├── db/              init.sql (CREATE EXTENSION vector;)
├── keycloak/        realm-export.json
├── docs/            arquitectura + documento técnico
└── docker-compose.yml
```

## Control de alucinaciones

El agente implementa **cuatro estrategias** para evitar inventar respuestas:

1. **Umbral de similitud coseno** ≥ 0.65 al recuperar de pgvector.
2. **Nodo `grade_documents`** que filtra chunks irrelevantes con el LLM.
3. **Prompt restrictivo** que obliga a responder *solo* con el contexto provisto.
4. **Nodo `grade_generation`** que verifica grounding post-generación; si falla, se
   fuerza el mensaje canónico de rechazo.
