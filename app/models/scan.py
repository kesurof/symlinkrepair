from pydantic import BaseModel


class Scan(BaseModel):
    id: int | None = None
    source: str
    mode: str = "simulate"
    status: str = "running"
    total: int = 0
    broken: int = 0
    processed: int = 0
    summary: str | None = None
    report_file: str | None = None
    created_at: str | None = None
    completed_at: str | None = None


class Result(BaseModel):
    id: int | None = None
    scan_id: int
    source: str
    symlink_path: str
    target_path: str | None = None
    media_type: str | None = None
    media_title: str | None = None
    season: int | None = None
    episode: int | None = None
    file_id: int | None = None
    tags: str | None = None
    detection: str = "broken_symlink"
    status: str = "détecté"
    action: str | None = None
    action_date: str | None = None
    notes: str | None = None
