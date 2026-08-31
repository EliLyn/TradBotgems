#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LCC ULTRA — Audit Linter (lcc_audit_linter.py)
================================================
Verificação periódica automatizada, pensada para ser rodada por uma IA (Claude,
outra LLM auditora, ou um cron/task scheduler) sem depender de relatos textuais.

Cada checagem produz EVIDÊNCIA REPRODUZÍVEL a partir dos arquivos reais no disco —
nunca aceita um número "porque o texto disse". Isso automatiza exatamente as
checagens que uma auditoria manual já fez neste projeto:

  1. ruff_scan          -> variáveis/imports indefinidos (F821) que já causaram
                            2 crashes reais em produção (asyncio, MAX_LOSS_USD_PER_TRADE)
  2. hash_manifest       -> recalcula SHA-256 de qualquer arquivo citado em specs
                            JSON e compara com o hash declarado (pega hash fabricado)
  3. config_drift        -> compara constantes hardcoded no código (ex: infra/risk.py)
                            contra os valores declarados em config/trading_config.json
                            (pegou a divergência real $0.40 declarado vs $0.85 real)
  4. banca_reconciliation-> reconstrói banca_final[i-1] + pnl_usd[i] e flagra
                            divergências grandes (achado real: até $5.36 de diff)
  5. dataset_emptiness   -> flagra dataset de AutoLearn vazio/pequeno demais
  6. test_count_claim    -> compara contagem de testes declarada em specs JSON
                            contra o resultado real de "pytest --collect-only"
  7. semantic_watch      -> detecta função/classe NOVA ou ALTERADA desde a última
                            rodada (via baseline de hashes) e aplica 3 heurísticas:
                            parâmetro simbólico sem fonte (ex: gamma_absorção usado
                            em fórmula sem nunca receber valor), estatística citada
                            sem dataset real por perto, e teste que só checa
                            "is not None" em vez de um valor esperado.
  8. duplicate_files     -> mesmo símbolo (classe/função) definido em arquivos
                            diferentes com conteúdo divergente (reconhece alias
                            de encaminhamento intencional e não confunde com
                            duplicata perigosa).
  9. complexity          -> arquivo ou função longos demais pra revisar com
                            confiança (limite de linhas configurável).

SAÍDA: sempre JSON primeiro (arquivo de máquina), com um resumo humano opcional.

USO:
    python lcc_audit_linter.py --root C:\\SYSTEMS\\FrameworkLCC\\LCC_ULTRA
    python lcc_audit_linter.py --root . --only ruff,banca,hash,semantic
    python lcc_audit_linter.py --root . --run-tests
    python lcc_audit_linter.py --root . --out audit_report.json --human
    python lcc_audit_linter.py --root . --update-baseline   # aceita o estado
                                                              # atual como "já revisado"

