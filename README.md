# 💎 TradBotGems v2.0 - Crypto Gem Hunter & Market Intelligence Bot

<div align="center">

[![Python Version](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge)](https://opensource.org/licenses/MIT)
[![Telegram](https://img.shields.io/badge/Telegram-Bot%20Alerts-2CA5E0?style=for-the-badge&logo=telegram&logoColor=white)](https://telegram.org/)
[![AsyncIO](https://img.shields.io/badge/AsyncIO-Fast%20%26%20Non--blocking-4B8BBE?style=for-the-badge&logo=fastapi&logoColor=white)](https://docs.python.org/3/library/asyncio.html)
[![Open Source](https://img.shields.io/badge/Open%20Source-%E2%9D%A4-red?style=for-the-badge)](https://github.com/EliLyn)

**Bot assíncrono e modular em Python para descoberta de Micro-Cap Gems, análise de Derivativos (CoinGlass), monitoramento em tempo real de DEXs e alertas avançados no Telegram.**

[Funcionalidades](#-funcionalidades) •
[Arquitetura](#-arquitetura) •
[Exemplos de Alertas](#-exemplos-de-alertas-no-telegram) •
[Instalação](#-instalação-passo-a-passo) •
[Configuração](#-configuração-de-variáveis-env) •
[Como Executar](#-como-executar) •
[Segurança](#-segurança-e-boas-práticas)

</div>

---

## 🌟 Visão Geral

O **TradBotGems** é uma plataforma automatizada de inteligência quantitativa e fundamentalista para o mercado de criptoativos. O bot rastreia milhares de tokens, identifica projetos em estágios iniciais com alto potencial assimétrico de valorização (*Gems*), cruza dados com o mercado de futuros e derivativos, avalia a liquidez em exchanges descentralizadas e entrega análises detalhadas no seu Telegram em tempo real.

---

## 🚀 Funcionalidades

### 1. 🔍 Rastreador de Micro & Small-Cap Gems (CoinGecko)
- **Varredura Dinâmica por Market Cap:** Filtra tokens em faixas configuráveis (ex: $20.000 a $10.000.000) buscando oportunidades ocultas antes da listagem em grandes CEXs.
- **Cache Local Inteligente:** Sistema de cache assíncrono com TTL para economizar limites de requisição e operar mesmo com conexões instáveis.
- **Resiliência contra Rate Limit (HTTP 429):** Retries automáticos com backoff exponencial.

### 2. 📊 Métricas Avançadas de Derivativos (CoinGlass)
- **Open Interest (OI):** Acompanha o volume de contratos em aberto e variações de interesse institucional.
- **Taxa de Financiamento (Funding Rate):** Identifica sentimento de mercado (sobrecomprado / sobrevendido).
- **Long/Short Ratio:** Proporção de posições compradas versus vendidas.
- **Liquidações em 24h:** Volume total de liquidações de longs e shorts em USD.

### 3. 🦄 Monitor DEX em Tempo Real (DexScreener & On-Chain)
- **Multi-Chain:** Suporte a Ethereum, BNB Chain, Polygon, Arbitrum, Optimism, Base e Avalanche.
- **Detecção de Novos Pares de Liquidez:** Identificação precoce de novas pools com liquidez e volume relevantes.
- **🛡️ Verificação de Risco / Honeypot:** Checagem preventiva contra golpes de tokens não-vendíveis.

### 4. 🧠 Motor de Classificação & Scoring Fundamentalista
- **Identificação de Narrativas Quentes:** Pontuação extra para **RWA (Real World Assets)**, **Inteligência Artificial (IA)**, **Ecossistema Bitcoin / Ordinals / BRC-20** e **Web3 Gaming**.
- **Análise de Velocidade de Transações (12h vs 24h):** Alertas especiais de aceleração repentina de atividade na rede.

---

## 📱 Exemplos de Alertas no Telegram

### 💎 Cartão de Análise Completa de Token
```markdown
💎 TNT - Titan Token
🗓️ 2026-08-31 21:00 UTC
📊 Capitalização de Mercado: $178,581.00
💲 Preço: $0.001785
⬆️ Var. 24h: -13.79%
⬆️ Var. 7d: -14.10%
💰 Volume 24h (Spot): $2,909.62
📈 Transações (12h): 142
📉 Transações (24h): 215
📝 Potencial: Potencial Alto (100k - 1M), Atividade Crescente, 🤖 IA
📦 Fornecimento Total: 100,000,000 (cem milhões)
📦 Fornecimento em Circulação: 100,000,000 (cem milhões)
🏷️ Categoria: Artificial Intelligence, Web3
⛓️ Blockchain: Ethereum
📄 Contrato: 0x1234...5678

*Dados de Derivativos (CoinGlass)*:
📊 Open Interest: $450,200
📈 Funding Rate: +0.0100%
🔄 Long/Short Ratio: 1.25
🔻 Liquidação Long (24h): $12,400
🔺 Liquidação Short (24h): $3,100
💰 Volume Futuros (24h): $1,250,000

*Sobre o Token*:
Protocolo descentralizado focado em agentes autônomos de IA...

*Redes Sociais*:
🌐 Site: https://exemplo.org
🐦 Twitter: @ProjetoOficial (Seguidores: 24,500)
✈️ Telegram: https://t.me/ProjetoOficial (Membros: 8,300)

*ALERTAS*:
🔥 TNT - Alta Atividade Recente!
✨ Token de Baixo Capital de Mercado - Fique de Olho!
```

---

## 🏛️ Arquitetura

```
┌──────────────────────────────────────────────────────────┐
│                   Provedores de Dados                    │
│  [CoinGecko API]  [CoinGlass API]  [DexScreener]  [EVM]  │
└────────────┬──────────────┬──────────────┬───────────┬───┘
             │              │              │           │
┌────────────▼──────────────▼──────────────▼───────────▼───┐
│              Camada de Clientes HTTP (Async)             │
│        (Rate limiting, Backoff, Resiliência e Cache)     │
└────────────────────────────┬─────────────────────────────┘
                             │
┌────────────────────────────▼─────────────────────────────┐
│                 Motor de Negócio & Scoring               │
│  • TokenAnalyzer (RWA, IA, BTC, Supply, Faixas de MCAP)   │
│  • DexMonitor (Volume, Liquidez, Honeypot Check)         │
│  • CacheManager (Persistência assíncrona com TTL)        │
└────────────────────────────┬─────────────────────────────┘
                             │
┌────────────────────────────▼─────────────────────────────┐
│                Telegram Notifier Service                 │
│      (Formatação MarkdownV2 segura e envio de cards)     │
└──────────────────────────────────────────────────────────┘
```

---

## 📦 Estrutura de Diretórios

```
core/
├── tradbot/                      # Pacote principal modular
│   ├── __init__.py
│   ├── config.py                 # Configurações com suporte a .env
│   ├── models.py                 # Dataclasses tipadas
│   ├── clients/                  # Clientes de APIs externas
│   │   ├── base.py               # Cliente HTTP com retry e timeout
│   │   ├── coingecko.py          # API CoinGecko
│   │   ├── coinglass.py          # API CoinGlass (Derivativos)
│   │   ├── dexscreener.py        # API DexScreener (DEX pairs)
│   │   ├── evm_explorer.py       # Etherscan, BscScan, PolygonScan
│   │   └── honeypot.py           # Verificação de segurança on-chain
│   ├── services/                 # Regras de negócio
│   │   ├── analyzer.py           # Algoritmo de classificação de Gems
│   │   ├── notifier.py           # Notificações ricas no Telegram
│   │   ├── cache.py              # Cache em disco com controle de validade
│   │   ├── collector.py          # Loop principal de coleta e análise
│   │   └── dex_monitor.py        # Monitor de pares descentralizados
│   └── utils/                    # Funções utilitárias
│       ├── formatting.py         # Escape MarkdownV2 e números por extenso
│       └── logger.py             # Logs coloridos no terminal e arquivo
├── tests/                        # Testes unitários automatizados
│   ├── test_formatting.py
│   └── test_analyzer.py
├── .env.example                  # Template seguro de credenciais
├── .gitignore                    # Regras de segurança de repositório
├── requirements.txt              # Dependências Python
├── run.py                        # Ponto de entrada CLI amigável
├── LICENSE                       # Licença MIT
└── README.md                     # Documentação completa
```

---

## 🛠️ Instalação Passo a Passo

### 1. Requisitos Prévios
- Python **3.10** ou superior instalado ([python.org](https://www.python.org/))
- Git instalado ([git-scm.com](https://git-scm.com/))

### 2. Clonar o Repositório
```bash
git clone https://github.com/EliLyn/TradBotGems.git
cd TradBotGems/core
```

### 3. Criar e Ativar Ambiente Virtual
```bash
# Windows (PowerShell):
python -m venv venv
venv\Scripts\activate

# Linux / MacOS:
python3 -m venv venv
source venv/bin/activate
```

### 4. Instalar as Dependências
```bash
pip install -r requirements.txt
```

---

## 🔑 Configuração de Variáveis (.env)

Copie o arquivo de exemplo para criar seu arquivo de configurações:

```bash
# Windows:
copy .env.example .env

# Linux / MacOS:
cp .env.example .env
```

Abra o arquivo `.env` e configure suas variáveis:

| Variável | Obrigatório | Descrição |
| :--- | :---: | :--- |
| `TELEGRAM_BOT_TOKEN` | **Sim** | Token do seu bot criado via [@BotFather](https://t.me/BotFather) |
| `TELEGRAM_CHAT_ID` | **Sim** | Seu Chat ID numérico obtido via [@userinfobot](https://t.me/userinfobot) ou ID de canal/grupo |
| `COINGLASS_API_KEY` | *Opcional* | Chave de API da [CoinGlass](https://open-api.coinglass.com/) para dados de derivativos |
| `ETHERSCAN_API_KEY` | *Opcional* | Chave da API [Etherscan](https://etherscan.io/) para métricas on-chain |
| `MIN_MARKET_CAP_USD` | Não | Limite mínimo de Market Cap para filtros (Padrão: `20000`) |
| `MAX_MARKET_CAP_USD` | Não | Limite máximo de Market Cap para filtros (Padrão: `10000000`) |
| `COLLECTION_INTERVAL_SECONDS` | Não | Intervalo entre ciclos completos em segundos (Padrão: `600` = 10 min) |

> 💡 **Como criar seu bot no Telegram em 1 minuto:**
> 1. Abra o Telegram e procure por `@BotFather`.
> 2. Envie `/newbot`, escolha um nome e um username para o bot.
> 3. Copie o **Token HTTP API** gerado e cole em `TELEGRAM_BOT_TOKEN`.
> 4. Inicie uma conversa com seu novo bot clicando em `/start`.
> 5. Abra o `@userinfobot`, envie qualquer mensagem e copie o seu `Id` para colar em `TELEGRAM_CHAT_ID`.

---

## 🚀 Como Executar

### Teste Rápido de Conectividade
Valida a conexão com as APIs e formatação enviando um ciclo com apenas 3 tokens:
```bash
python run.py --test
```

### Modo Caçador de Gems 24/7 (Padrão)
Executa a varredura contínua de micro e small-caps na CoinGecko com derivativos da CoinGlass:
```bash
python run.py --mode gems
```

### Modo Monitor de DEX em Tempo Real
Acompanha criação de pares de alta liquidez e volume nas principais DEXs:
```bash
python run.py --mode dex
```

### Modo Completo (Gems + DEX)
Executa ambos os serviços simultaneamente em tarefas assíncronas concorrentes:
```bash
python run.py --mode all
```

### Opções de Linha de Comando (CLI)
```bash
python run.py --help

Opções:
  -h, --help            Exibe a mensagem de ajuda
  --mode {gems,dex,all} Define o modo de operação (Padrão: gems)
  --test                Executa um ciclo curto de teste
  --max-tokens N        Limita o número de tokens analisados no ciclo
  --log-level {DEBUG,INFO,WARNING,ERROR}
                        Ajusta a verbosidade do terminal e arquivo
```

---

## 🧪 Testes Automatizados

O projeto inclui testes unitários para validar a lógica de pontuação, filtros e formatação segura de mensagens:

```bash
python -m unittest discover -s tests
```

---

## 🛡️ Segurança e Boas Práticas

- **Proteção de Credenciais:** Suas chaves de API e tokens nunca são enviados ao repositório público graças ao `.gitignore` configurado.
- **Código Seguro:** Validação de tipos com Dataclasses e tratamento defensivo de exceções de rede e serialização JSON.
- **Transparência:** Código 100% aberto e auditável.

---

## 🤝 Contribuindo

Contribuições são muito bem-vindas! Sinta-se à vontade para abrir uma *Issue* ou enviar um *Pull Request*:

1. Faça um Fork do projeto
2. Crie uma Branch para sua Feature (`git checkout -b feature/NovaFuncionalidade`)
3. Faça o Commit das suas mudanças (`git commit -m 'feat: Adiciona nova funcionalidade'`)
4. Faça o Push para a Branch (`git push origin feature/NovaFuncionalidade`)
5. Abra um Pull Request

---

## 📄 Licença

Este projeto está sob a licença **MIT** - veja o arquivo [LICENSE](LICENSE) para detalhes.

---

<div align="center">

Desenvolvido com ☕ e paixão por cripto por **[EliLyn](https://github.com/EliLyn)**.

*Se este projeto te ajudou, deixe uma ⭐ no repositório!*

</div>
