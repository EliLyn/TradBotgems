"""
Cliente para exploradores de blocos EVM (Etherscan, BscScan, PolygonScan, etc.).
"""

import asyncio
import logging
from typing import Optional, Dict, Any
from ..config import settings
from .base import BaseHttpClient

logger = logging.getLogger("tradbot.evm")


class EvmExplorerClient(BaseHttpClient):
    def __init__(self, session=None):
        super().__init__(session)
        self.url_map = settings.explorers.url_map

    async def get_token_transactions(
        self,
        platform_id: str,
        contract_address: str,
        action: str = "tokentx",
        page: int = 1,
        offset: int = 100
    ) -> Optional[Dict[str, Any]]:
        """Busca transações de um token em uma chain EVM compatível."""
        base_url = self.url_map.get(platform_id.lower())
        if not base_url:
            logger.debug(f"Explorer não mapeado para a plataforma: {platform_id}")
            return None

        api_key = getattr(settings.explorers, f"{platform_id.replace('-', '_')}_api_key", settings.explorers.etherscan_api_key)

        url = (
            f"{base_url}?module=account&action={action}&contractaddress={contract_address}"
            f"&page={page}&offset={offset}&sort=desc&apikey={api_key}"
        )

        await asyncio.sleep(0.3)  # Respeita rate limit das APIs gratuitas
        data = await self.fetch_json(url)

        if data and data.get("status") == "0" and "rate limit" in str(data.get("message", "")).lower():
            logger.warning(f"EVM Explorer ({platform_id}): Rate limit atingido. Aguardando 30s...")
            await asyncio.sleep(30)
            return await self.fetch_json(url)

        return data
