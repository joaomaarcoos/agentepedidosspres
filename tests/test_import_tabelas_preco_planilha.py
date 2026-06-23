import sys
import tempfile
import unittest
from pathlib import Path

from openpyxl import Workbook

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from execution.import_tabelas_preco_planilha import load_price_table


class ImportTabelasPrecoPlanilhaTests(unittest.TestCase):
    def test_load_price_table_uses_spreadsheet_name_and_price(self):
        wb = Workbook()
        ws = wb.active
        ws.append(["Produto", "Derivacao", "Desc.Prod./Derivacao - 205", "Preco Base"])
        ws.append(["SGPSSLAR", "05L", "SUCO DE LARANJA PASTEURIZADO GL 05L", 28.88])

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "tabela.xlsx"
            wb.save(path)

            items = load_price_table(path, "205")

        self.assertEqual(
            items[0],
            {
                "codigo_tabela": "205",
                "cod_produto": "SGPSSLAR",
                "nome_produto": "SUCO DE LARANJA PASTEURIZADO GL 05L",
                "variacao": "05L",
                "quantidade_minima": 1,
                "preco": 28.88,
                "desconto": 0,
                "synced_at": items[0]["synced_at"],
            },
        )


if __name__ == "__main__":
    unittest.main()
