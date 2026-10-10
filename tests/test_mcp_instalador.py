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
        self.assertEqual(len(nomes), 10)
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
    def test_instala_e_desinstala_preservando_conteudo(self):
        home = self.tmp / "home"
        (home / ".config" / "opencode").mkdir(parents=True)
        (home / ".hermes").mkdir()
        (home / ".config" / "opencode" / "AGENTS.md").write_text("# Minhas regras\n- usar pnpm\n", encoding="utf-8")
        (home / ".config" / "opencode" / "opencode.json").write_text('{"model": "opencode/x"}', encoding="utf-8")
        (home / ".hermes" / "SOUL.md").write_text("Seja direto.\n", encoding="utf-8")
        env = {k: v for k, v in os.environ.items() if k not in ("COFRE_VAULT",)}
        env.update(HOME=str(home), USERPROFILE=str(home), XDG_CONFIG_HOME=str(home / ".config"),
                   XDG_DATA_HOME=str(home / ".local" / "share"), LOCALAPPDATA=str(home / "AppData" / "Local"),
                   APPDATA=str(home / "AppData" / "Roaming"), PATH=os.path.dirname(sys.executable),
                   OPENCODE_CONFIG_DIR=str(home / ".config" / "opencode"), HERMES_HOME=str(home / ".hermes"))
        vault = home / "Cofre"
        script = str(RAIZ / "scripts" / "instalar.py")
        r = subprocess.run([sys.executable, script, "--vault", str(vault), "--sem-path"], capture_output=True,
                           text=True, env=env, timeout=120, encoding="utf-8")
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        agents = (home / ".config" / "opencode" / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("- usar pnpm", agents)
        self.assertIn("Protocolo do Cofre", agents)
        cfg = json.loads((home / ".config" / "opencode" / "opencode.json").read_text(encoding="utf-8"))
        self.assertEqual(cfg["model"], "opencode/x")
        self.assertIn("cofre", cfg["mcp"])
        self.assertIn("Protocolo do Cofre", (home / ".hermes" / "SOUL.md").read_text(encoding="utf-8"))
        self.assertTrue((home / ".hermes" / "plugins" / "cofre" / "__init__.py").exists())
        self.assertTrue((home / ".agents" / "skills" / "cofre-protocolo" / "SKILL.md").exists())
        self.assertTrue((vault / "00-Sistema" / "Protocolo das IAs.md").exists())
        self.assertFalse((home / ".claude").exists(), "Claude não deve ser tocado sem --claude-code")

        r = subprocess.run([sys.executable, script, "--desinstalar"], capture_output=True, text=True, env=env,
                           timeout=120, encoding="utf-8")
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        self.assertEqual((home / ".config" / "opencode" / "AGENTS.md").read_text(encoding="utf-8"),
                         "# Minhas regras\n- usar pnpm\n")
        self.assertEqual((home / ".hermes" / "SOUL.md").read_text(encoding="utf-8"), "Seja direto.\n")
        cfg = json.loads((home / ".config" / "opencode" / "opencode.json").read_text(encoding="utf-8"))
        self.assertNotIn("mcp", cfg)
        self.assertTrue((vault / "00-Sistema" / "Perfil.md").exists())


if __name__ == "__main__":
    unittest.main()
