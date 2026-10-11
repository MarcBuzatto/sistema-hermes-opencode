"""Modelo do vault: leitura/indexação das notas, IDs, escrita atômica e trava."""

from __future__ import annotations

import os
import re
import secrets
import time
import unicodedata
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Iterable, Iterator

from . import frontmatter
from .config import PADROES_VAULT, ErroCofre

PASTAS = {
    "sistema": "00-Sistema",
    "inbox": "01-Inbox",
    "sessoes_gerais": "02-Sessoes",
    "projetos": "10-Projetos",
    "missoes": "20-Missoes",
    "conhecimento": "30-Conhecimento",
    "clientes": "40-Clientes",
    "fontes": "50-Fontes",
    "skills": "60-Skills",
    "arquivo": "90-Arquivo",
}
DIR_EXPORTACOES = f"{PASTAS['arquivo']}/Exportacoes-NotebookLM"
DIRS_NAO_INDEXADOS = (DIR_EXPORTACOES, f"{PASTAS['sistema']}/Templates", PASTAS["skills"])
IGNORAR_DIRS = {".obsidian", ".git", ".trash", "node_modules", ".exportacoes"}

STATUS_FATO = ("hipotese", "verificado", "contestado", "refutado", "obsoleto")
STATUS_DECISAO = ("proposta", "aceita", "substituida", "rejeitada")
STATUS_MISSAO = ("ativa", "pausada", "concluida", "cancelada")
TIPOS = (
    "fato", "decisao", "sessao", "estado", "projeto", "missao",
    "captura", "cliente", "fonte", "perfil", "config",
)
PREFIXOS = {"fato": "F", "decisao": "D", "sessao": "S", "missao": "M", "captura": "C", "fonte": "N"}
_ALFABETO = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
_LINK = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|[^\]]*)?\]\]")


def hoje() -> str:
    return date.today().isoformat()


def agora() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def daqui(dias: int) -> str:
    return (date.today() + timedelta(days=int(dias))).isoformat()


def para_data(valor) -> date | None:
    if not valor:
        return None
    try:
        return date.fromisoformat(str(valor)[:10])
    except ValueError:
        return None


