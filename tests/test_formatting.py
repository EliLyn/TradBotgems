"""
Testes unitários para o módulo de formatação.
"""

import unittest
from tradbot.utils.formatting import escape_markdown_v2, number_to_words_pt, format_currency, format_percent


class TestFormatting(unittest.TestCase):
    def test_escape_markdown_v2(self):
        self.assertEqual(escape_markdown_v2("BTC-USDT"), r"BTC\-USDT")
        self.assertEqual(escape_markdown_v2("Hello (World)!"), r"Hello \(World\)\!")
        self.assertEqual(escape_markdown_v2("Price: $100.50"), r"Price: $100\.50")
        self.assertEqual(escape_markdown_v2(None), "")

    def test_number_to_words_pt(self):
        self.assertEqual(number_to_words_pt(0), "zero")
        self.assertEqual(number_to_words_pt(5), "cinco")
        self.assertEqual(number_to_words_pt(15), "quinze")
        self.assertEqual(number_to_words_pt(100), "cem")
        self.assertEqual(number_to_words_pt(120), "cento e vinte")
        self.assertIn("milhões", number_to_words_pt(5_000_000))
        self.assertIn("bilhões", number_to_words_pt(2_500_000_000))
        self.assertIn("trilhões", number_to_words_pt(1_000_000_000_000))

    def test_format_currency(self):
        self.assertEqual(format_currency(1234.56), "$1,234.56")
        self.assertEqual(format_currency(None), "N/A")

    def test_format_percent(self):
        self.assertEqual(format_percent(15.2), "+15.20%")
        self.assertEqual(format_percent(-5.5), "-5.50%")
        self.assertEqual(format_percent(None), "N/A")


if __name__ == "__main__":
    unittest.main()
