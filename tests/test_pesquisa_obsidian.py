"""Ajustes vindos da pesquisa do usuário sobre Obsidian (respostas do NotebookLM, 1 a 13)."""
import io
import json
import os
import re
import shutil
import subprocess
import unittest
from contextlib import redirect_stdout

from base import RAIZ, CofreTeste, cofre_main
from cofre import contexto, relevancia, revisar
from cofre import registrar as r
from cofre import skills as skills_mod
from cofre.mcp import Servidor
from cofre.vault import Cofre, agora, ler_nota


class TestPesquisaObsidian(CofreTeste):
    def nota(self, rel, texto):
        caminho = self.vault / rel
        caminho.parent.mkdir(parents=True, exist_ok=True)
        caminho.write_text(texto, encoding="utf-8")
        return caminho

    def rel(self, msg, projeto=None):
        self.cofre.invalidar()
        relevancia._MEMORIA.clear()
        return relevancia.relevante(type(self.cofre)(self.vault), msg, projeto=projeto)[0]

    def test_data_e_hora_no_formato_do_obsidian(self):
        self.assertRegex(agora(), r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$")
        res = r.checkpoint(self.cofre, self.agente, resumo="Primeira etapa pronta", cwd=str(self.proj))
        sessao = ler_nota(self.cofre.por_id(res.id).caminho)
        self.assertRegex(str(sessao.meta["atualizada"]), r"T\d{2}:\d{2}:\d{2}$")
        # Histórico continua legível (sem o T).
        self.assertRegex(sessao.corpo, r"### \d{2}:\d{2}\n")
        # Um segundo checkpoint em seguida reaproveita a mesma sessão (lê o formato novo).
        res2 = r.checkpoint(self.cofre, self.agente, resumo="Segunda etapa", cwd=str(self.proj))
        self.assertEqual(res.id, res2.id)

    def test_sessao_com_data_no_formato_antigo_ainda_e_reaproveitada(self):
        res = r.checkpoint(self.cofre, self.agente, resumo="Etapa inicial", cwd=str(self.proj))
        nota = self.cofre.por_id(res.id)
        texto = nota.caminho.read_text(encoding="utf-8")
        antigo = re.sub(r"atualizada: (\d{4}-\d{2}-\d{2})T(\d{2}:\d{2}):\d{2}", r"atualizada: \1 \2", texto)
        nota.caminho.write_text(antigo, encoding="utf-8")
        self.cofre.invalidar()
        res2 = r.checkpoint(self.cofre, self.agente, resumo="Etapa seguinte", cwd=str(self.proj))
        self.assertEqual(res.id, res2.id)

    def test_description_vira_o_resumo_do_ponteiro(self):
        self.nota("30-Conhecimento/Frontend/Tailwind dark mode.md",
                  "---\ndescription: Liga o tema escuro pela classe dark no html e darkMode class no config.\n---\n"
                  "# Tailwind dark mode\n\nTexto longo que não deveria virar o resumo.\n")
        bloco = self.rel("como faço o dark mode no tailwind")
        self.assertIn("Liga o tema escuro pela classe dark", bloco)
        self.assertNotIn("Texto longo", bloco)

    def test_moc_surge_como_mapa_do_assunto(self):
        self.nota("30-Conhecimento/Frontend/Tailwind dark mode.md", "# Tailwind dark mode\nTema escuro por classe.\n")
        self.nota("30-Conhecimento/Frontend/Zustand vs Redux.md", "# Zustand vs Redux\nEstado global simples.\n")
        self.nota("30-Conhecimento/Frontend/Next cache.md", "# Next cache\nRevalidate por rota.\n")
        self.nota("30-Conhecimento/MOCs/Frontend.md",
                  "---\ntipo: moc\ndescription: Tudo sobre frontend do usuário.\n---\n# Frontend\n\n"
                  "- [[Tailwind dark mode]] — tema escuro\n- [[Zustand vs Redux]] — estado\n- [[Next cache]] — cache\n")
        bloco = self.rel("vamos mexer no frontend do projeto")
        linhas = [ln for ln in bloco.split("\n") if ln.startswith("- ")]
        self.assertTrue(linhas, bloco)
        self.assertIn("mapa do assunto: Frontend (3 notas)", linhas[0])

    def test_moc_por_tag(self):
        self.nota("30-Conhecimento/MOCs/Pagamentos.md",
                  "---\ntags: [moc]\n---\n# Pagamentos\n\n- [[Stripe webhooks]]\n- [[Pix]]\n")
        self.assertIn("mapa do assunto: Pagamentos (2 notas)", self.rel("integração de pagamentos"))

    def test_arquivo_morto_fica_fora_da_busca_automatica(self):
        self.nota("90-Arquivo/Projeto antigo/Kubernetes legado.md", "# Kubernetes legado\nCluster antigo desligado.\n")
        self.assertEqual(self.rel("subir no kubernetes"), "")
        self.assertIn("Kubernetes legado", contexto.buscar(self.cofre, "kubernetes"))


    # ---- 5 e 7: nota longa lida por partes ------------------------------------
    def nota_longa(self):
        partes = "\n\n".join(f"## Etapa {i} do deploy\n" + ("passo detalhado " * 200) for i in range(1, 13))
        return self.nota("30-Conhecimento/Devops/Guia de deploy.md",
                         "---\ndescription: Guia completo de deploy.\n---\n# Guia de deploy\n\nResumo: deploy em 12 etapas.\n\n"
                         + partes)

    def test_nota_longa_vem_com_resumo_e_secoes(self):
        self.nota_longa()
        texto = contexto.ler(self.cofre, "30-Conhecimento/Devops/Guia de deploy")
        self.assertIn("Resumo: deploy em 12 etapas.", texto)
        self.assertIn("description: Guia completo de deploy.", texto)
        self.assertIn("- ## Etapa 12 do deploy (~", texto)
        self.assertIn("secao=", texto)
        self.assertNotIn("passo detalhado", texto)
        self.assertLess(len(texto), 2500)

    def test_secao_por_titulo_numero_e_tudo(self):
        self.nota_longa()
        ref = "30-Conhecimento/Devops/Guia de deploy"
        um = contexto.ler(self.cofre, ref, secao="etapa 1 do deploy")
        self.assertIn("Seção: Etapa 1 do deploy", um)
        self.assertNotIn("Etapa 10", um)
        self.assertIn("Seção: Etapa 10 do deploy", contexto.ler(self.cofre, ref, secao="Etapa 10"))
        self.assertIn("Seção: Etapa 3 do deploy", contexto.ler(self.cofre, ref, secao="3"))
        self.assertIn("não existe nesta nota", contexto.ler(self.cofre, ref, secao="kubernetes"))
        self.assertGreater(contexto.ler(self.cofre, ref, secao="tudo").count("passo detalhado"), 2000)

    def test_nota_curta_vem_inteira(self):
        self.nota("30-Conhecimento/Curta.md", "# Curta\n\n## A\ntexto a\n\n## B\ntexto b\n")
        texto = contexto.ler(self.cofre, "30-Conhecimento/Curta")
        self.assertIn("texto a", texto)
        self.assertIn("texto b", texto)

    def test_secao_pela_ferramenta_com_nome_em_ingles(self):
        self.nota_longa()
        os.environ["COFRE_CWD"] = str(self.proj)
        srv = Servidor(saida=io.BytesIO(), entrada=io.BytesIO())
        res = srv.chamar("cofre_ler", {"id": "30-Conhecimento/Devops/Guia de deploy.md", "section": "Etapa 2 do deploy"})
        self.assertFalse(res["isError"])
        self.assertIn("Seção: Etapa 2 do deploy", res["content"][0]["text"])

    # ---- 13: pasta privada --------------------------------------------------------
    def test_pasta_privada_fica_fora_de_tudo(self):
        self.nota("99-Privado/Contrato Acme.md", "---\ntipo: fonte\nid: N-PRIV1\n---\n# Contrato Acme\nMulta rescisória do contrato Acme.\n")
        self.nota("40-Clientes/Confidencial/Acme salario.md", "# Acme salario\nSalário combinado com a Acme.\n")
        self.assertEqual(self.rel("qual a multa rescisória"), "")
        self.assertIn("Nada encontrado", contexto.buscar(self.cofre, "multa rescisória"))
        self.assertIsNone(self.cofre.por_id("N-PRIV1"))
        bloqueio = contexto.ler(self.cofre, "99-Privado/Contrato Acme")
        self.assertIn("pasta privada", bloqueio)
        self.assertNotIn("Multa", bloqueio)
        self.assertIn("pasta privada", contexto.ler(self.cofre, "99-Privado\\Contrato Acme.md"))
        # Pasta extra só fica privada quando listada na config.
        self.assertIn("Acme salario", contexto.buscar(self.cofre, "salário acme"))
        cfg = self.vault / "00-Sistema" / "config.md"
        cfg.write_text(cfg.read_text(encoding="utf-8").replace(
            "pastas_privadas: []", "pastas_privadas:\n  - 40-Clientes/Confidencial"), encoding="utf-8")
        cofre = Cofre(self.vault)
        relevancia._MEMORIA.clear()
        self.assertIn("Nada encontrado", contexto.buscar(cofre, "salário acme"))
        self.assertIn("pasta privada", contexto.ler(cofre, "40-Clientes/Confidencial/Acme salario"))

    @unittest.skipUnless(shutil.which("git"), "git não instalado")
    def test_revisar_avisa_pasta_privada_versionada(self):
        self.nota("99-Privado/Notas.md", "# Notas\nconfidencial\n")
        subprocess.run(["git", "init", "-q", str(self.vault)], check=True)
        def erros():
            return [a.mensagem for a in revisar.revisar(Cofre(self.vault), conferir_evidencias=False)
                    if a.nota == "99-Privado" and a.gravidade == "erro"]
        self.assertEqual(erros(), [], "o template já ignora 99-Privado")
        gi = self.vault / ".gitignore"
        gi.write_text(gi.read_text(encoding="utf-8").replace("99-Privado/\n", ""), encoding="utf-8")
        self.assertTrue(any(".gitignore" in m for m in erros()))
        subprocess.run(["git", "-C", str(self.vault), "add", "99-Privado"], check=True)
        self.assertTrue(any("já está versionada" in m for m in erros()))

    def test_init_completa_gitignore_sem_apagar_linhas_do_usuario(self):
        gi = self.vault / ".gitignore"
        gi.write_text("minha-pasta/\n.obsidian/workspace*.json\n", encoding="utf-8")
        with redirect_stdout(io.StringIO()) as saida:
            cofre_main(["init", str(self.vault)])
        texto = gi.read_text(encoding="utf-8")
        self.assertIn("minha-pasta/", texto)
        self.assertIn("99-Privado/", texto)
        self.assertEqual(texto.count(".obsidian/workspace*.json"), 1)
        self.assertIn("linha(s) nova(s)", saida.getvalue())

    def test_cli_privado_lista_caminhos(self):
        with redirect_stdout(io.StringIO()) as saida:
            cofre_main(["privado", "--json"])
        dados = json.loads(saida.getvalue())
        self.assertEqual(dados["relativas"], ["99-Privado"])
        self.assertIn(os.path.join(os.path.abspath(self.vault), "99-Privado"), dados["absolutas"])
        self.assertIn(str((self.vault / "99-Privado").resolve()), dados["absolutas"])

    @unittest.skipIf(os.name == "nt", "symlink exige privilégio no Windows")
    def test_cli_privado_inclui_caminho_pelo_symlink(self):
        atalho = self.tmp / "atalho-vault"
        atalho.symlink_to(self.vault, target_is_directory=True)
        os.environ["COFRE_VAULT"] = str(atalho)
        with redirect_stdout(io.StringIO()) as saida:
            cofre_main(["privado", "--json"])
        dados = json.loads(saida.getvalue())
        self.assertIn(str(atalho / "99-Privado"), dados["absolutas"])
        self.assertIn(str((self.vault / "99-Privado").resolve()), dados["absolutas"])

    # ---- 8 e 9: revisão de notas soltas --------------------------------------------
    def test_revisar_orfas_moc_sugerido_e_nota_longa(self):
        for nome in ("Tailwind dark mode", "Zustand vs Redux", "Next cache"):
            self.nota(f"30-Conhecimento/Frontend/{nome}.md", f"# {nome}\nTexto curto.\n")
        self.nota("30-Conhecimento/Ideias soltas.md", "# Ideias soltas\n" + "palavra " * 1600)
        def info():
            return [a.mensagem for a in revisar.revisar(Cofre(self.vault), conferir_evidencias=False) if a.gravidade == "info"]
        msgs = info()
        self.assertTrue(any("sem nenhum [[link]]" in m and "Next cache" in m for m in msgs), msgs)
        self.assertTrue(any("pasta 30-Conhecimento/Frontend sem mapa" in m for m in msgs), msgs)
        self.assertTrue(any("sem títulos (##)" in m for m in msgs), msgs)
        self.nota("30-Conhecimento/MOCs/Frontend.md", "---\ntipo: moc\n---\n# Frontend\n\n"
                  "- [[Tailwind dark mode]]\n- [[Zustand vs Redux]]\n- [[Next cache]]\n")
        msgs = info()
        self.assertFalse(any("Frontend sem mapa" in m for m in msgs), msgs)
        self.assertFalse(any("sem nenhum [[link]]" in m and "Next cache" in m for m in msgs), msgs)

    # ---- 10: pesquisa -> skill ---------------------------------------------------
    def skill(self, status, fontes=""):
        pasta = self.vault / "60-Skills" / "devops" / "backup-rclone"
        pasta.mkdir(parents=True, exist_ok=True)
        (pasta / "SKILL.md").write_text(
            f"---\nname: backup-rclone\ndescription: Backup do vault com rclone crypt para nuvem.\nstatus: {status}\n{fontes}---\n"
            "# Backup com rclone\n\n1. Criar o remoto cifrado.\n", encoding="utf-8")

    def test_skill_rascunho_e_marcada_e_verificada_exige_fontes(self):
        self.skill("rascunho", "fontes: [N-AB123]\n")
        self.assertIn("RASCUNHO", self.rel("configurar backup do vault com rclone"))
        self.skill("verificada")
        alertas = [m for g, rot, m in skills_mod.verificar(self.vault) if rot == "skill:backup-rclone"]
        self.assertTrue(any("sem 'fontes'" in m for m in alertas), alertas)
        self.skill("verificada", "fontes: [N-AB123]\n")
        self.assertFalse([m for g, rot, m in skills_mod.verificar(self.vault) if rot == "skill:backup-rclone"])
        self.assertNotIn("RASCUNHO", self.rel("configurar backup do vault com rclone"))

    # ---- 12: anexos -----------------------------------------------------------
    def test_template_tem_anexos_e_privado(self):
        app = json.loads((RAIZ / "vault-template" / ".obsidian" / "app.json").read_text(encoding="utf-8"))
        self.assertEqual(app["attachmentFolderPath"], "80-Anexos")
        self.assertTrue((self.vault / "80-Anexos" / "LEIA-ME.md").is_file())
        self.assertTrue((self.vault / "99-Privado" / "LEIA-ME.md").is_file())
        self.assertIn("anexo:", (self.vault / "00-Sistema" / "Templates" / "Fonte.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
