import json
import math
import os
import re
import time
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from openai import OpenAI
from sentence_transformers import SentenceTransformer


ROOT = Path(__file__).resolve().parent
DOCS_PATH = ROOT / "chroma_data" / "edu_documents.json"
QA_PATH = ROOT / "data" / "education_knowledge.json"
RESULT_PATH = ROOT / "eval_three_scenarios_results.json"

SAMPLE_SIZE = 50
TOP_K_LIST = [1, 3, 5]
RAG_TOP_K = 3

EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
LLM_MODEL = "mixtral-8x7b-32768"
LLM_TEMPERATURE = 0.7
LLM_MAX_TOKENS = 500


@dataclass
class QAItem:
    qid: str
    question: str
    answer: str
    source: str


def repair_mojibake(text: str) -> str:
    if not text:
        return text
    if "Ã" not in text and "Æ" not in text and "á»" not in text:
        return text
    for codec in ("latin1", "cp1252"):
        try:
            repaired = text.encode(codec, errors="strict").decode("utf-8", errors="strict")
            if repaired.count(" ") >= text.count(" "):
                return repaired
        except Exception:
            continue
    return text


def strip_accents(text: str) -> str:
    out = text.replace("đ", "d").replace("Đ", "D")
    out = unicodedata.normalize("NFD", out)
    out = "".join(ch for ch in out if unicodedata.category(ch) != "Mn")
    return out


def normalize(text: str) -> str:
    text = repair_mojibake(text)
    text = strip_accents(text.lower())
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def tokenize(text: str) -> list[str]:
    return re.findall(r"[a-zA-Z0-9_]+", normalize(text))


def safe_env(path: Path) -> dict[str, str]:
    data: dict[str, str] = {}
    if not path.exists():
        return data
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        data[k.strip()] = v.strip()
    return data


def load_data(sample_size: int) -> tuple[list[str], list[QAItem], list[QAItem]]:
    docs_raw = json.loads(DOCS_PATH.read_text(encoding="utf-8"))
    docs = [repair_mojibake(str(row.get("content", ""))) for row in docs_raw]

    qa_raw = json.loads(QA_PATH.read_text(encoding="utf-8"))
    qa_subset = [
        QAItem(
            qid=str(row.get("id", "")),
            question=repair_mojibake(str(row.get("question", ""))),
            answer=repair_mojibake(str(row.get("answer", ""))),
            source=repair_mojibake(str(row.get("source", ""))),
        )
        for row in qa_raw[:sample_size]
    ]
    qa_full = [
        QAItem(
            qid=str(row.get("id", "")),
            question=repair_mojibake(str(row.get("question", ""))),
            answer=repair_mojibake(str(row.get("answer", ""))),
            source=repair_mojibake(str(row.get("source", ""))),
        )
        for row in qa_raw
    ]
    return docs, qa_subset, qa_full


def build_ground_truth(qa_items: list[QAItem], docs: list[str]) -> dict[str, set[int]]:
    gt: dict[str, set[int]] = {}
    for qa in qa_items:
        ids_match = {i for i, d in enumerate(docs) if qa.qid and qa.qid in d}
        if ids_match:
            gt[qa.qid] = ids_match
            continue

        source_n = normalize(qa.source)
        source_match = {i for i, d in enumerate(docs) if source_n and source_n in normalize(d)}
        if source_match:
            gt[qa.qid] = source_match
            continue

        ans_n = normalize(qa.answer)
        ans_match = {
            i
            for i, d in enumerate(docs)
            if ans_n and (ans_n[:120] in normalize(d) or ans_n[:80] in normalize(d))
        }
        gt[qa.qid] = ans_match
    return gt


