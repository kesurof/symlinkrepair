from pathlib import Path

import jinja2
from fastapi.templating import Jinja2Templates

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"

jinja_env = jinja2.Environment(
    loader=jinja2.FileSystemLoader(TEMPLATES_DIR),
    cache_size=0,
    auto_reload=True,
)

templates = Jinja2Templates(env=jinja_env)
