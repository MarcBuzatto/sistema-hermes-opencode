import unittest

from base import CofreTeste
from cofre import registrar as r
from cofre.config import ErroCofre
from cofre.vault import ler_nota, secao


class TestFatos(CofreTeste):
    def test_verificado_sem_evidencia_vira_hipotese(self):
        res = r.registrar_fato(self.cofre, self.agente, "O deploy de produção é na Vercel", status="verificado")
        self.assertEqual(ler_nota(res.caminho).meta["status"], "hipotese")
        self.assertTrue(any("HIPÓTESE" in a for a in res.avisos))

    def test_evidencia_de_arquivo_conferida(self):
        res = r.registrar_fato(self.cofre, self.agente, "O banco é PostgreSQL 16", status="verificado",
                               evidencias=[{"tipo": "arquivo", "ref": "docker-compose.yml:3", "trecho": "image: postgres:16"}],
                               cwd=str(self.proj / "src"))
        nota = ler_nota(res.caminho)
        self.assertEqual(nota.meta["status"], "verificado")
        self.assertEqual(nota.meta["projeto"], "[[loja]]")
        self.assertEqual(nota.meta["fonte"], "arquivo")
        self.assertEqual(nota.meta["registrado_por"], "opencode/glm-4.6")
        self.assertTrue(nota.meta["revisar_em"])
        self.assertIn("projeto", nota.meta)

    def test_evidencia_inventada_rejeitada(self):
        with self.assertRaisesRegex(ErroCofre, "NÃO confere"):
            r.registrar_fato(self.cofre, self.agente, "O banco é MySQL 8", status="verificado",
                             evidencias=[self.ev_arquivo("image: mysql:8")])
        with self.assertRaisesRegex(ErroCofre, "não encontrado"):
            r.registrar_fato(self.cofre, self.agente, "Existe um Dockerfile na raiz", status="verificado",
                             evidencias=[{"tipo": "arquivo", "ref": "nao-existe/Dockerfile", "trecho": "FROM node"}])
        self.assertEqual(self.cofre.por_tipo("fato"), [])

    def test_refutado_nao_volta_por_parafrase(self):
        res = r.registrar_fato(self.cofre, self.agente, "A API usa JWT para autenticação")
        r.atualizar_fato(self.cofre, self.agente, res.id, "refutar",
                         motivo="Usuário corrigiu: autenticação é por sessão",
                         evidencias=[{"tipo": "usuario", "ref": "conversa", "trecho": "não é JWT, é sessão com cookie"}],
                         afirmacao_correta="A API autentica com sessão em cookie httpOnly")
        # Reescritas pesadas também não devem passar (o modelo fraco reformula para escapar).
        for parafrase in ("A API usa JWT para autenticar usuários",
                          "A autenticação da API é feita por JWT",
                          "Autenticação por JWT na API",
                          "O login da API é via JWT"):
            with self.assertRaisesRegex(ErroCofre, "REFUTADA"):
                r.registrar_fato(self.cofre, self.agente, parafrase)
        with self.assertRaisesRegex(ErroCofre, "REFUTADA"):
            r.registrar_fato(self.cofre, self.agente, "A API usa JWT para autenticar usuários", forcar=True)
        # Fato genuinamente diferente sobre a mesma API NÃO é barrado como refutado.
        r.registrar_fato(self.cofre, self.agente, "A API tem rate limiting de cem requisições por minuto")
        antigo = self.cofre.por_id(res.id)
        self.assertEqual(antigo.status, "refutado")
        novo = self.cofre.resolver_ref(antigo.meta["substituido_por"])
        self.assertEqual(novo.status, "verificado")
        self.assertEqual(novo.meta["fonte"], "usuario")

    def test_duplicata_e_contradicao(self):
        r.registrar_fato(self.cofre, self.agente, "O banco é PostgreSQL 16", status="verificado",
                         evidencias=[self.ev_arquivo("image: postgres:16")])
        with self.assertRaisesRegex(ErroCofre, "parecido"):
            r.registrar_fato(self.cofre, self.agente, "O banco de dados de produção é PostgreSQL 16")
        with self.assertRaisesRegex(ErroCofre, "CONTRADIZ"):
            r.registrar_fato(self.cofre, self.agente, "O banco não é PostgreSQL 16")
        r.registrar_fato(self.cofre, self.agente, "O banco de dados de produção é PostgreSQL 16", forcar=True)

    def test_fato_do_usuario_so_usuario_refuta(self):
        res = r.registrar_fato(self.cofre, self.humano, "O cliente exige deploy na AWS", status="verificado",
                               evidencias=[{"tipo": "usuario", "ref": "conversa", "trecho": "o cliente exige AWS"}])
        with self.assertRaisesRegex(ErroCofre, "só o usuário"):
            r.atualizar_fato(self.cofre, self.agente, res.id, "refutar", motivo="Encontrei config da Vercel",
                             evidencias=[self.ev_arquivo("build: .")])
        r.atualizar_fato(self.cofre, self.agente, res.id, "contestar", motivo="Encontrei configuração de outro provedor")
        self.assertEqual(self.cofre.por_id(res.id).status, "contestado")

    def test_promover_e_politica_humano(self):
        res = r.registrar_fato(self.cofre, self.agente, "A API é construída pelo Dockerfile local")
        r.atualizar_fato(self.cofre, self.agente, res.id, "promover", evidencias=[self.ev_arquivo("build: .")])
        self.assertEqual(self.cofre.por_id(res.id).status, "verificado")
        cfg = self.vault / "00-Sistema" / "config.md"
        cfg.write_text(cfg.read_text(encoding="utf-8").replace("politica_verificacao: evidencia",
                                                               "politica_verificacao: humano"), encoding="utf-8")
        cofre2 = type(self.cofre)(self.vault)
        res2 = r.registrar_fato(cofre2, self.agente, "O banco roda a imagem oficial postgres", status="verificado",
                                evidencias=[self.ev_arquivo("image: postgres:16")])
        self.assertEqual(ler_nota(res2.caminho).meta["status"], "hipotese")

    def test_segredo_bloqueado(self):
        with self.assertRaisesRegex(ErroCofre, "credencial"):
            r.registrar_fato(self.cofre, self.agente, "O token do GitHub é ghp_" + "a" * 36)
        with self.assertRaisesRegex(ErroCofre, "credencial"):
            r.capturar(self.cofre, self.agente, "conexão postgres://admin:s3nh4forte@db.local/loja")
        # Segredo "fraco" (senha:/password=) também é barrado na escrita, não só na revisão.
        with self.assertRaisesRegex(ErroCofre, "credencial"):
            r.registrar_fato(self.cofre, self.agente, "Credencial do banco — senha: superSecreta123")
        with self.assertRaisesRegex(ErroCofre, "credencial"):
            r.capturar(self.cofre, self.agente, "anotação password=hunter2two no ambiente")

    def test_historico_preservado_ao_atualizar(self):
        res = r.registrar_fato(self.cofre, self.agente, "A fila de jobs usa BullMQ", contexto="Visto no README")
        r.atualizar_fato(self.cofre, self.agente, res.id, "contestar", motivo="Não achei bullmq no package.json")
        nota = ler_nota(res.caminho)
        self.assertIn("Visto no README", secao(nota.corpo, "Contexto"))
        historico = secao(nota.corpo, "Histórico")
        self.assertIn("criado como **hipotese**", historico)
        self.assertIn("**contestado**", historico)
        self.assertIn("[!warning] CONTESTADO", nota.corpo)


