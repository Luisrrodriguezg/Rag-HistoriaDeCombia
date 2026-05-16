# Rag · Historia de Colombia

Agente inteligente con arquitectura **RAG** (Retrieval-Augmented Generation) sobre el dominio de
**Historia de Colombia**, construido con **LangChain + LangGraph**, modelo local **Llama 3.1**
(vía Ollama), base vectorial **Postgres + pgvector**, autenticación con **Keycloak**, API REST en
**FastAPI** y frontend en **React + shadcn/ui**. Todo orquestado con **Docker Compose**.

> **Trabajo final** · Asignatura: *Implementación de Software*
> **Autores:** Luis Rodríguez · Simón Gómez
>
> **Estás en la rama `metal`** — Ollama corre en el host con aceleración Metal/GPU.
> Si quieres la versión 100 % dockerizada (más portable, más lenta), usa `main`.

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

## 3. Requisitos previos (rama `metal`)

Esta rama saca Ollama del compose y lo corre en el host para aprovechar **Metal/GPU**
en Apple Silicon. Inferencia ~5-10× más rápida que la versión dockerizada de `main`.

- **macOS** con Apple Silicon (M1/M2/M3/M4). Probablemente funcione en Intel pero sin Metal.
- **Docker Desktop** con ≥ 4 GB de RAM al engine (ya no hace falta tanto porque Ollama
  no vive aquí).
- **Ollama instalado en el host** — ver paso 4.1.

---

## 4. Puesta en marcha (paso a paso)

### 4.1 Instalar Ollama en el host

Una de las dos opciones, no ambas:

**a) Homebrew (recomendado, solo CLI/servidor — sin app del menú-bar):**
```bash
brew install ollama
```

**b) DMG con app de menú-bar:** descarga `Ollama.app` de https://ollama.com/download,
muévela a `/Applications` y ábrela una vez para que registre el binario `ollama` en
`/usr/local/bin`. Luego ciérrala — vas a correr `ollama serve` manualmente con un bind
distinto.

Verifica:
```bash
which ollama        # → /opt/homebrew/bin/ollama  (brew) o /usr/local/bin/ollama
ollama --version
```

### 4.2 Arrancar Ollama bind a 0.0.0.0

Los contenedores acceden al host vía `host.docker.internal`, que NO es loopback.
Ollama por defecto escucha solo en `127.0.0.1`, así que hay que cambiar el bind:

```bash
# Si tenías la app del menú-bar abierta, ciérrala antes:
killall Ollama 2>/dev/null
launchctl unload ~/Library/LaunchAgents/com.ollama.ollama.plist 2>/dev/null

# Arranca el server escuchando en todas las interfaces. DEJA esta terminal abierta.
OLLAMA_HOST=0.0.0.0:11434 ollama serve
```

Smoke test desde **otra terminal**:
```bash
curl http://localhost:11434/api/tags
# → {"models":[]}   (vacío al principio, eso está bien)
```

### 4.3 Descargar los modelos

En otra terminal (la primera la dejas con `ollama serve` viva):
```bash
ollama pull llama3.1:8b           # ≈ 4.7 GB
ollama pull nomic-embed-text      # ≈ 275 MB
```

Persisten en `~/.ollama/models`, no se redescargan en el siguiente arranque.

### 4.4 Levantar el stack

```bash
cp .env.example .env              # solo la primera vez
docker compose up -d --build
./scripts/check-stack.sh          # debe responder todo en verde
```

Si `check-stack.sh` falla en Ollama, vuelve al paso 4.2.

Una vez completado:

| Servicio | URL |
|---|---|
| Frontend | http://localhost:5173 |
| API (Swagger) | http://localhost:8000/docs |
| Keycloak admin | http://localhost:8080  (admin / admin) |

> **Nota:** el `KEYCLOAK_PORT` por defecto es 8080. Si en tu máquina ese puerto está ocupado
> (`docker ps | grep 8080`), edita `.env` y pon p.ej. `KEYCLOAK_PORT=8085` junto con
> `VITE_KEYCLOAK_URL=http://localhost:8085` y `KEYCLOAK_EXTERNAL_ISSUER=http://localhost:8085/realms/rag`.

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
| `OLLAMA_BASE_URL` | `http://host.docker.internal:11434` | Endpoint del Ollama del host (rama `metal`) |
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

## 9. Troubleshooting (rama `metal`)

| Síntoma | Causa probable | Solución |
|---|---|---|
| `zsh: command not found: ollama` | Ollama no está instalado en el host | `brew install ollama` (o instala el `.dmg` y abre la app una vez) |
| `check-stack.sh`: "Host Ollama is not responding on :11434" | El server no está corriendo, o quedó bindeado a `127.0.0.1` | Mata cualquier instancia previa (`killall Ollama`) y vuelve a arrancar con `OLLAMA_HOST=0.0.0.0:11434 ollama serve` |
| `LLMUnavailable` / `EmbeddingError` desde el backend | El contenedor no llega a `host.docker.internal:11434` | Confirma con `docker compose exec backend curl http://host.docker.internal:11434/api/tags`. Si responde "Connection refused", el bind sigue siendo loopback — repite el paso 4.2. |
| `pgvector extension not installed` | El volumen `pgdata` se creó antes de existir `db/init.sql` | `docker compose down -v && docker compose up -d` (¡esto sí borra los chunks!) |
| `401 INVALID_JWT` con `Token is missing sub claim` | Estás en una versión anterior al fix del scope `basic` | Pull de la rama, recrea Keycloak: `docker compose down && docker volume rm rag-historia-colombia_kc_data && docker compose up -d` |
| `Bind for 0.0.0.0:8080 failed: port is already allocated` | Otra app ocupa 8080 | En `.env` cambia `KEYCLOAK_PORT`, `VITE_KEYCLOAK_URL` y `KEYCLOAK_EXTERNAL_ISSUER` al mismo puerto alternativo |
| El chat sigue lento aunque Ollama está en host | `ollama serve` está corriendo en CPU (Rosetta / shell x86) | `arch` debe responder `arm64`; abre la terminal nativa, no la x86 |

---

## 10. Limitaciones conocidas (rama `metal`)

- Requiere host macOS con Apple Silicon (M1/M2/M3/M4) para Metal real. En Intel funciona
  igual pero sin aceleración GPU.
- `ollama serve` corre como proceso de usuario: si reinicias el Mac hay que volver a
  lanzarlo manualmente. Si quieres que arranque solo, `brew services start ollama` —
  pero por defecto bindea a `127.0.0.1` y habría que ajustar el plist; para una demo de
  clase la terminal dedicada es más simple.
- No hay rate limiting en el endpoint `/chat`; un usuario malicioso podría saturar Ollama.
- El grading de la generación añade una invocación LLM por respuesta; para corpus grandes
  conviene reemplazarlo por un re-ranker cross-encoder.

---

## 11. Volver a la rama `main` (versión 100 % dockerizada)

```bash
git checkout main
# editar .env: OLLAMA_BASE_URL=http://ollama:11434
docker compose down
docker compose up -d --build
```

En `main`, Ollama vuelve a estar como servicio del compose con su volumen `ollama_models`.
La inferencia será CPU-bound (más lenta) pero el stack levanta con un único comando sin
prerrequisitos en el host.
