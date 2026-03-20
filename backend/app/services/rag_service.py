from collections.abc import Generator
from functools import lru_cache
import logging
import re

from sentence_transformers import CrossEncoder

from app.core.config import get_settings
from app.services.embedding_service import embed_query
from app.services.llm_service import stream_answer
from app.services.vector_store import query_chunks, query_chunks_hybrid


logger = logging.getLogger("educhat.rag")


TOPIC_SYNONYMS: dict[str, list[str]] = {
    "tuyen sinh": ["xet tuyen", "phuong thuc tuyen sinh", "chi tieu"],
    "hoc phi": ["muc thu", "hoc phi tin chi", "mien giam hoc phi"],
    "chuong trinh": ["khung chuong trinh", "so tin chi", "mon hoc bat buoc"],
    "hoc vu": ["quy che hoc vu", "dieu kien tot nghiep", "canh bao hoc tap"],
    "thu tuc": ["ho so", "quy trinh", "giay to can nop"],
}


def _normalize_query(text: str) -> str:
    return " ".join((text or "").lower().split())


def _query_expansions(question: str, limit: int) -> list[str]:
    q = _normalize_query(question)
    expansions = [question]
    for key, values in TOPIC_SYNONYMS.items():
        if key in q:
            for item in values[:limit]:
                expansions.append(f"{question}. Tu khoa lien quan: {item}")
            break
    return expansions[: max(1, limit + 1)]


@lru_cache(maxsize=1)
def _get_reranker(model_name: str) -> CrossEncoder | None:
    try:
        return CrossEncoder(model_name)
    except Exception:
        return None


def _rerank_contexts(question: str, contexts: list[dict], model_name: str, top_k: int) -> list[dict]:
    if not contexts:
        return contexts
    reranker = _get_reranker(model_name)
    if reranker is None:
        return contexts[:top_k]

    pairs = [(question, str(item.get("content", ""))) for item in contexts]
    scores = reranker.predict(pairs)
    scored = sorted(zip(contexts, scores), key=lambda x: float(x[1]), reverse=True)
    return [ctx for ctx, _ in scored[:top_k]]


def _merge_ranked_contexts(rank_lists: list[list[dict]], limit: int) -> list[dict]:
    merged: dict[str, dict] = {}
    for ranked in rank_lists:
        for item in ranked:
            key = str(item.get("metadata", {}).get("document_id", "")) + "::" + str(
                item.get("metadata", {}).get("chunk_index", "")
            )
            if key not in merged:
                merged[key] = item
            else:
                merged[key]["score"] = max(float(merged[key].get("score", 0.0)), float(item.get("score", 0.0)))

    ordered = sorted(merged.values(), key=lambda row: float(row.get("score", 0.0)), reverse=True)
    return ordered[:limit]


def _norm_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def _dedupe_contexts(contexts: list[dict]) -> list[dict]:
    seen: set[str] = set()
    out: list[dict] = []
    for item in contexts:
        content_key = _norm_text(str(item.get("content", "")))[:400]
        src = str(item.get("metadata", {}).get("source", ""))
        chunk = str(item.get("metadata", {}).get("chunk_index", ""))
        key = f"{src}::{chunk}::{content_key}"
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def _top_score(contexts: list[dict]) -> float:
    if not contexts:
        return 0.0
    top = contexts[0]
    if "score" in top:
        return float(top.get("score", 0.0))
    dist = float(top.get("distance", 1.0))
    return 1.0 - dist


def _yield_no_context_answer() -> Generator[str, None, None]:
    message = "Khong tim thay thong tin trong tai lieu da cung cap."
    for token in message.split():
        yield token + " "


def build_prompt(question: str, contexts: list[dict]) -> str:
    context_blocks = []
    for idx, item in enumerate(contexts, start=1):
        src = item.get("metadata", {}).get("source", "unknown")
        content = item.get("content", "")
        context_blocks.append(f"[{idx}] Source: {src}\n{content}")

    context_text = "\n\n".join(context_blocks) if context_blocks else "Khong tim thay ngu canh phu hop."
    return (
        "Ban la tro ly tu van giao duc.\n"
        "Quy tac bat buoc:\n"
        "1) Chi duoc su dung thong tin trong Ngu canh.\n"
        "2) Neu thieu bang chung, tra loi: 'Khong tim thay thong tin trong tai lieu da cung cap.'.\n"
        "3) Trinh bay 2 phan: (A) Tra loi chinh, (B) Can cu [so].\n"
        "4) Uu tien thong tin cu the: moc thoi gian, muc phi, dieu kien, don vi xu ly.\n\n"
        "5) Khong lap lai thong tin, khong lap lai cau, toi da 5 y chinh.\n"
        "6) Khong duoc bo sung kien thuc ngoai Ngu canh.\n\n"
        f"Ngu canh:\n{context_text}\n\n"
        f"Cau hoi: {question}\n\n"
        "Tra loi bang tieng Viet."
    )


def stream_rag_response(question: str) -> tuple[Generator[str, None, None], list[dict]]:
    settings = get_settings()
    query_variants = [question]
    if settings.rag_enable_query_expansion:
        query_variants = _query_expansions(question, limit=settings.rag_query_expansion_limit)
    logger.info(
        "rag_query_start question_len=%s variants=%s top_k=%s hybrid=%s rerank=%s",
        len(question or ""),
        len(query_variants),
        settings.rag_top_k,
        settings.rag_enable_hybrid,
        settings.rag_enable_rerank,
    )

    ranked_lists: list[list[dict]] = []
    for query_text in query_variants:
        q_embedding = embed_query(query_text)
        if settings.rag_enable_hybrid:
            ranked = query_chunks_hybrid(
                query_text=query_text,
                query_embedding=q_embedding,
                top_k=max(settings.rag_top_k, settings.rag_candidate_pool // 2),
                alpha=settings.rag_hybrid_alpha,
                candidate_pool=settings.rag_candidate_pool,
            )
        else:
            ranked = query_chunks(q_embedding, top_k=settings.rag_top_k)
            for row in ranked:
                if "score" not in row:
                    row["score"] = 1.0 - float(row.get("distance", 1.0))
        ranked_lists.append(ranked)

    contexts = _merge_ranked_contexts(ranked_lists, limit=settings.rag_candidate_pool)
    contexts = _dedupe_contexts(contexts)
    if settings.rag_enable_rerank:
        contexts = _rerank_contexts(
            question=question,
            contexts=contexts,
            model_name=settings.rag_reranker_model,
            top_k=settings.rag_top_k,
        )
    else:
        contexts = contexts[: settings.rag_top_k]

    logger.info(
        "rag_contexts_ready count=%s top_score=%.4f min_count=%s min_conf=%.4f",
        len(contexts),
        _top_score(contexts),
        settings.rag_min_context_count,
        settings.rag_min_confidence,
    )

    if len(contexts) < settings.rag_min_context_count or _top_score(contexts) < settings.rag_min_confidence:
        logger.info("rag_fallback_no_context reason=threshold_not_met")
        return _yield_no_context_answer(), contexts

    prompt = build_prompt(question, contexts)
    generator = stream_answer(
        prompt=prompt,
        temperature=settings.rag_temperature,
        max_output_tokens=settings.rag_max_output_tokens,
    )
    return generator, contexts
