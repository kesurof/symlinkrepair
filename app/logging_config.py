import json
import logging
import logging.handlers
import os
import re
import sys
from datetime import datetime, timezone

DISCORD_PATTERN = re.compile(r"discord\.com/api/webhooks/\S+", re.IGNORECASE)
KV_PATTERNS = [
    re.compile(r"(api_key|apikey)\s*[:=]\s*['\"]?\S+['\"]?", re.IGNORECASE),
    re.compile(r"(webhook|webhook_url)\s*[:=]\s*['\"]?\S+['\"]?", re.IGNORECASE),
    re.compile(r"(token|secret|password)\s*[:=]\s*['\"]?\S+['\"]?", re.IGNORECASE),
]


def _redact(text: str) -> str:
    text = DISCORD_PATTERN.sub("discord.com/api/webhooks/***REDACTED***", text)
    for pattern in KV_PATTERNS:
        text = pattern.sub(r"\1=***REDACTED***", text)
    return text


class SensitiveDataFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = _redact(record.msg)
        if record.args:
            record.args = tuple(_redact(a) if isinstance(a, str) else a for a in record.args)
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        super().format(record)
        return json.dumps(
            {
                "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
                "level": record.levelname,
                "logger": record.name,
                "message": record.getMessage(),
            }
        )


class PrettyFormatter(logging.Formatter):
    COLORS = {
        logging.DEBUG: "\033[2m",
        logging.INFO: "",
        logging.WARNING: "\033[33m",
        logging.ERROR: "\033[31m",
        logging.CRITICAL: "\033[41m\033[37m",
    }
    RESET = "\033[0m"
    EMOJIS = {
        "main": "🚀",
        "database": "💾",
        "scheduler": "🔄",
        "scanner": "🔍",
        "filescanner": "📂",
        "cleanup": "🗑️",
        "verifier": "⏳",
        "sonarr": "📡",
        "radarr": "📡",
        "discord": "💬",
        "scan": "🔍",
        "results": "📋",
        "reports": "📊",
        "api_config": "⚙️",
        "config_service": "⚙️",
        "error_handlers": "❌",
    }

    def format(self, record: logging.LogRecord) -> str:
        emoji = self.EMOJIS.get(record.module, "")
        if emoji:
            record.module = f"{emoji} {record.module}"
        formatted = super().format(record)
        color = self.COLORS.get(record.levelno, "")
        return f"{color}{formatted}{self.RESET}" if color else formatted


def setup_logging():
    level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    log_format = os.getenv("LOG_FORMAT", "text").lower()
    log_file = os.getenv("LOG_FILE", "")

    base_fmt = "%(asctime)s [%(levelname)-5s] [%(module)s] %(message)s"
    base_datefmt = "%m-%d %H:%M:%S"

    if log_format == "json":
        formatter = JsonFormatter()
    elif log_format == "pretty":
        formatter = PrettyFormatter(fmt=base_fmt, datefmt=base_datefmt)
    else:
        formatter = logging.Formatter(fmt=base_fmt, datefmt=base_datefmt)

    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    root_logger = logging.getLogger()
    if root_logger.handlers:
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)

    root_logger.setLevel(level)
    sensitive_filter = SensitiveDataFilter()

    if log_file:
        file_handler = logging.handlers.RotatingFileHandler(
            log_file, maxBytes=10_485_760, backupCount=5, encoding="utf-8"
        )
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        file_handler.addFilter(sensitive_filter)
        root_logger.addHandler(file_handler)

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setLevel(level)
    stream_handler.setFormatter(formatter)
    stream_handler.addFilter(sensitive_filter)
    root_logger.addHandler(stream_handler)
