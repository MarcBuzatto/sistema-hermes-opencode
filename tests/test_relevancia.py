import os
import time
import unittest

from base import CofreTeste
from cofre import contexto, registrar as r, relevancia


class TestRelevancia(CofreTeste):
    def nota(self, rel, texto):
        caminho = self.vault / rel
        caminho.parent.mkdir(parents=True, exist_ok=True)
        caminho.write_text(texto, encoding="utf-8")
        return caminho

    def popular(self):
        self.nota("60-Skills/seguranca/pentest-web/SKILL.md",
                  "---\nname: pentest-web\ndescription: Metodologia de pentest em aplicações web (OWASP). Use em testes de intrusão autorizados.\n---\n# Pentest web\nEscopo, reconhecimento, testes.\n")
        self.nota("60-Skills/seguranca/pentest-web/references/owasp.md", "# Checklist OWASP\n- Testar IDOR nas rotas autenticadas\n")
        self.nota("30-Conhecimento/Seguranca/Burp Suite.md", "# Burp Suite\nProxy para pentest web; Repeater e Intruder.\n")
        self.nota("30-Conhecimento/Frontend/Tailwind.md", "# Tailwind CSS\nDark mode via classe no tailwind.config.ts.\n")
        r.registrar_fato(self.cofre, self.humano, "O cliente Acme autoriza testes de intrusão só em staging",
                         status="verificado", projeto="global",
                         evidencias=[{"tipo": "usuario", "ref": "conversa", "trecho": "pentest só em staging"}])

    def test_acha_o_assunto_mesmo_com_erro_de_digitacao(self):
        self.popular()
        for consulta in ("estou falando de penteast", "vamos fazer pentest", "petnest no app"):
            bloco, _ = relevancia.relevante(self.cofre, consulta)
            self.assertIn("pentest-web", bloco, consulta)
        bloco, _ = relevancia.relevante(self.cofre, "bora fazer um teste de intrusão no cliente")
        self.assertIn("[VERIFICADO]", bloco)

    def test_nao_injeta_nada_sem_relacao(self):
        self.popular()
        for consulta in ("oi tudo bem?", "vamos revisar o docker compose", "ok valeu"):
            self.assertEqual(relevancia.relevante(self.cofre, consulta)[0], "", consulta)

    def test_referencia_de_skill_e_nota_livre(self):
        self.popular()
        bloco, ids = relevancia.relevante(self.cofre, "preciso testar IDOR com o burp")
        self.assertIn("Burp Suite", bloco)
        self.assertIn("referência da skill `pentest-web`", bloco)
        self.assertTrue(ids)
        bloco2, _ = relevancia.relevante(self.cofre, "preciso testar IDOR com o burp", excluir=ids)
        self.assertEqual(bloco2, "", "itens já mostrados não se repetem")

    def test_indice_em_cache_atualiza_arquivo_alterado(self):
        self.popular()
        antigo = self.vault / ".cofre" / "indice.json"
        antigo.parent.mkdir(parents=True, exist_ok=True)
        antigo.write_text("{}", encoding="utf-8")
        relevancia.carregar_indice(self.vault)
        self.assertTrue(relevancia.arquivo_indice(self.vault).exists())
        self.assertFalse(relevancia.arquivo_indice(self.vault).is_relative_to(self.vault), "índice fora do vault")
        self.assertFalse(antigo.exists(), "índice antigo dentro do vault é apagado")
        nota = self.nota("30-Conhecimento/Frontend/Tailwind.md", "# Tailwind CSS\nAgora fala de kubernetes e helm.\n")
        futuro = time.time() + 5
        os.utime(nota, (futuro, futuro))
        relevancia._MEMORIA.clear()  # edição externa: num processo aberto aparece em até MEMORIA_TTL s
        self.assertIn("Tailwind", relevancia.relevante(self.cofre, "deploy com kubernetes e helm")[0])

    def test_escrita_do_proprio_processo_invalida_o_cache(self):
        self.popular()
        self.assertEqual(relevancia.relevante(self.cofre, "migração para kubernetes")[0], "")
        r.registrar_fato(self.cofre, self.humano, "O cluster de produção roda em kubernetes 1.30", projeto="global")
        self.assertIn("kubernetes", relevancia.relevante(self.cofre, "migração para kubernetes")[0])

    def test_ignora_sistema_modelos_e_exemplos(self):
        docs = relevancia.carregar_indice(self.vault)
        self.assertFalse(any(k.startswith("00-Sistema/") for k in docs))
        self.assertFalse(any(k.endswith("LEIA-ME.md") for k in docs))

    def test_buscar_e_ler_por_caminho(self):
        self.popular()
        saida = contexto.buscar(self.cofre, "burp")
        self.assertIn("30-Conhecimento/Seguranca/Burp Suite.md", saida)
        self.assertIn("Proxy para pentest", contexto.ler(self.cofre, "30-Conhecimento/Seguranca/Burp Suite.md"))
        self.assertIn("não encontrada", contexto.ler(self.cofre, "../../etc/passwd"))

    def test_desligavel_pela_config(self):
        self.popular()
        cfg = self.vault / "00-Sistema" / "config.md"
        cfg.write_text(cfg.read_text(encoding="utf-8").replace("relevancia_ativa: true", "relevancia_ativa: false"),
                       encoding="utf-8")
        self.assertEqual(relevancia.relevante(type(self.cofre)(self.vault), "pentest")[0], "")


if __name__ == "__main__":
    unittest.main()
