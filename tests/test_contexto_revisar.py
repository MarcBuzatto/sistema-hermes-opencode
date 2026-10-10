import unittest

from base import CofreTeste
from cofre import contexto, notebooklm, registrar as r
from cofre.revisar import revisar


class TestContexto(CofreTeste):
    def popular(self):
        c = str(self.proj)
        r.registrar_fato(self.cofre, self.agente, "O banco é PostgreSQL 16", status="verificado",
                         evidencias=[self.ev_arquivo("image: postgres:16")], cwd=c)
        h = r.registrar_fato(self.cofre, self.agente, "A API usa JWT para autenticação", cwd=c)
        r.atualizar_fato(self.cofre, self.humano, h.id, "refutar", motivo="Autenticação é por sessão com cookie")
        r.registrar_fato(self.cofre, self.agente, "O deploy de produção é na Vercel", cwd=c)
        r.registrar_fato(self.cofre, self.agente, "O usuário trabalha no fuso de Brasília", projeto="global")
        r.checkpoint(self.cofre, self.agente, "Mapeei a stack", proximos_passos=["tela de login"],
                     foco="Autenticação", cwd=str(self.proj))

    def test_secoes_e_rotulos(self):
        self.popular()
        texto = contexto.montar(self.cofre, cwd=str(self.proj))
        for trecho in ("Estado atual", "Foco: Autenticação", "Armadilhas", "NÃO é verdade", "VERIFICADOS",
                       "HIPÓTESES", "Regras do cofre", "Preferências do usuário"):
            self.assertIn(trecho, texto)

    def test_limite_de_tamanho_prioriza_armadilhas(self):
        self.popular()
        for i in range(30):
            r.registrar_fato(self.cofre, self.agente, f"Hipótese numerada {i} sobre o módulo {i * 7} xyz{i}",
                             forcar=True, projeto="loja")
        texto = contexto.montar(self.cofre, cwd=str(self.proj), max_chars=1800)
        self.assertLessEqual(len(texto), 1800)
        self.assertIn("NÃO é verdade", texto)
        self.assertIn("omitidos", texto)

    def test_sem_projeto_e_ancora(self):
        texto = contexto.montar(self.cofre, cwd=str(self.tmp))
        self.assertIn("nenhum projeto associado", texto)
        self.assertIn("loja", texto)
        self.popular()
        anc = contexto.montar(self.cofre, cwd=str(self.proj), modo="ancora")
        self.assertIn("Foco: Autenticação", anc)
        self.assertLess(len(anc), 500)

    def test_modo_sistema_estavel(self):
        self.popular()
        self.assertNotIn("Gerado", contexto.montar(self.cofre, cwd=str(self.proj), modo="sistema"))

    def test_buscar_e_ler(self):
        self.popular()
        achado = contexto.buscar(self.cofre, "postgres banco")
        self.assertIn("[VERIFICADO]", achado)
        ident = achado.split("\n")[1].split()[1]
        self.assertIn("Pode usar", contexto.ler(self.cofre, ident))


class TestRevisarENotebookLM(CofreTeste):
    def test_evidencia_que_deixou_de_conferir(self):
        res = r.registrar_fato(self.cofre, self.agente, "O banco é PostgreSQL 16", status="verificado",
                               evidencias=[self.ev_arquivo("image: postgres:16")])
        compose = self.proj / "docker-compose.yml"
        compose.write_text(compose.read_text(encoding="utf-8").replace("postgres:16", "postgres:17"), encoding="utf-8")
        achados = revisar(self.cofre)
        self.assertTrue(any(a.nota == res.id and "NÃO confere" in a.mensagem for a in achados))
        revisar(self.cofre, aplicar=True)
        self.assertEqual(type(self.cofre)(self.vault).por_id(res.id).status, "contestado")

    def test_segredo_colado_a_mao_e_apontado(self):
        nota = self.vault / "10-Projetos" / "loja" / "loja.md"
        nota.write_text(nota.read_text(encoding="utf-8") + "\nAKIA" + "A" * 16 + "\n", encoding="utf-8")
        self.assertTrue(any("credencial" in a.mensagem for a in revisar(self.cofre)))

    def test_exportar_e_importar(self):
        r.registrar_fato(self.cofre, self.agente, "O banco é PostgreSQL 16", status="verificado",
                         evidencias=[self.ev_arquivo("image: postgres:16")], cwd=str(self.proj))
        r.registrar_fato(self.cofre, self.agente, "O deploy de produção é na Vercel", projeto="loja")
        r.registrar_fato(self.cofre, self.agente, "O usuário usa Windows 11 como sistema principal", projeto="global")
        arquivos = notebooklm.exportar(self.cofre, "loja", incluir_hipoteses=True)
        self.assertEqual(len(arquivos), 6)
        verificados = arquivos[1].read_text(encoding="utf-8")
        self.assertIn("PostgreSQL 16", verificados)
        self.assertNotIn("Vercel", verificados)
        self.assertIn("Vercel", arquivos[5].read_text(encoding="utf-8"))
        antes = len(type(self.cofre)(self.vault).por_tipo("fato"))
        self.assertEqual(antes, 3, "exportações não podem ser indexadas como notas")
        self.assertNotIn("Windows 11", "".join(a.read_text(encoding="utf-8") for a in arquivos))
        res = notebooklm.importar(self.cofre, "Resumo: projeto usa Next.js", "Briefing", projeto="loja")
        self.assertEqual(self.cofre.por_id(res.id).meta["confiabilidade"], "sintese-externa")


if __name__ == "__main__":
    unittest.main()
