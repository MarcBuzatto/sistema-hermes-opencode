"""Busca por relevância: dado o texto da conversa, acha no vault o que tem a ver com ele.

É o que permite "falei de pentest, a IA lê o que existe sobre pentest": a cada mensagem
os plugins mandam o texto para cá e recebem de volta poucas linhas apontando as notas,
fatos, decisões, fontes e skills relacionadas, cada uma com o status.

- Ranqueamento BM25 com pesos por campo (título > tags/aliases/description > corpo).
- Tolerante a erro de digitação: radical de 5 letras ("penteast" e "pentest" viram
  "pente") e, para termos que não existem no vault, distância de edição 1.
- Indexa tudo que é nota do vault, inclusive notas livres sem `tipo` e as skills de
  `60-Skills` (SKILL.md e references/). Ignora 00-Sistema, modelos, exemplos e exportações.
- Índice em cache em `<vault>/.cofre/indice.json`, atualizado só para arquivos alterados.
"""

from __future__ import annotations

import json
import math
import os
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from . import frontmatter
from .vault import DIR_EXPORTACOES, IGNORAR_DIRS, PASTAS, Cofre, alvo_link, escrever_atomico, lista

VERSAO_INDICE = 4
ARQUIVO_INDICE = Path(".cofre") / "indice.json"
PESO_CAMPO = {"t": 3, "x": 2, "b": 1}
K1, B = 1.2, 0.75
MAX_CORPO = 12000
TIPOS_FORA = {"config", "perfil", "relatorio", "estado"}

_PARADAS = set("""
a o e de do da dos das em no na nos nas um uma uns umas que para por com os as ao aos se sua seu suas seus
esta este isto esse essa isso aquele aquela aquilo ja nao sim mas ou tambem como quando onde porque pois entao
muito muita muitos muitas mais menos bem so ainda agora aqui ali la eu tu ele ela nos voce voces eles elas me te
lhe nosso nossa meu minha teu tua dele dela deles delas ser estar ter haver fazer faz fez feito pode poder posso
podemos quero queria preciso precisa vou vai vamos estou esta estamos estao era foi sao tem tinha temos algo alguma
algum alguns coisa coisas tipo assim sobre entre ate desde sem sob apos cada todo toda todos todas outro outra
qual quais quem falando falar fala falei conversa conversar pergunta perguntar ajuda ajudar bora olha veja
acho achei sei saber sabe entao ok oi ola obrigado valeu certo beleza blz dai ai gente pessoal favor mim the is are was were be been of to in on at by for with from and or not this that these those it
its as an if then than so do does did have has had can could should would will just about into over what which
how why who when where you your we our they their i me my he she him her them us also very more most some any
""".split())


def termos(texto: str) -> list[str]:
    normal = unicodedata.normalize("NFKD", str(texto)).encode("ascii", "ignore").decode().lower()
    saida = []
    for t in re.findall(r"[a-z0-9]+", normal):
        if len(t) < 2 or t in _PARADAS or t.isdigit() and len(t) > 6:
            continue
        saida.append(t[:5] if t.isalpha() and len(t) > 5 else t)
    return saida


def _distancia_ate_1(a: str, b: str) -> bool:
    """Verdadeiro se a e b diferem por no máximo uma edição (inclui transposição)."""
    if a == b:
        return True
    la, lb = len(a), len(b)
    if abs(la - lb) > 1:
        return False
    if la == lb:
        dif = [i for i in range(la) if a[i] != b[i]]
        if len(dif) == 1:
            return True
        return len(dif) == 2 and dif[1] == dif[0] + 1 and a[dif[0]] == b[dif[1]] and a[dif[1]] == b[dif[0]]
    if la > lb:
        a, b = b, a
    i = j = 0
    pulou = False
    while i < len(a) and j < len(b):
        if a[i] != b[j]:
            if pulou:
                return False
            pulou = True
            j += 1
            continue
        i += 1
        j += 1
    return True


