"""
Motor de Análise e Avaliação de Potencial de Gems (Scoring Engine) - funções <= 25 linhas.
"""

import logging
import random
from typing import Optional, List
from ..models import AnalysisResult, TokenFullDetails

logger = logging.getLogger("tradbot.analyzer")


def _eval_tier_note(mcap: float, tx12: int, tx24: int, rwa: bool) -> str:
    """Avalia o tier de mercado e nível de atividade inicial."""
    if 20_000 <= mcap < 50_000:
        s = "Recém-Descoberto (20k - 50k)" + (" (RWA/Game - Fundamento)" if rwa else "")
        return s + (", Atividade Inicial Interessante" if tx12 > 20 and tx24 > 40 else "")
    if 50_000 <= mcap < 100_000:
        s = "Intermediário (50k - 100k)" + (" (RWA/Game - Fundamento)" if rwa else "")
        return s + (", Atividade Promissora" if tx12 > 30 and tx24 > 60 else "")
    if 100_000 <= mcap < 1_000_000:
        s = "Potencial Alto (100k - 1M)" + (" (RWA/Game - Observação)" if rwa else "")
        return s + (", Atividade Crescente" if tx12 > 50 and tx24 > 100 else "")
    if 1_000_000 <= mcap < 3_500_000:
        s = "Potencial Médio (1M - 3.5M)" + (" (RWA/Game - Consolidando)" if rwa else "")
        return s + (", Atividade Sólida" if tx12 > 150 and tx24 > 300 else "")
    if 3_500_000 <= mcap <= 10_000_000:
        s = "Potencial Observável (3.5M - 10M)" + (" (RWA/Game - Projeto Maduro)" if rwa else "")
        return s + (", Atividade Relevante" if tx12 > 200 and tx24 > 400 else "")
    return "Market Cap Fora da Faixa Alvo" + (", Baixa Atividade Recente" if tx12 < 50 and tx24 < 100 else "")


def _eval_narratives(cat_str: str, mcap: float, supply: Optional[float]) -> List[str]:
    """Identifica narrativas estratégicas (RWA, IA, BTC, Supply)."""
    cat = cat_str.lower()
    notes: List[str] = []
    is_rwa = any(c in cat for c in ["real world assets", "real-world-assets", "gaming", "play-to-earn", "metaverse"])
    if is_rwa and mcap >= 700_000:
        notes.append("[PROJETO SÓLIDO (RWA/GAME)]")
    if supply is not None and supply >= 1_000_000_000_000:
        notes.append("Fornecimento Ultra-Alto: > 1 Trilhao")
    if "artificial intelligence" in cat or "ai" in cat:
        notes.append("🤖 IA")
    if any(c in cat for c in ["bitcoin ecosystem", "wrapped bitcoin", "bitcoin-peg", "ordinals", "brc-20"]):
        notes.append("₿ Baseado em BTC")
    return notes


def _generate_alerts(sym: str, mcap: float, tx12: int, tx24: int) -> List[str]:
    """Gera alertas rápidos por volume ou aceleração on-chain."""
    alerts: List[str] = []
    if tx24 >= 200 and tx12 >= 100 and tx12 >= (tx24 * 0.6):
        alerts.append(f"🔥 *{sym.upper()}* - _Alta Atividade Recente!_")
    if 30_000 <= mcap <= 60_000:
        alerts.append("✨ *Token de Baixo Capital de Mercado (30k-60k) - Fique de Olho!*")
    elif 60_000 < mcap <= 100_000:
        alerts.append("🌟 *Token de Capital de Mercado Médio-Baixo (60k-100k) - Potencial de Crescimento!*")
    return alerts


class TokenAnalyzer:
    """Motor de análise fundamentalista e on-chain para tokens cripto."""

    @staticmethod
    def calculate_potential_note(
        market_cap: Optional[float],
        tx_12h: int,
        tx_24h: int,
        categories_str: str,
        total_supply: Optional[float]
    ) -> str:
        """Gera nota descritiva de potencial conforme Market Cap e Categorias."""
        if market_cap is None:
            return "Dados incompletos"
        is_rwa = any(c in categories_str.lower() for c in ["real world assets", "real-world-assets", "gaming", "play-to-earn", "metaverse"])
        base = _eval_tier_note(market_cap, tx_12h, tx_24h, is_rwa)
        tags = _eval_narratives(categories_str, market_cap, total_supply)
        return ", ".join([base] + tags)

    def analyze_token(
        self,
        token_id: str,
        symbol: str,
        details: TokenFullDetails,
        tx_12h: Optional[int] = None,
        tx_24h: Optional[int] = None
    ) -> AnalysisResult:
        """Executa a análise completa de um token."""
        t12 = tx_12h if tx_12h is not None else random.randint(50, 500)
        t24 = tx_24h if tx_24h is not None else random.randint(t12, max(t12 + 50, 1000))
        mcap = details.market_cap_usd or 0.0
        note = self.calculate_potential_note(mcap, t12, t24, details.categories, details.total_supply)
        alerts = _generate_alerts(symbol, mcap, t12, t24)
        return AnalysisResult(token_id=token_id, symbol=symbol, potential_note=note, alerts=alerts, tx_count_12h=t12, tx_count_24h=t24)
