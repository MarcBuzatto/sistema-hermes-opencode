"""Edição do config.yaml do Hermes com valores estruturados.

`hermes config set` não serve para listas e objetos: até a 0.19 ele grava JSON como texto, e o
MCP e o plugin ficam inválidos. Aqui o arquivo é editado pelo Python do próprio Hermes, que traz
PyYAML, com operações simples (ler, set, unset, add/remover em lista). Usado pelo instalador, pela
CLI (`cofre agentes sincronizar`) e pelo plugin do Hermes.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from .config import ErroCofre

# Também conserta valores que versões antigas do instalador gravaram como texto JSON.
MESCLA_YAML = r"""
import json, os, sys, tempfile
import yaml
caminho, ops = sys.argv[1], json.loads(sys.stdin.read())
dados = {}
if os.path.exists(caminho):
    with open(caminho, encoding="utf-8") as f:
        dados = yaml.safe_load(f) or {}
def texto_json(v):
    if isinstance(v, str) and v[:1] in "[{":
        try:
            return json.loads(v)
        except ValueError:
            pass
    return v
def no(chave, criar):
    atual = dados
    partes = chave.split(".")
    for p in partes[:-1]:
        if not isinstance(texto_json(atual.get(p)), dict):
            if not criar:
                return None, None
            atual[p] = {}
        atual[p] = texto_json(atual[p])
        atual = atual[p]
    return atual, partes[-1]
def lista(v):
    v = texto_json(v)
    return list(v) if isinstance(v, list) else ([v] if isinstance(v, str) and v else [])
saida = {}
for op, chave, valor in ops:
    pai, folha = no(chave, op not in ("ler", "unset", "remover"))
    if op == "ler":
        saida[chave] = texto_json(pai.get(folha)) if pai is not None else None
    elif op == "set":
        pai[folha] = valor
    elif op == "unset" and pai is not None:
        pai.pop(folha, None)
    elif op == "add":
        pai[folha] = [x for x in lista(pai.get(folha)) if x != valor] + [valor]
    elif op == "remover" and pai is not None and folha in pai:
        resto = [x for x in lista(pai.get(folha)) if x != valor]
        if resto:
            pai[folha] = resto
        else:
            pai.pop(folha)
if any(op != "ler" for op, _, _ in ops):
    os.makedirs(os.path.dirname(caminho) or ".", exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(caminho) or ".", prefix=".config.", suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        yaml.safe_dump(dados, f, sort_keys=False, allow_unicode=True)
    os.replace(tmp, caminho)
print(json.dumps(saida, ensure_ascii=False))
"""


def python_hermes(exe: str | None = None) -> Path | None:
    """Interpretador do Hermes (com PyYAML), achado a partir do comando `hermes`."""
    exe = exe or shutil.which("hermes")
    if not exe:
        return None
    alvo = Path(exe).resolve()
    candidatos: list[Path] = []
    if os.name == "nt":
        candidatos += [alvo.parent / "python.exe", alvo.parent.parent / "python.exe"]
    else:
        try:
            primeira = alvo.read_bytes()[:512].split(b"\n", 1)[0].decode("utf-8", "replace")
        except OSError:
            primeira = ""
        if primeira.startswith("#!"):
            partes = primeira[2:].strip().split()
            if partes and Path(partes[0]).name == "env" and len(partes) > 1:
                achado = shutil.which(partes[-1])
                if achado:
                    candidatos.append(Path(achado))
            elif partes:
                candidatos.append(Path(partes[0]))
        candidatos += [alvo.parent / "python3", alvo.parent / "python"]
    for candidato in candidatos:
        if tem_yaml(candidato):
            return candidato
    return None


def tem_yaml(python: Path) -> bool:
    try:
        return Path(python).is_file() and subprocess.run([str(python), "-c", "import yaml"], capture_output=True,
                                                         timeout=30).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def aplicar(python: Path | str, arquivo: Path, ops: list) -> dict:
    """Roda as operações; devolve os valores pedidos com 'ler'."""
    try:
        r = subprocess.run([str(python), "-c", MESCLA_YAML, str(arquivo)], input=json.dumps(ops), capture_output=True,
                           text=True, encoding="utf-8", errors="replace", timeout=60)
    except (OSError, subprocess.SubprocessError) as e:
        raise ErroCofre(f"não consegui editar {arquivo}: {e}") from e
    if r.returncode != 0:
        raise ErroCofre(f"não consegui editar {arquivo}: {(r.stderr or '').strip()[-300:]}")
    return json.loads(r.stdout or "{}")


def python_atual_tem_yaml() -> bool:
    try:
        import yaml  # noqa: F401
    except ImportError:
        return False
    return True


def config_padrao() -> Path:
    if os.environ.get("HERMES_HOME"):
        return Path(os.environ["HERMES_HOME"]) / "config.yaml"
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local") / "hermes"
    else:
        base = Path.home() / ".hermes"
    return base / "config.yaml"


def python_para_editar() -> Path | None:
    """Este Python, se tiver PyYAML (dentro do Hermes); senão o do comando `hermes`."""
    return Path(sys.executable) if python_atual_tem_yaml() else python_hermes()