class TestDecisaoCheckpointMissao(CofreTeste):
    def test_decisao_aceita_exige_citacao(self):
        res = r.decisao(self.cofre, self.agente, titulo="Usar Drizzle ORM", decisao_txt="Drizzle em vez de Prisma",
                        status="aceita")
        self.assertEqual(ler_nota(res.caminho).meta["status"], "proposta")
        r.decisao(self.cofre, self.agente, "aceitar", ident=res.id, citacao_usuario="pode usar o drizzle")
        nota = self.cofre.por_id(res.id)
        self.assertEqual(nota.status, "aceita")
        self.assertIn("Drizzle em vez de Prisma", secao(nota.corpo, "Decisão"))

    def test_checkpoint_atualiza_estado_e_reaproveita_sessao(self):
        a = r.checkpoint(self.cofre, self.agente, "Configurei o docker-compose", feito=["db"],
                         proximos_passos=["migrations", "seed"], foco="Banco de dados", cwd=str(self.proj))
        b = r.checkpoint(self.cofre, self.agente, "Migrations prontas", proximos_passos=["seed"], cwd=str(self.proj))
        self.assertEqual(a.id, b.id)
        estado = self.cofre.estado("loja")
        self.assertIn("Banco de dados", secao(estado.corpo, "Foco atual"))
        self.assertEqual(secao(estado.corpo, "Próximos passos").strip(), "- [ ] seed")
        sessao = self.cofre.por_id(a.id)
        self.assertEqual(sessao.corpo.count("### "), 2)

    def test_checkpoint_por_sessao_externa(self):
        a = r.checkpoint(self.cofre, self.agente, "Etapa um concluída", cwd=str(self.proj), sessao_externa="ses_A")
        b = r.checkpoint(self.cofre, Autor_outro(), "Etapa dois concluída", cwd=str(self.proj), sessao_externa="ses_A")
        self.assertEqual(a.id, b.id)

    def test_missao(self):
        res = r.missao_criar(self.cofre, self.agente, "Lançar checkout", "Checkout em produção",
                             passos=["Stripe", "Webhook"], projetos=["loja"])
        r.missao_atualizar(self.cofre, self.agente, res.id, concluir_passo="webhook")
        self.assertIn("(1/2 passos)", r.missao_listar(self.cofre))


def Autor_outro():
    return r.Autor(nome="hermes")


if __name__ == "__main__":
    unittest.main()
