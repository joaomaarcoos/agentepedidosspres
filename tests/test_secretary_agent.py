import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "execution"))

import clic_vendas_cli
import secretary_agent


class _FakeQuery:
    def __init__(self, data):
        self._data = data

    def select(self, *_args, **_kwargs):
        return self

    def eq(self, *_args, **_kwargs):
        return self

    def in_(self, *_args, **_kwargs):
        return self

    def order(self, *_args, **_kwargs):
        return self

    def limit(self, *_args, **_kwargs):
        return self

    def execute(self):
        return type("Result", (), {"data": self._data})()


class _FakeDb:
    def __init__(self, tables):
        self.tables = tables

    def table(self, name):
        return _FakeQuery(self.tables.get(name, []))


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

    def test_allowed_eliezer_phone_uses_profile_fallback(self):
        db = _FakeDb(
            {
                "representatives": [
                    {"cod_rep": 52, "name": "ELIEZER", "active": True, "whatsapp_number": ""},
                ],
                "system_settings": [
                    {
                        "value": {
                            "52": {
                                "cod_rep": 52,
                                "documento": "34501704810",
                                "nome": "ELIEZER GONZAGA DOS REIS",
                            }
                        }
                    }
                ],
            }
        )
        rep = secretary_agent._representative(db, "5516991377335")
        self.assertIsNotNone(rep)
        self.assertEqual(rep["cod_rep"], 52)
        self.assertEqual(rep["name"], "ELIEZER GONZAGA DOS REIS")

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

    def test_later_found_product_replaces_pending_equivalent(self):
        resolution = {
            "itens": [
                {
                    "status": "nao_encontrado",
                    "produto": "laranja natural",
                    "formato": "galao",
                    "texto_original": "01 galao laranja natural",
                },
                {
                    "status": "encontrado",
                    "produto": "Galao Laranja Pet",
                    "nome_catalogo": "SUCO GALAO LARANJA PET",
                    "formato": "galao",
                    "tamanho": "5L",
                    "quantidade": 1,
                    "cod_produto": "SGPSSLAR",
                    "preco_unitario": 28.88,
                },
            ]
        }
        cleaned = secretary_agent._drop_resolved_pending_items(resolution)
        self.assertEqual(len(cleaned["itens"]), 1)
        self.assertEqual(cleaned["itens"][0]["cod_produto"], "SGPSSLAR")

    def test_short_size_reply_replaces_generic_pending_equivalent(self):
        resolution = {
            "itens": [
                {
                    "status": "encontrado",
                    "produto": "Galao Laranja Pet",
                    "nome_catalogo": "SUCO GALAO LARANJA PET",
                    "formato": "galao",
                    "tamanho": "5L",
                    "quantidade": 1,
                    "cod_produto": "SGPSSLAR",
                    "preco_unitario": 28.88,
                },
                {
                    "status": "nao_encontrado",
                    "produto": "",
                    "formato": "galao",
                    "tamanho": "5L",
                    "texto_original": "Galao 5l",
                },
            ]
        }
        cleaned = secretary_agent._drop_resolved_pending_items(resolution)
        self.assertEqual(len(cleaned["itens"]), 1)
        self.assertEqual(cleaned["itens"][0]["cod_produto"], "SGPSSLAR")

    def test_customer_code_during_items_asks_before_switching_order(self):
        current_customer = {"code": "1233", "name": "Cliente Atual", "document": "1", "price_table_code": "205"}
        new_customer = {"code": "16069", "name": "IGOR MIRANDA BORGES", "document": "42423525818", "price_table_code": "205"}
        saved_states = []

        with patch.object(secretary_agent, "_db", return_value=object()), patch.object(
            secretary_agent, "_representative", return_value={"cod_rep": 52, "name": "ELIEZER"}
        ), patch.object(
            secretary_agent,
            "_conversation",
            return_value={
                "id": "conv-1",
                "state_json": {
                    "customer": current_customer,
                    "items": [{"cod_produto": "A"}],
                    "catalog_resolution": {"itens": []},
                },
            },
        ), patch.object(secretary_agent, "_add_message", return_value=True), patch.object(
            secretary_agent, "_portfolio_customers", return_value=[current_customer, new_customer]
        ), patch.object(secretary_agent, "_save_state", side_effect=lambda _db, _id, state: saved_states.append(state)), patch.object(
            secretary_agent, "_resolve_products_with_sales_subagent"
        ) as resolve_products:
            result = secretary_agent.process_secretary_message("5516991377335", "16069", "secretaria")

        self.assertEqual(result["action"], "secretary_confirm_customer_change")
        self.assertIn("IGOR MIRANDA BORGES", result["reply"])
        self.assertEqual(saved_states[-1]["pending_action"]["type"], "change_customer")
        resolve_products.assert_not_called()

    def test_confirm_pending_customer_change_resets_items_and_keeps_new_customer(self):
        current_customer = {"code": "1233", "name": "Cliente Atual", "document": "1", "price_table_code": "205"}
        new_customer = {"code": "16069", "name": "IGOR MIRANDA BORGES", "document": "42423525818", "price_table_code": "205"}
        saved_states = []

        with patch.object(secretary_agent, "_db", return_value=object()), patch.object(
            secretary_agent, "_representative", return_value={"cod_rep": 52, "name": "ELIEZER"}
        ), patch.object(
            secretary_agent,
            "_conversation",
            return_value={
                "id": "conv-1",
                "state_json": {
                    "customer": current_customer,
                    "items": [{"cod_produto": "A"}],
                    "sale_type_code": "9010P",
                    "pending_action": {"type": "change_customer", "customer": new_customer},
                },
            },
        ), patch.object(secretary_agent, "_add_message", return_value=True), patch.object(
            secretary_agent, "_save_state", side_effect=lambda _db, _id, state: saved_states.append(state)
        ):
            result = secretary_agent.process_secretary_message("5516991377335", "confirmo", "secretaria")

        self.assertEqual(result["action"], "secretary_customer_changed")
        self.assertEqual(saved_states[-1]["customer"]["code"], "16069")
        self.assertEqual(saved_states[-1]["sale_type_code"], "9010P")
        self.assertNotIn("items", saved_states[-1])
        self.assertNotIn("pending_action", saved_states[-1])

    def test_quantity_like_number_does_not_trigger_customer_change_by_fuzzy_match(self):
        customers = [
            {"code": "1233", "name": "Cliente Atual", "document": "1"},
            {"code": "16069", "name": "IGOR MIRANDA BORGES", "document": "42423525818"},
        ]
        candidate = secretary_agent._customer_change_candidate(customers, "120", customers[0])
        self.assertIsNone(candidate)

    def test_portfolio_uses_rep_order_base_and_customer_profiles(self):
        db = _FakeDb(
            {
                "rep_order_base": [
                    {
                        "cod_rep": 52,
                        "cod_cli": 16069,
                        "dat_emi": "2026-06-09",
                        "customer_document": None,
                        "customer_name": None,
                    }
                ],
                "system_settings": [
                    {
                        "value": {
                            "16069": {
                                "cod_cli": 16069,
                                "documento": "42423525818",
                                "nome": "IGOR MIRANDA BORGES",
                                "fantasia": "IGOR REPRESENTANTE DELIVERY SPRES",
                                "telefone": "16988369829",
                                "tabela_preco_codigo": "205",
                            }
                        }
                    }
                ],
                "clic_clientes": [
                    {
                        "cpf_cnpj": "42423525818",
                        "telefone": "16988369829",
                        "tabela_preco_codigo": "205",
                    }
                ],
            }
        )
        customers = secretary_agent._portfolio_customers(db, 52)
        self.assertEqual(customers[0]["code"], "16069")
        self.assertEqual(customers[0]["document"], "42423525818")
        self.assertEqual(customers[0]["name"], "IGOR MIRANDA BORGES")
        self.assertEqual(customers[0]["price_table_code"], "205")
        matches = secretary_agent._search_customers(customers, "Código 16069")
        self.assertEqual(matches[0]["code"], "16069")

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
