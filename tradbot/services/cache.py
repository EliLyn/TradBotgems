"""
Gerenciador de Cache com TTL e fallback (funções <= 25 linhas).
"""

import json
import os
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, Any

logger = logging.getLogger("tradbot.cache")


def _is_cache_valid(raw_time: Optional[str], hours: int) -> bool:
    """Verifica se o timestamp UTC do cache está dentro do TTL."""
    if not raw_time:
        return True
    try:
        cached = datetime.fromisoformat(raw_time)
        if cached.tzinfo is None:
            cached = cached.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - cached) < timedelta(hours=hours)
    except (ValueError, TypeError):
        return False


def _read_cache_file(filepath: str) -> Optional[dict]:
    """Lê e desserializa o arquivo JSON de cache."""
    if not os.path.exists(filepath):
        return None
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"Erro ao ler cache {filepath}: {e}")
        return None


class CacheManager:
    def __init__(self, cache_file: str, expiry_hours: int = 6):
        self.cache_file = cache_file
        self.expiry_hours = expiry_hours

    def get(self, ignore_expiry: bool = False) -> Optional[Any]:
        """Recupera dados do cache se válidos."""
        doc = _read_cache_file(self.cache_file)
        if not doc:
            return None
        payload = doc.get("data") if "data" in doc else doc.get("tokens")
        if payload is None:
            return None
        if ignore_expiry or _is_cache_valid(doc.get("timestamp"), self.expiry_hours):
            return payload
        return None

    def get_fallback(self) -> Optional[Any]:
        """Recupera qualquer dado em cache como fallback."""
        return self.get(ignore_expiry=True)

    def set(self, data: Any) -> bool:
        """Salva dados com timestamp UTC."""
        if not data:
            return False
        try:
            payload = {"timestamp": datetime.now(timezone.utc).isoformat(), "tokens": data}
            with open(self.cache_file, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            logger.error(f"Erro ao salvar cache: {e}")
            return False
