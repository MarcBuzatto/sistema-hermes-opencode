"""Plugin do Cofre para o Hermes Agent.

- Seção de prompt de sistema (estável, sobrevive à compactação): contexto do projeto
  detectado pelo diretório da sessão.
- pre_llm_call: a cada N turnos reinjeta uma âncora curta com o foco atual (lido do disco,
  então reflete checkpoints feitos no meio da sessão).
- post_tool_call + on_session_finalize: avisa ao fechar uma sessão longa sem checkpoint.

Gerado pelo instalador do cofre; COFRE_APP aponta para a instalação do pacote.
"""

import logging
import os
import sys

COFRE_APP = r"{{COFRE_APP}}"
log = logging.getLogger("cofre")
LINHA_HERMES = (
    "No Hermes: a ferramenta memory é só para preferências que o usuário confirmou; fatos de projeto, "
    "decisões e progresso vão para o cofre. Depois de uma compactação, chame cofre_contexto."
)

_turnos = {}
_checkpoints = set()
_cwd_sessao = {}


def _garantir_path():
    if COFRE_APP not in sys.path:
        sys.path.insert(0, COFRE_APP)


def _cofre():
    _garantir_path()
    from cofre.config import resolver_vault
    from cofre.vault import Cofre

    return Cofre(resolver_vault())


def _texto(cwd, modo):
    try:
        _garantir_path()
        from cofre import contexto

        return contexto.montar(_cofre(), cwd=cwd, modo=modo)
    except Exception as e:
        log.warning("cofre: contexto indisponível: %s", e)
        return ""


def _config(chave, padrao):
    try:
        return int(_cofre().config().get(chave, padrao))
    except Exception:
        return padrao


def register(ctx):
    def secao(info):
        cwd = info.get("cwd") or os.getcwd()
        if info.get("session_id"):
            _cwd_sessao[info["session_id"]] = cwd
        texto = _texto(cwd, "sistema")
        if not texto:
            return ""
        return (texto + "\n" + LINHA_HERMES)[:4000]

    ctx.register_system_prompt_section("cofre.contexto", secao, position="after_memory", max_chars=4000)

    def ancora(session_id=None, is_first_turn=False, **kwargs):
        n = _turnos.get(session_id, 0) + 1
        _turnos[session_id] = n
        intervalo = _config("ancora_a_cada_turnos", 5)
        if is_first_turn or intervalo <= 0 or n % intervalo:
            return None
        texto = _texto(_cwd_sessao.get(session_id) or os.getcwd(), "ancora")
        return {"context": texto} if texto else None

    ctx.register_hook("pre_llm_call", ancora)

    def marcar_checkpoint(tool_name="", task_id="", **kwargs):
        if "cofre_checkpoint" in str(tool_name):
            _checkpoints.add(task_id or kwargs.get("session_id") or "")

    ctx.register_hook("post_tool_call", marcar_checkpoint)

    def ao_finalizar(session_id=None, **kwargs):
        turnos = _turnos.pop(session_id, 0)
        _cwd_sessao.pop(session_id, None)
        teve = session_id in _checkpoints or "" in _checkpoints
        _checkpoints.discard(session_id)
        if turnos >= _config("lembrar_checkpoint_apos_turnos", 4) and not teve:
            return {"message": f"Cofre: esta sessão teve {turnos} turnos e nenhum checkpoint. "
                               "Na próxima, use /cofre-checkpoint antes de encerrar."}
        return None

    ctx.register_hook("on_session_finalize", ao_finalizar)
