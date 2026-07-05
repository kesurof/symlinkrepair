from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.models.config import AppConfig
from app.services.config_service import (
    browse_directory,
    load_config,
    public_config,
    save_config,
    test_radarr_connection,
    test_sonarr_connection,
)

router = APIRouter()


@router.get("/api/config")
async def get_config():
    return public_config()


@router.post("/api/config")
async def update_config(cfg: AppConfig):
    save_config(cfg)
    return {"ok": True}


@router.get("/api/browse")
async def browse(path: str = "/mnt"):
    config = load_config()
    result = browse_directory(path, config.browse_roots)
    if result is None:
        return JSONResponse({"error": "Chemin non autorisé ou invalide"}, status_code=403)
    return result


@router.get("/api/config/default-browse-roots")
async def default_browse_roots():
    return {"roots": load_config().browse_roots}


@router.post("/api/config/test-radarr")
async def test_radarr(request: Request):
    body = await request.json()
    return await test_radarr_connection(body.get("url", ""), body.get("api_key", ""))


@router.post("/api/config/test-sonarr")
async def test_sonarr(request: Request):
    body = await request.json()
    return await test_sonarr_connection(body.get("url", ""), body.get("api_key", ""))
