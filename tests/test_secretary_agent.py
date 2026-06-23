import sys
import unittest
from pathlib import Path
from unittest.mock import patch

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

    def test_secretary_allowed_phone_accepts_country_code_variation(self):
        with patch.dict("os.environ", {"SECRETARY_ALLOWED_PHONES": "16999999999"}):
            self.assertTrue(secretary_agent._is_secretary_phone_allowed("5516999999999"))

    def test_secretary_ignores_non_allowed_phone_before_db(self):
        with patch.dict("os.environ", {"SECRETARY_ALLOWED_PHONES": "5516999999999"}), patch.object(
            secretary_agent, "_db"
        ) as db:
            result = secretary_agent.process_secretary_message(
                phone="5516888888888",
                text="pedido para Mercado Central",
                instance_name="secretaria-01",
            )
        self.assertEqual(result["action"], "secretary_phone_not_allowed")
        self.assertFalse(result["should_reply"])
        db.assert_not_called()

    def test_secretary_default_allows_only_eliezer_phone(self):
        with patch.dict("os.environ", {}, clear=True):
            self.assertTrue(secretary_agent._is_secretary_phone_allowed("5516991377335"))
            self.assertTrue(secretary_agent._is_secretary_phone_allowed("16991377335"))
            self.assertFalse(secretary_agent._is_secretary_phone_allowed("5516888888888"))

    def test_build_clic_payload_omits_auto_fields(self):
        payload = secretary_agent._build_clic_order_payload(
            {
                "customer_document": "05482507000142",
                "sale_type_code": "9010P",
                "price_table_code": "201P",
                "items_json": [
                    {
                        "cod_produto": "SGRSSLAR",
                        "derivacao": "1L7",
                        "quantidade": 60,
                        "preco_unitario": 10.78,
                    }
                ],
            }
        )
        self.assertEqual(
            payload,
            [
                {
                    "numeroDocumentoCliente": "05482507000142",
                    "numeroDocumentoRepresentante": "34501704810",
                    "codigoTipoVenda": "9010P",
                    "itens": [
                        {
                            "codigoProduto": "SGRSSLAR",
                            "codigoVariacao": "1L7",
                            "quantidade": 60.0,
                            "precoVenda": 10.78,
                            "codigoTabelaPreco": "201P",
                            "percentualDesconto": 0,
                            "percentualAcrescimo": 0,
                        }
                    ],
                }
            ],
        )
        order_payload = payload[0]
        for forbidden in (
            "codigoFormaPagamento",
            "codigoCondicaoPagamento",
            "tipoFrete",
            "valorFrete",
            "situacao",
            "numeroExternoPedido",
            "observacao",
        ):
            self.assertNotIn(forbidden, order_payload)

    def test_sale_type_code_from_text(self):
        self.assertEqual(secretary_agent._sale_type_code_from_text("pedido pdv"), "9010P")
        self.assertEqual(secretary_agent._sale_type_code_from_text("bonificacao acordo"), "BONIF4")
        self.assertEqual(secretary_agent._sale_type_code_from_text("normal com nota"), "9010O")

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
