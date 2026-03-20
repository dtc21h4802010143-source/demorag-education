from datetime import datetime

from pydantic import BaseModel


class DocumentOut(BaseModel):
    id: int
    filename: str
    file_type: str
    status: str
    chunk_count: int
    created_at: datetime

    class Config:
        from_attributes = True