def slug(texto: str, max_len: int = 60) -> str:
    normal = unicodedata.normalize("NFKD", str(texto)).encode("ascii", "ignore").decode()
    normal = re.sub(r"[^a-zA-Z0-9]+", "-", normal).strip("-").lower()
    if len(normal) > max_len:
        corte = normal[:max_len]
        normal = corte.rsplit("-", 1)[0] if "-" in corte[max_len // 2:] else corte
    return normal.rstrip("-") or "nota"


def lista(valor) -> list:
    if valor is None or valor == "":
        return []
    if isinstance(valor, (list, tuple)):
        return [v for v in valor if v not in (None, "")]
    return [valor]


def alvo_link(valor) -> str | None:
    """'[[nome|alias]]' -> 'nome'; texto sem link é devolvido como está."""
    if not valor:
        return None
    m = _LINK.search(str(valor))
    return (m.group(1) if m else str(valor)).strip()


def link(nome: str) -> str:
    return f"[[{nome}]]"


@dataclass
class Nota:
    caminho: Path
    meta: dict
    corpo: str

    @property
    def tipo(self) -> str:
        return str(self.meta.get("tipo") or "")

    @property
    def id(self) -> str:
        return str(self.meta.get("id") or "")

    @property
    def nome(self) -> str:
        return self.caminho.stem

    @property
    def status(self) -> str:
        return str(self.meta.get("status") or "")

    @property
    def projeto(self) -> str | None:
        return alvo_link(self.meta.get("projeto"))

    def texto(self) -> str:
        return frontmatter.compor(self.meta, self.corpo)


def ler_nota(caminho: Path) -> Nota:
    meta, corpo = frontmatter.separar(caminho.read_text(encoding="utf-8", errors="replace"))
    return Nota(caminho, meta, corpo)


# Incrementado a cada escrita deste processo; caches em memória (índice de relevância) comparam.
GERACAO = [0]


def escrever_atomico(caminho: Path, texto: str) -> None:
    GERACAO[0] += 1
    caminho.parent.mkdir(parents=True, exist_ok=True)
    tmp = caminho.with_name(f".{caminho.name}.{os.getpid()}.tmp")
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(texto)
    for tentativa in range(5):
        try:
            os.replace(tmp, caminho)
            return
        except PermissionError:
            if tentativa == 4:
                raise
            time.sleep(0.2)


class Cofre:
    def __init__(self, raiz: Path):
        self.raiz = Path(raiz)
        if not self.raiz.is_dir():
            raise ErroCofre(f"Vault não encontrado: {self.raiz}")
        self._notas: list[Nota] | None = None
        self._config: dict | None = None

    # ---- leitura ---------------------------------------------------------
    def config(self) -> dict:
        if self._config is None:
            dados = dict(PADROES_VAULT)
            arq = self.raiz / PASTAS["sistema"] / "config.md"
            if arq.is_file():
                meta = ler_nota(arq).meta
                dados.update({k: v for k, v in meta.items() if k in PADROES_VAULT and v is not None})
            self._config = dados
        return self._config

    def _arquivos(self) -> Iterator[Path]:
        excluidos = {(self.raiz / d).resolve() for d in DIRS_NAO_INDEXADOS}
        for pasta, dirs, arquivos in os.walk(self.raiz):
            dirs[:] = [
                d for d in dirs
                if d not in IGNORAR_DIRS and not d.startswith(".")
                and (Path(pasta) / d).resolve() not in excluidos
            ]
            for nome in arquivos:
                if nome.endswith(".md") and not nome.startswith("."):
                    yield Path(pasta) / nome

    def notas(self, recarregar: bool = False) -> list[Nota]:
        if self._notas is None or recarregar:
            resultado = []
            for caminho in self._arquivos():
                try:
                    nota = ler_nota(caminho)
                except OSError:
                    continue
                if nota.tipo in TIPOS and not nota.meta.get("exemplo"):
                    resultado.append(nota)
            self._notas = resultado
        return self._notas

    def invalidar(self) -> None:
        self._notas = None

    def por_tipo(self, tipo: str) -> list[Nota]:
        return [n for n in self.notas() if n.tipo == tipo]

    def por_id(self, ident: str) -> Nota | None:
        from .normalizar import extrair_id

        alvo = extrair_id(ident) or str(ident).strip().strip("[]").upper().split(" ")[0]
        for nota in self.notas():
            if nota.id.upper() == alvo:
                return nota
        return None

    def sugestoes(self, ref, tipo: str | None = None, limite: int = 3) -> str:
        """Texto com IDs parecidos (erro de digitação) ou notas cujo texto casa com `ref`."""
        from .normalizar import extrair_id

        candidatos = [n for n in self.notas() if n.id and (tipo is None or n.tipo == tipo)]
        ident = extrair_id(ref)
        achados = []
        if ident:
            from .relevancia import _distancia_ate_1

            achados = [n for n in candidatos if _distancia_ate_1(n.id.upper(), ident)][:limite]
        if not achados and ref and len(str(ref).split()) >= 2:
            from .relevancia import buscar

            tipos = [tipo] if tipo else None
            ids = {a.doc.get("id") for a in buscar(self, str(ref), limite=limite, tipos=tipos, so_fortes=False)}
            achados = [n for n in candidatos if n.id in ids]
        if not achados:
            return ""
        def titulo(n: Nota) -> str:
            return str(n.meta.get("afirmacao") or n.meta.get("titulo") or n.nome)[:90]
        return " Talvez você quis dizer: " + "; ".join(f"{n.id} \"{titulo(n)}\"" for n in achados) + "."

    def por_nome(self, nome: str) -> Nota | None:
        for nota in self.notas():
            if nota.nome == nome:
                return nota
        return None

    def resolver_ref(self, ref) -> Nota | None:
        """Aceita ID ('F-7K3PQ'), link ('[[F-7K3PQ texto]]') ou nome de arquivo."""
        alvo = alvo_link(ref)
        if not alvo:
            return None
        return self.por_nome(alvo) or self.por_id(alvo)

    def exigir(self, ref, tipo: str, rotulo: str) -> Nota:
        nota = self.resolver_ref(ref)
        if nota and nota.tipo == tipo:
            return nota
        raise ErroCofre(
            f"{rotulo} '{ref}' não encontrado(a). Passe o ID exato (ex.: {PREFIXOS.get(tipo, 'X')}-7K3PQ)."
            + self.sugestoes(ref, tipo) + " Use cofre_buscar para achar o ID."
        )

    def projetos(self) -> dict[str, Nota]:
        return {n.nome: n for n in self.por_tipo("projeto")}

    def projeto(self, ref: str) -> Nota | None:
        if not ref:
            return None
        alvo = alvo_link(ref) or ""
        projetos = self.projetos()
        if alvo in projetos:
            return projetos[alvo]
        baixo = alvo.lower()
        for nome, nota in projetos.items():
            if nome.lower() == baixo or str(nota.meta.get("nome") or "").lower() == baixo:
                return nota
        return None

    def do_projeto(self, tipo: str, slug_projeto: str | None) -> list[Nota]:
        return [n for n in self.por_tipo(tipo) if n.projeto == slug_projeto]

    # ---- caminhos --------------------------------------------------------
    def pasta_projeto(self, slug_projeto: str) -> Path:
        return self.raiz / PASTAS["projetos"] / slug_projeto

    def pasta_para(self, tipo: str, slug_projeto: str | None) -> Path:
        sub = {"fato": "Fatos", "decisao": "Decisoes", "sessao": "Sessoes"}[tipo]
        if slug_projeto:
            return self.pasta_projeto(slug_projeto) / sub
        if tipo == "sessao":
            return self.raiz / PASTAS["sessoes_gerais"]
        return self.raiz / PASTAS["conhecimento"] / sub

    def arquivo_estado(self, slug_projeto: str) -> Path:
        return self.pasta_projeto(slug_projeto) / f"{slug_projeto} - Estado.md"

    def estado(self, slug_projeto: str) -> Nota | None:
        arq = self.arquivo_estado(slug_projeto)
        return ler_nota(arq) if arq.is_file() else None

    def perfil(self) -> Nota | None:
        arq = self.raiz / PASTAS["sistema"] / "Perfil.md"
        return ler_nota(arq) if arq.is_file() else None

    def relativo(self, caminho: Path) -> str:
        try:
            return caminho.relative_to(self.raiz).as_posix()
        except ValueError:
            return str(caminho)

    # ---- escrita ---------------------------------------------------------
    def novo_id(self, tipo: str) -> str:
        prefixo = PREFIXOS[tipo]
        existentes = {n.id.upper() for n in self.notas()}
        while True:
            candidato = f"{prefixo}-" + "".join(secrets.choice(_ALFABETO) for _ in range(5))
            if candidato not in existentes:
                return candidato

    def salvar(self, nota: Nota) -> None:
        escrever_atomico(nota.caminho, nota.texto())
        self.invalidar()

    @contextmanager
    def trava(self, timeout: float = 15.0) -> Iterator[None]:
        alvo = self.raiz / ".cofre.lock"
        inicio = time.time()
        while True:
            try:
                fd = os.open(alvo, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(fd, str(os.getpid()).encode())
                os.close(fd)
                break
            except FileExistsError:
                try:
                    if time.time() - alvo.stat().st_mtime > 30:
                        alvo.unlink()
                        continue
                except FileNotFoundError:
                    continue
                if time.time() - inicio > timeout:
                    raise ErroCofre("Cofre ocupado por outra escrita (.cofre.lock). Tente de novo.") from None
                time.sleep(0.1)
        try:
            yield
        finally:
            try:
                alvo.unlink()
            except FileNotFoundError:
                pass


# ---- corpo em seções -----------------------------------------------------
def secoes(corpo: str) -> list[tuple[str | None, str]]:
    """Divide o corpo em [(titulo_h2 | None, texto)]. Preserva a ordem."""
    resultado: list[tuple[str | None, list[str]]] = [(None, [])]
    for linha in corpo.split("\n"):
        if linha.startswith("## "):
            resultado.append((linha[3:].strip(), []))
        else:
            resultado[-1][1].append(linha)
    return [(t, "\n".join(ls).strip("\n")) for t, ls in resultado]


def juntar_secoes(partes: Iterable[tuple[str | None, str]]) -> str:
    blocos = []
    for titulo, texto in partes:
        if titulo is None:
            if texto.strip():
                blocos.append(texto.strip("\n"))
        else:
            blocos.append(f"## {titulo}\n" + (texto.strip("\n") + "\n" if texto.strip() else ""))
    return "\n\n".join(b.rstrip("\n") for b in blocos) + "\n"


def secao(corpo: str, titulo: str) -> str:
    for t, texto in secoes(corpo):
        if t == titulo:
            return texto
    return ""
