"""Guarda das pastas privadas do vault para os plugins dos agentes.

Decide se os argumentos de uma ferramenta (ler arquivo, buscar, terminal...) apontam para uma
pasta privada e tira de uma saída as linhas com o caminho dela. O plugin do OpenCode tem a mesma
regra em JavaScript (adapters/opencode/plugins/cofre.js).

O nome relativo (99-Privado) só conta quando o texto também aponta para o vault ou a sessão roda
dentro dele, para não bloquear nada em outros projetos que tenham uma pasta com o mesmo nome.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from .config import vault_configurado
from .vault import Cofre

MENSAGEM = ("Bloqueado pelo cofre: esse caminho fica numa pasta privada do usuário (99-Privado ou pastas_privadas "
            "do cofre). Não tente outro caminho nem outro comando; se precisar do conteúdo, peça ao usuário.")


def _normal(texto) -> str:
    return str(texto).replace("\\", "/").lower()


def _textos(valor, saida: list[str] | None = None) -> list[str]:
    saida = [] if saida is None else saida
    if isinstance(valor, str):
        saida.append(valor)
    elif isinstance(valor, dict):
        for v in valor.values():
            _textos(v, saida)
    elif isinstance(valor, (list, tuple)):
        for v in valor:
            _textos(v, saida)
    return saida


def caminhos(cofre: Cofre, vault: Path | None = None) -> dict:
    """Vault e pastas privadas como configurados e resolvidos (symlink, /var -> /private/var no
    macOS, nome curto 8.3 no Windows): a IA pode usar qualquer uma das formas."""
    raizes = list(dict.fromkeys([str(vault or cofre.raiz), str(cofre.raiz.resolve())]))
    absolutas = list(dict.fromkeys(os.path.join(r, *p.split("/")) for r in raizes for p in cofre.pastas_privadas()))
    return {"vaults": raizes, "absolutas": absolutas, "relativas": cofre.pastas_privadas()}


class Guarda:
    def __init__(self, vaults, absolutas, relativas):
        casa = _normal(os.path.expanduser("~"))

        def til(p: str) -> str:
            return "~" + p[len(casa):] if casa and p.startswith(casa + "/") else p

        abs_ = [_normal(p) for p in absolutas if p]
        vs = [_normal(v) for v in vaults if v]
        self.absolutas = list(dict.fromkeys(abs_ + [til(p) for p in abs_]))
        self.relativas = [_normal(p) for p in relativas if p]
        self.vaults = list(dict.fromkeys(vs + [til(v) for v in vs]))

    @classmethod
    def do_cofre(cls, cofre: Cofre, vault: Path | None = None) -> "Guarda":
        c = caminhos(cofre, vault)
        return cls(c["vaults"], c["absolutas"], c["relativas"])

    @classmethod
    def configurada(cls) -> "Guarda":
        vault = vault_configurado()
        return cls.do_cofre(Cofre(vault.resolve()), vault)

    def na_vault(self, cwd) -> bool:
        aqui = _normal(cwd or "") + "/"
        return bool(cwd) and any(aqui.startswith(v + "/") for v in self.vaults)

    def menciona(self, texto, na_vault: bool = False) -> bool:
        n = _normal(texto)
        if any(p in n for p in self.absolutas):
            return True
        return (na_vault or any(v in n for v in self.vaults)) and any(p in n for p in self.relativas)

    def toca(self, args, cwd=None) -> bool:
        na = self.na_vault(cwd)
        for t in _textos(args):
            if self.menciona(t, na):
                return True
            if cwd and len(t) < 1000 and "\n" not in t and self.menciona(os.path.normpath(os.path.join(cwd, t)), na):
                return True
        return False

    def filtrar(self, texto: str, cwd=None) -> str:
        """Tira as linhas que citam a pasta privada. Resultado em JSON (o terminal do Hermes devolve
        {"output": "..."} numa linha só) é filtrado por dentro dos textos, sem quebrar a estrutura."""
        na = self.na_vault(cwd)
        if texto.lstrip()[:1] in ("{", "["):
            try:
                dados = json.loads(texto)
            except ValueError:
                dados = None
            if dados is not None:
                return json.dumps(self._filtrar_valor(dados, na), ensure_ascii=False)
        return self._filtrar_linhas(texto, na)

    def _filtrar_linhas(self, texto: str, na: bool) -> str:
        return "\n".join(ln for ln in texto.split("\n") if not self.menciona(ln, na))

    def _filtrar_valor(self, valor, na: bool):
        if isinstance(valor, str):
            return self._filtrar_linhas(valor, na)
        if isinstance(valor, dict):
            return {k: self._filtrar_valor(v, na) for k, v in valor.items()}
        if isinstance(valor, list):
            return [self._filtrar_valor(v, na) for v in valor]
        return valor
