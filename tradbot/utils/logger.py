"""
Configuração centralizada de logs para console e arquivo com suporte a UTF-8 no Windows.
"""

import logging
import sys
from typing import Optional


def setup_logger(name: str = "tradbot", log_file: Optional[str] = "tradbotgems.log", level: str = "INFO") -> logging.Logger:
    """Configura e retorna um logger padronizado com saída UTF-8 no console e arquivo."""
    logger = logging.getLogger(name)
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    logger.setLevel(numeric_level)

    # Forçar codificação UTF-8 no stdout para evitar erros em terminais Windows (cp1252)
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    if logger.handlers:
        return logger

    formatter = logging.Formatter(
        fmt="%(asctime)s - [%(levelname)s] - %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Console Handler com tratamento seguro de erros de codificação
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(numeric_level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File Handler
    if log_file:
        try:
            file_handler = logging.FileHandler(log_file, encoding="utf-8", errors="replace")
            file_handler.setLevel(numeric_level)
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
        except Exception as e:
            logger.warning(f"Não foi possível iniciar log em arquivo ({log_file}): {e}")

    return logger
