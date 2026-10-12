"""Chamadas no estilo de modelos fracos: forma errada, intenção certa."""
import io
import json
import os
import random
import unittest

from base import CofreTeste
from cofre.mcp import Servidor
from cofre.vault import Cofre


class TestRobustez(CofreTeste):
    def setUp(self):
        super().setUp()
        os.environ["COFRE_CWD"] = str(self.proj)
        self.srv = Servidor(saida=io.BytesIO(), entrada=io.BytesIO())

    def chamar(self, nome, args):
        r = self.srv.chamar(nome, args)
        return r["isError"], r["content"][0]["text"]

    def test_json_em_string_chaves_com_acento_e_enum_maiusculo(self):
        args = json.dumps({
            "Afirmação": "O banco é PostgreSQL 16", "Status": "Verificado",
            "evidence": [{"type": "file", "path": str(self.proj / "docker-compose.yml") + ":3",
                          "excerpt": "image: postgres:16"}],
        })
        erro, texto = self.chamar("cofre_registrar_fato", args)
        self.assertFalse(erro, texto)
        self.assertIn("[VERIFICADO]", texto)

    def test_evidencia_como_texto_livre(self):
        erro, texto = self.chamar("cofre_registrar_fato", {
            "afirmacao": "A API é construída pelo Dockerfile local", "status": "verified",
            "evidencias": f"arquivo: {self.proj / 'docker-compose.yml'} -> build: ."})
        self.assertFalse(erro, texto)
        self.assertIn("[VERIFICADO]", texto)

    def test_texto_no_lugar_do_id_recebe_sugestao(self):
        _, texto = self.chamar("cofre_registrar_fato", {"afirmacao": "A fila de jobs usa BullMQ com Redis"})
        ident = texto.split(":")[1].split()[0]
        erro, texto = self.chamar("cofre_atualizar_fato", {
            "id": "a fila de jobs usa bullmq", "acao": "contestar", "motivo": "não achei bullmq no package.json"})
        self.assertTrue(erro)
        self.assertIn(ident, texto)
        erro, texto = self.chamar("cofre_atualizar_fato", {
            "id": ident.lower().replace("-", ""), "acao": "contestado", "motivo": "não achei bullmq no package.json"})
        self.assertFalse(erro, texto)
        self.assertEqual(Cofre(self.vault).por_id(ident).status, "contestado")

    def test_id_com_um_caractere_errado_sugere_o_certo(self):
        _, texto = self.chamar("cofre_registrar_fato", {"afirmacao": "Os testes rodam com Vitest no projeto"})
        ident = texto.split(":")[1].split()[0]
        errado = ident[:-1] + ("0" if ident[-1] != "0" else "1")
        erro, texto = self.chamar("cofre_ler", {"id": errado})
        self.assertIn(ident, texto)

    def test_parametro_obrigatorio_faltando_mostra_exemplo(self):
        erro, texto = self.chamar("cofre_registrar_fato", {"status": "hipotese"})
        self.assertTrue(erro)
        self.assertIn("afirmacao", texto)
        self.assertIn("Exemplo", texto)

    def test_repetir_a_mesma_chamada_errada_dispara_pare(self):
        args = {"afirmacao": "O banco é MySQL 8", "status": "verificado",
                "evidencias": [{"tipo": "arquivo", "ref": str(self.proj / "docker-compose.yml"), "trecho": "mysql:8"}]}
        textos = [self.chamar("cofre_registrar_fato", args)[1] for _ in range(3)]
        self.assertNotIn("PARE", textos[0])
        self.assertIn("PARE", textos[2])

    def test_nome_de_ferramenta_sem_prefixo_e_listas_em_texto(self):
        erro, texto = self.chamar("checkpoint", {
            "summary": "Configurei o banco de dados", "next_steps": "migrations\nseed", "tags": "a, b"})
        self.assertFalse(erro, texto)
        estado = Cofre(self.vault).estado("loja")
        self.assertIn("- [ ] seed", estado.corpo)

    def test_projeto_com_caixa_diferente(self):
        erro, texto = self.chamar("cofre_registrar_fato", {"afirmacao": "O deploy é feito na Vercel", "projeto": "LOJA"})
        self.assertFalse(erro, texto)
        self.assertIn("projeto loja", texto)

    def test_argumentos_lixo_nao_derrubam(self):
        for lixo in (None, "", "não é json", 42, ["lista"]):
            erro, texto = self.chamar("cofre_buscar", lixo)
            self.assertTrue(erro)
            self.assertIn("consulta", texto)

    def test_campo_string_recebendo_lista_ou_dict_nao_estoura(self):
        # Modelo manda um dict/lista num campo que é string (acao): vira erro limpo, não AttributeError.
        for valor in ({"a": 1}, [{"x": 1}], [{"x": 1}, {"y": 2}], 42):
            erro, texto = self.chamar("cofre_missao", {"acao": valor})
            self.assertNotIn("Erro interno", texto, f"{valor!r} -> {texto}")

    def test_fuzz_nenhuma_ferramenta_estoura(self):
        from cofre.ferramentas import POR_NOME
        valores = [None, "", 0, 1.5, True, [], {}, [None], {"a": {"b": 1}}, [{"x": 1}],
                   "x" * 5000, "../../etc/passwd", "F-7K3PQ", "a,b,c", "Verificado", 10**20,
                   {"tipo": "arquivo", "ref": "x", "trecho": "y"}, "https://u:p@h/x"]
        chaves = ["afirmacao", "status", "acao", "id", "consulta", "titulo", "objetivo", "evidencias",
                  "tarefas", "url", "quando_usar", "spec", "tarefa", "texto", "projeto", "cwd"]
        rnd = random.Random(7)
        for nome in POR_NOME:
            for _ in range(60):
                args = {k: rnd.choice(valores) for k in rnd.sample(chaves, rnd.randint(0, 4))}
                r = self.srv.chamar(nome, args)  # não pode lançar
                self.assertIn("content", r)
                self.assertIsInstance(r["content"][0]["text"], str)
                self.assertNotIn("Erro interno do cofre: AttributeError", r["content"][0]["text"])
        Cofre(self.vault).notas(recarregar=True)  # vault não corrompeu


if __name__ == "__main__":
    unittest.main()
