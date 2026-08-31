# 💎 TradBotGems - Open Source Crypto Gem Hunter & Market Intelligence Bot

[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)
[![Telegram](https://img.shields.io/badge/Telegram-Alerts-blue.svg)](https://telegram.org/)
[![AsyncIO](https://img.shields.io/badge/AsyncIO-Enabled-yellow.svg)](https://docs.python.org/3/library/asyncio.html)

**TradBotGems** é um bot modular e assíncrono de inteligência de mercado cripto desenvolvido em Python. Ele monitora e filtra automaticamente tokens de micro e média capitalização (*gems*), analisa dados de derivativos em tempo real (Open Interest, Funding Rate, Liquidações), verifica métricas on-chain e novos pares em DEXs descentralizadas, enviando alertas enriquecidos diretamente para o seu Telegram.

---

## 🚀 Principais Funcionalidades

- 🔍 **Varredura Inteligente de Micro-Caps & Gems:** Filtra tokens na CoinGecko em faixas específicas de Market Cap (ex: $20k a $10M) para identificar assimetrias de valor e novos projetos promissores.
- 📊 **Análise de Derivativos (CoinGlass):** Integração com métricas de Futuros, Open Interest, Funding Rate, Long/Short Ratio e volume de liquidações em 24h.
- 🦄 **Monitor de DEX em Tempo Real:** Monitora pares recém-criados ou de alto volume em Uniswap, PancakeSwap, Raydium e outras DEXs via DexScreener.
- 🛡️ **Checagem On-Chain & Honeypot:** Verificação de segurança de contrato para mitigar riscos de golpes e liquidez travada.
- 🤖 **Classificação Fundamentalista por IA e Categorias:** Pontuação automática para nichos de alta demanda (RWA - Real World Assets, IA, Bitcoin Ecosystem/Ordinals, Gaming).
- 📢 **Alertas Telegram em MarkdownV2:** Relatórios e cartões de análise completos com links sociais, endereços de contrato, supply e gráficos de variação.
- ⚡ **Arquitetura Assíncrona & Cache Resiliente:** Construído com `aiohttp` e `asyncio`, com retries exponenciais, tratamento de rate limit (HTTP 429) e cache local com TTL.

---

## 📁 Arquitetura do Projeto

```
core/
├── tradbot/                      # Pacote principal modular
│   ├── __init__.py
│   ├── config.py                 # Centralização de configurações e .env
│   ├── models.py                 # Modelos de dados e Dataclasses tipadas
│   ├── clients/                  # Clientes HTTP assíncronos
│   │   ├── base.py               # Cliente base com retry, timeout e rate limit
│   │   ├── coingecko.py          # API CoinGecko
│   │   ├── coinglass.py          # API CoinGlass (Derivativos)
│   │   ├── dexscreener.py        # API DexScreener (DEX pairs)
│   │   ├── evm_explorer.py       # Etherscan, BscScan, PolygonScan, etc.
│   │   └── honeypot.py           # Verificação de contratos maliciosos
│   ├── services/                 # Regras de negócio e serviços
│   │   ├── analyzer.py           # Motor de pontuação e análise de potencial
│   │   ├── notifier.py           # Notificações e formatação para Telegram
│   │   ├── cache.py              # Gerenciador de cache local com TTL
│   │   ├── collector.py          # Orquestrador do ciclo 24/7 de gems
│   │   └── dex_monitor.py        # Monitor de pares DEX
│   └── utils/                    # Utilitários de apoio
│       ├── formatting.py         # Escape MarkdownV2 e números por extenso
│       └── logger.py             # Logging simultâneo em console e arquivo
├── tests/                        # Testes unitários automatizados
│   ├── test_formatting.py
│   └── test_analyzer.py
├── backup_original/              # Cópia preservada dos scripts legados originais
├── .env.example                  # Template seguro de variáveis de ambiente
├── .gitignore                    # Regras de exclusão de secrets, logs e caches
├── requirements.txt              # Dependências do projeto
├── run.py                        # Ponto de entrada CLI amigável
└── README.md                     # Documentação do projeto
```

---

## ⚙️ Instalação e Configuração

### 1. Clonar o Repositório
```bash
git clone https://github.com/SEU_USUARIO/TradBotGems.git
cd TradBotGems/core
```

### 2. Criar Ambiente Virtual (Recomendado)
```bash
python -m venv venv
# No Windows:
venv\Scripts\activate
# No Linux/Mac:
source venv/bin/activate
```

### 3. Instalar Dependências
```bash
pip install -r requirements.txt
```

### 4. Configurar as Variáveis de Ambiente
Copie o arquivo `.env.example` para `.env` e preencha suas credenciais:
```bash
cp .env.example .env
```

Edite o `.env`:
```ini
# Configurações do Telegram (Obrigatório para alertas)
TELEGRAM_BOT_TOKEN=seu_token_aqui
TELEGRAM_CHAT_ID=seu_chat_id_aqui

# CoinGlass (Opcional - para métricas de derivativos e futuros)
COINGLASS_API_KEY=sua_chave_coinglass

# Exploradores EVM (Opcional)
ETHERSCAN_API_KEY=sua_chave_etherscan

# Filtros de Market Cap
MIN_MARKET_CAP_USD=20000
MAX_MARKET_CAP_USD=10000000
COLLECTION_INTERVAL_SECONDS=600
```

---

## 🎮 Como Executar

### 1. Teste Rápido (Executa 1 ciclo com 3 tokens para validar conectividade)
```bash
python run.py --test
```

### 2. Executar o Caçador de Gems (Loop Contínuo 24/7)
```bash
python run.py --mode gems
```

### 3. Executar o Monitor de DEX (Uniswap / Pancake / Base em Tempo Real)
```bash
python run.py --mode dex
```

### 4. Executar Ambos Simultaneamente
```bash
python run.py --mode all
```

### 5. Opções Adicionais de CLI
```bash
python run.py --help
# Opções:
#   --mode {gems,dex,all}   Seleciona o modo de operação
#   --test                  Executa teste único de conectividade
#   --max-tokens N          Limita o número de tokens analisados
#   --log-level {DEBUG,INFO,WARNING,ERROR}  Ajusta a verbosidade dos logs
```

---

## 🧪 Executando os Testes Unitários

Para rodar a suíte de testes automatizados:
```bash
python -m unittest discover -s tests
```

---

## 📜 Licença

Distribuído sob a licença **MIT**. Consulte `LICENSE` para mais informações.

---

## ⚠️ Aviso Legal (Disclaimer)

*Este software é fornecido exclusivamente para fins educacionais e de pesquisa de mercado. Não constitui recomendação financeira ou de investimento. O mercado de criptomoedas, especialmente micro-caps e tokens de baixa liquidez, envolve alto risco de perda total de capital.*
