from collections.abc import Generator
import re

from openai import OpenAI

from app.core.config import get_settings


def _normalize_sentence(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def _dedupe_answer(text: str) -> str:
    if not text:
        return text

    parts = re.split(r"(?<=[.!?])\s+", text)
    output: list[str] = []
    seen_count: dict[str, int] = {}
    prev = ""
    for part in parts:
        norm = _normalize_sentence(part)
        if not norm:
            continue
        if norm == prev:
            continue
        # Keep at most one repeated identical sentence globally.
        count = seen_count.get(norm, 0)
        if count >= 1:
            continue
        seen_count[norm] = count + 1
        output.append(part.strip())
        prev = norm

    cleaned = " ".join(output).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned


def stream_answer(prompt: str, temperature: float, max_output_tokens: int) -> Generator[str, None, None]:
    settings = get_settings()

    provider = settings.llm_provider.lower().strip()
    client: OpenAI | None = None
    model: str | None = None

    if provider == "groq" and settings.groq_api_key:
        client = OpenAI(
            api_key=settings.groq_api_key,
            base_url="https://api.groq.com/openai/v1",
            max_retries=1,
            timeout=25.0,
        )
        model = settings.groq_model
    elif provider == "openai" and settings.openai_api_key:
        client = OpenAI(api_key=settings.openai_api_key, max_retries=1, timeout=25.0)
        model = settings.openai_model

    if client is None or model is None:
        # Fallback demo mode when API key is not configured.
        yield from _yield_demo_fallback(prompt)
        return

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            max_tokens=max_output_tokens,
        )
        text = (response.choices[0].message.content or "").strip()
        cleaned = _dedupe_answer(text)
        if not cleaned:
            cleaned = "Khong tim thay thong tin trong tai lieu da cung cap."
        for token in cleaned.split():
            yield token + " "
    except Exception as exc:
        raw_error = str(exc)
        normalized = raw_error.lower()
        if "rate_limit_exceeded" in normalized or "rate limit" in normalized or "error code: 429" in normalized:
            # Keep chat usable by falling back to demo-style response when provider quota is exhausted.
            yield from _yield_demo_fallback(prompt)
            return
        else:
            message = f"[LLM error] Khong the lay phan hoi tu {provider}. Vui long thu lai sau."
        for token in message.split():
            yield token + " "


def _yield_demo_fallback(prompt: str) -> Generator[str, None, None]:
    del prompt
    fallback = (
        "Khong tim thay thong tin trong tai lieu da cung cap. "
        "Vui long thu lai sau hoac dat cau hoi cu the hon."
    )
    for token in fallback.split():
        yield token + " "