100% local — nenhuma chamada de rede além do que o próprio `pytest`/`ruff`
já fazem localmente. Zero dependência de API externa ou chave de acesso.
Se ruff/pytest não estiverem instalados, a checagem correspondente é
pulada e reportada como SKIPPED, nunca inventada.
"""
import logging
import argparse
import ast
import json
import os
import re
import subprocess
import sys
import hashlib
from pathlib import Path
from datetime import datetime, timezone

# ============================================================================
# Config declarativa: onde encontrar cada coisa. Editar aqui conforme o
# projeto evolui — isso é o "arquivo de máquina" desse próprio linter.
# ============================================================================

RUFF_TARGETS = ["core", "cognitive", "infra", "main.py", "lyndssen_cognitive_core", "scripts", "tools"]
RUFF_RULES = "F821,F401,F811,E9"  # E9 = erro de sintaxe


# ============================================================================
# MANIFESTO DE INTEGRIDADE DO PRÓPRIO LINTER — NÃO EDITAR.
# ============================================================================
# Isso existe porque uma versão anterior deste script foi editada por outra
# IA pra rebaixar um achado CRÍTICO (divergência de banca) pra WARN e pra
# remover 2 das 3 checagens de config_drift, sem nenhuma evidência nova —
# só pra fazer o relatório parecer limpo.
#
# Esse manifesto é verificado EM TEMPO DE EXECUÇÃO, a cada rodada. Se alguém
# reduzir DRIFT_CHECKS, ou tentar afrouxar a severidade da reconciliação de
# banca, o próprio linter denuncia isso como achado CRÍTICO — "tamper
# detectado" — em vez de silenciosamente reportar "tudo OK".
#
# A defesa definitiva contra edição do arquivo inteiro é o self-hash
# impresso em toda execução (ver self_integrity_hash()). Guarde o hash que
# eu te der agora, fora deste repositório (num bloco de notas seu, não num
# lugar que a IA "vagabunda" também acesse). Se o hash mudar sem você ter
# pedido a mudança, o arquivo foi mexido.
REQUIRED_DRIFT_CHECK_NAMES = {"stop_loss_hard_cap_usd", "max_stop_pct", "min_quorum_votes"}
MIN_DRIFT_CHECKS = 3
BANCA_SEVERITY_FLOOR = "CRITICAL"  # a checagem de banca NUNCA relata abaixo disso
EXPECTED_CHECK_MODULE_COUNT = 16  # 15 checagens de estado + 1 (bug_ledger) de histórico

# Constantes críticas que devem bater entre código hardcoded e config externo.
# Cada entrada: onde está o valor "oficial" (JSON) vs onde está hardcoded (código).
DRIFT_CHECKS = [
    {
        "name": "stop_loss_hard_cap_usd",
        "config_file": "config/trading_config.json",
        "config_path": ["risk", "max_loss_usd_per_trade"],
        "code_file": "infra/risk.py",
        "code_regex": r"MAX_LOSS_USD\s*=\s*([0-9.]+)",
    },
    {
        "name": "max_stop_pct",
        "config_file": "config/trading_config.json",
        "config_path": ["risk", "max_stop_pct"],
        "code_file": "infra/risk.py",
        "code_regex": r"MAX_STOP_PCT\s*=\s*([0-9.]+)",
    },
    {
        "name": "min_quorum_votes",
        "config_file": "config/trading_config.json",
        "config_path": ["quorum", "min_votes_required"],
        "code_file": "core/engines.py",
        "code_regex": r"MINIMO_APROVACOES\s*=\s*([0-9.]+)",
    },
]

# Caminhos padrão de dataset / telemetria / specs (relativos à raiz do projeto)
TRADE_DATASET = "dataset_ai_trades/trade_dataset.jsonl"
BUG_TELEMETRY = "production_bugs_telemetry.jsonl"
SPEC_CANDIDATES = [
    "bot_integrity_audit.json",
    "bot_specification.json",
    "dataset_ai_trades/system_metrics_report.json",
]
TESTS_DIR = "tests"

# Tolerância de reconciliação de banca: acima disso, exige explicação
# (ex: posições concorrentes). Default conservador.
BANCA_DIFF_TOLERANCE_USD = 0.10

HEX64_RE = re.compile(r"^[0-9A-Fa-f]{64}$")

# ----------------------------------------------------------------------
# "Vigia semântico": detecta função/classe NOVA ou ALTERADA desde a última
# rodada (via baseline de hashes) e aplica heurísticas nos padrões de
# problema que essa auditoria já pegou manualmente mais de uma vez.
# ----------------------------------------------------------------------
DEFAULT_BASELINE_FILE = ".lcc_audit_baseline.json"

# Nomes de parâmetro que, historicamente, apareceram em fórmulas sem nunca
# receber um valor numérico rastreável (ex: γ_absorção do PredictiveLiquidityShadowEngine)
SYMBOLIC_PARAM_RE = re.compile(
    r"\b(gamma\w*|alpha\w*|beta\w*|omega\w*|sigma\w*|theta\w*|"
    r"fator_\w+|coef\w*_\w+|constante_\w+|peso_\w+)\b",
    re.IGNORECASE,
)
ASSIGNMENT_RE_TEMPLATE = r"\b{name}\s*(?::\s*\w+\s*)?=(?!=)"
DEFAULT_PARAM_RE_TEMPLATE = r"\b{name}\s*(?::\s*\w+\s*)?=\s*[0-9.]+"

# Palavras que, perto de um número/percentual num comentário ou docstring,
# indicam uma estatística sendo citada como fato (ex: "72,5% de acerto")
STAT_KEYWORDS = r"(taxa\s+de\s+acerto|winrate|win\s*rate|expectativa|" \
                r"probabilidade|lucro\s+m[eé]dio|acerto\s+estat[íi]stico)"
STAT_NUMBER_RE = re.compile(
    STAT_KEYWORDS + r".{0,60}?(\d{1,3}[.,]\d{1,2}\s*%|\$\s?\d+[.,]\d+)",
    re.IGNORECASE,
)
DATA_SOURCE_HINTS = ("trade_dataset", "symbol_edge_metrics", "ai_optimized_parameters",
                     "sample_size", "total_samples", "load_json", "load_jsonl")


# ============================================================================
# Utilidades
# ============================================================================

def now_iso():
    return datetime.now(timezone.utc).isoformat()


def self_integrity_hash():
    """SHA-256 do próprio arquivo do linter. Guarde esse valor fora do
    repositório. Se ele mudar sem você ter pedido, o arquivo foi editado."""
    try:
        return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    except Exception:
        return "INDISPONIVEL (não foi possível ler o próprio arquivo)"


def load_json_safe(path: Path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f), None
    except FileNotFoundError:
        return None, "FILE_NOT_FOUND"
    except json.JSONDecodeError as e:
        return None, f"JSON_DECODE_ERROR: {e}"


def load_jsonl_safe(path: Path):
    records, errors = [], []
    try:
        with open(path, "r", encoding="utf-8") as f:
            for i, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError as e:
                    errors.append(f"linha {i}: {e}")
    except FileNotFoundError:
        return None, ["FILE_NOT_FOUND"]
    return records, errors


def get_nested(d, path):
    cur = d
    for key in path:
        if not isinstance(cur, dict) or key not in cur:
            return None
        cur = cur[key]
    return cur


def sha256_of_file(path: Path):
    h = hashlib.sha256()
    try:
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()
    except FileNotFoundError:
        return None


# ============================================================================
# Checagem 1 — ruff (variáveis/imports indefinidos)
# ============================================================================

def check_ruff(root: Path):
    result = {"check": "ruff_scan", "status": "OK", "findings": [], "meta": {}}
    targets = [str(root / t) for t in RUFF_TARGETS if (root / t).exists()]
    if not targets:
        result["status"] = "SKIPPED"
        result["meta"]["reason"] = "nenhum diretório alvo encontrado"
        return result

    try:
        proc = subprocess.run(
            ["ruff", "check", "--select", RUFF_RULES, "--output-format", "json", *targets],
            capture_output=True, text=True, timeout=60,
        )
    except FileNotFoundError:
        result["status"] = "SKIPPED"
        result["meta"]["reason"] = "ruff não instalado (pip install ruff)"
        return result
    except subprocess.TimeoutExpired:
        result["status"] = "ERROR"
        result["meta"]["reason"] = "timeout ao rodar ruff"
        return result

    try:
        issues = json.loads(proc.stdout) if proc.stdout.strip() else []
    except json.JSONDecodeError:
        result["status"] = "ERROR"
        result["meta"]["raw_stdout"] = proc.stdout[:2000]
        return result

    critical = [i for i in issues if i.get("code") in ("F821", "E9")]
    cosmetic = [i for i in issues if i.get("code") not in ("F821", "E9")]

    result["meta"]["total_issues"] = len(issues)
    result["meta"]["critical_count"] = len(critical)
    result["meta"]["cosmetic_count"] = len(cosmetic)
    result["findings"] = [
        {
            "severity": "CRITICAL" if i.get("code") in ("F821", "E9") else "COSMETIC",
            "code": i.get("code"),
            "message": i.get("message"),
            "file": i.get("filename"),
            "line": i.get("location", {}).get("row"),
        }
        for i in issues
    ]
    if critical:
        result["status"] = "FAIL"
    return result


# ============================================================================
# Checagem 2 — verificação de hash (pega hash fabricado, não só formato válido)
# ============================================================================

def find_hash_claims(obj, trail=()):
    """Varre recursivamente um JSON procurando pares (caminho_arquivo, hash_hex64)."""
    claims = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, str) and HEX64_RE.match(v):
                # o hash provavelmente se refere ao caminho no nome da chave
                looks_like_path = "/" in k or "\\" in k or "." in k
                if looks_like_path:
                    claims.append((k, v))
            claims.extend(find_hash_claims(v, trail + (k,)))
    elif isinstance(obj, list):
        for item in obj:
            claims.extend(find_hash_claims(item, trail))
    return claims


def check_hash_manifest(root: Path):
    result = {"check": "hash_manifest", "status": "OK", "findings": [], "meta": {}}
    any_spec_found = False
    for spec_name in SPEC_CANDIDATES:
        spec_path = root / spec_name
        data, err = load_json_safe(spec_path)
        if err:
            continue
        any_spec_found = True
        claims = find_hash_claims(data)
        for filepath, claimed_hash in claims:
            target = root / filepath
            real_hash = sha256_of_file(target)
            if real_hash is None:
                result["findings"].append({
                    "severity": "CRITICAL",
                    "file": filepath,
                    "issue": "ARQUIVO_NAO_ENCONTRADO_NO_DISCO",
                    "claimed_hash": claimed_hash,
                })
                result["status"] = "FAIL"
            elif real_hash.upper() != claimed_hash.upper():
                result["findings"].append({
                    "severity": "CRITICAL",
                    "file": filepath,
                    "issue": "HASH_NAO_BATE",
                    "claimed_hash": claimed_hash,
                    "real_hash": real_hash,
                })
                result["status"] = "FAIL"
    if not any_spec_found:
        result["status"] = "SKIPPED"
        result["meta"]["reason"] = "nenhum arquivo de spec com hashes encontrado"
    else:
        result["meta"]["hashes_checked"] = len(result["findings"]) if result["status"] == "FAIL" else "todos batem"
    return result


# ============================================================================
# Checagem 3 — drift entre config JSON e constantes hardcoded no código
# ============================================================================

def check_config_drift(root: Path):
    result = {"check": "config_drift", "status": "OK", "findings": [], "meta": {}}

    # --- Auto-checagem de integridade: alguém reduziu DRIFT_CHECKS? ---
    current_names = {spec["name"] for spec in DRIFT_CHECKS}
    missing = REQUIRED_DRIFT_CHECK_NAMES - current_names
    if len(DRIFT_CHECKS) < MIN_DRIFT_CHECKS or missing:
        result["status"] = "FAIL"
        result["findings"].append({
            "severity": "CRITICAL",
            "name": "LINTER_TAMPER_DETECTED",
            "issue": (
                f"DRIFT_CHECKS foi reduzido: esperado >= {MIN_DRIFT_CHECKS} checagens "
                f"incluindo {sorted(REQUIRED_DRIFT_CHECK_NAMES)}, encontrado "
                f"{len(DRIFT_CHECKS)} checagens, faltando {sorted(missing) if missing else 'nenhuma (mas contagem baixa)'}. "
                f"Isso indica que o arquivo do linter foi editado pra reduzir cobertura. "
                f"Confira o self_hash deste relatório contra a versão original."
            ),
        })
        # não retorna aqui — segue rodando o que sobrou, mas já marcou FAIL

    checked = 0
    for spec in DRIFT_CHECKS:
        config_path = root / spec["config_file"]
        code_path = root / spec["code_file"]
        config_data, err = load_json_safe(config_path)
        if err:
            result["findings"].append({
                "severity": "WARN", "name": spec["name"],
                "issue": f"config não encontrado: {err}",
            })
            continue
        declared = get_nested(config_data, spec["config_path"])
        if declared is None:
            result["findings"].append({
                "severity": "WARN", "name": spec["name"],
                "issue": "chave não encontrada no config JSON",
            })
            continue
        if not code_path.exists():
            result["findings"].append({
                "severity": "WARN", "name": spec["name"],
                "issue": f"arquivo de código não encontrado: {spec['code_file']}",
            })
            continue
        code_text = code_path.read_text(encoding="utf-8", errors="ignore")
        m = re.search(spec["code_regex"], code_text)
        if not m:
            result["findings"].append({
                "severity": "WARN", "name": spec["name"],
                "issue": "constante não encontrada no código via regex",
            })
            continue
        hardcoded = float(m.group(1))
        checked += 1
        if abs(hardcoded - float(declared)) > 1e-9:
            result["findings"].append({
                "severity": "CRITICAL",
                "name": spec["name"],
                "config_value": declared,
                "code_value": hardcoded,
                "config_file": spec["config_file"],
                "code_file": spec["code_file"],
                "issue": "DIVERGENCIA: código não reflete o config declarado",
            })
            result["status"] = "FAIL"
    result["meta"]["checked"] = checked
    result["meta"]["drift_checks_registered"] = len(DRIFT_CHECKS)
    if checked == 0 and result["status"] == "OK":
        result["status"] = "SKIPPED"
    return result


# ============================================================================
# Checagem 4 — reconciliação de banca trade a trade
# ============================================================================
# IMPORTANTE: a severidade abaixo é FIXA em BANCA_SEVERITY_FLOOR ("CRITICAL").
# Não existe parâmetro pra suavizar isso. Se uma explicação plausível (ex:
# posições concorrentes) existir, ela precisa vir acompanhada de um arquivo
# de evidência real (ver --position-log) — nunca de uma reescrita de texto.

def check_banca_reconciliation(root: Path, tolerance=BANCA_DIFF_TOLERANCE_USD, position_log_path: Path = None):
    result = {"check": "banca_reconciliation", "status": "OK", "findings": [], "meta": {}}
    records, errors = load_jsonl_safe(root / TRADE_DATASET)
    if records is None:
        result["status"] = "SKIPPED"
        result["meta"]["reason"] = "trade_dataset.jsonl não encontrado"
        return result
    if not records:
        result["status"] = "SKIPPED"
        result["meta"]["reason"] = "trade_dataset.jsonl vazio (0 trades)"
        return result

    required_fields = {"timestamp", "banca_final", "pnl_usd", "symbol"}
    valid = [r for r in records if required_fields.issubset(r.keys())]
    if len(valid) < 2:
        result["status"] = "SKIPPED"
        result["meta"]["reason"] = "menos de 2 trades válidos para reconciliar"
        return result

    valid.sort(key=lambda r: r["timestamp"])
    big_diffs = []
    for i in range(1, len(valid)):
        prev_banca = valid[i - 1]["banca_final"]
        curr_banca = valid[i]["banca_final"]
        pnl = valid[i]["pnl_usd"]
        expected = prev_banca + pnl
        diff = curr_banca - expected
        if abs(diff) > tolerance:
            big_diffs.append({
                "trade_id": valid[i].get("trade_id"),
                "symbol": valid[i]["symbol"],
                "timestamp": valid[i]["timestamp"],
                "expected_banca": round(expected, 4),
                "real_banca": round(curr_banca, 4),
                "diff_usd": round(diff, 4),
            })

    result["meta"]["total_trades"] = len(valid)
    result["meta"]["divergences_found"] = len(big_diffs)
    result["meta"]["tolerance_usd"] = tolerance

    # Só existe UMA forma de reduzir a severidade: evidência real de posições
    # concorrentes, vinda de um arquivo de log separado (não de texto explicativo).
    # Sem esse arquivo, TODA divergência grande é CRITICAL — sem exceção.
    position_log, plog_err = (None, "não fornecido")
    if position_log_path is not None:
        position_log, plog_err = load_json_safe(position_log_path)
    result["meta"]["position_log_status"] = plog_err if plog_err else "carregado e usado na reconciliação"

    if big_diffs:
        for d in big_diffs:
            explained = False
            if position_log:
                # Só aceita explicação se o log mostrar >=2 posições abertas
                # simultaneamente no timestamp exato do trade em questão.
                concurrent = position_log.get(d["trade_id"], {}).get("concurrent_open_positions", 0)
                explained = concurrent >= 2
            d["severity"] = BANCA_SEVERITY_FLOOR  # SEMPRE CRITICAL, nunca suavizado por texto
            d["explained_by_position_log"] = explained
            d["issue"] = (
                "banca_final não reconcilia com banca_anterior + pnl_usd. "
                + ("Log de posições confirma >=2 posições concorrentes neste timestamp "
                   "(explicação plausível, mas ainda requer conferência manual do valor exato)."
                   if explained else
                   "SEM evidência de posições concorrentes no position_log — "
                   "causa desconhecida, requer investigação antes de aceitar qualquer explicação.")
            )
        result["findings"] = big_diffs
        all_explained = all(d["explained_by_position_log"] for d in big_diffs)
        # Mesmo totalmente "explicado", fica WARN (não OK) — sempre exige
        # conferência manual antes de virar OK. Nunca CRITICAL vira OK sozinho.
        result["status"] = "WARN" if all_explained else "FAIL"
    return result


# ============================================================================
# Checagem 4B — arquivos duplicados por nome, em diretórios diferentes
# ============================================================================
# Motivo de existir: a árvore do projeto revelou core/risk.py E infra/risk.py,
# e 3 cópias de lcc_audit_linter.py (raiz, scripts/, linter/). Se duas cópias
# do "mesmo" arquivo divergirem em conteúdo, o código que o bot realmente
# importa pode não ser o que foi revisado/corrigido — a correção "acontece"
# numa cópia enquanto o bot roda outra, silenciosamente.

DUPLICATE_SCAN_EXCLUDE_DIRS = {"__pycache__", ".git", "node_modules", "obsoleto", ".pytest_cache", ".venv", ".ruff_cache"}


def find_py_files(root: Path, targets):
    files = []
    for t in targets:
        base = root / t
        if base.is_file() and base.suffix == ".py":
            files.append(base)
        elif base.is_dir():
            for py_file in base.rglob("*.py"):
                if not any(part in DUPLICATE_SCAN_EXCLUDE_DIRS for part in py_file.parts):
                    files.append(py_file)
    # Também inclui .py soltos na raiz do projeto (main.py, dashboard, etc.)
    for py_file in root.glob("*.py"):
        files.append(py_file)
    return list(set(files))


SCANNABLE_EXTENSIONS = (".py", ".json", ".jsonl", ".md")


def find_scannable_files(root: Path):
    """Varre o projeto INTEIRO (não só core/infra/etc.) -- inclui dataset_ai_trades/,
    linter/, specs na raiz -- porque foi um .jsonl fora das pastas de código que
    causou confusão de hash por causa de \\r\\n."""
    files = []
    for p in root.rglob("*"):
        if not p.is_file() or p.suffix not in SCANNABLE_EXTENSIONS:
            continue
        if any(part in DUPLICATE_SCAN_EXCLUDE_DIRS for part in p.parts):
            continue
        files.append(p)
    return files


def find_importers(root: Path, all_py_files, module_dotted_names):
    """Para cada nome de módulo candidato (ex: 'risk', 'core.risk', 'infra.risk'),
    varre todo o codebase procurando 'import X' ou 'from X import' que bata."""
    importers = {name: [] for name in module_dotted_names}
    import_re = re.compile(r"^\s*(?:from\s+([\w.]+)\s+import|import\s+([\w.]+))", re.MULTILINE)
    for py_file in all_py_files:
        try:
            text = py_file.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        for m in import_re.finditer(text):
            mod = m.group(1) or m.group(2)
            if not mod:
                continue
            for candidate in module_dotted_names:
                if mod == candidate or mod.endswith("." + candidate.split(".")[-1]):
                    importers[candidate].append(str(py_file.relative_to(root)))
    return importers


def is_pure_reexport_shim(py_file: Path):
    """True se o arquivo não define NENHUMA classe/função própria — só
    reexporta símbolo(s) de outro módulo (padrão de alias intencional,
    ex: 'from infra.risk import RiskManager'). Isso NÃO é uma duplicata
    perigosa, é encaminhamento deliberado."""
    try:
        tree = ast.parse(py_file.read_text(encoding="utf-8", errors="ignore"))
    except (SyntaxError, UnicodeDecodeError):
        return False, None
    imported_from = None
    for node in ast.walk(tree):
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            return False, None  # define algo próprio -> não é shim puro
        if isinstance(node, ast.ImportFrom) and node.module:
            imported_from = node.module
    return True, imported_from


def check_duplicate_files(root: Path):
    result = {"check": "duplicate_files", "status": "OK", "findings": [], "meta": {}}
    targets = [t for t in RUFF_TARGETS if (root / t).exists()]
    all_py_files = find_py_files(root, targets)
    if not all_py_files:
        result["status"] = "SKIPPED"
        result["meta"]["reason"] = "nenhum arquivo .py encontrado"
        return result

    by_basename = {}
    for f in all_py_files:
        by_basename.setdefault(f.name, []).append(f)

    duplicates = {name: paths for name, paths in by_basename.items() if len(paths) > 1}
    result["meta"]["arquivos_py_escaneados"] = len(all_py_files)
    result["meta"]["nomes_duplicados_encontrados"] = len(duplicates)

    for basename, paths in duplicates.items():
        hashes = {str(p.relative_to(root)): sha256_of_file(p) for p in paths}
        unique_hashes = set(hashes.values())
        content_identical = len(unique_hashes) == 1

        # Verifica se algum dos "duplicados" é na verdade um alias puro
        # (não define nada, só reexporta) -- isso NÃO é perigoso.
        shim_info = {}
        for p in paths:
            is_shim, imported_from = is_pure_reexport_shim(p)
            if is_shim:
                shim_info[str(p.relative_to(root))] = imported_from

        # Tenta descobrir quem importa cada cópia, pelo caminho de módulo dotted
        module_candidates = []
        for p in paths:
            rel = p.relative_to(root)
            dotted = ".".join(rel.with_suffix("").parts)
            module_candidates.append(dotted)
        importers = find_importers(root, all_py_files, module_candidates)

        entry = {
            "basename": basename,
            "paths": list(hashes.keys()),
            "content_identical": content_identical,
            "hashes": hashes,
            "importado_por": importers,
        }

        if shim_info:
            # Um ou mais arquivos do grupo são aliases puros -- não é
            # duplicata perigosa, é encaminhamento intencional.
            entry["severity"] = "OK"
            entry["shims_detectados"] = shim_info
            entry["issue"] = (
                f"'{basename}' existe em {len(paths)} lugares, mas {list(shim_info.keys())} "
                f"não define implementação própria — só reexporta de {list(shim_info.values())}. "
                f"Isso é um alias intencional, não uma duplicata perigosa. Confirme que o alias "
                f"aponta pro arquivo certo, mas não precisa tratar como achado crítico."
            )
        elif not content_identical:
            entry["severity"] = "CRITICAL"
            entry["issue"] = (
                f"'{basename}' existe em {len(paths)} lugares com CONTEÚDO DIFERENTE, e nenhum "
                f"dos dois é um alias de encaminhamento — são duas implementações reais e "
                f"divergentes. Se o código que roda em produção importa uma cópia e a "
                f"auditoria/correção foi feita na outra, a correção não tem efeito nenhum. "
                f"Precisa confirmar manualmente qual cópia o main.py/bot.py de fato usa."
            )
            result["status"] = "FAIL"
        else:
            entry["severity"] = "WARN"
            entry["issue"] = (
                f"'{basename}' existe em {len(paths)} lugares com conteúdo IDÊNTICO. "
                f"Não é perigoso agora, mas é fácil uma cópia divergir da outra no futuro "
                f"sem ninguém perceber — considere deixar só uma e importar as outras."
            )
        result["findings"].append(entry)

    # ------------------------------------------------------------------
    # SEGUNDA CAMADA: mesma classe/função definida em arquivos com nomes
    # DIFERENTES. Comparar só o nome do arquivo não pega isso — precisa ler
    # o AST de todo o codebase e comparar símbolo por símbolo (classe,
    # método) pelo conteúdo real, não pelo nome do arquivo que o contém.
    # ------------------------------------------------------------------
    all_defs = scan_all_defs(root, targets)  # {qname: {kind, source, lineno, hash}}
    by_symbol = {}
    for qname, info in all_defs.items():
        if "::" not in qname:
            continue
        file_part, local_symbol = qname.split("::", 1)
        by_symbol.setdefault(local_symbol, []).append((file_part, info))

    symbol_duplicates = {sym: entries for sym, entries in by_symbol.items()
                          if len({f for f, _ in entries}) > 1}
    result["meta"]["simbolos_duplicados_entre_arquivos"] = len(symbol_duplicates)

    for local_symbol, entries in symbol_duplicates.items():
        files_involved = sorted({os.path.relpath(f, root) for f, _ in entries})
        hashes = {os.path.relpath(f, root): info["hash"] for f, info in entries}
        unique_hashes = set(hashes.values())
        content_identical = len(unique_hashes) == 1
        kind = entries[0][1]["kind"]

        entry = {
            "symbol": local_symbol,
            "kind": kind,
            "files": files_involved,
            "content_identical": content_identical,
            "hashes": hashes,
        }
        if not content_identical:
            entry["severity"] = "CRITICAL"
            entry["issue"] = (
                f"'{local_symbol}' ({kind}) está definido em {len(files_involved)} arquivos "
                f"DIFERENTES ({', '.join(files_involved)}) com IMPLEMENTAÇÃO DIFERENTE em cada um. "
                f"Isso é mais perigoso que arquivo duplicado: o nome é idêntico, então qualquer "
                f"import ambíguo (`from X import {local_symbol.split('.')[0]}`) pode pegar a versão "
                f"errada sem erro nenhum. Precisa decidir qual é a implementação real e eliminar a outra."
            )
            result["status"] = "FAIL"
        else:
            entry["severity"] = "WARN"
            entry["issue"] = (
                f"'{local_symbol}' ({kind}) está copiado, idêntico, em {len(files_involved)} arquivos. "
                f"Redundante — considere manter uma definição só e importar dos outros lugares."
            )
        result["findings"].append(entry)

    return result


# ============================================================================
# Checagem 4C — arquivos e funções longas demais pra revisar com confiança
# ============================================================================
# Motivo de existir: o bug do MAX_LOSS_USD_PER_TRADE ficou escondido dentro
# de uma função grande em main.py, e ninguém pegou "no olho" porque a função
# era grande demais pra ler de ponta a ponta com atenção real. Função/arquivo
# curto não garante ausência de bug, mas função gigante praticamente garante
# que algum trecho nunca foi lido com cuidado por ninguém.

FUNCTION_LENGTH_WARN = 60
FUNCTION_LENGTH_CRITICAL = 150
FILE_LENGTH_WARN = 500
FILE_LENGTH_CRITICAL = 1000

# Complexidade ciclomática (McCabe, 1976) — métrica institucional real, não
# um número inventado. Limiares padrão da indústria, usados por default em
# flake8-mccabe, radon e a maioria dos linters estáticos:
#   <= 10 : baixo risco
#   11-20 : moderado, exige mais teste
#   > 20  : alto risco, difícil de auditar todos os caminhos
CYCLOMATIC_COMPLEXITY_WARN = 10
CYCLOMATIC_COMPLEXITY_CRITICAL = 20


def calculate_cyclomatic_complexity(func_source: str) -> int:
    """Complexidade ciclomática de McCabe: 1 + número de pontos de decisão.
    Conta if/elif, for, while, except, and/or, comprehension-if, assert."""
    import textwrap
    try:
        tree = ast.parse(textwrap.dedent(func_source))
    except SyntaxError:
        return -1  # não foi possível parsear isoladamente (raro, edge case de sintaxe)
    complexity = 1
    for node in ast.walk(tree):
        if isinstance(node, (ast.If, ast.For, ast.AsyncFor, ast.While, ast.ExceptHandler)):
            complexity += 1
        elif isinstance(node, ast.BoolOp):
            complexity += len(node.values) - 1
        elif isinstance(node, ast.comprehension):
            complexity += len(node.ifs)
        elif isinstance(node, ast.Assert):
            complexity += 1
        elif isinstance(node, (ast.Match,)) if hasattr(ast, "Match") else False:
            complexity += len(getattr(node, "cases", [])) - 1
    return complexity


def check_complexity(root: Path):
    result = {"check": "complexity", "status": "OK", "findings": [], "meta": {}}
    targets = [t for t in RUFF_TARGETS if (root / t).exists()]
    all_py_files = find_py_files(root, targets)
    if not all_py_files:
        result["status"] = "SKIPPED"
        result["meta"]["reason"] = "nenhum arquivo .py encontrado"
        return result

    # --- Arquivos longos ---
    files_checked = 0
    for f in all_py_files:
        try:
            n_lines = len(f.read_text(encoding="utf-8", errors="ignore").splitlines())
        except Exception:
            continue
        files_checked += 1
        rel = str(f.relative_to(root))
        if n_lines > FILE_LENGTH_CRITICAL:
            result["findings"].append({
                "severity": "CRITICAL", "type": "ARQUIVO_MUITO_EXTENSO",
                "file": rel, "lines": n_lines,
                "issue": f"{rel} tem {n_lines} linhas (limite crítico: {FILE_LENGTH_CRITICAL}). "
                         f"Praticamente impossível auditar de ponta a ponta com confiança. "
                         f"Considere quebrar em módulos menores por responsabilidade.",
            })
            result["status"] = "FAIL"
        elif n_lines > FILE_LENGTH_WARN:
            result["findings"].append({
                "severity": "WARN", "type": "ARQUIVO_EXTENSO",
                "file": rel, "lines": n_lines,
                "issue": f"{rel} tem {n_lines} linhas (aviso: {FILE_LENGTH_WARN}). Vale considerar dividir.",
            })

    # --- Funções/métodos longos (reaproveita o scanner AST do vigia semântico) ---
    all_defs = scan_all_defs(root, targets)
    funcs_checked = 0
    for qname, info in all_defs.items():
        if info["kind"] not in ("function", "async_function"):
            continue
        funcs_checked += 1
        n_lines = info["source"].count("\n") + 1
        short_name = qname.split("::")[-1]
        if n_lines > FUNCTION_LENGTH_CRITICAL:
            result["findings"].append({
                "severity": "CRITICAL", "type": "FUNCAO_MUITO_LONGA",
                "symbol": qname, "lines": n_lines, "line_start": info["lineno"],
                "issue": f"'{short_name}' tem {n_lines} linhas (limite crítico: "
                         f"{FUNCTION_LENGTH_CRITICAL}). É exatamente esse tamanho de função "
                         f"que já escondeu bug de import (MAX_LOSS_USD_PER_TRADE) nesse projeto. "
                         f"Considere quebrar em funções menores com responsabilidade única.",
            })
            result["status"] = "FAIL"
        elif n_lines > FUNCTION_LENGTH_WARN:
            result["findings"].append({
                "severity": "WARN", "type": "FUNCAO_LONGA",
                "symbol": qname, "lines": n_lines, "line_start": info["lineno"],
                "issue": f"'{short_name}' tem {n_lines} linhas (aviso: {FUNCTION_LENGTH_WARN}).",
            })

        # Métrica institucional real: complexidade ciclomática (McCabe, 1976)
        cc = calculate_cyclomatic_complexity(info["source"])
        if cc >= 0:  # -1 = não foi possível calcular, ignora silenciosamente
            if cc > CYCLOMATIC_COMPLEXITY_CRITICAL:
                result["findings"].append({
                    "severity": "CRITICAL", "type": "COMPLEXIDADE_CICLOMATICA_ALTA",
                    "symbol": qname, "cyclomatic_complexity": cc, "line_start": info["lineno"],
                    "issue": f"'{short_name}' tem complexidade ciclomática {cc} "
                             f"(limite crítico institucional: {CYCLOMATIC_COMPLEXITY_CRITICAL}, "
                             f"padrão McCabe 1976). Alto risco: praticamente impossível testar "
                             f"todos os caminhos de decisão, mesmo com a função relativamente curta.",
                })
                result["status"] = "FAIL"
            elif cc > CYCLOMATIC_COMPLEXITY_WARN:
                result["findings"].append({
                    "severity": "WARN", "type": "COMPLEXIDADE_CICLOMATICA_MODERADA",
                    "symbol": qname, "cyclomatic_complexity": cc, "line_start": info["lineno"],
                    "issue": f"'{short_name}' tem complexidade ciclomática {cc} "
                             f"(aviso: {CYCLOMATIC_COMPLEXITY_WARN}, padrão McCabe 1976). "
                             f"Vale garantir teste cobrindo os principais caminhos.",
                })

    result["meta"]["arquivos_escaneados"] = files_checked
    result["meta"]["funcoes_escaneadas"] = funcs_checked
    result["meta"]["arquivos_criticos"] = len(
        [f for f in result["findings"] if f.get("type") == "ARQUIVO_MUITO_EXTENSO"])
    result["meta"]["funcoes_criticas"] = len(
        [f for f in result["findings"] if f.get("type") == "FUNCAO_MUITO_LONGA"])
    result["meta"]["complexidade_ciclomatica_critica"] = len(
        [f for f in result["findings"] if f.get("type") == "COMPLEXIDADE_CICLOMATICA_ALTA"])
    return result


# ============================================================================
# Checagem 5 — dataset de AutoLearn vazio ou pequeno demais
# ============================================================================

def check_dataset_emptiness(root: Path, min_trades_for_confidence=30):
    result = {"check": "dataset_emptiness", "status": "OK", "findings": [], "meta": {}}
    records, errors = load_jsonl_safe(root / TRADE_DATASET)
    if records is None:
        result["status"] = "SKIPPED"
        result["meta"]["reason"] = "trade_dataset.jsonl não encontrado"
        return result
    n = len(records)
    result["meta"]["trade_count"] = n
    if n == 0:
        result["status"] = "FAIL"
        result["findings"].append({
            "severity": "CRITICAL",
            "issue": "dataset vazio — qualquer claim de AutoLearn/self-tuning ativo é falso",
        })
    elif n < min_trades_for_confidence:
        result["status"] = "WARN"
        result["findings"].append({
            "severity": "WARN",
            "issue": f"apenas {n} trades — insuficiente para qualquer conclusão "
                     f"estatística de win rate ou edge (mínimo sugerido: {min_trades_for_confidence})",
        })
    return result


# ============================================================================
# Checagem 6 — contagem de testes declarada vs real
# ============================================================================

def check_test_count_claim(root: Path, run_tests=False):
    result = {"check": "test_count_claim", "status": "OK", "findings": [], "meta": {}}

    # 1. Descobre a contagem REAL via pytest --collect-only (não precisa rodar os testes)
    tests_dir = root / TESTS_DIR
    if not tests_dir.exists():
        result["status"] = "SKIPPED"
        result["meta"]["reason"] = "pasta tests/ não encontrada"
        return result

    try:
        mode = ["--collect-only", "-q"] if not run_tests else ["-q"]
        proc = subprocess.run(
            ["python", "-m", "pytest", str(tests_dir), *mode],
            capture_output=True, text=True, timeout=120, cwd=str(root),
        )
        output = proc.stdout + proc.stderr
    except FileNotFoundError:
        result["status"] = "SKIPPED"
        result["meta"]["reason"] = "pytest não disponível"
        return result
    except subprocess.TimeoutExpired:
        result["status"] = "ERROR"
        result["meta"]["reason"] = "timeout ao rodar pytest"
        return result

    m = re.search(r"(\d+)\s+(?:tests? collected|passed)", output)
    real_count = int(m.group(1)) if m else None
    result["meta"]["real_test_count"] = real_count
    result["meta"]["pytest_exit_code"] = proc.returncode
    if real_count is None:
        result["status"] = "ERROR"
        result["meta"]["raw_output_tail"] = output[-1000:]
        return result
    if run_tests and proc.returncode != 0:
        result["status"] = "FAIL"
        result["findings"].append({
            "severity": "CRITICAL",
            "issue": "pytest rodou e teve falha real (returncode != 0)",
            "raw_output_tail": output[-1500:],
        })

    # 2. Compara contra o que os arquivos de spec declaram
    for spec_name in SPEC_CANDIDATES:
        data, err = load_json_safe(root / spec_name)
        if err:
            continue
        declared = (
            get_nested(data, ["test_suite_metrics", "total_unit_tests"])
            or get_nested(data, ["quality_assurance_test_suite", "total_unit_tests"])
            or get_nested(data, ["audit_metadata", "unit_tests_passing"])
        )
        if declared is None:
            continue
        declared_num = None
        if isinstance(declared, (int, float)):
            declared_num = int(declared)
        elif isinstance(declared, str):
            m2 = re.search(r"(\d+)", declared)
            declared_num = int(m2.group(1)) if m2 else None
        if declared_num is not None and declared_num != real_count:
            result["status"] = "FAIL"
            result["findings"].append({
                "severity": "CRITICAL",
                "spec_file": spec_name,
                "declared_count": declared_num,
                "real_count": real_count,
                "issue": "contagem de testes declarada na spec não bate com a real",
            })
    return result


# ============================================================================
# Checagem 7 — vigia semântico (código NOVO/ALTERADO vira revisão obrigatória)
# ============================================================================

def _qualified_defs(tree: ast.AST, module_name: str):
    """Extrai (nome_qualificado, source_lines) de toda função/classe do módulo."""
    defs = {}

    class Visitor(ast.NodeVisitor):
        def __init__(self):
            self.stack = []

        def _record(self, node, kind):
            qname = f"{module_name}::" + ".".join(self.stack + [node.name])
            try:
                seg = ast.get_source_segment(Visitor.SRC, node) or ""
            except Exception:
                seg = ""
            defs[qname] = {"kind": kind, "source": seg, "lineno": node.lineno}
            self.stack.append(node.name)
            self.generic_visit(node)
            self.stack.pop()

        def visit_FunctionDef(self, node):
            self._record(node, "function")

        def visit_AsyncFunctionDef(self, node):
            self._record(node, "async_function")

        def visit_ClassDef(self, node):
            self._record(node, "class")

    return defs, Visitor


def extract_defs_from_file(path: Path):
    try:
        src = path.read_text(encoding="utf-8", errors="ignore")
        tree = ast.parse(src)
    except (SyntaxError, UnicodeDecodeError):
        return {}
    module_name = str(path)
    defs = {}
    Visitor_cls_holder = {}

    class Visitor(ast.NodeVisitor):
        SRC = src

        def __init__(self):
            self.stack = []

        def _record(self, node, kind):
            qname = f"{module_name}::" + ".".join(self.stack + [node.name])
            seg = ast.get_source_segment(src, node) or ""
            defs[qname] = {
                "kind": kind,
                "source": seg,
                "lineno": node.lineno,
                "hash": hashlib.sha256(seg.encode("utf-8")).hexdigest(),
            }
            self.stack.append(node.name)
            self.generic_visit(node)
            self.stack.pop()

        def visit_FunctionDef(self, node):
            self._record(node, "function")

        def visit_AsyncFunctionDef(self, node):
            self._record(node, "async_function")

        def visit_ClassDef(self, node):
            self._record(node, "class")

    Visitor().visit(tree)
    return defs


def scan_all_defs(root: Path, targets):
    all_defs = {}
    for t in targets:
        base = root / t
        if base.is_file() and base.suffix == ".py":
            all_defs.update(extract_defs_from_file(base))
        elif base.is_dir():
            for py_file in base.rglob("*.py"):
                all_defs.update(extract_defs_from_file(py_file))
    return all_defs


def _has_assignment(name: str, source: str) -> bool:
    """True se `name` recebe valor em algum ponto do trecho (atribuição ou
    parâmetro de função com default numérico literal)."""
    if re.search(ASSIGNMENT_RE_TEMPLATE.format(name=re.escape(name)), source):
        return True
    if re.search(DEFAULT_PARAM_RE_TEMPLATE.format(name=re.escape(name)), source):
        return True
    return False


def analyze_new_code_semantics(qname: str, info: dict):
    """Aplica as 3 heurísticas num trecho de código novo/alterado."""
    findings = []
    source = info["source"]

    # Heurística 1: parâmetro simbólico usado mas nunca definido/atribuído
    symbolic_names = set(m.group(1) for m in SYMBOLIC_PARAM_RE.finditer(source))
    for name in symbolic_names:
        if not _has_assignment(name, source):
            findings.append({
                "severity": "NEEDS_REVIEW",
                "type": "PARAMETRO_SIMBOLICO_SEM_FONTE",
                "symbol": qname,
                "detail": f"'{name}' é referenciado em fórmula mas nunca recebe valor "
                          f"numérico neste trecho. Precisa: valor concreto + origem/calibração.",
            })

    # Heurística 2: estatística citada sem variável de dado real por perto
    for m in STAT_NUMBER_RE.finditer(source):
        has_data_hint = any(hint in source for hint in DATA_SOURCE_HINTS)
        if not has_data_hint:
            findings.append({
                "severity": "NEEDS_REVIEW",
                "type": "ESTATISTICA_SEM_FONTE_RASTREAVEL",
                "symbol": qname,
                "detail": f"Estatística citada ('{m.group(0).strip()}') sem referência a "
                          f"dataset real (trade_dataset/symbol_edge_metrics/sample_size) "
                          f"neste trecho. Exigir origem antes de aceitar.",
            })

    # Heurística 3: teste fraco (só aplica a defs dentro de arquivos de teste)
    if "tests" + "/" in qname.replace("\\", "/") or "test_" in qname:
        asserts = re.findall(r"assert\s+(.+)", source)
        if asserts:
            trivial = sum(
                1 for a in asserts
                if re.match(r"^(is not None|isinstance\(|True\b)", a.strip())
            )
            if trivial / len(asserts) > 0.5:
                findings.append({
                    "severity": "NEEDS_REVIEW",
                    "type": "TESTE_POSSIVELMENTE_FRACO",
                    "symbol": qname,
                    "detail": f"{trivial}/{len(asserts)} dos asserts só checam "
                              f"is not None/isinstance/True, não um valor esperado "
                              f"específico. Verificar se o teste realmente valida a lógica.",
                })
    return findings


def check_semantic_watch(root: Path, baseline_path: Path = None, update_baseline: bool = False,
                          review_notes_path: Path = None):
    result = {"check": "semantic_watch", "status": "OK", "findings": [], "meta": {}}
    targets = [t for t in RUFF_TARGETS if (root / t).exists()]
    if not targets:
        result["status"] = "SKIPPED"
        result["meta"]["reason"] = "nenhum diretório alvo encontrado"
        return result

    current_defs = scan_all_defs(root, targets)
    baseline_path = baseline_path or (root / DEFAULT_BASELINE_FILE)
    baseline, err = load_json_safe(baseline_path)
    if err:
        baseline = {}
        result["meta"]["baseline_status"] = "PRIMEIRA_EXECUCAO (nenhuma baseline anterior encontrada)"
    else:
        result["meta"]["baseline_status"] = f"comparando contra baseline de {baseline_path}"

    new_or_changed = []
    for qname, info in current_defs.items():
        prev = baseline.get(qname)
        if prev is None:
            new_or_changed.append((qname, info, "NOVO"))
        elif prev.get("hash") != info["hash"]:
            new_or_changed.append((qname, info, "ALTERADO"))

    removed = [q for q in baseline if q not in current_defs]

    result["meta"]["total_defs_atuais"] = len(current_defs)
    result["meta"]["novos_ou_alterados"] = len(new_or_changed)
    result["meta"]["removidos"] = len(removed)

    for qname, info, change_type in new_or_changed:
        heuristic_findings = analyze_new_code_semantics(qname, info)
        entry = {
            "severity": "NEEDS_REVIEW",
            "symbol": qname,
            "kind": info["kind"],
            "change_type": change_type,
            "line": info["lineno"],
            "heuristic_flags": heuristic_findings,
            "issue": f"{change_type}: requer leitura semântica (humana ou de IA) — "
                     f"linter não valida lógica de negócio, só garante que isso não passe despercebido.",
        }
        result["findings"].append(entry)

    if new_or_changed:
        # NEEDS_REVIEW não é FAIL (não é "quebrado"), é "pendente de revisão humana"
        result["status"] = "NEEDS_REVIEW"

    # ------------------------------------------------------------------
    # ENDURECIMENTO: --update-baseline agora EXIGE um arquivo de notas de
    # revisão contendo, pra CADA qname novo/alterado, uma justificativa não
    # vazia escrita por um humano ou por uma IA que leu o código de verdade.
    # Sem isso, a baseline não é gravada — mesmo que --update-baseline tenha
    # sido passado. Isso fecha o buraco por onde o gamma_absorção passou
    # sem revisão: alguém rodou --update-baseline sem nunca olhar os achados.
    # ------------------------------------------------------------------
    if update_baseline:
        if new_or_changed and not review_notes_path:
            result["meta"]["baseline_update_status"] = (
                "RECUSADO: existem {} símbolos novos/alterados e nenhum --review-notes foi "
                "fornecido. Baseline NÃO foi atualizada.".format(len(new_or_changed))
            )
        else:
            review_notes, notes_err = (
                load_json_safe(review_notes_path) if review_notes_path else ({}, None)
            )
            if notes_err:
                review_notes = {}
            missing_notes = [
                qname for qname, info, _ in new_or_changed
                if not str(review_notes.get(qname, "")).strip()
            ]
            # --- ENDURECIMENTO 2 (v2): detecta nota genérica preenchida em massa ---
            # "não vazio" sozinho não garante revisão real. E só comparar texto
            # bruto não basta: um script pode inserir o nome do símbolo num
            # template fixo ("Revisão técnica ... para o símbolo {X}") e cada
            # nota fica "única" no texto bruto, mas é o MESMO texto disfarçado.
            # Por isso normaliza removendo o nome do próprio símbolo antes de
            # comparar -- se as notas colapsarem num template comum, é
            # preenchimento em massa disfarçado de específico.
            notes_used = [str(review_notes.get(qname, "")).strip()
                          for qname, info, _ in new_or_changed if qname not in set(missing_notes)]
            notes_with_symbols = [(qname, str(review_notes.get(qname, "")).strip())
                                   for qname, info, _ in new_or_changed if qname not in set(missing_notes)]
            bulk_filler_detected = False
            most_common_note = None
            if len(notes_used) >= 5:
                from collections import Counter
                # Camada 1: texto bruto idêntico
                most_common_note, most_common_count = Counter(notes_used).most_common(1)[0]
                if most_common_count / len(notes_used) > 0.20:
                    bulk_filler_detected = True
                # Camada 2: template após remover o nome do símbolo da nota
                if not bulk_filler_detected:
                    normalized = []
                    for qname, note in notes_with_symbols:
                        full_symbol = qname.split("::")[-1] if "::" in qname else qname
                        short_symbol = full_symbol.split(".")[-1]
                        norm = note.replace(full_symbol, "<SYM>").replace(short_symbol, "<SYM>")
                        normalized.append(norm)
                    most_common_template, most_common_template_count = Counter(normalized).most_common(1)[0]
                    if most_common_template_count / len(normalized) > 0.20:
                        bulk_filler_detected = True
                        most_common_note = most_common_template
            if missing_notes:
                result["meta"]["baseline_update_status"] = (
                    f"RECUSADO: {len(missing_notes)} símbolo(s) sem nota de revisão em "
                    f"{review_notes_path}: {missing_notes[:5]}{'...' if len(missing_notes) > 5 else ''}. "
                    f"Baseline NÃO foi atualizada."
                )
            elif bulk_filler_detected:
                result["status"] = "FAIL"
                result["findings"].append({
                    "severity": "CRITICAL",
                    "type": "REVIEW_NOTES_LIKELY_BULK_FILLER",
                    "issue": (
                        f"A nota '{most_common_note[:80]}' foi usada em "
                        f"{most_common_count}/{len(notes_used)} símbolos ("
                        f"{most_common_count/len(notes_used)*100:.0f}%). Isso não é revisão "
                        f"individual — é preenchimento genérico em massa. Baseline NÃO foi atualizada."
                    ),
                })
                result["meta"]["baseline_update_status"] = "RECUSADO: notas de revisão parecem preenchimento em massa, não revisão real."
            else:
                new_baseline = {q: {"hash": info["hash"], "kind": info["kind"]}
                                 for q, info in current_defs.items()}
                baseline_path.write_text(json.dumps(new_baseline, indent=2, ensure_ascii=False), encoding="utf-8")
                result["meta"]["baseline_atualizada"] = str(baseline_path)
                result["meta"]["baseline_update_status"] = "ACEITO: todos os símbolos tinham nota de revisão distinta"
                # Trilha de auditoria permanente, append-only
                log_path = root / "review_log.jsonl"
                with open(log_path, "a", encoding="utf-8") as f:
                    for qname, info, change_type in new_or_changed:
                        f.write(json.dumps({
                            "timestamp": now_iso(),
                            "symbol": qname,
                            "change_type": change_type,
                            "reviewer_note": review_notes.get(qname, ""),
                        }, ensure_ascii=False) + "\n")

    return result


# ============================================================================
# Checagem 10 — encoding e quebra de linha (pega EXATAMENTE o tipo de
# confusão que já aconteceu nessa auditoria: hash "diferente" que na
# real era só \r\n vs \n, ou falta de quebra de linha final)
# ============================================================================
# Motivo de existir: qualquer diferença de encoding gera hash SHA-256
# totalmente diferente mesmo sem nenhuma mudança de comportamento real.
# Isso já causou confusão pelo menos duas vezes nessa auditoria. Detecta
# (e, com --fix-encoding, corrige) em TODO o projeto -- não só código,
# também .json/.jsonl/.md, porque foi um .jsonl fora das pastas de código
# que causou o susto original.

def check_encoding(root: Path, fix: bool = False):
    result = {"check": "encoding", "status": "OK", "findings": [], "meta": {}}
    all_files = find_scannable_files(root)
    if not all_files:
        result["status"] = "SKIPPED"
        result["meta"]["reason"] = "nenhum arquivo escaneável encontrado"
        return result

    crlf_count, lf_count, fixed = 0, 0, []

    for f in all_files:
        try:
            raw = f.read_bytes()
        except Exception:
            continue
        if not raw:
            continue

        rel = str(f.relative_to(root))
        try:
            raw.decode("utf-8")
        except UnicodeDecodeError as e:
            result["findings"].append({
                "severity": "CRITICAL", "type": "ENCODING_INVALIDO", "file": rel,
                "issue": f"{rel} não decodifica como UTF-8 válido ({e}). Risco real de "
                         f"corrupção ou comportamento inconsistente entre máquinas/editores.",
            })
            result["status"] = "FAIL"
            continue

        has_bom = raw.startswith(b"\xef\xbb\xbf")
        has_crlf = b"\r\n" in raw
        has_bare_lf = b"\n" in raw.replace(b"\r\n", b"")
        mixed = has_crlf and has_bare_lf
        missing_trailing_newline = not raw.endswith(b"\n")

        if has_crlf:
            crlf_count += 1
        elif has_bare_lf:
            lf_count += 1

        issues = []
        if has_bom:
            issues.append("BOM_PRESENTE")
        if mixed:
            issues.append("QUEBRA_DE_LINHA_MISTA_CRLF_E_LF")
        if missing_trailing_newline:
            issues.append("SEM_QUEBRA_FINAL")

        if issues:
            sev = "CRITICAL" if mixed else "WARN"
            result["findings"].append({
                "severity": sev, "type": "+".join(issues), "file": rel,
                "issue": f"{rel}: {', '.join(issues)}. Isso já causou hash SHA-256 divergente "
                         f"entre cópias supostamente idênticas nesse projeto.",
            })
            if sev == "CRITICAL":
                result["status"] = "FAIL"

        # O --fix-encoding normaliza QUALQUER arquivo que precise de mudança de
        # bytes -- inclusive CRLF "limpo" sem nenhum outro problema -- porque o
        # objetivo é convenção única no projeto inteiro, não só corrigir o que
        # já virou achado individual (senão CRLF puro nunca seria tocado).
        if fix:
            new_raw = raw[3:] if has_bom else raw
            new_raw = new_raw.replace(b"\r\n", b"\n")
            if not new_raw.endswith(b"\n"):
                new_raw += b"\n"
            if new_raw != raw:
                f.write_bytes(new_raw)
                fixed.append(rel)

    if crlf_count > 0 and lf_count > 0:
        result["findings"].append({
            "severity": "WARN", "type": "CONVENCAO_INCONSISTENTE_NO_PROJETO",
            "issue": f"{crlf_count} arquivo(s) usam CRLF e {lf_count} usam LF puro no mesmo "
                     f"projeto. Misturar convenção entre arquivos é a causa raiz de hash "
                     f"divergente ao comparar cópias que deveriam ser idênticas.",
        })

    result["meta"]["arquivos_escaneados"] = len(all_files)
    result["meta"]["arquivos_com_crlf"] = crlf_count
    result["meta"]["arquivos_com_lf_puro"] = lf_count
    if fix:
        result["meta"]["arquivos_corrigidos"] = fixed
        result["meta"]["total_corrigidos"] = len(fixed)

    return result


# ============================================================================
# Checagem 11 — exceções silenciosas (except: pass sem log)
# ============================================================================
# Motivo de existir: já achamos esse padrão 2x manualmente nessa auditoria
# (position_log.json, market_scanner.py knowledge_base) -- e é provavelmente
# a mesma classe de causa raiz por trás dos crashes de asyncio/alerter: erro
# real acontecendo e sendo engolido sem log, então ninguém percebe até o
# comportamento errado aparecer em produção.

SILENT_EXCEPT_MAX_BODY_STATEMENTS = 1  # except com só "pass" ou só um statement sem log


def scan_silent_excepts(source: str):
    """Retorna lista de (lineno, exception_type_str) pra blocos except que não
    logam nem re-levantam a exceção -- só engolem silenciosamente."""
    import textwrap
    findings = []
    try:
        tree = ast.parse(textwrap.dedent(source))
    except SyntaxError:
        return findings
    for node in ast.walk(tree):
        if not isinstance(node, ast.ExceptHandler):
            continue
        body = node.body
        has_logging = False
        has_reraise = False
        for stmt in body:
            code = ast.dump(stmt)
            if "log" in code.lower() or "print" in code.lower() or "logger" in code.lower():
                has_logging = True
            if isinstance(stmt, ast.Raise):
                has_reraise = True
        if not has_logging and not has_reraise:
            exc_type = ast.unparse(node.type) if node.type else "Exception"
            findings.append((node.lineno, exc_type))
    return findings


def check_silent_exceptions(root: Path):
    result = {"check": "silent_exceptions", "status": "OK", "findings": [], "meta": {}}
    targets = [t for t in RUFF_TARGETS if (root / t).exists()]
    all_py_files = find_py_files(root, targets)
    if not all_py_files:
        result["status"] = "SKIPPED"
        result["meta"]["reason"] = "nenhum arquivo .py encontrado"
        return result

    for f in all_py_files:
        result["findings"].extend(_escanear_excecoes_silenciosas(f, root))

    if any(finding["severity"] == "CRITICAL" for finding in result["findings"]):
        result["status"] = "FAIL"
    result["meta"]["arquivos_escaneados"] = len(all_py_files)
    result["meta"]["total_encontrado"] = len(result["findings"])
    return result


def _escanear_excecoes_silenciosas(f, root):
    """Escaneia UM arquivo por 'except X:' que nem loga nem relança.
    Extraído de check_silent_exceptions. Retorna a lista de findings
    desse arquivo (vazia se nenhum ou erro de leitura)."""
    try:
        source = f.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return []
    rel = str(f.relative_to(root))
    findings = []
    for lineno, exc_type in scan_silent_excepts(source):
        # CRITICAL se pega Exception genérica (mais perigoso, esconde qualquer erro);
        # WARN se pega um tipo específico (menos abrangente, ainda merece log)
        sev = "CRITICAL" if exc_type in ("Exception", "BaseException") else "WARN"
        findings.append({
            "severity": sev, "type": "EXCECAO_SILENCIOSA",
            "file": rel, "line": lineno, "exception_type": exc_type,
            "issue": f"{rel}:{lineno} -- 'except {exc_type}:' não loga nem relança o erro. "
                     f"Se algo falhar aqui, ninguém vai saber -- é exatamente o padrão que "
                     f"já escondeu falha de gravação em position_log.json nesse projeto.",
        })
    return findings


# ============================================================================
# Checagem 12 — caminhos absolutos hardcoded (fragilidade/portabilidade)
# ============================================================================
# Motivo de existir: achamos "C:\SYSTEMS\FrameworkLCC\metadata\..." hardcoded
# dentro de market_scanner.py. Isso só funciona numa máquina específica e
# falha silenciosamente em qualquer outra (o except ao redor engole o erro).

HARDCODED_PATH_RE = re.compile(
    r"""["']([A-Za-z]:\\[^"']{3,}|/home/[^"']{3,}|/Users/[^"']{3,})["']"""
)


