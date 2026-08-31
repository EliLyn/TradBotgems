"""
TradBotGems - Entry Point Principal (CLI / Runner)
Execução do caçador de gems, monitor de DEX e testes rápidos.
"""

import argparse
import asyncio
import sys
import os

# Forçar suporte a UTF-8 no Windows Console
try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# Adiciona o diretório atual ao PYTHONPATH
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from tradbot.config import settings
from tradbot.utils.logger import setup_logger
from tradbot.services.collector import GemCollectorService
from tradbot.services.dex_monitor import DexMonitorService


async def main():
    parser = argparse.ArgumentParser(
        description="TradBotGems - Bot Inteligente de Análise e Descoberta de Crypto Gems"
    )
    parser.add_argument(
        "--mode",
        choices=["gems", "dex", "all"],
        default="gems",
        help="Modo de execução: 'gems' (caçador de micro-caps/altcoins), 'dex' (monitor em tempo real de novos pares), ou 'all' (ambos)"
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Executa apenas 1 ciclo com poucos tokens para testar a conectividade e alertas"
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=None,
        help="Limita o número de tokens analisados no ciclo de teste"
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Nível de detalhamento do log"
    )

    args = parser.parse_args()

    # Inicialização do logger padronizado
    logger = setup_logger(level=args.log_level, log_file=settings.log_file)
    logger.info("==================================================")
    logger.info("🚀 TradBotGems v2.0 - Open Source Crypto Hunter")
    logger.info(f"Modo: {args.mode.upper()} | Teste: {args.test}")
    logger.info("==================================================")

    # Validar credenciais mínimas
    if not settings.telegram.is_configured:
        logger.warning(
            "⚠️ ATENÇÃO: TELEGRAM_BOT_TOKEN ou TELEGRAM_CHAT_ID não estão configurados no arquivo .env!\n"
            "As notificações no Telegram não serão entregues até que você preencha essas variáveis."
        )

    collector_service = GemCollectorService()
    dex_service = DexMonitorService()

    if args.test:
        logger.info("⚡ Executando ciclo de teste rápido...")
        max_t = args.max_tokens or 3
        await collector_service.run_single_cycle(max_tokens=max_t)
        logger.info("✅ Teste finalizado com sucesso!")
        return

    # Execução normal contínua
    tasks = []
    if args.mode in ["gems", "all"]:
        tasks.append(asyncio.create_task(collector_service.run_forever()))

    if args.mode in ["dex", "all"]:
        tasks.append(asyncio.create_task(dex_service.run_forever()))

    try:
        await asyncio.gather(*tasks)
    except (KeyboardInterrupt, asyncio.CancelledError):
        logger.info("🛑 Bot interrompido pelo usuário. Encerrando serviços graciosamente...")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nEncerrado.")
