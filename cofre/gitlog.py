"""Commit automático das escritas no vault (trilha de auditoria: quem gravou o quê)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def _git(raiz: Path, *args: str, timeout: int = 15) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(raiz), *args], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)


def commit(raiz: Path, caminhos: list[Path], mensagem: str, habilitado: bool = True) -> bool:
    if not habilitado or not (Path(raiz) / ".git").exists() or not caminhos:
        return False
    rels = []
    for c in caminhos:
        try:
            rels.append(Path(c).resolve().relative_to(Path(raiz).resolve()).as_posix())
        except ValueError:
            continue
    if not rels:
        return False
    try:
        _git(raiz, "add", "--", *rels)
        r = _git(raiz, "commit", "-q", "--no-verify", "-m", mensagem, "--", *rels)
        if r.returncode != 0 and "tell me who you are" in (r.stderr or "").lower():
            r = _git(
                raiz, "-c", "user.name=cofre", "-c", "user.email=cofre@localhost",
                "commit", "-q", "--no-verify", "-m", mensagem, "--", *rels,
            )
        return r.returncode == 0
    except (OSError, subprocess.SubprocessError) as e:
        print(f"[cofre] git commit falhou: {e}", file=sys.stderr)
        return False
