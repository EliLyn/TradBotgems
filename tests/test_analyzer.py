"""
Testes unitários para o motor de análise.
"""

import unittest
from tradbot.services.analyzer import TokenAnalyzer
from tradbot.models import TokenFullDetails


class TestAnalyzer(unittest.TestCase):
    def setUp(self):
        self.analyzer = TokenAnalyzer()

    def test_potential_note_micro_cap(self):
        note = self.analyzer.calculate_potential_note(
            market_cap=35000,
            tx_12h=30,
            tx_24h=60,
            categories_str="Real World Assets, Gaming",
            total_supply=100_000_000
        )
        self.assertIn("Recém-Descoberto", note)
        self.assertIn("RWA/Game", note)

    def test_potential_note_ai_and_btc(self):
        note = self.analyzer.calculate_potential_note(
            market_cap=500_000,
            tx_12h=100,
            tx_24h=200,
            categories_str="Artificial Intelligence, Bitcoin Ecosystem",
            total_supply=500_000_000
        )
        self.assertIn("Potencial Alto", note)
        self.assertIn("🤖 IA", note)
        self.assertIn("₿ Baseado em BTC", note)

    def test_analyze_token_generation(self):
        details = TokenFullDetails(
            id="test-token",
            symbol="TEST",
            name="Test Token",
            market_cap_usd=45000,
            current_price_usd=0.045,
            total_supply=1_000_000,
            categories="gaming"
        )
        result = self.analyzer.analyze_token("test-token", "TEST", details, tx_12h=120, tx_24h=200)
        self.assertEqual(result.symbol, "TEST")
        self.assertTrue(len(result.alerts) > 0)


if __name__ == "__main__":
    unittest.main()
