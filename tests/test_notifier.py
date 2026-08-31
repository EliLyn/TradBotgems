"""
Testes unitários para o serviço de notificação do Telegram.
"""

import unittest
from tradbot.services.notifier import TelegramNotifier
from tradbot.models import (
    TokenFullDetails,
    DerivativesMetrics,
    AnalysisResult,
    TokenMarketSummary
)


class TestNotifier(unittest.TestCase):
    def setUp(self):
        self.notifier = TelegramNotifier(bot_token="test_token", chat_id="123456")

    def test_build_token_card_structure(self):
        details = TokenFullDetails(
            id="gem-token",
            symbol="GEM",
            name="Gem Token",
            market_cap_usd=50_000,
            current_price_usd=0.05,
            total_supply=1_000_000,
            circulating_supply=800_000,
            description="Um token de teste promissor",
            categories="Artificial Intelligence, Gaming",
            blockchain_id="ethereum",
            contract_address="0x1234567890abcdef1234567890abcdef12345678",
            homepage="https://gemtoken.io",
            twitter_handle="gemtoken",
            twitter_followers=5000
        )
        derivatives = DerivativesMetrics(
            open_interest=100_000,
            funding_rate=0.015,
            long_short_ratio=1.45,
            liquidation_long_24h_usd=2000,
            liquidation_short_24h_usd=1000,
            futures_volume_24h_usd=500_000
        )
        analysis = AnalysisResult(
            token_id="gem-token",
            symbol="GEM",
            potential_note="Potencial Alto (100k - 1M), 🤖 IA",
            alerts=["🔥 *GEM* - _Alta Atividade Recente!_"],
            tx_count_12h=150,
            tx_count_24h=250
        )

        card = self.notifier.build_token_card(
            details=details,
            derivatives=derivatives,
            analysis=analysis,
            price_change_24h=12.5,
            price_change_7d=35.0,
            total_volume_24h=45_000
        )

        self.assertIn("GEM", card)
        self.assertIn("Gem Token", card)
        self.assertIn("Open Interest", card)
        self.assertIn("ALERTAS", card)
        self.assertIn("Twitter", card)
        self.assertLessEqual(len(card), 4096)


if __name__ == "__main__":
    unittest.main()
