from __future__ import annotations

import hashlib
import math
import os

import httpx

from app.llm import llm_configured
from app.models import Document


def statement_text(document: Document) -> str:
    return f"{document.title}\n{document.statement}"


def statement_hash(document: Document) -> str:
    return hashlib.sha256(statement_text(document).encode()).hexdigest()


def cosine(left: list[float], right: list[float]) -> float:
    dot = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return dot / (left_norm * right_norm)


LAST_ERROR = ""


def embed_texts(texts: list[str]) -> list[list[float]] | None:
    global LAST_ERROR
    LAST_ERROR = ""
    if not llm_configured() or not texts:
        LAST_ERROR = "no_key"
        return None
    api_key = os.environ.get("LLM_API_KEY", "").strip()
    base_url = os.environ.get("LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    model = os.environ.get("EMBED_MODEL", "text-embedding-3-small")
    try:
        response = httpx.post(
            f"{base_url}/embeddings",
            headers={"Authorization": f"Bearer {api_key}"},
            json={"model": model, "input": texts},
            timeout=30,
        )
        response.raise_for_status()
        rows = sorted(response.json()["data"], key=lambda item: item["index"])
        return [row["embedding"] for row in rows]
    except httpx.HTTPStatusError as exc:
        LAST_ERROR = f"http {exc.response.status_code}"
        return None
    except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError):
        LAST_ERROR = "request_failed"
        return None


def ensure_statement_embeddings(path, documents: list[Document]) -> dict[tuple[str, int], list[float]]:
    from app.db import load_statement_embeddings, save_statement_embeddings

    if not llm_configured():
        return {}
    model = os.environ.get("EMBED_MODEL", "text-embedding-3-small")
    stored = load_statement_embeddings(path)
    missing: list[tuple[Document, str]] = []
    for document in documents:
        if not document.chunks:
            continue
        digest = statement_hash(document)
        current = stored.get((document.version_id, 0))
        if current and current[0] == digest and current[1] == model:
            continue
        missing.append((document, digest))
    if missing:
        vectors = embed_texts([statement_text(document) for document, _digest in missing])
        if not vectors or len(vectors) != len(missing):
            return {
                key: row[2]
                for key, row in stored.items()
            }
        save_statement_embeddings(
            path,
            [
                (document.version_id, 0, digest, model, vector)
                for (document, digest), vector in zip(missing, vectors)
            ],
        )
        for (document, digest), vector in zip(missing, vectors):
            stored[(document.version_id, 0)] = (digest, model, vector)
    return {key: row[2] for key, row in stored.items()}
