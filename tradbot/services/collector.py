"""
Orquestrador do Ciclo 24/7 de Caça a Gems (funções enxutas <= 25 linhas).
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import List, Optional

from ..config import settings
from ..models import TokenMarketSummary, TokenFullDetails
from ..clients.coingecko import CoinGeckoClient
from ..clients.coinglass import CoinGlassClient
from .analyzer import TokenAnalyzer
from .notifier import TelegramNotifier
from .cache import CacheManager

logger = logging.getLogger("tradbot.collector")


def _parse_tokens(data: list) -> List[TokenMarketSummary]:
    """Filtra e extrai tokens válidos dentro da faixa de market cap."""
    res = []
    for t in data:
        mcap = t.get("market_cap")
        tid = t.get("id")
        if tid and mcap and (settings.min_market_cap_usd <= mcap <= settings.max_market_cap_usd):
            res.append(TokenMarketSummary(
                id=tid, symbol=t.get("symbol", "").upper(), name=t.get("name", ""),
                market_cap=mcap, current_price=t.get("current_price") or 0.0,
                price_change_percentage_24h=t.get("price_change_percentage_24h_in_currency"),
                price_change_percentage_7d=t.get("price_change_percentage_7d_in_currency"),
                total_volume=t.get("total_volume")
            ))
    return res


async def _scan_pages(client: CoinGeckoClient) -> List[TokenMarketSummary]:
    """Varre as páginas da CoinGecko em ordem reversa."""
    tokens: List[TokenMarketSummary] = []
    for p in range(settings.coingecko.total_pages_to_check, 0, -1):
        data = await client.get_markets_page(page=p, per_page=settings.coingecko.per_page)
        if not data:
            break
        tokens.extend(_parse_tokens(data))
        if data[0].get("market_cap", 0) > settings.max_market_cap_usd:
            break
        await asyncio.sleep(settings.sleep_between_pages)
    tokens.sort(key=lambda x: x.market_cap)
    return tokens


def _load_fallback(cache: CacheManager) -> List[TokenMarketSummary]:
    """Carrega dados em cache como fallback se a rede falhar."""
    fb = cache.get_fallback() or []
    return [
        TokenMarketSummary(
            id=i.get("id", ""), symbol=i.get("symbol", "").upper(), name=i.get("name", ""),
            market_cap=i.get("market_cap") or 0.0, current_price=i.get("current_price") or 0.0,
            price_change_percentage_24h=i.get("price_change_percentage_24h"),
            price_change_percentage_7d=i.get("price_change_percentage_7d"),
            total_volume=i.get("total_volume")
        ) for i in fb if isinstance(i, dict)
    ]


class GemCollectorService:
    def __init__(self, cg: Optional[CoinGeckoClient] = None, cgl: Optional[CoinGlassClient] = None, an: Optional[TokenAnalyzer] = None, notif: Optional[TelegramNotifier] = None, cm: Optional[CacheManager] = None):
        self.coingecko = cg or CoinGeckoClient()
        self.coinglass = cgl or CoinGlassClient()
        self.analyzer = an or TokenAnalyzer()
        self.notifier = notif or TelegramNotifier()
        self.cache = cm or CacheManager(cache_file=settings.coingecko.cache_file, expiry_hours=settings.coingecko.cache_expiry_hours)

    async def close(self):
        """Encerra sessões HTTP abertas."""
        await self.coingecko.close()
        await self.coinglass.close()

    async def fetch_filtered_token_list(self) -> List[TokenMarketSummary]:
        """Busca lista de tokens (cache -> API -> fallback)."""
        cached = self.cache.get()
        if cached:
            return [TokenMarketSummary(**x) for x in cached if isinstance(x, dict)]
        tokens = await _scan_pages(self.coingecko)
        if tokens:
            self.cache.set([t.__dict__ for t in tokens])
            return tokens
        return _load_fallback(self.cache)

    async def process_token(self, token: TokenMarketSummary) -> bool:
        """Processa um token individual e envia notificação."""
        det = await self.coingecko.get_token_details(token.id) or TokenFullDetails(
            id=token.id, symbol=token.symbol, name=token.name,
            market_cap_usd=token.market_cap, current_price_usd=token.current_price,
            categories="Gems / Micro-Cap", description=f"Token {token.name} ({token.symbol})"
        )
        der = await self.coinglass.get_derivatives_data(token.symbol)
        an = self.analyzer.analyze_token(token.id, token.symbol, det)
        card = self.notifier.build_token_card(det, der, an, token.price_change_percentage_24h, token.price_change_percentage_7d, token.total_volume)
        return await self.notifier.send_message(card)

    async def run_single_cycle(self, max_tokens: Optional[int] = None):
        """Executa um ciclo único de varredura."""
        tokens = await self.fetch_filtered_token_list()
        if not tokens:
            return
        target = tokens[:max_tokens] if max_tokens else tokens
        for i, t in enumerate(target, 1):
            await self.process_token(t)
            if i < len(target):
                await asyncio.sleep(2 if max_tokens else settings.sleep_between_tokens)
        await self.notifier.send_market_summary(tokens, top_count=settings.top_gainers_count)

    async def run_forever(self):
        """Loop contínuo 24/7."""
        while True:
            t0 = datetime.now(timezone.utc)
            try:
                await self.run_single_cycle()
            except Exception as e:
                logger.error(f"Erro no ciclo: {e}")
            elapsed = (datetime.now(timezone.utc) - t0).total_seconds()
            await asyncio.sleep(max(0, settings.collection_interval_seconds - elapsed))
