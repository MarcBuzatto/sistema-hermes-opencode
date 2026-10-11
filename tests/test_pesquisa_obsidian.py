"""Ajustes vindos da pesquisa do usuário sobre Obsidian (respostas 1 a 4 do NotebookLM)."""
import re
import unittest

from base import CofreTeste
from cofre import contexto, relevancia
from cofre import registrar as r
from cofre.vault import agora, ler_nota


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


if __name__ == "__main__":
    unittest.main()
