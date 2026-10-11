"""AGENTS.md grande -> núcleo curto + instruções no vault, entregues por assunto.

Um AGENTS.md longo é lido inteiro em toda conversa e os modelos, principalmente os menores,
deixam de seguir boa parte dele. Aqui ele é dividido por seção (##): as seções curtas e
gerais ficam num núcleo proposto; as específicas (de uma linguagem, ferramenta, cliente)
viram notas `tipo: instrucao` em 30-Conhecimento/Instrucoes, que a busca por relevância
mostra à IA quando o assunto aparece na conversa.

O arquivo original nunca é alterado: o resultado é uma proposta em 00-Sistema/Relatorios
para o usuário revisar e aplicar se quiser.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

from . import epistemica as ep
from .config import ErroCofre
from .vault import PASTAS, Cofre, Nota, escrever_atomico, hoje, slug

PASTA_INSTRUCOES = f"{PASTAS['conhecimento']}/Instrucoes"
MAX_LINHAS_NUCLEO = 12
_GERAIS = re.compile(
    r"(?i)geral|gerais|regra|princ[ií]pio|estilo|comunica|idioma|l[ií]ngua|tom\b|resposta|seguran|git|commit|"
    r"sempre|nunca|importante|prefer|perfil|sobre mim|general|rules?\b|style|principles?|communication|language")


@dataclass
class Secao:
    titulo: str
    nivel: int
    texto: str

    @property
    def linhas(self) -> int:
        return len([x for x in self.texto.split("\n") if x.strip()])

    @property
    def nucleo(self) -> bool:
        if not self.titulo or _GERAIS.search(self.titulo):
            return True
        return self.linhas <= MAX_LINHAS_NUCLEO and "```" not in self.texto


def caminho_padrao() -> Path | None:
    candidatos = [Path(os.environ["OPENCODE_CONFIG_DIR"]) / "AGENTS.md"] if os.environ.get("OPENCODE_CONFIG_DIR") else []
    base = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    candidatos += [base / "opencode" / "AGENTS.md", Path.home() / ".config" / "opencode" / "AGENTS.md",
                   Path.cwd() / "AGENTS.md"]
    return next((c for c in candidatos if c.is_file()), None)


def dividir_secoes(texto: str) -> list[Secao]:
    texto = texto.replace("\r\n", "\n")
    linhas = texto.split("\n")
    em_codigo = False
    cabecalhos = []
    for i, linha in enumerate(linhas):
        if linha.strip().startswith("```"):
            em_codigo = not em_codigo
        m = None if em_codigo else re.match(r"^(#{1,6})\s+(.*\S)\s*$", linha)
        if m:
            cabecalhos.append((i, len(m.group(1)), m.group(2).strip("# ").strip()))
    niveis = sorted({n for _, n, _ in cabecalhos})
    corte = niveis[1] if len(niveis) > 1 and [n for _, n, _ in cabecalhos].count(niveis[0]) == 1 else (niveis[0] if niveis else 0)
    pontos = [(i, n, t) for i, n, t in cabecalhos if n <= corte]
    secoes = []
    inicio = 0
    titulo, nivel = "", 0
    for i, n, t in pontos + [(len(linhas), 0, "")]:
        corpo = "\n".join(linhas[inicio:i]).strip()
        if titulo:
            corpo = "\n".join(corpo.split("\n")[1:]).strip()
        if corpo or titulo:
            secoes.append(Secao(titulo, nivel, corpo))
        inicio, titulo, nivel = i, t, n
    return secoes


def _tokens(texto: str) -> int:
    return max(1, len(texto) // 4)


def analisar(caminho: Path) -> str:
    texto = Path(caminho).read_text(encoding="utf-8", errors="replace")
    secoes = dividir_secoes(texto)
    nucleo = [s for s in secoes if s.nucleo]
    fora = [s for s in secoes if not s.nucleo]
    tam_nucleo = sum(len(s.texto) + len(s.titulo) for s in nucleo)
    linhas = [
        f"{caminho}: {len(texto.splitlines())} linhas, ~{_tokens(texto)} tokens, {len(secoes)} seções.",
        f"Núcleo proposto (fica no AGENTS.md): {len(nucleo)} seções, ~{_tokens('x' * tam_nucleo)} tokens.",
        f"Para o vault (entregue só quando o assunto aparecer): {len(fora)} seções.",
        "",
    ]
    for s in secoes:
        destino = "núcleo" if s.nucleo else "vault "
        linhas.append(f"- [{destino}] {s.titulo or '(início do arquivo)'} — {s.linhas} linhas")
    linhas += ["", "Para gerar as notas e a proposta: cofre agents-md dividir --aplicar "
               "(use --manter \"Título\" para manter uma seção no núcleo). O arquivo original não é alterado."]
    return "\n".join(linhas)


def dividir(cofre: Cofre, caminho: Path, aplicar: bool = False, manter=()) -> str:
    caminho = Path(caminho)
    if not caminho.is_file():
        raise ErroCofre(f"Arquivo não encontrado: {caminho}")
    texto = caminho.read_text(encoding="utf-8", errors="replace")
    manter = {m.strip().lower() for m in manter or () if m.strip()}
    secoes = dividir_secoes(texto)
    pasta = cofre.raiz / PASTA_INSTRUCOES
    criadas, existentes, nucleo, ponteiros = [], [], [], []
    for s in secoes:
        if s.nucleo or s.titulo.lower() in manter:
            nucleo.append(s)
            continue
        if ep.achar_segredos(s.texto):
            raise ErroCofre(f"A seção '{s.titulo}' parece conter credencial; tire do AGENTS.md antes de dividir.")
        destino = pasta / f"{slug(s.titulo, 60)}.md"
        ponteiros.append(s.titulo)
        if destino.exists():
            existentes.append(cofre.relativo(destino))
            continue
        criadas.append(cofre.relativo(destino))
        if aplicar:
            nota = Nota(destino, {
                "tipo": "instrucao", "titulo": s.titulo, "origem": str(caminho), "importado_em": hoje(),
                "tags": ["instrucao"], "aliases": [s.titulo],
            }, f"# {s.titulo}\n\n{s.texto}\n")
            cofre.salvar(nota)
    partes = []
    for s in nucleo:
        partes.append(s.texto if not s.titulo else f"{'#' * (s.nivel or 2)} {s.titulo}\n\n{s.texto}".strip())
    if ponteiros:
        partes.append(
            "## Instruções por assunto\n\n"
            "Estas instruções ficam no cofre (Obsidian) e chegam à IA quando o assunto aparece na conversa "
            "(Hermes e OpenCode com o plugin do cofre). Para consultar: `cofre_buscar` pelo assunto.\n\n"
            + "\n".join(f"- {t}" for t in ponteiros))
    proposta = "\n\n".join(p for p in partes if p.strip()) + "\n"
    rel_proposta = f"{PASTAS['sistema']}/Relatorios/AGENTS-enxuto {hoje()}.md"
    if aplicar:
        escrever_atomico(cofre.raiz / rel_proposta, proposta)
        cofre.invalidar()
    antes, depois = _tokens(texto), _tokens(proposta)
    linhas = [
        f"AGENTS.md: ~{antes} tokens -> núcleo proposto: ~{depois} tokens ({len(nucleo)} seções no núcleo, "
        f"{len(ponteiros)} no vault).",
        ("Notas criadas" if aplicar else "Notas que seriam criadas") + f" em {PASTA_INSTRUCOES}: {len(criadas)}",
        *[f"- {c}" for c in criadas],
    ]
    if existentes:
        linhas += [f"Já existiam (mantidas): {len(existentes)}", *[f"- {e}" for e in existentes]]
    if aplicar:
        linhas += ["", f"Proposta de AGENTS.md enxuto: {rel_proposta}",
                   f"Revise no Obsidian e, se gostar, substitua o conteúdo de {caminho} por ela (o cofre não altera o original)."]
    else:
        linhas += ["", "Nada foi gravado. Rode com --aplicar para criar as notas e a proposta."]
    return "\n".join(linhas)
