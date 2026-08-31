# 💎 TradBotGems - Scanner de Criptoativos & Alertas no Telegram

<div align="center">

[![Python Version](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=flat-square)](https://opensource.org/licenses/MIT)
[![Telegram](https://img.shields.io/badge/Telegram-Alerts-2CA5E0?style=flat-square&logo=telegram&logoColor=white)](https://telegram.org/)
[![Tests](https://img.shields.io/badge/Tests-19%20Passing-success?style=flat-square)](tests/)

**Scanner modular em Python baseado nos scripts originais de coleta, análise de derivativos, monitor de DEX e notificações via Telegram.**

[O que havia na pasta original](#-o-que-havia-na-pasta-original-backup-de-julho2025) •
[O que foi feito na refatoração](#-o-que-foi-feito-na-refatoração-agosto2026) •
[Comparativo Real](#-comparativo-real-dos-arquivos) •
[Como Funciona](#-como-funciona) •
[Instalação e Uso](#-instalação-e-uso) •
[Testes](#-testes-unitários)

</div>

---

## 📂 O que havia na pasta original (Backup de Julho/2025)

No backup original preservado em `backup_original/`, o projeto era composto por scripts independentes criados entre 30/06/2025 e 09/07/2025:

1. **`TradBotGems.py` (38 KB - 09/07/2025):**
   - Script principal de varredura multi-página na CoinGecko (faixa de Market Cap configurada entre \$20k e \$10M).
   - Coleta de dados de futuros na CoinGlass: Open Interest, Funding Rate, Long/Short Ratio, Volume 24h e Liquidações.
   - Geração de notas de potencial por faixas de valor e categorias (RWA, IA, Ecossistema Bitcoin, Supply > 1T).
   - Envio de cartões formatados em MarkdownV2 e resumo diário de Top Gainers / Alto Volume no Telegram.
   - Simulação de contagem de transações (12h/24h) com `random.randint` para testar os gatilhos de alerta.

2. **`data_collector.py` (51 KB - 06/07/2025):**
   - Coletor com motor de pontuação por tiers: volume 24h, média de volume semanal, seguidores no Twitter, membros no Telegram e taxas de crescimento.
   - Categorias bônus (Gaming, RWA, Bitcoin Ecosystem) somando pontos na classificação.
   - Sistema de níveis com emojis (`🚨 CRÍTICO`, `🔴 Baixo`, `🟠 Moderado`, `🟡 Alto`, `🟢 DESTAQUE`).
   - Mapeamento de exploradores EVM (Ethereum, BSC, Polygon, Arbitrum, Optimism, Avalanche, Fantom, Gnosis, Cronos, Base).

3. **`dex_monitor.py` & `dex_monitor_test.py` (21 KB / 9 KB - 05/07/2025):**
   - Monitoramento de pares DEX consultando a API do DexScreener para os contratos de WETH, WBNB, WMATIC, WAVAX e WFTM.
   - Filtros locais: liquidez mínima (\$50k), volume 24h (\$50k) e transações em 60 min.
   - Consulta à API do Honeypot.is para checagem de risco em contratos.

4. **`SuperDataCollector.py` (8.5 KB - 06/07/2025):**
   - Coletor focado em lista fixa de tokens principais (BTC, ETH, BNB, SOL, DOGE), gerando `crypto_data.json`.

5. **`bitget_websocket.py` & `bitget_sdk_websocket_test.py` (6.7 KB / 4.7 KB - 06/07 a 09/07/2025):**
   - Testes de conexão WebSocket com a exchange Bitget para dados de tickers em tempo real.

6. **Arquivos de Áudio e Cache:**
   - Efeitos sonoros locais (`caixa_registradora.wav.wav`, `sirene.wav.wav`).
   - Caches e históricos JSON (`coingecko_token_cache.json`, `token_classification_history.json`, `known_coingecko_tokens.json`).

---

## 🛠️ O que foi feito na refatoração (Agosto/2026)

Os scripts isolados foram unificados em uma arquitetura de software modular dentro do pacote `tradbot/`:

1. **Unificação dos Módulos:**
   - **`tradbot/clients/`**: Clientes HTTP assíncronos separados por serviço (`coingecko.py`, `coinglass.py`, `dexscreener.py`, `evm_explorer.py`, `honeypot.py`).
   - **`tradbot/services/`**: Lógicas de negócio isoladas em `analyzer.py` (regras e scoring), `notifier.py` (Telegram), `cache.py` (gerenciamento com TTL) e `collector.py` (orquestrador de loops).
   - **`tradbot/models.py`**: Estruturas de dados tipadas com Dataclasses (`TokenMarketSummary`, `TokenFullDetails`, `DerivativesMetrics`, `AnalysisResult`, `DexPairInfo`).
2. **Segurança de Credenciais:**
   - Remoção de chaves e tokens gravados diretamente no código; migração para `.env` com arquivo modelo `.env.example` e proteção via `.gitignore`.
3. **Resolução de Rede e DNS no Windows:**
   - Implementação de `TCPConnector(family=socket.AF_INET, resolver=ThreadedResolver())` resolvendo problemas de conexão assíncrona IPv6 no Windows.
4. **Regra de Funções Enxutas:**
   - Todas as funções e métodos de todos os módulos foram estruturados para ter **no máximo 25 linhas**.
5. **Testes Automatizados:**
   - Criação de **19 testes unitários** com `unittest` cobrindo todos os módulos do pacote.
6. **Entry Point CLI (`run.py`):**
   - Executável único com suporte a parâmetros: `--mode gems`, `--mode dex`, `--mode all`, `--test`, `--max-tokens`.

---

## 📊 Comparativo Real dos Arquivos

| Arquivo Original (Backup Jul/2025) | Onde está na versão modular (Ago/2026) | O que mudou |
| :--- | :--- | :--- |
| `TradBotGems.py` (784 linhas) | `tradbot/services/collector.py` + `notifier.py` | Dividido em serviços desacoplados; funções ≤ 25 linhas; escape seguro |
| `data_collector.py` (895 linhas) | `tradbot/services/analyzer.py` + `clients/evm_explorer.py` | Lógica de pontuação, categorias e mapeamento EVM transformadas em classes dedicadas |
| `dex_monitor.py` (416 linhas) | `tradbot/services/dex_monitor.py` + `clients/dexscreener.py` + `honeypot.py` | Clientes de API isolados do serviço de monitoramento |
| `SuperDataCollector.py` (182 linhas) | `tradbot/services/collector.py` (modo `--test`) | Integrado ao fluxo de coleta com opções de limite |
| Chaves hardcoded nos scripts | `tradbot/config.py` + `.env` | Credenciais lidas via variáveis de ambiente com fallback seguro |
| Sem testes unitários | Pasta `tests/` (19 testes) | Testes para formatadores, analisador, cache, clientes e modelos |

---

## ⚙️ Instalação e Uso

### 1. Clonar e Instalar
```bash
git clone https://github.com/EliLyn/TradBotGems.git
cd TradBotGems/core

python -m venv venv
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

pip install -r requirements.txt
```

### 2. Configurar o `.env`
Copie o `.env.example`:
```bash
cp .env.example .env
```
Preencha seu `TELEGRAM_BOT_TOKEN` e `TELEGRAM_CHAT_ID`. A chave da `COINGLASS_API_KEY` é opcional (necessária apenas se desejar dados de futuros/derivativos).

### 3. Comandos de Execução
```bash
# Teste rápido (1 ciclo com 3 tokens):
python run.py --test

# Executar o Caçador de Gems (CoinGecko + CoinGlass):
python run.py --mode gems

# Executar o Monitor de DEX (DexScreener + Honeypot):
python run.py --mode dex

# Executar ambos simultaneamente:
python run.py --mode all
```

---

## 🧪 Testes Unitários

Para rodar a suíte com os 19 testes automatizados:

```bash
python -m unittest discover -s tests -v
```

Resultado:
```
Ran 19 tests in 0.005s
OK
```

---

## 📄 Licença

Distribuído sob a licença [MIT](LICENSE).

<div align="center">

*Concepção e evolução de código por [EliLyn](https://github.com/EliLyn).*

</div>
