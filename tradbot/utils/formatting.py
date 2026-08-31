"""
Funções de formatação e utilidades de texto.
"""

from typing import Optional, Union


def number_to_words_pt(num: Optional[Union[int, float]]) -> str:
    """Converte um número em texto por extenso em português (milhões, bilhões, trilhões)."""
    if num is None:
        return "N/A"

    try:
        num_val = float(num)
    except (ValueError, TypeError):
        return "N/A"

    num_int = int(num_val)

    if num_int == 0:
        return "zero"

    unidades = ["", "um", "dois", "três", "quatro", "cinco", "seis", "sete", "oito", "nove"]
    dezenas = ["", "dez", "vinte", "trinta", "quarenta", "cinquenta", "sessenta", "setenta", "oitenta", "noventa"]
    centenas = ["", "cento", "duzentos", "trezentos", "quatrocentos", "quinhentos", "seiscentos", "setecentos", "oitocentos", "novecentos"]
    excecoes_dez = ["", "onze", "doze", "treze", "catorze", "quinze", "dezesseis", "dezessete", "dezoito", "dezenove"]

    if num_int < 10:
        return unidades[num_int]
    elif num_int < 20:
        return excecoes_dez[num_int - 10]
    elif num_int < 100:
        return dezenas[num_int // 10] + (" e " + unidades[num_int % 10] if num_int % 10 != 0 else "")
    elif num_int < 1000:
        if num_int == 100:
            return "cem"
        return centenas[num_int // 100] + (" e " + number_to_words_pt(num_int % 100) if num_int % 100 != 0 else "")

    if num_int >= 1_000_000_000_000_000_000:
        return f"{num_int / 1_000_000_000_000_000_000:.2f} quintilhões"
    if num_int >= 1_000_000_000_000_000:
        return f"{num_int / 1_000_000_000_000_000:.2f} quatrilhões"
    if num_int >= 1_000_000_000_000:
        return f"{num_int / 1_000_000_000_000:.2f} trilhões"
    if num_int >= 1_000_000_000:
        return f"{num_int / 1_000_000_000:.2f} bilhões"
    if num_int >= 1_000_000:
        return f"{num_int / 1_000_000:.2f} milhões"
    if num_int >= 1_000:
        return f"{num_int / 1_000:.2f} mil"

    return str(num_int)


def escape_markdown_v2(text: Optional[Any] = None) -> str:
    """Escapa todos os caracteres especiais do Telegram MarkdownV2."""
    if text is None:
        return ""

    text_str = str(text)
    special_characters = r"\_*[]()~`>#+-=|{}.!"
    escaped_text = ""
    for char in text_str:
        if char == '\\':
            escaped_text += r'\\'
        elif char in special_characters:
            escaped_text += '\\' + char
        else:
            escaped_text += char
    return escaped_text


def format_currency(value: Optional[float], decimals: int = 2) -> str:
    """Formata valor em dólares (ex: $1,250.00)."""
    if value is None:
        return "N/A"
    return f"${value:,.{decimals}f}"


def format_percent(value: Optional[float], decimals: int = 2) -> str:
    """Formata valor percentual (ex: +15.50%)."""
    if value is None:
        return "N/A"
    sign = "+" if value > 0 else ""
    return f"{sign}{value:.{decimals}f}%"
