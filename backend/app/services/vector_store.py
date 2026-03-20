import json
import re
import unicodedata
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
from rank_bm25 import BM25Okapi

from app.core.config import get_settings


def _storage_path() -> Path:
    settings = get_settings()
    persist_dir = Path(settings.chroma_persist_dir)
    persist_dir.mkdir(parents=True, exist_ok=True)
    return persist_dir / f"{settings.chroma_collection}.json"


def _load_rows() -> list[dict[str, Any]]:
    path = _storage_path()
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def _save_rows(rows: list[dict[str, Any]]) -> None:
    path = _storage_path()
    path.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")


def _normalize(text: str) -> str:
    text = text.replace("đ", "d").replace("Đ", "D")
    text = unicodedata.normalize("NFD", text.lower())
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _tokenize(text: str) -> list[str]:
    return _normalize(text).split()


def _minmax_norm(values: np.ndarray) -> np.ndarray:
    if values.size == 0:
        return values
    lo = float(values.min())
    hi = float(values.max())
    if hi - lo < 1e-9:
        return np.zeros_like(values)
    return (values - lo) / (hi - lo)


def _dataset_signature(path: Path) -> str:
    if not path.exists():
        return "missing"
    stat = path.stat()
    return f"{path}:{int(stat.st_mtime)}:{stat.st_size}"


@lru_cache(maxsize=1)
def _get_bm25_index(signature: str) -> tuple[BM25Okapi | None, list[dict[str, Any]]]:
    del signature
    rows = _load_rows()
    if not rows:
        return None, rows
    tokenized_docs = [_tokenize(str(row.get("content", ""))) for row in rows]
    return BM25Okapi(tokenized_docs), rows


def upsert_chunks(document_id: int, chunks: list[str], embeddings: list[list[float]], source: str) -> None:
    rows = [row for row in _load_rows() if row.get("metadata", {}).get("document_id") != document_id]
    for idx, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
        rows.append(
            {
                "id": f"doc-{document_id}-chunk-{idx}",
                "content": chunk,
                "embedding": embedding,
                "metadata": {
                    "document_id": document_id,
                    "source": source,
                    "chunk_index": idx,
                },
            }
        )
    _save_rows(rows)
    _get_bm25_index.cache_clear()


def delete_document_chunks(document_id: int) -> None:
    rows = [row for row in _load_rows() if row.get("metadata", {}).get("document_id") != document_id]
    _save_rows(rows)
    _get_bm25_index.cache_clear()


def query_chunks(query_embedding: list[float], top_k: int) -> list[dict[str, Any]]:
    rows = _load_rows()
    if not rows:
        return []

    q = np.array(query_embedding, dtype=np.float32)
    q_norm = np.linalg.norm(q)
    if q_norm == 0:
        return []

    scored: list[tuple[float, dict[str, Any]]] = []
    for row in rows:
        emb = np.array(row.get("embedding", []), dtype=np.float32)
        denom = (np.linalg.norm(emb) * q_norm)
        if denom == 0:
            continue
        similarity = float(np.dot(q, emb) / denom)
        scored.append((similarity, row))

    scored.sort(key=lambda item: item[0], reverse=True)
    top = scored[:top_k]

    return [
        {
            "content": row.get("content", ""),
            "metadata": row.get("metadata", {}),
            "distance": 1.0 - similarity,
        }
        for similarity, row in top
    ]


def query_chunks_hybrid(
    query_text: str,
    query_embedding: list[float],
    top_k: int,
    alpha: float = 0.55,
    candidate_pool: int = 24,
) -> list[dict[str, Any]]:
    path = _storage_path()
    signature = _dataset_signature(path)
    bm25, rows = _get_bm25_index(signature)
    if not rows:
        return []

    q = np.array(query_embedding, dtype=np.float32)
    q_norm = np.linalg.norm(q)
    if q_norm == 0:
        return []

    bm25_scores = (
        np.asarray(bm25.get_scores(_tokenize(query_text)), dtype=np.float32)
        if bm25 is not None
        else np.zeros(len(rows), dtype=np.float32)
    )
    vec_scores = np.zeros(len(rows), dtype=np.float32)

    for idx, row in enumerate(rows):
        emb = np.array(row.get("embedding", []), dtype=np.float32)
        denom = np.linalg.norm(emb) * q_norm
        if denom <= 0:
            continue
        vec_scores[idx] = float(np.dot(q, emb) / denom)

    hybrid_scores = alpha * _minmax_norm(bm25_scores) + (1.0 - alpha) * _minmax_norm(vec_scores)
    top_n = max(top_k, candidate_pool)
    top_indices = np.argsort(-hybrid_scores)[:top_n]

    results: list[dict[str, Any]] = []
    for idx in top_indices[:top_k]:
        row = rows[int(idx)]
        vec_sim = float(vec_scores[int(idx)])
        results.append(
            {
                "content": row.get("content", ""),
                "metadata": row.get("metadata", {}),
                "distance": 1.0 - vec_sim,
                "score": float(hybrid_scores[int(idx)]),
                "lexical_score": float(bm25_scores[int(idx)]),
                "semantic_score": vec_sim,
            }
        )

    return results
