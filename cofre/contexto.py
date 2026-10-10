"""Montagem do pacote de contexto e consultas (buscar/ler).

O pacote é o que os agentes recebem no início de cada sessão (e a cada chamada,
no plugin do OpenCode). Cada item vem rotulado com o status epistêmico para que
um modelo fraco não confunda hipótese com fato, e as afirmações refutadas aparecem
como "armadilhas" para não serem repetidas.
"""

from __future__ import annotations

from datetime import date

from . import epistemica as ep
from .projetos import resolver_projeto
from .vault import Cofre, Nota, agora, alvo_link, lista, para_data, secao

ROTULOS = {
    "verificado": "VERIFICADO",
    "hipotese": "HIPÓTESE",
    "contestado": "CONTESTADO",
    "refutado": "REFUTADO",
    "obsoleto": "OBSOLETO",
    "proposta": "PROPOSTA",
    "aceita": "ACEITA",
    "substituida": "SUBSTITUÍDA",
    "rejeitada": "REJEITADA",
}

REGRAS = [
    "Hierarquia de confiança: código/comando executado agora > usuário nesta conversa > VERIFICADO > HIPÓTESE > sua memória.",
    "Nunca apresente HIPÓTESE ou CONTESTADO como fato; diga 'hipótese do cofre, não verificada'.",
    "Nunca repita uma afirmação listada em Armadilhas (REFUTADO).",
    "Descobriu algo? cofre_registrar_fato (hipótese sem evidência; verificado só com evidência copiada do arquivo/comando).",
    "Errou ou o usuário corrigiu? cofre_atualizar_fato (contestar/refutar) com a correção — não só na conversa.",
    "Terminou uma etapa ou a conversa ficou longa? cofre_checkpoint (resumo, feito, próximos passos).",
    "Antes de afirmar algo sobre o projeto que não está aqui: cofre_buscar.",
]


def vencido(nota: Nota, ref: date | None = None) -> bool:
    limite = para_data(nota.meta.get("revisar_em"))
    return bool(limite and limite < (ref or date.today()))


def rotulo(nota: Nota) -> str:
    r = ROTULOS.get(nota.status, nota.status.upper() or "?")
    if nota.status == "verificado" and vencido(nota):
        r += "·VENCIDO (reverificar)"
    return r


def _curto(texto, n: int) -> str:
    t = " ".join(str(texto or "").split())
    return t if len(t) <= n else t[: n - 1].rstrip() + "…"


def _evid_resumo(nota: Nota) -> str:
    for bruto in lista(nota.meta.get("evidencia")):
        try:
            e = ep.ler_evidencia(bruto)
        except Exception:
            continue
        ref = e.ref
        if e.tipo == "arquivo":
            ref = ref.replace("\\", "/").rstrip("/").rsplit("/", 1)[-1]
        return f"{e.tipo} {_curto(ref, 50)}"
    return "sem evidência"


def linha_fato(cofre: Cofre, nota: Nota) -> str:
    afirm = _curto(nota.meta.get("afirmacao") or nota.nome, 160)
    if nota.status == "refutado":
        partes = [f"- {nota.id} · NÃO é verdade: \"{afirm}\""]
        if nota.meta.get("motivo"):
            partes.append(f"motivo: {_curto(nota.meta['motivo'], 120)}")
        correto = cofre.resolver_ref(nota.meta.get("substituido_por")) if nota.meta.get("substituido_por") else None
        if correto:
            partes.append(f"correto: {correto.id} \"{_curto(correto.meta.get('afirmacao'), 100)}\" [{rotulo(correto)}]")
        return " — ".join(partes)
    if nota.status == "verificado":
        extra = f"evid.: {_evid_resumo(nota)}, {nota.meta.get('verificado_em', '?')}"
        if vencido(nota):
            extra += ", VENCIDO: reverificar antes de confiar"
        return f"- {nota.id} · {afirm} ({extra})"
    if nota.status == "contestado":
        return f"- {nota.id} · {afirm} — conflito: {_curto(nota.meta.get('motivo'), 120)}"
    return f"- {nota.id} · {afirm} (por {nota.meta.get('registrado_por', '?')}, {nota.meta.get('registrado_em', '?')}) — NÃO confirmado"


