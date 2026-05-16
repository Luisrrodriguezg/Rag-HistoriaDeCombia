-- Initialization script executed by the official Postgres image on first boot.
-- Mounted as /docker-entrypoint-initdb.d/init.sql via docker-compose.
--
-- The `pgvector/pgvector:pg16` image already has the extension binaries
-- installed; we just need to enable it inside the `rag` database.

CREATE EXTENSION IF NOT EXISTS vector;