# ---- índice ----------------------------------------------------------------
def _ignorar_dir(raiz: Path, pasta: Path, nome: str) -> bool:
    if nome in IGNORAR_DIRS or nome.startswith("."):
        return True
    rel = (pasta / nome).relative_to(raiz).as_posix()
    return rel in (PASTAS["sistema"], DIR_EXPORTACOES)


def _arquivos(raiz: Path):
    for pasta, dirs, arquivos in os.walk(raiz):
        p = Path(pasta)
        dirs[:] = [d for d in dirs if not _ignorar_dir(raiz, p, d)]
        for nome in arquivos:
            if nome.endswith(".md") and not nome.startswith(".") and nome != "LEIA-ME.md":
                yield p / nome


def _primeira_linha(corpo: str) -> str:
    for linha in corpo.split("\n"):
        if linha.lstrip().startswith(("#", ">")):
            continue
        limpa = linha.strip()
        if not limpa or limpa.startswith(("![[", "---", "|")):
            continue
        return " ".join(limpa.split())[:220]
    return ""


_DATA_HORA = re.compile(r"\b\d{4}-\d{2}-\d{2}(?:[ T]\d{2}:\d{2})?\b")


def _corpo_util(corpo: str) -> str:
    """Corpo sem o que é moldura gerada pelo cofre (callouts, Histórico, datas)."""
    linhas, pular = [], False
    for linha in corpo.split("\n"):
        if linha.startswith("## "):
            pular = linha[3:].strip() in ("Histórico", "Log")
            continue
        if pular or linha.lstrip().startswith(">"):
            continue
        linhas.append(_DATA_HORA.sub(" ", linha))
    return "\n".join(linhas)


def _analisar(raiz: Path, caminho: Path, mtime: float) -> dict | None:
    try:
        texto = caminho.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    meta, corpo = frontmatter.separar(texto)
    if meta.get("exemplo"):
        return None
    rel = caminho.relative_to(raiz).as_posix()
    skill = None
    tipo = str(meta.get("tipo") or "")
    if rel.startswith(PASTAS["skills"] + "/"):
        partes = rel.split("/")
        if caminho.name == "SKILL.md":
            tipo, skill = "skill", caminho.parent.name
        else:
            idx = next((i for i in range(len(partes) - 1, 0, -1)
                        if (raiz / "/".join(partes[:i]) / "SKILL.md").is_file()), None)
            tipo = "skill-ref"
            skill = partes[idx - 1] if idx else None
    elif not tipo:
        tipo = "nota"
    if tipo in TIPOS_FORA:
        return None
    titulo_h1 = next((ln[2:].strip() for ln in corpo.split("\n") if ln.startswith("# ")), "")
    titulo = str(meta.get("afirmacao") or meta.get("titulo") or meta.get("nome") or meta.get("name")
                 or titulo_h1 or caminho.stem)
    extras = [str(x) for x in lista(meta.get("tags")) + lista(meta.get("aliases"))]
    extras += [str(meta.get(k)) for k in ("description", "id", "motivo") if meta.get(k)]
    if tipo == "skill-ref":
        extras.append(caminho.stem)
    tf: Counter = Counter()
    tx = set()
    for campo, conteudo in (("t", titulo), ("x", " ".join(extras)), ("b", _corpo_util(corpo)[:MAX_CORPO])):
        ts = termos(conteudo)
        for t in ts:
            tf[t] += PESO_CAMPO[campo]
        if campo != "b":
            tx.update(ts)
    return {
        "mtime": mtime,
        "tipo": tipo,
        "id": str(meta.get("id") or ""),
        "titulo": " ".join(titulo.split())[:200],
        "status": str(meta.get("status") or ""),
        "projeto": alvo_link(meta.get("projeto")),
        "origem": str(meta.get("origem") or meta.get("confiabilidade") or ""),
        "skill": skill,
        "resumo": " ".join(str(meta.get("description") or "").split())[:220] or _primeira_linha(corpo),
        "tf": dict(tf),
        "tx": sorted(tx),
        "len": sum(tf.values()),
    }


