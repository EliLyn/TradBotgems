"""
Cliente de integração com a API CoinGecko com funções <= 25 linhas.
"""

from typing import List, Optional, Dict, Any
from ..config import settings
from ..models import TokenFullDetails
from .base import BaseHttpClient


def _extract_links(links: dict, comm: dict) -> tuple:
    """Extrai links de redes sociais e contagens da comunidade."""
    tw = links.get("twitter_screen_name") or "N/A"
    tw_f = comm.get("twitter_followers") or 0
    tg = links.get("telegram_channel_identifier") or "N/A"
    tg_m = comm.get("telegram_channel_user_count") or 0
    disc = next((c for c in links.get("chat_url", []) if "discord" in c), "N/A")
    hp = (links.get("homepage") or ["N/A"])[0] or "N/A"
    return hp, tw, tw_f, tg, tg_m, disc


def _extract_contract(data: dict) -> tuple:
    """Extrai endereço de contrato e blockchain associada."""
    pid = data.get("asset_platform_id") or "N/A"
    addr = data.get("platforms", {}).get(pid) if pid != "N/A" else None
    return pid, addr


class CoinGeckoClient(BaseHttpClient):
    def __init__(self, session=None, base_url: Optional[str] = None):
        super().__init__(session)
        self.base_url = base_url or settings.coingecko.base_url

    async def get_markets_page(self, page: int, per_page: int = 300, vs_currency: str = "usd") -> Optional[List[Dict[str, Any]]]:
        """Busca uma página do ranking de mercado."""
        url = f"{self.base_url}/coins/markets?vs_currency={vs_currency}&order=market_cap_desc&per_page={per_page}&page={page}&sparkline=false&price_change_percentage=24h,7d"
        return await self.fetch_json(url)

    async def get_token_details(self, token_id: str) -> Optional[TokenFullDetails]:
        """Busca os dados detalhados de um token específico na CoinGecko."""
        url = f"{self.base_url}/coins/{token_id}?localization=true&tickers=false&market_data=true&community_data=true&developer_data=false&sparkline=false"
        data = await self.fetch_json(url)
        if not data:
            return None
        mdata = data.get("market_data", {})
        desc = (data.get("description", {}).get("pt") or data.get("description", {}).get("en") or "N/A")
        cats = ", ".join(data.get("categories", [])) if data.get("categories") else "N/A"
        hp, tw, tw_f, tg, tg_m, disc = _extract_links(data.get("links", {}), data.get("community_data", {}))
        pid, addr = _extract_contract(data)
        return TokenFullDetails(
            id=data.get("id", token_id), symbol=data.get("symbol", "").upper(), name=data.get("name", ""),
            market_cap_usd=mdata.get("market_cap", {}).get("usd"), current_price_usd=mdata.get("current_price", {}).get("usd"),
            total_supply=mdata.get("total_supply"), circulating_supply=mdata.get("circulating_supply"),
            description=desc, categories=cats, blockchain_id=pid, contract_address=addr,
            homepage=hp, twitter_handle=tw, twitter_followers=tw_f, telegram_url=tg,
            telegram_channel_user_count=tg_m, subreddit_url=data.get("links", {}).get("subreddit_url") or "N/A", discord_link=disc
        )
