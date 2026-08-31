"""
Cliente HTTP base assíncrono com funções <= 25 linhas.
"""

import asyncio
import logging
import socket
from typing import Optional, Dict, Any
import aiohttp

logger = logging.getLogger("tradbot.http")


async def _handle_request_once(session: aiohttp.ClientSession, url: str, headers: dict, params: dict, attempt: int, max_r: int, delay: float):
    """Executa uma tentativa única de requisição HTTP com rate limit."""
    try:
        async with session.get(url, headers=headers, params=params, timeout=aiohttp.ClientTimeout(total=20)) as resp:
            if resp.status == 429:
                wait_t = 60 if "coingecko" in url else (delay * attempt * 2)
                logger.warning(f"Rate Limit 429 para {url}. Aguardando {wait_t}s...")
                await asyncio.sleep(wait_t)
                return "RETRY"
            if resp.status == 500 and "coinglass" in url:
                return None
            resp.raise_for_status()
            return await resp.json()
    except (aiohttp.ClientResponseError, aiohttp.ClientError, asyncio.TimeoutError) as e:
        logger.warning(f"Erro de rede ({type(e).__name__}) para {url} (Tentativa {attempt}/{max_r})")
        if attempt < max_r:
            await asyncio.sleep(delay * attempt)
            return "RETRY"
        return None


class BaseHttpClient:
    def __init__(self, session: Optional[aiohttp.ClientSession] = None):
        self._session = session
        self._owns_session = False

    async def get_session(self) -> aiohttp.ClientSession:
        """Obtém ou instancia sessão aiohttp com IPv4 forçado."""
        if self._session is None or self._session.closed:
            connector = aiohttp.TCPConnector(family=socket.AF_INET, resolver=aiohttp.ThreadedResolver())
            self._session = aiohttp.ClientSession(connector=connector)
            self._owns_session = True
        return self._session

    async def close(self):
        """Fecha a sessão HTTP se ela pertencer a esta instância."""
        if self._session and not self._session.closed:
            await self._session.close()

    async def fetch_json(self, url: str, headers: Optional[Dict[str, str]] = None, params: Optional[Dict[str, Any]] = None, max_retries: int = 3, retry_delay: float = 2.0) -> Optional[Any]:
        """Executa requisição GET assíncrona com suporte a retries."""
        session = await self.get_session()
        for attempt in range(1, max_retries + 1):
            res = await _handle_request_once(session, url, headers or {}, params or {}, attempt, max_retries, retry_delay)
            if res != "RETRY":
                return res
        return None
