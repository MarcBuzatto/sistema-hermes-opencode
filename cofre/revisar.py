"""Revisão periódica do cofre: integridade, validade, evidências e segredos."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from . import epistemica as ep
from .contexto import vencido
from .projetos import bases_de_arquivos
from .registrar import Autor, _corpo_fato, _linha_hist
from .vault import (
    PASTAS, STATUS_DECISAO, STATUS_FATO, STATUS_MISSAO, Cofre, Nota, escrever_atomico, hoje, ler_nota,
    lista, para_data, secoes,
)

GRAVIDADE = {"erro": 0, "alerta": 1, "info": 2}


@dataclass
class Achado:
    gravidade: str
    nota: str
    mensagem: str


def _rotulo(n: Nota) -> str:
    return n.id or n.nome


def revisar(cofre: Cofre, projeto: str | None = None, conferir_evidencias: bool = True,
            aplicar: bool = False, cwd: str | None = None) -> list[Achado]:
    cfg = cofre.config()
    achados: list[Achado] = []
    notas = cofre.notas(recarregar=True)
    if projeto:
        proj = cofre.projeto(projeto)
        notas = [n for n in notas if n.projeto == (proj.nome if proj else projeto) or n.nome == projeto]

    vistos: dict[str, Nota] = {}
    for n in notas:
        if n.id:
            chave = n.id.upper()
            if chave in vistos:
                achados.append(Achado("erro", _rotulo(n), f"ID duplicado com {vistos[chave].caminho.name}"))
            vistos[chave] = n
        segredos = ep.achar_segredos(n.texto(), incluir_fracos=True)
        if segredos:
            achados.append(Achado("erro", _rotulo(n), "possível credencial no texto: " + ", ".join(segredos)
                                  + f" ({cofre.relativo(n.caminho)})"))

    hoje_d = date.today()
    antigas = int(cfg.get("hipotese_antiga_dias", 14))
    fatos = [n for n in notas if n.tipo == "fato"]
    for n in fatos:
        rot = _rotulo(n)
        if n.status not in STATUS_FATO:
            achados.append(Achado("erro", rot, f"status inválido '{n.status}' (use {', '.join(STATUS_FATO)})"))
            continue
        if not n.meta.get("afirmacao"):
            achados.append(Achado("erro", rot, "fato sem 'afirmacao'"))
        evs = []
        for bruto in lista(n.meta.get("evidencia")):
            try:
                evs.append(ep.ler_evidencia(bruto))
            except Exception as e:
                achados.append(Achado("alerta", rot, f"evidência mal formatada: {bruto} ({e})"))
        if n.status == "verificado":
            if not evs:
                achados.append(Achado("erro", rot, "VERIFICADO sem evidência — rebaixe para hipótese ou anexe evidência"))
            if vencido(n):
                achados.append(Achado("alerta", rot, f"verificação vencida desde {n.meta.get('revisar_em')}: reverificar"))
            if conferir_evidencias:
                proj = cofre.projeto(n.projeto) if n.projeto else None
                bases = bases_de_arquivos(proj, cwd)
                for e in evs:
                    if e.tipo != "arquivo":
                        continue
                    ok, msg = ep.conferir_arquivo(e, bases)
                    if ok is False:
                        achados.append(Achado("erro", rot, f"evidência NÃO confere mais: {msg}"))
                        if aplicar:
                            _marcar_contestado(cofre, n, f"conferência automática falhou: {msg}")
                    elif ok is None:
                        achados.append(Achado("info", rot, f"evidência não conferível nesta máquina: {msg}"))
        if n.status == "hipotese":
            criado = para_data(n.meta.get("registrado_em"))
            if criado and (hoje_d - criado).days > antigas:
                achados.append(Achado("alerta", rot, f"hipótese aberta há {(hoje_d - criado).days} dias: verificar ou descartar"))
        if n.status == "contestado":
            achados.append(Achado("alerta", rot, "fato CONTESTADO aguardando resolução (promover com evidência nova ou refutar)"))
        for chave in ("substitui", "substituido_por"):
            if n.meta.get(chave) and not cofre.resolver_ref(n.meta[chave]):
                achados.append(Achado("alerta", rot, f"'{chave}' aponta para nota inexistente: {n.meta[chave]}"))

    por_escopo: dict[str | None, list[Nota]] = {}
    for n in fatos:
        if n.status in ("hipotese", "verificado", "contestado"):
            por_escopo.setdefault(n.projeto, []).append(n)
    for grupo in por_escopo.values():
        for i, a in enumerate(grupo):
            for b in grupo[i + 1:]:
                fa, fb = str(a.meta.get("afirmacao", "")), str(b.meta.get("afirmacao", ""))
                if ep.similaridade(fa, fb) >= 0.6:
                    tipo = "contradição" if ep.polaridade_oposta(fa, fb) else "possível duplicata"
                    achados.append(Achado("alerta", _rotulo(a), f"{tipo} com {_rotulo(b)}: \"{fa}\" × \"{fb}\""))

    for n in notas:
        if n.tipo == "decisao" and n.status not in STATUS_DECISAO:
            achados.append(Achado("erro", _rotulo(n), f"status de decisão inválido '{n.status}'"))
        if n.tipo == "decisao" and n.status == "aceita" and not n.meta.get("citacao_usuario") \
                and n.meta.get("registrado_por") != "usuario":
            achados.append(Achado("alerta", _rotulo(n), "decisão ACEITA sem citação do usuário"))
        if n.tipo == "missao" and n.status not in STATUS_MISSAO:
            achados.append(Achado("erro", _rotulo(n), f"status de missão inválido '{n.status}'"))
        if n.tipo == "captura" and n.status == "pendente":
            achados.append(Achado("info", _rotulo(n), f"captura pendente de triagem na inbox: {n.caminho.stem}"))
    achados.sort(key=lambda a: (GRAVIDADE.get(a.gravidade, 9), a.nota))
    return achados


def _marcar_contestado(cofre: Cofre, nota: Nota, motivo: str) -> None:
    autor = Autor("cofre-revisar")
    with cofre.trava():
        atual = ler_nota(nota.caminho)
        atual.meta.update(status="contestado", contestado_em=hoje(), motivo=motivo)
        corpo = _corpo_fato(atual.meta, secoes(atual.corpo), _linha_hist(f"**contestado**: {motivo}", autor))
        cofre.salvar(Nota(nota.caminho, atual.meta, corpo))


def relatorio(achados: list[Achado], titulo: str = "Revisão do cofre") -> str:
    if not achados:
        return f"# {titulo} — {hoje()}\n\nNenhum problema encontrado."
    contagem = {g: sum(1 for a in achados if a.gravidade == g) for g in GRAVIDADE}
    linhas = [f"# {titulo} — {hoje()}", "",
              f"Erros: {contagem['erro']} · Alertas: {contagem['alerta']} · Info: {contagem['info']}", ""]
    atual = None
    for a in achados:
        if a.gravidade != atual:
            atual = a.gravidade
            linhas += ["", f"## {atual.capitalize()}"]
        linhas.append(f"- **{a.nota}** — {a.mensagem}")
    return "\n".join(linhas).replace("\n\n\n", "\n\n") + "\n"


def salvar_relatorio(cofre: Cofre, texto: str) -> str:
    destino = cofre.raiz / PASTAS["sistema"] / "Relatorios" / f"Revisao {hoje()}.md"
    escrever_atomico(destino, "---\ntipo: relatorio\n---\n" + texto)
    return cofre.relativo(destino)
