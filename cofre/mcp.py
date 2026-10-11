"""Servidor MCP (stdio) mínimo, sem dependências.

Implementa o handshake `initialize`, `tools/list`, `tools/call`, `ping` e consulta
`roots/list` ao cliente (quando suportado) para descobrir o workspace atual.
Mensagens são JSON-RPC 2.0 delimitadas por linha, conforme o transporte stdio do MCP.
"""

from __future__ import annotations

import json
import os
import sys
import traceback
from urllib.parse import unquote, urlparse

from . import __version__
from .config import ErroCofre, resolver_vault
from .ferramentas import POR_NOME, descricoes_mcp
from .registrar import Autor
from .vault import Cofre

VERSOES = ("2025-11-25", "2025-06-18", "2025-03-26", "2024-11-05")
INSTRUCOES = (
    "Cofre = memória compartilhada do usuário em Obsidian. (1) Chame cofre_contexto no início e após compactações. "
    "(2) Confiança: código/comando visto agora > usuário > VERIFICADO > HIPÓTESE > sua memória. "
    "(3) Nunca trate HIPÓTESE como fato nem repita afirmações REFUTADAS (Armadilhas). "
    "(4) Descobertas: cofre_registrar_fato (verificado só com evidência copiada exatamente, caminho absoluto). "
    "(5) Correções do usuário ou conflitos com o código: cofre_atualizar_fato. (6) Decisões: cofre_decisao. "
    "(7) cofre_checkpoint ao fim de cada etapa. (8) Assunto novo na conversa: cofre_buscar pelo tema (o vault tem notas, "
    "fontes e skills) e abra só o que servir com cofre_ler. (9) Nunca grave segredos. Procedimento completo: skill cofre-protocolo."
)


def _caminho_de_uri(uri: str) -> str | None:
    if not uri or not uri.startswith("file:"):
        return None
    p = urlparse(uri)
    caminho = unquote(p.path)
    if os.name == "nt" and len(caminho) > 2 and caminho[0] == "/" and caminho[2] == ":":
        caminho = caminho[1:]
    return caminho or None


class Servidor:
    def __init__(self, vault: str | None = None, saida=None, entrada=None):
        self.vault_arg = vault
        self.saida = saida or sys.stdout.buffer
        self.entrada = entrada or sys.stdin.buffer
        self.cliente = "agente"
        self.cliente_tem_roots = False
        self.raiz_workspace: str | None = None
        self._seq = 0

    # ---- E/S -------------------------------------------------------------
    def enviar(self, msg: dict) -> None:
        dados = json.dumps(msg, ensure_ascii=False, separators=(",", ":")).encode("utf-8") + b"\n"
        self.saida.write(dados)
        self.saida.flush()

    def responder(self, ident, resultado=None, erro=None) -> None:
        msg = {"jsonrpc": "2.0", "id": ident}
        if erro is not None:
            msg["error"] = erro
        else:
            msg["result"] = resultado if resultado is not None else {}
        self.enviar(msg)

    def pedir_roots(self) -> None:
        self._seq += 1
        self.enviar({"jsonrpc": "2.0", "id": f"cofre-roots-{self._seq}", "method": "roots/list"})

    # ---- tratamento --------------------------------------------------------
    def cwd(self) -> str:
        return os.environ.get("COFRE_CWD") or self.raiz_workspace or os.getcwd()

    def autor(self, args: dict) -> Autor:
        nome = os.environ.get("COFRE_AGENTE") or self.cliente or "agente"
        return Autor(nome=nome, humano=False, modelo=(args or {}).get("agente"))

    def chamar(self, nome: str, args: dict, meta: dict | None = None) -> dict:
        ferramenta = POR_NOME.get(nome)
        if not ferramenta:
            return {"content": [{"type": "text", "text": f"Ferramenta desconhecida: {nome}"}], "isError": True}
        try:
            cofre = Cofre(resolver_vault(self.vault_arg))
            args = dict(args or {})
            externa = (meta or {}).get("ai.opencode/sessionID")
            if externa:
                args["_sessao_externa"] = str(externa)
            texto = ferramenta["handler"](cofre, self.autor(args), args, self.cwd())
            return {"content": [{"type": "text", "text": texto}], "isError": False}
        except ErroCofre as e:
            return {"content": [{"type": "text", "text": str(e)}], "isError": True}
        except KeyError as e:
            return {"content": [{"type": "text", "text": f"Parâmetro obrigatório ausente: {e}"}], "isError": True}
        except Exception as e:
            traceback.print_exc(file=sys.stderr)
            return {"content": [{"type": "text", "text": f"Erro interno do cofre: {type(e).__name__}: {e}"}], "isError": True}

    def tratar(self, msg: dict) -> None:
        metodo = msg.get("method")
        ident = msg.get("id")
        if metodo is None:
            if isinstance(ident, str) and ident.startswith("cofre-roots-"):
                roots = (msg.get("result") or {}).get("roots") or []
                for r in roots:
                    caminho = _caminho_de_uri(r.get("uri", ""))
                    if caminho:
                        self.raiz_workspace = caminho
                        break
            return
        if metodo == "initialize":
            params = msg.get("params") or {}
            pedida = params.get("protocolVersion")
            info = params.get("clientInfo") or {}
            self.cliente = str(info.get("name") or "agente").lower()
            self.cliente_tem_roots = "roots" in (params.get("capabilities") or {})
            self.responder(ident, {
                "protocolVersion": pedida if pedida in VERSOES else VERSOES[1],
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": "cofre", "version": __version__},
                "instructions": INSTRUCOES,
            })
            return
        if metodo == "notifications/initialized":
            if self.cliente_tem_roots:
                self.pedir_roots()
            return
        if metodo == "notifications/roots/list_changed":
            self.pedir_roots()
            return
        if ident is None:
            return
        if metodo == "ping":
            self.responder(ident, {})
        elif metodo == "tools/list":
            self.responder(ident, {"tools": descricoes_mcp()})
        elif metodo == "tools/call":
            params = msg.get("params") or {}
            self.responder(ident, self.chamar(params.get("name", ""), params.get("arguments") or {}, params.get("_meta")))
        elif metodo in ("resources/list", "prompts/list", "resources/templates/list"):
            chave = {"resources/list": "resources", "prompts/list": "prompts"}.get(metodo, "resourceTemplates")
            self.responder(ident, {chave: []})
        else:
            self.responder(ident, erro={"code": -32601, "message": f"Método não suportado: {metodo}"})

    def rodar(self) -> int:
        for linha in iter(self.entrada.readline, b""):
            linha = linha.strip()
            if not linha:
                continue
            try:
                msg = json.loads(linha.decode("utf-8"))
            except (ValueError, UnicodeDecodeError):
                self.enviar({"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "JSON inválido"}})
                continue
            for item in msg if isinstance(msg, list) else [msg]:
                if isinstance(item, dict):
                    self.tratar(item)
        return 0


def main(vault: str | None = None) -> int:
    return Servidor(vault).rodar()
