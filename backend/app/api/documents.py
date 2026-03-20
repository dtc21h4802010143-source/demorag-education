from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.db.session import get_db
from app.models.document import Document
from app.schemas.document import DocumentOut
from app.services.document_parser import UnsupportedFileTypeError
from app.services.document_service import (
    create_document_record,
    delete_document,
    process_document,
    save_upload_to_disk,
)

router = APIRouter(prefix="/documents", tags=["documents"])


@router.get("", response_model=list[DocumentOut])
def list_documents(db: Session = Depends(get_db)):
    return db.query(Document).order_by(Document.created_at.desc()).all()


@router.post("/upload", response_model=DocumentOut)
def upload_document(
    _: str = Depends(require_admin),
    db: Session = Depends(get_db),
    file: UploadFile = File(...),
):
    suffix = file.filename.split(".")[-1].lower() if file.filename and "." in file.filename else ""
    if suffix not in {"pdf", "docx", "txt", "json"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only PDF, DOCX, TXT, JSON are allowed")

    existing = db.query(Document).filter(Document.filename == file.filename).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File already exists")

    data = file.file.read()
    path = save_upload_to_disk(file.filename, data)

    doc = create_document_record(db, filename=file.filename, file_type=suffix)
    try:
        return process_document(db, doc, path)
    except UnsupportedFileTypeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/{document_id}/reindex", response_model=DocumentOut)
def reindex_document(document_id: int, _: str = Depends(require_admin), db: Session = Depends(get_db)):
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    from app.services.document_service import UPLOAD_DIR

    path = UPLOAD_DIR / doc.filename
    if not path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source file not found")

    doc.status = "processing"
    db.add(doc)
    db.commit()
    db.refresh(doc)

    return process_document(db, doc, path)


@router.delete("/{document_id}")
def remove_document(document_id: int, _: str = Depends(require_admin), db: Session = Depends(get_db)):
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    delete_document(db, doc)
    return {"message": "Deleted"}
