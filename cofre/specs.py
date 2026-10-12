"""Spec-Driven Development com tarefas verificáveis (o "harness" do cofre).

Fluxo: rascunho -> aprovada -> em_execucao -> concluida (ou cancelada).

- A spec diz O QUE fazer: objetivo, requisitos (R1, R2...), fora de escopo, perguntas em
  aberto, plano e tarefas (T1, T2...). Cada tarefa diz qual requisito cobre e qual comando
  prova que ficou pronta.
- Só o usuário aprova: citação literal dele (agente) ou --humano. Para aprovar, todo
  requisito precisa de tarefa, toda tarefa precisa de verificação e não pode haver pergunta
  aberta. A aprovação congela objetivo, requisitos e tarefas por hash; mudou depois, volta
  para rascunho e precisa de nova aprovação.
- Uma tarefa por vez. Concluir = o cofre roda o comando de verificação na pasta do projeto;
  a tarefa só fica pronta se o comando sair com código 0. Três falhas seguidas bloqueiam a
  tarefa (pare e peça ajuda). O modelo não tem como marcar "pronto" sem a verificação passar.
- Ao concluir a última tarefa o cofre roda todas as verificações de novo (regressão).
- O cofre não usa shell e só executa comandos de teste/lint/build conhecidos (ou os que o
  usuário liberar em `verificacao_comandos` no config.md). Os demais viram verificação
  manual: concluir exige a confirmação do usuário.
"""

from __future__ import annotations

import hashlib
import os
import re
import shlex
import shutil
import subprocess
import time
from dataclasses import dataclass, field

from . import epistemica as ep
from .config import ErroCofre
from .normalizar import chave as chave_normal
from .projetos import _converter_caminho, dentro_de, resolver_projeto
from .registrar import Autor, Resultado, _commit, _limpar, _linha_hist
from .vault import Cofre, Nota, agora, hoje, juntar_secoes, ler_nota, lista, secoes, slug

MAX_FALHAS = 3

# Acrescentado ao prompt quando o agente "spec" (OpenCode) ou a personality "spec" (Hermes) está ativo.
INSTRUCOES_MODO_SPEC = """MODO SPEC (Spec-Driven Development com o cofre). Siga em ordem, sem pular etapa:
1. Entender: leia o código relacionado antes de propor. Dúvida que só o usuário responde vira pergunta na spec; não suponha.
2. Especificar: cofre_spec(acao='criar') com objetivo, requisitos no formato "QUANDO <situação>, O SISTEMA DEVE <comportamento>", fora_escopo e perguntas.
3. Tarefas: pequenas e em ordem, cada uma com 'cobre' (R1...) e 'verificar' = comando que sai com código 0 quando a tarefa está pronta (teste específico, lint, typecheck, build). Se o teste ainda não existe, a tarefa cria o teste. 'manual' só para o que não dá para testar (visual).
4. Aprovar: mostre requisitos e tarefas ao usuário e PARE. Só chame cofre_spec(acao='aprovar') com as palavras exatas dele em citacao_usuario. Não edite código antes da aprovação.
5. Implementar: cofre_tarefa(acao='proxima'), faça SÓ essa tarefa, rode a verificação você mesmo e, passando, cofre_tarefa(acao='concluir'). O cofre roda o comando de novo e só aceita se passar.
6. Falhou: leia a saída, corrija o código e tente de novo. Nunca enfraqueça o teste, nunca troque o comando de verificação e nunca marque tarefa como pronta editando a nota. 3 falhas = tarefa bloqueada: pare e mostre o erro ao usuário.
7. Escopo mudou: cofre_spec(acao='adicionar'); a spec volta para aprovação.
8. Ao fim de cada tarefa: cofre_checkpoint curto.
A linha AGORA do contexto diz em que passo você está: siga ela."""
SECOES = ("Objetivo", "Requisitos", "Fora de escopo", "Perguntas em aberto", "Plano", "Tarefas", "Histórico")
MARCAS = {" ": "pendente", "/": "em_andamento", "x": "concluida", "!": "bloqueada", "-": "cancelada"}
MARCA_DE = {v: k for k, v in MARCAS.items()}

_TAREFA = re.compile(r"^- \[(.)\] (T\d+):\s*(.*)$")
_REQUISITO = re.compile(r"^- (R\d+):\s*(.*)$")
_PERGUNTA = re.compile(r"^- \[([ xX])\] (P\d+):\s*(.*)$")
_ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")
# Metacaracteres de shell e caracteres de controle (tab, NUL etc.) e comentário. A verificação roda
# com subprocess (lista de argumentos, sem shell), então isto é defesa em profundidade: um comando de
# teste legítimo não tem nada disso, e o que tiver vira verificação manual.
_SHELL = re.compile(r"[;&|<>`$#\t\x00-\x08\x0b\x0c\x0e-\x1f]" + ("|[%^\r\n]" if os.name == "nt" else r"|[\r\n]"))


# ---- modelo ---------------------------------------------------------------------
@dataclass
class Tarefa:
    id: str
    descricao: str
    marca: str = " "
    cobre: list[str] = field(default_factory=list)
    verificar: str = ""
    falhas: int = 0
    motivo: str = ""

    @property
    def estado(self) -> str:
        return MARCAS.get(self.marca, "pendente")

    def render(self) -> str:
        partes = [f"- [{self.marca}] {self.id}: {self.descricao}"]
        if self.cobre:
            partes.append("cobre: " + ", ".join(self.cobre))
        partes.append("verificar: " + (f"`{self.verificar}`" if self.verificar and self.verificar != "manual" else "manual"))
        if self.falhas:
            partes.append(f"falhas: {self.falhas}")
        if self.motivo:
            partes.append(f"motivo: {self.motivo}")
        return " · ".join(partes)

    def definicao(self) -> str:
        return f"{self.id}|{self.descricao}|{','.join(self.cobre)}|{self.verificar}"


