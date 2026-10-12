from __future__ import annotations

import io
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from cofre.cli import MARCAS_AGENTE, main as cofre_main  # noqa: E402
from cofre.registrar import Autor, projeto_criar  # noqa: E402
from cofre.vault import Cofre  # noqa: E402


class CofreTeste(unittest.TestCase):
    """Cria um vault temporário a partir do template e um diretório de projeto com arquivos reais."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="cofre-teste-"))
        self.env_antigo = dict(os.environ)
        for var in (*MARCAS_AGENTE, "COFRE_PROJETO", "COFRE_CWD"):
            os.environ.pop(var, None)
        os.environ["XDG_CONFIG_HOME"] = str(self.tmp / "cfg")
        os.environ["APPDATA"] = str(self.tmp / "cfg")
        os.environ["COFRE_CACHE"] = str(self.tmp / "cache")
        self.vault = self.tmp / "vault"
        os.environ["COFRE_VAULT"] = str(self.vault)
        from contextlib import redirect_stdout
        with redirect_stdout(io.StringIO()):
            cofre_main(["init", str(self.vault)])
        self.proj = self.tmp / "proj"
        self.proj.mkdir()
        (self.proj / "docker-compose.yml").write_text(
            "services:\n  db:\n    image: postgres:16\n  api:\n    build: .\n", encoding="utf-8")
        self.cofre = Cofre(self.vault)
        self.humano = Autor(humano=True)
        self.agente = Autor(nome="opencode", modelo="glm-4.6")
        projeto_criar(self.cofre, self.humano, "loja", nome="Loja", caminhos=[str(self.proj)])

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self.env_antigo)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def ev_arquivo(self, trecho: str, arquivo: str = "docker-compose.yml") -> dict:
        return {"tipo": "arquivo", "ref": str(self.proj / arquivo), "trecho": trecho}
