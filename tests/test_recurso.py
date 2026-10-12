import io
import os
import unittest

from base import CofreTeste
from cofre import relevancia
from cofre.mcp import Servidor


class TestRecurso(CofreTeste):
    def setUp(self):
        super().setUp()
        os.environ["COFRE_CWD"] = str(self.proj)
        self.srv = Servidor(saida=io.BytesIO(), entrada=io.BytesIO())

    def chamar(self, nome, args):
        r = self.srv.chamar(nome, args)
        return r["content"][0]["text"], r["isError"]

    def rel(self, msg):
        self.cofre.invalidar()
        return relevancia.relevante(self.cofre, msg, projeto="loja")[0]

    def test_ia_registra_e_relevancia_mostra(self):
        # chamada "torta" de modelo fraco: chaves em inglês (title/link/when_to_use)
        texto, erro = self.chamar("cofre_recurso", {
            "title": "Shodan", "link": "https://www.shodan.io",
            "when_to_use": "descobrir serviços e portas expostas de um alvo em reconhecimento"})
        self.assertFalse(erro, texto)
        nota = self.cofre.raiz / "10-Projetos" / "loja" / "Recursos" / "shodan.md"
        self.assertTrue(nota.exists())
        conteudo = nota.read_text(encoding="utf-8")
        self.assertIn("tipo: recurso", conteudo)
        self.assertIn("url: https://www.shodan.io", conteudo)

        bloco = self.rel("preciso descobrir os serviços expostos do alvo")
        self.assertIn("recurso: Shodan", bloco)
        self.assertIn("https://www.shodan.io", bloco)
        self.assertEqual(self.rel("oi, tudo bem?"), "", "recurso não aparece sem relação")

    def test_global_quando_sem_projeto(self):
        os.environ.pop("COFRE_CWD", None)
        texto, erro = self.chamar("cofre_recurso", {"titulo": "regex101", "url": "https://regex101.com",
                                                    "quando_usar": "testar expressões regulares", "projeto": "global"})
        self.assertFalse(erro, texto)
        self.assertTrue((self.cofre.raiz / "30-Conhecimento" / "Recursos" / "regex101.md").exists())

    def test_atualiza_em_vez_de_duplicar(self):
        self.chamar("cofre_recurso", {"titulo": "Shodan", "url": "https://www.shodan.io", "quando_usar": "reconhecimento"})
        self.chamar("cofre_recurso", {"titulo": "Shodan", "url": "https://shodan.io", "quando_usar": "recon de portas e serviços"})
        notas = list((self.cofre.raiz / "10-Projetos" / "loja" / "Recursos").glob("*.md"))
        self.assertEqual(len(notas), 1)
        self.assertIn("recon de portas", notas[0].read_text(encoding="utf-8"))

    def test_url_com_segredo_e_bloqueada(self):
        texto, erro = self.chamar("cofre_recurso", {
            "titulo": "API interna", "url": "https://user:supersecret123@api.interno.com", "quando_usar": "x"})
        self.assertTrue(erro)
        self.assertIn("credencial", texto.lower())

    def test_cenario_pentest_ferramenta_surge_no_assunto(self):
        # Pesquisa que o usuário jogou no vault (skill + ferramenta em container)
        skill = self.vault / "60-Skills" / "seguranca" / "pentest-web" / "SKILL.md"
        skill.parent.mkdir(parents=True, exist_ok=True)
        skill.write_text("---\nname: pentest-web\ndescription: Metodologia de pentest autorizado em aplicações web "
                         "(escopo, reconhecimento, análise, relatório).\n---\n# Pentest web\n", encoding="utf-8")
        self.chamar("cofre_recurso", {"titulo": "Scanner em container", "url": "docker pull exemplo/scanner",
                                      "quando_usar": "varredura de vulnerabilidades no pentest autorizado",
                                      "tags": ["pentest", "docker"]})
        bloco = self.rel("quero fazer um pentest no meu próprio site")
        self.assertIn("pentest-web", bloco)
        # a ferramenta aparece quando a conversa fala de varredura
        bloco2 = self.rel("roda a varredura de vulnerabilidade no alvo")
        self.assertIn("Scanner em container", bloco2)
        self.assertIn("docker pull exemplo/scanner", bloco2)


if __name__ == "__main__":
    unittest.main()
