import json
import os
import subprocess
import sys
import unittest

from base import RAIZ, CofreTeste


class TestMCP(CofreTeste):
    def conversar(self, mensagens, cwd="/"):
        entrada = "".join(json.dumps(m) + "\n" for m in mensagens)
        env = dict(os.environ, PYTHONPATH=str(RAIZ), COFRE_AGENTE="opencode")
        saida = subprocess.run([sys.executable, "-m", "cofre", "mcp"], input=entrada, capture_output=True,
                               text=True, cwd=cwd, env=env, timeout=60, encoding="utf-8")
        self.assertEqual(saida.returncode, 0, saida.stderr)
        return [json.loads(linha) for linha in saida.stdout.splitlines() if linha.strip()]

    def test_handshake_roots_e_ferramentas(self):
        respostas = self.conversar([
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
                "protocolVersion": "2025-06-18", "capabilities": {"roots": {}},
                "clientInfo": {"name": "opencode", "version": "2"}}},
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": "cofre-roots-1", "result": {"roots": [{"uri": self.proj.as_uri()}]}},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {
                "name": "cofre_registrar_fato", "arguments": {
                    "afirmacao": "O banco é PostgreSQL 16", "status": "verificado",
                    "evidencias": [{"tipo": "arquivo", "ref": "docker-compose.yml:3", "trecho": "image: postgres:16"}]}}},
            {"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {
                "name": "cofre_registrar_fato", "arguments": {
                    "afirmacao": "O banco é MySQL", "status": "verificado",
                    "evidencias": [{"tipo": "arquivo", "ref": "docker-compose.yml", "trecho": "mysql"}]}}},
            {"jsonrpc": "2.0", "id": 5, "method": "tools/call", "params": {
                "name": "cofre_checkpoint", "arguments": {"resumo": "Primeira etapa pronta"},
                "_meta": {"ai.opencode/sessionID": "ses_X"}}},
            {"jsonrpc": "2.0", "id": 6, "method": "tools/call", "params": {"name": "cofre_contexto", "arguments": {}}},
            {"jsonrpc": "2.0", "id": 7, "method": "metodo/inexistente"},
        ])
        por_id = {m.get("id"): m for m in respostas}
        self.assertIn(por_id[1]["result"]["protocolVersion"], ("2025-06-18",))
        self.assertTrue(any(m.get("method") == "roots/list" for m in respostas))
        nomes = [t["name"] for t in por_id[2]["result"]["tools"]]
        self.assertEqual(len(nomes), 12)
        self.assertFalse(por_id[3]["result"]["isError"], por_id[3])
        self.assertIn("projeto loja", por_id[3]["result"]["content"][0]["text"])
        self.assertTrue(por_id[4]["result"]["isError"])
        self.assertFalse(por_id[5]["result"]["isError"])
        self.assertIn("PostgreSQL 16", por_id[6]["result"]["content"][0]["text"])
        self.assertEqual(por_id[7]["error"]["code"], -32601)
        sessao = [n for n in type(self.cofre)(self.vault).por_tipo("sessao")][0]
        self.assertEqual(sessao.meta["sessao_externa"], "ses_X")
        self.assertEqual(sessao.meta["agente"], "opencode")


