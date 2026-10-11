"""Busca por relevância: dado o texto da conversa, acha no vault o que tem a ver com ele.

É o que permite "falei de pentest, a IA lê o que existe sobre pentest": a cada mensagem
os plugins mandam o texto para cá e recebem de volta poucas linhas apontando as notas,
fatos, decisões, fontes e skills relacionadas, cada uma com o status.

- Ranqueamento BM25 com pesos por campo (título > tags/aliases/description > corpo).
- Radical: tira o plural e corta em RADICAL letras ("notificações" e "notificação" viram
  "notifi"). Erro de digitação: palavra da mensagem que não existe no vault casa com
  palavra inteira do título/tags/description a uma edição de distância ("penteast" ->
  "pentest"). A comparação é entre palavras inteiras, não entre radicais, para "seguir"
  não virar "segurança" nem "explica" virar "explain".
- Com projeto atual definido, o nome dele sai da consulta: já está no contexto e casaria
  com todos os fatos do projeto.
- Indexa tudo que é nota do vault, inclusive notas livres sem `tipo` e as skills de
  `60-Skills` (SKILL.md e references/). Ignora 00-Sistema, modelos, exemplos e exportações.
- Índice em cache em `<vault>/.cofre/indice.json`, atualizado só para arquivos alterados,
  e em memória nos processos que ficam abertos. Avaliação: tests/avaliacao_relevancia.py.
"""

from __future__ import annotations

import json
import math
import os
import re
import time
import unicodedata
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from . import frontmatter
from .vault import DIR_EXPORTACOES, GERACAO, IGNORAR_DIRS, PASTAS, Cofre, alvo_link, escrever_atomico, lista

