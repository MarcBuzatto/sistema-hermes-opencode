"""Associação diretório de trabalho -> projeto do cofre.

Cada nota de projeto declara `caminhos` (pastas locais) e `repos` (remotos git).
Caminhos do Windows e do WSL são tratados como equivalentes (C:/x == /mnt/c/x),
porque é comum rodar o Hermes no WSL e o OpenCode nativo no mesmo projeto.
"""

from __future__ import annotations

import os
import re
import subprocess

from .vault import Cofre, Nota, lista


def normalizar_caminho(caminho: str) -> str:
    s = os.path.expanduser(str(caminho).strip()).replace("\\", "/")
    m = re.match(r"^/mnt/([a-zA-Z])(/.*)?$", s)
    if m:
        s = f"{m.group(1)}:{m.group(2) or '/'}"
    if re.match(r"^[a-zA-Z]:", s):
        s = s.lower()
    if len(s) > 1:
        s = s.rstrip("/")
        if re.match(r"^[a-z]:$", s):
            s += "/"
    return s


def dentro_de(alvo: str, base: str) -> bool:
    if alvo == base:
        return True
    return alvo.startswith(base if base.endswith("/") else base + "/")


def normalizar_repo(url: str) -> str:
    u = str(url).strip().lower()
    u = re.sub(r"\.git/?$", "", u).rstrip("/")
    m = re.match(r"^[a-z0-9+.\-]+://(?:[^@/]+@)?([^/:]+)(?::\d+)?/(.+)$", u)
    if m:
        return f"{m.group(1)}/{m.group(2).strip('/')}"
    m = re.match(r"^(?:[^@/]+@)?([^/:]+):(?!\d+/)(.+)$", u)
    if m:
        return f"{m.group(1)}/{m.group(2).strip('/')}"
    return u.strip("/")


def remoto_git(cwd: str) -> str | None:
    try:
        saida = subprocess.run(
            ["git", "-C", str(cwd), "config", "--get", "remote.origin.url"],
            capture_output=True, text=True, timeout=3,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if saida.returncode != 0 or not saida.stdout.strip():
        return None
    return normalizar_repo(saida.stdout.strip())


def resolver_projeto(cofre: Cofre, cwd: str | None = None, explicito: str | None = None) -> Nota | None:
    ref = explicito or os.environ.get("COFRE_PROJETO")
    if ref:
        return cofre.projeto(ref)
    if not cwd:
        return None
    alvo = normalizar_caminho(os.path.abspath(cwd))
    melhor, tamanho = None, -1
    for nota in cofre.projetos().values():
        for caminho in lista(nota.meta.get("caminhos")):
            base = normalizar_caminho(caminho)
            if dentro_de(alvo, base) and len(base) > tamanho:
                melhor, tamanho = nota, len(base)
    if melhor:
        return melhor
    remoto = remoto_git(cwd)
    if remoto:
        for nota in cofre.projetos().values():
            if remoto in {normalizar_repo(r) for r in lista(nota.meta.get("repos"))}:
                return nota
    return None


def bases_de_arquivos(projeto: Nota | None, cwd: str | None) -> list[str]:
    """Pastas onde procurar arquivos citados como evidência relativa."""
    bases = []
    if cwd:
        bases.append(os.path.abspath(cwd))
    if projeto:
        for caminho in lista(projeto.meta.get("caminhos")):
            expandido = os.path.expanduser(str(caminho))
            if os.path.isdir(expandido):
                bases.append(expandido)
            else:
                convertido = _converter_caminho(expandido)
                if convertido and os.path.isdir(convertido):
                    bases.append(convertido)
    vistos, unicos = set(), []
    for b in bases:
        if b not in vistos:
            vistos.add(b)
            unicos.append(b)
    return unicos


def _converter_caminho(caminho: str) -> str | None:
    """Converte C:/x <-> /mnt/c/x conforme o sistema atual."""
    s = caminho.replace("\\", "/")
    m = re.match(r"^([a-zA-Z]):(/.*)?$", s)
    if m and os.name != "nt":
        return f"/mnt/{m.group(1).lower()}{m.group(2) or '/'}"
    m = re.match(r"^/mnt/([a-zA-Z])(/.*)?$", s)
    if m and os.name == "nt":
        return f"{m.group(1).upper()}:{m.group(2) or '/'}"
    return None
