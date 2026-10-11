"""Plugin do Cofre para o Hermes Agent.

- Seção de prompt de sistema (estável, sobrevive à compactação): contexto do projeto
  detectado pelo diretório da sessão.
- pre_llm_call (toda mensagem): procura no vault o que tem a ver com o que o usuário acabou
  de escrever (notas, fatos, decisões, fontes, skills) e anexa poucas linhas apontando para
  isso, sem repetir o que já foi mostrado na sessão. Com spec ativa, anexa a linha AGORA
  (spec, tarefa atual e próximo passo) em toda mensagem; sem spec, uma âncora com o foco
  atual a cada N turnos. Depois de N mensagens sem checkpoint, anexa um lembrete.
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
_vistos = {}


def _garantir_path():
    if COFRE_APP not in sys.path:
        sys.path.insert(0, COFRE_APP)


def _cofre():
    _garantir_path()
    from cofre.config import resolver_vault
    from cofre.vault import Cofre

    return Cofre(resolver_vault())


def _texto(cwd, modo, incluir_agora=True):
    try:
        _garantir_path()
        from cofre import contexto

        return contexto.montar(_cofre(), cwd=cwd, modo=modo, incluir_agora=incluir_agora)
    except Exception as e:
        log.warning("cofre: contexto indisponível: %s", e)
        return ""


def _texto_mensagem(mensagem):
    if isinstance(mensagem, str):
        return mensagem
    if isinstance(mensagem, list):
        return "\n".join(p.get("text", "") for p in mensagem if isinstance(p, dict) and p.get("type") == "text")
    return ""


def _relevante(session_id, texto):
    try:
        _garantir_path()
        from cofre import contexto, relevancia

        cofre = _cofre()
        proj = contexto.resolver_projeto(cofre, _cwd_sessao.get(session_id) or os.getcwd())
        vistos = _vistos.setdefault(session_id, set())
        bloco, ids = relevancia.relevante(cofre, texto, projeto=proj.nome if proj else None, excluir=vistos)
        vistos.update(ids)
        return bloco
    except Exception as e:
        log.warning("cofre: relevância indisponível: %s", e)
        return ""


def _ancora(cwd):
    return _texto(cwd, "ancora")


def _lembrete(historico):
    try:
        _garantir_path()
        from cofre import contexto

        return contexto.lembrete_checkpoint(_cofre(), contexto.mensagens_sem_checkpoint(historico or []))
    except Exception as e:
        log.warning("cofre: lembrete indisponível: %s", e)
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
        texto = _texto(cwd, "sistema", incluir_agora=False)
        if not texto:
            return ""
        return (texto + "\n" + LINHA_HERMES)[:4000]

    ctx.register_system_prompt_section("cofre.contexto", secao, position="after_memory", max_chars=4000)

    def por_mensagem(session_id=None, user_message="", is_first_turn=False, conversation_history=None, **kwargs):
        n = _turnos.get(session_id, 0) + 1
        _turnos[session_id] = n
        partes = []
        bloco = _relevante(session_id, _texto_mensagem(user_message))
        if bloco:
            partes.append(bloco)
        cwd = _cwd_sessao.get(session_id) or os.getcwd()
        ancora = _ancora(cwd)
        intervalo = _config("ancora_a_cada_turnos", 5)
        if ancora and ("AGORA ·" in ancora or (not is_first_turn and intervalo > 0 and n % intervalo == 0)):
            partes.append(ancora)
        lembrete = _lembrete(conversation_history)
        if lembrete:
            partes.append(lembrete)
        return {"context": "\n\n".join(partes)} if partes else None

    ctx.register_hook("pre_llm_call", por_mensagem)

    def marcar_checkpoint(tool_name="", task_id="", **kwargs):
        if "cofre_checkpoint" in str(tool_name):
            _checkpoints.add(task_id or kwargs.get("session_id") or "")

    ctx.register_hook("post_tool_call", marcar_checkpoint)

    def ao_finalizar(session_id=None, **kwargs):
        turnos = _turnos.pop(session_id, 0)
        _cwd_sessao.pop(session_id, None)
        _vistos.pop(session_id, None)
        teve = session_id in _checkpoints or "" in _checkpoints
        _checkpoints.discard(session_id)
        if turnos >= _config("lembrar_checkpoint_apos_turnos", 4) and not teve:
            return {"message": f"Cofre: esta sessão teve {turnos} turnos e nenhum checkpoint. "
                               "Na próxima, use /cofre-checkpoint antes de encerrar."}
        return None

    ctx.register_hook("on_session_finalize", ao_finalizar)
