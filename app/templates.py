from pathlib import Path

import jinja2
from fastapi.templating import Jinja2Templates

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"


def date_fr(value):
    """Convert ISO date string to French format: DD/MM/YYYY HH:MM"""
    if not value:
        return ""
    date_part = value[:10]
    time_part = value[11:16] if len(value) >= 16 else ""
    parts = date_part.split("-")
    if len(parts) == 3:
        result = f"{parts[2]}/{parts[1]}/{parts[0]}"
        if time_part:
            result += f" {time_part}"
        return result
    return value


def path_filename(value):
    """Extract filename from a file path"""
    if not value:
        return ""
    return value.split("/")[-1]


jinja_env = jinja2.Environment(
    loader=jinja2.FileSystemLoader(TEMPLATES_DIR),
    cache_size=50,
    auto_reload=True,
)

jinja_env.filters["date_fr"] = date_fr
jinja_env.filters["path_filename"] = path_filename

templates = Jinja2Templates(env=jinja_env)
