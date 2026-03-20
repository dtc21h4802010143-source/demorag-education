import json
import logging
from collections.abc import Generator

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import AuthError, decode_access_token
from app.db.session import get_db
from app.models.chat import ChatMessage, ChatSession
from app.models.usage import AnonymousUsage
from app.schemas.chat import ChatAskRequest, ChatMessageOut, ChatSessionOut
from app.services.rag_service import stream_rag_response

router = APIRouter(prefix="/chat", tags=["chat"])
security = HTTPBearer(auto_error=False)
logger = logging.getLogger("educhat.chat")


def _to_sse(payload: dict) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


@router.get("/sessions", response_model=list[ChatSessionOut])
def list_sessions(db: Session = Depends(get_db)):
    return db.query(ChatSession).order_by(ChatSession.created_at.desc()).all()


@router.get("/quota")
def get_quota(client_id: str, db: Session = Depends(get_db)):
    settings = get_settings()
    row = db.query(AnonymousUsage).filter(AnonymousUsage.client_id == client_id).first()
    used = row.question_count if row else 0
    return {
        "limit": settings.anonymous_question_limit,
        "used": used,
        "remaining": max(0, settings.anonymous_question_limit - used),
    }


@router.get("/sessions/{session_id}/messages", response_model=list[ChatMessageOut])
def get_messages(session_id: int, db: Session = Depends(get_db)):
    session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    return (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.asc())
        .all()
    )


@router.delete("/sessions/{session_id}")
def delete_session(session_id: int, db: Session = Depends(get_db)):
    session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    db.delete(session)
    db.commit()
    return {"message": "Deleted"}


@router.delete("/sessions")
def delete_all_sessions(db: Session = Depends(get_db)):
    db.query(ChatMessage).delete()
    db.query(ChatSession).delete()
    db.commit()
    return {"message": "All history deleted"}


@router.post("/stream")
def ask_stream(
    payload: ChatAskRequest,
    request: Request,
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
):
    del request

    is_logged_in = False
    if credentials:
        try:
            token_data = decode_access_token(credentials.credentials)
            is_logged_in = token_data.get("role") in {"admin", "user"}
        except AuthError:
            is_logged_in = False

    settings = get_settings()
    logger.info(
        "chat_stream_received session_id=%s logged_in=%s client_id=%s question_len=%s",
        payload.session_id,
        is_logged_in,
        payload.client_id,
        len(payload.question or ""),
    )
    remaining = None
    if not is_logged_in:
        if not payload.client_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="client_id is required for anonymous chat",
            )

        usage = db.query(AnonymousUsage).filter(AnonymousUsage.client_id == payload.client_id).first()
        if usage is None:
            usage = AnonymousUsage(client_id=payload.client_id, question_count=0)
            db.add(usage)
            db.commit()
            db.refresh(usage)

        if usage.question_count >= settings.anonymous_question_limit:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Anonymous limit reached ({settings.anonymous_question_limit} questions). Please login.",
            )

        usage.question_count += 1
        db.add(usage)
        db.commit()
        remaining = max(0, settings.anonymous_question_limit - usage.question_count)

    if payload.session_id is None:
        title = payload.question[:80] if payload.question else "New chat"
        session = ChatSession(title=title)
        db.add(session)
        db.commit()
        db.refresh(session)
    else:
        session = db.query(ChatSession).filter(ChatSession.id == payload.session_id).first()
        if not session:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    session_id = session.id

    user_msg = ChatMessage(session_id=session_id, role="user", content=payload.question)
    db.add(user_msg)
    db.commit()

    token_stream, contexts = stream_rag_response(payload.question)
    logger.info(
        "chat_stream_contexts session_id=%s context_count=%s",
        session_id,
        len(contexts),
    )

    def event_stream() -> Generator[str, None, None]:
        full_answer = ""
        yield _to_sse(
            {
                "type": "meta",
                "session_id": session_id,
                "contexts": contexts,
                "is_logged_in": is_logged_in,
                "remaining_questions": remaining,
            }
        )

        for token in token_stream:
            full_answer += token
            yield _to_sse({"type": "token", "content": token})

        assistant_msg = ChatMessage(session_id=session_id, role="assistant", content=full_answer)
        db.add(assistant_msg)
        db.commit()
        logger.info(
            "chat_stream_done session_id=%s answer_len=%s",
            session_id,
            len(full_answer),
        )
        yield _to_sse({"type": "done"})

    return StreamingResponse(event_stream(), media_type="text/event-stream")
