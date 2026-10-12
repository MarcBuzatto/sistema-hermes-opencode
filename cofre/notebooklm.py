"""Ponte com o NotebookLM.

Exportação: consolida as notas de um projeto em poucos arquivos Markdown (o
NotebookLM limita o número de fontes por notebook), separando o que é verificado
do que é hipótese, com o significado de cada status no topo de cada arquivo.

Importação: o que volta do NotebookLM (respostas, briefings, guias) entra como
nota de fonte com confiabilidade "síntese externa". Afirmações tiradas dali só
viram fato como HIPÓTESE citando a fonte, até serem conferidas na origem.
"""

from __future__ import annotations

from pathlib import Path

from . import epistemica as ep
from .config import ErroCofre
from .contexto import rotulo
from .registrar import Autor, Resultado, _commit, _limpar
from .vault import (
    DIR_EXPORTACOES, PASTAS, Cofre, Nota, agora_texto, escrever_atomico, hoje, link, lista, secao, slug,
)

LEGENDA = """> Legenda de confiabilidade (gerado pelo Cofre em {quando}):
> - VERIFICADO: comprovado por evidência (arquivo, comando, documentação ou confirmação do usuário).
> - HIPÓTESE: não comprovado. Não use como fato.
> - CONTESTADO: há evidência conflitante.
> - REFUTADO: comprovadamente falso (mantido para não ser repetido).
> Ao responder, cite o status de cada afirmação que usar.
"""
LIMITE_PALAVRAS = 400_000


def _arquivo(destino: Path, titulo: str, corpo: str) -> Path:
    texto = f"# {titulo}\n\n{LEGENDA.format(quando=agora_texto())}\n{corpo.strip()}\n"
    if len(texto.split()) > LIMITE_PALAVRAS:
        raise ErroCofre(f"{destino.name} passou de {LIMITE_PALAVRAS} palavras; exporte por período ou divida o projeto.")
    escrever_atomico(destino, texto)
    return destino


def _fato_completo(cofre: Cofre, n: Nota) -> str:
    linhas = [f"### {n.id} [{rotulo(n)}] {n.meta.get('afirmacao', '')}"]
    for bruto in lista(n.meta.get("evidencia")):
        try:
            linhas.append(f"- Evidência: {ep.ler_evidencia(bruto).legivel()}")
        except ErroCofre:
            linhas.append(f"- Evidência: {bruto}")
    if n.meta.get("motivo"):
        linhas.append(f"- Motivo: {n.meta['motivo']}")
    if n.meta.get("substituido_por"):
        alvo = cofre.resolver_ref(n.meta["substituido_por"])
        if alvo:
            linhas.append(f"- Correto: {alvo.id} — {alvo.meta.get('afirmacao', '')}")
    contexto = secao(n.corpo, "Contexto").strip()
    if contexto:
        linhas.append(f"- Contexto: {' '.join(contexto.split())[:600]}")
    datas = ", ".join(f"{k}: {n.meta[k]}" for k in ("registrado_em", "verificado_em", "refutado_em") if n.meta.get(k))
    linhas.append(f"- Datas: {datas}")
    return "\n".join(linhas)


