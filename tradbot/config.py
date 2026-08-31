"""
Configuração do TradBotGems carregada a partir de variáveis de ambiente (.env).
"""

import os
from dataclasses import dataclass, field
from typing import Dict

# Tentar carregar dotenv se disponível
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


@dataclass
class TelegramConfig:
    bot_token: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    chat_id: str = os.getenv("TELEGRAM_CHAT_ID", "")

    @property
    def is_configured(self) -> bool:
        return bool(self.bot_token and self.chat_id)


@dataclass
class CoinGlassConfig:
    api_key: str = os.getenv("COINGLASS_API_KEY", "")
    base_url: str = os.getenv("COINGLASS_API_BASE_URL", "https://open-api.coinglass.com/api/pro/v1/futures")

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)


@dataclass
class CoinGeckoConfig:
    base_url: str = os.getenv("COINGECKO_API_BASE_URL", "https://api.coingecko.com/api/v3")
    cache_file: str = os.getenv("CACHE_FILE_NAME", "coingecko_token_cache.json")
    cache_expiry_hours: int = int(os.getenv("CACHE_EXPIRY_HOURS", "6"))
    per_page: int = int(os.getenv("COINGECKO_PER_PAGE", "300"))
    total_pages_to_check: int = int(os.getenv("COINGECKO_TOTAL_PAGES", "59"))


@dataclass
class ExplorerConfig:
    etherscan_api_key: str = os.getenv("ETHERSCAN_API_KEY", "")
    bscscan_api_key: str = os.getenv("BSCSCAN_API_KEY", "")
    polygonscan_api_key: str = os.getenv("POLYGONSCAN_API_KEY", "")
    arbiscan_api_key: str = os.getenv("ARBISCAN_API_KEY", "")
    basescan_api_key: str = os.getenv("BASESCAN_API_KEY", "")
    
    url_map: Dict[str, str] = field(default_factory=lambda: {
        'ethereum': "https://api.etherscan.io/api",
        'binance-smart-chain': "https://api.bscscan.com/api",
        'polygon-pos': "https://api.polygonscan.io/api",
        'arbitrum-one': "https://api.arbiscan.io/api",
        'optimistic-ethereum': "https://api-optimistic.etherscan.io/api",
        'avalanche': "https://api.snowscan.io/api",
        'base': "https://api.basescan.org/api",
        'fantom': "https://api.ftmscan.com/api",
    })


@dataclass
class BotSettings:
    min_market_cap_usd: float = float(os.getenv("MIN_MARKET_CAP_USD", "20000"))
    max_market_cap_usd: float = float(os.getenv("MAX_MARKET_CAP_USD", "10000000"))
    high_volume_threshold_usd: float = float(os.getenv("HIGH_VOLUME_THRESHOLD_USD", "500000"))
    top_gainers_count: int = int(os.getenv("TOP_GAINERS_COUNT", "5"))

    collection_interval_seconds: int = int(os.getenv("COLLECTION_INTERVAL_SECONDS", "600"))
    sleep_between_tokens: int = int(os.getenv("SLEEP_BETWEEN_TOKEN_REQUESTS_SECONDS", "20"))
    sleep_between_pages: int = int(os.getenv("SLEEP_BETWEEN_PAGE_REQUESTS_SECONDS", "22"))

    telegram: TelegramConfig = field(default_factory=TelegramConfig)
    coinglass: CoinGlassConfig = field(default_factory=CoinGlassConfig)
    coingecko: CoinGeckoConfig = field(default_factory=CoinGeckoConfig)
    explorers: ExplorerConfig = field(default_factory=ExplorerConfig)
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    log_file: str = os.getenv("LOG_FILE", "tradbotgems.log")


# Instância global padrão de configurações
settings = BotSettings()
