"""Regras epistêmicas: evidências, conferência automática, similaridade e segredos."""

from __future__ import annotations

import os
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from .config import ErroCofre

SEP = " :: "
TIPOS_EVIDENCIA = {
    "arquivo": "caminho[:linha] do arquivo + trecho copiado dele",
    "comando": "comando executado + trecho da saída",
    "url": "URL da documentação oficial + trecho citado",
    "usuario": "'conversa' + citação literal do usuário",
    "nota": "ID de outra nota do cofre + trecho",
}
FONTE_POR_EVIDENCIA = {
    "usuario": "usuario",
    "comando": "execucao",
    "arquivo": "arquivo",
    "url": "documentacao",
    "nota": "nota",
}
_PRIORIDADE_FONTE = ["usuario", "execucao", "arquivo", "documentacao", "nota"]
_MAX_LEITURA = 5 * 1024 * 1024


@dataclass
class Evidencia:
    tipo: str
    ref: str
    trecho: str

    def texto(self) -> str:
        return f"{self.tipo}{SEP}{self.ref}{SEP}{self.trecho}"

    def legivel(self) -> str:
        return f"`{self.tipo}` {self.ref} — \"{self.trecho}\""


def ler_evidencia(item) -> Evidencia:
    if isinstance(item, Evidencia):
        ev = item
    elif isinstance(item, dict):
        ev = Evidencia(
            str(item.get("tipo", "")).strip().lower(),
            str(item.get("ref", "")).strip(),
            str(item.get("trecho", "")).strip(),
        )
    else:
        bruto = str(item)
        if SEP in bruto:
            partes = bruto.split(SEP, 2)
        elif "::" in bruto:
            partes = bruto.split("::", 2)
        else:
            partes = bruto.split(" | ", 2)
        partes = [p.strip() for p in partes]
        while len(partes) < 3:
            partes.append("")
        ev = Evidencia(partes[0].lower(), partes[1], partes[2])
    ev.trecho = ev.trecho.strip().strip("`").strip()
    if ev.tipo not in TIPOS_EVIDENCIA:
        raise ErroCofre(
            f"Tipo de evidência inválido: '{ev.tipo}'. Use um de: "
            + ", ".join(f"{k} ({v})" for k, v in TIPOS_EVIDENCIA.items())
        )
    if not ev.ref:
        raise ErroCofre(f"Evidência '{ev.tipo}' sem 'ref'. Esperado: {TIPOS_EVIDENCIA[ev.tipo]}.")
    if not ev.trecho:
        raise ErroCofre(
            f"Evidência '{ev.tipo}' sem 'trecho'. Copie o trecho exato que comprova a afirmação "
            f"({TIPOS_EVIDENCIA[ev.tipo]})."
        )
    if "\n" in ev.ref:
        raise ErroCofre("A 'ref' da evidência deve ter uma linha só.")
    ev.trecho = " ".join(ev.trecho.split())[:400]
    return ev


def ler_evidencias(itens) -> list[Evidencia]:
    if not itens:
        return []
    if isinstance(itens, (str, dict)):
        itens = [itens]
    return [ler_evidencia(i) for i in itens]


def fonte_de(evidencias: list[Evidencia]) -> str:
    fontes = {FONTE_POR_EVIDENCIA[e.tipo] for e in evidencias}
    for f in _PRIORIDADE_FONTE:
        if f in fontes:
            return f
    return "inferencia"


def _compactar(texto: str) -> str:
    return " ".join(texto.split())


def separar_ref_arquivo(ref: str) -> tuple[str, int | None]:
    m = re.match(r"^(.*?)(?::(\d+)(?:-\d+)?)?$", ref.strip())
    caminho = m.group(1) if m else ref
    linha = int(m.group(2)) if m and m.group(2) else None
    return caminho, linha


def conferir_arquivo(ev: Evidencia, bases: list[str]) -> tuple[bool | None, str]:
    """(True, onde) se o trecho existe no arquivo; (False, motivo) se não confere;
    (None, motivo) se o arquivo não foi localizado."""
    caminho, _ = separar_ref_arquivo(ev.ref)
    caminho = os.path.expanduser(caminho.strip().strip("`\"'"))
    candidatos = [Path(caminho)] if os.path.isabs(caminho) else [Path(b) / caminho for b in bases]
    for candidato in candidatos:
        if candidato.is_file():
            try:
                with open(candidato, "r", encoding="utf-8", errors="replace") as f:
                    conteudo = f.read(_MAX_LEITURA)
            except OSError as e:
                return None, f"não foi possível ler {candidato}: {e}"
            if _compactar(ev.trecho) in _compactar(conteudo):
                return True, str(candidato)
            return False, f"o trecho \"{ev.trecho[:80]}\" NÃO existe em {candidato}"
    tentados = ", ".join(str(c) for c in candidatos) or "(nenhuma pasta base conhecida)"
    return None, f"arquivo não encontrado: {caminho} (procurado em: {tentados}). Use caminho absoluto."


