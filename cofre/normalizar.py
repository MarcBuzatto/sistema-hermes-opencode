"""Normalização tolerante dos argumentos que os modelos mandam para as ferramentas.

Modelos menores erram a forma da chamada com frequência: mandam JSON como string,
lista como texto, chaves com acento ou em inglês, enums com maiúscula ou no particípio
("Verificado", "refutado"), ID com o título junto. Em vez de falhar, o cofre ajusta o
que é inequívoco. As regras epistêmicas continuam rígidas; só a forma é flexível.
"""

from __future__ import annotations

import json
import re
import unicodedata

ALIASES_CHAVE = {
    "claim": "afirmacao", "statement": "afirmacao", "fato": "afirmacao", "fact": "afirmacao", "texto_fato": "afirmacao",
    "evidence": "evidencias", "evidences": "evidencias", "evidencia": "evidencias", "provas": "evidencias", "prova": "evidencias",
    "project": "projeto", "proj": "projeto", "action": "acao", "acoes": "acao", "operation": "acao", "operacao": "acao",
    "reason": "motivo", "why": "motivo", "justificativa": "motivo",
    "correct": "afirmacao_correta", "correcao": "afirmacao_correta", "correct_claim": "afirmacao_correta",
    "afirmacao_certa": "afirmacao_correta", "correto": "afirmacao_correta",
    "query": "consulta", "q": "consulta", "termo": "consulta", "termos": "consulta", "busca": "consulta", "search": "consulta",
    "summary": "resumo", "done": "feito", "feitos": "feito", "concluido": "feito",
    "next_steps": "proximos_passos", "proximos": "proximos_passos", "next": "proximos_passos", "passos_seguintes": "proximos_passos",
    "blockers": "bloqueios", "bloqueio": "bloqueios", "focus": "foco",
    "session_id": "sessao_id", "sessao": "sessao_id", "session": "sessao_id",
    "fact_id": "id", "id_fato": "id", "decision_id": "id", "spec_id": "spec", "id_spec": "spec",
    "task": "tarefa", "task_id": "tarefa", "id_tarefa": "tarefa",
    "tasks": "tarefas", "requirements": "requisitos", "requisito": "requisitos", "questions": "perguntas",
    "title": "titulo", "name": ("titulo", "nome", "slug"), "nome": ("titulo", "nome"), "nome_spec": "titulo", "objective": "objetivo", "goal": "objetivo",
    "decision": "decisao", "alternatives": "alternativas", "consequences": "consequencias",
    "user_quote": "citacao_usuario", "citacao": "citacao_usuario", "quote": "citacao_usuario",
    "text": "texto", "content": "conteudo", "section": "secao", "mode": "modo",
    "link": "url", "site": "url", "endereco": "url", "when_to_use": "quando_usar", "usar_quando": "quando_usar",
    "path": "caminho", "repository": "repo", "client": "cliente", "description": "descricao",
    "criticality": "criticidade", "force": "forcar", "limit": "limite", "type": "tipo", "model": "agente",
    "working_directory": "cwd", "workdir": "cwd", "diretorio": "cwd",
    "answer": "resposta", "question": "pergunta", "out_of_scope": "fora_escopo", "fora_de_escopo": "fora_escopo",
    "plan": "plano", "objetivo_spec": "objetivo", "verification": "verificar", "verify": "verificar",
}

ALIASES_VALOR = {
    "verified": "verificado", "verificada": "verificado", "confirmado": "verificado", "confirmada": "verificado",
    "hypothesis": "hipotese", "hipoteses": "hipotese", "suposicao": "hipotese", "nao_verificado": "hipotese",
    "refute": "refutar", "refutado": "refutar", "refutada": "refutar", "falso": "refutar", "reject_fact": "refutar",
    "promote": "promover", "promovido": "promover", "verificar": "promover", "verify": "promover", "confirmar": "promover",
    "contest": "contestar", "contestado": "contestar", "dispute": "contestar",
    "add_evidence": "adicionar_evidencia", "evidencia": "adicionar_evidencia", "anexar_evidencia": "adicionar_evidencia",
    "obsolete": "tornar_obsoleto", "obsoleto": "tornar_obsoleto", "obsoletar": "tornar_obsoleto",
    "register": "registrar", "create": "criar", "new": "criar", "novo": "criar", "nova": "criar",
    "list": "listar", "listagem": "listar", "update": "atualizar", "edit": "atualizar", "editar": "atualizar",
    "link": "vincular", "approve": "aprovar", "aprovado": "aprovar", "aprovada": "aprovar",
    "accept": "aceitar", "aceito": "aceitar", "aceita_decisao": "aceitar", "reject": "rejeitar",
    "start": "iniciar", "begin": "iniciar", "comecar": "iniciar", "finish": "concluir", "complete": "concluir",
    "done": "concluir", "concluida": "concluir", "concluido": "concluir", "terminar": "concluir", "feito": "concluir",
    "block": "bloquear", "bloqueado": "bloquear", "bloqueada": "bloquear", "next": "proxima", "proximo": "proxima",
    "read": "ler", "get": "ler", "cancel": "cancelar", "high": "alta", "normal_": "normal",
    "file": "arquivo", "command": "comando", "cmd": "comando", "user": "usuario", "note": "nota", "link_url": "url",
    "replace": "substituir", "append": "acrescentar", "adicionar": "acrescentar",
    "show": "ver", "view": "ver", "mostrar": "ver", "add": "adicionar", "incluir": "adicionar",
    "answer": "responder", "resposta": "responder", "reopen": "reabrir", "redo": "reabrir",
    "aprovacao": "aprovar", "proxima_tarefa": "proxima", "comecar_tarefa": "iniciar",
}
# Quando o apelido geral não serve para a ferramenta (ex.: "adicionar" é "acrescentar" no
# checkpoint mas "adicionar" no cofre_spec), tenta estes antes de desistir.
_SEGUNDA_OPCAO = {"ler": "ver", "acrescentar": "adicionar", "listar": "ver"}

