from pathlib import Path
import json

from docx import Document as DocxDocument
from pypdf import PdfReader


class UnsupportedFileTypeError(Exception):
    pass


def _flatten_json(value, out: list[str]) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            out.append(str(key))
            _flatten_json(item, out)
        return
    if isinstance(value, list):
        for item in value:
            _flatten_json(item, out)
        return
    if value is None:
        return
    out.append(str(value))


def extract_text(file_path: Path) -> str:
    suffix = file_path.suffix.lower()
    if suffix == ".txt":
        return file_path.read_text(encoding="utf-8", errors="ignore")

    if suffix == ".pdf":
        reader = PdfReader(str(file_path))
        pages = [page.extract_text() or "" for page in reader.pages]
        return "\n".join(pages)

    if suffix == ".docx":
        doc = DocxDocument(str(file_path))
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        return "\n".join(paragraphs)

    if suffix == ".json":
        raw = json.loads(file_path.read_text(encoding="utf-8", errors="ignore"))
        parts: list[str] = []
        _flatten_json(raw, parts)
        return "\n".join(parts)

    raise UnsupportedFileTypeError(f"Unsupported file type: {suffix}")