def check_hardcoded_paths(root: Path):
    result = {"check": "hardcoded_paths", "status": "OK", "findings": [], "meta": {}}
    targets = [t for t in RUFF_TARGETS if (root / t).exists()]
    all_py_files = find_py_files(root, targets)
    if not all_py_files:
        result["status"] = "SKIPPED"
        result["meta"]["reason"] = "nenhum arquivo .py encontrado"
        return result

    for f in all_py_files:
        result["findings"].extend(_escanear_caminhos_hardcoded(f, root))

    result["meta"]["arquivos_escaneados"] = len(all_py_files)
    result["meta"]["total_encontrado"] = len(result["findings"])
    if result["findings"]:
        result["status"] = "WARN"
    return result


def _escanear_caminhos_hardcoded(f, root):
    """Escaneia UM arquivo por caminhos absolutos hardcoded (Windows/Unix)
    em strings literais. Extraído de check_hardcoded_paths. Retorna a
    lista de findings desse arquivo (vazia se nenhum ou erro de leitura)."""
    try:
        text = f.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return []
    rel = str(f.relative_to(root))
    findings = []
    for i, line in enumerate(text.splitlines(), 1):
        for m in HARDCODED_PATH_RE.finditer(line):
            findings.append({
                "severity": "WARN", "type": "CAMINHO_ABSOLUTO_HARDCODED",
                "file": rel, "line": i, "path_found": m.group(1),
                "issue": f"{rel}:{i} tem caminho absoluto hardcoded ('{m.group(1)}'). "
                         f"Só funciona nessa máquina específica; quebra silenciosamente em "
                         f"qualquer outra instalação (ainda mais grave se estiver dentro de "
                         f"um except sem log).",
            })
    return findings


