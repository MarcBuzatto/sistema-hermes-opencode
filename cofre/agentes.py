"""Agentes guardados no vault (`65-Agentes/<nome>.md`) e levados ao OpenCode e ao Hermes.

Um agente é uma nota com frontmatter simples e o prompt no corpo:

    ---
    description: Revisa código procurando falhas de segurança. Use antes de publicar.
    mode: primary            # primary | subagent | all (OpenCode)
    model: opencode/x        # opcional
    ferramentas_desligadas: [write, edit]
    ---
    Você é um revisor...

- OpenCode: vira `<config>/agents/<nome>.md` no formato V1 (a V2 lê e migra). Trocar com Tab
  ou chamar com @nome.
- Hermes: vira `agent.personalities.<nome>` (description + system_prompt). `/personality nome`.

Só arquivos criados pelo cofre são atualizados ou apagados: um manifesto na config do usuário
guarda o que foi sincronizado em cada destino. Agente seu com o mesmo nome, criado à mão no
OpenCode ou no Hermes, é mantido.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from . import epistemica as ep
from . import frontmatter
from .config import dir_config_usuario
from .vault import PASTAS, slug

PASTA_AGENTES = PASTAS["agentes"]
MODOS = ("primary", "subagent", "all")
# Nomes que o OpenCode já usa ou que o cofre instala (agente/personality `spec`).
RESERVADOS = {"spec", "build", "plan", "general", "explore", "compaction", "title", "summary"}


@dataclass
class Agente:
    id: str
    arquivo: Path
    meta: dict
    prompt: str

    @property
    def descricao(self) -> str:
        return " ".join(str(self.meta.get("description") or "").split())

    @property
    def modo(self) -> str:
        modo = str(self.meta.get("mode") or "primary").strip().lower()
        return modo if modo in MODOS else "primary"

    @property
    def desligadas(self) -> list[str]:
        bruto = self.meta.get("ferramentas_desligadas") or []
        return [str(x).strip() for x in (bruto if isinstance(bruto, list) else [bruto]) if str(x).strip()]


def pasta(raiz_vault: Path) -> Path:
    return Path(raiz_vault) / PASTA_AGENTES


def listar(raiz_vault: Path) -> list[Agente]:
    base = pasta(raiz_vault)
    if not base.is_dir():
        return []
    saida = []
    for arquivo in sorted(base.rglob("*.md")):
        rel = arquivo.relative_to(base).parts
        if arquivo.name == "LEIA-ME.md" or any(p.startswith(".") for p in rel):
            continue
        try:
            meta, corpo = frontmatter.separar(arquivo.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
        if meta.get("exemplo"):
            continue
        saida.append(Agente(slug(arquivo.stem, 64), arquivo, meta, corpo.strip()))
    return saida


def verificar(raiz_vault: Path) -> list[tuple[str, str, str]]:
    achados, vistos = [], {}
    for ag in listar(raiz_vault):
        rot = f"agente:{ag.id}"
        if ag.id in vistos:
            achados.append(("erro", rot, f"nome repetido em {ag.arquivo.name} e {vistos[ag.id].name}: só um é levado"))
        vistos[ag.id] = ag.arquivo
        if ag.arquivo.stem != ag.id:
            achados.append(("alerta", rot, f"nome do arquivo vira '{ag.id}' nos agentes (use minúsculas e hífen)"))
        if not ag.descricao:
            achados.append(("erro", rot, "sem 'description': o OpenCode e o Hermes mostram isso para escolher o agente"))
        if not ag.prompt:
            achados.append(("erro", rot, "corpo vazio: o corpo da nota é o prompt do agente"))
        if str(ag.meta.get("mode") or "primary").strip().lower() not in MODOS:
            achados.append(("alerta", rot, f"mode '{ag.meta.get('mode')}' inválido (use {', '.join(MODOS)})"))
        if ag.id in RESERVADOS:
            achados.append(("alerta", rot, f"'{ag.id}' já é um agente do OpenCode ou do cofre; renomeie (não será levado)"))
        segredos = ep.achar_segredos(ag.prompt + " " + json.dumps(ag.meta, ensure_ascii=False, default=str))
        if segredos:
            achados.append(("erro", rot, f"possível credencial: {', '.join(segredos)}"))
    return achados


def _validos(raiz_vault: Path) -> list[Agente]:
    vistos, saida = set(), []
    for ag in listar(raiz_vault):
        if ag.descricao and ag.prompt and ag.id not in RESERVADOS and ag.id not in vistos:
            vistos.add(ag.id)
            saida.append(ag)
    return saida


def texto_opencode(ag: Agente) -> str:
    linhas = ["---", f"description: {frontmatter.formatar(ag.descricao)}", f"mode: {ag.modo}"]
    for chave in ("model", "color"):
        if ag.meta.get(chave):
            linhas.append(f"{chave}: {frontmatter.formatar(str(ag.meta[chave]))}")
    if ag.meta.get("temperature") not in (None, ""):
        linhas.append(f"temperature: {frontmatter.formatar(ag.meta['temperature'])}")
    if ag.desligadas:
        linhas.append("tools:")
        linhas += [f"  {frontmatter.formatar(nome)}: false" for nome in ag.desligadas]
    linhas.append("---")
    return "\n".join(linhas) + "\n" + ag.prompt + "\n"


def personality_hermes(ag: Agente) -> dict:
    return {"description": ag.descricao, "system_prompt": ag.prompt}


# ---- manifesto ---------------------------------------------------------------
def _arquivo_manifesto() -> Path:
    return dir_config_usuario() / "agentes-sincronizados.json"


def _manifesto() -> dict:
    try:
        return json.loads(_arquivo_manifesto().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _gravar_manifesto(dados: dict) -> None:
    arq = _arquivo_manifesto()
    arq.parent.mkdir(parents=True, exist_ok=True)
    arq.write_text(json.dumps(dados, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


# ---- OpenCode -------------------------------------------------------------------
def sincronizar_opencode(raiz_vault: Path, destino: Path, remover: bool = False) -> tuple[list[str], list[str], list[str]]:
    """Escreve os agentes em `destino/<nome>.md`. Retorna (escritos, removidos, avisos)."""
    destino = Path(destino)
    chave = f"opencode:{destino.resolve()}"
    manifesto = _manifesto()
    antes = set(manifesto.get(chave, []))
    atuais = {} if remover else {ag.id: ag for ag in _validos(raiz_vault)}
    if not atuais and not antes:
        return [], [], []
    escritos, removidos, avisos, nossos = [], [], [], set()
    for nome in sorted(antes - set(atuais)):
        alvo = destino / f"{nome}.md"
        if alvo.is_file():
            alvo.unlink()
            removidos.append(nome)
    for nome, ag in atuais.items():
        alvo = destino / f"{nome}.md"
        if alvo.exists() and nome not in antes:
            avisos.append(f"{alvo} já existe e não foi criado pelo cofre; mantive o seu.")
            continue
        texto = texto_opencode(ag)
        nossos.add(nome)
        if not alvo.is_file() or alvo.read_text(encoding="utf-8", errors="replace") != texto:
            destino.mkdir(parents=True, exist_ok=True)
            alvo.write_text(texto, encoding="utf-8")
            escritos.append(nome)
    if nossos:
        manifesto[chave] = sorted(nossos)
    else:
        manifesto.pop(chave, None)
    if manifesto != _manifesto() or escritos or removidos:
        _gravar_manifesto(manifesto)
    return escritos, removidos, avisos


# ---- Hermes ---------------------------------------------------------------------
def sincronizar_hermes(raiz_vault: Path, config_yaml: Path, python: Path | str,
                       remover: bool = False) -> tuple[list[str], list[str], list[str]]:
    """Leva os agentes para `agent.personalities` do config.yaml do Hermes."""
    from .hermes_config import aplicar

    config_yaml = Path(config_yaml)
    chave = f"hermes:{config_yaml.resolve()}"
    manifesto = _manifesto()
    antes = set(manifesto.get(chave, []))
    atuais = {} if remover else {ag.id: ag for ag in _validos(raiz_vault)}
    if not atuais and not antes:
        return [], [], []
    existentes = (aplicar(python, config_yaml, [["ler", "agent.personalities", None]]).get("agent.personalities")
                  if config_yaml.exists() else None)
    existentes = existentes if isinstance(existentes, dict) else {}
    ops, escritos, removidos, avisos, nossos = [], [], [], [], set()
    for nome in sorted(antes - set(atuais)):
        if nome in existentes:
            ops.append(["unset", f"agent.personalities.{nome}", None])
            removidos.append(nome)
    for nome, ag in atuais.items():
        if nome in existentes and nome not in antes:
            avisos.append(f"o Hermes já tem a personality '{nome}' (não é do cofre); mantive a sua.")
            continue
        valor = personality_hermes(ag)
        nossos.add(nome)
        if existentes.get(nome) != valor:
            ops.append(["set", f"agent.personalities.{nome}", valor])
            escritos.append(nome)
    if ops:
        aplicar(python, config_yaml, ops)
    if nossos:
        manifesto[chave] = sorted(nossos)
    else:
        manifesto.pop(chave, None)
    _gravar_manifesto(manifesto)
    return escritos, removidos, avisos


def resumo(raiz_vault: Path) -> str:
    agentes = listar(raiz_vault)
    if not agentes:
        return f"Nenhum agente em {pasta(raiz_vault)}."
    return "\n".join([f"Agentes em {pasta(raiz_vault)}:"] + [
        f"- {ag.id} [{ag.modo}] — {ag.descricao[:140] or '(sem description)'}" for ag in agentes])