@dataclass
class Spec:
    nota: Nota
    objetivo: str
    requisitos: list[tuple[str, str]]
    fora_escopo: list[str]
    perguntas: list[tuple[str, bool, str]]
    plano: str
    tarefas: list[Tarefa]
    historico: str

    @property
    def id(self) -> str:
        return self.nota.id

    @property
    def status(self) -> str:
        return self.nota.status

    @property
    def titulo(self) -> str:
        return str(self.nota.meta.get("titulo") or self.nota.nome)

    def hash(self) -> str:
        base = "\n".join([
            " ".join(self.objetivo.split()),
            *[f"{r}:{' '.join(t.split())}" for r, t in self.requisitos],
            *[" ".join(x.split()) for x in self.fora_escopo],
            *[t.definicao() for t in self.tarefas],
        ])
        return hashlib.sha256(base.encode("utf-8")).hexdigest()[:16]

    def alterada_apos_aprovacao(self) -> bool:
        aprovado = str(self.nota.meta.get("hash_aprovado") or "")
        return bool(aprovado) and aprovado != self.hash()

    def tarefa(self, ref) -> Tarefa | None:
        m = re.search(r"\d+", str(ref or ""))
        alvo = f"T{int(m.group())}" if m else ""
        return next((t for t in self.tarefas if t.id == alvo), None)

    def em_andamento(self) -> Tarefa | None:
        return next((t for t in self.tarefas if t.estado == "em_andamento"), None)

    def abertas(self) -> list[tuple[str, bool, str]]:
        return [p for p in self.perguntas if not p[1]]


def _itens(texto: str) -> list[str]:
    return [linha.strip()[2:].strip() for linha in texto.split("\n") if linha.strip().startswith("- ")]


def _ler_tarefa(linha: str) -> Tarefa | None:
    m = _TAREFA.match(linha.strip())
    if not m:
        return None
    marca, ident, resto = m.groups()
    partes = [p.strip() for p in resto.split(" · ")]
    t = Tarefa(ident, partes[0], marca if marca in MARCAS else " ")
    for p in partes[1:]:
        chave, _, valor = p.partition(":")
        chave, valor = chave.strip().lower(), valor.strip()
        if chave == "cobre":
            t.cobre = [r.strip().upper() for r in re.split(r"[,\s]+", valor) if r.strip()]
        elif chave == "verificar":
            t.verificar = valor.strip("`").strip()
        elif chave == "falhas" and valor.isdigit():
            t.falhas = int(valor)
        elif chave == "motivo":
            t.motivo = valor
    return t


def carregar(nota: Nota) -> Spec:
    mapa = {t: x for t, x in secoes(nota.corpo) if t}
    requisitos = [m.groups() for m in (_REQUISITO.match(linha.strip()) for linha in mapa.get("Requisitos", "").split("\n")) if m]
    perguntas = []
    for linha in mapa.get("Perguntas em aberto", "").split("\n"):
        m = _PERGUNTA.match(linha.strip())
        if m:
            perguntas.append((m.group(2), m.group(1).lower() == "x", m.group(3)))
    tarefas = [t for t in (_ler_tarefa(linha) for linha in mapa.get("Tarefas", "").split("\n")) if t]
    return Spec(nota, mapa.get("Objetivo", "").strip(), requisitos, _itens(mapa.get("Fora de escopo", "")),
                perguntas, mapa.get("Plano", "").strip(), tarefas, mapa.get("Histórico", "").strip())


def _corpo(s: Spec) -> str:
    return juntar_secoes([
        (None, f"# {s.titulo}"),
        ("Objetivo", s.objetivo or "(defina)"),
        ("Requisitos", "\n".join(f"- {r}: {t}" for r, t in s.requisitos) or "(nenhum)"),
        ("Fora de escopo", "\n".join(f"- {x}" for x in s.fora_escopo) or "(nada declarado)"),
        ("Perguntas em aberto", "\n".join(f"- [{'x' if ok else ' '}] {p}: {t}" for p, ok, t in s.perguntas) or "(nenhuma)"),
        ("Plano", s.plano or "(a definir)"),
        ("Tarefas", "\n".join(t.render() for t in s.tarefas) or "(nenhuma)"),
        ("Histórico", s.historico),
    ])


def _salvar(cofre: Cofre, s: Spec, autor: Autor, log: str) -> None:
    s.historico = (s.historico.rstrip("\n") + "\n" + _linha_hist(log, autor)).strip("\n")
    s.nota.meta["atualizada"] = agora()
    s.nota.corpo = _corpo(s)
    cofre.salvar(s.nota)


# ---- comandos de verificação ------------------------------------------------------
_FERRAMENTAS = {
    "pytest", "ruff", "mypy", "pyright", "tox", "nox", "tsc", "eslint", "vitest", "jest", "playwright", "biome",
    "prettier", "phpunit", "pest", "phpstan", "golangci-lint", "rg", "grep", "stylelint", "cypress", "mocha",
}
_SUBCOMANDOS = {
    "npm": {"test", "t", "run", "run-script"}, "pnpm": {"test", "t", "run"}, "yarn": {"test", "run"},
    "bun": {"test", "run"}, "deno": {"test", "check", "lint", "fmt"}, "go": {"test", "vet", "build"},
    "cargo": {"test", "check", "clippy", "build", "fmt", "nextest"}, "dotnet": {"test", "build"},
    "flutter": {"test", "analyze"}, "dart": {"test", "analyze", "format"}, "mvn": {"test", "verify", "package"},
    "mvnw": {"test", "verify", "package"}, "gradle": {"test", "check", "build", "lint"},
    "gradlew": {"test", "check", "build", "lint"}, "composer": {"test", "run-script", "run", "validate"},
    "swift": {"test", "build"},
}
# Script de package.json/composer que pode ser rodado como verificação: só os com cara de checagem.
_SCRIPT_VERIFICACAO = re.compile(r"^(test|tests|lint|typecheck|type-check|types|check|build|e2e|verify|spec|"
                                 r"format:check|fmt:check|ci|coverage)([:\-_.].*)?$", re.I)
