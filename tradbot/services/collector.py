"""
Orquestrador do Ciclo 24/7 de Caça a Gems e Análise de Mercado.
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import List, Optional
import aiohttp

from ..config import settings
from ..models import TokenMarketSummary, TokenFullDetails
from ..clients.coingecko import CoinGeckoClient
from ..clients.coinglass import CoinGlassClient
from .analyzer import TokenAnalyzer
from .notifier import TelegramNotifier
from .cache import CacheManager

logger = logging.getLogger("tradbot.collector")


class GemCollectorService:
    def __init__(
        self,
        coingecko_client: Optional[CoinGeckoClient] = None,
        coinglass_client: Optional[CoinGlassClient] = None,
        analyzer: Optional[TokenAnalyzer] = None,
        notifier: Optional[TelegramNotifier] = None,
        cache_manager: Optional[CacheManager] = None
    ):
        self.coingecko = coingecko_client or CoinGeckoClient()
        self.coinglass = coinglass_client or CoinGlassClient()
        self.analyzer = analyzer or TokenAnalyzer()
        self.notifier = notifier or TelegramNotifier()
        self.cache = cache_manager or CacheManager(
            cache_file=settings.coingecko.cache_file,
            expiry_hours=settings.coingecko.cache_expiry_hours
        )

    async def close(self):
        """Fecha sessões HTTP abertas."""
        await self.coingecko.close()
        await self.coinglass.close()

    async def fetch_filtered_token_list(self) -> List[TokenMarketSummary]:
        """Busca lista de tokens dentro da faixa de Market Cap desejada com suporte a cache e fallback."""
        cached_data = self.cache.get()
        if cached_data:
            return [TokenMarketSummary(**item) for item in cached_data if isinstance(item, dict)]

        logger.info("Buscando lista dinâmica de tokens da CoinGecko...")
        filtered_tokens: List[TokenMarketSummary] = []
        per_page = settings.coingecko.per_page
        total_pages = settings.coingecko.total_pages_to_check

        # Varredura reversa de páginas para encontrar micro e small caps
        for page in range(total_pages, 0, -1):
            logger.info(f"Consultando página {page}/{total_pages}...")
            data = await self.coingecko.get_markets_page(page=page, per_page=per_page)

            if not data:
                logger.warning(f"Sem dados retornados na página {page}. Encerrando busca de páginas.")
                break

            highest_mcap_in_page = data[0].get("market_cap") or 0

            for t in data:
                mcap = t.get("market_cap")
                tid = t.get("id")
                if tid and mcap is not None:
                    if settings.min_market_cap_usd <= mcap <= settings.max_market_cap_usd:
                        filtered_tokens.append(
                            TokenMarketSummary(
                                id=tid,
                                symbol=t.get("symbol", "").upper(),
                                name=t.get("name", ""),
                                market_cap=mcap,
                                current_price=t.get("current_price") or 0.0,
                                price_change_percentage_24h=t.get("price_change_percentage_24h_in_currency"),
                                price_change_percentage_7d=t.get("price_change_percentage_7d_in_currency"),
                                total_volume=t.get("total_volume")
                            )
                        )

            if highest_mcap_in_page > settings.max_market_cap_usd:
                logger.info(f"Market Cap ({highest_mcap_in_page:,.0f}) excedeu o teto de filtro. Finalizando varredura.")
                break

            await asyncio.sleep(settings.sleep_between_pages)

        if filtered_tokens:
            filtered_tokens.sort(key=lambda x: x.market_cap)
            logger.info(f"Total de {len(filtered_tokens)} tokens qualificados encontrados.")
            self.cache.set([t.__dict__ for t in filtered_tokens])
            return filtered_tokens

        # Fallback para cache local existente se a rede/DNS estiver indisponível
        fallback_data = self.cache.get_fallback()
        if fallback_data:
            logger.info(f"⚠️ Usando dados em cache local como fallback ({len(fallback_data)} tokens carregados).")
            tokens_list = []
            for item in fallback_data:
                if isinstance(item, dict):
                    # Normalizar chaves caso venham do cache antigo
                    tokens_list.append(
                        TokenMarketSummary(
                            id=item.get("id", ""),
                            symbol=item.get("symbol", "").upper(),
                            name=item.get("name", ""),
                            market_cap=item.get("market_cap") or 0.0,
                            current_price=item.get("current_price") or 0.0,
                            price_change_percentage_24h=item.get("price_change_percentage_24h"),
                            price_change_percentage_7d=item.get("price_change_percentage_7d"),
                            total_volume=item.get("total_volume")
                        )
                    )
            return tokens_list

        return []

    async def process_token(self, token_summary: TokenMarketSummary) -> bool:
        """Processa um token individual: busca detalhes, derivativos, analisa e notifica."""
        logger.info(f"Analisando token: {token_summary.name} ({token_summary.symbol})...")

        details = await self.coingecko.get_token_details(token_summary.id)
        if not details:
            # Fallback construído a partir do resumo se rede falhar
            logger.warning(f"Rede indisponível para detalhes de {token_summary.id}. Usando dados de resumo.")
            details = TokenFullDetails(
                id=token_summary.id,
                symbol=token_summary.symbol,
                name=token_summary.name,
                market_cap_usd=token_summary.market_cap,
                current_price_usd=token_summary.current_price,
                categories="Gems / Micro-Cap",
                description=f"Token {token_summary.name} ({token_summary.symbol})"
            )

        # Derivativos na CoinGlass
        derivatives = await self.coinglass.get_derivatives_data(token_summary.symbol)

        # Análise
        analysis = self.analyzer.analyze_token(
            token_id=token_summary.id,
            symbol=token_summary.symbol,
            details=details
        )

        # Montar card e enviar no Telegram
        card_message = self.notifier.build_token_card(
            details=details,
            derivatives=derivatives,
            analysis=analysis,
            price_change_24h=token_summary.price_change_percentage_24h,
            price_change_7d=token_summary.price_change_percentage_7d,
            total_volume_24h=token_summary.total_volume
        )

        await self.notifier.send_message(card_message)
        return True

    async def run_single_cycle(self, max_tokens: Optional[int] = None):
        """Executa um ciclo completo de coleta, análise e relatório diário."""
        start_time = datetime.now(timezone.utc)
        logger.info(f"=== Iniciando Ciclo de Coleta: {start_time.strftime('%Y-%m-%d %H:%M:%S UTC')} ===")

        try:
            tokens = await self.fetch_filtered_token_list()
            if not tokens:
                logger.warning("Nenhum token encontrado neste ciclo.")
                return

            target_tokens = tokens[:max_tokens] if max_tokens else tokens

            for i, token in enumerate(target_tokens, 1):
                logger.info(f"[{i}/{len(target_tokens)}] Processando {token.symbol}...")
                await self.process_token(token)
                if i < len(target_tokens):
                    await asyncio.sleep(2 if max_tokens else settings.sleep_between_tokens)

            # Envia resumo diário dos top performers
            await self.notifier.send_market_summary(tokens, top_count=settings.top_gainers_count)

            duration = (datetime.now(timezone.utc) - start_time).total_seconds()
            logger.info(f"=== Ciclo finalizado em {duration:.2f}s ===")
        finally:
            await self.close()

    async def run_forever(self):
        """Loop principal 24/7 com controle de intervalo e tratamento resiliente de falhas."""
        logger.info("Iniciando TradBotGems em modo contínuo 24/7...")

        try:
            while True:
                cycle_start = datetime.now(timezone.utc)
                try:
                    await self.run_single_cycle()
                except Exception as e:
                    logger.error(f"Erro durante o ciclo de coleta: {e}", exc_info=True)

                elapsed = (datetime.now(timezone.utc) - cycle_start).total_seconds()
                sleep_time = max(0, settings.collection_interval_seconds - elapsed)

                if sleep_time > 0:
                    logger.info(f"Aguardando {sleep_time:.1f}s para o próximo ciclo...")
                    await asyncio.sleep(sleep_time)
                else:
                    logger.warning("O ciclo durou mais que o intervalo configurado. Reiniciando imediatamente.")
        finally:
            await self.close()
