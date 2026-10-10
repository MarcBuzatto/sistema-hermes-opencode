#!/usr/bin/env python3
"""Instalador do Cofre (Windows, Linux, macOS e WSL; só biblioteca padrão).

Instala o pacote, cria/completa o vault e liga o cofre SOMENTE nos agentes de
terminal (Hermes, OpenCode e, se pedido, Claude Code CLI e Codex CLI). Os apps de
chat (Claude Desktop, ChatGPT) não são tocados.

Nenhum arquivo de instruções é editado (AGENTS.md, SOUL.md, CLAUDE.md): o protocolo
chega aos modelos pelos plugins (prompt de sistema), pelas instruções do servidor MCP
e pela skill cofre-protocolo. Blocos deixados por versões antigas do instalador são
removidos.

Uso:
  python scripts/instalar.py --vault ~/Obsidian/Cofre --git
  python scripts/instalar.py --dry-run           (mostra o que faria)
  python scripts/instalar.py --desinstalar       (remove integrações; o vault fica)
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
WIN = os.name == "nt"
INICIO = "### >>> COFRE (bloco gerenciado pelo instalador do cofre; edite fora dele) >>>"
FIM = "### <<< COFRE <<<"
MARCA_COMANDO = "[cofre]"


def _home_dados() -> Path:
    if WIN:
        return Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
    return Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")


def _hermes_home() -> Path:
    if os.environ.get("HERMES_HOME"):
        return Path(os.environ["HERMES_HOME"])
    return _home_dados() / "hermes" if WIN else Path.home() / ".hermes"


class Instalador:
    def __init__(self, a: argparse.Namespace):
        self.a = a
        self.seco = a.dry_run
        self.pendencias: list[str] = []
        self.cofre_home = _home_dados() / "cofre"
        self.app = self.cofre_home / "app"
        self.python = Path(sys.executable)
        self.bin_dir = self.cofre_home / "bin" if WIN else Path.home() / ".local" / "bin"
        self.launcher = self.bin_dir / ("cofre.cmd" if WIN else "cofre")
        self.opencode_dir = Path(os.environ.get("OPENCODE_CONFIG_DIR") or Path.home() / ".config" / "opencode")
        self.hermes_home = _hermes_home()
        self.skills_legado = Path.home() / ".agents" / "skills"
        self.vault: Path | None = None

    # ---- utilidades ------------------------------------------------------
    def info(self, msg: str) -> None:
        print(("[simulação] " if self.seco else "[ok] ") + msg)

    def aviso(self, msg: str) -> None:
        print(f"[aviso] {msg}")

    def escrever(self, destino: Path, texto: str, executavel: bool = False) -> None:
        self.info(f"escrever {destino}")
        if self.seco:
            return
        destino.parent.mkdir(parents=True, exist_ok=True)
        with open(destino, "w", encoding="utf-8", newline="\r\n" if destino.suffix == ".cmd" else "\n") as f:
            f.write(texto)
        if executavel and not WIN:
            destino.chmod(0o755)

    def backup(self, arquivo: Path) -> None:
        copia = arquivo.with_name(arquivo.name + ".cofre-bak")
        if arquivo.exists() and not copia.exists() and not self.seco:
            shutil.copy2(arquivo, copia)

    def bloco(self, arquivo: Path, conteudo: str | None) -> None:
        """Insere/atualiza (ou remove, se conteudo=None) o bloco gerenciado no arquivo."""
        atual = arquivo.read_text(encoding="utf-8") if arquivo.exists() else ""
        padrao = re.compile(re.escape(INICIO) + r".*?" + re.escape(FIM) + r"\n?", re.S)
        sem_bloco = padrao.sub("", atual).rstrip("\n")
        if conteudo is None:
            if atual and atual != sem_bloco:
                self.escrever(arquivo, (sem_bloco + "\n") if sem_bloco else "")
            return
        novo_bloco = f"{INICIO}\n{conteudo.strip()}\n{FIM}\n"
        novo = (sem_bloco + "\n\n" + novo_bloco) if sem_bloco else novo_bloco
        if novo != atual:
            self.backup(arquivo)
            self.escrever(arquivo, novo)

    def rodar(self, cmd: list[str], descricao: str) -> subprocess.CompletedProcess | None:
        self.info(f"{descricao}: {' '.join(cmd)}")
        if self.seco:
            return None
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
        except (OSError, subprocess.SubprocessError) as e:
            self.pendencias.append(f"Falhou ({e}): {' '.join(cmd)}")
            return None
        if r.returncode != 0:
            self.pendencias.append(f"Falhou ({(r.stderr or r.stdout).strip()[:200]}): {' '.join(cmd)}")
        return r

    def limpar_blocos_legados(self) -> None:
        """Remove blocos que versões antigas do instalador puseram em arquivos de instrução."""
        codex = Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex")
        for arquivo in (self.opencode_dir / "AGENTS.md", self.hermes_home / "SOUL.md",
                        Path.home() / ".claude" / "CLAUDE.md", codex / "AGENTS.md"):
            if arquivo.exists() and INICIO in arquivo.read_text(encoding="utf-8", errors="replace"):
                self.bloco(arquivo, None)
        if self.skills_legado.is_dir():
            for pasta in self.skills_legado.glob("cofre-*"):
                self.info(f"remover {pasta} (local antigo das skills do cofre)")
                if not self.seco:
                    shutil.rmtree(pasta, ignore_errors=True)

    @property
    def pasta_skills(self) -> Path:
        return (self.vault or Path(".")) / "60-Skills"

    def cmd_cofre(self) -> str:
        caminhos = [p.rstrip("/\\") for p in os.environ.get("PATH", "").split(os.pathsep)]
        if str(self.bin_dir) in caminhos or (WIN and not self.a.sem_path):
            return "cofre"
        return f"'{self.launcher}'" if not WIN else f'"{self.launcher}"'

    def mcp_comando(self) -> list[str]:
        return [str(self.python), str(self.app), "mcp"]

    # ---- pacote e vault --------------------------------------------------
    def instalar_pacote(self) -> None:
        ignorar = shutil.ignore_patterns("__pycache__", "*.pyc")
        for origem, nome in ((RAIZ / "cofre", "cofre"), (RAIZ / "vault-template", "vault-template")):
            destino = self.app / nome
            self.info(f"copiar {origem} -> {destino}")
            if not self.seco:
                if destino.exists():
                    shutil.rmtree(destino)
                shutil.copytree(origem, destino, ignore=ignorar)
        self.escrever(self.app / "__main__.py", "from cofre.cli import main\n\nraise SystemExit(main())\n")
        if WIN:
            self.escrever(self.launcher, f'@echo off\n"{self.python}" "{self.app}" %*\n')
            if not self.a.sem_path:
                self._path_windows()
        else:
            self.escrever(self.launcher, f'#!/bin/sh\nexec "{self.python}" "{self.app}" "$@"\n', executavel=True)
            if str(self.bin_dir) not in os.environ.get("PATH", ""):
                self.pendencias.append(f"Adicione {self.bin_dir} ao PATH para usar o comando `cofre` no terminal.")

    def _path_windows(self) -> None:
        alvo = str(self.bin_dir)
        script = (
            "$p=[Environment]::GetEnvironmentVariable('Path','User'); if(-not $p){$p=''}; "
            f"if(-not (($p -split ';') -contains '{alvo}')){{"
            f"[Environment]::SetEnvironmentVariable('Path', ($p.TrimEnd(';') + ';{alvo}').TrimStart(';'), 'User')}}"
        )
        self.rodar(["powershell", "-NoProfile", "-Command", script], "adicionar ao PATH do usuário")
        self.pendencias.append("Abra um terminal novo (e reinicie OpenCode/Hermes) para o PATH valer.")

    def preparar_vault(self) -> None:
        sys.path.insert(0, str(RAIZ))
        from cofre.config import gravar_config_usuario, ler_config_usuario

        valor = self.a.vault or ler_config_usuario().get("vault")
        if not valor:
            raise SystemExit("Informe o caminho do vault: --vault ~/Obsidian/Cofre (pasta nova ou existente).")
        self.vault = Path(os.path.expanduser(valor)).resolve()
        self.info(f"vault: {self.vault}")
        if not self.seco:
            from cofre.cli import main as cofre_main

            cofre_main(["init", str(self.vault)])
            gravar_config_usuario({"vault": str(self.vault), "python": str(self.python), "app": str(self.app)})
        for pasta in sorted((RAIZ / "adapters" / "shared" / "skills").iterdir()):
            self.escrever(self.pasta_skills / "sistema" / pasta.name / "SKILL.md",
                          (pasta / "SKILL.md").read_text(encoding="utf-8"))
        if self.a.git and not (self.vault / ".git").exists():
            for cmd in (["git", "-C", str(self.vault), "init", "-q"],
                        ["git", "-C", str(self.vault), "add", "-A"],
                        ["git", "-C", str(self.vault), "-c", "user.name=cofre", "-c", "user.email=cofre@localhost",
                         "commit", "-qm", "cofre: vault inicial"]):
                self.rodar(cmd, "git")

    # ---- OpenCode --------------------------------------------------------
    def versao_opencode(self) -> int | None:
        exe = shutil.which("opencode")
        if not exe:
            return None
        try:
            saida = subprocess.run([exe, "--version"], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=20).stdout
        except (OSError, subprocess.SubprocessError):
            return None
        m = re.search(r"(\d+)\.(\d+)\.(\d+)", saida or "")
        return int(m.group(1)) if m else None

    def opencode(self, remover: bool = False) -> None:
        if not remover and not (shutil.which("opencode") or self.opencode_dir.exists() or self.a.opencode):
            self.aviso("OpenCode não encontrado; pulei (use --opencode para forçar).")
            return
        versao = self.versao_opencode()
        destino_sync = None if (versao and versao >= 2) else self.opencode_dir / "skills"
        for arq in sorted((RAIZ / "adapters" / "opencode" / "commands").glob("*.md")):
            destino = self.opencode_dir / "commands" / arq.name
            existente = destino.read_text(encoding="utf-8") if destino.exists() else ""
            if existente and MARCA_COMANDO not in existente:
                self.aviso(f"{destino} já existe e não é do cofre; mantive o seu.")
                continue
            if remover:
                if existente:
                    self.info(f"remover {destino}")
                    if not self.seco:
                        destino.unlink()
                continue
            self.escrever(destino, arq.read_text(encoding="utf-8").replace("{{COFRE}}", self.cmd_cofre()))
        plugin = self.opencode_dir / "plugins" / "cofre.js"
        if remover or self.a.sem_plugin_opencode:
            if plugin.exists():
                self.info(f"remover {plugin}")
                if not self.seco:
                    plugin.unlink()
        else:
            texto = (RAIZ / "adapters" / "opencode" / "plugins" / "cofre.js").read_text(encoding="utf-8")
            texto = texto.replace("{{PYTHON}}", json.dumps(str(self.python))[1:-1]).replace(
                "{{APP}}", json.dumps(str(self.app))[1:-1]).replace(
                "{{DESTINO_SKILLS}}", json.dumps(str(destino_sync)) if destino_sync else "null")
            self.escrever(plugin, texto)
        self._opencode_config(remover, versao)
        if destino_sync and self.vault:
            argumentos = ["skills", "sincronizar", "--destino", str(destino_sync)] + (["--remover"] if remover else [])
            self.rodar([str(self.python), str(self.app), *argumentos], "skills do vault -> OpenCode V1")

    def _opencode_config(self, remover: bool, versao: int | None) -> None:
        jsonc = self.opencode_dir / "opencode.jsonc"
        arq = self.opencode_dir / "opencode.json"
        if versao and versao >= 2:
            entrada = {"type": "local", "command": self.mcp_comando(),
                       "environment": {"COFRE_AGENTE": "opencode"}, "codemode": False}
        else:
            entrada = {"type": "local", "command": self.mcp_comando(),
                       "environment": {"COFRE_AGENTE": "opencode"}, "enabled": True}
        v2 = bool(versao and versao >= 2)
        pasta_skills = str(self.pasta_skills)
        if jsonc.exists() and not arq.exists():
            caminho_json = "mcp.servers.cofre" if v2 else "mcp.cofre"
            if not remover:
                extra = f'\ne em "skills": ["{pasta_skills}"]' if v2 else ""
                self.pendencias.append(
                    f"Edite {jsonc} e adicione em {caminho_json}:\n{json.dumps(entrada, indent=2, ensure_ascii=False)}{extra}")
            return
        try:
            cfg = json.loads(arq.read_text(encoding="utf-8")) if arq.exists() else {"$schema": "https://opencode.ai/config.json"}
        except ValueError:
            self.pendencias.append(f"{arq} não é JSON puro; adicione o servidor MCP 'cofre' à mão:\n"
                                   + json.dumps(entrada, indent=2, ensure_ascii=False))
            return
        mcp = cfg.setdefault("mcp", {})
        mudou = False
        for alvo in (mcp, mcp.get("servers") if isinstance(mcp.get("servers"), dict) else None):
            if alvo is not None and "cofre" in alvo:
                del alvo["cofre"]
                mudou = True
        if not remover:
            if versao and versao >= 2:
                mcp.setdefault("servers", {})["cofre"] = entrada
            else:
                mcp["cofre"] = entrada
            mudou = True
        if isinstance(mcp.get("servers"), dict) and not mcp["servers"]:
            del mcp["servers"]
        if not mcp:
            cfg.pop("mcp", None)
        if isinstance(cfg.get("skills"), list) or v2:
            atuais = [x for x in cfg.get("skills") or [] if x != pasta_skills]
            novos = atuais if (remover or not v2) else atuais + [pasta_skills]
            if novos != (cfg.get("skills") or []):
                mudou = True
            if novos:
                cfg["skills"] = novos
            else:
                cfg.pop("skills", None)
        if mudou:
            self.backup(arq)
            self.escrever(arq, json.dumps(cfg, indent=2, ensure_ascii=False) + "\n")
        if versao is None and not remover:
            self.aviso("Não consegui ler a versão do OpenCode; gravei o MCP no formato V1 (aceito também pela V2). "
                       "Na V2, para expor as ferramentas direto ao modelo, use mcp.servers.cofre com \"codemode\": false.")

    # ---- Hermes ----------------------------------------------------------
    def hermes(self, remover: bool = False) -> None:
        exe = shutil.which("hermes")
        if not remover and not (exe or self.hermes_home.exists() or self.a.hermes):
            self.aviso("Hermes não encontrado; pulei (use --hermes para forçar).")
            return
        destino_plugin = self.hermes_home / "plugins" / "cofre"
        if remover:
            if destino_plugin.exists():
                self.info(f"remover {destino_plugin}")
                if not self.seco:
                    shutil.rmtree(destino_plugin)
        else:
            origem = RAIZ / "adapters" / "hermes" / "plugin" / "cofre"
            self.escrever(destino_plugin / "plugin.yaml", (origem / "plugin.yaml").read_text(encoding="utf-8"))
            self.escrever(destino_plugin / "__init__.py",
                          (origem / "__init__.py").read_text(encoding="utf-8").replace("{{COFRE_APP}}", str(self.app)))
            if not self.a.manter_memoria_hermes:
                memoria = self.hermes_home / "memories" / "MEMORY.md"
                if memoria.exists():
                    self.backup(memoria)
                    self.rodar([str(self.python), str(self.app), "importar-memoria-hermes",
                                "--hermes-home", str(self.hermes_home)], "levar memória antiga do Hermes para a inbox")
        if exe:
            for cmd in self._comandos_hermes(remover):
                self.rodar([exe, *cmd], "hermes config")
        else:
            self.pendencias.append(self._instrucoes_hermes_manual(remover))

    def _instrucoes_hermes_manual(self, remover: bool) -> str:
        if remover:
            return ("Comando `hermes` não está no PATH. Depois rode `hermes config unset mcp_servers.cofre`, "
                    "`hermes config unset skills.create_dir` (se apontar para o vault) e remova 'cofre' de "
                    "plugins.enabled (mantendo os outros itens).")
        servidor = {"command": str(self.python), "args": [str(self.app), "mcp"],
                    "env": {"COFRE_AGENTE": "hermes"}, "timeout": 60}
        listas = ["'cofre' em plugins.enabled"]
        if not self.a.manter_skill_obsidian:
            listas.append("'obsidian' em skills.disabled")
        escalares = [f"hermes config set skills.create_dir {_citar(str(self.pasta_skills))}",
                     "hermes config set skills.write_approval true", "hermes config set memory.write_approval true"]
        if not self.a.manter_memoria_hermes:
            escalares.append("hermes config set memory.memory_enabled false")
        return (
            "Comando `hermes` não está no PATH. Depois rode:\n"
            f"hermes config set mcp_servers.cofre {_citar(json.dumps(servidor))}\n" + "\n".join(escalares) + "\n"
            "e acrescente (sem apagar o que já existe) " + ", ".join(listas) + ". "
            "Se a lista estiver vazia, ex.: hermes config set plugins.enabled '[\"cofre\"]'. "
            "Ou rode o instalador de novo depois que o `hermes` estiver no PATH."
        )

    def _valor_hermes(self, chave: str):
        exe = shutil.which("hermes")
        if not exe or self.seco:
            return None
        try:
            r = subprocess.run([exe, "config", "get", chave, "--json"], capture_output=True, text=True,
                               encoding="utf-8", errors="replace", timeout=30)
            valor = json.loads(r.stdout.strip() or "null") if r.returncode == 0 else None
        except (OSError, subprocess.SubprocessError, ValueError):
            valor = None
        if isinstance(valor, dict) and "value" in valor:
            valor = valor["value"]
        return valor

    def _lista_hermes(self, chave: str) -> list:
        valor = self._valor_hermes(chave)
        return list(valor) if isinstance(valor, list) else []

    def _comandos_hermes(self, remover: bool) -> list[list[str]]:
        def mesclar(chave: str, item: str) -> list[str]:
            atual = [x for x in self._lista_hermes(chave) if x != item]
            novo = atual if remover else atual + [item]
            return ["config", "set", chave, json.dumps(novo)]

        nossa = str(self.pasta_skills)
        atual = self._valor_hermes("skills.create_dir")
        atual = str(atual) if atual else ""
        if remover:
            cmds = [["config", "unset", "mcp_servers.cofre"], mesclar("plugins.enabled", "cofre")]
            if atual and self.vault and Path(os.path.expanduser(atual)) == self.pasta_skills:
                cmds.append(["config", "unset", "skills.create_dir"])
            elif nossa in self._lista_hermes("skills.external_dirs"):
                cmds.append(mesclar("skills.external_dirs", nossa))
            return cmds
        servidor = {"command": str(self.python), "args": [str(self.app), "mcp"],
                    "env": {"COFRE_AGENTE": "hermes"}, "timeout": 60}
        cmds = [
            ["config", "set", "mcp_servers.cofre", json.dumps(servidor)],
            mesclar("plugins.enabled", "cofre"),
            ["config", "set", "skills.write_approval", "true"],
            ["config", "set", "memory.write_approval", "true"],
        ]
        local = self.hermes_home / "skills"
        if not atual or Path(os.path.expanduser(atual)) in (self.pasta_skills, local):
            cmds.append(["config", "set", "skills.create_dir", nossa])
        else:
            self.aviso(f"skills.create_dir do Hermes já aponta para {atual}; mantive e adicionei o vault em external_dirs.")
            cmds.append(mesclar("skills.external_dirs", nossa))
        if not self.a.manter_skill_obsidian:
            cmds.append(mesclar("skills.disabled", "obsidian"))
        if not self.a.manter_memoria_hermes:
            cmds.append(["config", "set", "memory.memory_enabled", "false"])
        return cmds

    # ---- opcionais: Claude Code CLI e Codex CLI -----------------------------
    def claude_code(self, remover: bool = False) -> None:
        exe = shutil.which("claude")
        if remover:
            cmd = ["mcp", "remove", "-s", "user", "cofre"]
        else:
            cmd = ["mcp", "add", "-s", "user", "-e", "COFRE_AGENTE=claude-code", "cofre", "--", *self.mcp_comando()]
        if exe:
            self.rodar([exe, *cmd], "claude")
        else:
            self.pendencias.append("Claude Code não está no PATH. Rode: claude " + " ".join(_citar(c) for c in cmd))

    def codex(self, remover: bool = False) -> None:
        pasta = Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex")
        cfg = pasta / "config.toml"
        atual = cfg.read_text(encoding="utf-8") if cfg.exists() else ""
        padrao = re.compile(r"\n?# cofre:inicio\n.*?# cofre:fim\n", re.S)
        limpo = padrao.sub("", atual)
        if remover:
            if limpo != atual:
                self.escrever(cfg, limpo)
            return
        if "[mcp_servers.cofre]" in limpo:
            self.aviso(f"{cfg} já tem [mcp_servers.cofre] fora do bloco do instalador; mantive.")
            return
        bloco = (
            "\n# cofre:inicio\n[mcp_servers.cofre]\n"
            f"command = '{self.python}'\nargs = ['{self.app}', 'mcp']\n"
            "env = { COFRE_AGENTE = 'codex' }\n# cofre:fim\n"
        )
        self.backup(cfg)
        self.escrever(cfg, limpo.rstrip("\n") + "\n" + bloco if limpo.strip() else bloco.lstrip("\n"))

    # ---- fluxo -----------------------------------------------------------
    def instalar(self) -> None:
        self.instalar_pacote()
        self.preparar_vault()
        self.limpar_blocos_legados()
        if not self.a.sem_opencode:
            self.opencode()
        if not self.a.sem_hermes:
            self.hermes()
        if self.a.claude_code:
            self.claude_code()
        if self.a.codex:
            self.codex()
        self.resumo()

    def desinstalar(self) -> None:
        sys.path.insert(0, str(RAIZ))
        from cofre.config import ler_config_usuario

        vault = ler_config_usuario().get("vault")
        self.vault = Path(vault) if vault else None
        self.limpar_blocos_legados()
        self.opencode(remover=True)
        self.hermes(remover=True)
        if shutil.which("claude"):
            self.claude_code(remover=True)
        if (Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex") / "config.toml").exists():
            self.codex(remover=True)
        for alvo in (self.launcher, self.app):
            if alvo.exists():
                self.info(f"remover {alvo}")
                if not self.seco:
                    shutil.rmtree(alvo) if alvo.is_dir() else alvo.unlink()
        self.pendencias.append(
            "O vault não foi tocado. Se quiser reativar a memória nativa do Hermes: "
            "hermes config set memory.memory_enabled true && hermes config set memory.write_approval false")
        self.resumo()

    def resumo(self) -> None:
        print("")
        if not self.seco and not self.a.desinstalar:
            try:
                saida = subprocess.run([str(self.python), str(self.app), "doctor"], capture_output=True, text=True,
                                       encoding="utf-8", errors="replace", timeout=60).stdout
                print(saida)
            except (OSError, subprocess.SubprocessError):
                pass
        if self.pendencias:
            print("Pendências (faça à mão):")
            for p in self.pendencias:
                print(f"- {p}")
        else:
            print("Sem pendências.")


def _citar(s: str) -> str:
    if re.fullmatch(r"[\w@%+=:,./~-]+", s):
        return s
    return "'" + s.replace("'", "'\"'\"'") + "'"


def main() -> None:
    p = argparse.ArgumentParser(description="Instala o Cofre e liga Hermes/OpenCode a ele.")
    p.add_argument("--vault", help="Pasta do vault (nova ou existente)")
    p.add_argument("--git", action="store_true", help="Inicializa git no vault (recomendado: trilha de auditoria)")
    p.add_argument("--dry-run", action="store_true", help="Só mostra o que faria")
    p.add_argument("--desinstalar", action="store_true", help="Remove integrações (mantém o vault)")
    p.add_argument("--sem-opencode", action="store_true")
    p.add_argument("--sem-hermes", action="store_true")
    p.add_argument("--opencode", action="store_true", help="Força a integração mesmo sem detectar o OpenCode")
    p.add_argument("--hermes", action="store_true", help="Força a integração mesmo sem detectar o Hermes")
    p.add_argument("--sem-plugin-opencode", action="store_true", help="Não instala o plugin de injeção de contexto")
    p.add_argument("--claude-code", action="store_true", help="Também liga o Claude Code CLI (afeta a aba Code do app)")
    p.add_argument("--codex", action="store_true", help="Também liga o Codex CLI")
    p.add_argument("--manter-memoria-hermes", action="store_true", help="Não desliga o MEMORY.md do Hermes")
    p.add_argument("--manter-skill-obsidian", action="store_true", help="Não desativa a skill nativa 'obsidian' do Hermes")
    p.add_argument("--sem-path", action="store_true", help="Windows: não mexe no PATH do usuário")
    a = p.parse_args()
    for fluxo in (sys.stdout, sys.stderr):
        if hasattr(fluxo, "reconfigure"):
            try:
                fluxo.reconfigure(encoding="utf-8", errors="replace")
            except (OSError, ValueError):
                pass
    if sys.version_info < (3, 9):
        raise SystemExit("Requer Python 3.9 ou mais novo.")
    inst = Instalador(a)
    inst.desinstalar() if a.desinstalar else inst.instalar()


if __name__ == "__main__":
    main()
