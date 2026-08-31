"""
Cliente HTTP base assíncrono com tratamento de erros, retries e rate limiting.
"""

import asyncio
import logging
from typing import Optional, Dict, Any
import aiohttp

logger = logging.getLogger("tradbot.http")


class BaseHttpClient:
    def __init__(self, session: Optional[aiohttp.ClientSession] = None):
        self._session = session
        self._owns_session = False

    async def get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
            self._owns_session = True
        return self._session

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()

    async def fetch_json(
        self,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, Any]] = None,
        max_retries: int = 3,
        retry_delay: float = 2.0
    ) -> Optional[Any]:
        """Executa uma requisição GET assíncrona com suporte a retry em 429 / 5xx."""
        session = await self.get_session()

        for attempt in range(1, max_retries + 1):
            try:
                async with session.get(url, headers=headers, params=params, timeout=aiohttp.ClientTimeout(total=20)) as response:
                    # Rate limit handling (429)
                    if response.status == 429:
                        wait_time = 60 if "coingecko" in url else (retry_delay * attempt * 2)
                        logger.warning(f"Erro 429 (Rate Limit) para {url}. Aguardando {wait_time}s (Tentativa {attempt}/{max_retries})")
                        await asyncio.sleep(wait_time)
                        continue

                    # CoinGlass erro 500 comum quando token não tem derivativos
                    if response.status == 500 and "coinglass" in url:
                        logger.debug(f"CoinGlass: Sem mercado de derivativos para a URL: {url} (Status 500)")
                        return None

                    response.raise_for_status()
                    return await response.json()

            except aiohttp.ClientResponseError as e:
                logger.warning(f"Erro de resposta HTTP {e.status} para {url}: {e.message}")
                if e.status >= 500 and attempt < max_retries:
                    await asyncio.sleep(retry_delay * attempt)
                    continue
                return None
            except asyncio.TimeoutError:
                logger.warning(f"Timeout ao acessar {url} (Tentativa {attempt}/{max_retries})")
                if attempt < max_retries:
                    await asyncio.sleep(retry_delay * attempt)
                    continue
                return None
            except aiohttp.ClientError as e:
                logger.warning(f"Erro de rede para {url}: {e}")
                if attempt < max_retries:
                    await asyncio.sleep(retry_delay * attempt)
                    continue
                return None
            except Exception as e:
                logger.error(f"Erro inesperado ao buscar {url}: {e}")
                return None

        return None
