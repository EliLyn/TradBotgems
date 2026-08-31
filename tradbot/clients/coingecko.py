"""
Cliente de integração com a API CoinGecko.
"""

import asyncio
import logging
from typing import List, Optional, Dict, Any
from ..config import settings
from ..models import TokenMarketSummary, TokenFullDetails
from .base import BaseHttpClient

logger = logging.getLogger("tradbot.coingecko")


class CoinGeckoClient(BaseHttpClient):
    def __init__(self, session=None, base_url: Optional[str] = None):
        super().__init__(session)
        self.base_url = base_url or settings.coingecko.base_url

    async def get_markets_page(
        self,
        page: int,
        per_page: int = 300,
        vs_currency: str = "usd"
    ) -> Optional[List[Dict[str, Any]]]:
        """Busca uma página do ranking de mercado."""
        url = (
            f"{self.base_url}/coins/markets"
            f"?vs_currency={vs_currency}&order=market_cap_desc"
            f"&per_page={per_page}&page={page}&sparkline=false"
            f"&price_change_percentage=24h,7d"
        )
        return await self.fetch_json(url)

    async def get_token_details(self, token_id: str) -> Optional[TokenFullDetails]:
        """Busca os dados detalhados de um token específico na CoinGecko."""
        url = (
            f"{self.base_url}/coins/{token_id}"
            f"?localization=true&tickers=false&market_data=true"
            f"&community_data=true&developer_data=false&sparkline=false"
        )
        data = await self.fetch_json(url)
        if not data:
            return None

        market_data = data.get("market_data", {})
        links = data.get("links", {})
        community_data = data.get("community_data", {})
        platforms_data = data.get("platforms", {})
        asset_platform_id = data.get("asset_platform_id") or "N/A"

        contract_address = None
        if asset_platform_id != "N/A" and asset_platform_id in platforms_data:
            contract_address = platforms_data.get(asset_platform_id)

        # Descrição (preferência português, fallback inglês)
        descriptions = data.get("description", {})
        description = descriptions.get("pt") or descriptions.get("en") or "N/A"

        # Categorias
        categories = data.get("categories", [])
        categories_str = ", ".join(categories) if categories else "N/A"

        # Homepage
        homepages = links.get("homepage", [])
        homepage = homepages[0] if homepages and homepages[0] else "N/A"

        # Discord
        discord_link = "N/A"
        for chat_url in links.get("chat_url", []):
            if "discord" in chat_url:
                discord_link = chat_url
                break

        return TokenFullDetails(
            id=data.get("id", token_id),
            symbol=data.get("symbol", "").upper(),
            name=data.get("name", ""),
            market_cap_usd=market_data.get("market_cap", {}).get("usd"),
            current_price_usd=market_data.get("current_price", {}).get("usd"),
            total_supply=market_data.get("total_supply"),
            circulating_supply=market_data.get("circulating_supply"),
            description=description,
            categories=categories_str,
            blockchain_id=asset_platform_id,
            contract_address=contract_address,
            homepage=homepage,
            twitter_handle=links.get("twitter_screen_name") or "N/A",
            twitter_followers=community_data.get("twitter_followers") or 0,
            telegram_url=links.get("telegram_channel_identifier") or "N/A",
            telegram_channel_user_count=community_data.get("telegram_channel_user_count") or 0,
            subreddit_url=links.get("subreddit_url") or "N/A",
            discord_link=discord_link,
        )
