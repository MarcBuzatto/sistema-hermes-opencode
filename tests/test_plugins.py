"""Plugins do Hermes (carregado com um ctx falso) e do OpenCode (executado com Node, se houver)."""

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import unittest

from base import RAIZ, CofreTeste
from cofre import specs


class _Ctx:
    def __init__(self):
        self.secoes, self.hooks = {}, {}

    def register_system_prompt_section(self, nome, funcao, position=None, max_chars=None):
        self.secoes[nome] = funcao

    def register_hook(self, nome, funcao):
        self.hooks[nome] = funcao


def _usuario(texto):
    return {"role": "user", "content": texto}


class PluginTeste(CofreTeste):
    def setUp(self):
        super().setUp()
        nota = self.vault / "30-Conhecimento" / "Seguranca" / "Burp Suite.md"
        nota.parent.mkdir(parents=True, exist_ok=True)
        nota.write_text("# Burp Suite\nProxy de interceptação usado no pentest web.\n", encoding="utf-8")
        (self.proj / "ok.py").write_text("print('ok')\n", encoding="utf-8")

    def spec_aprovada(self):
        res = specs.criar(self.cofre, self.humano, "Cupom no checkout", "Cliente aplica cupom",
                          requisitos=["QUANDO o cupom for válido, O SISTEMA DEVE dar desconto"],
                          tarefas=["Validar cupom | verificar: python ok.py"], projeto="loja")
        specs.atualizar(self.cofre, self.humano, "aprovar", res.id)
        return res.id


class TestPluginHermes(PluginTeste):
    def carregar(self):
        fonte = (RAIZ / "adapters" / "hermes" / "plugin" / "cofre" / "__init__.py").read_text(encoding="utf-8")
        arquivo = self.tmp / "hermes_plugin_cofre.py"
        arquivo.write_text(fonte.replace("{{COFRE_APP}}", str(RAIZ)), encoding="utf-8")
        spec = importlib.util.spec_from_file_location("hermes_plugins_cofre_teste", arquivo)
        modulo = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(modulo)
        ctx = _Ctx()
        modulo.register(ctx)
        return ctx

    def test_secao_de_sistema_e_contexto_por_mensagem(self):
        self.spec_aprovada()
        ctx = self.carregar()
        secao = ctx.secoes["cofre.contexto"]({"cwd": str(self.proj), "session_id": "s1"})
        self.assertIn("contexto do projeto: Loja", secao)
        self.assertNotIn("AGORA", secao, "a seção é montada uma vez por sessão; AGORA ficaria velho")
        self.assertLessEqual(len(secao), 4000)

        por_mensagem = ctx.hooks["pre_llm_call"]
        saida = por_mensagem(session_id="s1", user_message="o burp não intercepta https", is_first_turn=True,
                             conversation_history=[_usuario("o burp não intercepta https")])
        self.assertIn("Burp Suite", saida["context"])
        self.assertIn("AGORA · spec", saida["context"])
        self.assertNotIn("mensagens do usuário sem checkpoint", saida["context"])

        saida = por_mensagem(session_id="s1", user_message="e agora?", conversation_history=[_usuario("x")] * 8)
        self.assertIn("8 mensagens do usuário sem checkpoint", saida["context"])
        self.assertNotIn("Burp Suite", saida["context"], "o que já foi mostrado na sessão não se repete")

        historico = [_usuario("x")] * 8 + [
            {"role": "assistant", "content": "", "tool_calls": [{"function": {"name": "mcp_cofre_cofre_checkpoint"}}]}]
        saida = por_mensagem(session_id="s1", user_message="segue", conversation_history=historico)
        self.assertNotIn("mensagens do usuário sem checkpoint", (saida or {}).get("context", ""))

    def test_sem_spec_ancora_so_a_cada_n_turnos(self):
        ctx = self.carregar()
        ctx.secoes["cofre.contexto"]({"cwd": str(self.proj), "session_id": "s2"})
        por_mensagem = ctx.hooks["pre_llm_call"]
        saidas = [por_mensagem(session_id="s2", user_message="ok", conversation_history=[]) for _ in range(5)]
        com_ancora = [i for i, s in enumerate(saidas, 1) if s and "[cofre · loja]" in s["context"]]
        self.assertEqual(com_ancora, [5])


