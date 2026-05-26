# Rag · Historia de Colombia

Agente inteligente con arquitectura **RAG** (Retrieval-Augmented Generation) sobre el dominio
de **Historia de Colombia**, construido con **LangChain + LangGraph**, modelo local
**Qwen 2.5 14B** (vía Ollama con Metal/GPU), embeddings multilingües **bge-m3**, base vectorial
**Postgres + pgvector**, autenticación con **Keycloak**, API REST + **streaming SSE** en
**FastAPI** y frontend en **React + shadcn/ui** con **trazabilidad visual de nodos en vivo**.
Todo orquestado con **Docker Compose**.

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
| Streaming | Server-Sent Events (`StreamingResponse`) con trazabilidad de nodos |
| Agente | LangChain + LangGraph (grafo de tres nodos efectivos) |
| LLM | Ollama · `qwen2.5:14b-instruct-q5_K_M` (~10 GB, 100 % GPU) |
| Embeddings | Ollama · `bge-m3` (1024 dim, multilingüe) |
| Vector store | PostgreSQL 16 + extensión `pgvector` (`VECTOR(1024)`) |
| Auth | Keycloak 25 (OIDC + PKCE) |
| Orquestación | Docker Compose |

---

## 2. Arquitectura

Ver `docs/arquitectura.md`. Versión rápida:

```
React ──Bearer JWT──► FastAPI ──► LangGraph
                       │            ├── retrieve (bge-m3 + pgvector)
                       │            ├── classify (1 LLM call: YES | NO + topics)
                       │            ├── generate (streaming token-a-token)
                       │            └── refuse_with_topics (refusal + sugerencias)
                       │
                       └── Keycloak (JWKS verification)
```

El endpoint `/chat/stream` emite eventos `node_start` / `node_end` / `token` / `done` por SSE
para que el frontend muestre el avance del agente en vivo junto con la respuesta. Los últimos
3 turnos del usuario se inyectan al prompt para que follow-ups con pronombres funcionen.

---

## 3. Requisitos previos (rama `metal`)

Esta rama saca Ollama del compose y lo corre en el host para aprovechar **Metal/GPU**
en Apple Silicon. Inferencia ~5-10× más rápida que la versión dockerizada de `main`.

- **macOS** con Apple Silicon (M1/M2/M3/M4). En Intel funciona pero sin Metal.
- **24 GB de RAM mínimo** — el LLM ocupa ~10 GB en VRAM + cache de contexto.
- **~15 GB libres en disco** para los modelos de Ollama.
- **Docker Desktop** con suficiente RAM al engine (4 GB es suficiente; el peso está en Ollama).
- **Ollama instalado en el host** — ver paso 4.1.

---

## 4. Puesta en marcha (paso a paso)

### 4.1 Instalar Ollama en el host

Una de las dos opciones, no ambas:

