import os
import unittest

from base import CofreTeste
from cofre.projetos import normalizar_caminho, normalizar_repo, resolver_projeto
from cofre.registrar import projeto_vincular


class TestNormalizacao(unittest.TestCase):
    def test_windows_e_wsl_equivalentes(self):
        self.assertEqual(normalizar_caminho("C:\\Users\\Ana\\dev\\loja\\"), "c:/users/ana/dev/loja")
        self.assertEqual(normalizar_caminho("/mnt/c/Users/Ana/dev/loja"), "c:/users/ana/dev/loja")
        self.assertEqual(normalizar_caminho("/home/ana/Dev"), "/home/ana/Dev")

    def test_repos(self):
        esperado = "github.com/org/repo"
        for url in (
            "https://github.com/org/repo.git",
            "git@github.com:org/repo.git",
            "ssh://git@github.com:22/org/repo",
            "github.com/org/repo",
            "https://user@github.com/Org/Repo/",
        ):
            self.assertEqual(normalizar_repo(url), esperado, url)


class TestResolucao(CofreTeste):
    def test_por_caminho_e_subpasta(self):
        sub = self.proj / "src" / "app"
        sub.mkdir(parents=True)
        self.assertEqual(resolver_projeto(self.cofre, str(sub)).nome, "loja")
        self.assertIsNone(resolver_projeto(self.cofre, str(self.tmp)))

    @unittest.skipIf(os.name == "nt", "symlink exige privilégio no Windows")
    def test_projeto_aberto_por_symlink(self):
        # macOS: o projeto é vinculado como /var/... e o os.getcwd() devolve /private/var/...;
        # o mesmo vale para qualquer symlink.
        from cofre.registrar import projeto_criar
        real = self.tmp / "real" / "alfa"
        (real / "src").mkdir(parents=True)
        atalho = self.tmp / "atalho-alfa"
        atalho.symlink_to(real, target_is_directory=True)
        projeto_criar(self.cofre, self.humano, "alfa", caminhos=[str(atalho)])
        self.cofre.invalidar()
        self.assertEqual(resolver_projeto(self.cofre, str(real.resolve() / "src")).nome, "alfa")
        self.assertEqual(resolver_projeto(self.cofre, str(atalho / "src")).nome, "alfa")

    def test_caminho_mais_especifico_vence(self):
        from cofre.registrar import projeto_criar
        interno = self.proj / "pacotes" / "admin"
        interno.mkdir(parents=True)
        projeto_criar(self.cofre, self.humano, "loja-admin", caminhos=[str(interno)])
        self.assertEqual(resolver_projeto(self.cofre, str(interno / "x")).nome, "loja-admin")
        self.assertEqual(resolver_projeto(self.cofre, str(self.proj / "outro")).nome, "loja")

    def test_vincular_e_variavel(self):
        outro = self.tmp / "outro"
        outro.mkdir()
        projeto_vincular(self.cofre, self.humano, "loja", caminho=str(outro))
        self.assertEqual(resolver_projeto(self.cofre, str(outro)).nome, "loja")
        import os
        os.environ["COFRE_PROJETO"] = "loja"
        self.assertEqual(resolver_projeto(self.cofre, "/qualquer").nome, "loja")


if __name__ == "__main__":
    unittest.main()