def carregar_indice(raiz: Path, salvar: bool = True) -> dict[str, dict]:
    raiz = Path(raiz)
    arq = raiz / ARQUIVO_INDICE
    antigo: dict = {}
    try:
        dados = json.loads(arq.read_text(encoding="utf-8"))
        if dados.get("versao") == VERSAO_INDICE:
            antigo = dados.get("docs", {})
    except (OSError, ValueError):
        pass
    novo: dict[str, dict] = {}
    mudou = False
    for caminho in _arquivos(raiz):
        rel = caminho.relative_to(raiz).as_posix()
        try:
            mtime = caminho.stat().st_mtime
        except OSError:
            continue
        doc = antigo.get(rel)
        if doc is None or doc.get("mtime") != mtime:
            doc = _analisar(raiz, caminho, mtime)
            mudou = True
            if doc is None:
                doc = {"mtime": mtime, "fora": True}
        novo[rel] = doc
    if set(antigo) - set(novo):
        mudou = True
    if mudou and salvar:
        try:
            escrever_atomico(arq, json.dumps({"versao": VERSAO_INDICE, "docs": novo}, ensure_ascii=False,
                                             separators=(",", ":")))
        except OSError:
            pass
    return {k: v for k, v in novo.items() if not v.get("fora")}


# ---- busca -------------------------------------------------------------------
@dataclass
class Achado:
    rel: str
    doc: dict
    pontos: float

    @property
    def chave(self) -> str:
        return self.doc.get("id") or self.rel


def _peso(doc: dict, projeto: str | None) -> float:
    tipo, status = doc.get("tipo"), doc.get("status")
    peso = {"skill": 1.3, "skill-ref": 1.0, "fato": 1.1, "decisao": 1.1, "fonte": 1.0, "nota": 1.0,
            "missao": 0.9, "cliente": 1.0, "projeto": 0.9, "sessao": 0.6, "captura": 0.5}.get(tipo, 0.9)
    if tipo == "fato":
        peso *= {"verificado": 1.15, "refutado": 1.15, "contestado": 1.0, "hipotese": 0.9, "obsoleto": 0.4}.get(status, 1)
    if tipo == "decisao" and status in ("substituida", "rejeitada"):
        peso *= 0.5
    if doc.get("projeto"):
        peso *= 1.3 if projeto and doc["projeto"] == projeto else 0.7
    return peso


def buscar(cofre: Cofre, texto: str, projeto: str | None = None, limite: int = 5, excluir=(),
           tipos=None, status=None, so_fortes: bool = True) -> list[Achado]:
    consulta = list(dict.fromkeys(termos(str(texto)[:4000])))
    if not consulta:
        return []
    docs = carregar_indice(cofre.raiz)
    if tipos:
        docs = {k: d for k, d in docs.items() if d.get("tipo") in set(tipos)}
    if status:
        docs = {k: d for k, d in docs.items() if d.get("status") in set(status)}
    if not docs:
        return []
    n = len(docs)
    df: Counter = Counter()
    for d in docs.values():
        df.update(d["tf"].keys())
    vocab = set(df)
    expandida: dict[str, list[str]] = {}
    for q in consulta:
        if q in vocab:
            expandida[q] = [q]
        elif len(q) >= 4:
            parecidos = [v for v in vocab if v[0] == q[0] and _distancia_ate_1(q, v)]
            if parecidos:
                expandida[q] = parecidos
    if not expandida:
        return []
    media = sum(d["len"] for d in docs.values()) / n or 1.0
    excluir = set(excluir)
    achados = []
    for rel, d in docs.items():
        if rel in excluir or (d.get("id") and d["id"] in excluir):
            continue
        tf, tx = d["tf"], set(d.get("tx", ()))
        pontos, forte, cobertos = 0.0, False, 0
        for termos_doc in expandida.values():
            melhor = 0.0
            for t in termos_doc:
                f = tf.get(t)
                if not f:
                    continue
                idf = math.log(1 + (n - df[t] + 0.5) / (df[t] + 0.5))
                melhor = max(melhor, idf * f * (K1 + 1) / (f + K1 * (1 - B + B * d["len"] / media)))
                if t in tx or (f >= 2 * PESO_CAMPO["b"] and (n < 4 or df[t] / n <= 0.5)):
                    forte = True
            pontos += melhor
            cobertos += melhor > 0
        if cobertos >= 2:
            forte = True
        if pontos <= 0 or (so_fortes and not forte):
            continue
        achados.append(Achado(rel, d, pontos * _peso(d, projeto)))
    achados.sort(key=lambda a: a.pontos, reverse=True)
    if achados and so_fortes:
        corte = achados[0].pontos * 0.35
        achados = [a for a in achados if a.pontos >= corte]
    return achados[: max(1, int(limite))]


