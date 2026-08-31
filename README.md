# 💎 TradBotGems - Crypto Market Scanner & Telegram Alert Bot

<div align="center">

[![Python Version](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=flat-square)](https://opensource.org/licenses/MIT)
[![Telegram](https://img.shields.io/badge/Telegram-Alerts-2CA5E0?style=flat-square&logo=telegram&logoColor=white)](https://telegram.org/)
[![Tests](https://img.shields.io/badge/Tests-19%20Passing-success?style=flat-square)](tests/)

**Scanner modular em Python para filtragem de tokens (micro e small caps), consulta de métricas de futuros via CoinGlass e envio de resumos formatados no Telegram.**

[Sobre o Projeto](#-sobre-o-projeto) •
[A Evolução (v1 vs v2)](#-a-evolução-do-projeto-v1-vs-v2) •
[O que o Bot Realmente Faz](#-o-que-o-bot-realmente-faz) •
[Instalação](#-instalação-e-configuração) •
[Como Usar](#-como-usar) •
[Testes](#-testes-unitários) •
[Limitações Conhecidas](#-limitações-e-transparência)

</div>

---

## 📖 Sobre o Projeto

O **TradBotGems** nasceu como um projeto experimental pessoal para automatizar a descoberta e o acompanhamento de tokens cripto em faixas específicas de capitalização de mercado.

Ele consome dados públicos da API da **CoinGecko**, enriquece com dados de derivativos da **CoinGlass** (quando disponíveis para o ativo) e envia relatórios estruturados para um canal ou conversa privada no **Telegram**.

---

## 📈 A Evolução do Projeto (v1 vs v2)

Este repositório documenta a evolução prática de um protótipo inicial para uma base de código modular e auditável:

| Aspecto | v1.0 — Protótipo (09/07/2025) | v2.0 — Modular (31/08/2026) |
| :--- | :--- | :--- |
| **Estrutura** | Script monolítico (~800 linhas em arquivo único) | Pacote modular (`tradbot/`) com funções de no máximo 25 linhas |
| **Segurança de Chaves** | Tokens e chaves de API hardcoded no script | Variáveis de ambiente isoladas em `.env` (bloqueadas no `.gitignore`) |
| **Fontes de Dados** | CoinGecko + endpoints básicos da CoinGlass | Clientes desacoplados: CoinGecko, CoinGlass, DexScreener, EVM e Honeypot |
| **Tratamento de Rede** | Requisições simples com risco de falha | Retries, resolução IPv4 forçada no Windows e fallback de cache local |
| **Alertas Telegram** | Função de envio com escape manual frágil | Notificador com escape MarkdownV2 rigoroso e divisão de mensagens |
| **Métricas On-Chain** | Valores de transações simulados para teste de layout | Módulos preparados para explorers EVM (Etherscan, BscScan, etc.) |
| **Testes** | Nenhum teste automatizado | 19 testes unitários cobrindo todos os módulos (`unittest`) |
| **Execução** | Loop único sem parâmetros | CLI com argumentos (`--mode gems`, `--mode dex`, `--test`, `--max-tokens`) |

---

## 🔍 O que o Bot Realmente Faz

### 1. Varredura Periódica de Mercado (CoinGecko)
- Consulta páginas da CoinGecko em intervalos configuráveis.
- Filtra tokens cuja capitalização de mercado esteja dentro da faixa desejada (ex: entre \$20.000 e \$10.000.000).
- Salva o resultado em cache local (`coingecko_token_cache.json`) para evitar requisições desnecessárias.

### 2. Consulta de Derivativos (CoinGlass)
- Para cada token filtrado, consulta se há dados de derivativos disponíveis:
  - Open Interest (OI)
  - Funding Rate (Taxa de Financiamento)
  - Long/Short Ratio
  - Volume de Liquidações em 24h
- Se o token não tiver mercado de futuros listado, o bot trata silenciosamente e marca esses campos como `N/A`.

### 3. Classificação por Regras e Categorias
- Avalia faixas de Market Cap para gerar notas descritivas.
- Identifica palavras-chave nas categorias do token (ex: *Artificial Intelligence*, *Gaming*, *RWA*, *Bitcoin Ecosystem*).

### 4. Notificações no Telegram
- Monta um cartão formatado em MarkdownV2 com links sociais, suprimento (supply) e métricas disponíveis.
- Gera um resumo diário opcional com os maiores ganhadores do ciclo (*Top Gainers*).

### 5. Monitor de DEX (Polling Periódico)
- Consulta a API pública do DexScreener para pares com liquidez mínima pré-definida.
- Faz uma checagem auxiliar de contrato via API Honeypot.is.

---

## 📁 Estrutura do Código

```
core/
├── tradbot/                      # Pacote principal
│   ├── __init__.py
│   ├── config.py                 # Configurações centralizadas via .env
│   ├── models.py                 # Modelos de dados e Dataclasses
│   ├── clients/                  # Clientes HTTP assíncronos
│   │   ├── base.py               # Cliente base com retry e timeout
│   │   ├── coingecko.py          # Integração CoinGecko
│   │   ├── coinglass.py          # Integração CoinGlass
│   │   ├── dexscreener.py        # Integração DexScreener
│   │   ├── evm_explorer.py       # Integração com exploradores EVM
│   │   └── honeypot.py           # Consulta à API Honeypot.is
│   ├── services/                 # Regras de negócio
│   │   ├── analyzer.py           # Regras de pontuação e categorias
│   │   ├── notifier.py           # Formatação e envio Telegram
│   │   ├── cache.py              # Gerenciador de cache com TTL
│   │   ├── collector.py          # Orquestrador do ciclo de gems
│   │   └── dex_monitor.py        # Polling de pares DEX
│   └── utils/                    # Utilitários auxiliares
│       ├── formatting.py         # Formatação de texto e números
│       └── logger.py             # Configuração de logs
├── tests/                        # 19 Testes unitários automatizados
│   ├── test_analyzer.py
│   ├── test_cache.py
│   ├── test_clients.py
│   ├── test_formatting.py
│   ├── test_models.py
│   └── test_notifier.py
├── backup_original/              # Cópia intacta do protótipo v1 (09/07/2025)
├── .env.example                  # Modelo de variáveis de ambiente
├── .gitignore                    # Regras de exclusão de chaves e dados locais
├── requirements.txt              # Dependências Python
├── run.py                        # Ponto de entrada CLI
└── README.md
```

---

## 🛠️ Instalação e Configuração

### 1. Clonar o Repositório
```bash
git clone https://github.com/EliLyn/TradBotGems.git
cd TradBotGems/core
```

### 2. Criar Ambiente Virtual e Instalar Dependências
```bash
python -m venv venv

# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

pip install -r requirements.txt
```

### 3. Configurar o `.env`
Copie o modelo de configuração:
```bash
cp .env.example .env
```

Edite o arquivo `.env` com suas credenciais:
```ini
TELEGRAM_BOT_TOKEN=seu_token_aqui
TELEGRAM_CHAT_ID=seu_chat_id_aqui

# Opcional (apenas se quiser derivativos da CoinGlass):
COINGLASS_API_KEY=sua_chave_aqui

# Filtros de Market Cap:
MIN_MARKET_CAP_USD=20000
MAX_MARKET_CAP_USD=10000000
COLLECTION_INTERVAL_SECONDS=600
```

---

## 🚀 Como Usar

### Teste de Conexão Rápido (1 ciclo com 3 tokens)
```bash
python run.py --test
```

### Executar Caçador de Gems Contínuo
```bash
python run.py --mode gems
```

### Executar Monitor de Pares DEX
```bash
python run.py --mode dex
```

### Ajuda e Parâmetros
```bash
python run.py --help
```

---

## 🧪 Testes Unitários

Todos os módulos possuem testes automatizados com `unittest`:

```bash
python -m unittest discover -s tests -v
```

Resultado esperado:
```
Ran 19 tests in 0.005s
OK
```

---

## ⚠️ Limitações e Transparência

Para manter a clareza técnica sobre o escopo do projeto:

- **APIs Gratuitas:** A versão padrão utiliza endpoints públicos da CoinGecko e DexScreener, que possuem limites de taxa (*rate limits*). O bot possui pausas entre requisições para mitigar bloqueios.
- **Tokens Sem Futuros:** A grande maioria das micro-caps não possui mercado de derivativos na CoinGlass; nesses casos, os campos de derivativos são exibidos como `N/A`, o que é o comportamento esperado.
- **Finalidade:** Este software é um experimento educacional de monitoramento e automação de dados públicos, não constituindo ferramenta de recomendação financeira ou execução automática de ordens.

---

## 📄 Licença

Este projeto é disponibilizado sob a licença [MIT](LICENSE).

<div align="center">

*Concepção e evolução com auxílio de IA por [EliLyn](https://github.com/EliLyn).*

</div>