# Nomes de alvo/script (make, npm run, ./scripts/x.sh) que não são verificação.
_PERIGOSAS = re.compile(r"(?i)deploy|publish|release|migrat|seed|drop|destroy|push|upload|prod\b|production|"
                        r"install|login|logout|clean|reset|serve|start|dev\b|watch")
_PY_MODULOS = {"pytest", "unittest", "mypy", "ruff", "pylint", "flake8", "black", "compileall", "doctest", "tox"}
_LIVRES = {"make", "just", "task"}


def _programa(argv0: str) -> str:
    nome = argv0.replace("\\", "/").rsplit("/", 1)[-1].lower()
    for ext in (".cmd", ".exe", ".bat", ".ps1"):
        if nome.endswith(ext):
            nome = nome[: -len(ext)]
    return nome


def _relativo_seguro(caminho: str) -> bool:
    c = caminho.replace("\\", "/")
    return not (c.startswith("/") or re.match(r"^[A-Za-z]:", c) or ".." in c.split("/"))


def _argv_permitido(argv: list[str]) -> bool:
    if not argv:
        return False
    prog = _programa(argv[0])
    resto = list(argv[1:])
    nao_flag = next((a for a in resto if not a.startswith("-")), "")
    interpretador = bool(re.fullmatch(r"python[0-9.]*|py|node", prog))
    if "/" in argv[0].replace("\\", "/") and not _relativo_seguro(argv[0]) and not interpretador:
        return False
    if prog in _LIVRES:
        return not any(_PERIGOSAS.search(a) for a in resto if not a.startswith("-"))
    if prog in _FERRAMENTAS:
        return True
    if prog in _SUBCOMANDOS:
        if prog in ("npm", "pnpm", "yarn", "bun", "composer") and nao_flag in ("run", "run-script"):
            script = next((a for a in resto[resto.index(nao_flag) + 1:] if not a.startswith("-")), "")
            return bool(_SCRIPT_VERIFICACAO.match(script)) and not _PERIGOSAS.search(script)
        return nao_flag in _SUBCOMANDOS[prog] or (prog in ("gradle", "gradlew") and nao_flag.startswith(("test", "assemble", "lint")))
    if interpretador and prog != "node":
        if len(resto) >= 2 and resto[0] == "-m":
            return resto[1] in _PY_MODULOS
        return bool(resto) and resto[0].endswith(".py") and _relativo_seguro(resto[0])
    if prog == "node":
        return bool(resto) and (resto[0] == "--test" or (resto[0].endswith((".js", ".mjs", ".cjs")) and _relativo_seguro(resto[0])))
    if prog == "npx":
        alvo = [a for a in resto if a not in ("--no-install", "--no")]
        return bool(alvo) and _programa(alvo[0]) in _FERRAMENTAS
    if prog in ("uv", "poetry", "pipenv") and resto and resto[0] == "run":
        interno = resto[1:]
        while interno and interno[0].startswith("-"):
            interno.pop(0)
        return _argv_permitido(interno)
    if prog == "php":
        return resto[:2] == ["artisan", "test"] or (bool(resto) and _programa(resto[0]) in _FERRAMENTAS)
    # Script do próprio projeto (./scripts/test.sh, vendor/bin/phpunit, node_modules/.bin/vitest).
    return (argv[0].startswith(("./", ".\\", "vendor/", "node_modules/")) and _relativo_seguro(argv[0])
            and not _PERIGOSAS.search(argv[0].replace("\\", "/").rsplit("/", 1)[-1]))


def avaliar_comando(cmd: str, liberados=()) -> tuple[bool, str]:
    """(o cofre executa automaticamente?, explicação)."""
    cmd = (cmd or "").strip()
    if not cmd or cmd == "manual":
        return False, "verificação manual: o usuário confirma"
    if _SHELL.search(cmd):
        return False, "tem caractere de shell (; | & > < ` $); o cofre não usa shell. Use um comando simples ou um script do projeto"
    try:
        argv = shlex.split(cmd)
    except ValueError:
        return False, "aspas desbalanceadas no comando"
    if any(cmd == x or cmd.startswith(str(x).strip() + " ") for x in liberados if str(x).strip()):
        return True, "liberado em verificacao_comandos"
    if _argv_permitido(argv):
        return True, "comando de teste/lint/build"
    return False, (f"o cofre só roda sozinho comandos de teste/lint/build (não '{cmd}'). Vira verificação manual, ou o "
                   "usuário libera em verificacao_comandos no 00-Sistema/config.md")


def pasta_do_projeto(proj: Nota, cwd: str | None) -> str:
    pastas = []
    for c in lista(proj.meta.get("caminhos")):
        c = os.path.expanduser(str(c))
        alvo = c if os.path.isdir(c) else _converter_caminho(c)
        if alvo and os.path.isdir(alvo):
            pastas.append(alvo)
    for p in pastas:
        if cwd and dentro_de(os.path.abspath(cwd), p):
            return p
    if pastas:
        return pastas[0]
    if cwd and os.path.isdir(cwd):
        return os.path.abspath(cwd)
    raise ErroCofre(f"Não achei a pasta do projeto '{proj.nome}' nesta máquina. Vincule com cofre_projeto(acao='vincular').")


