# Documento Técnico — Rag · Historia de Colombia

## 1. Nombre del proyecto
**Rag · Historia de Colombia** — Agente inteligente con Retrieval-Augmented Generation sobre
literatura y artículos de historia colombiana.

## 2. Integrantes
- Luis Rodríguez
- Simón Gómez

## 3. Tema seleccionado
**Historia de Colombia.** Cubre eventos, personajes y procesos políticos/sociales del país,
desde la conquista y la Independencia hasta la historia republicana del siglo XX.

## 4. Descripción del problema
El conocimiento histórico de Colombia está disperso entre enciclopedias, libros académicos y
artículos en línea. Para un estudiante o investigador es engorroso consultar varios documentos
para responder una pregunta puntual con respaldo bibliográfico. Este proyecto entrega un agente
que **responde con base en documentos cargados** por el propio usuario y se niega a inventar
información cuando no tiene contexto suficiente.

## 5. Arquitectura general
Cliente React (con autenticación OIDC) ↔ API REST en FastAPI ↔ Agente LangGraph ↔ pgvector +
Ollama. Todos los componentes corren como servicios Docker en la misma red interna.

## 6. Diagrama de arquitectura
Ver `docs/arquitectura.md` (ASCII) y `docs/arquitectura.png` (exportar desde Excalidraw para la
presentación).

## 7. Tecnologías utilizadas

| Capa | Tecnología | Versión |
|---|---|---|
| Frontend | React + Vite + TypeScript + Tailwind + shadcn/ui | 18 / 5.4 / 5.6 |
| Auth (cliente) | keycloak-js | 25 |
| Backend | FastAPI + Pydantic v2 + SQLAlchemy 2 async | 0.115 / 2.9 / 2.0 |
| Agente | LangChain + LangGraph | 0.3 / 0.2 |
| LLM | Ollama · `llama3.1:8b` | latest |
| Embeddings | Ollama · `nomic-embed-text` (768 dim) | latest |
| Vector store | Postgres 16 + pgvector | 16 / 0.7 |
| Auth (servidor) | Keycloak | 25.0 |
| Orquestación | Docker Compose | v2 |

## 8. Descripción del backend
- **Framework:** FastAPI con `lifespan` para inicializar el esquema (sin Alembic).
- **Endpoints:**
  - `GET /health`
  - `GET /auth/me`
  - `POST /documents`, `GET /documents`, `DELETE /documents/{id}`
  - `POST /chat`, `GET /chat/history`
- **Seguridad:** todos los endpoints excepto `/health` exigen `Authorization: Bearer <JWT>`. El
  token se valida contra el JWKS de Keycloak con cache TTL.
- **Errores uniformes:** `app/core/exceptions.py` define la jerarquía `AppError`
  (`InvalidJWT`, `DocumentNotFound`, `UnsupportedFileType`, `EmbeddingError`,
  `LLMUnavailable`, …) y los handlers que producen `{code, message, details}`.

## 9. Descripción del frontend
- SPA en React + Vite, estilada con Tailwind y componentes shadcn/ui.
- Tres páginas: `LoginPage` (con autores), `ChatPage`, `DocumentsPage`.
- `Header` con navegación entre Chat y Documentos y **botón "Cerrar sesión"** siempre visible.
- Interceptor de axios refresca el token en cada request y redirige a Keycloak ante 401.

## 10. Descripción del agente
Grafo en LangGraph con cinco nodos (más uno terminal de rechazo):

1. `retrieve` — embebe la pregunta y consulta los top-k chunks por similitud coseno en pgvector.
2. `grade_documents` — el LLM clasifica cada chunk como relevante / no relevante.
3. `decide_route` (condicional) — si no quedan chunks relevantes, va a `refuse`; si quedan, a
   `generate`.
4. `generate` — produce respuesta con prompt restrictivo (sólo contexto, en español).
5. `grade_generation` — verifica grounding; si la respuesta no está respaldada, fuerza el
   mensaje canónico.
6. `refuse` — emite el mensaje canónico y marca `grounded=false`.

## 11. Flujo de LangGraph

```
START → retrieve → grade_documents → decide_route
                                      ├── refuse → END
                                      └── generate → grade_generation → END
```

## 12. Modelo local utilizado
- **`llama3.1:8b`** mediante Ollama.
- Elegido por su buen balance calidad/tamaño, soporte multilingüe y disponibilidad en Ollama.
- Se ejecuta dentro del contenedor `ollama`; el volumen `ollama_models` evita re-descargas.
- **Limitación:** sin Metal/GPU la inferencia es CPU-bound y cada respuesta puede tardar
  segundos a minutos. Aceptado como trade-off por reproducibilidad.

