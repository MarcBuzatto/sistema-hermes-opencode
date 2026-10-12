"""Leitura e escrita do frontmatter YAML das notas.

Suporta o subconjunto que o Obsidian usa em propriedades: escalares, listas inline
e listas em bloco. Mapas aninhados não são suportados (as notas do cofre não usam).
Implementado sem dependências para rodar em qualquer Python >= 3.9.
"""

from __future__ import annotations

import re
from typing import Any

_DATA = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_INT = re.compile(r"^-?\d+$")
_FLOAT = re.compile(r"^-?\d+\.\d+$")
_CHAVE = re.compile(r"^([A-Za-z_][\w\-]*)\s*:(?:\s+(.*)|\s*)$")
_ITEM = re.compile(r"^\s*-(?:\s+(.*)|\s*)$")
_RESERVADAS = {"true", "false", "null", "~", "yes", "no", "on", "off"}


def separar(texto: str) -> tuple[dict, str]:
    """Separa (meta, corpo). Sem frontmatter válido retorna ({}, texto)."""
    texto = texto.replace("\r\n", "\n")
    if texto.startswith("\ufeff"):
        texto = texto[1:]
    if not texto.startswith("---"):
        return {}, texto
    linhas = texto.split("\n")
    if linhas[0].strip() != "---":
        return {}, texto
    for i in range(1, len(linhas)):
        if linhas[i].strip() in ("---", "..."):
            meta = parse("\n".join(linhas[1:i]))
            corpo = "\n".join(linhas[i + 1:])
            return meta, corpo
    return {}, texto


def parse(bloco: str) -> dict:
    meta: dict[str, Any] = {}
    chave_aberta: str | None = None
    itens: list = []
    for bruta in bloco.split("\n"):
        if not bruta.strip() or bruta.lstrip().startswith("#"):
            continue
        m_item = _ITEM.match(bruta)
        if chave_aberta is not None and m_item:
            itens.append(_escalar(m_item.group(1) or ""))
            continue
        if bruta[0].isspace():
            continue
        m = _CHAVE.match(bruta)
        if not m:
            continue
        if chave_aberta is not None:
            meta[chave_aberta] = itens if itens else None
            chave_aberta, itens = None, []
        chave, resto = m.group(1), (m.group(2) or "").strip()
        if resto == "":
            chave_aberta, itens = chave, []
        else:
            meta[chave] = _valor(resto)
    if chave_aberta is not None:
        meta[chave_aberta] = itens if itens else None
    return meta


def _valor(resto: str) -> Any:
    if resto.startswith("[") and not resto.startswith("[[") and resto.rstrip().endswith("]"):
        return _lista_inline(resto.strip()[1:-1])
    return _escalar(resto)


def _lista_inline(conteudo: str) -> list:
    itens, atual, aspas, prof = [], [], None, 0
    i = 0
    while i < len(conteudo):
        c = conteudo[i]
        if aspas:
            atual.append(c)
            if c == "\\" and aspas == '"' and i + 1 < len(conteudo):
                atual.append(conteudo[i + 1])
                i += 2
                continue
            if c == aspas:
                aspas = None
        elif c in "\"'":
            aspas = c
            atual.append(c)
        elif c == "[":
            prof += 1
            atual.append(c)
        elif c == "]":
            prof -= 1
            atual.append(c)
        elif c == "," and prof == 0:
            itens.append("".join(atual))
            atual = []
        else:
            atual.append(c)
        i += 1
    if "".join(atual).strip():
        itens.append("".join(atual))
    return [_escalar(x) for x in itens if x.strip()]


def _tirar_comentario(s: str) -> str:
    aspas = None
    for i, c in enumerate(s):
        if aspas:
            if c == aspas:
                aspas = None
        elif c in "\"'" and (i == 0 or s[i - 1].isspace()):
            aspas = c
        elif c == "#" and i > 0 and s[i - 1].isspace():
            return s[:i].rstrip()
    return s


def _escalar(bruto: str) -> Any:
    s = bruto.strip()
    if not s:
        return None
    if s[0] == '"':
        fim = _fim_aspas_duplas(s)
        if fim > 0:
            interno = s[1:fim]
            return (
                interno.replace("\\\\", "\x00")
                .replace('\\"', '"')
                .replace("\\n", "\n")
                .replace("\\t", "\t")
                .replace("\x00", "\\")
            )
    if s[0] == "'":
        j = 1
        while j < len(s):
            if s[j] == "'":
                if j + 1 < len(s) and s[j + 1] == "'":
                    j += 2
                    continue
                return s[1:j].replace("''", "'")
            j += 1
    s = _tirar_comentario(s)
    baixo = s.lower()
    if baixo in ("true", "yes"):
        return True
    if baixo in ("false", "no"):
        return False
    if baixo in ("null", "~"):
        return None
    if _INT.match(s):
        try:
            return int(s)
        except ValueError:
            return s
    if _FLOAT.match(s):
        return float(s)
    return s


def _fim_aspas_duplas(s: str) -> int:
    j = 1
    while j < len(s):
        if s[j] == "\\":
            j += 2
            continue
        if s[j] == '"':
            return j
        j += 1
    return -1


def _precisa_aspas(s: str) -> bool:
    if s != s.strip() or s.lower() in _RESERVADAS:
        return True
    if _INT.match(s) or _FLOAT.match(s):
        return True
    if s[0] in "[]{}&*!|>'\"%@`#,?:-":
        return True
    if ": " in s or " #" in s or s.endswith(":") or "\n" in s or "\t" in s:
        return True
    return False


def formatar(v: Any) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    s = str(v)
    if s == "":
        return '""'
    if _DATA.match(s):
        return s
    if _precisa_aspas(s):
        escapado = s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\t", "\\t")
        return f'"{escapado}"'
    return s


def dump(meta: dict) -> str:
    linhas = []
    for chave, valor in meta.items():
        if valor is None:
            linhas.append(f"{chave}:")
        elif isinstance(valor, (list, tuple)):
            if not valor:
                linhas.append(f"{chave}: []")
            else:
                linhas.append(f"{chave}:")
                linhas.extend(f"  - {formatar(item)}" for item in valor)
        else:
            linhas.append(f"{chave}: {formatar(valor)}")
    return "\n".join(linhas)


def compor(meta: dict, corpo: str) -> str:
    corpo = corpo.lstrip("\n")
    return f"---\n{dump(meta)}\n---\n{corpo}" + ("" if corpo.endswith("\n") else "\n")
