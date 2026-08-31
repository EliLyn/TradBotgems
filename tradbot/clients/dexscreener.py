"""
Cliente de integração com a API DexScreener (funções <= 25 linhas).
"""

from typing import List, Optional
from ..models import DexPairInfo
from .base import BaseHttpClient
from datetime import datetime


def _parse_dex_pair(p: dict) -> Optional[DexPairInfo]:
    """Converte payload bruto do DexScreener em DexPairInfo."""
    try:
        created = datetime.utcfromtimestamp(p["pairCreatedAt"] / 1000.0) if p.get("pairCreatedAt") else None
        txns = (p.get("txns", {}).get("h1", {}).get("buys", 0) or 0) + (p.get("txns", {}).get("h1", {}).get("sells", 0) or 0)
        return DexPairInfo(
            chain_id=p.get("chainId", ""), dex_id=p.get("dexId", ""), pair_address=p.get("pairAddress", ""),
            base_token_symbol=p.get("baseToken", {}).get("symbol", ""), base_token_address=p.get("baseToken", {}).get("address", ""),
            quote_token_symbol=p.get("quoteToken", {}).get("symbol", ""),
            price_usd=float(p["priceUsd"]) if p.get("priceUsd") else None,
            liquidity_usd=float(p["liquidity"]["usd"]) if p.get("liquidity", {}).get("usd") else None,
            volume_24h_usd=float(p["volume"]["h24"]) if p.get("volume", {}).get("h24") else None,
            txns_60m=txns, pair_created_at=created
        )
    except (ValueError, KeyError, TypeError):
        return None


class DexScreenerClient(BaseHttpClient):
    BASE_URL = "https://api.dexscreener.com/latest/dex"

    async def get_pairs_by_token(self, token_address: str) -> List[DexPairInfo]:
        """Busca todos os pares de DEX de um token."""
        data = await self.fetch_json(f"{self.BASE_URL}/tokens/{token_address}")
        if not data or "pairs" not in data:
            return []
        pairs = [_parse_dex_pair(p) for p in data.get("pairs", [])]
        return [p for p in pairs if p is not None]
