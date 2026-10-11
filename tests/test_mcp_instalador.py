import importlib.util
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
        self.assertEqual(len(nomes), 13)
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
        privada = str(vault.resolve() / "99-Privado")
        regras = {(r["action"], r["resource"]) for r in cfg["permissions"] if r["effect"] == "deny"}
        for acao in ("read", "edit", "external_directory"):
            self.assertIn((acao, privada), regras)
            self.assertIn((acao, privada + "/*"), regras)
        for acao in ("read", "edit"):
            self.assertIn((acao, "99-Privado/*"), regras, "sessão aberta dentro do vault: a V2 confere o caminho relativo")
        self.assertNotIn(("external_directory", "99-Privado/*"), regras)
        self.assertNotIn("permission", cfg, "a V2 usa a lista 'permissions'")

        # Regras do usuário ficam; as do cofre são refeitas no fim (a última que casa vence na V2).
        cfg["permissions"].insert(0, {"action": "shell", "resource": "rm *", "effect": "deny"})
        cfg["permissions"].append({"action": "read", "resource": "*", "effect": "allow"})
        (oc / "opencode.json").write_text(json.dumps(cfg), encoding="utf-8")
        cofre_cfg = vault / "00-Sistema" / "config.md"
        cofre_cfg.write_text(cofre_cfg.read_text(encoding="utf-8").replace(
            "pastas_privadas: []", "pastas_privadas:\n  - 40-Clientes/Confidencial"), encoding="utf-8")
        self.rodar(env, "--vault", str(vault), "--sem-hermes", "--sem-path")
        cfg = json.loads((oc / "opencode.json").read_text(encoding="utf-8"))
        acoes = [(r["action"], r["resource"], r["effect"]) for r in cfg["permissions"]]
        self.assertEqual(acoes[0], ("shell", "rm *", "deny"))
        self.assertIn(("read", "*", "allow"), acoes)
        ultimo_do_usuario = acoes.index(("read", "*", "allow"))
        nossas = [i for i, a in enumerate(acoes) if a[2] == "deny" and a[1] != "rm *"]
        self.assertTrue(nossas and min(nossas) > ultimo_do_usuario, acoes)
        absolutas = [a for a in acoes if a[2] == "deny" and a[1].startswith(str(vault.resolve()))]
        self.assertEqual(len(absolutas), 12, "sem duplicar regras ao reinstalar; 2 pastas x 3 ações x 2 padrões")
        self.assertIn(("read", str(vault.resolve() / "40-Clientes" / "Confidencial" / "*"), "deny"), acoes)

        self.rodar(env, "--desinstalar")
        cfg = json.loads((oc / "opencode.json").read_text(encoding="utf-8"))
        self.assertNotIn("skills", cfg)
        self.assertEqual([(r["action"], r["resource"]) for r in cfg["permissions"]],
                         [("shell", "rm *"), ("read", "*")], "desinstalar tira só as regras do cofre")

    @unittest.skipIf(os.name == "nt", "binário falso em shell script")
    def hermes_falso(self, com_yaml=True):
        """`hermes` cujo interpretador (shebang) é este Python: o instalador edita o config.yaml com ele."""
        binarios = self.tmp / "bin"
        binarios.mkdir(exist_ok=True)
        falso = binarios / "hermes"
        interpretador = sys.executable if com_yaml else "/bin/sh"
        falso.write_text(f"#!{interpretador}\nimport sys\n", encoding="utf-8")
        falso.chmod(0o755)
        return binarios

    @unittest.skipIf(os.name == "nt", "binário falso com shebang")
    @unittest.skipUnless(importlib.util.find_spec("yaml"), "PyYAML não instalado (o Hermes traz)")
    def test_hermes_config_estruturado_e_conserto_de_json_em_texto(self):
        import yaml

        home = self.tmp / "home"
        (home / ".hermes").mkdir(parents=True)
        # Config deixada por versão antiga do instalador: valores gravados como TEXTO JSON (Hermes 0.19).
        (home / ".hermes" / "config.yaml").write_text(
            "model:\n  provider: custom\n  default: meu-modelo\n"
            "plugins:\n  enabled: '[\"outro\", \"cofre\"]'\n"
            "mcp_servers:\n  cofre: '{\"command\": \"x\"}'\n  github: {command: npx}\n", encoding="utf-8")
        env = self.ambiente(home)
        env["PATH"] = str(self.hermes_falso()) + os.pathsep + env["PATH"]
        self.rodar(env, "--vault", str(home / "Cofre"), "--sem-opencode", "--sem-path")
        cfg = yaml.safe_load((home / ".hermes" / "config.yaml").read_text(encoding="utf-8"))
        self.assertEqual(cfg["model"], {"provider": "custom", "default": "meu-modelo"}, "config do usuário intacta")
        servidor = cfg["mcp_servers"]["cofre"]
        self.assertIsInstance(servidor, dict)
        self.assertEqual(servidor["timeout"], 1200)
        self.assertEqual(servidor["args"][-1], "mcp")
        self.assertEqual(cfg["mcp_servers"]["github"], {"command": "npx"})
        self.assertEqual(cfg["plugins"]["enabled"], ["outro", "cofre"])
        self.assertEqual(cfg["skills"]["disabled"], ["obsidian"])
        self.assertIs(cfg["memory"]["memory_enabled"], False)
        spec = cfg["agent"]["personalities"]["spec"]
        self.assertIn("[cofre]", spec["description"])
        self.assertIn("MODO SPEC", spec["system_prompt"])

        self.rodar(env, "--desinstalar")
        cfg = yaml.safe_load((home / ".hermes" / "config.yaml").read_text(encoding="utf-8"))
        self.assertNotIn("cofre", cfg["mcp_servers"])
        self.assertEqual(cfg["plugins"]["enabled"], ["outro"])
        self.assertNotIn("spec", (cfg.get("agent") or {}).get("personalities") or {})

    @unittest.skipIf(os.name == "nt", "binário falso com shebang")
    def test_hermes_sem_python_com_yaml_recebe_instrucao_em_yaml(self):
        home = self.tmp / "home"
        (home / ".hermes").mkdir(parents=True)
        env = self.ambiente(home)
        env["PATH"] = str(self.hermes_falso(com_yaml=False)) + os.pathsep + env["PATH"]
        saida = self.rodar(env, "--vault", str(home / "Cofre"), "--sem-opencode", "--sem-path")
        self.assertIn("mcp_servers:\n  cofre:", saida)
        self.assertIn("timeout: 1200", saida)
        self.assertFalse((home / ".hermes" / "config.yaml").exists(), "sem PyYAML não escreve nada pela metade")

if __name__ == "__main__":
    unittest.main()
