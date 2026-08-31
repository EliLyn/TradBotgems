"""
TradBotGems - Entry Point Principal (funções <= 25 linhas).
"""

import argparse
import asyncio
import sys
import os
from typing import Optional

try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError, OSError):
    pass

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from tradbot.config import settings
from tradbot.utils.logger import setup_logger
from tradbot.services.collector import GemCollectorService
from tradbot.services.dex_monitor import DexMonitorService


def parse_args():
    """Configura e retorna argumentos de linha de comando."""
    p = argparse.ArgumentParser(description="TradBotGems - Bot Inteligente de Análise e Descoberta de Crypto Gems")
    p.add_argument("--mode", choices=["gems", "dex", "all"], default="gems", help="Modo de execução")
    p.add_argument("--test", action="store_true", help="Executa apenas 1 ciclo curto de teste")
    p.add_argument("--max-tokens", type=int, default=None, help="Limite de tokens no teste")
    p.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"], help="Nível de log")
    return p.parse_args()


async def _run_test_mode(collector: GemCollectorService, max_tokens: Optional[int], logger):
    """Executa o ciclo único de teste rápido."""
    logger.info("⚡ Executando ciclo de teste rápido...")
    await collector.run_single_cycle(max_tokens=max_tokens or 3)
    logger.info("✅ Teste finalizado com sucesso!")


async def _run_continuous_mode(collector: GemCollectorService, dex: DexMonitorService, mode: str):
    """Executa os loops contínuos conforme o modo selecionado."""
    tasks = []
    if mode in ["gems", "all"]:
        tasks.append(asyncio.create_task(collector.run_forever()))
    if mode in ["dex", "all"]:
        tasks.append(asyncio.create_task(dex.run_forever()))
    try:
        await asyncio.gather(*tasks)
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass


async def main():
    """Orquestrador principal da aplicação."""
    args = parse_args()
    logger = setup_logger(level=args.log_level, log_file=settings.log_file)
    logger.info("🚀 TradBotGems v2.0 - Open Source Crypto Hunter")
    if not settings.telegram.is_configured:
        logger.warning("⚠️ TELEGRAM_BOT_TOKEN ou TELEGRAM_CHAT_ID não configurados no .env!")
    collector = GemCollectorService()
    dex = DexMonitorService()
    if args.test:
        await _run_test_mode(collector, args.max_tokens, logger)
    else:
        await _run_continuous_mode(collector, dex, args.mode)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nEncerrado.")
