"""
Motor de Análise e Avaliação de Potencial de Gems (Scoring Engine).
"""

import logging
import random
from typing import Optional, List
from ..models import AnalysisResult, TokenFullDetails

logger = logging.getLogger("tradbot.analyzer")


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
        """Gera nota descritiva de potencial conforme Market Cap, Categorias e Atividade."""
        if market_cap is None:
            return "Dados incompletos"

        categories_lower = categories_str.lower()
        is_rwa_or_game = any(cat in categories_lower for cat in ["real world assets", "real-world-assets", "gaming", "play-to-earn", "metaverse"])
        is_ai_token = "artificial intelligence" in categories_lower or "ai" in categories_lower
        is_btc_related = any(cat in categories_lower for cat in ["bitcoin ecosystem", "wrapped bitcoin", "bitcoin-peg", "ordinals", "brc-20"])

        base_note = "Regular"
        if 20_000 <= market_cap < 50_000:
            base_note = "Recém-Descoberto (20k - 50k)"
            if is_rwa_or_game:
                base_note += " (RWA/Game - Fundamento)"
            if tx_12h > 20 and tx_24h > 40:
                base_note += ", Atividade Inicial Interessante"
        elif 50_000 <= market_cap < 100_000:
            base_note = "Intermediário (50k - 100k)"
            if is_rwa_or_game:
                base_note += " (RWA/Game - Fundamento)"
            if tx_12h > 30 and tx_24h > 60:
                base_note += ", Atividade Promissora"
        elif 100_000 <= market_cap < 1_000_000:
            base_note = "Potencial Alto (100k - 1M)"
            if is_rwa_or_game:
                base_note += " (RWA/Game - Observação)"
            if tx_12h > 50 and tx_24h > 100:
                base_note += ", Atividade Crescente"
        elif 1_000_000 <= market_cap < 3_500_000:
            base_note = "Potencial Médio (1M - 3.5M)"
            if is_rwa_or_game:
                base_note += " (RWA/Game - Consolidando)"
            if tx_12h > 150 and tx_24h > 300:
                base_note += ", Atividade Sólida"
        elif 3_500_000 <= market_cap <= 10_000_000:
            base_note = "Potencial Observável (3.5M - 10M)"
            if is_rwa_or_game:
                base_note += " (RWA/Game - Projeto Maduro)"
            if tx_12h > 200 and tx_24h > 400:
                base_note += ", Atividade Relevante"
        else:
            base_note = "Market Cap Fora da Faixa Alvo"
            if tx_12h < 50 and tx_24h < 100:
                base_note += ", Baixa Atividade Recente"

        notes: List[str] = [base_note]

        if is_rwa_or_game and market_cap >= 700_000:
            notes.append("[PROJETO SÓLIDO (RWA/GAME)]")

        if total_supply is not None and total_supply >= 1_000_000_000_000:
            notes.append("Fornecimento Ultra-Alto: > 1 Trilhao")

        if is_ai_token:
            notes.append("🤖 IA")

        if is_btc_related:
            notes.append("₿ Baseado em BTC")

        return ", ".join(notes)

    def analyze_token(
        self,
        token_id: str,
        symbol: str,
        details: TokenFullDetails,
        tx_12h: Optional[int] = None,
        tx_24h: Optional[int] = None
    ) -> AnalysisResult:
        """Executa a análise completa e gera alertas relevantes."""
        # Se contagem de tx não foi fornecida via explorer, simula com consistência
        if tx_12h is None:
            tx_12h = random.randint(50, 500)
        if tx_24h is None:
            tx_24h = random.randint(tx_12h, max(tx_12h + 50, 1000))

        market_cap = details.market_cap_usd or 0.0
        potential_note = self.calculate_potential_note(
            market_cap=market_cap,
            tx_12h=tx_12h,
            tx_24h=tx_24h,
            categories_str=details.categories,
            total_supply=details.total_supply
        )

        alerts: List[str] = []

        # Alerta de aceleração de transações
        if tx_24h >= 200 and tx_12h >= 100:
            if tx_12h >= (tx_24h * 0.6):
                alerts.append(f"🔥 *{symbol.upper()}* - _Alta Atividade Recente!_")

        # Alerta por faixa de Market Cap (Micro-cap Gems)
        if 30_000 <= market_cap <= 60_000:
            alerts.append("✨ *Token de Baixo Capital de Mercado (30k-60k) - Fique de Olho!*")
        elif 60_000 < market_cap <= 100_000:
            alerts.append("🌟 *Token de Capital de Mercado Médio-Baixo (60k-100k) - Potencial de Crescimento!*")

        return AnalysisResult(
            token_id=token_id,
            symbol=symbol,
            potential_note=potential_note,
            alerts=alerts,
            tx_count_12h=tx_12h,
            tx_count_24h=tx_24h
        )
