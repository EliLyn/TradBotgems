"""
Testes unitários para clientes e mapeamento de exploradores.
"""

import unittest
from tradbot.clients.coingecko import CoinGeckoClient
from tradbot.clients.coinglass import CoinGlassClient
from tradbot.clients.evm_explorer import EvmExplorerClient
from tradbot.clients.honeypot import HoneypotClient
from tradbot.config import settings


class TestClients(unittest.TestCase):
    def test_coingecko_client_init(self):
        client = CoinGeckoClient()
        self.assertIn("coingecko.com", client.base_url)

    def test_coinglass_client_headers(self):
        client = CoinGlassClient(api_key="fake_key_123")
        headers = client._get_headers()
        self.assertEqual(headers["coinglassSecret"], "fake_key_123")

    def test_evm_explorer_url_mapping(self):
        client = EvmExplorerClient()
        self.assertIn("ethereum", client.url_map)
        self.assertIn("binance-smart-chain", client.url_map)
        self.assertIn("polygon-pos", client.url_map)
        self.assertIn("arbitrum-one", client.url_map)
        self.assertIn("base", client.url_map)

    def test_honeypot_client_init(self):
        client = HoneypotClient()
        self.assertEqual(client.BASE_URL, "https://api.honeypot.is/v1/IsHoneypot")


if __name__ == "__main__":
    unittest.main()
