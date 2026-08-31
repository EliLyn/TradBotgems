"""
Serviço de Monitoramento de Novos Pares em DEX (funções <= 25 linhas).
"""

import asyncio
import logging
from typing import Optional
from ..clients.dexscreener import DexScreenerClient
from ..clients.honeypot import HoneypotClient
from ..models import DexPairInfo
from .notifier import TelegramNotifier
from ..utils.formatting import escape_markdown_v2

logger = logging.getLogger("tradbot.dex_monitor")


def _format_dex_alert(chain: str, p: DexPairInfo, is_hp: Optional[bool]) -> str:
    """Formata o alerta de novo par DEX."""
    hp_text = "🚨 RISCO DE HONEYPOT" if is_hp else "✅ Seguro / Não Detectado"
    liq = p.liquidity_usd or 0.0
    vol = p.volume_24h_usd or 0.0
    return (
        f"🦄 \\*Novo Par de Alto Volume na DEX\\* 🦄\n"
        f"⛓️ \\*Chain\\*: {escape_markdown_v2(chain.title())}\n"
        f"🪙 \\*Par\\*: {escape_markdown_v2(p.base_token_symbol)} / {escape_markdown_v2(p.quote_token_symbol)}\n"
        f"💧 \\*Liquidez\\*: \\${escape_markdown_v2(f'{liq:,.2f}')}\n"
        f"💰 \\*Volume 24h\\*: \\${escape_markdown_v2(f'{vol:,.2f}')}\n"
        f"📈 \\*Transações \\(1h\\)\\*: {p.txns_60m}\n"
        f"🛡️ \\*Honeypot Check\\*: {escape_markdown_v2(hp_text)}\n"
        f"📄 \\*Contrato\\*: `{escape_markdown_v2(p.base_token_address)}`"
    )


class DexMonitorService:
    POPULAR_TOKENS = {
        "ethereum": "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2", "bsc": "0xbb4CdB9eD5BBadB3c5d6fF08cD540cD7ee5Ab3eB",
        "polygon": "0x0d500B1d8E8eF31E21C99d1Db9A6444d3ADf1270", "arbitrum": "0x82aF49447D8a07e3bd95bD0d56f35241523fBab1",
        "base": "0x4200000000000000000000000000000000000006", "avalanche": "0xB31f66AA3C6E785363F0875A1B74E27b85FD66c7",
    }

    def __init__(self, dex: Optional[DexScreenerClient] = None, hp: Optional[HoneypotClient] = None, notif: Optional[TelegramNotifier] = None, min_liq: float = 50000.0, min_vol: float = 50000.0):
        self.dex = dex or DexScreenerClient()
        self.honeypot = hp or HoneypotClient()
        self.notifier = notif or TelegramNotifier()
        self.min_liquidity = min_liq
        self.min_volume = min_vol
        self.seen_pairs = set()

    async def scan_chain_pairs(self, chain_name: str, token_address: str):
        """Varre pares de uma chain específica."""
        pairs = await self.dex.get_pairs_by_token(token_address)
        for p in pairs:
            if p.pair_address not in self.seen_pairs and (p.liquidity_usd or 0) >= self.min_liquidity and (p.volume_24h_usd or 0) >= self.min_volume:
                self.seen_pairs.add(p.pair_address)
                is_hp = await self.honeypot.check_token(p.base_token_address, chain_id=chain_name)
                msg = _format_dex_alert(chain_name, p, is_hp)
                await self.notifier.send_message(msg)

    async def run_forever(self, interval_seconds: int = 60):
        """Executa o monitor contínuo de DEX."""
        while True:
            for chain, addr in self.POPULAR_TOKENS.items():
                await self.scan_chain_pairs(chain, addr)
                await asyncio.sleep(1)
            await asyncio.sleep(interval_seconds)
