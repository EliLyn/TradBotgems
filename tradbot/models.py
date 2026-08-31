"""
Modelos de dados tipados para o TradBotGems.
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone


def _utc_now():
    return datetime.now(timezone.utc)


@dataclass
class TokenMarketSummary:
    """Resumo de mercado básico obtido da listagem de moedas."""
    id: str
    symbol: str
    name: str
    market_cap: float
    current_price: float
    price_change_percentage_24h: Optional[float] = None
    price_change_percentage_7d: Optional[float] = None
    total_volume: Optional[float] = None


@dataclass
class TokenFullDetails:
    """Detalhes completos de um token."""
    id: str
    symbol: str
    name: str
    market_cap_usd: Optional[float] = None
    current_price_usd: Optional[float] = None
    total_supply: Optional[float] = None
    circulating_supply: Optional[float] = None
    description: str = "N/A"
    categories: str = "N/A"
    blockchain_id: str = "N/A"
    contract_address: Optional[str] = None
    homepage: str = "N/A"
    twitter_handle: str = "N/A"
    twitter_followers: int = 0
    telegram_url: str = "N/A"
    telegram_channel_user_count: int = 0
    subreddit_url: str = "N/A"
    discord_link: str = "N/A"


@dataclass
class DerivativesMetrics:
    """Métricas de derivativos obtidas da CoinGlass."""
    open_interest: Optional[float] = None
    open_interest_change_24h_percent: Optional[float] = None
    funding_rate: Optional[float] = None
    long_short_ratio: Optional[float] = None
    liquidation_long_24h_usd: Optional[float] = None
    liquidation_short_24h_usd: Optional[float] = None
    futures_volume_24h_usd: Optional[float] = None

    @property
    def has_data(self) -> bool:
        return any(
            v is not None and v != 0
            for v in [
                self.open_interest,
                self.funding_rate,
                self.long_short_ratio,
                self.liquidation_long_24h_usd,
                self.liquidation_short_24h_usd,
                self.futures_volume_24h_usd
            ]
        )


@dataclass
class AnalysisResult:
    """Resultado da análise quantitativa e qualitativa de um token."""
    token_id: str
    symbol: str
    potential_note: str
    alerts: List[str] = field(default_factory=list)
    tx_count_12h: int = 0
    tx_count_24h: int = 0
    score: int = 0
    classification_level: str = "Normal"
    is_contract_renounced: bool = False
    timestamp_utc: datetime = field(default_factory=_utc_now)


@dataclass
class DexPairInfo:
    """Informações sobre pares de DEX (Uniswap, Raydium, Pancake, etc.)."""
    chain_id: str
    dex_id: str
    pair_address: str
    base_token_symbol: str
    base_token_address: str
    quote_token_symbol: str
    price_usd: Optional[float] = None
    liquidity_usd: Optional[float] = None
    volume_24h_usd: Optional[float] = None
    txns_60m: int = 0
    pair_created_at: Optional[datetime] = None
    is_honeypot: Optional[bool] = None