# ---- formatação -------------------------------------------------------------
_ROTULO = {"verificado": "VERIFICADO", "hipotese": "HIPÓTESE", "contestado": "CONTESTADO", "refutado": "REFUTADO",
           "obsoleto": "OBSOLETO", "proposta": "PROPOSTA", "aceita": "ACEITA"}


def _curto(texto: str, n: int) -> str:
    t = " ".join(str(texto or "").split())
    return t if len(t) <= n else t[: n - 1].rstrip() + "…"


def linha(a: Achado) -> str:
    d = a.doc
    tipo, st = d.get("tipo"), d.get("status")
    if tipo == "skill":
        return f"- skill `{d['skill']}` — {_curto(d.get('resumo') or d['titulo'], 150)} (carregue a skill se servir)"
    if tipo == "skill-ref":
        return f"- referência da skill `{d.get('skill')}`: {_curto(d['titulo'], 80)} — cofre_ler \"{a.rel}\""
    if tipo == "fato":
        if st == "refutado":
            return f"- {d['id']} [REFUTADO] NÃO é verdade: \"{_curto(d['titulo'], 140)}\" — cofre_ler {d['id']}"
        return f"- {d['id']} [{_ROTULO.get(st, st.upper())}] {_curto(d['titulo'], 150)}"
    if tipo == "decisao":
        return f"- {d['id']} [decisão {_ROTULO.get(st, st)}] {_curto(d['titulo'], 140)}"
    if tipo == "fonte":
        return f"- {d['id']} [fonte {d.get('origem') or 'externa'}, não é fato] {_curto(d['titulo'], 110)} — cofre_ler {d['id']}"
    if tipo in ("sessao", "captura", "missao"):
        return f"- {d['id'] or a.rel} [{tipo}] {_curto(d['titulo'], 130)}"
    ref = d["id"] or f"\"{a.rel}\""
    resumo = f": {_curto(d['resumo'], 110)}" if d.get("resumo") and d["resumo"] != d["titulo"] else ""
    return f"- {tipo or 'nota'} {_curto(d['titulo'], 80)}{resumo} — cofre_ler {ref}"


def bloco(achados: list[Achado], max_chars: int = 1600) -> str:
    if not achados:
        return ""
    cab = "[cofre] Possivelmente relevante para esta mensagem (abra só o que servir; só VERIFICADO é fato):"
    linhas = [cab]
    for a in achados:
        candidata = linha(a)
        if len("\n".join(linhas + [candidata])) > max_chars:
            break
        linhas.append(candidata)
    return "\n".join(linhas) if len(linhas) > 1 else ""


def relevante(cofre: Cofre, texto: str, projeto: str | None = None, excluir=()) -> tuple[str, list[str]]:
    cfg = cofre.config()
    if not cfg.get("relevancia_ativa", True) or len(str(texto).strip()) < 3:
        return "", []
    achados = buscar(cofre, texto, projeto=projeto, limite=int(cfg.get("relevancia_max_itens", 5)), excluir=excluir)
    texto_bloco = bloco(achados, int(cfg.get("relevancia_max_chars", 1600)))
    usados = [a.chave for a in achados if linha(a) in texto_bloco]
    return texto_bloco, usados