## 13. Base de datos vectorial utilizada
**PostgreSQL 16 + pgvector.** Una sola base de datos (`rag`) almacena tanto los metadatos
relacionales (`documents`, `chat_messages`) como los embeddings (`chunks.embedding`
con tipo `VECTOR(768)`). Índice `ivfflat` con `vector_cosine_ops` (100 listas).

## 14. Proceso de carga de documentos

1. Frontend hace `POST /documents` con `multipart/form-data`.
2. Backend persiste el binario en el volumen `docs_storage` y extrae texto:
   - PDF → `pypdf`
   - DOCX → `python-docx`
   - TXT / MD → decodificación UTF-8 con fallback latin-1
3. `RecursiveCharacterTextSplitter` divide el texto (800/120 por defecto).
4. `OllamaEmbeddings(nomic-embed-text)` genera vectores 768-dim.
5. Inserción en bulk en `chunks` con FK al documento.
6. Respuesta 201 con `{id, filename, chunk_count}`.

## 15. Estrategias para evitar alucinaciones

| # | Estrategia | Capa | Configurable |
|---|---|---|---|
| 1 | Umbral de similitud coseno ≥ 0.65 | retrieve | `RAG_SIMILARITY_THRESHOLD` |
| 2 | LLM grading de documentos (yes/no) | grade_documents | prompt |
| 3 | Prompt restrictivo "solo contexto" | generate | prompt |
| 4 | LLM grading de la generación (grounding) | grade_generation | prompt |

## 16. Seguridad y autenticación
- **Keycloak 25** con realm `rag` importado vía `--import-realm`.
- Cliente público `rag-frontend` con flujo `Authorization Code + PKCE S256`.
- Auto-registro habilitado; rol por defecto `user`.
- Backend valida `RS256` con JWKS cacheado y rotación lazy si aparece un `kid` nuevo.
- API REST 100 % protegida: cualquier endpoint distinto de `/health` exige Bearer JWT.

## 17. Despliegue
Toda la solución se despliega en local con un único comando:

```bash
docker compose up -d --build
```

Cinco servicios (`db`, `keycloak`, `ollama`, `backend`, `frontend`) en una red interna
`rag-net`; volúmenes persistentes (`pgdata`, `kc_data`, `ollama_models`, `docs_storage`) para
no re-descargar/re-popular en cada reinicio. *El despliegue a nube quedó fuera del alcance del
trabajo final por restricción de tiempo del equipo; la arquitectura es cloud-ready (Compose +
variables de entorno) y portable a Render/Railway/Fly sin cambios estructurales.*

## 18. Evidencias de funcionamiento
*(Insertar capturas en `docs/screenshots/`):*
- Pantalla de login con autores visibles.
- Pantalla de Documentos con archivos cargados.
- Chat con pregunta válida (respuesta + fuentes con porcentaje de similitud).
- Chat con pregunta fuera de dominio (mensaje canónico de rechazo).
- Logs del backend con la traza del grafo (retrieve → grade → generate → grade_generation).

## 19. Problemas encontrados
*(Completar con la experiencia real durante el desarrollo; ejemplos típicos:)*
- Calibración del umbral de similitud: 0.5 era demasiado permisivo, 0.8 demasiado estricto;
  se fijó en 0.65 tras pruebas con preguntas de control.
- El servicio `ollama-init` debe esperar a que el contenedor `ollama` esté saludable
  (`condition: service_healthy`); inicialmente fallaba porque intentaba pull antes del
  arranque completo.
- Keycloak emite el `iss` con la URL externa (`localhost`) aunque el backend lo resuelva por
  DNS interno (`keycloak`); se aceptan ambos issuers en la verificación.

## 20. Conclusiones
- La combinación pgvector + Ollama + LangGraph es suficiente para un RAG de alta calidad sin
  depender de servicios cloud comerciales.
- Las cuatro estrategias anti-alucinación implementadas reducen drásticamente las respuestas
  inventadas; la verificación post-generación (grounding check) es la más efectiva.
- La separación clara entre capas (`models / repositories / services / agents / api`) facilita
  ampliar el agente con nuevos nodos o reemplazar el LLM sin tocar el resto del código.
- Limitaciones de inferencia CPU sugieren que en producción se debería contar con GPU o
  considerar modelos pequeños (Gemma 2 2B, Llama 3.2 3B) para tiempo de respuesta interactivo.
