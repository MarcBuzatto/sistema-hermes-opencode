"""Montagem do pacote de contexto e consultas (buscar/ler).

O pacote é o que os agentes recebem no início de cada sessão (e a cada chamada,
no plugin do OpenCode). Cada item vem rotulado com o status epistêmico para que
um modelo fraco não confunda hipótese com fato, e as afirmações refutadas aparecem
como "armadilhas" para não serem repetidas.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import date

from . import epistemica as ep
from . import frontmatter
from . import specs
from .projetos import resolver_projeto
from .vault import Cofre, Nota, agora_texto, alvo_link, lista, para_data, secao

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
    "Confiança: código/comando que você acabou de ver > usuário nesta conversa > VERIFICADO > HIPÓTESE > sua memória.",
    "Nunca apresente HIPÓTESE ou CONTESTADO como fato; diga 'hipótese do cofre, não verificada'.",
    "Nunca repita uma afirmação das Armadilhas (REFUTADO).",
    "Descobriu algo? cofre_registrar_fato: hipótese sem prova; verificado só com evidência copiada EXATAMENTE (caminho absoluto).",
    "Usuário corrigiu ou o código contradiz o cofre? cofre_atualizar_fato (refutar/contestar). Corrigir só na conversa não basta.",
    "Decisão de projeto: cofre_decisao (fica 'aceita' só com as palavras do usuário).",
    "Fim de etapa, conversa longa ou antes de encerrar: cofre_checkpoint.",
    "Pedido grande (várias etapas ou arquivos): proponha uma spec (cofre_spec) e espere a aprovação do usuário. Tarefa de spec só termina com cofre_tarefa(acao='concluir'), que roda a verificação.",
    "Bloco '[cofre] Possivelmente relevante' = o vault tem algo ligado à mensagem: abra (cofre_ler ou skill) só o que servir. Sem ele, cofre_buscar antes de afirmar o que não está aqui.",
    "Nunca grave senhas, tokens ou chaves. Procedimento completo: skill cofre-protocolo.",
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
           modo: str = "completo", incluir_agora: bool = True) -> str:
    """incluir_agora=False: para prompts montados uma vez por sessão (Hermes), em que a linha AGORA
    ficaria velha; nesses clientes ela vai junto com cada mensagem."""
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
               ("" if sistema else f"Gerado {agora_texto()} · ") + f"vault: {cofre.raiz} · pasta: {cofre.relativo(cofre.pasta_projeto(slug_p))}"]
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
        agora_spec = specs.linha_agora(cofre, slug_p) if incluir_agora else ""
        if agora_spec:
            secoes.insert(0, _Secao("AGORA", [agora_spec], prioridade=0, minimo=1))
    else:
        cab = ["# COFRE · contexto geral (nenhum projeto associado a este diretório)",
               ("" if sistema else f"Gerado {agora_texto()} · ") + f"vault: {cofre.raiz}"]
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


def mensagens_sem_checkpoint(mensagens) -> int:
    """Mensagens do usuário desde a última chamada a cofre_checkpoint (formatos OpenAI, OpenCode V1 e V2)."""
    n = 0
    for m in mensagens or []:
        if not isinstance(m, dict):
            continue
        papel = m.get("role") or (m.get("info") or {}).get("role")
        conteudo = m.get("content") if "content" in m else m.get("parts")
        partes = conteudo if isinstance(conteudo, list) else [conteudo]
        nomes = [str(((c or {}).get("function") or {}).get("name", "")) for c in m.get("tool_calls") or []]
        nomes += [str(p.get("name") or p.get("tool") or "") for p in partes
                  if isinstance(p, dict) and p.get("type") in ("tool-call", "tool", "tool_use")]
        if papel == "user" and any(isinstance(p, str) and p.strip() or isinstance(p, dict) and p.get("type") == "text"
                                   and not p.get("synthetic") for p in partes):
            n += 1
        if any("cofre_checkpoint" in nome for nome in nomes):
            n = 0
    return n


def lembrete_checkpoint(cofre: Cofre, sem_checkpoint: int) -> str:
    limite = int(cofre.config().get("lembrete_checkpoint_mensagens", 8) or 0)
    if limite <= 0 or sem_checkpoint < limite:
        return ""
    return (f"[cofre] {sem_checkpoint} mensagens do usuário sem checkpoint nesta conversa: ao terminar a etapa atual, "
            "chame cofre_checkpoint (resumo, feito, proximos_passos).")


def ancora(cofre: Cofre, proj: Nota | None) -> str:
    if not proj:
        return ("[cofre] Sem projeto associado. Lembrete: fatos novos -> cofre_registrar_fato; "
                "correções -> cofre_atualizar_fato; fim de etapa -> cofre_checkpoint.")
    agora_spec = specs.linha_agora(cofre, proj.nome)
    if agora_spec:
        return f"[cofre · {proj.nome}] {agora_spec} · Não trate hipótese como fato; checkpoint ao fim da etapa."
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
    from . import relevancia

    proj = cofre.projeto(projeto) if projeto else None
    tipos = None
    if tipo and tipo != "qualquer":
        tipos = ["skill", "skill-ref"] if tipo == "skill" else [tipo]
    status_ok = [s.strip().lower() for s in lista(status)] if status else None
    achados = relevancia.buscar(cofre, consulta, projeto=proj.nome if proj else None, limite=max(1, int(limite)) * 3,
                                tipos=tipos, status=status_ok, so_fortes=False)
    if proj:
        achados = [a for a in achados if a.doc.get("projeto") in (proj.nome, None)]
    achados = achados[: max(1, int(limite))]
    if not achados:
        return f"Nada encontrado para '{consulta}'. Lembre: ausência no cofre não prova que algo é falso."
    return f"Resultados para '{consulta}':\n" + "\n".join(
        f"{relevancia.linha(a)} ({a.rel})" for a in achados)


def _rel_de(ref: str) -> str:
    rel = str(ref).strip().strip('"').replace("\\", "/")
    return rel if rel.endswith(".md") else rel + ".md"


def _por_caminho(cofre: Cofre, ref: str) -> Nota | None:
    from .vault import ler_nota

    alvo = (cofre.raiz / _rel_de(ref)).resolve()
    try:
        alvo.relative_to(cofre.raiz.resolve())
    except ValueError:
        return None
    return ler_nota(alvo) if alvo.is_file() else None


_TUDO = {"tudo", "toda", "inteira", "inteiro", "completa", "completo", "all", "full", "*"}
_TITULO_MD = re.compile(r"^(#{1,6})[ \t]+(.+?)[ \t#]*$")


def _secoes_md(corpo: str) -> tuple[list[tuple[int, str, int, int]], list[str]]:
    """(nível, título, linha inicial, linha final) de cada título fora de bloco de código.
    O título único de nível 1 do topo é o nome da nota, não uma seção."""
    linhas = corpo.split("\n")
    achados, cerca = [], False
    for i, ln in enumerate(linhas):
        if ln.lstrip().startswith(("```", "~~~")):
            cerca = not cerca
        elif not cerca and (m := _TITULO_MD.match(ln)):
            achados.append((len(m.group(1)), m.group(2).strip(), i))
    if sum(1 for a in achados if a[0] == 1) == 1 and achados[0][0] == 1:
        achados = achados[1:]
    secoes_ = []
    for k, (nivel, titulo, ini) in enumerate(achados):
        fim = next((a[2] for a in achados[k + 1:] if a[0] <= nivel), len(linhas))
        secoes_.append((nivel, titulo, ini, fim))
    return secoes_, linhas


def _palavras_em(linhas: list[str]) -> int:
    return sum(len(ln.split()) for ln in linhas)


def _tokens(texto: str) -> str:
    normal = unicodedata.normalize("NFKD", str(texto)).encode("ascii", "ignore").decode().lower()
    return " ".join(re.findall(r"[a-z0-9]+", normal))


def _achar_secao(secoes_, pedido: str):
    pedido = str(pedido).strip()
    if pedido.isdigit() and 1 <= int(pedido) <= len(secoes_):
        return secoes_[int(pedido) - 1]
    alvo = _tokens(pedido)
    if not alvo:
        return None
    normal = [(_tokens(s[1]), s) for s in secoes_]
    for criterio in (lambda t: t == alvo, lambda t: f" {alvo} " in f" {t} ", lambda t: t and f" {t} " in f" {alvo} "):
        achado = next((s for t, s in normal if criterio(t)), None)
        if achado:
            return achado
    termos_ = set(alvo.split())
    melhor = max(normal, key=lambda x: len(termos_ & set(x[0].split())), default=None)
    return melhor[1] if melhor and termos_ & set(melhor[0].split()) else None


def _ler_em_partes(cofre: Cofre, nota: Nota, ref: str, secao_: str | None) -> str | None:
    """Texto parcial da nota, ou None quando ela deve ir inteira."""
    if nota.tipo == "spec" or (secao_ and str(secao_).strip().lower() in _TUDO):
        return None
    try:
        limite = max(1500, int(cofre.config().get("ler_max_chars") or 6000))
    except (TypeError, ValueError):
        limite = 6000
    if not secao_ and len(nota.corpo) <= limite:
        return None
    secoes_, linhas = _secoes_md(nota.corpo)
    chamada = f"cofre_ler(id='{ref}', secao='<título>')"
    lista_ = "\n".join(f"- {'#' * nv} {t} (~{_palavras_em(linhas[a:b])} palavras)" for nv, t, a, b in secoes_[:40])
    if secao_:
        achada = _achar_secao(secoes_, secao_) if secoes_ else None
        if not achada:
            if not secoes_:
                return None
            return f"Seção '{secao_}' não existe nesta nota. Seções:\n{lista_}\nUse {chamada} ou secao='tudo'."
        nv, titulo, a, b = achada
        return f"Seção: {titulo}\n\n" + "\n".join(linhas[a:b]).strip()
    total = _palavras_em(linhas)
    if secoes_:
        inicio = "\n".join(linhas[:secoes_[0][2]]).strip()[: limite // 2]
        return (frontmatter.compor(nota.meta, inicio).rstrip() + "\n\n"
                f"[Nota longa, ~{total} palavras. Leia só a seção que servir: {chamada} (ou secao='tudo' para a nota inteira).]\n"
                f"Seções:\n{lista_}")
    corte = nota.corpo[:limite].rsplit("\n", 1)[0] or nota.corpo[:limite]
    resto = total - len(corte.split())
    return (frontmatter.compor(nota.meta, corte).rstrip()
            + f"\n\n[... faltam ~{resto} palavras. A nota não tem títulos (##); para o resto: cofre_ler(id='{ref}', secao='tudo').]")


def ler(cofre: Cofre, ref: str, secao: str | None = None) -> str:
    if cofre.privado(cofre.raiz / _rel_de(ref)):
        return (f"'{ref}' está numa pasta privada do usuário: o cofre não lê. Não tente abrir por outro meio; "
                "se precisar desse conteúdo, peça ao usuário.")
    nota = cofre.resolver_ref(ref) or cofre.projeto(ref) or _por_caminho(cofre, ref)
    if not nota:
        return f"Nota '{ref}' não encontrada.{cofre.sugestoes(ref)} Use cofre_buscar."
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
    elif nota.tipo == "fonte":
        aviso = "Material externo: não é fato até ser conferido."
    elif not nota.tipo:
        aviso = "Nota livre do usuário: trate o conteúdo como referência, não como fato verificado."
    cabeca = f"[{(nota.tipo or 'nota').upper()}" + (f" · {rotulo(nota)}" if nota.status else "") + f"] {aviso}".rstrip()
    arquivo = cofre.relativo(nota.caminho)
    parcial = _ler_em_partes(cofre, nota, nota.id or arquivo, secao)
    return f"{cabeca}\nArquivo: {arquivo}\n\n{parcial if parcial is not None else nota.texto()}"