**a) Homebrew (recomendado, solo CLI/servidor):**
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
ollama pull qwen2.5:14b-instruct-q5_K_M    # ≈ 10 GB · LLM
ollama pull bge-m3                          # ≈ 1.2 GB · embeddings multilingües
```

Persisten en `~/.ollama/models`, no se redescargan en el siguiente arranque.
Confirma que se cargarán en GPU:

```bash
ollama ps    # tras la primera pregunta debe decir PROCESSOR=100% GPU
```

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

### Aplicar cambios en `.env`

`docker compose restart` **no** relee `.env`. Para que el backend tome variables modificadas:

```bash
docker compose up -d --force-recreate backend
```

---

## 5. Uso

1. **Inicio de sesión** → pantalla con autores visibles → "Iniciar sesión" abre el flujo de
   Keycloak (PKCE) o "Registrarse" para crear una cuenta.
2. **Documentos** → subir PDF / TXT / MD / DOCX. El backend extrae texto, divide en fragmentos
   (800 chars con overlap 120), genera embeddings con `bge-m3` y los indexa en `pgvector`.
3. **Chat** → hacer preguntas. El agente:
   - Recupera los **12 fragmentos más similares** (≥ 0.25 de similitud coseno con bge-m3).
   - **Clasifica relevancia** con una sola llamada al LLM. Si la pregunta es de seguimiento
     ("y él?", "ese", "el primero de ellos"), el LLM ve los últimos 3 turnos para entender
     a qué se refiere.
   - Si es relevante → **`generate`** produce la respuesta con `qwen2.5:14b` y la
     **streamea token-a-token** vía SSE; cada hecho factual va con cita `[N]` al fragmento.
   - Si no es relevante → **`refuse_with_topics`** devuelve el mensaje canónico
     *"No tengo suficiente información…"* seguido de 2–4 temas concretos del corpus que
     el usuario sí podría consultar.
   - El usuario ve los pasos del agente en vivo (🔍 Recuperando · 🧠 Clasificando · ✍️ Generando)
     con spinner → check y metadata de cada nodo.
4. **Cerrar sesión** → botón en la esquina superior derecha del header.

---

## 6. Control de alucinaciones

Cuatro estrategias combinadas:

| # | Estrategia | Implementación |
|---|---|---|
| 1 | Umbral de similitud coseno | `RAG_SIMILARITY_THRESHOLD=0.25` aplicado en `retrieve_node` (calibrado para bge-m3) |
| 2 | Clasificación LLM de relevancia | Nodo `classify` con prompt YES/NO + extracción de temas para el path de rechazo |
| 3 | Prompt estricto de generación | `ANSWER_PROMPT` prohíbe inventar nombres/fechas/cifras **incluso con disclaimer**; cada hecho factual debe ir con cita `[N]` |
| 4 | Auto-rechazo | El modelo emite la `REFUSAL_MESSAGE` exacta cuando el contexto no le sirve; el flujo la detecta y la honra |

> El diseño previo tenía dos compuertas LLM adicionales (`grade_documents` per-chunk +
> `grade_generation` grounding-check). Se retiraron porque rechazaban en exceso preguntas
> conversacionales/amplias. Una sola compuerta `classify` + un prompt restrictivo es
> suficiente con `qwen2.5:14b-q5_K_M`.

---

## 7. Variables de entorno

Ver `.env.example`. Las claves más relevantes:

| Variable | Por defecto | Descripción |
|---|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://rag:rag@db:5432/rag` | Conexión a Postgres |
| `KEYCLOAK_INTERNAL_JWKS_URL` | `http://keycloak:8080/realms/rag/protocol/openid-connect/certs` | JWKS interno |
| `KEYCLOAK_EXTERNAL_ISSUER` | `http://localhost:8080/realms/rag` | `iss` esperado en el JWT |
| `OLLAMA_BASE_URL` | `http://host.docker.internal:11434` | Endpoint del Ollama del host (rama `metal`) |
| `OLLAMA_LLM_MODEL` | `qwen2.5:14b-instruct-q5_K_M` | Modelo de generación |
| `OLLAMA_EMBED_MODEL` | `bge-m3` | Modelo de embeddings (1024 dim) |
| `OLLAMA_NUM_CTX` | `16384` | Ventana de contexto del LLM (defaults 2048 de Ollama insuficiente) |
| `OLLAMA_KEEP_ALIVE` | `30m` | Tiempo que el modelo permanece en VRAM tras la última petición |
| `RAG_SIMILARITY_THRESHOLD` | `0.25` | Umbral mínimo de similitud coseno (calibrado para bge-m3) |
| `RAG_TOP_K` | `12` | k para `retrieve` |
| `RAG_CHUNK_SIZE` / `RAG_CHUNK_OVERLAP` | `800` / `120` | Parámetros del splitter |
| `CHAT_HISTORY_TURNS` | `3` | Turnos previos inyectados al prompt para resolver follow-ups |
| `RAG_RESET_VECTORS` | `false` | One-shot: si está en `1` al boot, dropea `chunks` para reindexar |

---

## 8. Estructura del repositorio

```
rag-historia-colombia/
├── docker-compose.yml
├── .env.example
├── db/init.sql              # CREATE EXTENSION vector
├── keycloak/realm-export.json
├── scripts/
│   ├── check-stack.sh
│   ├── seed_corpus.py
│   └── reindex.py           # re-embed chunks tras cambiar el embedder
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
│       ├── lib/             # auth (keycloak-js) · api (axios + SSE) · utils
│       ├── components/      # ui/ (shadcn) · Header · ChatWindow · DocumentList · UploadDialog
│       ├── pages/           # LoginPage · ChatPage · DocumentsPage
│       └── hooks/           # useAuth
└── docs/
    ├── arquitectura.md
    ├── documento-tecnico.md
    ├── presentacion.html    # 12 slides reveal.js
    └── Images/              # capturas para presentación / evidencias
```

---

## 9. Re-indexar tras cambiar el embedder

Si cambias `OLLAMA_EMBED_MODEL` (o subes a una versión de `bge-m3` que cambie de dim), la
columna `Vector(N)` es incompatible con los embeddings existentes y hay que reindexar.
Los binarios de los documentos ya cargados están en el volumen `docs_storage`, así que
**no se pierden** — sólo se re-embeben:

```bash
# 1) Cambiar OLLAMA_EMBED_MODEL en .env y EMBEDDING_DIM en backend/app/models/chunk.py si aplica.
# 2) Boot con flag de reset: dropea la tabla chunks + índice IVFFlat antes de recrearlos.
RAG_RESET_VECTORS=1 docker compose up -d --force-recreate backend

# 3) Re-embeber todos los documentos desde disco:
docker compose exec backend python scripts/reindex.py

# 4) Quitar el flag y dejar el stack normal.
sed -i '' '/^RAG_RESET_VECTORS/d' .env
docker compose up -d --force-recreate backend
```

---

## 10. Troubleshooting (rama `metal`)

