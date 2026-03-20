from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.document import Document
from app.services.document_parser import extract_text
from app.services.embedding_service import embed_texts
from app.services.vector_store import delete_document_chunks, upsert_chunks
from app.utils.chunking import chunk_text


UPLOAD_DIR = Path("./uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
SEED_DATA_FILE = Path("./data/education_knowledge.json")


def save_upload_to_disk(filename: str, content: bytes) -> Path:
    target = UPLOAD_DIR / filename
    target.write_bytes(content)
    return target


def process_document(db: Session, document: Document, file_path: Path) -> Document:
    settings = get_settings()
    raw_text = extract_text(file_path)

    chunks = chunk_text(
        raw_text,
        chunk_size_words=settings.rag_chunk_size_words,
        overlap_words=settings.rag_chunk_overlap_words,
    )
    embeddings = embed_texts(chunks) if chunks else []

    delete_document_chunks(document.id)
    if chunks:
        upsert_chunks(document.id, chunks, embeddings, source=document.filename)

    document.status = "indexed"
    document.chunk_count = len(chunks)
    db.add(document)
    db.commit()
    db.refresh(document)
    return document


def create_document_record(db: Session, filename: str, file_type: str) -> Document:
    doc = Document(filename=filename, file_type=file_type, status="processing")
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


def delete_document(db: Session, document: Document) -> None:
    delete_document_chunks(document.id)

    file_path = UPLOAD_DIR / document.filename
    if file_path.exists():
        file_path.unlink()

    db.delete(document)
    db.commit()


def seed_json_knowledge_if_needed(db: Session) -> None:
    seed_name = "education_knowledge.json"
    if not SEED_DATA_FILE.exists():
        return

    existing = db.query(Document).filter(Document.filename == seed_name).first()
    if existing:
        return

    target = UPLOAD_DIR / seed_name
    if not target.exists():
        target.write_bytes(SEED_DATA_FILE.read_bytes())

    doc = create_document_record(db, filename=seed_name, file_type="json")
    process_document(db, doc, target)
