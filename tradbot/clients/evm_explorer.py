"""
Cliente para exploradores de blocos EVM (funções <= 25 linhas).
"""

import asyncio
import logging
from typing import Optional, Dict, Any
from ..config import settings
from .base import BaseHttpClient

logger = logging.getLogger("tradbot.evm")


def _build_evm_url(base_url: str, action: str, address: str, page: int, offset: int, key: str) -> str:
    """Constrói a URL de requisição para exploradores EVM."""
    return f"{base_url}?module=account&action={action}&contractaddress={address}&page={page}&offset={offset}&sort=desc&apikey={key}"


class EvmExplorerClient(BaseHttpClient):
    def __init__(self, session=None):
        super().__init__(session)
        self.url_map = settings.explorers.url_map

    async def get_token_transactions(self, platform_id: str, contract_address: str, action: str = "tokentx", page: int = 1, offset: int = 100) -> Optional[Dict[str, Any]]:
        """Busca transações de um token em uma chain EVM."""
        base_url = self.url_map.get(platform_id.lower())
        if not base_url:
            return None
        api_key = getattr(settings.explorers, f"{platform_id.replace('-', '_')}_api_key", settings.explorers.etherscan_api_key)
        url = _build_evm_url(base_url, action, contract_address, page, offset, api_key)
        await asyncio.sleep(0.3)
        data = await self.fetch_json(url)
        if data and data.get("status") == "0" and "rate limit" in str(data.get("message", "")).lower():
            await asyncio.sleep(30)
            return await self.fetch_json(url)
        return data