def retrieval_metrics(
    ranked: dict[str, list[int]],
    ground_truth: dict[str, set[int]],
    k_values: list[int],
) -> dict[str, float]:
    out: dict[str, float] = {}
    for k in k_values:
        recall_vals: list[float] = []
        precision_vals: list[float] = []
        mrr_vals: list[float] = []
        for qid, pred in ranked.items():
            rel = ground_truth.get(qid, set())
            if not rel:
                recall_vals.append(0.0)
                precision_vals.append(0.0)
                mrr_vals.append(0.0)
                continue

            topk = pred[:k]
            hits = len(rel.intersection(topk))
            recall_vals.append(hits / max(len(rel), 1))
            precision_vals.append(hits / float(k))

            rr = 0.0
            for rank, doc_id in enumerate(topk, start=1):
                if doc_id in rel:
                    rr = 1.0 / rank
                    break
            mrr_vals.append(rr)

        out[f"Recall@{k}"] = float(np.mean(recall_vals))
        out[f"Precision@{k}"] = float(np.mean(precision_vals))
        out[f"MRR@{k}"] = float(np.mean(mrr_vals))
    return out


def create_llm_client(env_cfg: dict[str, str]) -> tuple[OpenAI | None, str, str]:
    if env_cfg.get("GROQ_API_KEY"):
        client = OpenAI(
            api_key=env_cfg["GROQ_API_KEY"],
            base_url="https://api.groq.com/openai/v1",
            max_retries=0,
            timeout=20.0,
        )
        return client, "groq", LLM_MODEL
    if env_cfg.get("OPENAI_API_KEY"):
        client = OpenAI(api_key=env_cfg["OPENAI_API_KEY"], max_retries=0, timeout=20.0)
        return client, "openai", LLM_MODEL
    return None, "none", "fallback"


def build_rag_prompt(question: str, contexts: list[str]) -> str:
    ctx_block = "\n\n".join([f"[{i + 1}] {c}" for i, c in enumerate(contexts)])
    return (
        "Ban la tro ly tu van giao duc ICTU.\n"
        "Chi tra loi dua tren ngu canh da cho.\n"
        "Neu khong du thong tin, tra loi: Khong tim thay thong tin trong tai lieu da cung cap.\n\n"
        f"Ngu canh:\n{ctx_block}\n\n"
        f"Cau hoi: {question}\n"
        "Tra loi bang tieng Viet, ngan gon va chinh xac."
    )


def generate_answer(
    client: OpenAI | None,
    question: str,
    contexts: list[str] | None,
    model: str,
    temperature: float,
    max_tokens: int,
) -> tuple[str, float, str]:
    prompt = build_rag_prompt(question, contexts or []) if contexts is not None else question
    start = time.time()

    if client is None:
        if contexts:
            fallback = " ".join(contexts[:2]).strip()
            text = fallback[:700] if fallback else "Khong tim thay thong tin trong tai lieu da cung cap."
        else:
            text = "Khong tim thay thong tin trong tai lieu da cung cap."
        return text, (time.time() - start) * 1000.0, "fallback"

    try:
        res = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        txt = (res.choices[0].message.content or "").strip()
        if not txt:
            txt = "Khong tim thay thong tin trong tai lieu da cung cap."
        return txt, (time.time() - start) * 1000.0, model
    except BaseException as ex:
        if contexts:
            fallback = " ".join(contexts[:2]).strip()
            txt = fallback[:700] if fallback else "Khong tim thay thong tin trong tai lieu da cung cap."
        else:
            txt = "Khong tim thay thong tin trong tai lieu da cung cap."
        tag = "fallback-rate-limit" if "429" in str(ex) else "fallback"
        return txt, (time.time() - start) * 1000.0, tag


def clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def score_two_experts(pred: str, ref: str, emb_model: SentenceTransformer) -> dict[str, Any]:
    vec = emb_model.encode([pred, ref], normalize_embeddings=True, convert_to_numpy=True)
    cos = float(vec[0] @ vec[1])
    p_tok = set(tokenize(pred))
    r_tok = set(tokenize(ref))
    overlap = len(p_tok.intersection(r_tok)) / max(len(r_tok), 1)

    # Expert A
    acc_a = 1.0 if cos >= 0.82 else (0.5 if cos >= 0.68 else 0.0)
    comp_a = int(round(clamp(1.0 + overlap * 4.5, 1.0, 5.0)))
    nat_a = 3
    if 10 <= len(tokenize(pred)) <= 130:
        nat_a += 1
    if pred.strip().endswith((".", "!", "?")):
        nat_a += 1
    if "khong tim thay thong tin" in normalize(pred):
        nat_a -= 1
    nat_a = int(clamp(float(nat_a), 1.0, 5.0))

    # Expert B
    acc_b = 1.0 if (cos >= 0.78 and overlap >= 0.28) else (0.5 if (cos >= 0.62 and overlap >= 0.18) else 0.0)
    comp_b = int(round(clamp(1.0 + overlap * 5.0, 1.0, 5.0)))
    nat_b = 2
    wc = len(tokenize(pred))
    if 12 <= wc <= 160:
        nat_b += 2
    if "," in pred or ";" in pred or ":" in pred:
        nat_b += 1
    if "khong tim thay thong tin" in normalize(pred):
        nat_b -= 1
    nat_b = int(clamp(float(nat_b), 1.0, 5.0))

    return {
        "cosine": cos,
        "overlap": overlap,
        "expert_a": {"accuracy": acc_a, "completeness": comp_a, "naturalness": nat_a},
        "expert_b": {"accuracy": acc_b, "completeness": comp_b, "naturalness": nat_b},
        "avg": {
            "accuracy": (acc_a + acc_b) / 2.0,
            "completeness": (comp_a + comp_b) / 2.0,
            "naturalness": (nat_a + nat_b) / 2.0,
        },
    }


def tfidf_build(corpus_texts: list[str]) -> tuple[list[dict[str, float]], list[float], dict[str, float]]:
    tokenized = [tokenize(t) for t in corpus_texts]
    n = len(tokenized)

    df: dict[str, int] = {}
    for toks in tokenized:
        for t in set(toks):
            df[t] = df.get(t, 0) + 1

    idf = {t: math.log((1 + n) / (1 + d)) + 1.0 for t, d in df.items()}

    vecs: list[dict[str, float]] = []
    norms: list[float] = []
    for toks in tokenized:
        tf: dict[str, float] = {}
        for t in toks:
            tf[t] = tf.get(t, 0.0) + 1.0
        if toks:
            inv_len = 1.0 / len(toks)
            for t in list(tf.keys()):
                tf[t] = tf[t] * inv_len * idf.get(t, 1.0)
        norm = math.sqrt(sum(v * v for v in tf.values()))
        vecs.append(tf)
        norms.append(norm)

    return vecs, norms, idf


def tfidf_query_vec(text: str, idf: dict[str, float]) -> tuple[dict[str, float], float]:
    toks = tokenize(text)
    tf: dict[str, float] = {}
    for t in toks:
        tf[t] = tf.get(t, 0.0) + 1.0
    if toks:
        inv_len = 1.0 / len(toks)
        for t in list(tf.keys()):
            tf[t] = tf[t] * inv_len * idf.get(t, 1.0)
    norm = math.sqrt(sum(v * v for v in tf.values()))
    return tf, norm


def tfidf_best_match(
    query: str,
    doc_vecs: list[dict[str, float]],
    doc_norms: list[float],
    idf: dict[str, float],
) -> int:
    qv, qn = tfidf_query_vec(query, idf)
    if qn <= 1e-12:
        return 0

    best_idx = 0
    best_score = -1.0
    for i, dv in enumerate(doc_vecs):
        dn = doc_norms[i]
        if dn <= 1e-12:
            continue
        dot = 0.0
        for t, val in qv.items():
            dot += val * dv.get(t, 0.0)
        score = dot / (qn * dn)
        if score > best_score:
            best_score = score
            best_idx = i
    return best_idx


def summarize_scores(rows: list[dict[str, Any]]) -> dict[str, float]:
    return {
        "Accuracy": float(np.mean([r["scores"]["avg"]["accuracy"] for r in rows])) if rows else 0.0,
        "Completeness": float(np.mean([r["scores"]["avg"]["completeness"] for r in rows])) if rows else 0.0,
        "Naturalness": float(np.mean([r["scores"]["avg"]["naturalness"] for r in rows])) if rows else 0.0,
        "MeanLatencyMs": float(np.mean([r["latency_ms"] for r in rows])) if rows else 0.0,
    }