def executar(cmd: str, pasta: str, timeout: int) -> tuple[int | None, str, float]:
    argv = shlex.split(cmd)
    exe = argv[0]
    if exe.startswith(("./", ".\\")) or "/" in exe or "\\" in exe:
        candidato = os.path.join(pasta, exe)
        exe = candidato if os.path.exists(candidato) else (shutil.which(candidato) or candidato)
    else:
        exe = shutil.which(exe) or exe
    env = dict(os.environ, CI="1", NO_COLOR="1", FORCE_COLOR="0", PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
    inicio = time.monotonic()
    try:
        r = subprocess.run([exe, *argv[1:]], cwd=pasta, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=timeout, stdin=subprocess.DEVNULL, env=env)
        codigo, saida = r.returncode, (r.stdout or "") + ("\n" + r.stderr if r.stderr else "")
    except FileNotFoundError:
        raise ErroCofre(f"Programa '{argv[0]}' não encontrado no PATH desta máquina. Instale ou ajuste o comando "
                        "de verificação (isso não conta como falha da tarefa).") from None
    except subprocess.TimeoutExpired as e:
        bruto = e.stdout or b""
        saida = bruto.decode("utf-8", "replace") if isinstance(bruto, bytes) else str(bruto)
        codigo, saida = None, saida + f"\n(tempo esgotado: {timeout}s)"
    return codigo, ep.mascarar_segredos(_ANSI.sub("", saida)).strip(), time.monotonic() - inicio


def _cauda(texto: str, n: int) -> str:
    texto = texto.strip()
    return texto if len(texto) <= n else "…" + texto[-n:]


# ---- leitura -----------------------------------------------------------------------
def _specs(cofre: Cofre, projeto: str | None = None) -> list[Spec]:
    return [carregar(n) for n in cofre.por_tipo("spec") if projeto is None or n.projeto == projeto]


def spec_ativa(cofre: Cofre, projeto: str | None) -> Spec | None:
    """A spec em que o projeto está trabalhando: em execução > aprovada > rascunho mais recente."""
    if not projeto:
        return None
    ordem = {"em_execucao": 0, "aprovada": 1, "rascunho": 2}
    candidatas = [s for s in _specs(cofre, projeto) if s.status in ordem]
    candidatas.sort(key=lambda s: (ordem[s.status], -_tempo(s)))
    return candidatas[0] if candidatas else None


def _tempo(s: Spec) -> float:
    try:
        return s.nota.caminho.stat().st_mtime
    except OSError:
        return 0.0


def _resolver(cofre: Cofre, ref, cwd: str | None, projeto: str | None = None) -> Spec:
    if ref:
        return carregar(ler_nota(cofre.exigir(ref, "spec", "Spec").caminho))
    proj = cofre.projeto(projeto) if projeto else resolver_projeto(cofre, cwd)
    s = spec_ativa(cofre, proj.nome if proj else None)
    if not s:
        raise ErroCofre("Nenhuma spec ativa neste projeto. Passe 'spec' com o ID (E-XXXXX) ou crie uma com "
                        "cofre_spec(acao='criar').")
    return s


def pendencias(s: Spec) -> list[str]:
    """O que impede a aprovação, em ordem de correção."""
    itens = []
    if not s.objetivo or s.objetivo == "(defina)":
        itens.append("Falta o objetivo.")
    if not s.requisitos:
        itens.append("Falta requisito. Ex.: 'QUANDO o usuário enviar e-mail inválido, O SISTEMA DEVE mostrar erro'.")
    if not s.tarefas:
        itens.append("Falta tarefa. Quebre o trabalho em tarefas pequenas, cada uma com o comando que prova que ficou pronta.")
    cobertos = {r for t in s.tarefas for r in t.cobre}
    for r, _ in s.requisitos:
        if r not in cobertos:
            itens.append(f"{r} não é coberto por nenhuma tarefa (use 'cobre: {r}' em alguma tarefa).")
    for t in s.tarefas:
        if not t.verificar:
            itens.append(f"{t.id} não tem verificação (um comando de teste, ou 'manual').")
    for p, _, texto in s.abertas():
        itens.append(f"Pergunta aberta {p}: {texto} — pergunte ao usuário e registre com acao='responder'.")
    return itens


def proximo_passo(s: Spec) -> str:
    if s.status == "concluida":
        return "Spec concluída. Faça cofre_checkpoint com o resumo."
    if s.status == "cancelada":
        return "Spec cancelada."
    if s.alterada_apos_aprovacao():
        return ("A spec mudou depois de aprovada. Mostre a versão nova ao usuário e peça aprovação de novo "
                "(cofre_spec acao='aprovar' com citacao_usuario).")
    if s.status == "rascunho":
        falta = pendencias(s)
        if falta:
            return "Antes de aprovar: " + " ".join(falta[:3])
        return ("Mostre a spec ao usuário (requisitos e tarefas) e peça aprovação. Com o 'ok' dele: "
                f"cofre_spec(acao='aprovar', spec='{s.id}', citacao_usuario='<palavras exatas dele>'). Não comece a codar antes.")
    atual = s.em_andamento()
    if atual:
        verif = f"`{atual.verificar}` passar" if atual.verificar != "manual" else "o usuário confirmar"
        return (f"Trabalhe SÓ em {atual.id}: {atual.descricao}. Pronto quando {verif}. "
                f"Depois: cofre_tarefa(acao='concluir', tarefa='{atual.id}').")
    if any(t.estado == "pendente" for t in s.tarefas):
        return "Chame cofre_tarefa(acao='proxima') para começar a próxima tarefa."
    bloqueadas = [t for t in s.tarefas if t.estado == "bloqueada"]
    if bloqueadas:
        t = bloqueadas[0]
        return f"{t.id} está BLOQUEADA ({t.motivo or 'sem motivo'}). Pare e peça ajuda ao usuário."
    return "Todas as tarefas resolvidas."


def resumo(s: Spec, completo: bool = True) -> str:
    feitas = sum(t.estado == "concluida" for t in s.tarefas)
    linhas = [f"{s.id} · {s.titulo} [{s.status}] · projeto {s.nota.projeto or '?'} · {feitas}/{len(s.tarefas)} tarefas"]
    if completo:
        linhas.append(f"Objetivo: {s.objetivo}")
        linhas += [f"- {r}: {t}" for r, t in s.requisitos]
        if s.fora_escopo:
            linhas.append("Fora de escopo: " + "; ".join(s.fora_escopo))
        linhas += [f"- [{'x' if ok else ' '}] {p}: {t}" for p, ok, t in s.perguntas]
        if s.plano and s.plano != "(a definir)":
            linhas.append(f"Plano: {s.plano[:600]}")
    atual = s.em_andamento()
    linhas += [t.render() + ("  <- AGORA" if t is atual else "") for t in s.tarefas]
    linhas.append(f"Próximo passo: {proximo_passo(s)}")
    return "\n".join(linhas)


def linha_agora(cofre: Cofre, projeto: str | None) -> str:
    """Uma a duas linhas para o contexto de cada chamada: em que spec/tarefa o projeto está."""
    s = spec_ativa(cofre, projeto)
    if not s:
        return ""
    feitas = sum(t.estado == "concluida" for t in s.tarefas)
    return f"AGORA · spec {s.id} \"{s.titulo}\" [{s.status}, {feitas}/{len(s.tarefas)} tarefas]: {proximo_passo(s)}"


# ---- escrita -----------------------------------------------------------------------
def _como_tarefa(item, ident: str, requisitos: list[tuple[str, str]]) -> Tarefa:
    if isinstance(item, dict):
        item = {chave_normal(k): v for k, v in item.items()}

        def primeiro(*nomes):
            return next((item[n] for n in nomes if item.get(n) not in (None, "", [])), "")

        desc = str(primeiro("descricao", "titulo", "tarefa", "description", "title", "task", "nome"))
        cobre = primeiro("cobre", "requisitos", "requisito", "covers", "requirements") or []
        verificar = str(primeiro("verificar", "verificacao", "comando", "verify", "verification", "command", "teste", "test"))
    else:
        partes = [p.strip() for p in re.split(r"\s+[|·]\s+", str(item))]
        desc, cobre, verificar = partes[0], [], ""
        for p in partes[1:]:
            chave, _, valor = p.partition(":")
            if chave.strip().lower() in ("cobre", "requisitos", "covers"):
                cobre = valor
            elif chave.strip().lower() in ("verificar", "verificacao", "verificação", "comando", "verify"):
                verificar = valor
    if isinstance(cobre, str):
        cobre = re.split(r"[,\s]+", cobre)
    cobre = [f"R{int(m.group())}" for c in cobre for m in [re.search(r"\d+", str(c))] if m]
    if not cobre and len(requisitos) == 1:
        cobre = [requisitos[0][0]]
    desc = " ".join(desc.replace(" · ", " - ").split())
    if len(desc) < 5:
        raise ErroCofre(f"Tarefa sem descrição: {item!r}. Ex.: {{'descricao': 'Validar e-mail no cadastro', "
                        "'cobre': ['R1'], 'verificar': 'npm test -- cadastro'}}")
    verificar = verificar.strip().strip("`").strip()
    if verificar.lower() in ("manual", "usuario", "usuário", "humano"):
        verificar = "manual"
    return Tarefa(ident, desc[:200], cobre=cobre, verificar=verificar)


def _proximo_num(itens: list[str], prefixo: str) -> int:
    nums = [int(i[1:]) for i in itens if i.startswith(prefixo) and i[1:].isdigit()]
    return max(nums, default=0) + 1


def _linhas(itens) -> list:
    """Itens em texto com várias linhas viram vários itens (modelos mandam a lista num texto só)."""
    saida = []
    for item in lista(itens):
        if isinstance(item, str) and "\n" in item.strip():
            saida += [x.strip(" -*\t") for x in item.split("\n") if x.strip(" -*\t")]
        else:
            saida.append(item)
    return saida


def _acrescentar(s: Spec, requisitos=(), tarefas=(), perguntas=(), fora_escopo=()) -> tuple[list[str], list[str]]:
    requisitos, tarefas, perguntas, fora_escopo = map(_linhas, (requisitos, tarefas, perguntas, fora_escopo))
    log, avisos = [], []
    for texto in lista(requisitos):
        texto = " ".join(str(texto).split())
        texto = re.sub(r"^R\d+\s*[:\-]\s*", "", texto)
        if not texto:
            continue
        r = f"R{_proximo_num([x for x, _ in s.requisitos], 'R')}"
        s.requisitos.append((r, texto))
        log.append(r)
        if not re.search(r"(?i)\b(deve|devem|must|shall|should)\b", texto):
            avisos.append(f"{r} não diz o que o sistema DEVE fazer. Prefira: 'QUANDO <situação>, O SISTEMA DEVE <comportamento>'.")
    for item in lista(tarefas):
        t = _como_tarefa(item, f"T{_proximo_num([t.id for t in s.tarefas], 'T')}", s.requisitos)
        s.tarefas.append(t)
        log.append(t.id)
    for texto in lista(perguntas):
        texto = re.sub(r"^P\d+\s*[:\-]\s*", "", " ".join(str(texto).split()))
        if texto:
            p = f"P{_proximo_num([x for x, _, _ in s.perguntas], 'P')}"
            s.perguntas.append((p, False, texto))
            log.append(p)
    s.fora_escopo += [" ".join(str(x).split()) for x in lista(fora_escopo) if str(x).strip()]
    return log, avisos


def criar(cofre: Cofre, autor: Autor, titulo: str, objetivo: str, requisitos=None, tarefas=None, perguntas=None,
          fora_escopo=None, plano: str = "", projeto: str | None = None, cwd: str | None = None) -> Resultado:
    titulo = " ".join(str(titulo or "").split())
    if len(titulo) < 5 or not str(objetivo or "").strip():
        raise ErroCofre("Spec precisa de 'titulo' (mín. 5 caracteres) e 'objetivo' (o problema e o resultado esperado).")
    proj = cofre.projeto(projeto) if projeto else resolver_projeto(cofre, cwd)
    if projeto and not proj:
        raise ErroCofre(f"Projeto '{projeto}' não existe no cofre. Projetos: {', '.join(sorted(cofre.projetos())) or '(nenhum)'}.")
    if not proj:
        raise ErroCofre("Spec precisa de projeto: rode dentro da pasta de um projeto do cofre ou passe 'projeto'.")
    ep.barrar_segredos(titulo, str(objetivo), str(plano or ""), *[str(x) for x in lista(requisitos) + lista(tarefas)])
    with cofre.trava():
        ident = cofre.novo_id("spec")
        meta = _limpar({
            "tipo": "spec", "id": ident, "titulo": titulo, "status": "rascunho", "projeto": f"[[{proj.nome}]]",
            "criada": hoje(), "atualizada": agora(), "registrado_por": autor.assinatura, "aliases": [ident],
        })
        caminho = cofre.pasta_para("spec", proj.nome) / f"{ident} {slug(titulo, 50)}.md"
        s = Spec(Nota(caminho, meta, ""), " ".join(str(objetivo).split()), [], [], [], str(plano or "").strip(), [], "")
        _, avisos = _acrescentar(s, requisitos, tarefas, perguntas, fora_escopo)
        _salvar(cofre, s, autor, "spec criada")
    _commit(cofre, [caminho], f"cofre: spec {ident} criada por {autor.assinatura}")
    return Resultado(f"Spec criada: {ident} — {titulo} [rascunho]\n{resumo(s)}", ident, caminho, avisos)


def atualizar(cofre: Cofre, autor: Autor, acao: str, ref=None, cwd: str | None = None, projeto: str | None = None,
              requisitos=None, tarefas=None, perguntas=None, fora_escopo=None, plano: str | None = None,
              pergunta: str | None = None, resposta: str = "", citacao_usuario: str = "", motivo: str = "") -> Resultado:
    acao = (acao or "").strip().lower()
    with cofre.trava():
        s = _resolver(cofre, ref, cwd, projeto)
        avisos: list[str] = []
        if acao == "ver":
            return Resultado(resumo(s), s.id, s.nota.caminho)
        if s.status in ("concluida", "cancelada") and acao != "ver":
            raise ErroCofre(f"Spec {s.id} está {s.status}; crie outra spec para trabalho novo.")
        if acao == "adicionar":
            ep.barrar_segredos(*[str(x) for x in lista(requisitos) + lista(tarefas) + lista(perguntas)], str(plano or ""))
            antes = s.hash()
            log, avisos = _acrescentar(s, requisitos, tarefas, perguntas, fora_escopo)
            if plano:
                s.plano = str(plano).strip()
                log.append("plano")
            if not log:
                raise ErroCofre("Nada para adicionar: passe requisitos, tarefas, perguntas, fora_escopo ou plano.")
            feito = "adicionado: " + ", ".join(log)
            if s.status in ("aprovada", "em_execucao") and s.hash() != antes:
                s.nota.meta["status"] = "rascunho"
                feito += " (spec volta para rascunho: precisa de nova aprovação)"
            _salvar(cofre, s, autor, feito)
        elif acao == "responder":
            alvo = re.search(r"\d+", str(pergunta or ""))
            idx = next((i for i, (p, _, _) in enumerate(s.perguntas) if alvo and p == f"P{int(alvo.group())}"), None)
            if idx is None:
                abertas = ", ".join(p for p, _, _ in s.abertas()) or "(nenhuma aberta)"
                raise ErroCofre(f"Pergunta '{pergunta}' não encontrada. Abertas: {abertas}.")
            if not str(resposta).strip():
                raise ErroCofre("Passe 'resposta' com o que o usuário respondeu.")
            ep.barrar_segredos(str(resposta))
            p, _, texto = s.perguntas[idx]
            texto = texto.split(" → resposta:")[0]
            s.perguntas[idx] = (p, True, f"{texto} → resposta: {' '.join(str(resposta).split())}")
            feito = f"{p} respondida"
            _salvar(cofre, s, autor, feito)
        elif acao == "aprovar":
            falta = pendencias(s)
            if falta:
                raise ErroCofre("Ainda não dá para aprovar:\n- " + "\n- ".join(falta))
            citacao = " ".join(str(citacao_usuario or "").split())
            if not autor.humano and len(citacao) < 2:
                raise ErroCofre("Só o usuário aprova uma spec. Mostre a spec, peça o 'ok' e passe as palavras exatas "
                                "dele em 'citacao_usuario'. Não invente aprovação.")
            liberados = lista(cofre.config().get("verificacao_comandos"))
            for t in s.tarefas:
                auto, explicacao = avaliar_comando(t.verificar, liberados)
                if not auto and t.verificar != "manual":
                    avisos.append(f"{t.id}: {explicacao}.")
            s.nota.meta.update({"status": "aprovada", "aprovada_em": agora(), "hash_aprovado": s.hash()})
            if citacao:
                s.nota.meta["citacao_usuario"] = citacao
            feito = "spec aprovada" + (f": \"{citacao}\"" if citacao else " pelo usuário")
            _salvar(cofre, s, autor, feito)
        elif acao == "cancelar":
            if not autor.humano and not str(citacao_usuario).strip():
                raise ErroCofre("Cancelar uma spec exige 'citacao_usuario' com o pedido do usuário.")
            s.nota.meta["status"] = "cancelada"
            feito = f"spec cancelada: {motivo or citacao_usuario}"
            _salvar(cofre, s, autor, feito)
        else:
            raise ErroCofre(f"acao inválida: '{acao}'. Use criar, ver, listar, adicionar, responder, aprovar ou cancelar.")
    _commit(cofre, [s.nota.caminho], f"cofre: spec {s.id} {acao} por {autor.assinatura}")
    return Resultado(f"Spec {s.id} [{s.status}]: {feito}.\nPróximo passo: {proximo_passo(s)}", s.id,
                     s.nota.caminho, avisos)


def listar(cofre: Cofre, projeto: str | None = None, cwd: str | None = None) -> str:
    proj = cofre.projeto(projeto) if projeto else resolver_projeto(cofre, cwd)
    specs = _specs(cofre, proj.nome if proj else None)
    if not specs:
        return "Nenhuma spec" + (f" no projeto {proj.nome}." if proj else ".")
    return "Specs:\n" + "\n".join(resumo(s, completo=False).split("\n")[0] for s in sorted(specs, key=_tempo, reverse=True))


# ---- tarefas -------------------------------------------------------------------------
def _exigir_execucao(s: Spec) -> None:
    if s.status == "rascunho":
        raise ErroCofre(f"Spec {s.id} ainda é rascunho: não comece a implementar. {proximo_passo(s)}")
    if s.status in ("concluida", "cancelada"):
        raise ErroCofre(f"Spec {s.id} está {s.status}.")
    if s.alterada_apos_aprovacao():
        raise ErroCofre(proximo_passo(s))


def _verificar(cofre: Cofre, s: Spec, t: Tarefa, cwd: str | None, autor: Autor, citacao: str,
               timeout: int | None = None) -> tuple[bool, str]:
    """(passou?, texto do resultado). Comando liberado: o cofre roda. Senão, exige confirmação do usuário."""
    cfg = cofre.config()
    auto, explicacao = avaliar_comando(t.verificar, lista(cfg.get("verificacao_comandos")))
    if not auto:
        if autor.humano or citacao:
            return True, "confirmado pelo usuário" + (f": \"{citacao}\"" if citacao else "")
        raise ErroCofre(f"{t.id} tem verificação manual ({explicacao}). Peça ao usuário para conferir e passe as "
                        "palavras dele em 'citacao_usuario'. Não diga que está pronto sem isso.")
    proj = cofre.projeto(s.nota.projeto or "")
    if not proj:
        raise ErroCofre(f"O projeto da spec ({s.nota.projeto}) não existe mais no cofre.")
    pasta = pasta_do_projeto(proj, cwd)
    codigo, saida, segundos = executar(t.verificar, pasta, timeout or int(cfg.get("verificacao_timeout", 300)))
    estado = "passou" if codigo == 0 else ("tempo esgotado" if codigo is None else f"falhou (código {codigo})")
    return codigo == 0, f"`{t.verificar}` em {pasta}: {estado} em {segundos:.1f}s\n{_cauda(saida, 1500)}"


def tarefa(cofre: Cofre, autor: Autor, acao: str, ref_spec=None, ref_tarefa=None, cwd: str | None = None,
           projeto: str | None = None, motivo: str = "", citacao_usuario: str = "") -> Resultado:
    acao = (acao or "").strip().lower()
    citacao = " ".join(str(citacao_usuario or "").split())
    with cofre.trava():
        s = _resolver(cofre, ref_spec, cwd, projeto)
        _exigir_execucao(s)
        atual = s.em_andamento()
        t = s.tarefa(ref_tarefa) if ref_tarefa else None
        if ref_tarefa and not t:
            raise ErroCofre(f"Tarefa '{ref_tarefa}' não existe em {s.id}. Tarefas: {', '.join(x.id for x in s.tarefas)}.")
        texto, sucesso_final = "", None
        if acao in ("proxima", "iniciar"):
            if atual and (t is None or t is atual):
                return Resultado(f"{atual.id} já está em andamento.\nPróximo passo: {proximo_passo(s)}", s.id, s.nota.caminho)
            if atual:
                raise ErroCofre(f"{atual.id} ainda está em andamento. Uma tarefa por vez: conclua ou bloqueie {atual.id} antes.")
            t = t or next((x for x in s.tarefas if x.estado == "pendente"), None)
            if not t:
                return Resultado(f"Não há tarefa pendente em {s.id}.\nPróximo passo: {proximo_passo(s)}", s.id, s.nota.caminho)
            if t.estado not in ("pendente", "bloqueada"):
                raise ErroCofre(f"{t.id} está {t.estado}; só tarefa pendente ou bloqueada pode ser iniciada.")
            t.marca, t.motivo = "/", ""
            s.nota.meta["status"] = "em_execucao"
            log = f"{t.id} iniciada"
        elif acao == "concluir":
            t = t or atual or next((x for x in s.tarefas if x.estado == "pendente"), None)
            if not t:
                raise ErroCofre(f"Nenhuma tarefa em andamento em {s.id}.")
            if atual and t is not atual:
                raise ErroCofre(f"{atual.id} é a tarefa em andamento; conclua ela antes de {t.id}.")
            if t.estado not in ("pendente", "em_andamento"):
                raise ErroCofre(f"{t.id} está {t.estado}.")
            passou, texto = _verificar(cofre, s, t, cwd, autor, citacao)
            s.nota.meta["status"] = "em_execucao"
            if passou:
                t.marca, t.falhas, t.motivo = "x", 0, ""
                log = f"{t.id} concluída — {texto.splitlines()[0]}"
                if all(x.estado in ("concluida", "cancelada") for x in s.tarefas):
                    sucesso_final, regressao = _regressao(cofre, s, cwd, autor, ja_rodado=t.verificar)
                    texto += "\n\n" + regressao
                    log += "; " + regressao.splitlines()[0]
            else:
                t.marca, t.falhas = "/", t.falhas + 1
                log = f"{t.id} verificação falhou ({t.falhas}/{MAX_FALHAS}) — {texto.splitlines()[0]}"
                if t.falhas >= MAX_FALHAS:
                    t.marca, t.motivo = "!", f"verificação falhou {t.falhas} vezes"
                    log += "; tarefa bloqueada"
        elif acao == "regressao":
            if any(x.estado not in ("concluida", "cancelada") for x in s.tarefas):
                raise ErroCofre(f"Ainda há tarefas abertas em {s.id}; a regressão roda quando todas estiverem concluídas.")
            sucesso_final, texto = _regressao(cofre, s, cwd, autor)
            log = texto.splitlines()[0]
        elif acao == "bloquear":
            t = t or atual
            if not t:
                raise ErroCofre("Diga qual tarefa bloquear ('tarefa') e o 'motivo'.")
            if not str(motivo).strip():
                raise ErroCofre("Passe 'motivo' (o que impede de continuar).")
            t.marca, t.motivo = "!", " ".join(str(motivo).split())[:200]
            log = f"{t.id} bloqueada: {t.motivo}"
        elif acao == "reabrir":
            if not t:
                raise ErroCofre("Diga qual tarefa reabrir ('tarefa').")
            if not autor.humano and not citacao:
                raise ErroCofre("Reabrir tarefa exige 'citacao_usuario' (o usuário pediu para refazer).")
            t.marca, t.falhas, t.motivo = " ", 0, ""
            log = f"{t.id} reaberta"
        else:
            raise ErroCofre(f"acao inválida: '{acao}'. Use proxima, iniciar, concluir, bloquear, reabrir ou regressao.")
        if sucesso_final:
            s.nota.meta["status"] = "concluida"
            s.nota.meta["concluida_em"] = agora()
        _salvar(cofre, s, autor, log + (f" (\"{citacao}\")" if citacao and acao in ("concluir", "reabrir") else ""))
    _commit(cofre, [s.nota.caminho], f"cofre: spec {s.id} {log[:60]} por {autor.assinatura}")
    cab = log
    if acao == "concluir" and t.estado == "concluida":
        cab = f"{t.id} concluída: a verificação passou."
    elif acao == "concluir" and t.estado == "em_andamento":
        cab = (f"{t.id} NÃO está pronta: a verificação falhou ({t.falhas}/{MAX_FALHAS}). Leia a saída, corrija e chame "
               "concluir de novo. Não diga ao usuário que está pronto.")
    elif acao == "concluir" and t.estado == "bloqueada":
        cab = (f"PARE: {t.id} falhou {t.falhas} vezes e foi BLOQUEADA. Mostre o erro ao usuário e peça orientação; "
               "não tente contornar a verificação.")
    return Resultado("\n".join(x for x in (cab, texto.strip(), f"Próximo passo: {proximo_passo(s)}") if x),
                     s.id, s.nota.caminho)


def _regressao(cofre: Cofre, s: Spec, cwd: str | None, autor: Autor, ja_rodado: str = "") -> tuple[bool, str]:
    """Roda de novo as verificações automáticas das tarefas anteriores; reabre a primeira que quebrou.

    Tempo total limitado a 2x verificacao_timeout, para caber no timeout de chamada dos clientes MCP."""
    cfg = cofre.config()
    liberados = lista(cfg.get("verificacao_comandos"))
    limite = int(cfg.get("verificacao_timeout", 300))
    prazo = time.monotonic() + 2 * limite
    vistos, quebradas, puladas, rodadas = {ja_rodado}, [], [], 0
    for t in s.tarefas:
        if t.estado != "concluida" or t.verificar in vistos or not avaliar_comando(t.verificar, liberados)[0]:
            continue
        vistos.add(t.verificar)
        restante = int(prazo - time.monotonic())
        if restante < 5:
            puladas.append(t.id)
            continue
        passou, texto = _verificar(cofre, s, t, cwd, autor, "", timeout=min(limite, restante))
        rodadas += 1
        if not passou:
            quebradas.append((t, texto))
    if not quebradas and puladas:
        return False, (f"Regressão incompleta: acabou o tempo antes de {', '.join(puladas)}. Spec continua em execução; "
                       "chame cofre_tarefa(acao='regressao') para terminar.")
    if not quebradas:
        return True, f"Regressão: {rodadas} verificação(ões) anteriores rodadas de novo, todas passaram. Spec concluída."
    t, texto = quebradas[0]
    t.marca, t.falhas = "/", 1
    nomes = ", ".join(x.id for x, _ in quebradas)
    return False, f"Regressão FALHOU em {nomes}: o trabalho novo quebrou algo que já passava. {t.id} reaberta.\n{texto}"
