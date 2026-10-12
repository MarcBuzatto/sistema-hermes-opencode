"""Agentes do vault (65-Agentes) levados ao OpenCode e ao Hermes."""
import importlib.util
import io
import os
import sys
import unittest
from contextlib import redirect_stdout

from base import CofreTeste, cofre_main
from cofre import agentes, relevancia, revisar
from cofre.vault import Cofre

REVISOR = ("---\ndescription: Revisa código procurando falhas de segurança antes de publicar.\nmode: primary\n"
           "ferramentas_desligadas: [write, edit]\n---\nVocê é um revisor de segurança. Aponte arquivo e linha.\n")


class TestAgentes(CofreTeste):
    def criar(self, nome, texto=REVISOR):
        arq = self.vault / "65-Agentes" / f"{nome}.md"
        arq.parent.mkdir(parents=True, exist_ok=True)
        arq.write_text(texto, encoding="utf-8")
        return arq

    def test_listar_e_formato_do_opencode(self):
        self.criar("revisor-seguranca")
        [ag] = agentes.listar(self.vault)
        self.assertEqual((ag.id, ag.modo, ag.desligadas), ("revisor-seguranca", "primary", ["write", "edit"]))
        texto = agentes.texto_opencode(ag)
        self.assertTrue(texto.startswith("---\ndescription: Revisa código"))
        self.assertIn("mode: primary\ntools:\n  write: false\n  edit: false\n---\n", texto)
        self.assertTrue(texto.rstrip().endswith("Aponte arquivo e linha."))

    def test_sincronizar_opencode_preserva_agente_do_usuario_e_remove_o_que_saiu(self):
        destino = self.tmp / "opencode" / "agents"
        destino.mkdir(parents=True)
        (destino / "meu.md").write_text("---\ndescription: meu\n---\noi\n", encoding="utf-8")
        self.criar("revisor-seguranca")
        self.criar("meu")
        escritos, removidos, avisos = agentes.sincronizar_opencode(self.vault, destino)
        self.assertEqual(escritos, ["revisor-seguranca"])
        self.assertTrue(any("meu.md" in a for a in avisos))
        self.assertEqual((destino / "meu.md").read_text(encoding="utf-8"), "---\ndescription: meu\n---\noi\n")
        # Sem mudança: não reescreve.
        self.assertEqual(agentes.sincronizar_opencode(self.vault, destino)[0], [])
        (self.vault / "65-Agentes" / "revisor-seguranca.md").unlink()
        _, removidos, _ = agentes.sincronizar_opencode(self.vault, destino)
        self.assertEqual(removidos, ["revisor-seguranca"])
        self.assertFalse((destino / "revisor-seguranca.md").exists())
        self.assertTrue((destino / "meu.md").exists(), "arquivo do usuário nunca é apagado")

    def test_reservado_e_invalido_nao_vao_e_revisao_aponta(self):
        self.criar("spec")
        self.criar("sem-descricao", "---\nmode: primary\n---\nprompt\n")
        self.criar("Nome Torto", REVISOR)
        destino = self.tmp / "agents"
        escritos, _, _ = agentes.sincronizar_opencode(self.vault, destino)
        self.assertEqual(escritos, ["nome-torto"])
        msgs = {(a.nota, a.gravidade) for a in revisar.revisar(Cofre(self.vault), conferir_evidencias=False)}
        self.assertIn(("agente:spec", "alerta"), msgs)
        self.assertIn(("agente:sem-descricao", "erro"), msgs)
        self.assertIn(("agente:nome-torto", "alerta"), msgs)

    def test_relevancia_sugere_o_agente(self):
        self.criar("revisor-seguranca")
        relevancia._MEMORIA.clear()
        bloco = relevancia.relevante(Cofre(self.vault), "faz uma revisão de segurança antes de publicar")[0]
        self.assertIn("agente `revisor-seguranca`", bloco)
        self.assertIn("/personality revisor-seguranca", bloco)

    def test_cli_sincroniza_so_o_destino_pedido(self):
        self.criar("revisor-seguranca")
        destino = self.tmp / "oc" / "agents"
        os.environ["HERMES_HOME"] = str(self.tmp / "hermes")
        (self.tmp / "hermes").mkdir()
        with redirect_stdout(io.StringIO()) as saida:
            cofre_main(["agentes", "sincronizar", "--opencode", str(destino)])
        self.assertTrue((destino / "revisor-seguranca.md").exists())
        self.assertNotIn("Hermes", saida.getvalue())
        self.assertFalse((self.tmp / "hermes" / "config.yaml").exists())

    @unittest.skipUnless(importlib.util.find_spec("yaml"), "PyYAML não instalado (o Hermes traz)")
    def test_sincronizar_hermes_personalities(self):
        import yaml

        config = self.tmp / "hermes" / "config.yaml"
        config.parent.mkdir()
        config.write_text("agent:\n  personalities:\n    meu: {description: minha, system_prompt: oi}\n"
                          "model:\n  default: x\n", encoding="utf-8")
        self.criar("revisor-seguranca")
        self.criar("meu")
        escritos, _, avisos = agentes.sincronizar_hermes(self.vault, config, sys.executable)
        self.assertEqual(escritos, ["revisor-seguranca"])
        self.assertTrue(any("'meu'" in a for a in avisos))
        cfg = yaml.safe_load(config.read_text(encoding="utf-8"))
        self.assertEqual(cfg["model"], {"default": "x"})
        self.assertEqual(cfg["agent"]["personalities"]["meu"], {"description": "minha", "system_prompt": "oi"})
        p = cfg["agent"]["personalities"]["revisor-seguranca"]
        self.assertIn("revisor de segurança", p["system_prompt"])
        _, removidos, _ = agentes.sincronizar_hermes(self.vault, config, sys.executable, remover=True)
        self.assertEqual(removidos, ["revisor-seguranca"])
        cfg = yaml.safe_load(config.read_text(encoding="utf-8"))
        self.assertEqual(list(cfg["agent"]["personalities"]), ["meu"])


if __name__ == "__main__":
    unittest.main()
