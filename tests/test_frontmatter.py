import unittest

from base import RAIZ  # noqa: F401
from cofre import frontmatter


class TestFrontmatter(unittest.TestCase):
    def test_ida_e_volta(self):
        meta = {
            "tipo": "fato",
            "afirmacao": "A porta é: 3000 # padrão",
            "status": "verificado",
            "projeto": "[[loja]]",
            "evidencia": ['arquivo :: src/a.ts:3 :: const x = "y"', "comando :: npm ls | grep react :: react@19"],
            "vazia": [],
            "nada": None,
            "numero": 42,
            "texto_numerico": "042",
            "data": "2026-10-10",
            "booleano": True,
            "reservada": "true",
        }
        texto = frontmatter.compor(meta, "# Corpo\n")
        lido, corpo = frontmatter.separar(texto)
        self.assertEqual(lido, meta)
        self.assertEqual(corpo, "# Corpo\n")

    def test_formatos_do_obsidian(self):
        texto = (
            "---\n"
            "tags: [stack, 'banco de dados', \"[[link]]\"]\n"
            "aliases:\n  - F-1\n  - \"F 2\"\n"
            "titulo: C# e Rust # comentário\n"
            "vazio:\n"
            "---\ncorpo"
        )
        meta, corpo = frontmatter.separar(texto)
        self.assertEqual(meta["tags"], ["stack", "banco de dados", "[[link]]"])
        self.assertEqual(meta["aliases"], ["F-1", "F 2"])
        self.assertEqual(meta["titulo"], "C# e Rust")
        self.assertIsNone(meta["vazio"])
        self.assertEqual(corpo, "corpo")

    def test_sem_frontmatter_e_crlf(self):
        self.assertEqual(frontmatter.separar("# só corpo"), ({}, "# só corpo"))
        meta, corpo = frontmatter.separar("---\r\ntipo: fato\r\n---\r\nx\r\n")
        self.assertEqual(meta, {"tipo": "fato"})
        self.assertEqual(corpo, "x\n")


if __name__ == "__main__":
    unittest.main()