_ID = re.compile(r"\b([FDSMCNE])-?([0-9A-HJKMNP-TV-Z]{5})\b", re.I)
_VERDADEIRO = {"true", "sim", "yes", "1", "verdadeiro", "s", "y"}
_LISTA_POR_VIRGULA = {"tags", "stack", "status", "projetos", "fatos", "decisoes"}


def chave(texto: str) -> str:
    s = unicodedata.normalize("NFKD", str(texto)).encode("ascii", "ignore").decode().strip().lower()
    return re.sub(r"[\s\-]+", "_", s)


def extrair_id(valor) -> str | None:
    """'f-7k3pq', 'F7K3PQ', '[[F-7K3PQ banco...]]', 'F-7K3PQ · texto' -> 'F-7K3PQ'."""
    if not valor:
        return None
    m = _ID.search(str(valor))
    return f"{m.group(1).upper()}-{m.group(2).upper()}" if m else None


def _como_lista(valor, itens_objeto: bool, virgula: bool = False) -> list:
    if valor is None or valor == "":
        return []
    if isinstance(valor, dict):
        return [valor]
    if isinstance(valor, (list, tuple)):
        return [v for v in valor if v not in (None, "")]
    s = str(valor).strip()
    if s.startswith(("[", "{")):
        try:
            convertido = json.loads(s)
            return _como_lista(convertido, itens_objeto, virgula)
        except ValueError:
            pass
    if itens_objeto:
        return [s]
    partes = [p.strip(" -*•\t") for p in re.split(r"\n+|;\s+" + (r"|,\s*" if virgula else ""), s)]
    return [p for p in partes if p]


def _valor_enum(valor, opcoes: list[str]):
    if valor is None:
        return None
    original = chave(valor)
    v = ALIASES_VALOR.get(original, original)
    for candidato in (v, original, _SEGUNDA_OPCAO.get(v)):
        if candidato in opcoes:
            return candidato
    candidatos = [o for o in opcoes if o.startswith(v) or v.startswith(o)]
    return candidatos[0] if len(candidatos) == 1 else valor


def normalizar(args, schema: dict) -> dict:
    if isinstance(args, str):
        try:
            args = json.loads(args) if args.strip() else {}
        except ValueError:
            args = {}
    if not isinstance(args, dict):
        return {}
    props = schema.get("properties", {})
    por_chave = {chave(p): p for p in props}
    saida: dict = {}
    for k, v in args.items():
        ck = chave(k)
        apelidos = ALIASES_CHAVE.get(ck, ())
        apelidos = (apelidos,) if isinstance(apelidos, str) else apelidos
        alvo = next((por_chave[c] for c in (ck, *map(chave, apelidos), ck.replace("_", "")) if c in por_chave), None)
        if alvo is None:
            if ck.startswith("_"):
                saida[k] = v
            continue
        if alvo not in saida or saida[alvo] in (None, "", []):
            saida[alvo] = v
    for nome, definicao in props.items():
        if nome not in saida:
            continue
        v = saida[nome]
        tipo = definicao.get("type")
        if tipo == "array":
            itens = definicao.get("items", {})
            v = _como_lista(v, itens.get("type") == "object", nome in _LISTA_POR_VIRGULA)
            if itens.get("enum"):
                v = [_valor_enum(x, itens["enum"]) for x in v]
        elif tipo == "string":
            if isinstance(v, (list, tuple)):
                v = v[0] if len(v) == 1 else "\n".join(str(x) for x in v)
            elif isinstance(v, dict):
                v = json.dumps(v, ensure_ascii=False)
            elif v is not None and not isinstance(v, str):
                v = str(v)
            if v is not None and definicao.get("enum"):
                v = _valor_enum(v, definicao["enum"])
        elif tipo == "boolean":
            v = v if isinstance(v, bool) else chave(v) in _VERDADEIRO
        elif tipo == "integer":
            try:
                v = int(str(v).strip())
            except (TypeError, ValueError):
                v = None
        saida[nome] = v
    return saida