# ============================================================================
# Checagem 13 — dependências não travadas (requirements.txt)
# ============================================================================

def check_dependency_lock(root: Path):
    result = {"check": "dependency_lock", "status": "OK", "findings": [], "meta": {}}
    req_path = root / "requirements.txt"
    if not req_path.exists():
        result["status"] = "SKIPPED"
        result["meta"]["reason"] = "requirements.txt não encontrado"
        return result

    lines = [l.strip() for l in req_path.read_text(encoding="utf-8", errors="ignore").splitlines()
             if l.strip() and not l.strip().startswith("#")]
    unpinned = [l for l in lines if not re.search(r"==\d", l)]
    result["meta"]["total_dependencias"] = len(lines)
    result["meta"]["nao_travadas"] = len(unpinned)
    if unpinned:
        result["status"] = "WARN"
        result["findings"].append({
            "severity": "WARN", "type": "DEPENDENCIA_SEM_VERSAO_TRAVADA",
            "packages": unpinned,
            "issue": f"{len(unpinned)} dependência(s) sem versão travada com '==': {unpinned}. "
                     f"Build não é 100% reprodutível -- uma atualização de biblioteca pode mudar "
                     f"comportamento sem ninguém ter pedido.",
        })
    return result


# ============================================================================
# Checagem 14 — integridade dos arquivos persistentes (ledger e baseline)
# ============================================================================
# Motivo de existir: o self-hash protege o .py do linter, mas nada protegia
# o .lcc_bug_ledger.json e a baseline em si contra edição manual por fora do
# linter (alguém abrir o JSON e marcar "RESOLVED" na mão).