def linha_decisao(nota: Nota) -> str:
    texto = _curto(secao(nota.corpo, "Decisão"), 140)
    quando = nota.meta.get("decidido_em") or nota.meta.get("registrado_em", "?")
    return f"- {nota.id} · {nota.meta.get('titulo', nota.nome)}: {texto} ({ROTULOS.get(nota.status, nota.status)}, {quando})"


def _ordenar_verificados(notas: list[Nota]) -> list[Nota]:
    return sorted(
        notas,
        key=lambda n: (n.meta.get("criticidade") == "alta", not vencido(n), str(n.meta.get("verificado_em", ""))),
        reverse=True,
    )


def _recentes(notas: list[Nota], chave: str) -> list[Nota]:
    return sorted(notas, key=lambda n: str(n.meta.get(chave, "")), reverse=True)


class _Secao:
    def __init__(self, titulo: str, itens: list[str], prioridade: int, minimo: int = 0, rodape: str = ""):
        self.titulo, self.itens, self.prioridade, self.minimo, self.rodape = titulo, itens, prioridade, minimo, rodape
        self.omitidos = 0

    def render(self) -> str:
        if not self.itens and not self.omitidos:
            return ""
        linhas = [f"## {self.titulo}"] + self.itens
        if self.omitidos:
            linhas.append(f"- (+{self.omitidos} omitidos — use cofre_buscar)")
        if self.rodape:
            linhas.append(self.rodape)
        return "\n".join(linhas)


def _ajustar(cabecalho: str, secoes: list[_Secao], maximo: int) -> str:
    def total() -> str:
        return "\n\n".join([cabecalho] + [s.render() for s in secoes if s.render()])

    texto = total()
    while len(texto) > maximo:
        candidatas = [s for s in secoes if len(s.itens) > s.minimo]
        if not candidatas:
            break
        alvo = max(candidatas, key=lambda s: s.prioridade)
        alvo.itens.pop()
        alvo.omitidos += 1
        texto = total()
    if len(texto) > maximo:
        texto = texto[: maximo - 40].rstrip() + "\n… (contexto truncado — use cofre_contexto)"
    return texto


def _secao_perfil(cofre: Cofre, limite: int) -> list[str]:
    perfil = cofre.perfil()
    if not perfil:
        return []
    linhas = [linha.strip() for linha in secao(perfil.corpo, "Preferências confirmadas").split("\n") if linha.strip().startswith("-")]
    return linhas[:limite]


