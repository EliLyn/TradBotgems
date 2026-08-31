"""
Funções de formatação e utilidades de texto modularizadas.
"""

from typing import Optional, Union, Any

UNIDADES = ["", "um", "dois", "três", "quatro", "cinco", "seis", "sete", "oito", "nove"]
DEZENAS = ["", "dez", "vinte", "trinta", "quarenta", "cinquenta", "sessenta", "setenta", "oitenta", "noventa"]
CENTENAS = ["", "cento", "duzentos", "trezentos", "quatrocentos", "quinhentos", "seiscentos", "setecentos", "oitocentos", "novecentos"]
EXCECOES_10 = ["", "onze", "doze", "treze", "catorze", "quinze", "dezesseis", "dezessete", "dezoito", "dezenove"]


def _format_small_int(n: int) -> str:
    """Formata inteiros menores que 100."""
    if n < 10:
        return UNIDADES[n]
    if n < 20:
        return EXCECOES_10[n - 10]
    resto = n % 10
    return DEZENAS[n // 10] + (f" e {UNIDADES[resto]}" if resto else "")


def _format_hundreds(n: int) -> str:
    """Formata inteiros de 100 a 999."""
    if n == 100:
        return "cem"
    resto = n % 100
    resto_str = f" e {_format_small_int(resto)}" if resto else ""
    return CENTENAS[n // 100] + resto_str


def _format_large_scales(n: int) -> Optional[str]:
    """Formata escalas de milhares até quintilhões."""
    scales = [
        (1_000_000_000_000_000_000, "quintilhões"),
        (1_000_000_000_000_000, "quatrilhões"),
        (1_000_000_000_000, "trilhões"),
        (1_000_000_000, "bilhões"),
        (1_000_000, "milhões"),
        (1_000, "mil"),
    ]
    for div, suffix in scales:
        if n >= div:
            return f"{n / div:.2f} {suffix}"
    return None


def number_to_words_pt(num: Optional[Union[int, float]]) -> str:
    """Converte um número em texto por extenso em português."""
    if num is None:
        return "N/A"
    try:
        n = int(float(num))
    except (ValueError, TypeError):
        return "N/A"
    if n == 0:
        return "zero"
    if n < 100:
        return _format_small_int(n)
    if n < 1000:
        return _format_hundreds(n)
    return _format_large_scales(n) or str(n)


def escape_markdown_v2(text: Optional[Any] = None) -> str:
    """Escapa caracteres especiais para MarkdownV2 do Telegram."""
    if text is None:
        return ""
    special = r"\_*[]()~`>#+-=|{}.!"
    return "".join(r"\\" if c == "\\" else f"\\{c}" if c in special else c for c in str(text))


def format_currency(val: Optional[float], dec: int = 2) -> str:
    """Formata valor monetário em dólares."""
    return f"${val:,.{dec}f}" if val is not None else "N/A"


def format_percent(val: Optional[float], dec: int = 2) -> str:
    """Formata valor percentual com sinal."""
    if val is None:
        return "N/A"
    return f"{'+' if val > 0 else ''}{val:.{dec}f}%"
