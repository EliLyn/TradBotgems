"""
Serviço de Notificação via Telegram com formatação MarkdownV2 e funções enxutas (<= 25 linhas).
"""

import asyncio
import logging
import socket
from datetime import datetime, timezone
from typing import List, Optional
import aiohttp

from ..config import settings
from ..models import TokenFullDetails, DerivativesMetrics, AnalysisResult, TokenMarketSummary
from ..utils.formatting import escape_markdown_v2, number_to_words_pt

logger = logging.getLogger("tradbot.notifier")


def _format_derivatives_block(d: DerivativesMetrics) -> str:
    """Formata bloco de derivativos da CoinGlass."""
    if not d.has_data:
        return "\n\\*Dados de Derivativos \\(CoinGlass\\)\\*: N/A \\(Sem atividade relevante\\)\n"
    oi = escape_markdown_v2(f"${d.open_interest:,.0f}" if d.open_interest is not None else "N/A")
    fr = escape_markdown_v2(f"{d.funding_rate:.4f}%" if d.funding_rate is not None else "N/A")
    ls = escape_markdown_v2(f"{d.long_short_ratio:.2f}" if d.long_short_ratio is not None else "N/A")
    liq_l = escape_markdown_v2(f"${d.liquidation_long_24h_usd:,.0f}" if d.liquidation_long_24h_usd is not None else "N/A")
    liq_s = escape_markdown_v2(f"${d.liquidation_short_24h_usd:,.0f}" if d.liquidation_short_24h_usd is not None else "N/A")
    vol = escape_markdown_v2(f"${d.futures_volume_24h_usd:,.0f}" if d.futures_volume_24h_usd is not None else "N/A")
    return (
        f"\n\\*Dados de Derivativos \\(CoinGlass\\)\\*:\n"
        f"📊 \\*Open Interest\\*: {oi}\n📈 \\*Funding Rate\\*: {fr}\n🔄 \\*Long/Short Ratio\\*: {ls}\n"
        f"🔻 \\*Liquidação Long \\(24h\\)\\*: {liq_l}\n🔺 \\*Liquidação Short \\(24h\\)\\*: {liq_s}\n💰 \\*Volume Futuros \\(24h\\)\\*: {vol}\n"
    )


def _format_social_links(d: TokenFullDetails) -> str:
    """Formata links de redes sociais e canais oficiais."""
    tw_f = f"\\(Seguidores: {d.twitter_followers:,}\\)" if d.twitter_followers else ""
    tg_m = f"\\(Membros: {d.telegram_channel_user_count:,}\\)" if d.telegram_channel_user_count else ""
    site = f"[Link para o Site]({d.homepage})" if d.homepage != "N/A" else "N/A"
    tw = f"@{escape_markdown_v2(d.twitter_handle)} {tw_f}" if d.twitter_handle != "N/A" else "N/A"
    tg = f"[Link para o Canal](https://t.me/{d.telegram_url}) {tg_m}" if d.telegram_url != "N/A" else "N/A"
    disc = f"[Link para o Discord]({d.discord_link})" if d.discord_link != "N/A" else "N/A"
    red = f"[Link para o Subreddit]({d.subreddit_url})" if d.subreddit_url != "N/A" else "N/A"
    return (
        f"\n\\*Redes Sociais\\*:\n"
        f"🌐 Site: {site}\n🐦 Twitter: {tw}\n✈️ Telegram: {tg}\n💬 Discord: {disc}\n👽 Reddit: {red}\n"
    )


def _format_market_header(d: TokenFullDetails, a: AnalysisResult, p24: Optional[float], p7d: Optional[float], vol: Optional[float]) -> str:
    """Formata cabeçalho e estatísticas de preço de um token."""
    now_str = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
    p24_s = escape_markdown_v2(f"{p24:.2f}%" if p24 is not None else "N/A")
    p7d_s = escape_markdown_v2(f"{p7d:.2f}%" if p7d is not None else "N/A")
    vol_s = escape_markdown_v2(f"${vol:,.2f}" if vol is not None else "N/A")
    mcap_s = escape_markdown_v2(f"{d.market_cap_usd:,.2f}" if d.market_cap_usd is not None else "N/A")
    price_s = escape_markdown_v2(f"{d.current_price_usd:,.4f}" if d.current_price_usd is not None else "N/A")
    return (
        f"💎 *{escape_markdown_v2(d.symbol)}* \\- {escape_markdown_v2(d.name)}\n🗓️ {escape_markdown_v2(now_str)}\n"
        f"📊 \\*Capitalização de Mercado\\*: \\${mcap_s}\n💲 \\*Preço\\*: \\${price_s}\n"
        f"⬆️ \\*Var\\. 24h\\*: {p24_s}\n⬆️ \\*Var\\. 7d\\*: {p7d_s}\n💰 \\*Volume 24h \\(Spot\\)\\*: {vol_s}\n"
        f"📈 \\*Transações \\(12h\\)\\*: {escape_markdown_v2(str(a.tx_count_12h))}\n"
        f"📉 \\*Transações \\(24h\\)\\*: {escape_markdown_v2(str(a.tx_count_24h))}\n"
        f"📝 \\*Potencial\\*: _{escape_markdown_v2(a.potential_note)}_\n"
    )


