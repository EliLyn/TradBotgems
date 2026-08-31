"""
Cliente de integração com a API CoinGlass (funções <= 25 linhas).
"""

from typing import Optional
from ..config import settings
from ..models import DerivativesMetrics
from .base import BaseHttpClient


def _parse_overview(data: dict, m: DerivativesMetrics):
    """Extrai métricas de OI, Funding Rate, L/S Ratio e Volume de Futuros."""
    oi_list = data.get("openInterest") or []
    if isinstance(oi_list, list) and oi_list:
        m.open_interest = sum(i.get("openInterest", 0) for i in oi_list if i.get("openInterest") is not None)
    fr = data.get("avgFundingRate")
    if fr is not None:
        m.funding_rate = fr * 100
    m.long_short_ratio = data.get("longShortRatio")
    m.futures_volume_24h_usd = data.get("vol24h")


def _parse_liquidations(items: list, m: DerivativesMetrics):
    """Calcula soma das liquidações de long e short em 24h."""
    m.liquidation_long_24h_usd = sum(i.get("longVol", 0) or 0 for i in items if isinstance(i, dict))
    m.liquidation_short_24h_usd = sum(i.get("shortVol", 0) or 0 for i in items if isinstance(i, dict))


class CoinGlassClient(BaseHttpClient):
    def __init__(self, session=None, api_key: Optional[str] = None):
        super().__init__(session)
        self.api_key = api_key or settings.coinglass.api_key
        self.base_url = settings.coinglass.base_url

    def _get_headers(self) -> dict:
        """Retorna cabeçalhos com a chave secreta da CoinGlass."""
        return {"accept": "application/json", "coinglassSecret": self.api_key}

    async def get_derivatives_data(self, symbol: str) -> DerivativesMetrics:
        """Busca dados de derivativos (OI, Funding Rate, L/S Ratio, Liquidações) da CoinGlass."""
        m = DerivativesMetrics()
        if not self.api_key:
            return m
        h = self._get_headers()
        sym = symbol.upper().replace("USDT", "").replace("USD", "")
        ov = await self.fetch_json(f"{self.base_url}/coin_summary?symbol={sym}", headers=h)
        if ov and ov.get("code") == "0" and ov.get("data"):
            _parse_overview(ov["data"], m)
        liq = await self.fetch_json(f"{self.base_url}/liquidation?symbol={sym}&time_type=24h", headers=h)
        if liq and liq.get("code") == "0" and liq.get("data"):
            _parse_liquidations(liq["data"], m)
        return m