def montar(cofre: Cofre, cwd: str | None = None, projeto: str | None = None, max_chars: int | None = None,
           modo: str = "completo") -> str:
    cfg = cofre.config()
    sistema = modo == "sistema"
    maximo = int(max_chars or (cfg["contexto_sistema_max_chars"] if sistema else cfg["contexto_max_chars"]))
    proj = cofre.projeto(projeto) if projeto else resolver_projeto(cofre, cwd)
    if modo == "ancora":
        return ancora(cofre, proj)

    fatos = cofre.por_tipo("fato")
    slug_p = proj.nome if proj else None
    do_escopo = [f for f in fatos if f.projeto in (slug_p, None)]
    secoes: list[_Secao] = []

    if proj:
        nome = proj.meta.get("nome") or slug_p
        cab = [f"# COFRE · contexto do projeto: {nome} ({slug_p})",
               ("" if sistema else f"Gerado {agora()} · ") + f"vault: {cofre.raiz} · pasta: {cofre.relativo(cofre.pasta_projeto(slug_p))}"]
        estado = cofre.estado(slug_p)
        if estado:
            itens = [f"Foco: {_curto(secao(estado.corpo, 'Foco atual'), 300)}"]
            prox = [linha for linha in secao(estado.corpo, "Próximos passos").split("\n") if linha.strip().startswith("-")]
            itens += [f"Próximo: {_curto(linha.lstrip('- ').replace('[ ] ', ''), 140)}" for linha in prox[:5] if "(nenhum" not in linha]
            bloq = [linha for linha in secao(estado.corpo, "Bloqueios").split("\n") if linha.strip().startswith("-")]
            itens += [f"Bloqueio: {_curto(linha.lstrip('- '), 140)}" for linha in bloq[:3] if "(nenhum" not in linha]
            por = estado.meta.get("atualizado_por", "?")
            rod = f"(atualizado {estado.meta.get('atualizado', '?')} por {por}" + (
                ")" if por == "usuario" else " — escrito por agente, confira no código)")
            secoes.append(_Secao("Estado atual", itens, prioridade=1, minimo=1, rodape=rod))
    else:
        cab = ["# COFRE · contexto geral (nenhum projeto associado a este diretório)",
               ("" if sistema else f"Gerado {agora()} · ") + f"vault: {cofre.raiz}"]
        if cwd:
            cab.append(f"Diretório: {cwd}. Se for um projeto, vincule com cofre_projeto(acao='vincular') ou crie um (se o usuário pedir).")
        projetos = sorted(cofre.projetos().values(), key=lambda n: n.nome)
        secoes.append(_Secao("Projetos", [
            f"- {n.nome} — {n.meta.get('nome', n.nome)} [{n.meta.get('status', '?')}]" for n in projetos
        ], prioridade=6))

    refutados = _recentes([f for f in do_escopo if f.status == "refutado"], "refutado_em")
    secoes.append(_Secao("Armadilhas — afirmações REFUTADAS (nunca repita)", [linha_fato(cofre, f) for f in refutados],
                         prioridade=2, minimo=min(3, len(refutados))))
    contestados = [f for f in do_escopo if f.status == "contestado"]
    secoes.append(_Secao("CONTESTADOS — verificar antes de usar", [linha_fato(cofre, f) for f in contestados], prioridade=4))
    verificados = _ordenar_verificados([f for f in do_escopo if f.status == "verificado"])
    limite_v = int(cfg.get("fatos_verificados_no_contexto", 15))
    sec_v = _Secao("Fatos VERIFICADOS — pode usar", [linha_fato(cofre, f) for f in verificados[:limite_v]], prioridade=5)
    sec_v.omitidos = max(0, len(verificados) - limite_v)
    secoes.append(sec_v)
    decisoes = [d for d in cofre.por_tipo("decisao") if d.projeto == slug_p]
    aceitas = _recentes([d for d in decisoes if d.status == "aceita"], "decidido_em")
    propostas = _recentes([d for d in decisoes if d.status == "proposta"], "registrado_em")
    secoes.append(_Secao("Decisões ACEITAS (vigentes)", [linha_decisao(d) for d in aceitas], prioridade=6))
    secoes.append(_Secao("Decisões PROPOSTAS (aguardando o usuário)", [linha_decisao(d) for d in propostas[:3]], prioridade=9))
    hipoteses = _recentes([f for f in do_escopo if f.status == "hipotese"], "registrado_em")
    sec_h = _Secao("HIPÓTESES abertas — NÃO trate como verdade", [linha_fato(cofre, f) for f in hipoteses[:10]],
                   prioridade=8)
    sec_h.omitidos = max(0, len(hipoteses) - 10)
    secoes.append(sec_h)
    missoes = [m for m in cofre.por_tipo("missao") if m.status == "ativa"
               and (not slug_p or slug_p in [alvo_link(p) for p in lista(m.meta.get("projetos"))])]
    secoes.append(_Secao("Missões ativas", [f"- {m.id} · {m.meta.get('titulo', m.nome)}" for m in missoes[:5]], prioridade=7))
    secoes.append(_Secao("Preferências do usuário (confirmadas)", _secao_perfil(cofre, 8), prioridade=7))
    if sistema or modo == "completo":
        secoes.append(_Secao("Regras do cofre", [f"{i}. {r}" for i, r in enumerate(REGRAS, 1)], prioridade=3,
                             minimo=len(REGRAS) if sistema else 3))
    return _ajustar("\n".join(cab), secoes, maximo)


