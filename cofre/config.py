"""Resolução do vault e configuração (usuário e vault)."""

from __future__ import annotations

import json
import os
from pathlib import Path


class ErroCofre(Exception):
    """Erro de uso: a mensagem é mostrada ao agente/usuário como está."""


PADROES_VAULT = {
    # evidencia: agente pode marcar "verificado" com evidência conferível.
    # humano: só o usuário promove para "verificado"; agentes registram hipóteses.
    "politica_verificacao": "evidencia",
    "validade_padrao_dias": 90,
    "hipotese_antiga_dias": 14,
    "ancora_a_cada_turnos": 5,
    "git_autocommit": True,
    "contexto_max_chars": 6000,
    "contexto_sistema_max_chars": 3500,
    "fatos_verificados_no_contexto": 15,
    "lembrar_checkpoint_apos_turnos": 4,
    "relevancia_ativa": True,
    "relevancia_max_itens": 5,
    "relevancia_max_chars": 1600,
}


def dir_config_usuario() -> Path:
    if os.name == "nt":
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        return Path(base) / "cofre"
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "cofre"


def arquivo_config_usuario() -> Path:
    return dir_config_usuario() / "config.json"


def ler_config_usuario() -> dict:
    try:
        return json.loads(arquivo_config_usuario().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def gravar_config_usuario(dados: dict) -> Path:
    destino = arquivo_config_usuario()
    destino.parent.mkdir(parents=True, exist_ok=True)
    atual = ler_config_usuario()
    atual.update(dados)
    destino.write_text(json.dumps(atual, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return destino


def resolver_vault(explicito: str | None = None) -> Path:
    """Ordem: argumento > COFRE_VAULT > config do usuário."""
    for origem, valor in (
        ("argumento", explicito),
        ("COFRE_VAULT", os.environ.get("COFRE_VAULT")),
        (str(arquivo_config_usuario()), ler_config_usuario().get("vault")),
    ):
        if not valor:
            continue
        caminho = Path(os.path.expanduser(str(valor)))
        if caminho.is_dir():
            return caminho.resolve()
        raise ErroCofre(f"Vault do cofre não encontrado em {caminho} (definido por {origem}).")
    raise ErroCofre(
        "Vault do cofre não configurado. Rode scripts/instalar.py ou defina a variável COFRE_VAULT."
    )
