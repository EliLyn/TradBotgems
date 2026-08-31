"""
Serviço de Notificação via Telegram com formatação MarkdownV2 e divisão de mensagens.
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import List, Optional
import aiohttp

from ..config import settings
from ..models import TokenFullDetails, DerivativesMetrics, AnalysisResult, TokenMarketSummary, DexPairInfo
from ..utils.formatting import escape_markdown_v2, number_to_words_pt

logger = logging.getLogger("tradbot.notifier")


class TelegramNotifier:
    def __init__(self, bot_token: Optional[str] = None, chat_id: Optional[str] = None):
        self.bot_token = bot_token or settings.telegram.bot_token
        self.chat_id = chat_id or settings.telegram.chat_id

    async def send_message(self, message: str) -> bool:
        """Envia mensagem assíncrona para o Telegram com tratamento seguro de erros."""
        if not self.bot_token or not self.chat_id:
            logger.warning("Telegram Bot Token ou Chat ID não configurados. Notificação não enviada.")
            return False

        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": message,
            "parse_mode": "MarkdownV2",
            "disable_web_page_preview": True
        }

        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    if resp.status == 400:
                        error_data = await resp.json()
                        logger.error(f"Erro 400 ao enviar mensagem Telegram: {error_data}. Mensagem: {message[:100]}...")
                        return False

                    resp.raise_for_status()
                    data = await resp.json()
                    if data.get("ok"):
                        logger.info("Mensagem enviada para o Telegram com sucesso.")
                        return True
                    else:
                        logger.error(f"Telegram API retornou erro: {data.get('description')}")
                        return False
            except Exception as e:
                logger.error(f"Falha ao conectar com a API do Telegram: {e}")
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
        """Monta o card completo de análise de um token formatado em MarkdownV2."""
        now_str = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')

        total_supply_str = (
            f"{details.total_supply:,.0f} ({number_to_words_pt(details.total_supply)})"
            if details.total_supply is not None else "N/A"
        )
        circulating_supply_str = (
            f"{details.circulating_supply:,.0f} ({number_to_words_pt(details.circulating_supply)})"
            if details.circulating_supply is not None else "N/A"
        )

        desc = details.description
        if desc != "N/A" and len(desc) > 400:
            desc = desc[:400] + "..."

        blockchain_display = details.blockchain_id.replace('-', ' ').title() if details.blockchain_id else "N/A"

        # Derivativos (CoinGlass)
        if derivatives.has_data:
            oi_val = f"${derivatives.open_interest:,.0f}" if derivatives.open_interest is not None else "N/A"
            fr_val = f"{derivatives.funding_rate:.4f}%" if derivatives.funding_rate is not None else "N/A"
            ls_val = f"{derivatives.long_short_ratio:.2f}" if derivatives.long_short_ratio is not None else "N/A"
            liq_long_val = f"${derivatives.liquidation_long_24h_usd:,.0f}" if derivatives.liquidation_long_24h_usd is not None else "N/A"
            liq_short_val = f"${derivatives.liquidation_short_24h_usd:,.0f}" if derivatives.liquidation_short_24h_usd is not None else "N/A"
            vol_fut_val = f"${derivatives.futures_volume_24h_usd:,.0f}" if derivatives.futures_volume_24h_usd is not None else "N/A"

            derivatives_text = (
                f"\n\\*Dados de Derivativos \\(CoinGlass\\)\\*:\n"
                f"📊 \\*Open Interest\\*: {escape_markdown_v2(oi_val)}\n"
                f"📈 \\*Funding Rate\\*: {escape_markdown_v2(fr_val)}\n"
                f"🔄 \\*Long/Short Ratio\\*: {escape_markdown_v2(ls_val)}\n"
                f"🔻 \\*Liquidação Long \\(24h\\)\\*: {escape_markdown_v2(liq_long_val)}\n"
                f"🔺 \\*Liquidação Short \\(24h\\)\\*: {escape_markdown_v2(liq_short_val)}\n"
                f"💰 \\*Volume Futuros \\(24h\\)\\*: {escape_markdown_v2(vol_fut_val)}\n"
            )
        else:
            derivatives_text = "\n\\*Dados de Derivativos \\(CoinGlass\\)\\*: N/A \\(Sem atividade relevante\\)\n"

        # Redes Sociais
        twitter_followers = f"\\(Seguidores: {details.twitter_followers:,}\\)" if details.twitter_followers else ""
        telegram_members = f"\\(Membros: {details.telegram_channel_user_count:,}\\)" if details.telegram_channel_user_count else ""

        site_link = f"[Link para o Site]({details.homepage})" if details.homepage != "N/A" else "N/A"
        twitter_link = f"@{escape_markdown_v2(details.twitter_handle)} {twitter_followers}" if details.twitter_handle != "N/A" else "N/A"
        telegram_link = f"[Link para o Canal](https://t.me/{details.telegram_url}) {telegram_members}" if details.telegram_url != "N/A" else "N/A"
        discord_link = f"[Link para o Discord]({details.discord_link})" if details.discord_link != "N/A" else "N/A"
        reddit_link = f"[Link para o Subreddit]({details.subreddit_url})" if details.subreddit_url != "N/A" else "N/A"

        # Alertas Extras
        alerts_text = ""
        if analysis.alerts:
            alerts_text = "\n\\*ALERTAS\\*:\n" + "\n".join(escape_markdown_v2(a) for a in analysis.alerts) + "\n"

        price_24h_str = f"{price_change_24h:.2f}%" if price_change_24h is not None else "N/A"
        price_7d_str = f"{price_change_7d:.2f}%" if price_change_7d is not None else "N/A"
        vol_spot_str = f"${total_volume_24h:,.2f}" if total_volume_24h is not None else "N/A"
        market_cap_str = f"{details.market_cap_usd:,.2f}" if details.market_cap_usd is not None else "N/A"
        price_str = f"{details.current_price_usd:,.4f}" if details.current_price_usd is not None else "N/A"

        card = (
            f"💎 *{escape_markdown_v2(details.symbol)}* \\- {escape_markdown_v2(details.name)}\n"
            f"🗓️ {escape_markdown_v2(now_str)}\n"
            f"📊 \\*Capitalização de Mercado\\*: \\${escape_markdown_v2(market_cap_str)}\n"
            f"💲 \\*Preço\\*: \\${escape_markdown_v2(price_str)}\n"
            f"⬆️ \\*Var\\. 24h\\*: {escape_markdown_v2(price_24h_str)}\n"
            f"⬆️ \\*Var\\. 7d\\*: {escape_markdown_v2(price_7d_str)}\n"
            f"💰 \\*Volume 24h \\(Spot\\)\\*: {escape_markdown_v2(vol_spot_str)}\n"
            f"📈 \\*Transações \\(12h\\)\\*: {escape_markdown_v2(str(analysis.tx_count_12h))}\n"
            f"📉 \\*Transações \\(24h\\)\\*: {escape_markdown_v2(str(analysis.tx_count_24h))}\n"
            f"📝 \\*Potencial\\*: _{escape_markdown_v2(analysis.potential_note)}_\n"
            f"📦 \\*Fornecimento Total\\*: {escape_markdown_v2(total_supply_str)}\n"
            f"📦 \\*Fornecimento em Circulação\\*: {escape_markdown_v2(circulating_supply_str)}\n"
            f"🏷️ \\*Categoria\\*: {escape_markdown_v2(details.categories)}\n"
            f"⛓️ \\*Blockchain\\*: {escape_markdown_v2(blockchain_display)}\n"
            f"📄 \\*Contrato\\*: `{escape_markdown_v2(details.contract_address or 'N/A')}`\n"
            f"{derivatives_text}\n"
            f"\\*Sobre o Token\\*:\n{escape_markdown_v2(desc)}\n\n"
            f"\\*Redes Sociais\\*:\n"
            f"🌐 Site: {site_link}\n"
            f"🐦 Twitter: {twitter_link}\n"
            f"✈️ Telegram: {telegram_link}\n"
            f"💬 Discord: {discord_link}\n"
            f"👽 Reddit: {reddit_link}\n"
            f"{alerts_text}"
        )

        if len(card) > 4000:
            card = card[:3990] + "\n\\.\\.\\. \\(conteúdo truncado\\)"

        return card

    async def send_market_summary(self, tokens: List[TokenMarketSummary], top_count: int = 5) -> bool:
        """Envia o resumo de mercado com top gainers e moedas de alto volume."""
        valid_tokens = [
            t for t in tokens
            if t.price_change_percentage_24h is not None and
               t.price_change_percentage_7d is not None and
               t.total_volume is not None
        ]

        if not valid_tokens:
            return False

        top_24h = sorted(valid_tokens, key=lambda x: x.price_change_percentage_24h or 0, reverse=True)[:top_count]
        top_7d = sorted(valid_tokens, key=lambda x: x.price_change_percentage_7d or 0, reverse=True)[:top_count]
        high_vol = sorted([t for t in valid_tokens if (t.total_volume or 0) >= settings.high_volume_threshold_usd],
                          key=lambda x: x.total_volume or 0, reverse=True)[:top_count]

        now_str = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
        parts = [
            f"🏆 \\*Resumo Diário de Mercado\\* 🏆\n"
            f"🗓️ {escape_markdown_v2(now_str)}\n"
        ]

        if top_24h:
            parts.append("📈 \\*Maiores Valorizações \\(Últimas 24h\\)\\*:")
            for t in top_24h:
                parts.append(f"\\- {escape_markdown_v2(t.symbol)}: {escape_markdown_v2(f'{t.price_change_percentage_24h:.2f}%')}")
            parts.append("")

        if top_7d:
            parts.append("🚀 \\*Maiores Valorizações \\(Últimos 7d\\)\\*:")
            for t in top_7d:
                parts.append(f"\\- {escape_markdown_v2(t.symbol)}: {escape_markdown_v2(f'{t.price_change_percentage_7d:.2f}%')}")
            parts.append("")

        if high_vol:
            parts.append("💰 \\*Tokens com Alto Volume \\(Últimas 24h\\)\\*:")
            for t in high_vol:
                parts.append(f"\\- {escape_markdown_v2(t.symbol)}: \\${escape_markdown_v2(f'{t.total_volume:,.0f}')}")

        message = "\n".join(parts)
        return await self.send_message(message)
