from app.db.session import engine
from app.models.base import Base
from app.models.chat import ChatMessage, ChatSession
from app.models.document import Document
from app.models.usage import AnonymousUsage
from app.models.user import User, PasswordReset


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