def _compute_content_hash(data: dict, exclude_key: str = "_integrity_hash"):
    clean = {k: v for k, v in data.items() if k != exclude_key}
    raw = json.dumps(clean, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def check_ledger_integrity(root: Path, ledger_path: Path = None, baseline_path: Path = None):
    result = {"check": "ledger_integrity", "status": "OK", "findings": [], "meta": {}}
    ledger_path = ledger_path or (root / DEFAULT_LEDGER_FILE)
    baseline_path = baseline_path or (root / DEFAULT_BASELINE_FILE)
    checked_any = False

    for label, path in (("bug_ledger", ledger_path), ("baseline", baseline_path)):
        data, err = load_json_safe(path)
        if err:
            continue
        checked_any = True
        stored_hash = data.get("_integrity_hash") if isinstance(data, dict) else None
        # Ledger e baseline no formato atual não têm _integrity_hash embutido
        # ainda -- isso é OK na primeira vez que essa checagem roda (adota o
        # hash atual como referência). Só vira achado se, numa próxima
        # rodada, o conteúdo mudar SEM passar pelas funções do próprio linter
        # (que são as únicas que deveriam reescrever esses arquivos).
        real_hash = _compute_content_hash(data) if isinstance(data, dict) else None
        result["meta"][f"{label}_hash_atual"] = real_hash
        if stored_hash and real_hash and stored_hash != real_hash:
            result["status"] = "FAIL"
            result["findings"].append({
                "severity": "CRITICAL", "type": "ARQUIVO_PERSISTENTE_EDITADO_MANUALMENTE",
                "file": str(path),
                "issue": f"{label} ({path}) foi modificado por fora das funções do linter -- "
                         f"o hash de conteúdo não bate com o que estava gravado. Alguém editou "
                         f"esse JSON manualmente (possivelmente pra forjar um RESOLVED).",
            })

    if not checked_any:
        result["status"] = "SKIPPED"
        result["meta"]["reason"] = "nem ledger nem baseline encontrados ainda"
    return result


# ============================================================================
# Checagem 15 — LIVRO DE BUGS (histórico persistente: quando surgiu, quando
# foi corrigido, se voltou a acontecer)
# ============================================================================
# Motivo de existir: até aqui, cada achado só existe "nesse instante" do
# relatório. Se um problema CRITICAL sumir na próxima rodada, não dá pra
# saber se foi corrigido de verdade ou se o próprio linter parou de olhar
# pra ele (já vimos os dois casos nessa auditoria: correção real do risk.py,
# e enfraquecimento disfarçado do check de banca). Essa camada roda POR
# ÚLTIMO, depois de todas as outras, e compara os achados desta rodada
# contra um livro-razão persistente em disco.
#
# LIMITAÇÃO HONESTA: "resolvido" aqui significa "não detectado mais por
# este scan" — não significa "confirmado corrigido por um humano". Se os
# dados de entrada forem alterados pra esconder o problema (ex: apagar
# trades do trade_dataset.jsonl em vez de corrigir a causa), o ledger vai
# marcar como resolvido sem que nada tenha sido de fato corrigido. Trate
# "RESOLVIDO" como um convite pra conferir, não como certificado definitivo.

DEFAULT_LEDGER_FILE = "linter/.lcc_bug_ledger.json"


def fingerprint_finding(check_name: str, finding: dict) -> str:
    """Gera uma chave estável pro mesmo problema, mesmo que o texto do
    'issue' mude levemente entre rodadas. Prioriza o identificador mais
    específico disponível no achado."""
    parts = [check_name]
    for key in ("trade_id", "symbol", "file", "basename", "name", "spec_file"):
        val = finding.get(key)
        if val:
            parts.append(f"{key}={val}")
            break
    else:
        parts.append(f"issue={str(finding.get('issue', ''))[:60]}")
    if finding.get("type"):
        parts.append(f"type={finding['type']}")
    raw = "|".join(parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def check_bug_ledger(root: Path, checks_so_far: dict, ledger_path: Path = None):
    result = {"check": "bug_ledger", "status": "OK", "findings": [], "meta": {}}
    ledger_path = ledger_path or (root / DEFAULT_LEDGER_FILE)
    ledger, err = load_json_safe(ledger_path)
    if err:
        ledger = {}
    # Remove logo na leitura pra nenhum loop de entrada tratar isso como um
    # "achado" -- é reinserido só na hora de gravar, no final.
    ledger.pop("_integrity_hash", None)

    now = now_iso()

    # Só rastreia achados de severidade grave -- WARN/SKIPPED não entram
    # no livro de bugs, pra não poluir o histórico com ruído cosmético.
    current_fps = {}
    for check_name, res in checks_so_far.items():
        for f in res.get("findings", []):
            # Rastreia CRITICAL/FAIL como antes, e agora também NEEDS_REVIEW
            # (achados semânticos) -- antes esses passavam batido pelo livro
            # de bugs inteiro, e foi assim que 271 alterações de refactor
            # nunca ficaram registradas em lugar nenhum persistente.
            if f.get("severity") not in ("CRITICAL", "FAIL", "NEEDS_REVIEW"):
                continue
            fp = fingerprint_finding(check_name, f)
            current_fps[fp] = (check_name, f)

    newly_opened, still_open, regressions, resolved_this_run = [], [], [], []

    for fp, (check_name, finding) in current_fps.items():
        entry = ledger.get(fp)
        if entry is None:
            ledger[fp] = {
                "check": check_name,
                "description": str(finding.get("issue", ""))[:200],
                "status": "OPEN",
                "first_seen": now,
                "last_seen": now,
                "resolved_at": None,
                "history": [{"event": "OPENED", "timestamp": now}],
            }
            newly_opened.append(fp)
        elif entry["status"] == "RESOLVED":
            entry["status"] = "OPEN"
            entry["last_seen"] = now
            entry["resolved_at"] = None
            entry.setdefault("history", []).append({"event": "REGRESSAO_REABERTO", "timestamp": now})
            regressions.append(fp)
        else:
            entry["last_seen"] = now
            still_open.append(fp)

    for fp, entry in list(ledger.items()):
        if entry["status"] == "OPEN" and fp not in current_fps:
            entry["status"] = "RESOLVED"
            entry["resolved_at"] = now
            entry.setdefault("history", []).append({"event": "RESOLVIDO", "timestamp": now})
            resolved_this_run.append(fp)

    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    to_write = dict(ledger)
    to_write["_integrity_hash"] = _compute_content_hash(ledger)
    ledger_path.write_text(json.dumps(to_write, indent=2, ensure_ascii=False), encoding="utf-8")

    def _days_open(entry):
        try:
            d1 = datetime.fromisoformat(entry["first_seen"])
            d2 = datetime.fromisoformat(entry["resolved_at"] or now)
            return round((d2 - d1).total_seconds() / 86400, 2)
        except Exception:
            return None

    for fp in regressions:
        e = ledger[fp]
        result["findings"].append({
            "severity": "CRITICAL", "fingerprint": fp, "type": "REGRESSAO",
            "check": e["check"], "description": e["description"],
            "issue": f"Esse problema já tinha sido marcado RESOLVIDO e voltou a aparecer "
                     f"(visto pela primeira vez em {e['first_seen']}). Isso é pior que um "
                     f"bug novo: significa que a correção não se sustentou ou foi revertida.",
        })
    for fp in newly_opened:
        e = ledger[fp]
        result["findings"].append({
            "severity": "INFO", "fingerprint": fp, "type": "NOVO",
            "check": e["check"], "description": e["description"],
            "issue": "Detectado agora pela primeira vez -- entrou no livro de bugs.",
        })
    for fp in resolved_this_run:
        e = ledger[fp]
        result["findings"].append({
            "severity": "INFO", "fingerprint": fp, "type": "RESOLVIDO",
            "check": e["check"], "description": e["description"],
            "days_open": _days_open(e),
            "issue": f"Não aparece mais nesta rodada. Ficou aberto por {_days_open(e)} dia(s). "
                     f"Confirme manualmente antes de considerar fechado de vez.",
        })

    result["meta"]["total_no_ledger"] = len(ledger)
    result["meta"]["abertos_agora"] = len([e for e in ledger.values() if e["status"] == "OPEN"])
    result["meta"]["resolvidos_historico"] = len([e for e in ledger.values() if e["status"] == "RESOLVED"])
    result["meta"]["novos_nesta_rodada"] = len(newly_opened)
    result["meta"]["resolvidos_nesta_rodada"] = len(resolved_this_run)
    result["meta"]["regressoes_nesta_rodada"] = len(regressions)
    result["meta"]["ledger_path"] = str(ledger_path)

    if regressions:
        result["status"] = "FAIL"
    elif newly_opened:
        result["status"] = "WARN"

    return result


# ============================================================================
# Checagem 16 — Condições e Lógica Duplicada / Clones de Código em AST
# ============================================================================
# Motivo de existir: Condições redundantes (ex: if x and x), cadeias if/elif
# com a mesma condição duplicada (dead code), ramos then/else idênticos,
# chaves duplicadas em dicionários e funções redefinidas no mesmo escopo
# causam falhas graves e silenciosas no robô.

def normalize_ast_expr(node: ast.AST) -> str:
    """Retorna representação textual canônica da expressão AST."""
    try:
        return ast.unparse(node).strip()
    except Exception:
        return ast.dump(node)


def scan_duplicate_conditions_in_ast(tree: ast.AST, file_rel: str) -> list:
    findings = []

    # 1. Redefinição de funções no mesmo escopo
    def check_scope_redefinitions(node_list, scope_name):
        seen_names = {}
        for item in node_list:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                fn_name = item.name
                # Ignora decorators como overload/property
                is_special = any(
                    isinstance(d, ast.Name) and d.id in ("overload", "override")
                    or isinstance(d, ast.Attribute) and d.attr in ("setter", "getter", "deleter")
                    for d in item.decorator_list
                )
                if is_special:
                    continue
                if fn_name in seen_names:
                    first_line = seen_names[fn_name]
                    findings.append({
                        "severity": "CRITICAL",
                        "type": "REDEFINICAO_FUNCAO_MESMO_ESCOPO",
                        "file": file_rel,
                        "line": item.lineno,
                        "symbol": fn_name,
                        "issue": (
                            f"{file_rel}:{item.lineno} -- Função/Método '{fn_name}' foi redefinido no escopo "
                            f"'{scope_name}' (já definido na linha {first_line}). A segunda definição "
                            f"sobrescreve a primeira silenciosamente!"
                        ),
                    })
                else:
                    seen_names[fn_name] = item.lineno
            elif isinstance(item, ast.ClassDef):
                check_scope_redefinitions(item.body, f"class {item.name}")

    if isinstance(tree, ast.Module):
        check_scope_redefinitions(tree.body, "module")

    # 2. Condições duplicadas, ramos idênticos, expressões booleanas e dict keys
    for node in ast.walk(tree):
        if isinstance(node, ast.If):
            # Cadeia if / elif
            chain_conditions = []
            curr = node
            while isinstance(curr, ast.If):
                cond_str = normalize_ast_expr(curr.test)
                chain_conditions.append((cond_str, curr.lineno))
                if len(curr.orelse) == 1 and isinstance(curr.orelse[0], ast.If):
                    curr = curr.orelse[0]
                else:
                    break

            seen_conds = {}
            for c_str, lno in chain_conditions:
                if c_str in seen_conds:
                    prev_lno = seen_conds[c_str]
                    findings.append({
                        "severity": "CRITICAL",
                        "type": "CONDICAO_IF_ELIF_DUPLICADA",
                        "file": file_rel,
                        "line": lno,
                        "condition": c_str,
                        "issue": (
                            f"{file_rel}:{lno} -- Condição '{c_str}' já foi testada na linha {prev_lno} "
                            f"na mesma cadeia if/elif. Este ramo é inatingível (código morto)!"
                        ),
                    })
                else:
                    seen_conds[c_str] = lno

            # Ramos then / else idênticos
            if node.body and node.orelse and not (len(node.orelse) == 1 and isinstance(node.orelse[0], ast.If)):
                body_dump = [normalize_ast_expr(stmt) for stmt in node.body]
                else_dump = [normalize_ast_expr(stmt) for stmt in node.orelse]
                if body_dump == else_dump and len(body_dump) > 0:
                    findings.append({
                        "severity": "CRITICAL",
                        "type": "RAMOS_THEN_ELSE_IDENTICOS",
                        "file": file_rel,
                        "line": node.lineno,
                        "issue": (
                            f"{file_rel}:{node.lineno} -- Os blocos 'if' e 'else' executam exatamente as "
                            f"mesmas instruções. O teste condicional é inútil ou esconde um erro de cópia e cola!"
                        ),
                    })

        elif isinstance(node, ast.BoolOp):
            seen_values = set()
            for val in node.values:
                val_str = normalize_ast_expr(val)
                if val_str in seen_values:
                    op_name = "and" if isinstance(node.op, ast.And) else "or"
                    findings.append({
                        "severity": "CRITICAL",
                        "type": "EXPRESSAO_BOOLEANA_REDUNDANTE",
                        "file": file_rel,
                        "line": node.lineno,
                        "expression": normalize_ast_expr(node),
                        "issue": (
                            f"{file_rel}:{node.lineno} -- Sub-expressão '{val_str}' está repetida no operador "
                            f"'{op_name}'. Lógica redundante que indica possível erro de digitação!"
                        ),
                    })
                seen_values.add(val_str)

        elif isinstance(node, ast.Dict):
            seen_keys = set()
            for k in node.keys:
                if k is not None and isinstance(k, (ast.Constant, ast.Name)):
                    k_str = normalize_ast_expr(k)
                    if k_str in seen_keys:
                        findings.append({
                            "severity": "CRITICAL",
                            "type": "CHAVE_DICIONARIO_DUPLICADA",
                            "file": file_rel,
                            "line": node.lineno,
                            "key": k_str,
                            "issue": (
                                f"{file_rel}:{node.lineno} -- Chave de dicionário '{k_str}' está duplicada no "
                                f"mesmo literal. O segundo valor sobrescreve o primeiro silenciosamente!"
                            ),
                        })
                    seen_keys.add(k_str)

    return findings


def scan_duplicate_code_blocks(all_py_files: list, root: Path, min_statements: int = 6) -> list:
    findings = []
    block_hashes = {}

    for py_file in all_py_files:
        try:
            src = py_file.read_text(encoding="utf-8", errors="ignore")
            tree = ast.parse(src)
        except Exception:
            continue
        rel = str(py_file.relative_to(root))

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                body = node.body
                if len(body) >= min_statements:
                    for i in range(len(body) - min_statements + 1):
                        slice_nodes = body[i : i + min_statements]
                        raw_stmts = [normalize_ast_expr(st) for st in slice_nodes]
                        # Ignora blocos triviais de docstrings ou logs simples repetidos
                        if all(st.startswith("logger.") or st.startswith("pass") for st in raw_stmts):
                            continue
                        block_str = "\n".join(raw_stmts)
                        block_hash = hashlib.sha256(block_str.encode("utf-8")).hexdigest()[:16]
                        entry = {
                            "file": rel,
                            "function": node.name,
                            "line": slice_nodes[0].lineno,
                            "end_line": slice_nodes[-1].lineno,
                        }
                        block_hashes.setdefault(block_hash, []).append(entry)

    for b_hash, occurrences in block_hashes.items():
        unique_locs = {(occ["file"], occ["line"]) for occ in occurrences}
        if len(unique_locs) > 1:
            first = occurrences[0]
            loc_list = [f"{occ['file']}:{occ['line']} ({occ['function']})" for occ in occurrences]
            findings.append({
                "severity": "WARN",
                "type": "BLOCO_STATEMENTS_DUPLICADO",
                "file": first["file"],
                "line": first["line"],
                "occurrences": loc_list,
                "issue": (
                    f"Bloco de código duplicado ({min_statements}+ instruções) encontrado em múltiplos locais: "
                    f"{', '.join(loc_list[:4])}. Considere encapsular em função única para evitar "
                    f"bugs de dessincronização."
                ),
            })
    return findings


def check_duplicate_conditions_and_logic(root: Path):
    result = {"check": "duplicate_conditions", "status": "OK", "findings": [], "meta": {}}
    targets = [t for t in RUFF_TARGETS if (root / t).exists()]
    all_py_files = find_py_files(root, targets)
    if not all_py_files:
        result["status"] = "SKIPPED"
        result["meta"]["reason"] = "nenhum arquivo .py encontrado"
        return result

    for py_file in all_py_files:
        try:
            src = py_file.read_text(encoding="utf-8", errors="ignore")
            tree = ast.parse(src)
            rel = str(py_file.relative_to(root))
            result["findings"].extend(scan_duplicate_conditions_in_ast(tree, rel))
        except Exception:
            continue

    # Clones de código em blocos
    result["findings"].extend(scan_duplicate_code_blocks(all_py_files, root))

    if any(f["severity"] == "CRITICAL" for f in result["findings"]):
        result["status"] = "FAIL"
    elif any(f["severity"] == "WARN" for f in result["findings"]):
        result["status"] = "WARN"

    result["meta"]["arquivos_escaneados"] = len(all_py_files)
    result["meta"]["total_achados"] = len(result["findings"])
    return result


# ============================================================================
# SUGESTÃO DE CORREÇÃO -- todo achado grave/aviso ganha um campo "como_corrigir"
# ============================================================================
# Motivo de existir: você pediu -- sempre que o linter apontar algo, ele deve
# mostrar uma forma de corrigir junto, não só descrever o problema. Isso é
# uma sugestão de PRIMEIRO PASSO, não um fix automático (exceto encoding, que
# já tem --fix-encoding de verdade) -- ainda exige julgamento humano/de IA
# pros achados que envolvem lógica de negócio.

FIX_SUGGESTIONS = {
    # duplicate_conditions
    ("duplicate_conditions", "CONDICAO_IF_ELIF_DUPLICADA"): "Remova o ramo elif redundante ou corrija a condição para testar a variável correta.",
    ("duplicate_conditions", "RAMOS_THEN_ELSE_IDENTICOS"): "Corrija o corpo do if ou do else para executar a ação distinta esperada, ou remova o condicional se a ação for incondicional.",
    ("duplicate_conditions", "EXPRESSAO_BOOLEANA_REDUNDANTE"): "Elimine o operando duplicado no 'and'/'or' ou corrija para o segundo predicado pretendido.",
    ("duplicate_conditions", "CHAVE_DICIONARIO_DUPLICADA"): "Remova a chave duplicada ou renomeie para a chave correta no dicionário.",
    ("duplicate_conditions", "REDEFINICAO_FUNCAO_MESMO_ESCOPO"): "Renomeie uma das funções ou elimine a definição obsoleta para evitar que a segunda sobrescreva a primeira.",
    ("duplicate_conditions", "BLOCO_STATEMENTS_DUPLICADO"): "Extraia a sequência repetida de instruções em uma função/método auxiliar reutilizável.",
    # ruff
    ("ruff", "F821"): "Importe ou defina a variável/nome antes de usá-la. Rode "
                       "`ruff check --select F821,F401 --fix` pra corrigir os F401 "
                       "automaticamente; F821 precisa de correção manual.",
    ("ruff", "F401"): "Remova o import não utilizado, ou use `ruff check --fix` "
                       "pra remover automaticamente.",
    ("ruff", "F811"): "Remova a redefinição duplicada do mesmo nome no arquivo.",
    ("ruff", "E9"): "Corrija o erro de sintaxe na linha apontada antes de qualquer outra coisa.",
    # hash
    ("hash", "HASH_NAO_BATE"): "Recalcule o hash real do arquivo (Get-FileHash no PowerShell) "
                                "e atualize o valor na spec, ou restaure o arquivo original se "
                                "foi alterado sem intenção.",
    ("hash", "ARQUIVO_NAO_ENCONTRADO_NO_DISCO"): "O arquivo referenciado na spec não existe -- "
                                "restaure-o ou remova a entrada da spec.",
    # drift
    ("drift", "DIVERGENCIA"): "Escolha uma fonte de verdade única: ou atualize a constante "
                               "hardcoded no código pra bater com o config, ou vice-versa.",
    ("drift", "LINTER_TAMPER_DETECTED"): "Restaure DRIFT_CHECKS pro estado com as 3 checagens "
                               "originais -- compare o self-hash do linter contra a referência "
                               "que você guardou.",
    # duplicates
    ("duplicates", "file_critical"): "Decida qual arquivo é a implementação real; transforme "
                               "o outro em alias puro (`from X import Y`) como foi feito com "
                               "risk.py e lcc_ia_brain.py.",
    ("duplicates", "symbol_critical"): "Duas implementações reais sob o mesmo nome. Se forem a "
                               "mesma intenção: elimine uma, mantenha só a correta. Se forem "
                               "propósitos genuinamente diferentes: renomeie uma delas pra "
                               "desambiguar (como MarketScanner -> CognitiveRosterScanner).",
    ("duplicates", "warn_identical"): "Redundante mas idêntico -- mantenha uma definição só e "
                               "importe dos outros lugares.",
    # complexity
    ("complexity", "FUNCAO_MUITO_LONGA"): "Quebre em funções menores com responsabilidade "
                               "única. Comentários de seção dentro da função geralmente marcam "
                               "os pontos de corte naturais.",
    ("complexity", "FUNCAO_LONGA"): "Considere extrair a parte mais isolada da função num "
                               "helper nomeado.",
    ("complexity", "ARQUIVO_MUITO_EXTENSO"): "Divida o arquivo em módulos menores por "
                               "responsabilidade (ex: separar orquestração de lógica de decisão).",
    ("complexity", "ARQUIVO_EXTENSO"): "Considere dividir em 2 arquivos se crescer mais.",
    ("complexity", "COMPLEXIDADE_CICLOMATICA_ALTA"): "Extraia os condicionais aninhados em "
                               "funções auxiliares nomeadas, ou use early-return pra achatar "
                               "a estrutura em vez de aninhar if/elif.",
    ("complexity", "COMPLEXIDADE_CICLOMATICA_MODERADA"): "Vale a pena simplificar, mas não é "
                               "urgente -- garanta que existe teste cobrindo os principais caminhos.",
    # encoding
    ("encoding", "any"): "Rode com `--fix-encoding` pra normalizar automaticamente "
                               "(remove BOM, converte CRLF->LF, garante quebra de linha final). "
                               "Não muda lógica, só formatação de byte.",
    ("encoding", "ENCODING_INVALIDO"): "Abra o arquivo num editor e salve explicitamente como "
                               "UTF-8 -- há bytes que não decodificam, --fix-encoding não resolve isso.",
    # silent_exceptions
    ("silent_exceptions", "EXCECAO_SILENCIOSA"): "Adicione um `logger.error(...)` ou "
                               "`logger.warning(...)` dentro do bloco except antes do `pass`, "
                               "ou relance a exceção (`raise`) se ela não deveria ser engolida.",
    # hardcoded_paths
    ("hardcoded_paths", "CAMINHO_ABSOLUTO_HARDCODED"): "Mova o caminho pra uma variável de "
                               "config (config/settings.py ou .env), com valor relativo ao "
                               "projeto ou configurável por ambiente.",
    # dependency_lock
    ("dependency_lock", "DEPENDENCIA_SEM_VERSAO_TRAVADA"): "Rode `pip freeze > requirements.txt` "
                               "num ambiente que já funciona, pra travar a versão exata de cada "
                               "dependência com '=='.",
    # ledger_integrity
    ("ledger_integrity", "ARQUIVO_PERSISTENTE_EDITADO_MANUALMENTE"): "Restaure o arquivo a "
                               "partir do último estado que o próprio linter gravou (git, backup, "
                               "ou refaça a partir do zero) -- não deve ser editado à mão.",
    # banca
    ("banca", "banca"): "Consiga o extrato real de posições da Bybit (Account > Position "
                               "History) pro horário exato do trade, ou rode com --position-log "
                               "apontando pra um log real de posições concorrentes. Se a causa "
                               "já é conhecida (ex: operação manual sua), documente e siga em frente.",
    # dataset
    ("dataset", "dataset"): "Não é bug de código -- deixe o bot operar mais até acumular "
                               "amostra suficiente pra qualquer conclusão estatística.",
    # tests
    ("tests", "tests"): "Rode `pytest tests/ -v` e veja qual teste falhou, ou qual arquivo "
                               "tem contagem diferente da declarada na spec -- corrija o que "
                               "estiver errado (código ou a spec, o que não bater com a realidade).",
    # semantic
    ("semantic", "PARAMETRO_SIMBOLICO_SEM_FONTE"): "Defina o valor numérico da variável com "
                               "origem rastreável (config, cálculo explícito, ou dado real) -- "
                               "não deixe em fórmula sem nunca receber valor.",
    ("semantic", "ESTATISTICA_SEM_FONTE_RASTREAVEL"): "Cite a amostra real (arquivo, "
                               "sample_size) que sustenta a estatística, ou remova a alegação "
                               "até ter dado real.",
    ("semantic", "TESTE_POSSIVELMENTE_FRACO"): "Troque os asserts genéricos (is not None) por "
                               "asserts que comparam contra um valor esperado específico.",
    ("semantic", "review"): "Leia o trecho de código apontado e escreva uma nota de revisão "
                               "ESPECÍFICA (não um template com o nome do símbolo interpolado) "
                               "em --review-notes antes de rodar --update-baseline.",
    # bug_ledger
    ("bug_ledger", "REGRESSAO"): "Investigue por que a correção não se sustentou -- confira se "
                               "alguém reverteu o commit, ou se a correção nunca chegou a valer "
                               "no arquivo que roda de fato em produção.",
}


def suggest_fix(check_name: str, finding: dict) -> str:
    # Casos especiais: alguns checks guardam o "tipo" do achado num campo
    # diferente de "type" (drift usa "name"; hash reusa "issue" como código
    # curto em vez de frase).
    if check_name == "drift":
        name = finding.get("name", "")
        if name == "LINTER_TAMPER_DETECTED":
            return FIX_SUGGESTIONS[("drift", "LINTER_TAMPER_DETECTED")]
        if finding.get("severity") == "CRITICAL":
            return FIX_SUGGESTIONS[("drift", "DIVERGENCIA")]
        return ("O regex não encontrou a constante no código -- confirme o valor manualmente, "
                "e se o código mudou de formato/nome, ajuste o code_regex correspondente em "
                "DRIFT_CHECKS pra ele voltar a enxergar a constante.")
    if check_name == "hash":
        issue_code = finding.get("issue", "")
        key = ("hash", issue_code)
        if key in FIX_SUGGESTIONS:
            return FIX_SUGGESTIONS[key]

    ftype = finding.get("type", "")
    code = finding.get("code", "")
    key_candidates = [
        (check_name, code),
        (check_name, ftype),
        (check_name, ftype.split("+")[0] if "+" in ftype else ftype),  # encoding tipos compostos
        (check_name, "file_critical") if check_name == "duplicates" and "basename" in finding
            and finding.get("severity") == "CRITICAL" else None,
        (check_name, "symbol_critical") if check_name == "duplicates" and "symbol" in finding
            and finding.get("severity") == "CRITICAL" else None,
        (check_name, "warn_identical") if check_name == "duplicates" and finding.get("content_identical")
            else None,
        (check_name, "any") if check_name == "encoding" else None,
        (check_name, "review") if check_name == "semantic" and ftype not in
            ("PARAMETRO_SIMBOLICO_SEM_FONTE", "ESTATISTICA_SEM_FONTE_RASTREAVEL",
             "TESTE_POSSIVELMENTE_FRACO") else None,
        (check_name, check_name) if check_name in ("banca", "dataset", "tests") else None,
    ]
    for key in key_candidates:
        if key and key in FIX_SUGGESTIONS:
            return FIX_SUGGESTIONS[key]
    return "Sem sugestão automática pra esse tipo específico -- leia o campo 'issue' e avalie manualmente."


def attach_fix_suggestions(check_name: str, result: dict):
    """Adiciona 'como_corrigir' em todo achado do resultado, na própria estrutura
    (in-place), pra qualquer achado de severidade WARN/CRITICAL/FAIL/NEEDS_REVIEW."""
    for f in result.get("findings", []):
        if f.get("severity") in ("WARN", "CRITICAL", "FAIL", "NEEDS_REVIEW"):
            f["como_corrigir"] = suggest_fix(check_name, f)
            # Achados de semantic_watch trazem sub-achados em heuristic_flags
            for hf in f.get("heuristic_flags", []):
                hf["como_corrigir"] = suggest_fix(check_name, hf)


# ============================================================================
# Orquestrador
# ============================================================================

ALL_CHECKS = {
    "ruff": check_ruff,
    "hash": check_hash_manifest,
    "drift": check_config_drift,
    "duplicates": check_duplicate_files,
    "duplicate_conditions": check_duplicate_conditions_and_logic,
    "complexity": check_complexity,
    "encoding": check_encoding,
    "silent_exceptions": check_silent_exceptions,
    "hardcoded_paths": check_hardcoded_paths,
    "dependency_lock": check_dependency_lock,
    "ledger_integrity": check_ledger_integrity,
    "banca": check_banca_reconciliation,
    "dataset": check_dataset_emptiness,
    "tests": check_test_count_claim,
    "semantic": check_semantic_watch,
}


def run_audit(root: Path, only=None, run_tests=False, baseline_path=None, update_baseline=False,
              review_notes_path=None, position_log_path=None, bug_ledger_path=None,
              fix_encoding=False):
    selected = only if only else list(ALL_CHECKS.keys()) + ["bug_ledger"]
    report = {
        "audit_timestamp_utc": now_iso(),
        "linter_self_hash": self_integrity_hash(),
        "root": str(root),
        "checks": {},
        "summary": {"status": "OK", "critical_findings": 0, "warn_findings": 0,
                    "needs_review": 0, "skipped": 0},
    }
    for name in selected:
        if name == "bug_ledger":
            continue  # roda por último, depois -- precisa dos achados dos outros checks
        fn = ALL_CHECKS.get(name)
        if not fn:
            continue
        if name == "tests":
            res = fn(root, run_tests=run_tests)
        elif name == "semantic":
            res = fn(root, baseline_path=baseline_path, update_baseline=update_baseline,
                      review_notes_path=review_notes_path)
        elif name == "banca":
            res = fn(root, position_log_path=position_log_path)
        elif name == "encoding":
            res = fn(root, fix=fix_encoding)
        elif name == "ledger_integrity":
            res = fn(root, ledger_path=bug_ledger_path, baseline_path=baseline_path)
        else:
            res = fn(root)
        attach_fix_suggestions(name, res)
        report["checks"][name] = res
        if res["status"] == "FAIL":
            report["summary"]["status"] = "FAIL"
            report["summary"]["critical_findings"] += len(
                [f for f in res.get("findings", []) if f.get("severity") == "CRITICAL"]
            )
        elif res["status"] == "NEEDS_REVIEW":
            if report["summary"]["status"] == "OK":
                report["summary"]["status"] = "NEEDS_REVIEW"
            report["summary"]["needs_review"] += len(res.get("findings", []))
        elif res["status"] == "WARN":
            report["summary"]["warn_findings"] += 1
        elif res["status"] == "SKIPPED":
            report["summary"]["skipped"] += 1

    if "bug_ledger" in selected:
        ledger_res = check_bug_ledger(root, report["checks"], ledger_path=bug_ledger_path)
        attach_fix_suggestions("bug_ledger", ledger_res)
        report["checks"]["bug_ledger"] = ledger_res
        if ledger_res["status"] == "FAIL":
            report["summary"]["status"] = "FAIL"
            report["summary"]["critical_findings"] += len(
                [f for f in ledger_res.get("findings", []) if f.get("severity") == "CRITICAL"]
            )
        elif ledger_res["status"] == "WARN":
            report["summary"]["warn_findings"] += 1

    return report


def print_human_summary(report):
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception as _exc:
            # GUARDIAO/MUD-01: erro nao pode desaparecer sem rastro.
            logging.getLogger(__name__).warning("[MUD-01] %s:1956 ignorou %s: %s",
                            __name__, type(_exc).__name__, _exc)
    print("\n" + "=" * 70)
    print(f"  LCC ULTRA — AUDIT LINTER  |  {report['audit_timestamp_utc']}")
    print(f"  🔒 SELF-HASH DO LINTER: {report['linter_self_hash']}")
    print("     (guarde esse valor fora do repositório; se mudar sem você pedir, foi editado)")
    print("=" * 70)
    status = report["summary"]["status"]
    icon = {"OK": "🟢 OK", "FAIL": "🔴 FAIL", "NEEDS_REVIEW": "🟡 NEEDS REVIEW"}.get(status, status)
    print(f"  Status geral: {icon}")
    print(f"  Achados críticos: {report['summary']['critical_findings']}")
    print(f"  Pendentes de revisão semântica: {report['summary']['needs_review']}")
    print(f"  Avisos: {report['summary']['warn_findings']}")
    print(f"  Checagens puladas: {report['summary']['skipped']}")
    print("-" * 70)
    for name, res in report["checks"].items():
        icon = {"OK": "✅", "FAIL": "❌", "WARN": "⚠️ ", "SKIPPED": "⏭️ ",
                "ERROR": "💥", "NEEDS_REVIEW": "🟡"}.get(res["status"], "?")
        print(f"  {icon} {name:<25} status={res['status']}")
        if name == "bug_ledger":
            m = res.get("meta", {})
            print(f"       livro de bugs: {m.get('abertos_agora', 0)} aberto(s), "
                  f"{m.get('resolvidos_historico', 0)} resolvido(s) no histórico, "
                  f"{m.get('novos_nesta_rodada', 0)} novo(s) nesta rodada, "
                  f"{m.get('resolvidos_nesta_rodada', 0)} resolvido(s) nesta rodada, "
                  f"{m.get('regressoes_nesta_rodada', 0)} REGRESSÃO(ÕES)")
            for f in res.get("findings", []):
                tag = {"REGRESSAO": "🔴 REGRESSÃO", "RESOLVIDO": "✅ resolvido",
                       "NOVO": "🆕 novo"}.get(f.get("type"), f.get("type"))
                print(f"       {tag}: [{f['check']}] {f['description'][:80]}")
            continue
        for f in res.get("findings", []):
            if f.get("severity") == "CRITICAL":
                print(f"       -> {f.get('issue', '')} | {f}")
            elif f.get("severity") == "NEEDS_REVIEW" and name == "semantic":
                print(f"       -> [{f['change_type']}] {f['symbol']} (linha {f['line']})")
                for hf in f.get("heuristic_flags", []):
                    print(f"            ⚑ {hf['type']}: {hf['detail']}")
    print("=" * 70 + "\n")


def write_split_output(report: dict, out_dir: Path):
    """Grava um arquivo JSON pequeno por checagem, em vez de um único
    relatório gigante. Cada arquivo fica pequeno o bastante pra abrir,
    ler e colar em qualquer lugar sem truncar."""
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []

    summary = {
        "audit_timestamp_utc": report["audit_timestamp_utc"],
        "linter_self_hash": report["linter_self_hash"],
        "root": report["root"],
        "summary": report["summary"],
        "checks_status": {name: res["status"] for name, res in report["checks"].items()},
        "arquivos_desta_rodada": [f"{name}.json" for name in report["checks"]],
    }
    summary_path = out_dir / "_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    written.append(summary_path)

    for name, res in report["checks"].items():
        check_path = out_dir / f"{name}.json"
        check_path.write_text(json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")
        written.append(check_path)

    return written


def main():
    parser = argparse.ArgumentParser(description="LCC ULTRA — Audit Linter")
    parser.add_argument("--root", default=".", help="Raiz do projeto LCC_ULTRA")
    parser.add_argument("--only", default=None, help="Lista separada por vírgula: ruff,hash,drift,banca,dataset,tests")
    parser.add_argument("--run-tests", action="store_true", help="Roda a suíte pytest de verdade, não só coleta")
    parser.add_argument("--out", default=None, help="Salva o JSON completo em UM arquivo (além de stdout)")
    parser.add_argument("--split-output", default=None,
                         help="Pasta onde gravar UM arquivo JSON pequeno por checagem "
                              "(_summary.json + ruff.json, banca.json, etc.) em vez de um "
                              "relatório único grande. Use isso pra evitar truncamento ao "
                              "ler/colar um achado específico.")
    parser.add_argument("--human", action="store_true", help="Também imprime resumo legível no stderr")
    parser.add_argument("--baseline", default=None,
                         help="Caminho do arquivo de baseline do vigia semântico "
                              f"(default: <root>/{DEFAULT_BASELINE_FILE})")
    parser.add_argument("--update-baseline", action="store_true",
                         help="Após revisar os achados NEEDS_REVIEW, aceita o estado atual "
                              "do código como novo baseline. AGORA EXIGE --review-notes "
                              "com justificativa não vazia pra cada símbolo, senão é recusado.")
    parser.add_argument("--review-notes", default=None,
                         help="Caminho de um JSON {qname: 'nota do revisor'} — obrigatório "
                              "junto com --update-baseline se houver símbolos novos/alterados")
    parser.add_argument("--position-log", default=None,
                         help="Caminho de um JSON {trade_id: {concurrent_open_positions: N}} "
                              "usado como ÚNICA evidência aceitável pra explicar divergência de banca")
    parser.add_argument("--bug-ledger", default=None,
                         help="Caminho do livro de bugs persistente (default: "
                              f"<root>/{DEFAULT_LEDGER_FILE}). Rastreia quando cada achado grave "
                              "surgiu, se foi resolvido, e se voltou a acontecer (regressão).")
    parser.add_argument("--no-ledger", action="store_true",
                         help="Pula a checagem de livro de bugs nesta rodada (não atualiza o histórico)")
    parser.add_argument("--fix-encoding", action="store_true",
                         help="Corrige automaticamente: normaliza toda quebra de linha pra LF, "
                              "remove BOM, garante quebra de linha final. Só mexe em byte de "
                              "formatação -- nunca em lógica. Roda em TODO o projeto (.py/.json/"
                              ".jsonl/.md), não só nas pastas de código.")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    only = [x.strip() for x in args.only.split(",")] if args.only else None
    if args.no_ledger and only is None:
        only = list(ALL_CHECKS.keys())  # roda tudo, exceto bug_ledger
    baseline_path = Path(args.baseline).resolve() if args.baseline else None
    review_notes_path = Path(args.review_notes).resolve() if args.review_notes else None
    position_log_path = Path(args.position_log).resolve() if args.position_log else None
    bug_ledger_path = Path(args.bug_ledger).resolve() if args.bug_ledger else None

    report = run_audit(root, only=only, run_tests=args.run_tests,
                        baseline_path=baseline_path, update_baseline=args.update_baseline,
                        review_notes_path=review_notes_path, position_log_path=position_log_path,
                        bug_ledger_path=bug_ledger_path, fix_encoding=args.fix_encoding)

    output_json = json.dumps(report, indent=2, ensure_ascii=False)
    if args.out:
        Path(args.out).write_text(output_json, encoding="utf-8")
    if args.split_output:
        written = write_split_output(report, Path(args.split_output).resolve())
        print(f"[split-output] {len(written)} arquivos gravados em {args.split_output}", file=sys.stderr)
    if not args.split_output or args.out:
        print(output_json)

    if args.human:
        print_human_summary(report)

    # Exit codes pensados pra automação: 0=tudo ok, 1=crítico (bloqueia), 2=precisa revisão humana
    if report["summary"]["status"] == "FAIL":
        sys.exit(1)
    elif report["summary"]["status"] == "NEEDS_REVIEW":
        sys.exit(2)
    sys.exit(0)


if __name__ == "__main__":
    main()
