# Rag · Historia de Colombia

Agente inteligente con arquitectura **RAG** (Retrieval-Augmented Generation) sobre el dominio de
**Historia de Colombia**, construido con **LangChain + LangGraph**, modelo local **Llama 3.1**
(vía Ollama), base vectorial **Postgres + pgvector**, autenticación con **Keycloak**, API REST en
**FastAPI** y frontend en **React + shadcn/ui**. Todo orquestado con **Docker Compose**.

> **Trabajo final** · Asignatura: *Implementación de Software*
> **Autores:** Luis Rodríguez · Simón Gómez

---

## 1. Stack

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

---

## 2. Arquitectura

Ver `docs/arquitectura.md`. Versión rápida:

```
React ──Bearer JWT──► FastAPI ──► LangGraph
                       │            ├── retrieve (pgvector)
                       │            ├── grade_documents (LLM)
                       │            ├── generate (Llama 3.1)
                       │            ├── grade_generation (grounding)
                       │            └── refuse (canonical message)
                       │
                       └── Keycloak (JWKS verification)
```

---

## 3. Requisitos previos

- **Docker Desktop** con al menos **8 GB de RAM** asignados al engine
  (Settings → Resources). Llama 3.1 en CPU lo necesita.
- No es necesario instalar Ollama, Node o Python en el host: todo corre en contenedores.

---

## 4. Ejecución

```bash
cp .env.example .env
docker compose up -d --build
```

La primera ejecución descarga `llama3.1:8b` (≈ 4.7 GB) y `nomic-embed-text` (≈ 275 MB) mediante el
servicio efímero `ollama-init`. Puede tomar **5-10 minutos** la primera vez:

```bash
docker compose logs -f ollama-init
```

Una vez completado:

| Servicio | URL |
|---|---|
| Frontend | http://localhost:5173 |
| API (Swagger) | http://localhost:8000/docs |
| Keycloak admin | http://localhost:8080  (admin / admin) |

Verificación rápida de salud del stack:

```bash
./scripts/check-stack.sh
```

### Usuario de prueba

El realm `rag` se importa con un usuario pre-cargado:

- **Usuario:** `demo`
- **Contraseña:** `demo`

También puedes registrarte desde el frontend (botón **Registrarse** en la pantalla de inicio).

---

## 5. Uso

1. **Inicio de sesión** → pantalla con autores visibles → "Iniciar sesión" abre el flujo de
   Keycloak (PKCE) o "Registrarse" para crear una cuenta.
2. **Documentos** → subir PDF / TXT / MD / DOCX. El backend extrae texto, divide en fragmentos
   (800 chars con overlap 120), genera embeddings con `nomic-embed-text` y los indexa en
   `pgvector`.
3. **Chat** → hacer preguntas. El agente:
   - Recupera los 5 fragmentos más similares (≥ 0.65 de similitud coseno).
   - Filtra por relevancia LLM.
   - Genera respuesta con prompt restrictivo.
   - Verifica grounding (anti-alucinación).
   - Cuando falta información, devuelve el mensaje canónico
     *"No tengo suficiente información en mi base de conocimiento…"*.
4. **Cerrar sesión** → botón en la esquina superior derecha del header.

---

## 6. Control de alucinaciones

Cuatro estrategias combinadas:

| # | Estrategia | Implementación |
|---|---|---|
| 1 | Umbral de similitud coseno | `RAG_SIMILARITY_THRESHOLD=0.65` aplicado en `chunk_repo.similarity_search` |
| 2 | Grading LLM de documentos | Nodo `grade_documents` filtra chunks no relevantes con prompt yes/no |
| 3 | Prompt restrictivo | `ANSWER_PROMPT` obliga a usar solo el contexto y a emitir el mensaje canónico si falta info |
| 4 | Grading LLM de la generación | Nodo `grade_generation` verifica grounding; si falla, sobrescribe con el rechazo |

---

