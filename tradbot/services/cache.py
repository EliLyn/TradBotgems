"""
Gerenciador de Cache com expiração (TTL) e suporte a fallback de dados legados.
"""

import json
import os
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, Any

logger = logging.getLogger("tradbot.cache")


class CacheManager:
    def __init__(self, cache_file: str, expiry_hours: int = 6):
        self.cache_file = cache_file
        self.expiry_hours = expiry_hours

    def get(self, ignore_expiry: bool = False) -> Optional[Any]:
        """Recupera dados do cache se ainda não tiverem expirado (ou forçado por ignore_expiry)."""
        if not os.path.exists(self.cache_file):
            return None

        try:
            with open(self.cache_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Compatibilidade com formato novo ("data") e legado ("tokens")
            payload_data = data.get("data") if "data" in data else data.get("tokens")
            if payload_data is None:
                return None

            if ignore_expiry:
                return payload_data

            raw_time = data.get("timestamp")
            if not raw_time:
                return payload_data

            cached_time = datetime.fromisoformat(raw_time)
            if cached_time.tzinfo is None:
                cached_time = cached_time.replace(tzinfo=timezone.utc)

            now_utc = datetime.now(timezone.utc)
            if (now_utc - cached_time) < timedelta(hours=self.expiry_hours):
                logger.info(f"Dados válidos carregados do cache local ({self.cache_file}).")
                return payload_data
            else:
                logger.info(f"Cache ({self.cache_file}) tem mais de {self.expiry_hours}h.")
                return None
        except Exception as e:
            logger.warning(f"Falha ao ler cache {self.cache_file}: {e}")
            return None

    def get_fallback(self) -> Optional[Any]:
        """Recupera qualquer dado disponível no arquivo de cache, mesmo expirado."""
        return self.get(ignore_expiry=True)

    def set(self, data: Any) -> bool:
        """Salva dados no arquivo de cache (apenas se houver dados válidos)."""
        if not data:
            logger.debug("Tentativa de salvar cache vazio ignorada para preservar dados existentes.")
            return False

        try:
            payload = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "tokens": data
            }
            with open(self.cache_file, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2, ensure_ascii=False)
            logger.debug(f"Cache salvo com sucesso em {self.cache_file}.")
            return True
        except Exception as e:
            logger.error(f"Erro ao salvar cache em {self.cache_file}: {e}")
            return False
