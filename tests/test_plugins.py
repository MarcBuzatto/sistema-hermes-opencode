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

    def test_memoria_entre_troca_de_modelos(self):
        # janela curta para exercitar o reaparecimento rápido
        cfg = self.vault / "00-Sistema" / "config.md"
        cfg.write_text(cfg.read_text(encoding="utf-8").replace("relevancia_repete_turnos: 6", "relevancia_repete_turnos: 2"),
                       encoding="utf-8")
        self.spec_aprovada()
        from cofre import registrar as r
        r.registrar_fato(self.cofre, self.humano, "O deploy da loja é na Vercel", status="verificado",
                         projeto="loja", evidencias=[{"tipo": "usuario", "ref": "conversa", "trecho": "deploy na vercel"}])
        ctx = self.carregar()
        secao = ctx.secoes["cofre.contexto"]
        por_mensagem = ctx.hooks["pre_llm_call"]

        # Modelo A monta o prompt de sistema: contexto do projeto + fato verificado + AGORA da spec.
        s_a = secao({"cwd": str(self.proj), "session_id": "s3"})
        self.assertIn("contexto do projeto: Loja", s_a)
        m1 = por_mensagem(session_id="s3", user_message="o burp não intercepta https",
                          conversation_history=[_usuario("x")])
        self.assertIn("Burp Suite", m1["context"])
        # Mesmo assunto no turno seguinte: não repete (economia).
        m2 = por_mensagem(session_id="s3", user_message="e o burp?", conversation_history=[_usuario("x")] * 2)
        self.assertNotIn("Burp Suite", (m2 or {}).get("context", ""))

        # Troca de LLM na mesma sessão: o novo modelo chama a seção de sistema de novo e recebe
        # o mesmo contexto durável (fato verificado + AGORA), sem depender do que o modelo A leu.
        s_b = secao({"cwd": str(self.proj), "session_id": "s3"})
        self.assertEqual(s_a, s_b)
        self.assertIn("Vercel", s_b)  # fato verificado está no prompt de todo modelo que assumir a conversa

        # Passada a janela (simula compactação/esquecimento), o ponteiro reaparece ("puxar de novo").
        m3 = por_mensagem(session_id="s3", user_message="vamos voltar ao burp", conversation_history=[_usuario("x")] * 3)
        self.assertIn("Burp Suite", m3["context"])

    def test_sem_spec_ancora_so_a_cada_n_turnos(self):
        ctx = self.carregar()
        ctx.secoes["cofre.contexto"]({"cwd": str(self.proj), "session_id": "s2"})
        por_mensagem = ctx.hooks["pre_llm_call"]
        saidas = [por_mensagem(session_id="s2", user_message="ok", conversation_history=[]) for _ in range(5)]
        com_ancora = [i for i, s in enumerate(saidas, 1) if s and "[cofre · loja]" in s["context"]]
        self.assertEqual(com_ancora, [5])


class _CtxAntigo(_Ctx):
    """PluginContext do Hermes 0.19 (PyPI): sem register_system_prompt_section."""
    register_system_prompt_section = property(lambda self: (_ for _ in ()).throw(AttributeError("antigo")))


class TestPluginHermesAntigo(PluginTeste):
    def test_sem_secao_de_sistema_contexto_vai_no_primeiro_turno_e_apos_compactar(self):
        fonte = (RAIZ / "adapters" / "hermes" / "plugin" / "cofre" / "__init__.py").read_text(encoding="utf-8")
        arquivo = self.tmp / "hermes_plugin_cofre_antigo.py"
        arquivo.write_text(fonte.replace("{{COFRE_APP}}", str(RAIZ)), encoding="utf-8")
        spec = importlib.util.spec_from_file_location("hermes_plugins_cofre_antigo", arquivo)
        modulo = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(modulo)
        ctx = _CtxAntigo()
        modulo.register(ctx)
        self.assertEqual(ctx.secoes, {})
        self.addCleanup(os.chdir, os.getcwd())
        os.chdir(self.proj)
        hist = [_usuario("oi")]
        r1 = ctx.hooks["pre_llm_call"](session_id="a", user_message="oi", is_first_turn=True, conversation_history=[])
        self.assertIn("contexto do projeto: Loja", r1["context"])
        self.assertIn("mcp__cofre__cofre_ler", r1["context"])
        hist += [_usuario("x")] * 6
        r2 = ctx.hooks["pre_llm_call"](session_id="a", user_message="segue", conversation_history=hist)
        self.assertNotIn("contexto do projeto", (r2 or {}).get("context", ""))
        r3 = ctx.hooks["pre_llm_call"](session_id="a", user_message="continua", conversation_history=hist[:2])
        self.assertIn("contexto do projeto: Loja", r3["context"], "histórico encolheu = compactação")


