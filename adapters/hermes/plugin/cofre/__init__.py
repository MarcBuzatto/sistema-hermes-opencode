"""Plugin do Cofre para o Hermes Agent.

- Seção de prompt de sistema (estável, sobrevive à compactação): contexto do projeto
  detectado pelo diretório da sessão. Hermes sem register_system_prompt_section (até a
  0.19): o mesmo contexto vai no pre_llm_call do primeiro turno e de novo depois de uma
  compactação; o Hermes guarda esse texto junto da mensagem e o reenvia nos turnos seguintes.
- pre_llm_call (toda mensagem): procura no vault o que tem a ver com o que o usuário acabou
  de escrever (notas, fatos, decisões, fontes, skills) e anexa poucas linhas apontando para
  isso, sem repetir o que já foi mostrado na sessão. Com spec ativa, anexa a linha AGORA
  (spec, tarefa atual e próximo passo) em toda mensagem; sem spec, uma âncora com o foco
  atual a cada N turnos. Depois de N mensagens sem checkpoint, anexa um lembrete.
- post_tool_call + on_session_finalize: avisa ao fechar uma sessão longa sem checkpoint.
- pre_tool_call + transform_tool_result: bloqueia ferramentas que apontem para a pasta privada
  do vault (99-Privado e pastas_privadas) e tira as linhas com o caminho dela dos resultados.

Gerado pelo instalador do cofre; COFRE_APP aponta para a instalação do pacote.
"""

import logging
import os
import sys
import time

COFRE_APP = r"{{COFRE_APP}}"
log = logging.getLogger("cofre")
LINHA_HERMES = (
    "No Hermes: a ferramenta memory é só para preferências que o usuário confirmou; fatos de projeto, "
    "decisões e progresso vão para o cofre. Depois de uma compactação, chame cofre_contexto. "
    "Aqui as ferramentas do cofre têm o prefixo mcp__cofre__ (cofre_ler = mcp__cofre__cofre_ler)."
)

_turnos = {}
_checkpoints = set()
_cwd_sessao = {}
_vistos = {}
_guarda = [0.0, None]
_tam_historico = {}


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


def _relevante(session_id, texto, turno):
    """Janela deslizante: um ponteiro não repete nos próximos N turnos (economia), mas reaparece
    depois disso — cobre a troca de modelo na mesma conversa e a compactação, em que o modelo
    perde o que já tinha lido. O que precisa ser lembrado de verdade vira fato (prompt de sistema)."""
    try:
        _garantir_path()
        from cofre import contexto, relevancia

        cofre = _cofre()
        proj = contexto.resolver_projeto(cofre, _cwd_sessao.get(session_id) or os.getcwd())
        janela = _config("relevancia_repete_turnos", 6)
        vistos = _vistos.setdefault(session_id, {})
        recentes = {k for k, t in vistos.items() if turno - t < janela}
        bloco, ids = relevancia.relevante(cofre, texto, projeto=proj.nome if proj else None, excluir=recentes)
        for k in ids:
            vistos[k] = turno
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


def _guarda_privada():
    """Recalculada a cada 30 s (pastas_privadas pode mudar no config.md)."""
    agora = time.monotonic()
    if _guarda[1] is None or agora - _guarda[0] > 30:
        _garantir_path()
        from cofre.privado import Guarda

        _guarda[:] = [agora, Guarda.configurada()]
    return _guarda[1]


def _cwd_da_chamada(task_id, kwargs):
    return _cwd_sessao.get(kwargs.get("session_id") or task_id) or os.getcwd()


def register(ctx):
    def secao(info):
        cwd = info.get("cwd") or os.getcwd()
        if info.get("session_id"):
            _cwd_sessao[info["session_id"]] = cwd
        texto = _texto(cwd, "sistema", incluir_agora=False)
        if not texto:
            return ""
        return (texto + "\n" + LINHA_HERMES)[:4000]

    com_secao = hasattr(ctx, "register_system_prompt_section")
    if com_secao:
        ctx.register_system_prompt_section("cofre.contexto", secao, position="after_memory", max_chars=4000)

    def por_mensagem(session_id=None, user_message="", is_first_turn=False, conversation_history=None, **kwargs):
        n = _turnos.get(session_id, 0) + 1
        _turnos[session_id] = n
        partes = []
        if not com_secao:
            tamanho = len(conversation_history or [])
            compactou = tamanho < _tam_historico.get(session_id, 0)
            _tam_historico[session_id] = tamanho
            if n == 1 or is_first_turn or compactou:
                texto = secao({"session_id": session_id, "cwd": os.getcwd()})
                if texto:
                    partes.append(texto)
        bloco = _relevante(session_id, _texto_mensagem(user_message), n)
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

    # Exceção num pre_tool_call faz o Hermes bloquear a ferramenta: qualquer erro aqui deixa passar.
    def bloquear_privado(tool_name="", args=None, task_id="", **kwargs):
        try:
            if _guarda_privada().toca(args or {}, _cwd_da_chamada(task_id, kwargs)):
                from cofre.privado import MENSAGEM

                return {"action": "block", "message": MENSAGEM}
        except Exception as e:
            log.warning("cofre: guarda da pasta privada indisponível: %s", e)
        return None

    ctx.register_hook("pre_tool_call", bloquear_privado)

    def filtrar_privado(tool_name="", args=None, result="", task_id="", **kwargs):
        if not isinstance(result, str) or not result:
            return None
        try:
            novo = _guarda_privada().filtrar(result, _cwd_da_chamada(task_id, kwargs))
            return novo if novo != result else None
        except Exception as e:
            log.warning("cofre: filtro da pasta privada indisponível: %s", e)
            return None

    try:
        ctx.register_hook("transform_tool_result", filtrar_privado)
    except Exception as e:
        log.warning("cofre: este Hermes não tem transform_tool_result; só o bloqueio vale: %s", e)

    def ao_finalizar(session_id=None, **kwargs):
        _tam_historico.pop(session_id, None)
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
