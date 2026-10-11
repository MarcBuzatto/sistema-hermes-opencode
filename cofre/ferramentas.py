"""Definição das ferramentas expostas aos agentes (via MCP).

As descrições são curtas e imperativas de propósito: modelos menores seguem
melhor instruções diretas, e os erros devolvidos explicam como corrigir a chamada.
"""

from __future__ import annotations

from typing import Any, Callable

from . import contexto, registrar
from .registrar import Autor
from .vault import Cofre

_EVIDENCIAS = {
    "type": "array",
    "description": (
        "Provas conferíveis. arquivo: ref='caminho/absoluto.ext:linha', trecho=texto copiado EXATAMENTE do arquivo. "
        "comando: ref=comando executado, trecho=parte da saída. url: ref=link da doc oficial, trecho=citação. "
        "usuario: ref='conversa', trecho=palavras literais do usuário. nota: ref=ID de nota do cofre."
    ),
    "items": {
        "type": "object",
        "properties": {
            "tipo": {"type": "string", "enum": ["arquivo", "comando", "url", "usuario", "nota"]},
            "ref": {"type": "string"},
            "trecho": {"type": "string"},
        },
        "required": ["tipo", "ref", "trecho"],
    },
}
_LISTA = {"type": "array", "items": {"type": "string"}}
_PROJETO = {"type": "string", "description": "Slug do projeto no cofre. Omita para detectar pelo diretório; 'global' para fato sem projeto."}
_AGENTE = {"type": "string", "description": "Seu identificador de modelo, se souber (ex.: glm-4.6, claude-sonnet). Opcional."}
_CWD = {"type": "string", "description": "Caminho absoluto do projeto/workspace atual. Opcional, ajuda a detectar o projeto."}


def _objeto(props: dict, obrigatorios: list[str] | None = None) -> dict:
    return {"type": "object", "properties": props, "required": obrigatorios or []}


Handler = Callable[[Cofre, Autor, dict, str], str]


def _contexto(cofre: Cofre, autor: Autor, a: dict, cwd: str) -> str:
    return contexto.montar(cofre, cwd=a.get("cwd") or cwd, projeto=a.get("projeto"))


def _buscar(cofre: Cofre, autor: Autor, a: dict, cwd: str) -> str:
    return contexto.buscar(cofre, a["consulta"], projeto=a.get("projeto"), tipo=a.get("tipo"),
                           status=a.get("status"), limite=int(a.get("limite") or 10), cwd=cwd)


def _ler(cofre: Cofre, autor: Autor, a: dict, cwd: str) -> str:
    return contexto.ler(cofre, a["id"])


def _registrar_fato(cofre: Cofre, autor: Autor, a: dict, cwd: str) -> str:
    return registrar.registrar_fato(
        cofre, autor, a.get("afirmacao", ""), status=a.get("status", "hipotese"), evidencias=a.get("evidencias"),
        projeto=a.get("projeto"), contexto=a.get("contexto", ""), tags=a.get("tags"),
        criticidade=a.get("criticidade", "normal"), forcar=bool(a.get("forcar")), cwd=a.get("cwd") or cwd,
    ).texto()


def _atualizar_fato(cofre: Cofre, autor: Autor, a: dict, cwd: str) -> str:
    return registrar.atualizar_fato(
        cofre, autor, a.get("id", ""), a.get("acao", ""), evidencias=a.get("evidencias"),
        motivo=a.get("motivo", ""), afirmacao_correta=a.get("afirmacao_correta"), cwd=a.get("cwd") or cwd,
    ).texto()


def _decisao(cofre: Cofre, autor: Autor, a: dict, cwd: str) -> str:
    return registrar.decisao(
        cofre, autor, acao=a.get("acao", "registrar"), titulo=a.get("titulo", ""), decisao_txt=a.get("decisao", ""),
        contexto=a.get("contexto", ""), alternativas=a.get("alternativas"), consequencias=a.get("consequencias"),
        status=a.get("status", "proposta"), citacao_usuario=a.get("citacao_usuario", ""), projeto=a.get("projeto"),
        ident=a.get("id"), substitui=a.get("substitui"), motivo=a.get("motivo", ""), cwd=a.get("cwd") or cwd,
    ).texto()


def _checkpoint(cofre: Cofre, autor: Autor, a: dict, cwd: str) -> str:
    return registrar.checkpoint(
        cofre, autor, a.get("resumo", ""), feito=a.get("feito"), proximos_passos=a.get("proximos_passos"),
        bloqueios=a.get("bloqueios"), foco=a.get("foco"), projeto=a.get("projeto"), sessao_id=a.get("sessao_id"),
        fatos=a.get("fatos"), decisoes=a.get("decisoes"), cwd=a.get("cwd") or cwd,
        sessao_externa=a.get("_sessao_externa"),
    ).texto()


def _capturar(cofre: Cofre, autor: Autor, a: dict, cwd: str) -> str:
    return registrar.capturar(cofre, autor, a.get("texto", ""), titulo=a.get("titulo"), projeto=a.get("projeto"),
                              cwd=a.get("cwd") or cwd).texto()