class TestGuardaPrivadaHermes(PluginTeste):
    carregar = TestPluginHermes.carregar

    def test_bloqueia_e_filtra_pasta_privada(self):
        ctx = self.carregar()
        antes, depois = ctx.hooks["pre_tool_call"], ctx.hooks["transform_tool_result"]
        privada = str(self.vault / "99-Privado" / "contrato.md")
        self.assertEqual(antes(tool_name="read_file", args={"path": privada}, task_id="s1")["action"], "block")
        self.assertEqual(antes(tool_name="terminal", args={"command": f"cat '{privada}'"}, task_id="s1")["action"], "block")
        self.assertIsNone(antes(tool_name="read_file", args={"path": str(self.vault / "30-Conhecimento" / "x.md")}, task_id="s1"))
        self.assertIsNone(antes(tool_name="terminal", args={"command": "ls 99-Privado"}, task_id="s1"),
                          "nome relativo fora do vault não bloqueia outros projetos")
        self.assertIsNone(antes(tool_name="terminal", args=None, task_id="s1"))
        # Dentro do vault, o nome relativo basta.
        ctx.secoes["cofre.contexto"]({"session_id": "s2", "cwd": str(self.vault)})
        self.assertEqual(antes(tool_name="terminal", args={"command": "cat 99-Privado/contrato.md"}, task_id="s2")["action"], "block")
        saida = f"30-Conhecimento/a.md:1:x\n{privada}:1:multa"
        self.assertEqual(depois(tool_name="search_files", args={}, result=saida, task_id="s1"), "30-Conhecimento/a.md:1:x")
        self.assertIsNone(depois(tool_name="search_files", args={}, result="nada privado", task_id="s1"))
        # Terminal do Hermes devolve JSON numa linha: filtra por dentro, mantém a estrutura e a linha pública.
        bruto = json.dumps({"output": f"pub.md:1:multa\n{privada}:2:multa", "exit_code": 0})
        self.assertEqual(json.loads(depois(tool_name="terminal", args={}, result=bruto, task_id="s1")),
                         {"output": "pub.md:1:multa", "exit_code": 0})

    def test_erro_na_guarda_nao_bloqueia_ferramenta(self):
        ctx = self.carregar()
        os.environ["COFRE_VAULT"] = str(self.tmp / "nao-existe")
        modulo = ctx.hooks["pre_tool_call"].__globals__
        modulo["_guarda"][:] = [0.0, None]
        with self.assertLogs("cofre", level="WARNING"):
            self.assertIsNone(ctx.hooks["pre_tool_call"](tool_name="read_file", args={"path": "/x"}, task_id="s1"))


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
                          .replace("{{APP}}", json.dumps(str(app))[1:-1]).replace("{{DESTINO_SKILLS}}", "null").replace("{{DESTINO_AGENTES}}", "null"),
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
        self.assertIn("cofre_ler = cofre_cofre_ler", res["build"])
        self.assertIn("cofre_tarefa(acao='proxima')", res["build"])
        self.assertIn("Burp Suite", res["build"])
        self.assertNotIn("MODO SPEC", res["build"])
        self.assertIn("MODO SPEC", res["spec"])
        self.assertIn("9 mensagens do usuário sem checkpoint", res["lembrete"])
        self.assertNotIn("mensagens do usuário sem checkpoint", res["pos_checkpoint"])
        self.assertIn("Trabalhe SÓ em T1", res["apos_tarefa"], "chamada nova ao cofre invalida o cache")
        self.assertIn("MODO SPEC", res["v1_spec"])
        self.assertIn("contexto do projeto: Loja", res["v1_compactacao"])
        self.assertTrue(res["privado_abs"])
        self.assertTrue(res["privado_comando"])
        self.assertFalse(res["vault_normal"])
        self.assertFalse(res["outro_projeto"], "nome relativo fora do vault não bloqueia outros projetos")
        self.assertEqual(res["grep_filtrado"], "30-Conhecimento/a.md:1:x")
        self.assertEqual(res["json_filtrado"], {"output": "pub.md:1:x", "code": 0})
        self.assertTrue(res["v2_privado"])
        self.assertFalse(res["v2_normal"])
        self.assertEqual(res["v2_filtrado"], ["ok.md:1:x", "a"])


_ROTEIRO = r"""
import { execFileSync } from "node:child_process"
const [plugin, proj, python, app] = process.argv.slice(2)
const p = (await import(plugin)).default
const hooks = {}
const ferramentas = {}
const ctx = {
  location: { directory: proj },
  session: { hook: async (nome, fn) => { hooks[nome] = fn }, get: async () => ({ location: { directory: proj } }) },
  tool: { hook: async (nome, fn) => { ferramentas[nome] = fn } },
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
const vault = process.env.COFRE_VAULT
const bloqueia = async (tool, args) => {
  try { await v1["tool.execute.before"]({ tool }, { args }); return false } catch { return true }
}
r.privado_abs = await bloqueia("read", { filePath: vault + "/99-Privado/contrato.md" })
r.privado_comando = await bloqueia("bash", { command: `cat "${vault}/99-Privado/contrato.md"` })
r.vault_normal = await bloqueia("read", { filePath: vault + "/30-Conhecimento/LEIA-ME.md" })
r.outro_projeto = await bloqueia("bash", { command: "ls 99-Privado" })
const saida = { output: `30-Conhecimento/a.md:1:x\n${vault}/99-Privado/contrato.md:1:multa` }
await v1["tool.execute.after"]({ tool: "grep" }, saida)
r.grep_filtrado = saida.output
const saidaJson = { output: JSON.stringify({ output: `pub.md:1:x\n${vault}/99-Privado/contrato.md:1:multa`, code: 0 }) }
await v1["tool.execute.after"]({ tool: "mcp_outro" }, saidaJson)
r.json_filtrado = JSON.parse(saidaJson.output)
const bloqueiaV2 = async (input) => {
  try { await ferramentas["execute.before"]({ tool: "read", sessionID: "s1", input }); return false } catch { return true }
}
r.v2_privado = await bloqueiaV2({ path: vault + "/99-Privado/contrato.md" })
r.v2_normal = await bloqueiaV2({ path: vault + "/30-Conhecimento/LEIA-ME.md" })
const depois = { tool: "shell", sessionID: "s1", status: "completed",
  result: { content: [{ type: "text", text: `ok.md:1:x\n${vault}/99-Privado/contrato.md:1:multa` }], output: "a\n" + vault + "/99-Privado/b" } }
await ferramentas["execute.after"](depois)
r.v2_filtrado = [depois.result.content[0].text, depois.result.output]
console.log(JSON.stringify(r))
"""


if __name__ == "__main__":
    unittest.main()