@unittest.skipUnless(shutil.which("node"), "Node não instalado")
class TestPluginOpenCode(PluginTeste):
    def test_contexto_agente_spec_lembrete_e_cache(self):
        self.spec_aprovada()
        app = self.tmp / "app"
        app.mkdir()
        (app / "__main__.py").write_text(
            f"import sys\nsys.path.insert(0, {str(RAIZ)!r})\nfrom cofre.cli import main\nraise SystemExit(main())\n",
            encoding="utf-8")
        fonte = (RAIZ / "adapters" / "opencode" / "plugins" / "cofre.js").read_text(encoding="utf-8")
        plugin = self.tmp / "cofre.mjs"
        plugin.write_text(fonte.replace("{{PYTHON}}", json.dumps(sys.executable)[1:-1])
                          .replace("{{APP}}", json.dumps(str(app))[1:-1]).replace("{{DESTINO_SKILLS}}", "null"),
                          encoding="utf-8")
        roteiro = self.tmp / "roteiro.mjs"
        roteiro.write_text(_ROTEIRO, encoding="utf-8")
        env = dict(os.environ, COFRE_VAULT=str(self.vault))
        for var in ("OPENCODE", "CLAUDECODE", "COFRE_AGENTE"):
            env.pop(var, None)
        r_ = subprocess.run(["node", str(roteiro), plugin.as_uri(), str(self.proj), sys.executable, str(app)],
                            capture_output=True, text=True, encoding="utf-8", env=env, timeout=120)
        self.assertEqual(r_.returncode, 0, r_.stderr)
        res = json.loads(r_.stdout.strip().splitlines()[-1])

        self.assertIn("contexto do projeto: Loja", res["build"])
        self.assertIn("cofre_tarefa(acao='proxima')", res["build"])
        self.assertIn("Burp Suite", res["build"])
        self.assertNotIn("MODO SPEC", res["build"])
        self.assertIn("MODO SPEC", res["spec"])
        self.assertIn("9 mensagens do usuário sem checkpoint", res["lembrete"])
        self.assertNotIn("mensagens do usuário sem checkpoint", res["pos_checkpoint"])
        self.assertIn("Trabalhe SÓ em T1", res["apos_tarefa"], "chamada nova ao cofre invalida o cache")
        self.assertIn("MODO SPEC", res["v1_spec"])
        self.assertIn("contexto do projeto: Loja", res["v1_compactacao"])


_ROTEIRO = r"""
import { execFileSync } from "node:child_process"
const [plugin, proj, python, app] = process.argv.slice(2)
const p = (await import(plugin)).default
const hooks = {}
const ctx = {
  location: { directory: proj },
  session: { hook: async (nome, fn) => { hooks[nome] = fn }, get: async () => ({ location: { directory: proj } }) },
}
await p.setup(ctx)
const usuario = (n) => [...Array(n)].map((_, i) => ({ role: "user", content: [{ type: "text", text: `o burp nao intercepta https ${i}` }] }))
const chamada = (nome) => ({ role: "assistant", content: [{ type: "tool-call", name: nome }] })
async function contexto(agent, messages) {
  const ev = { sessionID: "s1", agent, system: [], messages }
  await hooks.context(ev)
  return ev.system.map((x) => x.text).join("\n---\n")
}
const r = {}
r.build = await contexto("build", usuario(1))
r.spec = await contexto("spec", usuario(1))
r.lembrete = await contexto("build", usuario(9))
r.pos_checkpoint = await contexto("build", [...usuario(9), chamada("cofre_cofre_checkpoint")])
execFileSync(python, [app, "tarefa", "proxima", "--cwd", proj, "--humano"])
r.apos_tarefa = await contexto("build", [...usuario(1), chamada("cofre_cofre_tarefa")])
const v1 = await p.server({ directory: proj })
const msgs = { messages: [{ info: { role: "user", agent: "spec" }, parts: [{ type: "text", text: "continua" }] }] }
await v1["experimental.chat.messages.transform"]({}, msgs)
const sys1 = { system: [] }
await v1["experimental.chat.system.transform"]({}, sys1)
r.v1_spec = sys1.system.join("\n---\n")
const comp = { context: [] }
await v1["experimental.session.compacting"]({}, comp)
r.v1_compactacao = comp.context.join("\n")
console.log(JSON.stringify(r))
"""


if __name__ == "__main__":
    unittest.main()