def _projeto(cofre: Cofre, autor: Autor, a: dict, cwd: str) -> str:
    acao = (a.get("acao") or "listar").lower()
    if acao == "listar":
        return registrar.projeto_listar(cofre)
    if acao == "criar":
        caminho = a.get("caminho") or None
        return registrar.projeto_criar(
            cofre, autor, a.get("slug", ""), nome=a.get("nome"), caminhos=[caminho] if caminho else [],
            repos=[a["repo"]] if a.get("repo") else [], cliente=a.get("cliente"),
            descricao=a.get("descricao", ""), stack=a.get("stack"),
        ).texto()
    if acao == "vincular":
        return registrar.projeto_vincular(cofre, autor, a.get("slug", ""), caminho=a.get("caminho"),
                                          repo=a.get("repo")).texto()
    return "acao deve ser 'listar', 'criar' ou 'vincular'."


def _missao(cofre: Cofre, autor: Autor, a: dict, cwd: str) -> str:
    acao = (a.get("acao") or "listar").lower()
    if acao == "listar":
        return registrar.missao_listar(cofre, status=a.get("status") or "ativa", projeto=a.get("projeto"))
    if acao == "criar":
        return registrar.missao_criar(cofre, autor, a.get("titulo", ""), a.get("objetivo", ""),
                                      criterios=a.get("criterios"), passos=a.get("passos"),
                                      projetos=a.get("projetos")).texto()
    if acao == "atualizar":
        return registrar.missao_atualizar(cofre, autor, a.get("id", ""), concluir_passo=a.get("concluir_passo"),
                                          adicionar_passo=a.get("adicionar_passo"), status=a.get("status"),
                                          nota_log=a.get("nota")).texto()
    return "acao deve ser 'listar', 'criar' ou 'atualizar'."