def main() -> None:
    t0 = time.time()
    docs, qa_items, qa_full = load_data(SAMPLE_SIZE)

    emb_model = SentenceTransformer(EMBEDDING_MODEL)
    docs_emb = emb_model.encode(docs, normalize_embeddings=True, convert_to_numpy=True)

    ground_truth = build_ground_truth(qa_items, docs)

    # Scenario 1: Retrieval evaluation
    ranked: dict[str, list[int]] = {}
    for qa in qa_items:
        qv = emb_model.encode([qa.question], normalize_embeddings=True, convert_to_numpy=True)[0]
        sims = docs_emb @ qv
        top = np.argsort(-sims)[: max(TOP_K_LIST)]
        ranked[qa.qid] = [int(i) for i in top]

    scenario1 = {
        "objective": "Evaluate retrieval effectiveness using all-MiniLM-L6-v2 with cosine similarity",
        "model": EMBEDDING_MODEL,
        "similarity": "cosine",
        "metrics": retrieval_metrics(ranked, ground_truth, TOP_K_LIST),
    }

    env_cfg = {**safe_env(ROOT / ".env"), **os.environ}
    client, llm_provider, llm_model = create_llm_client(env_cfg)
    if llm_model == "fallback":
        llm_model = LLM_MODEL

    # Scenario 2: Generation evaluation with two independent experts (proxy)
    scenario2_rows: list[dict[str, Any]] = []
    rag_answers_by_qid: dict[str, str] = {}
    rag_latency_by_qid: dict[str, float] = {}

    for qa in qa_items:
        top_docs = ranked[qa.qid][:RAG_TOP_K]
        contexts = [docs[i] for i in top_docs]
        pred, latency_ms, used_model = generate_answer(
            client=client,
            question=qa.question,
            contexts=contexts,
            model=llm_model,
            temperature=LLM_TEMPERATURE,
            max_tokens=LLM_MAX_TOKENS,
        )
        scores = score_two_experts(pred, qa.answer, emb_model)
        row = {
            "id": qa.qid,
            "question": qa.question,
            "reference": qa.answer,
            "prediction": pred,
            "latency_ms": latency_ms,
            "model": used_model,
            "scores": scores,
        }
        scenario2_rows.append(row)
        rag_answers_by_qid[qa.qid] = pred
        rag_latency_by_qid[qa.qid] = latency_ms
        if used_model == "fallback-rate-limit":
            client = None

    scenario2 = {
        "objective": "Evaluate answer generation quality at top_k=3",
        "llm": {
            "provider": llm_provider,
            "model": llm_model,
            "temperature": LLM_TEMPERATURE,
            "max_tokens": LLM_MAX_TOKENS,
        },
        "expert_protocol": {
            "accuracy_scale": [0.0, 0.5, 1.0],
            "completeness_scale": "1-5",
            "naturalness_scale": "1-5",
            "note": "This run uses two automatic proxy experts to emulate independent grading.",
        },
        "summary": summarize_scores(scenario2_rows),
        "details": scenario2_rows,
    }

    # Scenario 3: Compare with baselines
    faq_questions = [x.question for x in qa_full]
    faq_answers = [x.answer for x in qa_full]
    faq_vecs, faq_norms, faq_idf = tfidf_build(faq_questions)

    rag_rows: list[dict[str, Any]] = []
    llm_only_rows: list[dict[str, Any]] = []
    faq_rows: list[dict[str, Any]] = []

    for qa in qa_items:
        rag_pred = rag_answers_by_qid[qa.qid]
        rag_latency = rag_latency_by_qid[qa.qid]
        rag_scores = score_two_experts(rag_pred, qa.answer, emb_model)
        rag_rows.append({"id": qa.qid, "prediction": rag_pred, "latency_ms": rag_latency, "scores": rag_scores})

        llm_pred, llm_latency, llm_used = generate_answer(
            client=client,
            question=qa.question,
            contexts=None,
            model=llm_model,
            temperature=LLM_TEMPERATURE,
            max_tokens=LLM_MAX_TOKENS,
        )
        llm_scores = score_two_experts(llm_pred, qa.answer, emb_model)
        llm_only_rows.append(
            {
                "id": qa.qid,
                "prediction": llm_pred,
                "latency_ms": llm_latency,
                "model": llm_used,
                "scores": llm_scores,
            }
        )
        if llm_used == "fallback-rate-limit":
            client = None

        t_faq = time.time()
        idx = tfidf_best_match(qa.question, faq_vecs, faq_norms, faq_idf)
        faq_pred = faq_answers[idx]
        faq_latency = (time.time() - t_faq) * 1000.0
        faq_scores = score_two_experts(faq_pred, qa.answer, emb_model)
        faq_rows.append(
            {
                "id": qa.qid,
                "matched_question": faq_questions[idx],
                "prediction": faq_pred,
                "latency_ms": faq_latency,
                "scores": faq_scores,
            }
        )

    scenario3 = {
        "objective": "Compare RAG against LLM-only and FAQ TF-IDF baselines",
        "systems": {
            "RAG": summarize_scores(rag_rows),
            "Baseline1_LLMOnly": summarize_scores(llm_only_rows),
            "Baseline2_FAQ_TFIDF": summarize_scores(faq_rows),
        },
        "details": {
            "RAG": rag_rows,
            "Baseline1_LLMOnly": llm_only_rows,
            "Baseline2_FAQ_TFIDF": faq_rows,
        },
    }

    final_compare = [
        {
            "System": "RAG",
            "Accuracy": f"{scenario3['systems']['RAG']['Accuracy']:.3f}",
            "Completeness": f"{scenario3['systems']['RAG']['Completeness']:.3f}",
            "Naturalness": f"{scenario3['systems']['RAG']['Naturalness']:.3f}",
            "MeanLatencyMs": f"{scenario3['systems']['RAG']['MeanLatencyMs']:.2f}",
        },
        {
            "System": "Baseline1_LLMOnly",
            "Accuracy": f"{scenario3['systems']['Baseline1_LLMOnly']['Accuracy']:.3f}",
            "Completeness": f"{scenario3['systems']['Baseline1_LLMOnly']['Completeness']:.3f}",
            "Naturalness": f"{scenario3['systems']['Baseline1_LLMOnly']['Naturalness']:.3f}",
            "MeanLatencyMs": f"{scenario3['systems']['Baseline1_LLMOnly']['MeanLatencyMs']:.2f}",
        },
        {
            "System": "Baseline2_FAQ_TFIDF",
            "Accuracy": f"{scenario3['systems']['Baseline2_FAQ_TFIDF']['Accuracy']:.3f}",
            "Completeness": f"{scenario3['systems']['Baseline2_FAQ_TFIDF']['Completeness']:.3f}",
            "Naturalness": f"{scenario3['systems']['Baseline2_FAQ_TFIDF']['Naturalness']:.3f}",
            "MeanLatencyMs": f"{scenario3['systems']['Baseline2_FAQ_TFIDF']['MeanLatencyMs']:.2f}",
        },
    ]

    result = {
        "sample_size": len(qa_items),
        "scenarios": {
            "3.3.1_retrieval": scenario1,
            "3.3.2_generation": scenario2,
            "3.3.3_baseline_comparison": scenario3,
        },
        "final_compare": final_compare,
        "runtime_seconds": round(time.time() - t0, 2),
        "notes": [
            "Ground truth docs were inferred from qid/source/answer alignment because explicit chunk labels are unavailable.",
            "Generation quality uses two automatic proxy experts; for publication, replace with human expert ratings.",
            "If LLM API is unavailable, script falls back to extractive behavior to keep benchmarking runnable.",
        ],
    }

    RESULT_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved report: {RESULT_PATH}")


if __name__ == "__main__":
    main()