VERSAO_INDICE = 6
RADICAL = 6
PESO_APROXIMADO = 0.8
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
acho achei sei saber sabe entao ok oi ola obrigado valeu certo beleza blz dai ai gente pessoal favor mim
projeto projetos cliente clientes escreve escrever escrevo escreva escrevendo explica explicar explique mostra mostrar
mostre pede pedir pedindo manda mandar mande deixa deixar coloca colocar segue seguir continua continuar parou
servindo servir falta faltando faltou usa usar uso usando use usam versao versoes version hoje ontem amanha depois antes nesse nessa neste nessa disso desse dessa daquele the is are was were be been of to in on at by for with from and or not this that these those it
its as an if then than so do does did have has had can could should would will just about into over what which
how why who when where you your we our they their i me my he she him her them us also very more most some any
""".split())


def radical(palavra: str) -> str:
    if not palavra.isalpha():
        return palavra
    if len(palavra) > 4 and palavra.endswith("s") and not palavra.endswith("ss"):
        palavra = palavra[:-1]
    return palavra[:RADICAL]


def palavras(texto: str) -> list[str]:
    normal = unicodedata.normalize("NFKD", str(texto)).encode("ascii", "ignore").decode().lower()
    return [t for t in re.findall(r"[a-z0-9]+", normal)
            if len(t) >= 2 and t not in _PARADAS and not (t.isdigit() and len(t) > 6)]


def termos(texto: str) -> list[str]:
    return [radical(t) for t in palavras(texto)]


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
def _arquivos(raiz: Path):
    """(caminho relativo posix, caminho absoluto, mtime) de cada nota indexável."""
    fora = {PASTAS["sistema"], DIR_EXPORTACOES}
    pilha = [("", str(raiz))]
    while pilha:
        prefixo, pasta = pilha.pop()
        try:
            entradas = list(os.scandir(pasta))
        except OSError:
            continue
        for e in entradas:
            nome = e.name
            if nome.startswith("."):
                continue
            rel = prefixo + nome
            try:
                if e.is_dir():
                    if nome not in IGNORAR_DIRS and rel not in fora:
                        pilha.append((rel + "/", e.path))
                elif nome.endswith(".md") and nome != "LEIA-ME.md":
                    yield rel, e.path, e.stat().st_mtime
            except OSError:
                continue


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
    extras += [str(meta.get(k)) for k in ("description", "id", "motivo", "quando_usar") if meta.get(k)]
    url = str(meta.get("url") or meta.get("link") or "")
    if url:
        extras.append(url)
    if tipo == "skill-ref":
        extras.append(caminho.stem)
    tf: Counter = Counter()
    tx = set()
    inteiras = set()
    for campo, conteudo in (("t", titulo), ("x", " ".join(extras)), ("b", _corpo_util(corpo)[:MAX_CORPO])):
        ps = palavras(conteudo)
        ts = [radical(p) for p in ps]
        for t in ts:
            tf[t] += PESO_CAMPO[campo]
        if campo != "b":
            tx.update(ts)
            inteiras.update(p for p in ps if p.isalpha() and radical(p) != p)
    return {
        "mtime": mtime,
        "tipo": tipo,
        "id": str(meta.get("id") or ""),
        "titulo": " ".join(titulo.split())[:200],
        "status": str(meta.get("status") or ""),
        "projeto": alvo_link(meta.get("projeto")),
        "origem": str(meta.get("origem") or meta.get("confiabilidade") or ""),
        "skill": skill,
        "url": url,
        "resumo": " ".join(str(meta.get("quando_usar") or meta.get("description") or "").split())[:220] or _primeira_linha(corpo),
        "tf": dict(tf),
        "tx": sorted(tx),
        "w": sorted(inteiras),
        "len": sum(tf.values()),
    }


_MEMORIA: dict[str, tuple[float, int, dict, dict]] = {}
MEMORIA_TTL = 5.0


def carregar_indice(raiz: Path, salvar: bool = True) -> dict[str, dict]:
    """Índice do vault. Em processos que ficam abertos (plugin do Hermes, servidor MCP), reaproveita
    o índice em memória por MEMORIA_TTL segundos, ou até o próprio processo gravar no vault."""
    raiz = Path(raiz)
    chave = str(raiz.resolve())
    em_memoria = _MEMORIA.get(chave)
    if em_memoria and em_memoria[1] == GERACAO[0] and time.monotonic() - em_memoria[0] < MEMORIA_TTL:
        return em_memoria[2]
    antigo: dict = em_memoria[3] if em_memoria else {}
    arq = raiz / ARQUIVO_INDICE
    if not antigo:
        try:
            dados = json.loads(arq.read_text(encoding="utf-8"))
            if dados.get("versao") == VERSAO_INDICE:
                antigo = dados.get("docs", {})
        except (OSError, ValueError):
            pass
    novo: dict[str, dict] = {}
    mudou = False
    for rel, caminho, mtime in _arquivos(raiz):
        doc = antigo.get(rel)
        if doc is None or doc.get("mtime") != mtime:
            doc = _analisar(raiz, Path(caminho), mtime)
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
    validos = {k: v for k, v in novo.items() if not v.get("fora")}
    _MEMORIA[chave] = (time.monotonic(), GERACAO[0], validos, novo)
    return validos


# ---- busca -------------------------------------------------------------------
@dataclass
class Achado:
    rel: str
    doc: dict
    pontos: float
    termos: frozenset = frozenset()
    no_titulo: frozenset = frozenset()

    @property
    def chave(self) -> str:
        return self.doc.get("id") or self.rel


def _peso(doc: dict, projeto: str | None) -> float:
    tipo, status = doc.get("tipo"), doc.get("status")
    peso = {"skill": 1.3, "instrucao": 1.3, "recurso": 1.2, "skill-ref": 1.0, "fato": 1.1, "decisao": 1.1,
            "fonte": 1.0, "nota": 1.0, "missao": 0.9, "cliente": 1.0, "projeto": 0.9, "sessao": 0.6,
            "captura": 0.5}.get(tipo, 0.9)
    if tipo == "fato":
        peso *= {"verificado": 1.15, "refutado": 1.15, "contestado": 1.0, "hipotese": 0.9, "obsoleto": 0.4}.get(status, 1)
    if tipo == "decisao" and status in ("substituida", "rejeitada"):
        peso *= 0.5
    if doc.get("projeto"):
        peso *= 1.3 if projeto and doc["projeto"] == projeto else 0.7
    return peso


def _termos_do_projeto(cofre: Cofre, projeto: str | None) -> set[str]:
    if not projeto:
        return set()
    nota = cofre.projeto(projeto)
    nomes = [projeto] + ([str(nota.meta.get("nome") or ""), nota.nome] if nota else [])
    return {t for n in nomes for t in termos(n)}


def buscar(cofre: Cofre, texto: str, projeto: str | None = None, limite: int = 5, excluir=(),
           tipos=None, status=None, so_fortes: bool = True) -> list[Achado]:
    originais = list(dict.fromkeys(palavras(str(texto)[:4000])))
    do_projeto = _termos_do_projeto(cofre, projeto)
    sem_projeto = [p for p in originais if radical(p) not in do_projeto]
    originais = sem_projeto or originais
    if not originais:
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
    # Palavras inteiras do vault: as que o radical encurtou (guardadas em "w") e as que já são o
    # próprio radical (chaves curtas de tf).
    inteiras = {t for t in vocab if len(t) <= RADICAL and t.isalpha()}
    for d in docs.values():
        inteiras.update(d.get("w", ()))
    expandida: dict[str, list[str]] = {}
    aproximados: set[str] = set()
    for p in originais:
        q = radical(p)
        if q in expandida:
            continue
        if q in vocab:
            expandida[q] = [q]
        elif len(p) >= 5 and p.isalpha():
            # Em palavras de 5 letras, só letra a mais ou a menos ("nexjs" -> "nextjs"); trocar
            # uma letra transforma palavra real em outra palavra real ("falta" -> "falha").
            parecidos = {radical(v) for v in inteiras
                         if v[0] == p[0] and abs(len(v) - len(p)) <= 1 and (len(p) >= 6 or len(v) != len(p))
                         and _distancia_ate_1(p, v)}
            parecidos &= vocab
            if parecidos:
                expandida[q] = sorted(parecidos)
                aproximados.add(q)
    if not expandida:
        return []
    media = sum(d["len"] for d in docs.values()) / n or 1.0
    excluir = set(excluir)
    achados = []
    for rel, d in docs.items():
        if rel in excluir or (d.get("id") and d["id"] in excluir):
            continue
        tf, tx = d["tf"], set(d.get("tx", ()))
        pontos, forte = 0.0, False
        cobertos, no_titulo = set(), set()
        for q, termos_doc in expandida.items():
            melhor = 0.0
            for t in termos_doc:
                f = tf.get(t)
                if not f:
                    continue
                idf = math.log(1 + (n - df[t] + 0.5) / (df[t] + 0.5))
                melhor = max(melhor, idf * f * (K1 + 1) / (f + K1 * (1 - B + B * d["len"] / media)))
                if t in tx:
                    no_titulo.add(q)
                if t in tx or (f >= 2 * PESO_CAMPO["b"] and (n < 4 or df[t] / n <= 0.5)):
                    forte = True
            pontos += melhor * (PESO_APROXIMADO if q in aproximados else 1.0)
            if melhor > 0:
                cobertos.add(q)
        if len(cobertos) >= 2:
            forte = True
        if pontos <= 0 or (so_fortes and not forte):
            continue
        achados.append(Achado(rel, d, pontos * _peso(d, projeto), frozenset(cobertos), frozenset(no_titulo)))
    achados.sort(key=lambda a: a.pontos, reverse=True)
    if achados and so_fortes:
        # Corte relativo, mas quem traz um assunto da mensagem que nenhuma nota acima cobriu
        # (casado no título/tags) fica: mensagens costumam falar de mais de uma coisa.
        corte = achados[0].pontos * 0.35
        mantidos, vistos = [], set()
        for a in achados:
            if a.pontos >= corte or a.no_titulo - vistos:
                mantidos.append(a)
                vistos |= a.termos
        achados = mantidos
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
    if tipo == "instrucao":
        return f"- instrução sua: {_curto(d['titulo'], 90)} — siga se a tarefa envolver isso; texto: cofre_ler \"{a.rel}\""
    if tipo == "recurso":
        onde = f" [abra: {d['url']}]" if d.get("url") else ""
        quando = f" — {_curto(d['resumo'], 110)}" if d.get("resumo") and d["resumo"] != d["titulo"] else ""
        return f"- recurso: {_curto(d['titulo'], 70)}{onde}{quando} — detalhes: cofre_ler \"{a.rel}\""
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
