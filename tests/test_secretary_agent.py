import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "execution"))

import clic_vendas_cli
import secretary_agent


class SecretaryAgentTests(unittest.TestCase):
    def test_protocol_has_secretary_prefix(self):
        self.assertRegex(secretary_agent._new_protocol(), r"^MSE-\d{6}-[A-F0-9]{6}$")

    def test_customer_search_removes_customer_prefix(self):
        customers = [
            {"name": "Mercado Central", "city": "Ribeirao Preto", "code": "10", "document": "1234"},
            {"name": "Padaria Avenida", "city": "Sertaozinho", "code": "20", "document": "5678"},
        ]
        matches = secretary_agent._search_customers(customers, "cliente Mercado Central")
        self.assertEqual(matches[0]["code"], "10")

    def test_sales_reconciler_adds_official_product_code(self):
        catalog = [
            {"cod_produto": "A", "nome_produto": "GARRAFA LARANJA", "variacao": "900", "preco": 10},
            {"cod_produto": "B", "nome_produto": "GARRAFA LARANJA", "variacao": "300", "preco": 5},
        ]
        reconciled = secretary_agent._reconcile_catalog_resolution(
            {
                "itens": [
                    {
                        "produto": "laranja",
                        "formato": "garrafa",
                        "tamanho": "900ml",
                        "quantidade": 2,
                    }
                ]
            },
            catalog,
        )
        item = reconciled["itens"][0]
        self.assertEqual(item["status"], "encontrado")
        self.assertEqual(item["cod_produto"], "A")
        self.assertEqual(item["subtotal"], 20)

    def test_sales_reconciler_rejects_missing_derivation(self):
        catalog = [
            {"cod_produto": "A", "nome_produto": "GARRAFA LARANJA", "variacao": "900", "preco": 10},
        ]
        reconciled = secretary_agent._reconcile_catalog_resolution(
            {
                "itens": [
                    {
                        "produto": "laranja",
                        "formato": "garrafa",
                        "tamanho": "300ml",
                        "quantidade": 2,
                    }
                ]
            },
            catalog,
        )
        self.assertEqual(reconciled["itens"][0]["status"], "nao_encontrado")

    def test_secretary_reply_exposes_official_code(self):
        reply = secretary_agent._secretary_resolution_reply(
            {
                "itens": [
                    {
                        "status": "encontrado",
                        "cod_produto": "SGRSSLAR",
                        "nome_catalogo": "SUCO GARRAFA LARANJA",
                        "produto": "Laranja",
                        "formato": "garrafa",
                        "tamanho": "900ml",
                        "quantidade": 10,
                        "unidade": "UN",
                        "preco_unitario": 9.17,
                    }
                ]
            }
        )
        self.assertIn("SGRSSLAR", reply)
        self.assertIn("SUCO GARRAFA LARANJA", reply)

    def test_reconciliation_prefers_order_number(self):
        number_origin = {"id": "by-number", "protocol": "MSE-260615-AAAAAA"}
        protocol_origin = {"id": "by-protocol", "protocol": "MSE-260615-BBBBBB"}
        result = clic_vendas_cli._secretary_origin(
            {
                "numPed": 123,
                "observacao": "Origem: Marcela Secretaria | Ref: MSE-260615-BBBBBB",
            },
            {"123": number_origin},
            {"MSE-260615-BBBBBB": protocol_origin},
        )
        self.assertEqual(result["id"], "by-number")

    def test_reconciliation_uses_protocol_fallback(self):
        origin = {"id": "by-protocol", "protocol": "MSE-260615-BBBBBB"}
        result = clic_vendas_cli._secretary_origin(
            {
                "numPed": 456,
                "observacao": "Origem: Marcela Secretaria | Ref: MSE-260615-BBBBBB",
            },
            {},
            {"MSE-260615-BBBBBB": origin},
        )
        self.assertEqual(result["id"], "by-protocol")

    def test_forecast_supports_semester_boundaries(self):
        self.assertEqual(clic_vendas_cli._period_for_month(1, 2), 1)
        self.assertEqual(clic_vendas_cli._period_for_month(6, 2), 1)
        self.assertEqual(clic_vendas_cli._period_for_month(7, 2), 2)
        self.assertEqual(clic_vendas_cli._period_for_month(12, 2), 2)

    def test_forecast_uses_semester_labels(self):
        self.assertEqual(clic_vendas_cli._period_label(1, 2), "1o semestre")
        self.assertEqual(clic_vendas_cli._period_label(2, 2), "2o semestre")


if __name__ == "__main__":
    unittest.main()
