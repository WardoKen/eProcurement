from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any


def is_debug_enabled() -> bool:
    try:
        from django.conf import settings

        return bool(getattr(settings, "DEBUG", False))
    except Exception:
        return os.getenv("DJANGO_DEBUG", "False").lower() in {"1", "true", "yes"}


def get_debug_dir() -> Path:
    try:
        from django.conf import settings

        backend_dir = Path(getattr(settings, "BASE_DIR"))
        debug_dir = backend_dir.parent / "debug"
    except Exception:
        debug_dir = Path.cwd() / "debug"

    debug_dir.mkdir(parents=True, exist_ok=True)
    return debug_dir


def write_debug_json(filename: str, payload: Any) -> None:
    if not is_debug_enabled():
        return
    output_path = get_debug_dir() / filename
    with open(output_path, "w", encoding="utf-8") as file_handle:
        json.dump(payload, file_handle, indent=2, ensure_ascii=False)


def get_parser_logger() -> logging.Logger:
    logger = logging.getLogger("ocr.parser")
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    logger.propagate = False

    if is_debug_enabled():
        log_path = get_debug_dir() / "parser.log"
        handler = logging.FileHandler(log_path, encoding="utf-8")
        formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger
