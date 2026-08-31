"""
Cliente de detecção de Honeypot (Segurança on-chain).
"""

import logging
from typing import Optional
from .base import BaseHttpClient

logger = logging.getLogger("tradbot.honeypot")


class HoneypotClient(BaseHttpClient):
    BASE_URL = "https://api.honeypot.is/v1/IsHoneypot"

    async def check_token(self, token_address: str, chain_id: str = "eth") -> Optional[bool]:
        """
        Verifica se um token é Honeypot.
        Retorna True se for Honeypot (risco), False se for seguro, ou None em caso de falha de consulta.
        """
        chain_mapping = {
            "ethereum": "eth",
            "bsc": "bsc",
            "polygon": "polygon",
            "arbitrum": "arb",
            "optimism": "opt",
            "base": "base"
        }
        network = chain_mapping.get(chain_id.lower(), chain_id.lower())

        url = f"{self.BASE_URL}?address={token_address}&chainID={network}"
        data = await self.fetch_json(url)
        if data and "honeypotResult" in data:
            return bool(data["honeypotResult"].get("isHoneypot", False))
        return None