def exportar(cofre: Cofre, projeto: str | None, incluir_hipoteses: bool = False) -> list[Path]:
    proj = cofre.projeto(projeto) if projeto else None
    if projeto and not proj:
        raise ErroCofre(f"Projeto '{projeto}' não existe.")
    slug_p = proj.nome if proj else None
    nome = (proj.meta.get("nome") if proj else None) or slug_p or "global"
    pasta = cofre.raiz / DIR_EXPORTACOES / f"{hoje()}-{slug_p or 'global'}"
    pasta.mkdir(parents=True, exist_ok=True)
    fatos = [f for f in cofre.por_tipo("fato") if f.projeto == slug_p]
    gerados = []

    visao = []
    if proj:
        visao.append(proj.corpo.split("## Painel")[0].strip())
        estado = cofre.estado(slug_p)
        if estado:
            visao.append("## Estado atual (escrito por agentes)\n" + estado.corpo.split("\n", 1)[-1].strip())
    missoes = [m for m in cofre.por_tipo("missao")
               if not slug_p or slug_p in [str(p).strip("[]") for p in lista(m.meta.get("projetos"))]]
    if missoes:
        visao.append("## Missões\n" + "\n\n".join(f"### {m.meta.get('titulo')} [{m.status}]\n{m.corpo.split(chr(10), 1)[-1].strip()}"
                                                     for m in missoes))
    gerados.append(_arquivo(pasta / f"01 Visao geral - {nome}.md", f"Visão geral — {nome}", "\n\n".join(visao) or "(sem dados)"))

    verificados = [f for f in fatos if f.status == "verificado"]
    gerados.append(_arquivo(pasta / f"02 Fatos verificados - {nome}.md", f"Fatos verificados — {nome}",
                            "\n\n".join(_fato_completo(cofre, f) for f in verificados) or "(nenhum)"))
    decisoes = [d for d in cofre.por_tipo("decisao") if d.projeto == slug_p and d.status in ("aceita", "substituida")]
    gerados.append(_arquivo(pasta / f"03 Decisoes - {nome}.md", f"Decisões — {nome}",
                            "\n\n".join(f"### {d.id} [{rotulo(d)}] {d.meta.get('titulo')}\n{d.corpo.split(chr(10), 1)[-1].strip()}"
                                        for d in decisoes) or "(nenhuma)"))
    sessoes = sorted([s for s in cofre.por_tipo("sessao") if s.projeto == slug_p], key=lambda s: str(s.meta.get("iniciada")))
    gerados.append(_arquivo(pasta / f"04 Diario de sessoes - {nome}.md", f"Diário de sessões — {nome} (escrito por agentes)",
                            "\n\n".join(f"## {s.meta.get('iniciada')} · {s.meta.get('agente')}\n{secao(s.corpo, 'Checkpoints')}"
                                        for s in sessoes) or "(nenhuma)"))
    problemas = [f for f in fatos if f.status in ("refutado", "contestado", "obsoleto")]
    gerados.append(_arquivo(pasta / f"05 Armadilhas e conflitos - {nome}.md", f"Armadilhas, conflitos e obsoletos — {nome}",
                            "\n\n".join(_fato_completo(cofre, f) for f in problemas) or "(nenhum)"))
    if incluir_hipoteses:
        hipoteses = [f for f in fatos if f.status == "hipotese"]
        gerados.append(_arquivo(pasta / f"06 HIPOTESES NAO VERIFICADAS - {nome}.md",
                                f"HIPÓTESES NÃO VERIFICADAS — {nome} (não usar como fato)",
                                "\n\n".join(_fato_completo(cofre, f) for f in hipoteses) or "(nenhuma)"))
    return gerados


def importar(cofre: Cofre, texto: str, titulo: str, projeto: str | None = None,
             notebook: str | None = None, autor: Autor | None = None) -> Resultado:
    autor = autor or Autor(humano=True)
    texto = str(texto or "").strip()
    if not texto:
        raise ErroCofre("Conteúdo vazio.")
    ep.barrar_segredos(texto)
    proj = cofre.projeto(projeto) if projeto else None
    if projeto and not proj:
        raise ErroCofre(f"Projeto '{projeto}' não existe.")
    with cofre.trava():
        ident = cofre.novo_id("fonte")
        meta = _limpar({
            "tipo": "fonte",
            "id": ident,
            "origem": "notebooklm",
            "notebook": notebook,
            "confiabilidade": "sintese-externa",
            "projeto": link(proj.nome) if proj else None,
            "importado_em": hoje(),
            "registrado_por": autor.assinatura,
            "aliases": [ident],
        })
        corpo = (
            f"# {titulo}\n\n> [!quote] Síntese do NotebookLM. Útil para orientar, mas NÃO é fonte primária. "
            "Afirmações daqui viram fato só como HIPÓTESE (evidência `nota` apontando para este ID) até serem "
            "conferidas na origem.\n\n" + texto + "\n"
        )
        caminho = cofre.raiz / PASTAS["fontes"] / "NotebookLM" / f"{ident} {hoje()} {slug(titulo, 50)}.md"
        cofre.salvar(Nota(caminho, meta, corpo))
    _commit(cofre, [caminho], f"cofre: fonte notebooklm {ident} por {autor.assinatura}")
    return Resultado(f"Importado: {ident} — {titulo}\nArquivo: {cofre.relativo(caminho)}", ident, caminho)
