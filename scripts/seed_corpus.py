"""scripts/seed_corpus.py

Bulk-upload every supported file from a local directory into the running
backend so the agent has a ready-to-query corpus for the demo. The script
authenticates against Keycloak using the Resource Owner Password Credentials
flow (only enabled for the `demo` user in the seeded realm, NOT recommended
for production).

Usage:
    python scripts/seed_corpus.py /path/to/corpus

Env vars:
    BACKEND_URL          default http://localhost:8000
    KEYCLOAK_TOKEN_URL   default http://localhost:8080/realms/rag/protocol/openid-connect/token
    KEYCLOAK_CLIENT_ID   default rag-frontend
    SEED_USERNAME        default demo
    SEED_PASSWORD        default demo
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

try:
    import httpx
except ImportError:  # pragma: no cover
    print("This script requires `httpx`. Install with: pip install httpx", file=sys.stderr)
    sys.exit(1)

SUPPORTED = {".pdf", ".txt", ".md", ".markdown", ".docx"}


def get_token() -> str:
    url = os.getenv(
        "KEYCLOAK_TOKEN_URL",
        "http://localhost:8080/realms/rag/protocol/openid-connect/token",
    )
    data = {
        "grant_type": "password",
        "client_id": os.getenv("KEYCLOAK_CLIENT_ID", "rag-frontend"),
        "username": os.getenv("SEED_USERNAME", "demo"),
        "password": os.getenv("SEED_PASSWORD", "demo"),
    }
    resp = httpx.post(url, data=data, timeout=10.0)
    resp.raise_for_status()
    return resp.json()["access_token"]


def upload(client: httpx.Client, path: Path, token: str) -> None:
    with path.open("rb") as fh:
        files = {"file": (path.name, fh, "application/octet-stream")}
        r = client.post(
            "/documents",
            files=files,
            headers={"Authorization": f"Bearer {token}"},
            timeout=120.0,
        )
    r.raise_for_status()
    payload = r.json()
    print(f"  ✓ {path.name}  →  {payload['chunk_count']} chunks")


def main(corpus_dir: Path) -> None:
    if not corpus_dir.is_dir():
        sys.exit(f"Not a directory: {corpus_dir}")

    files = sorted(p for p in corpus_dir.iterdir() if p.suffix.lower() in SUPPORTED)
    if not files:
        sys.exit(f"No supported files in {corpus_dir}. Supported: {sorted(SUPPORTED)}")

    print(f"Authenticating to Keycloak as '{os.getenv('SEED_USERNAME', 'demo')}'…")
    token = get_token()

    base = os.getenv("BACKEND_URL", "http://localhost:8000")
    print(f"Uploading {len(files)} files to {base} …")
    with httpx.Client(base_url=base) as client:
        for path in files:
            upload(client, path, token)
    print("Done.")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("Usage: python scripts/seed_corpus.py <corpus_dir>")
    main(Path(sys.argv[1]))
