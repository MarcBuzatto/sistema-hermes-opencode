"""Revisão periódica do cofre: integridade, validade, evidências e segredos."""

from __future__ import annotations

import re
import subprocess
import time
from dataclasses import dataclass
from datetime import date

from . import epistemica as ep
from . import skills as skills_mod
from .contexto import vencido
from .projetos import bases_de_arquivos
from .registrar import Autor, _corpo_fato, _linha_hist
from .vault import (
    _LINK, PASTAS, STATUS_DECISAO, STATUS_FATO, STATUS_MISSAO, STATUS_SPEC, Cofre, Nota, escrever_atomico, hoje,
    ler_nota, lista, para_data, secoes,
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
        if n.tipo == "spec":
            achados += _revisar_spec(n)
        if n.tipo == "captura" and n.status == "pendente":
            criada = para_data(n.meta.get("capturado_em"))
            idade = f" (há {(hoje_d - criada).days} dias)" if criada and (hoje_d - criada).days >= 2 else ""
            achados.append(Achado("info", _rotulo(n), f"captura pendente de triagem na inbox{idade}: {n.caminho.stem}"))
    if not projeto:
        achados += [Achado(g, n, m) for g, n, m in skills_mod.verificar(cofre.raiz)]
        achados += _revisar_notas_livres(cofre)
        achados += _revisar_privadas(cofre)
    achados.sort(key=lambda a: (GRAVIDADE.get(a.gravidade, 9), a.nota))
    return achados


_FORA_DAS_LIVRES = (PASTAS["sistema"], PASTAS["inbox"], PASTAS["sessoes_gerais"], PASTAS["arquivo"])
_TITULO_SECAO = re.compile(r"^#{2,6}[ \t]+\S", re.M)


def _revisar_notas_livres(cofre: Cofre) -> list[Achado]:
    """Notas que você escreveu (sem `tipo`): sem nenhum link, temas com 3+ notas sem MOC, notas longas."""
    livres, mocs, alvos, paradas = [], [], set(), []
    for caminho in cofre._arquivos():
        try:
            nota, idade = ler_nota(caminho), time.time() - caminho.stat().st_mtime
        except OSError:
            continue
        rel = cofre.relativo(caminho)
        links = {re.sub(r"\.md$", "", m.strip().rsplit("/", 1)[-1].lower()) for m in _LINK.findall(nota.texto())}
        alvos |= links
        tags = {str(t).lower().lstrip("#") for t in lista(nota.meta.get("tags"))}
        if nota.meta.get("exemplo") or caminho.name == "LEIA-ME.md":
            continue
        if rel.startswith(PASTAS["inbox"] + "/"):
            if not nota.tipo and idade > 3 * 86400:
                paradas.append(rel)
            continue
        if rel.startswith(tuple(p + "/" for p in _FORA_DAS_LIVRES)):
            continue
        if nota.tipo == "moc" or (not nota.tipo and "moc" in tags):
            mocs.append(links)
        elif not nota.tipo:
            nomes = {caminho.stem.lower(), *(str(a).lower() for a in lista(nota.meta.get("aliases")))}
            livres.append((rel, nota, links, nomes, tags - {"moc"}))
    saida: list[Achado] = []
    if paradas:
        saida.append(Achado("info", PASTAS["inbox"], f"{len(paradas)} nota(s) sua(s) na inbox há mais de 3 dias: "
                                                    "transforme em nota permanente (com pelo menos um link) ou apague"))
    orfas = [rel for rel, _n, links, nomes, _t in livres if not links and not (nomes & alvos)]
    if orfas:
        mostra = ", ".join(orfas[:8]) + (f" e mais {len(orfas) - 8}" if len(orfas) > 8 else "")
        saida.append(Achado("info", "notas", f"{len(orfas)} nota(s) sem nenhum [[link]] (nem para ela, nem dela): {mostra}. "
                                          "Ligue cada uma a pelo menos uma nota ou MOC do assunto."))
    cobertas = set().union(*mocs) if mocs else set()
    grupos: dict[str, list] = {}
    for rel, _n, _l, nomes, tags in livres:
        pasta = rel.rsplit("/", 1)[0] if "/" in rel else ""
        chaves = {f"tag #{t}" for t in tags}
        if pasta.startswith(PASTAS["conhecimento"] + "/"):
            chaves.add(f"pasta {pasta}")
        for c in chaves:
            grupos.setdefault(c, []).append(nomes)
    sem_mapa = [(c, len(m)) for c, m in grupos.items()
                if len(m) >= 3 and sum(1 for nomes in m if nomes & cobertas) * 2 < len(m)]
    for chave, qtd in sorted(sem_mapa, key=lambda x: (-x[1], x[0]))[:10]:
        saida.append(Achado("info", "notas", f"{qtd} notas em {chave} sem mapa do assunto: crie um MOC "
                                          f"({PASTAS['conhecimento']}/MOCs/, template MOC) ligando-as; a IA abre o MOC primeiro e gasta menos."))
    for rel, nota, _l, _nm, _t in livres:
        palavras = len(nota.corpo.split())
        if palavras > 4000:
            saida.append(Achado("info", rel, f"nota com ~{palavras} palavras: se trata de vários assuntos, quebre em notas menores + MOC"))
        elif palavras > 1500 and not _TITULO_SECAO.search(nota.corpo):
            saida.append(Achado("info", rel, f"nota com ~{palavras} palavras e sem títulos (##): ponha títulos para a IA ler só a parte útil"))
    return saida


def _revisar_privadas(cofre: Cofre) -> list[Achado]:
    """Pasta privada dentro de um vault com git: precisa estar no .gitignore e fora do índice do git."""
    from .gitlog import _git

    if not (cofre.raiz / ".git").exists():
        return []
    saida = []
    for rel in cofre.pastas_privadas():
        if not (cofre.raiz / rel).is_dir():
            continue
        try:
            ignorada = _git(cofre.raiz, "check-ignore", "-q", rel + "/").returncode == 0
            versionados = _git(cofre.raiz, "ls-files", "--", rel).stdout.strip()
        except (OSError, subprocess.SubprocessError):
            continue
        if versionados:
            saida.append(Achado("erro", rel, f"pasta privada já está versionada no git do vault: rode "
                                             f"`git -C \"{cofre.raiz}\" rm -r --cached \"{rel}\"` (o histórico antigo continua com o conteúdo)"))
        if not ignorada:
            saida.append(Achado("erro", rel, f"pasta privada fora do .gitignore do vault: acrescente a linha `{rel}/`"))
    return saida


def _revisar_spec(n: Nota) -> list[Achado]:
    from . import specs

    rot, s, saida = _rotulo(n), specs.carregar(n), []
    if n.status not in STATUS_SPEC:
        return [Achado("erro", rot, f"status de spec inválido '{n.status}' (use {', '.join(STATUS_SPEC)})")]
    if n.status in ("aprovada", "em_execucao", "concluida") and s.alterada_apos_aprovacao():
        saida.append(Achado("alerta", rot, "requisitos/tarefas mudaram depois da aprovação; precisa de nova aprovação"))
    if n.status != "rascunho" and not n.meta.get("citacao_usuario") and "pelo usuário" not in s.historico:
        saida.append(Achado("alerta", rot, "spec aprovada sem citação do usuário"))
    abertas = [t.id for t in s.tarefas if t.estado not in ("concluida", "cancelada")]
    if n.status == "concluida" and abertas:
        saida.append(Achado("alerta", rot, f"spec marcada como concluída com tarefas abertas: {', '.join(abertas)}"))
    for t in s.tarefas:
        if t.estado == "concluida" and not re.search(rf"\b{t.id} concluída\b", s.historico):
            saida.append(Achado("alerta", rot, f"{t.id} marcada como pronta direto na nota, sem a verificação do cofre"))
    return saida


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
