"""Skills guardadas no vault (`60-Skills/`), no formato padrão Agent Skills.

Cada skill é uma pasta com `SKILL.md` (frontmatter `name` e `description`) e, se
precisar, `references/`, `scripts/` e `assets/`. Pode haver uma pasta de categoria
no meio (`60-Skills/<categoria>/<skill>/SKILL.md`). O ID é o nome da pasta, que é o
que Hermes e OpenCode usam.

Hermes lê o vault direto (`skills.create_dir`), OpenCode V2 também (`skills` no
opencode.json). Para o OpenCode V1, que só enxerga `~/.config/opencode/skills/*/SKILL.md`
(um nível), `sincronizar` copia as skills achatadas, marcando as cópias para poder
atualizá-las e removê-las sem tocar nas skills que você criou lá à mão.
"""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass
from pathlib import Path

from . import epistemica as ep
from . import frontmatter

PASTA_SKILLS = "60-Skills"
MARCA_SYNC = ".cofre-sync"
ID_VALIDO = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
# Skills vindas de pesquisa: `status` diz se os passos foram testados e `fontes` aponta a origem.
STATUS_SKILL = ("rascunho", "verificada", "obsoleta")
_TEXTO = {".md", ".txt", ".py", ".sh", ".ps1", ".js", ".ts", ".json", ".yaml", ".yml", ".toml"}


@dataclass
class Skill:
    id: str
    pasta: Path
    meta: dict
    categoria: str | None

    @property
    def arquivo(self) -> Path:
        return self.pasta / "SKILL.md"

    @property
    def nome(self) -> str:
        return str(self.meta.get("name") or "")

    @property
    def descricao(self) -> str:
        return " ".join(str(self.meta.get("description") or "").split())


def lista_fontes(meta: dict) -> list[str]:
    bruto = meta.get("fontes") or meta.get("sources") or []
    return [str(x) for x in (bruto if isinstance(bruto, list) else [bruto]) if str(x).strip()]


def pasta_skills(raiz_vault: Path) -> Path:
    return Path(raiz_vault) / PASTA_SKILLS


def listar(raiz_vault: Path) -> list[Skill]:
    base = pasta_skills(raiz_vault)
    if not base.is_dir():
        return []
    resultado = []
    for arquivo in sorted(base.rglob("SKILL.md")):
        rel = arquivo.relative_to(base).parts
        if any(p.startswith(".") for p in rel) or len(rel) < 2:
            continue
        try:
            meta, _ = frontmatter.separar(arquivo.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
        categoria = rel[-3] if len(rel) >= 3 else None
        resultado.append(Skill(arquivo.parent.name, arquivo.parent, meta, categoria))
    return resultado


def verificar(raiz_vault: Path) -> list[tuple[str, str, str]]:
    """Lista de (gravidade, 'skill:<id>', mensagem)."""
    achados = []
    vistos: dict[str, Skill] = {}
    for s in listar(raiz_vault):
        rot = f"skill:{s.id}"
        if s.id in vistos:
            achados.append(("erro", rot, f"ID repetido em {s.pasta} e {vistos[s.id].pasta}: só uma será carregada"))
        vistos[s.id] = s
        if not ID_VALIDO.match(s.id) or len(s.id) > 64:
            achados.append(("alerta", rot, "nome da pasta fora do padrão (minúsculas, números e hífen, até 64)"))
        if not s.descricao:
            achados.append(("erro", rot, "sem 'description' no frontmatter: o modelo nunca vai saber quando usar"))
        elif len(s.descricao) > 1024:
            achados.append(("alerta", rot, "description com mais de 1024 caracteres"))
        status = str(s.meta.get("status") or "").strip().lower()
        if status in ("verificada", "verificado", "ativa") and not lista_fontes(s.meta):
            achados.append(("alerta", rot, f"status '{status}' sem 'fontes': liste as notas (N-..., F-...) ou links que comprovam a skill"))
        elif status and status not in STATUS_SKILL:
            achados.append(("alerta", rot, f"status '{status}' desconhecido (use {', '.join(STATUS_SKILL)})"))
        if not s.nome:
            achados.append(("alerta", rot, "sem 'name' no frontmatter"))
        elif s.nome != s.id:
            achados.append(("alerta", rot, f"name '{s.nome}' difere da pasta '{s.id}' (o ID usado é o da pasta)"))
        for arq in s.pasta.rglob("*"):
            if arq.is_file() and arq.suffix.lower() in _TEXTO:
                try:
                    segredos = ep.achar_segredos(arq.read_text(encoding="utf-8", errors="replace"))
                except OSError:
                    continue
                if segredos:
                    achados.append(("erro", rot, f"possível credencial em {arq.name}: {', '.join(segredos)}"))
    return achados


def sincronizar(raiz_vault: Path, destino: Path, remover: bool = False) -> tuple[list[str], list[str], list[str]]:
    """Copia as skills do vault para `destino/<id>/` (um nível). Retorna (copiadas, removidas, avisos)."""
    destino = Path(destino)
    copiadas, removidas, avisos = [], [], []
    atuais = {} if remover else {s.id: s for s in listar(raiz_vault)}
    if destino.is_dir():
        for pasta in destino.iterdir():
            if pasta.is_dir() and (pasta / MARCA_SYNC).exists() and pasta.name not in atuais:
                shutil.rmtree(pasta)
                removidas.append(pasta.name)
    for ident, skill in atuais.items():
        alvo = destino / ident
        if alvo.exists() and not (alvo / MARCA_SYNC).exists():
            avisos.append(f"{alvo} já existe e não foi criada pelo cofre; mantive a sua.")
            continue
        if alvo.exists():
            shutil.rmtree(alvo)
        shutil.copytree(skill.pasta, alvo, ignore=shutil.ignore_patterns(".*", "__pycache__"))
        (alvo / MARCA_SYNC).write_text(f"origem: {skill.pasta}\n", encoding="utf-8")
        copiadas.append(ident)
    return copiadas, removidas, avisos


def resumo(raiz_vault: Path) -> str:
    skills = listar(raiz_vault)
    if not skills:
        return f"Nenhuma skill em {pasta_skills(raiz_vault)}."
    linhas = [f"Skills em {pasta_skills(raiz_vault)}:"]
    for s in skills:
        cat = f"[{s.categoria}] " if s.categoria else ""
        linhas.append(f"- {s.id} {cat}— {s.descricao[:140] or '(sem description)'}")
    return "\n".join(linhas)