| Síntoma | Causa probable | Solución |
|---|---|---|
| `zsh: command not found: ollama` | Ollama no está instalado en el host | `brew install ollama` (o instala el `.dmg` y abre la app una vez) |
| `check-stack.sh`: "Host Ollama is not responding on :11434" | El server no está corriendo, o quedó bindeado a `127.0.0.1` | Mata cualquier instancia previa (`killall Ollama`) y vuelve a arrancar con `OLLAMA_HOST=0.0.0.0:11434 ollama serve` |
| `LLMUnavailable` / `EmbeddingError` desde el backend | El contenedor no llega a `host.docker.internal:11434` | Confirma con `docker compose exec backend curl http://host.docker.internal:11434/api/tags`. Si responde "Connection refused", el bind sigue siendo loopback — repite el paso 4.2. |
| El chat se queda en "Pensando…" para siempre | Bundle viejo del frontend en caché del navegador | Hard refresh: `Cmd+Shift+R` (Chrome/Edge) o `Cmd+Opt+R` (Safari) |
| Cambié `.env` y el backend sigue con valores viejos | `docker compose restart` no relee `.env` | `docker compose up -d --force-recreate backend` |
| `ollama ps` muestra `XX% GPU / YY% CPU` | El modelo no cabe entero en VRAM | Cierra otras apps que consuman GPU, baja `OLLAMA_NUM_CTX` o cambia a `q4_K_M` |
| Subí un PDF y `chunk_count = 0` | Es un escaneo sin capa de texto (`pypdf` no hace OCR) | Verifica con `docker compose exec db psql -U rag -d rag -c "SELECT filename, COUNT(c.id) FROM documents d LEFT JOIN chunks c ON c.document_id = d.id GROUP BY filename;"`. Usa un PDF "nativo" (texto seleccionable). |
| `pgvector extension not installed` | El volumen `pgdata` se creó antes de existir `db/init.sql` | `docker compose down -v && docker compose up -d` (¡esto sí borra los chunks!) |
| `401 INVALID_JWT` con `Token is missing sub claim` | Estás en una versión anterior al fix del scope `basic` | Pull de la rama, recrea Keycloak: `docker compose down && docker volume rm rag-historia-colombia_kc_data && docker compose up -d` |
| `Bind for 0.0.0.0:8080 failed: port is already allocated` | Otra app ocupa 8080 | En `.env` cambia `KEYCLOAK_PORT`, `VITE_KEYCLOAK_URL` y `KEYCLOAK_EXTERNAL_ISSUER` al mismo puerto alternativo |
| El chat sigue lento aunque Ollama está en host | `ollama serve` está corriendo en CPU (Rosetta / shell x86) | `arch` debe responder `arm64`; abre la terminal nativa, no la x86 |

### Ver logs por pregunta

```bash
docker compose logs -f backend 2>&1 | grep -E "retrieve|classify|generate|refuse|run_agent"
```

Cada pregunta produce líneas tipo:

```
retrieve: q='…' top-12 similarities=['0.66|Presidentes…', '0.65|…', …]
retrieve: kept N/12 above threshold=0.25
classify: verdict='YES' -> is_relevant=True
generate: answer[:120]='…'
run_agent_stream: completed in 4.2s
```

---

## 11. Limitaciones conocidas

- Requiere host macOS con Apple Silicon para Metal real; en Intel funciona sin GPU.
- `ollama serve` corre como proceso de usuario: si reinicias el Mac hay que volver a
  lanzarlo manualmente con el bind correcto (`OLLAMA_HOST=0.0.0.0:11434 ollama serve`).
- No hay rate limiting en el endpoint `/chat`; un usuario malicioso podría saturar Ollama.
- `pypdf` no hace OCR: documentos escaneados terminan con `chunk_count = 0`.
- **CSV no está soportado** como formato de carga (sí PDF/DOCX/TXT/MD); añadirlo son
  ~10 líneas en `chunker.py` con `csv.reader`.
- **Sin despliegue cloud**: el proyecto vive en local. Reproducir la latencia interactiva
  del LLM con aceleración GPU en cloud asequible no es viable; la arquitectura es
  portable (Compose + variables de entorno) si se aceptara latencia mayor o se moviera
  el LLM a un servicio gestionado (Groq, Together, etc.).

---

## 12. Volver a la rama `main` (versión 100 % dockerizada)

```bash
git checkout main
# editar .env: OLLAMA_BASE_URL=http://ollama:11434
docker compose down
docker compose up -d --build
```

En `main`, Ollama vuelve a estar como servicio del compose con su volumen `ollama_models`.
La inferencia será CPU-bound (mucho más lenta) pero el stack levanta con un único
comando sin prerrequisitos en el host. La rama `main` también tiene el set de modelos y
parámetros previos (`llama3.1:8b` + `nomic-embed-text`); la rama `metal` es la que tiene
los modelos actualizados y todos los cambios documentados en `docs/documento-tecnico.md`.
