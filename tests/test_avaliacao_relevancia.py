import unittest

from avaliacao_relevancia import avaliar, popular
from base import CofreTeste


class TestAvaliacaoRelevancia(CofreTeste):
    """Limites mínimos de qualidade da busca por relevância (detalhes: tests/avaliacao_relevancia.py)."""

    def test_qualidade_minima(self):
        rel = avaliar(self, popular(self))
        detalhes = "\n".join(rel["falhas"])
        self.assertGreaterEqual(rel["acerto"], 0.95, detalhes)
        self.assertGreaterEqual(rel["recall"], 0.9, detalhes)
        self.assertGreaterEqual(rel["silencio_sem_relacao"], 0.9, detalhes)
        self.assertLessEqual(rel["falsos_positivos"], 3, detalhes)


if __name__ == "__main__":
    unittest.main()