def ancora(cofre: Cofre, proj: Nota | None) -> str:
    if not proj:
        return ("[cofre] Sem projeto associado. Lembrete: fatos novos -> cofre_registrar_fato; "
                "correções -> cofre_atualizar_fato; fim de etapa -> cofre_checkpoint.")
    estado = cofre.estado(proj.nome)
    foco = _curto(secao(estado.corpo, "Foco atual"), 160) if estado else "(sem estado)"
    prox = []
    if estado:
        prox = [_curto(linha.lstrip("- ").replace("[ ] ", ""), 60)
                for linha in secao(estado.corpo, "Próximos passos").split("\n") if linha.strip().startswith("- [ ]")][:2]
    return (
        f"[cofre · {proj.nome}] Foco: {foco}" + (f" · Próximos: {'; '.join(prox)}" if prox else "")
        + " · Lembrete: não trate hipótese como fato; registre descobertas/correções no cofre; checkpoint ao fim da etapa."
    )


# ---- consultas ------------------------------------------------------------
def buscar(cofre: Cofre, consulta: str, projeto: str | None = None, tipo: str | None = None,
           status=None, limite: int = 10, cwd: str | None = None) -> str:
    termos = ep.tokens(consulta)
    if not termos:
        return "Consulta vazia."
    proj = cofre.projeto(projeto) if projeto else None
    status_ok = {s.strip().lower() for s in lista(status)} if status else None
    resultados = []
    baixo = " ".join(str(consulta).lower().split())
    for n in cofre.notas():
        if tipo and tipo != "qualquer" and n.tipo != tipo:
            continue
        if n.tipo in ("config",):
            continue
        if status_ok and n.status not in status_ok:
            continue
        if proj and n.projeto not in (proj.nome, None) and n.nome != proj.nome:
            continue
        titulo = str(n.meta.get("afirmacao") or n.meta.get("titulo") or n.nome)
        alvo_tokens = ep.tokens(titulo + " " + n.corpo[:4000] + " " + " ".join(map(str, lista(n.meta.get("tags")))))
        comuns = termos & alvo_tokens
        if not comuns:
            continue
        pontos = len(comuns) / len(termos) + (0.5 if baixo in titulo.lower() else 0) + (0.3 if termos <= ep.tokens(titulo) else 0)
        resultados.append((pontos, n, titulo))
    if not resultados:
        return f"Nada encontrado para '{consulta}'. Lembre: ausência no cofre não prova que algo é falso."
    resultados.sort(key=lambda x: x[0], reverse=True)
    linhas = [f"Resultados para '{consulta}':"]
    for _, n, titulo in resultados[: max(1, int(limite))]:
        escopo = f" · projeto {n.projeto}" if n.projeto else (" · global" if n.tipo == "fato" else "")
        ident = n.id or n.nome
        st = f"[{rotulo(n)}] " if n.status else ""
        linhas.append(f"- {ident} {n.tipo} {st}{_curto(titulo, 140)}{escopo} — {cofre.relativo(n.caminho)}")
    return "\n".join(linhas)


def ler(cofre: Cofre, ref: str) -> str:
    nota = cofre.resolver_ref(ref) or cofre.projeto(ref)
    if not nota:
        return f"Nota '{ref}' não encontrada. Use cofre_buscar."
    aviso = ""
    if nota.tipo == "fato":
        aviso = {
            "verificado": "Pode usar." + (" ATENÇÃO: VENCIDO, reverifique." if vencido(nota) else ""),
            "hipotese": "NÃO confirmado: não trate como verdade.",
            "contestado": "Em conflito: verifique antes de usar.",
            "refutado": "FALSO: nunca repita esta afirmação.",
            "obsoleto": "Não vale mais.",
        }.get(nota.status, "")
    elif nota.tipo in ("sessao", "estado", "captura"):
        aviso = "Escrito por agente / bruto: não é fonte de verdade."
    cabeca = f"[{nota.tipo.upper()}" + (f" · {rotulo(nota)}" if nota.status else "") + f"] {aviso}".rstrip()
    return f"{cabeca}\nArquivo: {cofre.relativo(nota.caminho)}\n\n{nota.texto()}"
