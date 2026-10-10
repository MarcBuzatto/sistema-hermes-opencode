"""Linha de comando do cofre (uso humano, hooks e comandos dos agentes)."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

from . import __version__, contexto, notebooklm, registrar
from . import skills as skills_mod
from .config import ErroCofre, arquivo_config_usuario, gravar_config_usuario, ler_config_usuario, resolver_vault
from .registrar import Autor
from .revisar import relatorio, revisar, salvar_relatorio
from .vault import Cofre

MARCAS_AGENTE = ("OPENCODE", "CLAUDECODE", "CODEX_SANDBOX", "HERMES_SESSION_KEY", "HERMES_SESSION_ID", "COFRE_AGENTE")


def _dentro_de_agente() -> bool:
    return any(os.environ.get(v) for v in MARCAS_AGENTE)


def _autor(args) -> Autor:
    if getattr(args, "humano", False):
        if _dentro_de_agente():
            raise ErroCofre("--humano não é aceito quando o comando roda dentro de um agente. Use as ferramentas cofre_* (MCP).")
        return Autor(humano=True)
    if not _dentro_de_agente() and sys.stdin.isatty() and sys.stdout.isatty():
        return Autor(humano=True)
    return Autor(nome=os.environ.get("COFRE_AGENTE") or "cli", modelo=getattr(args, "agente", None))


def _cofre(args) -> Cofre:
    return Cofre(resolver_vault(args.vault))


def _imprimir(texto: str) -> None:
    saida = sys.stdout
    try:
        saida.write(texto.rstrip("\n") + "\n")
    except UnicodeEncodeError:
        saida.buffer.write((texto.rstrip("\n") + "\n").encode("utf-8"))


def _dir_template() -> Path:
    return Path(__file__).resolve().parent.parent / "vault-template"


# ---- comandos -------------------------------------------------------------
def cmd_contexto(a):
    _imprimir(contexto.montar(_cofre(a), cwd=a.cwd or os.getcwd(), projeto=a.projeto, max_chars=a.max, modo=a.modo))


def cmd_buscar(a):
    _imprimir(contexto.buscar(_cofre(a), a.consulta, projeto=a.projeto, tipo=a.tipo, status=a.status, limite=a.limite))


def cmd_ler(a):
    _imprimir(contexto.ler(_cofre(a), a.id))


def cmd_fato(a):
    r = registrar.registrar_fato(
        _cofre(a), _autor(a), a.afirmacao, status=a.status, evidencias=a.evidencia, projeto=a.projeto,
        contexto=a.contexto or "", tags=a.tag, criticidade="alta" if a.alta else "normal", forcar=a.forcar,
        cwd=a.cwd or os.getcwd(),
    )
    _imprimir(r.texto())


def _atualizar(acao):
    def cmd(a):
        r = registrar.atualizar_fato(
            _cofre(a), _autor(a), a.id, acao, evidencias=getattr(a, "evidencia", None),
            motivo=getattr(a, "motivo", "") or "", afirmacao_correta=getattr(a, "correto", None), cwd=os.getcwd(),
        )
        _imprimir(r.texto())
    return cmd


def cmd_decisao(a):
    r = registrar.decisao(
        _cofre(a), _autor(a), "registrar", titulo=a.titulo, decisao_txt=a.decisao, contexto=a.contexto or "",
        alternativas=a.alternativa, consequencias=a.consequencia, status="aceita" if a.aceita else "proposta",
        citacao_usuario=a.citacao or "", projeto=a.projeto, substitui=a.substitui, cwd=os.getcwd(),
    )
    _imprimir(r.texto())


def _decisao_acao(acao):
    def cmd(a):
        r = registrar.decisao(_cofre(a), _autor(a), acao, ident=a.id, citacao_usuario=a.citacao or "",
                              motivo=a.motivo or "")
        _imprimir(r.texto())
    return cmd


def cmd_checkpoint(a):
    r = registrar.checkpoint(
        _cofre(a), _autor(a), a.resumo, feito=a.feito, proximos_passos=a.proximo, bloqueios=a.bloqueio,
        foco=a.foco, projeto=a.projeto, sessao_id=a.sessao, cwd=a.cwd or os.getcwd(),
    )
    _imprimir(r.texto())


def cmd_capturar(a):
    _imprimir(registrar.capturar(_cofre(a), _autor(a), a.texto, titulo=a.titulo, projeto=a.projeto,
                                 cwd=os.getcwd()).texto())


def cmd_projeto(a):
    cofre = _cofre(a)
    if a.acao == "listar":
        _imprimir(registrar.projeto_listar(cofre))
    elif a.acao == "criar":
        if not a.slug:
            raise ErroCofre("Informe o slug: cofre projeto criar loja-acme --nome 'Loja Acme' --caminho .")
        caminhos = [os.path.abspath(c) if c in (".", "./") else c for c in (a.caminho or [])]
        _imprimir(registrar.projeto_criar(cofre, _autor(a), a.slug, nome=a.nome, caminhos=caminhos, repos=a.repo,
                                          cliente=a.cliente, descricao=a.descricao or "", stack=a.stack).texto())
    else:
        if not a.slug:
            raise ErroCofre("Informe o slug do projeto.")
        caminho = (a.caminho or [None])[0]
        if caminho in (".", "./"):
            caminho = os.getcwd()
        _imprimir(registrar.projeto_vincular(cofre, _autor(a), a.slug, caminho=caminho,
                                             repo=(a.repo or [None])[0]).texto())


def cmd_missao(a):
    cofre = _cofre(a)
    if a.acao == "listar":
        _imprimir(registrar.missao_listar(cofre, status=a.status or "ativa"))
    elif a.acao == "criar":
        _imprimir(registrar.missao_criar(cofre, _autor(a), a.alvo or "", a.objetivo or "", criterios=a.criterio,
                                         passos=a.passo, projetos=a.projeto).texto())
    else:
        _imprimir(registrar.missao_atualizar(cofre, _autor(a), a.alvo or "", concluir_passo=a.concluir,
                                             adicionar_passo=a.adicionar, status=a.status, nota_log=a.nota).texto())


def cmd_revisar(a):
    cofre = _cofre(a)
    if a.projeto_atual and not a.projeto:
        proj = contexto.resolver_projeto(cofre, os.getcwd())
        if not proj:
            _imprimir("Nenhum projeto do cofre associado a este diretório; revisando o cofre inteiro.")
        a.projeto = proj.nome if proj else None
    achados = revisar(cofre, projeto=a.projeto, conferir_evidencias=not a.sem_conferir, aplicar=a.aplicar,
                      cwd=os.getcwd())
    texto = relatorio(achados)
    _imprimir(texto)
    if a.salvar:
        _imprimir(f"\nRelatório salvo em {salvar_relatorio(cofre, texto)}")
    return 1 if any(x.gravidade == "erro" for x in achados) and a.estrito else 0


def cmd_exportar(a):
    arquivos = notebooklm.exportar(_cofre(a), a.projeto, incluir_hipoteses=a.hipoteses)
    _imprimir("Arquivos para enviar ao NotebookLM (um por fonte):\n" + "\n".join(f"- {p}" for p in arquivos))


def cmd_importar(a):
    texto = sys.stdin.read() if a.arquivo == "-" else Path(a.arquivo).read_text(encoding="utf-8")
    titulo = a.titulo or (Path(a.arquivo).stem if a.arquivo != "-" else "Resposta do NotebookLM")
    _imprimir(notebooklm.importar(_cofre(a), texto, titulo, projeto=a.projeto, notebook=a.notebook,
                                  autor=_autor(a)).texto())


def _hermes_home(explicito: str | None) -> Path:
    if explicito:
        return Path(os.path.expanduser(explicito))
    if os.environ.get("HERMES_HOME"):
        return Path(os.environ["HERMES_HOME"])
    if os.name == "nt":
        return Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local"))) / "hermes"
    return Path.home() / ".hermes"


def cmd_importar_memoria(a):
    cofre = _cofre(a)
    pasta = _hermes_home(a.hermes_home) / "memories"
    total = 0
    for arquivo, rotulo in (("MEMORY.md", "memória do agente"), ("USER.md", "perfil do usuário")):
        caminho = pasta / arquivo
        if not caminho.is_file():
            continue
        entradas = [e.strip() for e in caminho.read_text(encoding="utf-8", errors="replace").split("§") if e.strip()]
        for entrada in entradas:
            registrar.capturar(
                cofre, Autor(nome="hermes-memoria"),
                f"Entrada antiga da {rotulo} do Hermes ({arquivo}). NÃO verificada: confirme antes de virar fato "
                f"ou preferência.\n\n{entrada}",
                titulo=f"Hermes {arquivo}: {' '.join(entrada.split())[:60]}", projeto=a.projeto,
            )
            total += 1
    _imprimir(f"{total} entradas importadas para a inbox (01-Inbox) para triagem." if total
              else f"Nenhuma memória encontrada em {pasta}.")


def _destino_skills_opencode() -> Path:
    base = os.environ.get("OPENCODE_CONFIG_DIR") or str(Path.home() / ".config" / "opencode")
    return Path(base) / "skills"


def cmd_skills(a):
    cofre = _cofre(a)
    if a.acao == "listar":
        _imprimir(skills_mod.resumo(cofre.raiz))
    elif a.acao == "verificar":
        achados = skills_mod.verificar(cofre.raiz)
        _imprimir("\n".join(f"- [{g}] {n}: {m}" for g, n, m in achados) or "Skills sem problemas.")
        return 1 if any(g == "erro" for g, _, _ in achados) else 0
    else:
        destino = Path(os.path.expanduser(a.destino)) if a.destino else _destino_skills_opencode()
        copiadas, removidas, avisos = skills_mod.sincronizar(cofre.raiz, destino, remover=a.remover)
        _imprimir(f"Destino: {destino}\nCopiadas: {len(copiadas)} · Removidas: {len(removidas)}"
                  + "".join(f"\n[aviso] {x}" for x in avisos))


def cmd_mcp(a):
    from .mcp import main as mcp_main
    return mcp_main(a.vault)


def cmd_init(a):
    destino = Path(os.path.expanduser(a.destino)).resolve()
    origem = Path(a.template).resolve() if a.template else _dir_template()
    if not origem.is_dir():
        raise ErroCofre(f"Template do vault não encontrado em {origem}.")
    dentro_de_vault = any((p / ".obsidian").is_dir() for p in [destino, *destino.parents])
    criados, mantidos = 0, 0
    for arq in origem.rglob("*"):
        if arq.is_dir():
            continue
        rel = arq.relative_to(origem)
        if rel.parts[0] == ".obsidian" and dentro_de_vault:
            continue
        alvo = destino / rel
        if alvo.exists():
            mantidos += 1
            continue
        alvo.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(arq, alvo)
        criados += 1
    if a.registrar:
        gravar_config_usuario({"vault": str(destino)})
    _imprimir(f"Vault em {destino}: {criados} arquivos criados, {mantidos} já existiam (preservados)."
              + (f"\nConfig do usuário atualizada: {arquivo_config_usuario()}" if a.registrar else ""))


def cmd_hook_hermes(a):
    """Modo shell hook (alternativa ao plugin): lê JSON do Hermes em stdin e devolve {"context": ...}."""
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except ValueError:
        payload = {}
    extra = payload.get("extra") or {}
    try:
        cofre = Cofre(resolver_vault(a.vault))
        modo = "sistema" if extra.get("is_first_turn") else "ancora"
        texto = contexto.montar(cofre, cwd=payload.get("cwd") or os.getcwd(), modo=modo)
    except ErroCofre:
        texto = ""
    _imprimir(json.dumps({"context": texto} if texto else {}, ensure_ascii=False))


def cmd_doctor(a):
    linhas = [f"cofre {__version__} · Python {sys.version.split()[0]} · {sys.executable}"]
    cfg = ler_config_usuario()
    linhas.append(f"config do usuário: {arquivo_config_usuario()} {'[ok]' if cfg else '[ausente]'}")
    try:
        cofre = _cofre(a)
        notas = cofre.notas()
        linhas.append(f"vault: {cofre.raiz} [ok] · {len(notas)} notas · {len(cofre.projetos())} projetos")
        linhas.append(f"git no vault: {'[ok]' if (cofre.raiz / '.git').exists() else '[sem git: sem histórico de quem gravou o quê]'}")
        proj = contexto.resolver_projeto(cofre, os.getcwd())
        linhas.append(f"projeto do diretório atual: {proj.nome if proj else '(nenhum)'}")
        linhas.append(f"skills no vault: {len(skills_mod.listar(cofre.raiz))} em {skills_mod.pasta_skills(cofre.raiz)}")
    except ErroCofre as e:
        linhas.append(f"vault: [erro] {e}")
    for rotulo, caminho in _integracoes():
        linhas.append(f"{rotulo}: {'[ok]' if caminho.exists() else '[não instalado]'} {caminho}")
    _imprimir("\n".join(linhas))


def _integracoes() -> list[tuple[str, Path]]:
    oc = Path(os.environ.get("OPENCODE_CONFIG_DIR") or (Path.home() / ".config" / "opencode"))
    hh = _hermes_home(None)
    return [
        ("OpenCode opencode.json", oc / "opencode.json"),
        ("OpenCode comandos", oc / "commands" / "checkpoint.md"),
        ("OpenCode plugin", oc / "plugins" / "cofre.js"),
        ("Hermes plugin", hh / "plugins" / "cofre" / "__init__.py"),
    ]


# ---- parser ---------------------------------------------------------------
def criar_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="cofre", description="Memória epistêmica em Obsidian para agentes de IA.")
    p.add_argument("--vault", help="Caminho do vault (padrão: COFRE_VAULT ou config do usuário)")
    p.add_argument("--version", action="version", version=f"cofre {__version__}")
    sub = p.add_subparsers(dest="comando", required=True)

    def novo(nome, func, ajuda, autor=False):
        sp = sub.add_parser(nome, help=ajuda, description=ajuda)
        sp.set_defaults(func=func)
        if autor:
            sp.add_argument("--humano", action="store_true", help="Grava com autoridade do usuário")
            sp.add_argument("--agente", help="Identificador do modelo (quando chamado por agente)")
        return sp

    sp = novo("contexto", cmd_contexto, "Mostra o pacote de contexto do projeto atual")
    sp.add_argument("--cwd")
    sp.add_argument("--projeto")
    sp.add_argument("--max", type=int)
    sp.add_argument("--modo", choices=["completo", "sistema", "ancora"], default="completo")

    sp = novo("buscar", cmd_buscar, "Busca notas no cofre")
    sp.add_argument("consulta")
    sp.add_argument("--projeto")
    sp.add_argument("--tipo")
    sp.add_argument("--status", nargs="*")
    sp.add_argument("--limite", type=int, default=10)

    sp = novo("ler", cmd_ler, "Lê uma nota pelo ID")
    sp.add_argument("id")

    sp = novo("fato", cmd_fato, "Registra um fato", autor=True)
    sp.add_argument("afirmacao")
    sp.add_argument("--status", default="hipotese", choices=["hipotese", "verificado"])
    sp.add_argument("--evidencia", action="append", help="'tipo :: ref :: trecho' (tipos: arquivo, comando, url, usuario, nota)")
    sp.add_argument("--projeto")
    sp.add_argument("--contexto")
    sp.add_argument("--tag", action="append")
    sp.add_argument("--alta", action="store_true", help="criticidade alta (sempre no contexto)")
    sp.add_argument("--forcar", action="store_true")
    sp.add_argument("--cwd")

    for nome, acao, ajuda, motivo, correto in (
        ("promover", "promover", "Promove hipótese/contestado a verificado", False, False),
        ("evidencia", "adicionar_evidencia", "Anexa evidência a um fato", False, False),
        ("contestar", "contestar", "Marca fato como contestado", True, False),
        ("refutar", "refutar", "Marca fato como refutado (falso)", True, True),
        ("obsoleto", "tornar_obsoleto", "Marca fato como obsoleto", True, True),
        ("reabrir", "reabrir", "Reabre fato como hipótese (só usuário)", False, False),
    ):
        sp = novo(nome, _atualizar(acao), ajuda, autor=True)
        sp.add_argument("id")
        sp.add_argument("--evidencia", action="append")
        if motivo:
            sp.add_argument("--motivo", required=True)
        if correto:
            sp.add_argument("--correto", help="Afirmação correta (cria fato substituto)")

    sp = novo("decisao", cmd_decisao, "Registra uma decisão", autor=True)
    sp.add_argument("titulo")
    sp.add_argument("--decisao", required=True)
    sp.add_argument("--contexto")
    sp.add_argument("--alternativa", action="append")
    sp.add_argument("--consequencia", action="append")
    sp.add_argument("--aceita", action="store_true")
    sp.add_argument("--citacao")
    sp.add_argument("--projeto")
    sp.add_argument("--substitui")
    for nome, acao in (("aceitar-decisao", "aceitar"), ("rejeitar-decisao", "rejeitar")):
        sp = novo(nome, _decisao_acao(acao), f"{acao.capitalize()} uma decisão", autor=True)
        sp.add_argument("id")
        sp.add_argument("--citacao")
        sp.add_argument("--motivo")

    sp = novo("checkpoint", cmd_checkpoint, "Salva progresso (estado + sessão)", autor=True)
    sp.add_argument("--resumo", required=True)
    sp.add_argument("--feito", action="append")
    sp.add_argument("--proximo", action="append")
    sp.add_argument("--bloqueio", action="append")
    sp.add_argument("--foco")
    sp.add_argument("--projeto")
    sp.add_argument("--sessao")
    sp.add_argument("--cwd")

    sp = novo("capturar", cmd_capturar, "Joga texto na inbox", autor=True)
    sp.add_argument("texto")
    sp.add_argument("--titulo")
    sp.add_argument("--projeto")

    sp = novo("projeto", cmd_projeto, "Projetos: listar | criar | vincular", autor=True)
    sp.add_argument("acao", choices=["listar", "criar", "vincular"])
    sp.add_argument("slug", nargs="?")
    sp.add_argument("--nome")
    sp.add_argument("--caminho", action="append", help="Pasta local ('.' = diretório atual)")
    sp.add_argument("--repo", action="append")
    sp.add_argument("--cliente")
    sp.add_argument("--descricao")
    sp.add_argument("--stack", action="append")

    sp = novo("missao", cmd_missao, "Missões: listar | criar | atualizar", autor=True)
    sp.add_argument("acao", choices=["listar", "criar", "atualizar"])
    sp.add_argument("alvo", nargs="?", help="Título (criar) ou ID (atualizar)")
    sp.add_argument("--objetivo")
    sp.add_argument("--criterio", action="append")
    sp.add_argument("--passo", action="append")
    sp.add_argument("--projeto", action="append")
    sp.add_argument("--concluir")
    sp.add_argument("--adicionar")
    sp.add_argument("--status")
    sp.add_argument("--nota")

    sp = novo("revisar", cmd_revisar, "Revisa integridade, validade, evidências e segredos")
    sp.add_argument("--projeto")
    sp.add_argument("--projeto-atual", action="store_true", help="Usa o projeto do diretório atual")
    sp.add_argument("--salvar", action="store_true", help="Grava relatório em 00-Sistema/Relatorios")
    sp.add_argument("--aplicar", action="store_true", help="Marca como contestado o que não confere mais")
    sp.add_argument("--sem-conferir", action="store_true", help="Não confere evidências de arquivo")
    sp.add_argument("--estrito", action="store_true", help="Sai com código 1 se houver erros")

    sp = novo("exportar-notebooklm", cmd_exportar, "Gera arquivos consolidados para o NotebookLM")
    sp.add_argument("projeto", nargs="?")
    sp.add_argument("--hipoteses", action="store_true", help="Inclui arquivo separado de hipóteses")

    sp = novo("importar-notebooklm", cmd_importar, "Importa resposta do NotebookLM como fonte", autor=True)
    sp.add_argument("arquivo", help="Arquivo .md/.txt ou '-' para stdin")
    sp.add_argument("--titulo")
    sp.add_argument("--projeto")
    sp.add_argument("--notebook")

    sp = novo("importar-memoria-hermes", cmd_importar_memoria, "Leva MEMORY.md/USER.md do Hermes para a inbox")
    sp.add_argument("--hermes-home")
    sp.add_argument("--projeto")

    sp = novo("skills", cmd_skills, "Skills do vault (60-Skills): listar | verificar | sincronizar")
    sp.add_argument("acao", choices=["listar", "verificar", "sincronizar"])
    sp.add_argument("--destino", help="sincronizar: pasta de destino (padrão: ~/.config/opencode/skills)")
    sp.add_argument("--remover", action="store_true", help="sincronizar: remove do destino as cópias feitas pelo cofre")

    novo("mcp", cmd_mcp, "Inicia o servidor MCP (stdio)")

    sp = novo("init", cmd_init, "Cria/completa um vault a partir do template")
    sp.add_argument("destino")
    sp.add_argument("--template")
    sp.add_argument("--registrar", action="store_true", help="Grava este vault como padrão na config do usuário")

    novo("hook-hermes", cmd_hook_hermes, "Shell hook pre_llm_call do Hermes (alternativa ao plugin)")
    novo("doctor", cmd_doctor, "Diagnóstico da instalação")
    return p


def main(argv: list[str] | None = None) -> int:
    for fluxo in (sys.stdout, sys.stderr):
        if hasattr(fluxo, "reconfigure"):
            try:
                fluxo.reconfigure(encoding="utf-8", errors="replace")
            except (OSError, ValueError):
                pass
    args = criar_parser().parse_args(argv)
    try:
        codigo = args.func(args)
        return int(codigo or 0)
    except ErroCofre as e:
        print(f"cofre: {e}", file=sys.stderr)
        return 2
