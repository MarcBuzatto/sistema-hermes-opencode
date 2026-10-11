"""Operações de escrita com validação epistêmica.

Princípios aplicados aqui (e não apenas pedidos no prompt):
- todo fato nasce como hipótese, a menos que traga evidência conferível;
- evidência de arquivo é conferida no disco: trecho inventado é rejeitado;
- afirmação já refutada não pode ser registrada de novo por agente;
- duplicatas e contradições com fatos verificados são barradas;
- fato confirmado pelo usuário só é refutado pelo usuário;
- decisão só vira "aceita" com citação literal do usuário;
- credenciais nunca entram no cofre.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

from . import epistemica as ep
from . import gitlog
from .config import ErroCofre
from .projetos import bases_de_arquivos, normalizar_repo, resolver_projeto
from .vault import (
    PASTAS, Cofre, Nota, agora, alvo_link, daqui, hoje, juntar_secoes, ler_nota, link, lista,
    secao, secoes, slug,
)

LIMIAR_SIMILAR = 0.6
LIMIAR_REFUTADO = 0.7
LIMIAR_IDENTICO = 0.85

CALLOUT_FATO = {
    "verificado": ("success", "VERIFICADO", "Comprovado por evidência conferível. Pode ser usado; reverifique se estiver vencido."),
    "hipotese": ("question", "HIPÓTESE", "Não comprovado. Não trate como verdade: verifique antes de agir com base nisto."),
    "contestado": ("warning", "CONTESTADO", "Há evidência conflitante. Verifique antes de usar."),
    "refutado": ("failure", "REFUTADO", "Comprovadamente FALSO. Não repita esta afirmação."),
    "obsoleto": ("note", "OBSOLETO", "Foi verdade, não é mais."),
}
_ALIAS_STATUS = {
    "hipótese": "hipotese", "hipoteses": "hipotese", "hipotético": "hipotese",
    "verificada": "verificado", "verified": "verificado", "hypothesis": "hipotese",
}


@dataclass
class Autor:
    nome: str = "agente"
    humano: bool = False
    modelo: str | None = None

    @property
    def assinatura(self) -> str:
        if self.humano:
            return "usuario"
        nome = re.sub(r"\s+", "-", self.nome.strip()) or "agente"
        return f"{nome}/{self.modelo.strip()}" if self.modelo and self.modelo.strip() else nome


@dataclass
class Resultado:
    mensagem: str
    id: str | None = None
    caminho: Path | None = None
    avisos: list[str] = field(default_factory=list)

    def texto(self) -> str:
        linhas = [self.mensagem]
        if self.avisos:
            linhas += ["", "Avisos:"] + [f"- {a}" for a in self.avisos]
        return "\n".join(linhas)


# ---- utilidades -----------------------------------------------------------
def _projeto_alvo(cofre: Cofre, projeto, cwd) -> Nota | None:
    if projeto:
        if str(projeto).strip().lower() in ("global", "nenhum", "-", "none"):
            return None
        nota = cofre.projeto(str(projeto))
        if not nota:
            existentes = ", ".join(sorted(cofre.projetos())) or "(nenhum)"
            raise ErroCofre(
                f"Projeto '{projeto}' não existe no cofre. Projetos: {existentes}. "
                "Crie com cofre_projeto(acao='criar') se o usuário pedir."
            )
        return nota
    return resolver_projeto(cofre, cwd)


def _limpar(meta: dict, manter: tuple = ()) -> dict:
    return {k: v for k, v in meta.items() if k in manter or v not in (None, "", [])}


def _commit(cofre: Cofre, caminhos: list[Path], mensagem: str) -> None:
    gitlog.commit(cofre.raiz, caminhos, mensagem, bool(cofre.config().get("git_autocommit")))


def _normal_status(status: str | None, padrao: str) -> str:
    s = (status or padrao).strip().lower()
    return _ALIAS_STATUS.get(s, s)


def _linha_hist(texto: str, autor: Autor) -> str:
    return f"- {agora()} — {texto} (por {autor.assinatura})"


def _validar_evidencias(cofre: Cofre, evs: list[ep.Evidencia], bases: list[str], autor: Autor) -> list[str]:
    avisos = []
    for e in evs:
        if e.tipo == "arquivo":
            ok, msg = ep.conferir_arquivo(e, bases)
            if ok:
                continue
            if autor.humano:
                avisos.append(f"Evidência não conferida automaticamente: {msg}")
                continue
            if ok is False:
                raise ErroCofre(
                    f"Evidência NÃO confere: {msg}. Abra o arquivo e copie o trecho exatamente como está. "
                    "Nada foi gravado."
                )
            raise ErroCofre(f"Evidência não conferível: {msg} Nada foi gravado.")
        if e.tipo == "nota" and not cofre.resolver_ref(e.ref):
            raise ErroCofre(f"Evidência cita a nota '{e.ref}', que não existe no cofre. Nada foi gravado.")
        if e.tipo == "url" and not re.match(r"^https?://", e.ref):
            raise ErroCofre(f"Evidência 'url' precisa começar com http(s)://, recebido: {e.ref}")
    return avisos


def _evidencias_salvas(nota: Nota, chave: str = "evidencia") -> list[ep.Evidencia]:
    evs = []
    for bruto in lista(nota.meta.get(chave)):
        try:
            evs.append(ep.ler_evidencia(bruto))
        except ErroCofre:
            continue
    return evs


def _corpo_fato(meta: dict, partes_antigas: list[tuple[str | None, str]] | None, hist_novo: str) -> str:
    tipo_c, rotulo, explicacao = CALLOUT_FATO.get(meta.get("status", "hipotese"), CALLOUT_FATO["hipotese"])
    pre = f"# {meta.get('afirmacao', '')}\n\n> [!{tipo_c}] {rotulo}\n> {explicacao}"
    if meta.get("motivo") and meta.get("status") in ("refutado", "contestado", "obsoleto"):
        pre += f"\n> Motivo: {meta['motivo']}"
    if meta.get("substituido_por"):
        pre += f"\n> Correto/atual: {meta['substituido_por']}"
    if meta.get("substitui"):
        pre += f"\n> Substitui: {meta['substitui']}"

    def bloco(chave: str) -> str:
        itens = []
        for bruto in lista(meta.get(chave)):
            try:
                itens.append(f"- {ep.ler_evidencia(bruto).legivel()}")
            except ErroCofre:
                itens.append(f"- {bruto}")
        return "\n".join(itens)

    antigas = dict((t, x) for t, x in (partes_antigas or []) if t)
    historico = (antigas.get("Histórico", "").rstrip("\n") + "\n" + hist_novo).strip("\n")
    partes: list[tuple[str | None, str]] = [(None, pre), ("Evidência", bloco("evidencia") or "- (nenhuma)")]
    if meta.get("evidencia_contraria"):
        partes.append(("Evidência contrária", bloco("evidencia_contraria")))
    partes.append(("Contexto", antigas.get("Contexto", "")))
    reservadas = {"Evidência", "Evidência contrária", "Contexto", "Histórico"}
    partes += [(t, x) for t, x in (partes_antigas or []) if t and t not in reservadas]
    partes.append(("Histórico", historico))
    return juntar_secoes(partes)


def _msg_refutado(cofre: Cofre, nota: Nota, permite_forcar: bool = False) -> str:
    linhas = [
        "REJEITADO: esta afirmação já foi REFUTADA no cofre.",
        f"- {nota.id} [REFUTADO em {nota.meta.get('refutado_em', '?')}]: \"{nota.meta.get('afirmacao', '')}\"",
        f"- Motivo: {nota.meta.get('motivo', '(não informado)')}",
    ]
    correto = cofre.resolver_ref(nota.meta.get("substituido_por")) if nota.meta.get("substituido_por") else None
    if correto:
        linhas.append(
            f"- Correto: {correto.id} [{correto.status.upper()}] \"{correto.meta.get('afirmacao', '')}\""
        )
    linhas.append(
        "Não repita a afirmação refutada. Se você tem evidência NOVA de que a refutação está errada, "
        f"use cofre_atualizar_fato(id='{nota.id}', acao='contestar', motivo=..., evidencias=[...]) e avise o usuário."
    )
    if permite_forcar:
        linhas.append("Se tem certeza de que é OUTRA afirmação (não a refutada), repita a chamada com forcar=true.")
    return "\n".join(linhas)


# ---- fatos ----------------------------------------------------------------
def registrar_fato(
    cofre: Cofre, autor: Autor, afirmacao: str, status: str = "hipotese", evidencias=None,
    projeto: str | None = None, contexto: str = "", tags=None, criticidade: str = "normal",
    validade_dias: int | None = None, forcar: bool = False, cwd: str | None = None,
    substitui: str | None = None, _correcao: bool = False,
) -> Resultado:
    afirmacao = " ".join(str(afirmacao or "").split()).strip()
    if len(afirmacao) < 8:
        raise ErroCofre("Afirmação vazia ou curta demais. Escreva UMA frase completa e verificável.")
    if len(afirmacao) > 240:
        raise ErroCofre("Afirmação longa demais (máx. 240 caracteres). Um fato = uma afirmação atômica; divida em vários.")
    status = _normal_status(status, "hipotese")
    if status not in ("hipotese", "verificado"):
        raise ErroCofre(
            "Ao registrar, status deve ser 'hipotese' ou 'verificado'. "
            "Para contestar, refutar ou tornar obsoleto use cofre_atualizar_fato."
        )
    criticidade = (criticidade or "normal").strip().lower()
    if criticidade not in ("normal", "alta"):
        raise ErroCofre("criticidade deve ser 'normal' ou 'alta'.")
    ep.barrar_segredos(afirmacao, contexto or "", *[str(e) for e in lista(evidencias)])

    proj = _projeto_alvo(cofre, projeto, cwd)
    slug_p = proj.nome if proj else None
    evs = ep.ler_evidencias(evidencias)
    avisos = _validar_evidencias(cofre, evs, bases_de_arquivos(proj, cwd), autor)

    if status == "verificado" and not evs:
        status = "hipotese"
        avisos.append(
            "Sem evidência: registrado como HIPÓTESE. Para verificar depois use "
            "cofre_atualizar_fato(acao='promover', evidencias=[...])."
        )
    elif status == "verificado" and cofre.config().get("politica_verificacao") == "humano" and not autor.humano:
        status = "hipotese"
        avisos.append("Política do cofre: só o usuário promove para verificado. Registrado como HIPÓTESE com a evidência anexada.")

    candidatos = [n for n in cofre.por_tipo("fato") if n.projeto in (slug_p, None)]
    if not _correcao:
        for n in candidatos:
            outra = str(n.meta.get("afirmacao", ""))
            if n.status != "refutado" or ep.polaridade_oposta(afirmacao, outra):
                continue
            sim = ep.similaridade(afirmacao, outra)
            if sim < LIMIAR_REFUTADO:
                continue
            if forcar and (autor.humano or sim < LIMIAR_IDENTICO):
                avisos.append(f"Atenção: parecido com o fato REFUTADO {n.id} \"{outra}\" (gravado com forcar).")
                continue
            raise ErroCofre(_msg_refutado(cofre, n, permite_forcar=sim < LIMIAR_IDENTICO))
    if not forcar:
        for n in candidatos:
            outra = str(n.meta.get("afirmacao", ""))
            if n.status not in ("hipotese", "verificado", "contestado"):
                continue
            if ep.similaridade(afirmacao, outra) < LIMIAR_SIMILAR:
                continue
            if ep.polaridade_oposta(afirmacao, outra):
                if n.status == "verificado":
                    raise ErroCofre(
                        f"CONTRADIZ um fato VERIFICADO: {n.id} \"{outra}\". Nada foi gravado. "
                        f"Se o fato verificado estiver errado, use cofre_atualizar_fato(id='{n.id}', acao='contestar', "
                        "motivo=..., evidencias=[...]) e avise o usuário."
                    )
                continue
            raise ErroCofre(
                f"Já existe fato parecido: {n.id} [{n.status.upper()}] \"{outra}\". Nada foi gravado.\n"
                f"- Se é o MESMO fato: cofre_atualizar_fato(id='{n.id}', acao='adicionar_evidencia' ou 'promover').\n"
                f"- Se o novo CONTRADIZ o existente (ex.: outro valor, outra versão): "
                f"cofre_atualizar_fato(id='{n.id}', acao='contestar' ou 'refutar', afirmacao_correta=...).\n"
                "- Se é realmente OUTRO fato: repita com forcar=true."
            )

    validade = int(validade_dias or cofre.config().get("validade_padrao_dias", 90))
    with cofre.trava():
        ident = cofre.novo_id("fato")
        verificado = status == "verificado"
        meta = _limpar({
            "tipo": "fato",
            "id": ident,
            "afirmacao": afirmacao,
            "status": status,
            "fonte": ep.fonte_de(evs),
            "evidencia": [e.texto() for e in evs],
            "projeto": link(slug_p) if slug_p else None,
            "tags": [str(t).strip().lstrip("#") for t in lista(tags)],
            "criticidade": criticidade,
            "registrado_por": autor.assinatura,
            "registrado_em": hoje(),
            "verificado_por": autor.assinatura if verificado else None,
            "verificado_em": hoje() if verificado else None,
            "revisar_em": daqui(validade) if verificado else None,
            "substitui": substitui,
            "aliases": [ident],
        }, manter=("evidencia", "projeto"))
        partes = [("Contexto", str(contexto or "").strip())]
        corpo = _corpo_fato(meta, partes, _linha_hist(f"criado como **{status}**", autor))
        caminho = cofre.pasta_para("fato", slug_p) / f"{ident} {slug(afirmacao, 50)}.md"
        nota = Nota(caminho, meta, corpo)
        cofre.salvar(nota)
    _commit(cofre, [caminho], f"cofre: fato {ident} ({status}) por {autor.assinatura}")
    escopo = f"projeto {slug_p}" if slug_p else "escopo global"
    if not slug_p and not projeto:
        avisos.append(
            "Nenhum projeto detectado pelo diretório: gravado como GLOBAL. Se o fato é de um projeto, "
            "passe projeto='<slug>' ou cwd='<caminho absoluto do projeto>' nas próximas chamadas."
        )
    return Resultado(
        f"Fato registrado: {ident} [{status.upper()}] ({escopo}) — {afirmacao}\nArquivo: {cofre.relativo(caminho)}",
        ident, caminho, avisos,
    )


ACOES_FATO = ("adicionar_evidencia", "promover", "contestar", "refutar", "tornar_obsoleto", "reabrir")


def atualizar_fato(
    cofre: Cofre, autor: Autor, ident: str, acao: str, evidencias=None, motivo: str = "",
    afirmacao_correta: str | None = None, cwd: str | None = None,
) -> Resultado:
    nota = cofre.exigir(ident, "fato", "Fato")
    acao = (acao or "").strip().lower()
    if acao not in ACOES_FATO:
        raise ErroCofre(f"Ação inválida '{acao}'. Use: {', '.join(ACOES_FATO)}.")
    motivo = " ".join(str(motivo or "").split())
    ep.barrar_segredos(motivo, afirmacao_correta or "", *[str(e) for e in lista(evidencias)])
    proj = cofre.projeto(nota.projeto) if nota.projeto else None
    bases = bases_de_arquivos(proj, cwd)
    evs = ep.ler_evidencias(evidencias)
    avisos = _validar_evidencias(cofre, evs, bases, autor)
    meta = dict(nota.meta)
    status = nota.status
    politica_humano = cofre.config().get("politica_verificacao") == "humano"
    validade = int(cofre.config().get("validade_padrao_dias", 90))

    if acao == "adicionar_evidencia":
        if not evs:
            raise ErroCofre("Informe ao menos uma evidência em 'evidencias'.")
        meta["evidencia"] = lista(meta.get("evidencia")) + [e.texto() for e in evs]
        hist = f"evidência adicionada ({', '.join(e.tipo for e in evs)})"
    elif acao == "promover":
        if status not in ("hipotese", "contestado"):
            raise ErroCofre(f"Só hipótese ou contestado pode ser promovido (status atual: {status}).")
        if politica_humano and not autor.humano:
            raise ErroCofre(
                "Política do cofre: só o USUÁRIO promove para verificado. Anexe a evidência com "
                "acao='adicionar_evidencia' e peça ao usuário para confirmar."
            )
        if status == "contestado" and not evs:
            raise ErroCofre("Para promover um fato CONTESTADO, anexe evidência NOVA que resolva o conflito.")
        existentes = _evidencias_salvas(nota)
        if not autor.humano:
            _validar_evidencias(cofre, [e for e in existentes if e.tipo == "arquivo"], bases, autor)
        todas = existentes + evs
        if not todas:
            raise ErroCofre(
                "Promover exige evidência conferível (arquivo, comando, url ou citação do usuário). "
                "Passe em 'evidencias'."
            )
        meta["evidencia"] = [e.texto() for e in todas]
        meta.update(
            status="verificado", fonte=ep.fonte_de(todas), verificado_por=autor.assinatura,
            verificado_em=hoje(), revisar_em=daqui(validade),
        )
        meta.pop("motivo", None)
        hist = "promovido a **verificado**"
    elif acao == "contestar":
        if status not in ("verificado", "hipotese"):
            raise ErroCofre(f"Só fato verificado ou hipótese pode ser contestado (status atual: {status}).")
        if len(motivo) < 10:
            raise ErroCofre("Explique o conflito em 'motivo' (o que você observou que contradiz o fato).")
        meta.update(status="contestado", contestado_em=hoje(), motivo=motivo)
        if evs:
            meta["evidencia_contraria"] = lista(meta.get("evidencia_contraria")) + [e.texto() for e in evs]
        hist = f"**contestado**: {motivo}"
    elif acao == "refutar":
        if status == "refutado":
            raise ErroCofre("Este fato já está refutado.")
        if len(motivo) < 10:
            raise ErroCofre("Explique em 'motivo' por que a afirmação é falsa.")
        if not evs and not autor.humano:
            raise ErroCofre(
                "Refutar exige evidência (arquivo, comando, url ou citação do usuário) mostrando que é falso. "
                "Se você só desconfia, use acao='contestar'."
            )
        if meta.get("fonte") == "usuario" and not autor.humano and not any(e.tipo == "usuario" for e in evs):
            raise ErroCofre(
                "Este fato foi confirmado pelo USUÁRIO; só o usuário pode refutá-lo. "
                "Use acao='contestar' com sua evidência e avise o usuário do conflito."
            )
        meta.update(status="refutado", refutado_em=hoje(), motivo=motivo)
        meta["evidencia_contraria"] = lista(meta.get("evidencia_contraria")) + [e.texto() for e in evs]
        meta.pop("revisar_em", None)
        hist = f"**refutado**: {motivo}"
    elif acao == "tornar_obsoleto":
        if len(motivo) < 10:
            raise ErroCofre("Explique em 'motivo' o que mudou (ex.: versão atualizada, serviço migrado).")
        meta.update(status="obsoleto", obsoleto_em=hoje(), motivo=motivo)
        meta.pop("revisar_em", None)
        hist = f"**obsoleto**: {motivo}"
    else:
        if not autor.humano:
            raise ErroCofre("Só o usuário reabre fatos. Para questionar um fato use acao='contestar'.")
        meta.update(status="hipotese")
        for chave in ("verificado_em", "verificado_por", "revisar_em", "refutado_em", "obsoleto_em", "contestado_em"):
            meta.pop(chave, None)
        hist = "reaberto como **hipotese**"

    with cofre.trava():
        atual = ler_nota(nota.caminho)
        corpo = _corpo_fato(meta, secoes(atual.corpo), _linha_hist(hist, autor))
        cofre.salvar(Nota(nota.caminho, meta, corpo))
    caminhos = [nota.caminho]
    mensagem = f"Fato {nota.id} atualizado: {status} -> {meta['status']}."

    if afirmacao_correta and acao in ("refutar", "tornar_obsoleto"):
        evs_novo = [e for e in evs if e.tipo in ("arquivo", "comando", "url", "usuario")]
        novo = registrar_fato(
            cofre, autor, afirmacao_correta,
            status="verificado" if evs_novo else "hipotese",
            evidencias=[e.texto() for e in evs_novo], projeto=nota.projeto or "global",
            contexto=f"Correção de {link(nota.nome)}: {motivo}", tags=meta.get("tags"),
            criticidade=str(meta.get("criticidade") or "normal"), forcar=True, cwd=cwd,
            substitui=link(nota.nome), _correcao=True,
        )
        avisos += novo.avisos
        with cofre.trava():
            atual = ler_nota(nota.caminho)
            atual.meta["substituido_por"] = link(novo.caminho.stem)
            corpo = _corpo_fato(atual.meta, secoes(atual.corpo), _linha_hist(f"substituído por {novo.id}", autor))
            cofre.salvar(Nota(nota.caminho, atual.meta, corpo))
        caminhos.append(novo.caminho)
        mensagem += f"\n{novo.mensagem}"
    _commit(cofre, caminhos, f"cofre: fato {nota.id} {acao} por {autor.assinatura}")
    return Resultado(mensagem, nota.id, nota.caminho, avisos)


# ---- decisões -------------------------------------------------------------
def _preambulo_decisao(meta: dict) -> str:
    aceita = meta.get("status") == "aceita"
    rotulo = {"aceita": "ACEITA", "proposta": "PROPOSTA (aguarda o usuário)", "substituida": "SUBSTITUÍDA",
              "rejeitada": "REJEITADA"}.get(meta.get("status"), str(meta.get("status", "")).upper())
    pre = f"# {meta['titulo']}\n\n> [!{'success' if aceita else 'question'}] {rotulo}"
    if meta.get("citacao_usuario"):
        pre += f"\n> Usuário: \"{meta['citacao_usuario']}\""
    if meta.get("substituida_por"):
        pre += f"\n> Substituída por: {meta['substituida_por']}"
    return pre


def _corpo_decisao(meta: dict, partes: list[tuple[str | None, str]], hist: str) -> str:
    mapa = dict((t, x) for t, x in partes if t)
    mapa["Histórico"] = (mapa.get("Histórico", "").rstrip("\n") + "\n" + hist).strip("\n")
    ordem = [t for t, _ in partes if t and t != "Histórico"] + ["Histórico"]
    return juntar_secoes([(None, _preambulo_decisao(meta))] + [(t, mapa[t]) for t in ordem])


def decisao(
    cofre: Cofre, autor: Autor, acao: str = "registrar", titulo: str = "", decisao_txt: str = "",
    contexto: str = "", alternativas=None, consequencias=None, status: str = "proposta",
    citacao_usuario: str = "", projeto: str | None = None, ident: str | None = None,
    substitui: str | None = None, motivo: str = "", cwd: str | None = None,
) -> Resultado:
    acao = (acao or "registrar").strip().lower()
    citacao_usuario = " ".join(str(citacao_usuario or "").split())
    if acao in ("aceitar", "rejeitar"):
        nota = cofre.exigir(ident, "decisao", "Decisão")
        if not autor.humano and not citacao_usuario:
            raise ErroCofre(f"Para {acao} uma decisão, passe 'citacao_usuario' com as palavras do usuário.")
        meta = dict(nota.meta)
        meta["status"] = "aceita" if acao == "aceitar" else "rejeitada"
        if citacao_usuario:
            meta["citacao_usuario"] = citacao_usuario
        if acao == "aceitar":
            meta["decidido_em"] = hoje()
        with cofre.trava():
            atual = ler_nota(nota.caminho)
            corpo = _corpo_decisao(meta, secoes(atual.corpo), _linha_hist(f"{acao} {motivo}".strip(), autor))
            cofre.salvar(Nota(nota.caminho, meta, corpo))
        _commit(cofre, [nota.caminho], f"cofre: decisão {nota.id} {acao} por {autor.assinatura}")
        return Resultado(f"Decisão {nota.id} agora está {meta['status'].upper()}.", nota.id, nota.caminho)

    if acao != "registrar":
        raise ErroCofre("acao deve ser 'registrar', 'aceitar' ou 'rejeitar'.")
    titulo = " ".join(str(titulo or "").split())
    if not (5 <= len(titulo) <= 120):
        raise ErroCofre("Título da decisão deve ter entre 5 e 120 caracteres.")
    if not str(decisao_txt or "").strip():
        raise ErroCofre("Descreva a decisão em 'decisao'.")
    status = _normal_status(status, "proposta")
    if status not in ("proposta", "aceita"):
        raise ErroCofre("status deve ser 'proposta' ou 'aceita'.")
    avisos = []
    if status == "aceita" and not autor.humano and not citacao_usuario:
        status = "proposta"
        avisos.append(
            "Decisão só fica ACEITA com a citação literal do usuário aprovando (citacao_usuario). "
            "Registrada como PROPOSTA."
        )
    ep.barrar_segredos(titulo, decisao_txt, contexto or "", citacao_usuario)
    proj = _projeto_alvo(cofre, projeto, cwd)
    slug_p = proj.nome if proj else None
    antiga = cofre.resolver_ref(substitui) if substitui else None
    if substitui and not antiga:
        raise ErroCofre(f"Decisão a substituir '{substitui}' não encontrada.")
    with cofre.trava():
        ident_novo = cofre.novo_id("decisao")
        meta = _limpar({
            "tipo": "decisao",
            "id": ident_novo,
            "titulo": titulo,
            "status": status,
            "projeto": link(slug_p) if slug_p else None,
            "decidido_em": hoje() if status == "aceita" else None,
            "citacao_usuario": citacao_usuario or None,
            "registrado_por": autor.assinatura,
            "registrado_em": hoje(),
            "substitui": link(antiga.nome) if antiga else None,
            "aliases": [ident_novo],
        }, manter=("projeto",))
        corpo = _corpo_decisao(meta, [
            ("Decisão", str(decisao_txt).strip()),
            ("Contexto", str(contexto or "").strip()),
            ("Alternativas consideradas", "\n".join(f"- {a}" for a in (_itens(alternativas) or []))),
            ("Consequências", "\n".join(f"- {c}" for c in (_itens(consequencias) or []))),
        ], _linha_hist(f"registrada como **{status}**", autor))
        caminho = cofre.pasta_para("decisao", slug_p) / f"{ident_novo} {slug(titulo, 50)}.md"
        cofre.salvar(Nota(caminho, meta, corpo))
        caminhos = [caminho]
        if antiga:
            antiga = ler_nota(antiga.caminho)
            antiga.meta["status"] = "substituida"
            antiga.meta["substituida_por"] = link(caminho.stem)
            antiga.corpo = _corpo_decisao(antiga.meta, secoes(antiga.corpo),
                                          _linha_hist(f"substituída por {ident_novo}", autor))
            cofre.salvar(antiga)
            caminhos.append(antiga.caminho)
    _commit(cofre, caminhos, f"cofre: decisão {ident_novo} ({status}) por {autor.assinatura}")
    return Resultado(
        f"Decisão registrada: {ident_novo} [{status.upper()}] — {titulo}\nArquivo: {cofre.relativo(caminho)}",
        ident_novo, caminho, avisos,
    )


# ---- checkpoint (estado + sessão) ----------------------------------------
def _itens(valor) -> list[str] | None:
    if valor is None:
        return None
    if isinstance(valor, str):
        valor = [v for v in re.split(r"\n+", valor) if v.strip()]
    return [re.sub(r"^\s*(?:[-*]\s+)?(?:\[[ xX]\]\s+)?", "", str(v)).strip() for v in valor if str(v).strip()]


def _sessao_aberta(cofre: Cofre, slug_p: str | None, autor: Autor) -> Nota | None:
    limite = datetime.now() - timedelta(hours=3)
    melhores = []
    for n in cofre.por_tipo("sessao"):
        if n.projeto != slug_p or n.meta.get("agente") != autor.assinatura:
            continue
        try:
            quando = datetime.strptime(str(n.meta.get("atualizada", ""))[:16], "%Y-%m-%d %H:%M")
        except ValueError:
            continue
        if quando >= limite:
            melhores.append((quando, n))
    return max(melhores, key=lambda x: x[0])[1] if melhores else None


def checkpoint(
    cofre: Cofre, autor: Autor, resumo: str, feito=None, proximos_passos=None, bloqueios=None,
    foco: str | None = None, projeto: str | None = None, sessao_id: str | None = None,
    fatos=None, decisoes=None, cwd: str | None = None, sessao_externa: str | None = None,
) -> Resultado:
    resumo = str(resumo or "").strip()
    if len(resumo) < 10:
        raise ErroCofre("Escreva um 'resumo' do que aconteceu desde o último checkpoint (mín. 10 caracteres).")
    feito, proximos, bloq = _itens(feito), _itens(proximos_passos), _itens(bloqueios)
    ep.barrar_segredos(resumo, foco or "", *(feito or []), *(proximos or []), *(bloq or []))
    proj = _projeto_alvo(cofre, projeto, cwd)
    slug_p = proj.nome if proj else None
    links_fatos = [link(n.nome) for n in (cofre.resolver_ref(f) for f in lista(fatos)) if n]
    links_dec = [link(n.nome) for n in (cofre.resolver_ref(d) for d in lista(decisoes)) if n]
    avisos = []
    caminhos = []
    with cofre.trava():
        sessao = cofre.resolver_ref(sessao_id) if sessao_id else None
        if not sessao and sessao_externa:
            sessao = next((n for n in cofre.por_tipo("sessao") if n.meta.get("sessao_externa") == sessao_externa), None)
        if not sessao and not sessao_id:
            sessao = _sessao_aberta(cofre, slug_p, autor)
        if sessao_id and not sessao:
            avisos.append(f"Sessão '{sessao_id}' não encontrada; criei uma nova.")
        bloco = [f"### {agora()[11:]}", resumo]
        if feito:
            bloco += ["", "**Feito**"] + [f"- {i}" for i in feito]
        if proximos:
            bloco += ["", "**Próximos passos**"] + [f"- {i}" for i in proximos]
        if bloq:
            bloco += ["", "**Bloqueios**"] + [f"- {i}" for i in bloq]
        if sessao:
            sessao = ler_nota(sessao.caminho)
            sessao.meta["atualizada"] = agora()
            sessao.meta["fatos"] = sorted(set(lista(sessao.meta.get("fatos")) + links_fatos))
            sessao.meta["decisoes"] = sorted(set(lista(sessao.meta.get("decisoes")) + links_dec))
            sessao.corpo = sessao.corpo.rstrip("\n") + "\n\n" + "\n".join(bloco) + "\n"
        else:
            ident = cofre.novo_id("sessao")
            meta = _limpar({
                "tipo": "sessao",
                "id": ident,
                "projeto": link(slug_p) if slug_p else None,
                "agente": autor.assinatura,
                "sessao_externa": sessao_externa,
                "iniciada": agora(),
                "atualizada": agora(),
                "confiabilidade": "diario",
                "fatos": links_fatos,
                "decisoes": links_dec,
                "aliases": [ident],
            }, manter=("projeto", "fatos", "decisoes"))
            corpo = (
                f"# Sessão {hoje()} — {resumo[:70]}\n\n"
                "> [!abstract] Diário escrito por agente. Não é fonte de verdade: fatos confiáveis ficam nas notas de fato.\n\n"
                "## Checkpoints\n\n" + "\n".join(bloco) + "\n"
            )
            caminho = cofre.pasta_para("sessao", slug_p) / f"{ident} {hoje()} {slug(resumo, 40)}.md"
            sessao = Nota(caminho, meta, corpo)
        cofre.salvar(sessao)
        caminhos.append(sessao.caminho)

        if slug_p:
            anterior = cofre.estado(slug_p)
            corpo_ant = anterior.corpo if anterior else ""
            foco_txt = (foco or "").strip() or secao(corpo_ant, "Foco atual") or resumo
            prox_txt = "\n".join(f"- [ ] {i}" for i in proximos) if proximos is not None else secao(corpo_ant, "Próximos passos")
            bloq_txt = "\n".join(f"- {i}" for i in bloq) if bloq is not None else secao(corpo_ant, "Bloqueios")
            meta_e = {
                "tipo": "estado",
                "projeto": link(slug_p),
                "atualizado": agora(),
                "atualizado_por": autor.assinatura,
                "ultima_sessao": link(sessao.caminho.stem),
            }
            nome_proj = proj.meta.get("nome") or slug_p
            corpo_e = juntar_secoes([
                (None, f"# Estado atual — {nome_proj}\n\n> [!info] Memória de trabalho do projeto, reescrita a cada checkpoint. "
                       "Escrita por agentes: confira com o código antes de afirmar algo como fato."),
                ("Foco atual", foco_txt),
                ("Próximos passos", prox_txt or "- (nenhum registrado)"),
                ("Bloqueios", bloq_txt or "- (nenhum)"),
                ("Último checkpoint", f"{resumo}\n\n({agora()}, {autor.assinatura}, {link(sessao.caminho.stem)})"),
            ])
            arq_estado = cofre.arquivo_estado(slug_p)
            cofre.salvar(Nota(arq_estado, meta_e, corpo_e))
            caminhos.append(arq_estado)
        else:
            avisos.append("Sem projeto associado: checkpoint salvo só como sessão geral (02-Sessoes).")
    _commit(cofre, caminhos, f"cofre: checkpoint {sessao.id} por {autor.assinatura}")
    return Resultado(
        f"Checkpoint salvo na sessão {sessao.id}" + (f" e no estado do projeto {slug_p}." if slug_p else ".")
        + f"\nUse sessao_id='{sessao.id}' nos próximos checkpoints desta conversa.",
        sessao.id, sessao.caminho, avisos,
    )


# ---- captura (inbox) ------------------------------------------------------
_URL = re.compile(r"^(https?://|www\.)", re.I)


def recurso(cofre: Cofre, autor: Autor, titulo: str, url: str = "", quando_usar: str = "",
            descricao: str = "", projeto: str | None = None, tags=None, cwd: str | None = None) -> Resultado:
    """Site, API ou ferramenta externa que a IA deve conhecer e abrir quando o assunto aparecer.
    Não é fato nem evidência: é um ponteiro para algo fora do cofre."""
    titulo = " ".join(str(titulo or "").split())[:120]
    url = str(url or "").strip()
    quando_usar = " ".join(str(quando_usar or "").split())
    if len(titulo) < 3:
        raise ErroCofre("Recurso precisa de 'titulo' (nome do site/ferramenta).")
    if url and not _URL.match(url) and "/" not in url and "." not in url:
        raise ErroCofre(f"'{url}' não parece um link ou comando. Passe a URL (https://...) ou o comando de instalação.")
    ep.barrar_segredos(titulo, url, quando_usar, descricao)
    proj = _projeto_alvo(cofre, projeto, cwd)
    with cofre.trava():
        meta = _limpar({
            "tipo": "recurso", "titulo": titulo, "url": url, "quando_usar": quando_usar,
            "projeto": link(proj.nome) if proj else None, "tags": _itens(tags),
            "registrado_por": autor.assinatura, "criado": hoje(),
        })
        corpo = juntar_secoes([
            (None, f"# {titulo}"),
            ("Quando usar", quando_usar or "(descreva em que situação a IA deve abrir isto)"),
            ("O que é", descricao.strip()),
            ("Link", url),
        ])
        pasta = (cofre.pasta_projeto(proj.nome) / "Recursos") if proj else (cofre.raiz / PASTAS["conhecimento"] / "Recursos")
        caminho = pasta / f"{slug(titulo, 60)}.md"
        if caminho.exists():
            nota = ler_nota(caminho)
            nota.meta.update({k: v for k, v in meta.items() if v})
            nota.corpo = corpo
            cofre.salvar(nota)
            acao = "atualizado"
        else:
            cofre.salvar(Nota(caminho, meta, corpo))
            acao = "registrado"
    _commit(cofre, [caminho], f"cofre: recurso {acao} por {autor.assinatura}")
    return Resultado(f"Recurso {acao}: {titulo}" + (f" ({url})" if url else ""), None, caminho)


def capturar(cofre: Cofre, autor: Autor, texto: str, titulo: str | None = None,
             projeto: str | None = None, cwd: str | None = None) -> Resultado:
    texto = str(texto or "").strip()
    if len(texto) < 5:
        raise ErroCofre("Texto da captura vazio.")
    ep.barrar_segredos(texto, titulo or "")
    proj = _projeto_alvo(cofre, projeto, cwd)
    titulo = " ".join(str(titulo or texto.split("\n")[0]).split())[:80]
    with cofre.trava():
        ident = cofre.novo_id("captura")
        meta = _limpar({
            "tipo": "captura",
            "id": ident,
            "status": "pendente",
            "projeto": link(proj.nome) if proj else None,
            "origem": autor.assinatura,
            "capturado_em": agora(),
            "aliases": [ident],
        })
        corpo = (
            f"# {titulo}\n\n> [!todo] Captura bruta, não verificada. Triar: virar fato/decisão/missão ou descartar.\n\n"
            f"{texto}\n"
        )
        caminho = cofre.raiz / PASTAS["inbox"] / f"{ident} {hoje()} {slug(titulo, 40)}.md"
        cofre.salvar(Nota(caminho, meta, corpo))
    _commit(cofre, [caminho], f"cofre: captura {ident} por {autor.assinatura}")
    return Resultado(f"Capturado na inbox: {ident} — {titulo}", ident, caminho)


# ---- projetos -------------------------------------------------------------
def _caminho_texto(c: str) -> str:
    return str(c).strip().replace("\\", "/")


def projeto_criar(cofre: Cofre, autor: Autor, slug_p: str, nome: str | None = None, caminhos=None,
                  repos=None, cliente: str | None = None, descricao: str = "", stack=None) -> Resultado:
    s = slug(slug_p or nome or "")
    if not slug_p and not nome:
        raise ErroCofre("Informe 'slug' (ex.: 'loja-acme') e de preferência 'nome'.")
    if s in cofre.projetos():
        raise ErroCofre(f"Projeto '{s}' já existe.")
    ep.barrar_segredos(descricao or "", nome or "")
    pasta = cofre.pasta_projeto(s)
    meta = _limpar({
        "tipo": "projeto",
        "nome": nome or s,
        "status": "ativo",
        "cliente": link(slug(cliente)) if cliente else None,
        "caminhos": [_caminho_texto(c) for c in lista(caminhos)],
        "repos": [normalizar_repo(r) for r in lista(repos)],
        "stack": [str(x) for x in lista(stack)],
        "criado": hoje(),
    }, manter=("caminhos", "repos"))
    corpo = (
        f"# {meta['nome']}\n\n"
        f"> [!info] Hub do projeto. Estado de trabalho: [[{s} - Estado]]. Fatos, decisões e sessões ficam nas subpastas.\n\n"
        f"## Visão geral\n{descricao.strip() or '(descreva o projeto, o cliente e o objetivo)'}\n\n"
        "## Painel\n![[Projeto.base]]\n\n"
        "## Notas livres\n"
    )
    with cofre.trava():
        cofre.salvar(Nota(pasta / f"{s}.md", meta, corpo))
        estado = Nota(cofre.arquivo_estado(s), {
            "tipo": "estado", "projeto": link(s), "atualizado": agora(), "atualizado_por": autor.assinatura,
        }, juntar_secoes([
            (None, f"# Estado atual — {meta['nome']}"),
            ("Foco atual", "(ainda sem checkpoint)"),
            ("Próximos passos", "- (nenhum registrado)"),
            ("Bloqueios", "- (nenhum)"),
        ]))
        cofre.salvar(estado)
    _commit(cofre, [pasta / f"{s}.md", estado.caminho], f"cofre: projeto {s} criado por {autor.assinatura}")
    return Resultado(f"Projeto criado: {s} ({meta['nome']}) em {cofre.relativo(pasta)}", s, pasta / f"{s}.md")


def projeto_vincular(cofre: Cofre, autor: Autor, ref: str, caminho: str | None = None,
                     repo: str | None = None) -> Resultado:
    nota = cofre.projeto(ref)
    if not nota:
        raise ErroCofre(f"Projeto '{ref}' não existe. Projetos: {', '.join(sorted(cofre.projetos())) or '(nenhum)'}.")
    if not caminho and not repo:
        raise ErroCofre("Informe 'caminho' (pasta local) e/ou 'repo' (URL do remoto git).")
    with cofre.trava():
        atual = ler_nota(nota.caminho)
        if caminho:
            atual.meta["caminhos"] = sorted(set(lista(atual.meta.get("caminhos")) + [_caminho_texto(caminho)]))
        if repo:
            atual.meta["repos"] = sorted(set(lista(atual.meta.get("repos")) + [normalizar_repo(repo)]))
        cofre.salvar(atual)
    _commit(cofre, [nota.caminho], f"cofre: projeto {nota.nome} vinculado por {autor.assinatura}")
    return Resultado(f"Projeto {nota.nome} vinculado: " + ", ".join(x for x in (caminho, repo) if x), nota.nome, nota.caminho)


def projeto_listar(cofre: Cofre) -> str:
    projetos = cofre.projetos()
    if not projetos:
        return "Nenhum projeto no cofre ainda."
    linhas = ["Projetos no cofre:"]
    for s, n in sorted(projetos.items()):
        caminhos = ", ".join(lista(n.meta.get("caminhos"))) or "sem caminho vinculado"
        linhas.append(f"- {s} — {n.meta.get('nome', s)} [{n.meta.get('status', '?')}] — {caminhos}")
    return "\n".join(linhas)


# ---- missões --------------------------------------------------------------
def missao_criar(cofre: Cofre, autor: Autor, titulo: str, objetivo: str, criterios=None, passos=None,
                 projetos=None) -> Resultado:
    titulo = " ".join(str(titulo or "").split())
    if len(titulo) < 5 or not str(objetivo or "").strip():
        raise ErroCofre("Missão precisa de 'titulo' (mín. 5 caracteres) e 'objetivo'.")
    ep.barrar_segredos(titulo, objetivo, *[str(x) for x in lista(criterios) + lista(passos)])
    links_proj = []
    for p in lista(projetos):
        nota = cofre.projeto(str(p))
        if not nota:
            raise ErroCofre(f"Projeto '{p}' não existe no cofre.")
        links_proj.append(link(nota.nome))
    with cofre.trava():
        ident = cofre.novo_id("missao")
        meta = _limpar({
            "tipo": "missao", "id": ident, "titulo": titulo, "status": "ativa", "projetos": links_proj,
            "criada": hoje(), "atualizada": agora(), "registrado_por": autor.assinatura, "aliases": [ident],
        }, manter=("projetos",))
        corpo = juntar_secoes([
            (None, f"# {titulo}"),
            ("Objetivo", str(objetivo).strip()),
            ("Critérios de pronto", "\n".join(f"- [ ] {c}" for c in (_itens(criterios) or [])) or "- [ ] (defina)"),
            ("Passos", "\n".join(f"- [ ] {p}" for p in (_itens(passos) or [])) or "- [ ] (defina)"),
            ("Log", _linha_hist("missão criada", autor)),
        ])
        caminho = cofre.raiz / PASTAS["missoes"] / f"{ident} {slug(titulo, 50)}.md"
        cofre.salvar(Nota(caminho, meta, corpo))
    _commit(cofre, [caminho], f"cofre: missão {ident} criada por {autor.assinatura}")
    return Resultado(f"Missão criada: {ident} — {titulo}", ident, caminho)


def missao_atualizar(cofre: Cofre, autor: Autor, ref: str, concluir_passo=None, adicionar_passo: str | None = None,
                     status: str | None = None, nota_log: str | None = None) -> Resultado:
    alvo = cofre.exigir(ref, "missao", "Missão")
    ep.barrar_segredos(adicionar_passo or "", nota_log or "")
    with cofre.trava():
        nota = ler_nota(alvo.caminho)
        partes = secoes(nota.corpo)
        mapa = dict((t, x) for t, x in partes if t)
        log = []
        if concluir_passo not in (None, ""):
            linhas = mapa.get("Passos", "").split("\n")
            pendentes = [i for i, linha in enumerate(linhas) if linha.strip().startswith("- [ ]")]
            escolhido = None
            if str(concluir_passo).strip().isdigit():
                k = int(str(concluir_passo).strip()) - 1
                todos = [i for i, linha in enumerate(linhas) if re.match(r"^\s*- \[[ xX]\]", linha)]
                if 0 <= k < len(todos) and todos[k] in pendentes:
                    escolhido = todos[k]
            else:
                termo = str(concluir_passo).strip().lower()
                escolhido = next((i for i in pendentes if termo in linhas[i].lower()), None)
            if escolhido is None:
                raise ErroCofre(f"Passo '{concluir_passo}' não encontrado entre os pendentes da missão.")
            linhas[escolhido] = linhas[escolhido].replace("- [ ]", "- [x]", 1)
            mapa["Passos"] = "\n".join(linhas)
            log.append(f"passo concluído: {linhas[escolhido][6:].strip()}")
        if adicionar_passo:
            mapa["Passos"] = (mapa.get("Passos", "").rstrip("\n") + f"\n- [ ] {adicionar_passo.strip()}").strip("\n")
            log.append(f"passo adicionado: {adicionar_passo.strip()}")
        if status:
            st = status.strip().lower()
            if st not in ("ativa", "pausada", "concluida", "cancelada"):
                raise ErroCofre("status da missão: ativa, pausada, concluida ou cancelada.")
            nota.meta["status"] = st
            log.append(f"status -> {st}")
        if nota_log:
            log.append(nota_log.strip())
        if not log:
            raise ErroCofre("Nada para atualizar: use concluir_passo, adicionar_passo, status ou nota.")
        mapa["Log"] = (mapa.get("Log", "").rstrip("\n") + "\n" + _linha_hist("; ".join(log), autor)).strip("\n")
        nota.meta["atualizada"] = agora()
        nota.corpo = juntar_secoes([(t, mapa.get(t, x) if t else x) for t, x in partes]
                                   + [(t, mapa[t]) for t in mapa if t not in dict(partes)])
        cofre.salvar(nota)
    _commit(cofre, [alvo.caminho], f"cofre: missão {alvo.id} atualizada por {autor.assinatura}")
    return Resultado(f"Missão {alvo.id} atualizada: " + "; ".join(log), alvo.id, alvo.caminho)


def missao_listar(cofre: Cofre, status: str | None = "ativa", projeto: str | None = None) -> str:
    missoes = cofre.por_tipo("missao")
    if status:
        missoes = [m for m in missoes if m.status == status]
    if projeto:
        missoes = [m for m in missoes if projeto in [alvo_link(p) for p in lista(m.meta.get("projetos"))]]
    if not missoes:
        return "Nenhuma missão" + (f" com status '{status}'." if status else ".")
    linhas = ["Missões:"]
    for m in sorted(missoes, key=lambda x: x.id):
        passos = secao(m.corpo, "Passos").split("\n")
        feitos = sum(1 for p in passos if p.strip().startswith("- [x]"))
        total = sum(1 for p in passos if re.match(r"^\s*- \[[ xX]\]", p))
        linhas.append(f"- {m.id} [{m.status}] {m.meta.get('titulo', m.nome)} ({feitos}/{total} passos)")
    return "\n".join(linhas)