def _format_token_supply_info(d: TokenFullDetails) -> str:
    """Formata informações de fornecimento, blockchain e contrato."""
    ts = f"{d.total_supply:,.0f} ({number_to_words_pt(d.total_supply)})" if d.total_supply is not None else "N/A"
    cs = f"{d.circulating_supply:,.0f} ({number_to_words_pt(d.circulating_supply)})" if d.circulating_supply is not None else "N/A"
    chain = d.blockchain_id.replace('-', ' ').title() if d.blockchain_id else "N/A"
    desc = d.description[:400] + "..." if (d.description != "N/A" and len(d.description) > 400) else d.description
    return (
        f"📦 \\*Fornecimento Total\\*: {escape_markdown_v2(ts)}\n"
        f"📦 \\*Fornecimento em Circulação\\*: {escape_markdown_v2(cs)}\n"
        f"🏷️ \\*Categoria\\*: {escape_markdown_v2(d.categories)}\n"
        f"⛓️ \\*Blockchain\\*: {escape_markdown_v2(chain)}\n"
        f"📄 \\*Contrato\\*: `{escape_markdown_v2(d.contract_address or 'N/A')}`\n"
        f"\n\\*Sobre o Token\\*:\n{escape_markdown_v2(desc)}\n"
    )


class TelegramNotifier:
    def __init__(self, bot_token: Optional[str] = None, chat_id: Optional[str] = None):
        self.bot_token = bot_token or settings.telegram.bot_token
        self.chat_id = chat_id or settings.telegram.chat_id

    async def send_message(self, message: str) -> bool:
        """Envia mensagem assíncrona para o Telegram com tratamento de erros."""
        if not self.bot_token or not self.chat_id:
            logger.warning("Telegram Bot Token ou Chat ID não configurados.")
            return False
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        payload = {"chat_id": self.chat_id, "text": message, "parse_mode": "MarkdownV2", "disable_web_page_preview": True}
        connector = aiohttp.TCPConnector(family=socket.AF_INET, resolver=aiohttp.ThreadedResolver())
        async with aiohttp.ClientSession(connector=connector) as session:
            try:
                async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    return bool(resp.status == 200)
            except Exception as e:
                logger.error(f"Falha ao conectar com Telegram: {e}")
                return False

    def build_token_card(
        self,
        details: TokenFullDetails,
        derivatives: DerivativesMetrics,
        analysis: AnalysisResult,
        price_change_24h: Optional[float] = None,
        price_change_7d: Optional[float] = None,
        total_volume_24h: Optional[float] = None
    ) -> str:
        """Monta o card completo de análise de um token."""
        header = _format_market_header(details, analysis, price_change_24h, price_change_7d, total_volume_24h)
        supply = _format_token_supply_info(details)
        derivs = _format_derivatives_block(derivatives)
        socials = _format_social_links(details)
        alerts = "\n\\*ALERTAS\\*:\n" + "\n".join(escape_markdown_v2(x) for x in analysis.alerts) + "\n" if analysis.alerts else ""
        card = header + supply + derivs + socials + alerts
        return card[:3990] + "\n\\.\\.\\. \\(truncado\\)" if len(card) > 4000 else card

    async def send_market_summary(self, tokens: List[TokenMarketSummary], top_count: int = 5) -> bool:
        """Envia o resumo diário de maiores valorizações e volume."""
        valid = [t for t in tokens if t.price_change_percentage_24h is not None and t.total_volume is not None]
        if not valid:
            return False
        top_24h = sorted(valid, key=lambda x: x.price_change_percentage_24h or 0, reverse=True)[:top_count]
        now_str = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
        lines = [f"🏆 \\*Resumo Diário de Mercado\\* 🏆\n🗓️ {escape_markdown_v2(now_str)}\n\n📈 \\*Maiores Valorizações \\(24h\\)\\*:"]
        for t in top_24h:
            lines.append(f"\\- {escape_markdown_v2(t.symbol)}: {escape_markdown_v2(f'{t.price_change_percentage_24h:.2f}%')}")
        return await self.send_message("\n".join(lines))