class TestInstalador(CofreTeste):
    def ambiente(self, home):
        env = {k: v for k, v in os.environ.items() if k not in ("COFRE_VAULT",)}
        env.update(HOME=str(home), USERPROFILE=str(home), XDG_CONFIG_HOME=str(home / ".config"),
                   XDG_DATA_HOME=str(home / ".local" / "share"), LOCALAPPDATA=str(home / "AppData" / "Local"),
                   APPDATA=str(home / "AppData" / "Roaming"), PATH=os.path.dirname(sys.executable),
                   OPENCODE_CONFIG_DIR=str(home / ".config" / "opencode"), HERMES_HOME=str(home / ".hermes"))
        return env

    def rodar(self, env, *args):
        r = subprocess.run([sys.executable, str(RAIZ / "scripts" / "instalar.py"), *args], capture_output=True,
                           text=True, env=env, timeout=120, encoding="utf-8", errors="replace")
        self.assertEqual(r.returncode, 0, (r.stderr or "") + (r.stdout or ""))
        return r.stdout

    def test_instala_sem_tocar_arquivos_de_instrucao(self):
        home = self.tmp / "home"
        oc = home / ".config" / "opencode"
        oc.mkdir(parents=True)
        (home / ".hermes").mkdir()
        agents = "# Minhas regras\n- usar pnpm\n"
        (oc / "AGENTS.md").write_text(agents, encoding="utf-8")
        (oc / "opencode.json").write_text('{"model": "opencode/x"}', encoding="utf-8")
        legado = "Seja direto.\n\n### >>> COFRE (bloco gerenciado pelo instalador do cofre; edite fora dele) >>>\nvelho\n### <<< COFRE <<<\n"
        (home / ".hermes" / "SOUL.md").write_text(legado, encoding="utf-8")
        (oc / "skills" / "minha-skill").mkdir(parents=True)
        (oc / "skills" / "minha-skill" / "SKILL.md").write_text("---\nname: minha-skill\n---\n", encoding="utf-8")
        env = self.ambiente(home)
        vault = home / "Cofre"
        self.rodar(env, "--vault", str(vault), "--sem-path")

        self.assertEqual((oc / "AGENTS.md").read_text(encoding="utf-8"), agents)
        self.assertEqual((home / ".hermes" / "SOUL.md").read_text(encoding="utf-8"), "Seja direto.\n")
        cfg = json.loads((oc / "opencode.json").read_text(encoding="utf-8"))
        self.assertEqual(cfg["model"], "opencode/x")
        self.assertIn("cofre", cfg["mcp"])
        self.assertTrue((home / ".hermes" / "plugins" / "cofre" / "__init__.py").exists())
        self.assertTrue((vault / "60-Skills" / "sistema" / "cofre-protocolo" / "SKILL.md").exists())
        self.assertFalse((home / ".agents").exists())
        self.assertFalse((home / ".claude").exists(), "Claude não deve ser tocado sem --claude-code")
        sincronizada = oc / "skills" / "cofre-protocolo"
        self.assertTrue((sincronizada / ".cofre-sync").exists(), "OpenCode sem versão detectada recebe cópia (V1)")
        plugin = (oc / "plugins" / "cofre.js").read_text(encoding="utf-8")
        self.assertNotIn("{{", plugin)
        self.assertIn("[cofre]", (oc / "agents" / "spec.md").read_text(encoding="utf-8"))
        self.assertIn("agent: spec", (oc / "commands" / "proxima.md").read_text(encoding="utf-8"))
        self.assertEqual(cfg["mcp"]["cofre"]["timeout"], 1200000, "V1: timeout longo para a verificação de tarefas")
        self.assertTrue((vault / "60-Skills" / "sistema" / "cofre-sdd" / "SKILL.md").exists())

        self.rodar(env, "--desinstalar")
        self.assertEqual((oc / "AGENTS.md").read_text(encoding="utf-8"), agents)
        cfg = json.loads((oc / "opencode.json").read_text(encoding="utf-8"))
        self.assertNotIn("mcp", cfg)
        self.assertFalse(sincronizada.exists())
        self.assertFalse((oc / "agents" / "spec.md").exists())
        self.assertTrue((oc / "skills" / "minha-skill" / "SKILL.md").exists(), "skill do usuário preservada")
        self.assertTrue((vault / "00-Sistema" / "Perfil.md").exists())

    @unittest.skipIf(os.name == "nt", "binário falso em shell script")
    def test_opencode_v2_aponta_skills_para_o_vault(self):
        home = self.tmp / "home"
        oc = home / ".config" / "opencode"
        oc.mkdir(parents=True)
        binarios = self.tmp / "bin"
        binarios.mkdir()
        falso = binarios / "opencode"
        falso.write_text("#!/bin/sh\necho 2.0.26\n", encoding="utf-8")
        falso.chmod(0o755)
        env = self.ambiente(home)
        env["PATH"] = str(binarios) + os.pathsep + env["PATH"]
        vault = home / "Cofre"
        self.rodar(env, "--vault", str(vault), "--sem-hermes", "--sem-path")
        cfg = json.loads((oc / "opencode.json").read_text(encoding="utf-8"))
        self.assertEqual(cfg["skills"], [str(vault.resolve() / "60-Skills")])
        self.assertFalse(cfg["mcp"]["servers"]["cofre"]["codemode"])
        self.assertNotIn("timeout", cfg["mcp"]["servers"]["cofre"], "V2 já tem 12 h de padrão; a chave V1 reduziria")
        self.assertFalse((oc / "skills").exists())
        self.rodar(env, "--desinstalar")
        cfg = json.loads((oc / "opencode.json").read_text(encoding="utf-8"))
        self.assertNotIn("skills", cfg)

    @unittest.skipIf(os.name == "nt", "binário falso em shell script")
    def test_hermes_recebe_timeout_e_personality_spec(self):
        home = self.tmp / "home"
        (home / ".hermes").mkdir(parents=True)
        binarios = self.tmp / "bin"
        binarios.mkdir()
        registro = self.tmp / "hermes.log"
        falso = binarios / "hermes"
        falso.write_text(f'#!/bin/sh\nprintf "%s\\n" "$*" >> "{registro}"\n'
                         'if [ "$2" = "get" ]; then echo null; fi\n', encoding="utf-8")
        falso.chmod(0o755)
        env = self.ambiente(home)
        env["PATH"] = str(binarios) + os.pathsep + env["PATH"]
        self.rodar(env, "--vault", str(home / "Cofre"), "--sem-opencode", "--sem-path")
        chamadas = registro.read_text(encoding="utf-8")
        self.assertIn('"timeout": 1200', chamadas)
        linha = next(x for x in chamadas.splitlines() if x.startswith("config set agent.personalities.spec "))
        valor = json.loads(linha.split(" ", 3)[3])
        self.assertIn("[cofre]", valor["description"])
        self.assertIn("MODO SPEC", valor["system_prompt"])


if __name__ == "__main__":
    unittest.main()
