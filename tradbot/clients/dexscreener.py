"""
Cliente de integração com a API DexScreener (Mercado descentralizado, pares e liquidez).
"""

import logging
from typing import List, Optional
from ..models import DexPairInfo
from .base import BaseHttpClient
from datetime import datetime

logger = logging.getLogger("tradbot.dexscreener")


class DexScreenerClient(BaseHttpClient):
    BASE_URL = "https://api.dexscreener.com/latest/dex"

    async def get_pairs_by_token(self, token_address: str) -> List[DexPairInfo]:
        """Busca todos os pares de DEX de um endereço de token."""
        url = f"{self.BASE_URL}/tokens/{token_address}"
        data = await self.fetch_json(url)
        if not data or "pairs" not in data or not data["pairs"]:
            return []

        pairs_list: List[DexPairInfo] = []
        for p in data["pairs"]:
            try:
                created_at = None
                if p.get("pairCreatedAt"):
                    created_at = datetime.utcfromtimestamp(p["pairCreatedAt"] / 1000.0)

                txns_m5_h1 = (p.get("txns", {}).get("h1", {}).get("buys", 0) or 0) + (p.get("txns", {}).get("h1", {}).get("sells", 0) or 0)

                pair_info = DexPairInfo(
                    chain_id=p.get("chainId", ""),
                    dex_id=p.get("dexId", ""),
                    pair_address=p.get("pairAddress", ""),
                    base_token_symbol=p.get("baseToken", {}).get("symbol", ""),
                    base_token_address=p.get("baseToken", {}).get("address", ""),
                    quote_token_symbol=p.get("quoteToken", {}).get("symbol", ""),
                    price_usd=float(p.get("priceUsd", 0)) if p.get("priceUsd") else None,
                    liquidity_usd=float(p.get("liquidity", {}).get("usd", 0)) if p.get("liquidity", {}).get("usd") else None,
                    volume_24h_usd=float(p.get("volume", {}).get("h24", 0)) if p.get("volume", {}).get("h24") else None,
                    txns_60m=txns_m5_h1,
                    pair_created_at=created_at
                )
                pairs_list.append(pair_info)
            except Exception as e:
                logger.debug(f"Erro ao converter par DexScreener: {e}")

        return pairs_list