FERRAMENTAS: list[dict[str, Any]] = [
    {
        "name": "cofre_contexto",
        "description": (
            "Contexto do cofre para o projeto atual: estado de trabalho, fatos VERIFICADOS, ARMADILHAS (afirmações "
            "refutadas), hipóteses, decisões e regras. Chame no início de toda tarefa e depois de qualquer resumo/compactação."
        ),
        "inputSchema": _objeto({"projeto": _PROJETO, "cwd": _CWD}),
        "annotations": {"readOnlyHint": True},
        "handler": _contexto,
    },
    {
        "name": "cofre_buscar",
        "description": "Busca no vault inteiro (notas livres, fatos, decisões, fontes, skills, sessões), tolerante a erro de digitação. Cada resultado vem com o status. Use antes de afirmar algo que não está no contexto.",
        "inputSchema": _objeto({
            "consulta": {"type": "string"},
            "projeto": _PROJETO,
            "tipo": {"type": "string", "enum": ["fato", "decisao", "sessao", "missao", "projeto", "captura", "fonte", "skill", "nota", "qualquer"]},
            "status": _LISTA,
            "limite": {"type": "integer", "description": "Máximo de resultados (padrão 10)."},
        }, ["consulta"]),
        "annotations": {"readOnlyHint": True},
        "handler": _buscar,
    },
    {
        "name": "cofre_ler",
        "description": "Lê uma nota completa do vault pelo ID (ex.: F-7K3PQ, D-..., N-...), slug de projeto ou caminho relativo ao vault (ex.: \"30-Conhecimento/Pentest/Burp.md\").",
        "inputSchema": _objeto({"id": {"type": "string"}}, ["id"]),
        "annotations": {"readOnlyHint": True},
        "handler": _ler,
    },
    {
        "name": "cofre_registrar_fato",
        "description": (
            "Registra UMA afirmação atômica sobre o projeto/ambiente. Sem evidência = 'hipotese'. 'verificado' só com "
            "evidência conferível (trecho copiado exatamente do arquivo/saída). Evidência de arquivo é conferida no disco; "
            "trecho inventado é rejeitado. Afirmações já refutadas são rejeitadas."
        ),
        "inputSchema": _objeto({
            "afirmacao": {"type": "string", "description": "Uma frase verificável, ex.: 'O banco de produção é PostgreSQL 16'."},
            "status": {"type": "string", "enum": ["hipotese", "verificado"]},
            "evidencias": _EVIDENCIAS,
            "projeto": _PROJETO,
            "contexto": {"type": "string", "description": "Como foi descoberto (curto)."},
            "tags": _LISTA,
            "criticidade": {"type": "string", "enum": ["normal", "alta"], "description": "'alta' = sempre aparece no contexto."},
            "forcar": {"type": "boolean", "description": "Só se o cofre apontou duplicata e você tem certeza de que é outro fato."},
            "cwd": _CWD,
            "agente": _AGENTE,
        }, ["afirmacao"]),
        "handler": _registrar_fato,
    },
    {
        "name": "cofre_atualizar_fato",
        "description": (
            "Muda o status de um fato. promover (hipótese->verificado, exige evidência); contestar (há conflito, exige motivo); "
            "refutar (é falso, exige motivo + evidência; passe afirmacao_correta para registrar a versão certa); "
            "tornar_obsoleto (mudou); adicionar_evidencia. Use quando o usuário corrigir algo ou o código contradisser o cofre."
        ),
        "inputSchema": _objeto({
            "id": {"type": "string"},
            "acao": {"type": "string", "enum": ["adicionar_evidencia", "promover", "contestar", "refutar", "tornar_obsoleto"]},
            "evidencias": _EVIDENCIAS,
            "motivo": {"type": "string"},
            "afirmacao_correta": {"type": "string", "description": "Ao refutar/tornar obsoleto: a afirmação correta."},
            "cwd": _CWD,
            "agente": _AGENTE,
        }, ["id", "acao"]),
        "handler": _atualizar_fato,
    },
    {
        "name": "cofre_decisao",
        "description": (
            "Registra decisão de projeto (arquitetura, biblioteca, padrão). Agente registra como 'proposta'; vira 'aceita' "
            "só com citacao_usuario (palavras literais do usuário aprovando). acao=aceitar/rejeitar muda uma existente."
        ),
        "inputSchema": _objeto({
            "acao": {"type": "string", "enum": ["registrar", "aceitar", "rejeitar"]},
            "titulo": {"type": "string"},
            "decisao": {"type": "string"},
            "contexto": {"type": "string"},
            "alternativas": _LISTA,
            "consequencias": _LISTA,
            "status": {"type": "string", "enum": ["proposta", "aceita"]},
            "citacao_usuario": {"type": "string"},
            "projeto": _PROJETO,
            "id": {"type": "string", "description": "Para aceitar/rejeitar."},
            "substitui": {"type": "string", "description": "ID da decisão que esta substitui."},
            "motivo": {"type": "string"},
            "cwd": _CWD,
            "agente": _AGENTE,
        }),
        "handler": _decisao,
    },
    {
        "name": "cofre_checkpoint",
        "description": (
            "Salva o progresso: atualiza o Estado do projeto (foco, próximos passos, bloqueios) e o diário da sessão. "
            "Chame ao concluir uma etapa, antes de encerrar e sempre que a conversa ficar longa. Reutilize o sessao_id devolvido."
        ),
        "inputSchema": _objeto({
            "resumo": {"type": "string"},
            "feito": _LISTA,
            "proximos_passos": _LISTA,
            "bloqueios": _LISTA,
            "foco": {"type": "string", "description": "Foco atual em uma frase."},
            "projeto": _PROJETO,
            "sessao_id": {"type": "string"},
            "fatos": {**_LISTA, "description": "IDs de fatos registrados nesta etapa."},
            "decisoes": {**_LISTA, "description": "IDs de decisões registradas nesta etapa."},
            "cwd": _CWD,
            "agente": _AGENTE,
        }, ["resumo"]),
        "handler": _checkpoint,
    },
    {
        "name": "cofre_capturar",
        "description": "Joga uma informação bruta na inbox do cofre para triagem depois (quando não souber classificar). Não é fato.",
        "inputSchema": _objeto({"texto": {"type": "string"}, "titulo": {"type": "string"}, "projeto": _PROJETO,
                                "cwd": _CWD, "agente": _AGENTE}, ["texto"]),
        "handler": _capturar,
    },
    {
        "name": "cofre_projeto",
        "description": "Lista, cria ou vincula projetos do cofre a pastas/repos. Crie ou vincule apenas quando o usuário pedir ou confirmar.",
        "inputSchema": _objeto({
            "acao": {"type": "string", "enum": ["listar", "criar", "vincular"]},
            "slug": {"type": "string"},
            "nome": {"type": "string"},
            "caminho": {"type": "string", "description": "Pasta local absoluta do projeto."},
            "repo": {"type": "string", "description": "URL do remoto git."},
            "cliente": {"type": "string"},
            "descricao": {"type": "string"},
            "stack": _LISTA,
        }, ["acao"]),
        "handler": _projeto,
    },
    {
        "name": "cofre_missao",
        "description": "Missões (objetivos com critérios de pronto e passos): listar, criar ou atualizar (concluir_passo pelo número ou texto, adicionar_passo, status, nota).",
        "inputSchema": _objeto({
            "acao": {"type": "string", "enum": ["listar", "criar", "atualizar"]},
            "id": {"type": "string"},
            "titulo": {"type": "string"},
            "objetivo": {"type": "string"},
            "criterios": _LISTA,
            "passos": _LISTA,
            "projetos": _LISTA,
            "concluir_passo": {"type": "string"},
            "adicionar_passo": {"type": "string"},
            "status": {"type": "string", "enum": ["ativa", "pausada", "concluida", "cancelada"]},
            "nota": {"type": "string"},
            "projeto": _PROJETO,
        }, ["acao"]),
        "handler": _missao,
    },
]

POR_NOME = {f["name"]: f for f in FERRAMENTAS}


def descricoes_mcp() -> list[dict]:
    return [{k: v for k, v in f.items() if k != "handler"} for f in FERRAMENTAS]