## 7. Variables de entorno

Ver `.env.example`. Las claves más relevantes:

| Variable | Por defecto | Descripción |
|---|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://rag:rag@db:5432/rag` | Conexión a Postgres |
| `KEYCLOAK_INTERNAL_JWKS_URL` | `http://keycloak:8080/realms/rag/protocol/openid-connect/certs` | JWKS interno |
| `KEYCLOAK_EXTERNAL_ISSUER` | `http://localhost:8080/realms/rag` | `iss` esperado en el JWT |
| `OLLAMA_BASE_URL` | `http://ollama:11434` | Endpoint Ollama dentro de la red Docker |
| `OLLAMA_LLM_MODEL` | `llama3.1:8b` | Modelo de generación |
| `OLLAMA_EMBED_MODEL` | `nomic-embed-text` | Modelo de embeddings |
| `RAG_SIMILARITY_THRESHOLD` | `0.65` | Umbral mínimo de similitud coseno |
| `RAG_TOP_K` | `5` | k para `retrieve` |
| `RAG_CHUNK_SIZE` / `RAG_CHUNK_OVERLAP` | `800` / `120` | Parámetros del splitter |

---

## 8. Estructura del repositorio

```
rag-historia-colombia/
├── docker-compose.yml
├── .env.example
├── db/init.sql              # CREATE EXTENSION vector
├── keycloak/realm-export.json
├── scripts/check-stack.sh
├── backend/
│   ├── Dockerfile
│   ├── pyproject.toml
│   └── app/
│       ├── main.py          # FastAPI factory, lifespan, CORS, handlers
│       ├── core/            # config · logging · db · exceptions · security
│       ├── api/             # deps + routes/{health,auth,documents,chat}
│       ├── agents/          # state · prompts · nodes · graph (LangGraph)
│       ├── services/        # chunker · embeddings · document_service
│       ├── repositories/    # document_repo · chunk_repo · chat_repo
│       ├── models/          # SQLAlchemy ORM (Document, Chunk, ChatMessage)
│       └── schemas/         # Pydantic v2 schemas
├── frontend/
│   ├── Dockerfile · nginx.conf
│   ├── package.json · vite.config.ts · tsconfig.json
│   └── src/
│       ├── main.tsx · App.tsx
│       ├── lib/             # auth (keycloak-js) · api (axios) · utils
│       ├── components/      # ui/ (shadcn) · Header · ChatWindow · DocumentList · UploadDialog
│       ├── pages/           # LoginPage · ChatPage · DocumentsPage
│       └── hooks/           # useAuth
└── docs/
    └── arquitectura.md
```

---

## 9. Troubleshooting

| Síntoma | Causa probable | Solución |
|---|---|---|
| `pgvector extension not installed` al arrancar el backend | El volumen `pgdata` fue creado antes de añadir `db/init.sql` | `docker compose down -v && docker compose up -d` |
| El chat tarda > 30 s en responder | Inferencia en CPU (sin GPU) | Esperado; mover Ollama a host con Metal lo acelera ~5× |
| `401 INVALID_JWT` constante | Reloj del contenedor desfasado o realm mal importado | `docker compose restart keycloak` y revisar `KEYCLOAK_INTERNAL_JWKS_URL` |
| Modelos no se descargan | Servicio `ollama-init` falló | `docker compose run --rm ollama-init` (reintenta el pull manualmente) |

---

## 10. Limitaciones conocidas

- Llama 3.1 8B en CPU está al límite de respuestas conversacionales — para producción se
  recomienda mover Ollama al host con Metal/GPU o usar un modelo más pequeño (`llama3.2:3b`,
  `gemma2:2b`).
- No hay rate limiting en el endpoint `/chat`; un usuario malicioso podría saturar Ollama.
- El grading de documentos y de la generación dispara una invocación LLM extra por fragmento;
  para corpus grandes conviene reemplazarlo por un re-ranker cross-encoder.
