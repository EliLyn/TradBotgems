"""
Testes unitários para os modelos de dados tipados.
"""

import unittest
from tradbot.models import (
    TokenMarketSummary,
    TokenFullDetails,
    DerivativesMetrics,
    AnalysisResult,
    DexPairInfo
)


class TestModels(unittest.TestCase):
    def test_token_market_summary(self):
        summary = TokenMarketSummary(
            id="bitcoin",
            symbol="BTC",
            name="Bitcoin",
            market_cap=1_000_000_000,
            current_price=60_000.0,
            price_change_percentage_24h=2.5
        )
        self.assertEqual(summary.id, "bitcoin")
        self.assertEqual(summary.symbol, "BTC")
        self.assertEqual(summary.price_change_percentage_24h, 2.5)

    def test_derivatives_metrics_has_data(self):
        empty_metrics = DerivativesMetrics()
        self.assertFalse(empty_metrics.has_data)

        active_metrics = DerivativesMetrics(open_interest=500_000, funding_rate=0.01)
        self.assertTrue(active_metrics.has_data)

    def test_token_full_details_defaults(self):
        details = TokenFullDetails(id="test", symbol="TST", name="Test")
        self.assertEqual(details.description, "N/A")
        self.assertEqual(details.categories, "N/A")
        self.assertEqual(details.twitter_followers, 0)

    def test_dex_pair_info(self):
        pair = DexPairInfo(
            chain_id="ethereum",
            dex_id="uniswap_v3",
            pair_address="0xabc",
            base_token_symbol="PEPE",
            base_token_address="0x123",
            quote_token_symbol="WETH",
            liquidity_usd=250_000,
            volume_24h_usd=1_000_000
        )
        self.assertEqual(pair.base_token_symbol, "PEPE")
        self.assertEqual(pair.liquidity_usd, 250_000)


if __name__ == "__main__":
    unittest.main()
