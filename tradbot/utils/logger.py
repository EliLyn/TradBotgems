"""
Configuração centralizada de logs para console e arquivo (funções <= 25 linhas).
"""

import logging
import sys
from typing import Optional


def _configure_terminal_utf8():
    """Força codificação UTF-8 no stdout para evitar erros em terminais Windows."""
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError, OSError):
        pass


def _create_file_handler(log_file: str, level: int, fmt: logging.Formatter) -> Optional[logging.FileHandler]:
    """Cria e retorna o handler de arquivo se possível."""
    try:
        fh = logging.FileHandler(log_file, encoding="utf-8", errors="replace")
        fh.setLevel(level)
        fh.setFormatter(fmt)
        return fh
    except (OSError, IOError):
        return None


def setup_logger(name: str = "tradbot", log_file: Optional[str] = "tradbotgems.log", level: str = "INFO") -> logging.Logger:
    """Configura e retorna um logger padronizado com saída UTF-8."""
    logger = logging.getLogger(name)
    num_level = getattr(logging, level.upper(), logging.INFO)
    logger.setLevel(num_level)
    _configure_terminal_utf8()
    if logger.handlers:
        return logger
    fmt = logging.Formatter(fmt="%(asctime)s - [%(levelname)s] - %(name)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(num_level)
    ch.setFormatter(fmt)
    logger.addHandler(ch)
    if log_file:
        fh = _create_file_handler(log_file, num_level, fmt)
        if fh:
            logger.addHandler(fh)
    return logger
