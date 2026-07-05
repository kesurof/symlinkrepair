from pydantic import BaseModel
from datetime import datetime


class Scan(BaseModel):
    id: int | None = None
    path: str
    status: str = "pending"
    broken_count: int = 0
    created_at: str | None = None
    completed_at: str | None = None


class Result(BaseModel):
    id: int | None = None
    scan_id: int
    symlink_path: str
    target_path: str | None = None
    status: str = "broken"
    action: str | None = None
