"""
Testes unitários para o gerenciador de cache com TTL e fallback.
"""

import unittest
import os
import json
from datetime import datetime, timezone, timedelta
from tradbot.services.cache import CacheManager


class TestCacheManager(unittest.TestCase):
    def setUp(self):
        self.test_cache_file = "test_cache_temp.json"
        self.cache = CacheManager(cache_file=self.test_cache_file, expiry_hours=1)

    def tearDown(self):
        if os.path.exists(self.test_cache_file):
            os.remove(self.test_cache_file)

    def test_set_and_get_valid_cache(self):
        data = [{"id": "bitcoin", "symbol": "BTC"}]
        self.assertTrue(self.cache.set(data))
        cached = self.cache.get()
        self.assertIsNotNone(cached)
        self.assertEqual(len(cached), 1)
        self.assertEqual(cached[0]["id"], "bitcoin")

    def test_cache_expired(self):
        old_time = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
        payload = {
            "timestamp": old_time,
            "tokens": [{"id": "ethereum", "symbol": "ETH"}]
        }
        with open(self.test_cache_file, "w", encoding="utf-8") as f:
            json.dump(payload, f)

        # Get normal deve retornar None por expiração
        self.assertIsNone(self.cache.get(ignore_expiry=False))
        # Fallback deve recuperar os dados mesmo expirados
        fallback = self.cache.get_fallback()
        self.assertIsNotNone(fallback)
        self.assertEqual(fallback[0]["symbol"], "ETH")

    def test_empty_cache_not_overwritten(self):
        initial_data = [{"id": "solana", "symbol": "SOL"}]
        self.cache.set(initial_data)
        # Tentar salvar lista vazia
        self.assertFalse(self.cache.set([]))
        # Deve manter os dados originais
        cached = self.cache.get()
        self.assertEqual(cached[0]["id"], "solana")


if __name__ == "__main__":
    unittest.main()
