"""
Cliente de integração com a API CoinGlass (Derivativos, OI, Funding Rate, Liquidações).
"""

import logging
from typing import Optional
from ..config import settings
from ..models import DerivativesMetrics
from .base import BaseHttpClient

logger = logging.getLogger("tradbot.coinglass")


class CoinGlassClient(BaseHttpClient):
    def __init__(self, session=None, api_key: Optional[str] = None):
        super().__init__(session)
        self.api_key = api_key or settings.coinglass.api_key
        self.base_url = settings.coinglass.base_url

    def _get_headers(self):
        return {
            "accept": "application/json",
            "coinglassSecret": self.api_key
        }

    async def get_derivatives_data(self, symbol: str) -> DerivativesMetrics:
        """Busca dados de derivativos (OI, Funding Rate, L/S Ratio, Liquidações) da CoinGlass."""
        metrics = DerivativesMetrics()
        if not self.api_key:
            return metrics

        headers = self._get_headers()
        clean_symbol = symbol.upper().replace("USDT", "").replace("USD", "")

        # 1. Resumo da moeda (OI, Funding Rate, Long/Short Ratio, Volume)
        overview_url = f"{self.base_url}/coin_summary?symbol={clean_symbol}"
        overview_data = await self.fetch_json(overview_url, headers=headers)

        if overview_data and overview_data.get("code") == "0" and overview_data.get("data"):
            data_dict = overview_data["data"]
            
            # Open Interest
            oi_list = data_dict.get("openInterest")
            if oi_list and isinstance(oi_list, list):
                total_oi = sum(item.get("openInterest", 0) for item in oi_list if item.get("openInterest") is not None)
                metrics.open_interest = total_oi

            # Funding Rate (convertido para porcentagem)
            avg_fr = data_dict.get("avgFundingRate")
            if avg_fr is not None:
                metrics.funding_rate = avg_fr * 100

            # Long/Short Ratio
            metrics.long_short_ratio = data_dict.get("longShortRatio")

            # Futures Volume 24h
            metrics.futures_volume_24h_usd = data_dict.get("vol24h")

        # 2. Liquidações nas últimas 24h
        liquidation_url = f"{self.base_url}/liquidation?symbol={clean_symbol}&time_type=24h"
        liquidation_data = await self.fetch_json(liquidation_url, headers=headers)

        if liquidation_data and liquidation_data.get("code") == "0" and liquidation_data.get("data"):
            items = liquidation_data["data"]
            total_long = 0.0
            total_short = 0.0
            for item in items:
                total_long += item.get("longVol", 0) or 0
                total_short += item.get("shortVol", 0) or 0
            metrics.liquidation_long_24h_usd = total_long
            metrics.liquidation_short_24h_usd = total_short

        return metrics
