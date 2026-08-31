# 💎 TradBotGems

<div align="center">

[![Python Version](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![License: GPL-3.0](https://img.shields.io/badge/License-GPL--3.0-blue.svg?style=flat-square)](https://www.gnu.org/licenses/gpl-3.0)
[![Telegram](https://img.shields.io/badge/Telegram-Alertas-2CA5E0?style=flat-square&logo=telegram&logoColor=white)](https://telegram.org/)
[![Tests](https://img.shields.io/badge/Testes-19%20Passando-success?style=flat-square)](tests/)

**Bot em Python para filtrar criptomoedas de baixa capitalização (micro-caps), consultar derivativos na CoinGlass e enviar resumos no Telegram.**

[Sobre o Projeto](#-sobre-o-projeto) •
[A Evolução do Código](#-a-evolução-do-código) •
[Como Funciona](#-como-funciona) •
[Instalação](#-instalação-e-uso) •
[Aviso Legal](#-aviso-legal-disclaimer) •
[Testes](#-testes)

</div>

---

## 📌 Sobre o Projeto

Não sou programador de formação. Criei este projeto porque queria automatizar minha rotina de garimpar tokens pequenos no mercado cripto sem ter que passar horas olhando telas manualmente.

Uso Inteligência Artificial no meu dia a dia como ferramenta para transformar minhas ideias em código: pesquiso o que preciso, discuto a lógica, peço revisões e vou ajustando o projeto aos poucos. 

Este repositório mostra essa evolução prática.

---

## 📈 A Evolução do Código

| Aspecto | v1 (Julho/2025) | v2 (Hoje) |
| :--- | :--- | :--- |
| **Estrutura** | Script único de ~800 linhas | Separado em módulos (`clients`, `services`, `models`) |
| **Funções** | Blocos longos e misturados | Funções diretas de no máximo 25 linhas |
| **Chaves de API** | Gravadas direto no script | Guardadas em arquivo `.env` seguro (fora do Git) |
| **Fontes** | CoinGecko + CoinGlass | CoinGecko, CoinGlass, DexScreener e exploradores EVM |
| **Testes** | Nenhum teste | 19 testes unitários automatizados |
| **Uso** | Executava de um jeito só | Opções no terminal (`--mode gems`, `--mode dex`, `--test`) |

---

## ⚙️ Como Funciona

1. **Varredura (CoinGecko):** O bot busca moedas na faixa de valor de mercado configurada (ex: \$20 mil a \$10 milhões).
2. **Derivativos (CoinGlass):** Se o token tiver mercado de futuros, ele pega dados de Open Interest, taxa de financiamento e liquidações. Se não tiver, marca como `N/A`.
3. **Filtros e Categorias:** Identifica categorias de interesse (como IA, RWA, Gaming e ecossistema BTC).
4. **Alerta no Telegram:** Envia uma mensagem formatada com preço, links oficiais, redes sociais e contrato da moeda.

---

## 📁 Estrutura das Pastas

```
core/
├── tradbot/                      # Código principal do bot
│   ├── config.py                 # Configurações e leitura do .env
│   ├── models.py                 # Estrutura dos dados
│   ├── clients/                  # Conexão com as APIs (CoinGecko, CoinGlass, DEX)
│   ├── services/                 # Lógica de análise, cache e envio do Telegram
│   └── utils/                    # Funções de texto e logs
├── tests/                        # 19 testes automatizados
├── backup_original/              # Cópia do primeiro script antigo (preservado)
├── .env.example                  # Modelo de configuração
├── requirements.txt              # Bibliotecas necessárias
├── run.py                        # Arquivo para iniciar o bot
└── README.md
```

---

## 🚀 Instalação e Uso

### 1. Instalar dependências
```bash
git clone https://github.com/EliLyn/TradBotgems.git
cd TradBotgems/core

python -m venv venv
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

pip install -r requirements.txt
```

### 2. Configurar suas chaves
Copie o arquivo `.env.example` para `.env`:
```bash
cp .env.example .env
```
Coloque o Token do seu bot do Telegram e o seu Chat ID dentro do `.env`.

### 3. Rodar
```bash
# Teste rápido (1 ciclo curto):
python run.py --test

# Rodar o bot de gems:
python run.py --mode gems

# Rodar o monitor de DEX:
python run.py --mode dex
```

---

## ⚠️ Aviso Legal (Disclaimer)

- **Sem Recomendação Financeira:** Este software é um projeto experimental e educacional de automação de dados públicos. Nenhuma informação, alerta ou nota gerada por este robô constitui conselho de investimento, recomendação de compra ou venda de ativos financeiros.
- **Risco do Mercado:** O mercado de criptomoedas — especialmente moedas de baixa liquidez e micro-capitalização — envolve alto risco de perda total do capital investido.
- **Responsabilidade do Usuário:** O autor não se responsabiliza por quaisquer decisões financeiras, lucros ou perdas decorrentes do uso direto ou indireto deste código. Qualquer pessoa que utilize este software o faz por sua própria conta e risco.

---

## 🧪 Testes

Para rodar os testes automatizados:

```bash
python -m unittest discover -s tests -v
```

---

## 📄 Licença

Distribuído sob a licença **GNU General Public License v3.0 (GPLv3)** - veja o arquivo [LICENSE](LICENSE) para detalhes.

<div align="center">

Criado por **[EliLyn](https://github.com/EliLyn)** com auxílio de IA.

</div>
