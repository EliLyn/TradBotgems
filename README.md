# 💎 TradBotGems — Minha Jornada de Construção com Inteligência Artificial

<div align="center">

[![Python Version](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=flat-square)](https://opensource.org/licenses/MIT)
[![Telegram](https://img.shields.io/badge/Telegram-Alerts-2CA5E0?style=flat-square&logo=telegram&logoColor=white)](https://telegram.org/)
[![Tests](https://img.shields.io/badge/Tests-19%20Passing-success?style=flat-square)](tests/)
[![AI Powered](https://img.shields.io/badge/Desenvolvido%20com-IA-blueviolet?style=flat-square)](https://github.com/EliLyn)

**Do primeiro protótipo monolítico à arquitetura modular: o registro real de como concebo, pesquiso e construo soluções utilizando Inteligência Artificial como parceira de desenvolvimento.**

[Sobre Mim e o Projeto](#-sobre-mim-e-este-projeto) •
[A Origem: O Primeiro Robô](#-a-origem-o-primeiro-experimento-julho2025) •
[O que Aprendi no Caminho](#-o-que-aprendi-no-caminho) •
[A Transformação (v1 vs v2)](#-a-transformação-v1-vs-v2) •
[Como Funciona](#-como-o-bot-funciona-hoje) •
[Instalação e Uso](#-como-executar) •
[Minha Filosofia](#-minha-filosofia)

</div>

---

## 👤 Sobre Mim e Este Projeto

**Eu não sou um programador tradicional.** 

Eu sou alguém que tem ideias de produtos, pesquisa a fundo as regras de negócio e informações de mercado necessárias, e utiliza **Inteligência Artificial como ferramenta ativa de desenvolvimento**, discutindo, questionando e aprimorando cada etapa continuamente.

O **TradBotGems** é o reflexo direto dessa jornada: a transição de um primeiro experimento prático para uma estrutura de software profissional, modular, segura e testada.

---

## 🌱 A Origem: O Primeiro Experimento (Julho/2025)

A ideia nasceu de uma dor real: analisar e garimpar manualmente milhares de criptomoedas em estágio inicial (*micro e small-caps*, conhecidas como *"Gems"*) consome muito tempo. Eu precisava de um robô que monitorasse o mercado 24/7 e me alertasse no **Telegram** quando encontrasse tokens com potencial e volume relevantes.

Em 09/07/2025, nasceu o primeiro robô:
- Um script único de quase 800 linhas (**monolítico**).
- Funcionava e enviava mensagens, mas tinha chaves de API colocadas diretamente no código.
- Tinha simulações randômicas de transações para testar os layouts visuais.
- Não possuía testes automatizados nem separação em arquivos menores.

Foi o protótipo que provou que a ideia era viável e me deu a base para buscar mais conhecimento.

---

## 🧠 O que Aprendi no Caminho

Conforme fui estudando, buscando informações e discutindo novas arquiteturas com a IA, entendi que fazer um software robusto vai muito além de apenas "fazer rodar":

1. **Segurança em primeiro lugar:** Chaves de API e tokens nunca devem ser expostos em código público; o uso de `.env` e `.gitignore` é obrigatório.
2. **Modularidade e Clareza:** Dividir o código em camadas (`clients`, `services`, `models`, `utils`) torna o sistema fácil de entender, debugar e manter.
3. **Funções Enxutas:** Limitar cada função a no máximo 25 linhas força o código a ser direto, evitando bugs escondidos.
4. **Testes Automatizados:** Testes unitários trazem a certeza de que cada cálculo e formatação funciona como esperado.
5. **Auditoria Contínua:** Não aceitar respostas cegas da IA — é preciso auditar, testar no terminal e exigir consistência em cada detalhe.

---

## 📊 A Transformação: v1 vs v2

| Aspecto | v1.0 — Primeiro Experimento (Jul/2025) | v2.0 — Versão Atual Modular (Ago/2026) |
| :--- | :--- | :--- |
| **Abordagem** | Script monolítico único (~800 linhas) | Pacote modular (`tradbot/`) dividido em responsabilidades |
| **Tamanho de Funções** | Funções longas misturando rede e regras | **Todas as funções têm no máximo 25 linhas** |
| **Segurança** | Chaves e tokens gravados no script | Isolamento total em `.env` (bloqueado no `.gitignore`) |
| **Fontes de Dados** | CoinGecko + endpoints básicos da CoinGlass | Clientes desacoplados: CoinGecko, CoinGlass, DexScreener e EVM |
| **Resiliência de Rede** | Requisições sem tratamento específico | Tratamento de rate limit, DNS IPv4 e fallback de cache local |
| **Alertas Telegram** | Envio com formatação básica | Cartões ricos em MarkdownV2 com tratamento de tamanho |
| **Testes** | Nenhum teste automatizado | **19 testes unitários** com `unittest` (100% de aprovação) |
| **Interface** | Loop único sem opções de linha de comando | CLI com modos (`--mode gems`, `--mode dex`, `--test`) |

---

## ⚙️ Como o Bot Funciona Hoje

```
┌────────────────────────────────────────────────────────┐
│ 1. Varredura de Mercado (CoinGecko Client)            │
│    Filtra tokens por faixas de valor de mercado       │
└──────────────────────────┬─────────────────────────────┘
                           │
┌──────────────────────────▼─────────────────────────────┐
│ 2. Derivativos & Futuros (CoinGlass Client)            │
│    Busca Open Interest, Funding Rate e Liquidações    │
└──────────────────────────┬─────────────────────────────┘
                           │
┌──────────────────────────▼─────────────────────────────┐
│ 3. Motor de Análise (TokenAnalyzer Service)            │
│    Avalia categorias (IA, RWA, Gaming, BTC) e volume  │
└──────────────────────────┬─────────────────────────────┘
                           │
┌──────────────────────────▼─────────────────────────────┐
│ 4. Notificador (TelegramNotifier Service)              │
│    Formata o card em MarkdownV2 e envia no Telegram    │
└────────────────────────────────────────────────────────┘
```

---

## 📁 Estrutura do Projeto

```
core/
├── tradbot/                      # Pacote principal modular
│   ├── config.py                 # Leitura de variáveis .env
│   ├── models.py                 # Dataclasses tipadas
│   ├── clients/                  # Clientes HTTP assíncronos (<= 25 linhas)
│   │   ├── base.py               # Cliente base com retry e IPv4
│   │   ├── coingecko.py          # Integração CoinGecko
│   │   ├── coinglass.py          # Integração CoinGlass (Derivativos)
│   │   ├── dexscreener.py        # Integração DexScreener
│   │   ├── evm_explorer.py       # Exploradores EVM
│   │   └── honeypot.py           # Consulta à API Honeypot.is
│   ├── services/                 # Regras de negócio (<= 25 linhas)
│   │   ├── analyzer.py           # Algoritmo de classificação e notas
│   │   ├── notifier.py           # Formatação e envio Telegram
│   │   ├── cache.py              # Cache local com TTL
│   │   ├── collector.py          # Orquestrador do ciclo 24/7
│   │   └── dex_monitor.py        # Monitor de pares em DEX
│   └── utils/                    # Utilitários auxiliares (<= 25 linhas)
│       ├── formatting.py         # Escape MarkdownV2 e números por extenso
│       └── logger.py             # Configuração de logs com suporte a UTF-8
├── tests/                        # 19 Testes unitários automatizados
├── backup_original/              # Cópia preservada do protótipo v1 (Jul/2025)
├── .env.example                  # Template seguro de credenciais
├── .gitignore                    # Bloqueio de chaves e dados locais
├── requirements.txt              # Dependências do projeto
├── run.py                        # Ponto de entrada CLI
└── README.md
```

---

## 🚀 Como Executar

### 1. Instalação
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

### 2. Configuração do `.env`
Copie o `.env.example`:
```bash
cp .env.example .env
```
Preencha suas credenciais no `.env`:
```ini
TELEGRAM_BOT_TOKEN=seu_token_aqui
TELEGRAM_CHAT_ID=seu_chat_id_aqui
COINGLASS_API_KEY=sua_chave_opcional
```

### 3. Execução
```bash
# Teste rápido (1 ciclo com 3 tokens):
python run.py --test

# Modo Caçador de Gems 24/7:
python run.py --mode gems

# Modo Monitor de DEX:
python run.py --mode dex
```

### 4. Executar os Testes Unitários
```bash
python -m unittest discover -s tests -v
```

---

## 🌟 Minha Filosofia

> *"Não sou programador. Uso IA para desenvolver, busco as informações de que preciso e discuto melhorias continuamente."*

Este repositório é a prova de que, com curiosidade, dedicação, busca de informações e o uso consciente da IA como copiloto, qualquer pessoa pode conceber uma ideia, construir um primeiro protótipo e evoluí-lo até um projeto de nível profissional.

---

## 📄 Licença

Distribuído sob a licença [MIT](LICENSE).

<div align="center">

Desenvolvido por **[EliLyn](https://github.com/EliLyn)**.

</div>