# ---- similaridade ---------------------------------------------------------
_PARADAS = {
    "a", "o", "e", "de", "do", "da", "dos", "das", "em", "no", "na", "nos", "nas", "um", "uma",
    "que", "para", "por", "com", "os", "as", "ao", "aos", "se", "sua", "seu", "esta", "este",
    "the", "is", "are", "of", "to", "in", "on", "and", "for", "with", "it", "be",
    "usa", "usam", "usar", "usado", "usada", "utiliza", "utilizam", "projeto", "sistema", "app", "aplicacao",
    "feito", "feita", "fica", "ficam", "tem", "sao", "estao", "foi", "ser", "atual", "atualmente",
    "uses", "use", "used", "project", "system", "has",
}
_NEGACOES = {"nao", "nunca", "sem", "nenhum", "nenhuma", "not", "never", "without"}


def _radical(t: str) -> str:
    return t[:5] if t.isalpha() and len(t) > 5 else t


def tokens(texto: str) -> set[str]:
    """Tokens normalizados (sem acento, minúsculos, radical de 5 letras) para comparar afirmações."""
    normal = unicodedata.normalize("NFKD", str(texto)).encode("ascii", "ignore").decode().lower()
    base = {_radical(t) for t in re.findall(r"[a-z0-9_.@/+-]+", normal) if len(t) >= 2 and t not in _PARADAS}
    return base | {t for t in re.findall(r"[a-z]+", normal) if t in _NEGACOES}


def similaridade(a: str, b: str) -> float:
    """Maior entre Jaccard e sobreposição pelo menor conjunto (paráfrase que estende a outra)."""
    ta, tb = tokens(a) - _NEGACOES, tokens(b) - _NEGACOES
    if not ta or not tb:
        return 0.0
    comum = len(ta & tb)
    jaccard = comum / len(ta | tb)
    menor = min(len(ta), len(tb))
    sobreposicao = comum / menor if menor >= 2 else 0.0
    return max(jaccard, 0.9 * sobreposicao)


def polaridade_oposta(a: str, b: str) -> bool:
    return bool(tokens(a) & _NEGACOES) != bool(tokens(b) & _NEGACOES)


# ---- segredos -------------------------------------------------------------
SEGREDOS_FORTES = [
    ("chave de API (sk-...)", re.compile(r"\bsk-(?:ant-|proj-)?[A-Za-z0-9_\-]{20,}")),
    ("token do GitHub", re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})")),
    ("chave AWS", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("chave privada", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA |PGP )?PRIVATE KEY")),
    ("token do Slack", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}")),
    ("chave Google API", re.compile(r"\bAIza[0-9A-Za-z_\-]{35}\b")),
    ("URL com senha embutida", re.compile(r"\b[a-z][a-z0-9+.\-]*://[^\s:/@]+:[^\s@/]{3,}@[^\s/]+")),
]
SEGREDO_FRACO = (
    "senha/token em texto",
    re.compile(r"(?i)\b(?:senha|password|passwd|secret|api[_-]?key|access[_-]?token)\s*[:=]\s*['\"]?[^\s'\"]{8,}"),
)


def achar_segredos(texto: str, incluir_fracos: bool = False) -> list[str]:
    achados = [nome for nome, rx in SEGREDOS_FORTES if rx.search(texto or "")]
    if incluir_fracos and SEGREDO_FRACO[1].search(texto or ""):
        achados.append(SEGREDO_FRACO[0])
    return achados


def barrar_segredos(*textos: str) -> None:
    for texto in textos:
        achados = achar_segredos(texto or "")
        if achados:
            raise ErroCofre(
                "Conteúdo bloqueado: parece conter credencial (" + ", ".join(achados) + "). "
                "Nunca grave segredos no cofre; registre só onde a credencial fica (ex.: 'variável STRIPE_KEY no .env')."
            )
