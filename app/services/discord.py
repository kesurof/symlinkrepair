import logging
from datetime import datetime, timezone

import httpx

logger = logging.getLogger(__name__)


def _build_embed(title: str, description: str, color: int, fields: list[dict]) -> dict:
    return {
        "embeds": [
            {
                "title": title,
                "description": description,
                "color": color,
                "fields": fields,
                "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            }
        ]
    }


async def send_webhook(webhook_url: str, payload: dict) -> bool:
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(webhook_url, json=payload)
            ok = resp.status_code in (200, 204)
            logger.info("Discord webhook sent: status=%d ok=%s", resp.status_code, ok)
            return ok
    except Exception as e:
        logger.warning("Discord webhook failed: %s", e)
        return False


async def notify_scan(config, source: str, scan_result: dict) -> bool:
    if not config.discord.enabled or not config.discord.webhook:
        return False

    logger.debug("Discord notify: source=%s event=scan", source)
    mode = scan_result.get("mode", "simulate")
    is_simulate = mode == "simulate"
    color = 0x57F287 if is_simulate else 0xFEE75C
    label = "Simulation" if is_simulate else "Nettoyage"
    title = f"{'🟢' if is_simulate else '🟡'} Scan {source} — {label}"

    fields = [
        {"name": "Source", "value": source, "inline": True},
        {"name": "Mode", "value": mode, "inline": True},
        {"name": "Statut", "value": scan_result.get("status", "?"), "inline": True},
        {"name": "Total symlinks", "value": str(scan_result.get("total", 0)), "inline": True},
        {"name": "Matchant préfixes", "value": str(scan_result.get("matching", 0)), "inline": True},
        {"name": "Cassés", "value": str(scan_result.get("broken", 0)), "inline": True},
    ]

    desc = f"{scan_result.get('broken', 0)} symlinks cassés détectés"
    payload = _build_embed(title, desc, color, fields)
    return await send_webhook(config.discord.webhook, payload)


async def notify_cleanup(config, result: dict, action_log: dict) -> bool:
    if not config.discord.enabled or not config.discord.webhook:
        return False

    logger.debug(
        "Discord notify: source=%s event=cleanup title=%s",
        result.get("source", "?"),
        result.get("media_title", "?"),
    )
    ok = action_log.get("api_delete", False)
    color = 0x57F287 if ok else 0xED4245
    title = f"{'✅' if ok else '❌'} Nettoyage — {result.get('media_title') or 'Sans titre'}"

    actions = []
    if action_log.get("api_delete"):
        actions.append("DELETE API")
    if action_log.get("symlink_removed"):
        actions.append("symlink supprimé")
    if action_log.get("refresh"):
        actions.append("refresh")
    if action_log.get("search"):
        actions.append("recherche")

    fields = [
        {"name": "Source", "value": str(result.get("source", "?")), "inline": True},
        {"name": "Titre", "value": str(result.get("media_title", "?")), "inline": True},
        {"name": "Actions", "value": ", ".join(actions) or "aucune", "inline": False},
    ]

    payload = _build_embed(title, f"Traitement de {result.get('media_title', '?')}", color, fields)
    return await send_webhook(config.discord.webhook, payload)


async def notify_season_cleanup(
    config, series_title: str, season: int, source: str, outcome: dict
) -> bool:
    if not config.discord.enabled or not config.discord.webhook:
        return False

    processed = outcome.get("processed", 0)
    total = outcome.get("total", 0)
    ok = processed > 0
    all_ok = processed == total and total > 0

    if all_ok:
        color = 0x57F287
        emoji = "✅"
    elif ok:
        color = 0xFEE75C
        emoji = "⚠️"
    else:
        color = 0xED4245
        emoji = "❌"

    title = f"{emoji} Saison nettoyée — {series_title} S{season}"

    actions = []
    actions_log = outcome.get("actions", {})
    if actions_log.get("api_delete"):
        actions.append("DELETE API")
    if actions_log.get("symlink_removed"):
        actions.append("symlink supprimé")
    if actions_log.get("refresh"):
        actions.append("refresh")
    if actions_log.get("search"):
        actions.append("recherche")

    fields = [
        {"name": "Source", "value": source, "inline": True},
        {"name": "Saison", "value": f"S{season}", "inline": True},
        {"name": "Traités", "value": f"{processed} / {total}", "inline": True},
        {"name": "Actions", "value": ", ".join(actions) or "aucune", "inline": False},
    ]

    payload = _build_embed(
        title, f"{processed}/{total} épisodes traités pour {series_title} S{season}", color, fields
    )
    return await send_webhook(config.discord.webhook, payload)
