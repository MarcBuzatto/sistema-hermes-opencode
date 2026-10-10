import unittest

from base import CofreTeste
from cofre import skills
from cofre.revisar import revisar


class TestSkills(CofreTeste):
    def criar(self, rel, frontmatter, corpo="Passos.\n"):
        pasta = self.vault / "60-Skills" / rel
        pasta.mkdir(parents=True, exist_ok=True)
        (pasta / "SKILL.md").write_text(f"---\n{frontmatter}\n---\n{corpo}", encoding="utf-8")
        return pasta

    def test_listar_com_e_sem_categoria(self):
        self.criar("nextjs-cache", "name: nextjs-cache\ndescription: Cache do Next.js")
        self.criar("devops/deploy-vps", "name: deploy-vps\ndescription: Deploy em VPS\nmetadata:\n  hermes:\n    tags: [devops]")
        por_id = {s.id: s for s in skills.listar(self.vault)}
        self.assertEqual(set(por_id), {"nextjs-cache", "deploy-vps"})
        self.assertEqual(por_id["deploy-vps"].categoria, "devops")
        self.assertIsNone(por_id["nextjs-cache"].categoria)
        self.assertEqual(self.cofre.por_tipo("fato"), [], "skills não são indexadas como notas")

    def test_verificar(self):
        self.criar("sem-descricao", "name: sem-descricao")
        self.criar("a/repetida", "name: repetida\ndescription: x")
        self.criar("b/repetida", "name: repetida\ndescription: y")
        self.criar("nome-errado", "name: outro\ndescription: z")
        self.criar("vazada", "name: vazada\ndescription: w", corpo="token ghp_" + "b" * 36 + "\n")
        texto = " | ".join(f"{g}:{n}:{m}" for g, n, m in skills.verificar(self.vault))
        self.assertIn("erro:skill:sem-descricao", texto)
        self.assertIn("erro:skill:repetida", texto)
        self.assertIn("alerta:skill:nome-errado", texto)
        self.assertIn("erro:skill:vazada", texto)
        self.assertTrue(any(a.nota == "skill:vazada" for a in revisar(self.cofre)))

    def test_sincronizar_preserva_skill_do_usuario(self):
        self.criar("cat/nextjs-cache", "name: nextjs-cache\ndescription: Cache")
        destino = self.tmp / "oc-skills"
        (destino / "minha").mkdir(parents=True)
        (destino / "minha" / "SKILL.md").write_text("x", encoding="utf-8")
        copiadas, removidas, avisos = skills.sincronizar(self.vault, destino)
        self.assertEqual(copiadas, ["nextjs-cache"])
        self.assertTrue((destino / "nextjs-cache" / "SKILL.md").exists())
        (self.vault / "60-Skills" / "cat" / "nextjs-cache" / "SKILL.md").unlink()
        _, removidas, _ = skills.sincronizar(self.vault, destino)
        self.assertEqual(removidas, ["nextjs-cache"])
        self.assertTrue((destino / "minha" / "SKILL.md").exists())


if __name__ == "__main__":
    unittest.main()
