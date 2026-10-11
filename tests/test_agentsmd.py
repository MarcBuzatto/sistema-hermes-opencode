import unittest

from base import CofreTeste
from cofre import agentsmd, relevancia

AGENTS = """# Minhas instruções

Sou dev freelancer full-stack.

## Regras gerais
- Responder em PT-BR.
- Não usar emojis.

## Git
- Commits pequenos, mensagem no imperativo.

## React e Next.js
""" + "\n".join(f"- regra {i} de componentes React, server components e cache do Next.js" for i in range(18)) + """
```tsx
export default async function Page() {}
```

## Laravel
""" + "\n".join(f"- regra {i} de filas, jobs e Eloquent no Laravel" for i in range(16)) + """

## Pentest
""" + "\n".join(f"- item {i}: confirmar escopo e autorização por escrito antes do pentest" for i in range(14)) + "\n"


class TestAgentsMd(CofreTeste):
    def setUp(self):
        super().setUp()
        self.arq = self.tmp / "AGENTS.md"
        self.arq.write_text(AGENTS, encoding="utf-8")

    def test_analisar_separa_nucleo_e_assuntos(self):
        saida = agentsmd.analisar(self.arq)
        self.assertIn("[núcleo] Regras gerais", saida)
        self.assertIn("[núcleo] Git", saida)
        self.assertIn("[vault ] React e Next.js", saida)
        self.assertIn("[vault ] Laravel", saida)

    def test_dividir_simula_e_depois_aplica_sem_tocar_no_original(self):
        saida = agentsmd.dividir(self.cofre, self.arq)
        self.assertIn("Nada foi gravado", saida)
        self.assertFalse((self.vault / agentsmd.PASTA_INSTRUCOES).exists())

        saida = agentsmd.dividir(self.cofre, self.arq, aplicar=True, manter=["Pentest"])
        pasta = self.vault / agentsmd.PASTA_INSTRUCOES
        self.assertEqual(sorted(p.stem for p in pasta.glob("*.md")), ["laravel", "react-e-next-js"])
        self.assertEqual(self.arq.read_text(encoding="utf-8"), AGENTS)
        proposta = next((self.vault / "00-Sistema" / "Relatorios").glob("AGENTS-enxuto*.md")).read_text(encoding="utf-8")
        self.assertIn("## Regras gerais", proposta)
        self.assertIn("## Pentest", proposta, "--manter deixa a seção no núcleo")
        self.assertIn("- React e Next.js", proposta)
        self.assertNotIn("regra 3 de componentes", proposta)
        self.assertLess(len(proposta), len(AGENTS) / 2)

        bloco, _ = relevancia.relevante(type(self.cofre)(self.vault), "o cache do next está servindo página velha")
        self.assertIn("instrução sua: React e Next.js", bloco)
        self.assertIn("Já existiam", agentsmd.dividir(self.cofre, self.arq, aplicar=True))


if __name__ == "__main__":
    unittest.main()
