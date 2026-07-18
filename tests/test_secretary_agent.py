import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "execution"))

import clic_vendas_cli
import clic_vendas_client
import secretary_agent
import secretary_ai_agent
import secretary_tools
import senior_order_client


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


class _CaptureUpsertQuery:
    def __init__(self, calls):
        self.calls = calls

    def upsert(self, row, **kwargs):
        self.calls.append((row, kwargs))
        return self

    def execute(self):
        return type("Result", (), {"data": []})()


class _CaptureUpsertDb:
    def __init__(self):
        self.calls = []

    def table(self, name):
        self.calls.append(("table", name))
        return _CaptureUpsertQuery(self.calls)


class _FakeOpenAIMessage:
    def __init__(self, content):
        self.content = content


class _FakeOpenAIChoice:
    def __init__(self, content):
        self.message = _FakeOpenAIMessage(content)


class _FakeOpenAIResponse:
    def __init__(self, content):
        self.choices = [_FakeOpenAIChoice(content)]


class _FakeChatCompletions:
    def __init__(self, content):
        self.content = content
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return _FakeOpenAIResponse(self.content)


class _FakeChat:
    def __init__(self, content):
        self.completions = _FakeChatCompletions(content)


class _FakeOpenAIClient:
    def __init__(self, content):
        self.chat = _FakeChat(content)


class SecretaryAgentTests(unittest.TestCase):
    def test_secretary_brain_falls_back_without_gpt_enabled(self):
        with patch.dict("os.environ", {"OPENAI_API_KEY": "test", "SECRETARY_AI_BRAIN_ENABLED": "false"}):
            decision = secretary_ai_agent.analyze_secretary_message(
                "Nao quero mudar o cliente. Quero suco de laranja de 900",
                {"customer": {"name": "Cliente Atual"}},
            )

        self.assertEqual(decision["intent"], "inform_products")
        self.assertTrue(decision["keep_current_customer"])
        self.assertIn("suco de laranja", decision["product_text"].lower())
        self.assertEqual(decision["source"], "heuristic")

    def test_secretary_brain_uses_gpt_json_when_enabled(self):
        fake_client = _FakeOpenAIClient(
            '{"intent":"select_sale_type","sale_type_code":"9010P","sale_type_only":true,'
            '"looks_like_product":false,"keep_current_customer":false,'
            '"product_text":"","customer_query":"","confidence":0.91}'
        )

        with patch.dict("os.environ", {"OPENAI_API_KEY": "test", "SECRETARY_AI_BRAIN_ENABLED": "true"}), patch(
            "openai.OpenAI", return_value=fake_client
        ):
            decision = secretary_ai_agent.analyze_secretary_message(
                "vai ser sem nota mesmo",
                {"customer": {"name": "Cliente Atual"}},
            )

        self.assertEqual(decision["source"], "gpt")
        self.assertEqual(decision["intent"], "select_sale_type")
        self.assertEqual(decision["sale_type_code"], "9010P")
        self.assertTrue(decision["sale_type_only"])

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

    def test_secretary_allowed_phone_accepts_mobile_ninth_digit_variation(self):
        with patch.dict("os.environ", {"SECRETARY_ALLOWED_PHONES": "5598981522794"}):
            self.assertTrue(secretary_agent._is_secretary_phone_allowed("559881522794"))
            self.assertTrue(secretary_agent._is_secretary_phone_allowed("9881522794"))

    def test_secretary_rejects_phone_without_active_representative(self):
        db = _FakeDb({"representatives": []})
        with patch.dict("os.environ", {"SECRETARY_ALLOWED_PHONES": "5516999999999"}), patch.object(
            secretary_agent, "_db", return_value=db
        ):
            result = secretary_agent.process_secretary_message(
                phone="5516888888888",
                text="pedido para Mercado Central",
                instance_name="secretaria-01",
            )
        self.assertEqual(result["action"], "secretary_unauthorized")
        self.assertTrue(result["should_reply"])

    def test_active_representative_phone_is_allowed_without_allowlist(self):
        db = _FakeDb(
            {
                "representatives": [
                    {
                        "cod_rep": 77,
                        "name": "REP TESTE",
                        "active": True,
                        "whatsapp_number": "16988887777",
                    }
                ]
            }
        )
        with patch.dict("os.environ", {"SECRETARY_ALLOWED_PHONES": "5516999999999"}), patch.object(
            secretary_agent, "_db", return_value=db
        ):
            self.assertTrue(secretary_agent.is_secretary_phone_allowed("5516988887777"))

    def test_secretary_default_allows_eliezer_and_test_phone(self):
        with patch.dict("os.environ", {}, clear=True):
            self.assertTrue(secretary_agent._is_secretary_phone_allowed("5516991377335"))
            self.assertTrue(secretary_agent._is_secretary_phone_allowed("16991377335"))
            self.assertTrue(secretary_agent._is_secretary_phone_allowed("98981522794"))
            self.assertTrue(secretary_agent._is_secretary_phone_allowed("5598981522794"))
            self.assertTrue(secretary_agent._is_secretary_phone_allowed("559881422794"))
        self.assertFalse(secretary_agent._is_secretary_phone_allowed("5516888888888"))

    def test_product_tool_resolves_items_and_saves_draft(self):
        state = {"customer": {"name": "Cliente"}, "product_history": []}
        result = secretary_tools.resolve_products_tool(
            text="10 suco de laranja 900",
            state=state,
            customer={"name": "Cliente"},
            catalog_lookup=lambda _customer: [{"cod_produto": "SGRSSLAR"}],
            resolver=lambda _text, _catalog, _state: {
                "itens": [
                    {
                        "status": "encontrado",
                        "cod_produto": "SGRSSLAR",
                        "nome_catalogo": "SUCO LARANJA",
                        "tamanho": "900",
                        "quantidade": 10,
                        "preco_unitario": 5.92,
                    }
                ]
            },
            drop_resolved_pending_items=lambda resolution: resolution,
            resolution_items=secretary_agent._resolution_items,
            safe_float=secretary_agent._safe_float,
            resolution_reply=secretary_agent._secretary_resolution_reply,
            save_draft=lambda _state: {"id": "order-1", "protocol": "MSE-1"},
            order_summary=secretary_agent._order_summary,
        )

        self.assertEqual(result.action, "secretary_reply")
        self.assertEqual(result.state["order_id"], "order-1")
        self.assertTrue(result.state["ready_to_submit"])
        self.assertIn("SUCO LARANJA", result.reply)

    def test_submit_tool_keeps_state_when_senior_fails(self):
        state = {
            "customer": {"name": "Cliente"},
            "items": [{"cod_produto": "SGRSSLAR", "subtotal": 59.2}],
            "order_id": "order-1",
            "ready_to_submit": True,
        }
        result = secretary_tools.submit_order_tool(
            state=state,
            load_order=lambda _order_id: {"id": "order-1"},
            save_draft=lambda _state: {"id": "order-1", "protocol": "MSE-1"},
            submit=lambda _order: (False, "Configuracao Senior incompleta."),
        )

        self.assertEqual(result.action, "secretary_submitted")
        self.assertEqual(result.state["order_id"], "order-1")
        self.assertIn("Senior", result.reply)

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

    def test_representative_document_reads_profile(self):
        db = _FakeDb(
            {
                "system_settings": [
                    {
                        "value": {
                            "52": {
                                "cod_rep": 52,
                                "documento": "345.017.048-10",
                            }
                        }
                    }
                ],
            }
        )
        self.assertEqual(secretary_agent._representative_document(db, 52), "34501704810")

    def test_clic_client_uses_representative_credentials_when_configured(self):
        with patch.dict(
            "os.environ",
            {
                "CLIC_VENDAS_URL": "https://api.example.test",
                "CLIC_VENDAS_AUTH_URL": "https://auth.example.test",
                "CLIC_VENDAS_USER": "admin",
                "CLIC_VENDAS_PASSWORD": "admin-pass",
                "CLIC_VENDAS_SUBDOMAIN": "sucosspres",
                "CLIC_VENDAS_REP_52_USER": "52",
                "CLIC_VENDAS_REP_52_PASSWORD": "rep-pass",
            },
        ):
            client = clic_vendas_client.ClicVendasClient.for_representative(52)

        self.assertEqual(client.username, "52")
        self.assertEqual(client.password, "rep-pass")
        self.assertEqual(client.credential_label, "rep:52")

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
            },
            representative_document="34501704810",
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

    def test_build_clic_payload_uses_technical_variation_code(self):
        payload = secretary_agent._build_clic_order_payload(
            {
                "customer_document": "05482507000142",
                "sale_type_code": "90100",
                "price_table_code": "205",
                "items_json": [
                    {"cod_produto": "SGRSSLAR", "derivacao": "900ml", "quantidade": 12, "preco_unitario": 5.92},
                    {"cod_produto": "SCPSSLAR", "derivacao": "200ml", "quantidade": 20, "preco_unitario": 1.49},
                    {"cod_produto": "SGPSSLAR", "derivacao": "5L", "quantidade": 1, "preco_unitario": 28.88},
                ],
            },
            representative_document="34501704810",
        )
        self.assertEqual(
            [item["codigoVariacao"] for item in payload[0]["itens"]],
            ["900", "200", "05L"],
        )

    def test_senior_order_is_mirrored_to_rep_order_base_for_representative(self):
        db = _CaptureUpsertDb()
        result = type("SeniorResult", (), {"parsed": {"sitPed": "1"}})()
        ok = secretary_agent._save_senior_order_to_rep_order_base(
            db,
            {
                "id": "order-1",
                "protocol": "MSE-260702-ABC123",
                "instance_name": "secretaria",
                "cod_rep": 52,
                "customer_code": "16069",
                "customer_document": "42423525818",
                "customer_name": "IGOR MIRANDA BORGES",
                "total": 71.04,
                "items_json": [
                    {
                        "cod_produto": "SGRSSLAR",
                        "derivacao": "900",
                        "nome": "SUCO GARRAFA LARANJA",
                        "quantidade": 12,
                        "preco_unitario": 5.92,
                        "subtotal": 71.04,
                    }
                ],
            },
            "352739",
            result,
        )

        self.assertTrue(ok)
        self.assertEqual(db.calls[0], ("table", "rep_order_base"))
        row, kwargs = db.calls[1]
        self.assertEqual(kwargs, {"on_conflict": "cod_rep,num_ped"})
        self.assertEqual(row["cod_rep"], 52)
        self.assertEqual(row["cod_cli"], 16069)
        self.assertEqual(row["rep_name"], "ELIEZER GONZAGA DOS REIS")
        self.assertEqual(row["num_ped"], "352739")
        self.assertEqual(row["source"], "senior_erp")
        self.assertEqual(row["origin_agent"], "marcela_secretaria")
        self.assertEqual(row["origin_protocol"], "MSE-260702-ABC123")
        self.assertEqual(row["items_json"][0]["codPro"], "SGRSSLAR")
        self.assertEqual(row["items_json"][0]["qtdPed"], 12.0)

    def test_build_clic_payload_requires_sale_type(self):
        with self.assertRaises(ValueError):
            secretary_agent._build_clic_order_payload(
                {
                    "customer_document": "05482507000142",
                    "price_table_code": "205",
                    "items_json": [
                        {"cod_produto": "SGRSSLAR", "derivacao": "900", "quantidade": 12, "preco_unitario": 5.92},
                    ],
                },
                representative_document="34501704810",
            )

    def test_build_clic_payload_requires_representative_document(self):
        with self.assertRaises(ValueError):
            secretary_agent._build_clic_order_payload(
                {
                    "customer_document": "05482507000142",
                    "sale_type_code": "90100",
                    "price_table_code": "205",
                    "items_json": [
                        {"cod_produto": "SGRSSLAR", "derivacao": "900", "quantidade": 12, "preco_unitario": 5.92},
                    ],
                }
            )

    def test_sale_type_code_from_text(self):
        self.assertEqual(secretary_agent._sale_type_code_from_text("pedido pdv"), "9010P")
        self.assertEqual(secretary_agent._sale_type_code_from_text("bonificacao acordo"), "BONIF4")
        self.assertEqual(secretary_agent._sale_type_code_from_text("normal com nota"), "90100")
        self.assertTrue(secretary_agent._sale_type_only_message("pedido normal"))
        self.assertTrue(secretary_agent._sale_type_only_message("entrada pedido normal."))

    def test_generic_message_without_customer_starts_conversation_naturally(self):
        saved_states = []
        with patch.object(secretary_agent, "_db", return_value=object()), patch.object(
            secretary_agent, "_representative", return_value={"cod_rep": 52, "name": "ELIEZER"}
        ), patch.object(
            secretary_agent, "_conversation", return_value={"id": "conv-1", "state_json": {}}
        ), patch.object(
            secretary_agent, "_add_message", return_value=True
        ), patch.object(
            secretary_agent, "_portfolio_customers"
        ) as portfolio, patch.object(
            secretary_agent, "_save_state", side_effect=lambda _db, _id, state: saved_states.append(state)
        ):
            result = secretary_agent.process_secretary_message("5598981522794", "teste", "secretaria")

        self.assertEqual(result["action"], "secretary_greeting")
        self.assertIn("sou a secretaria de pedidos", result["reply"])
        self.assertIn("código, nome ou documento do cliente", result["reply"])
        portfolio.assert_not_called()

    def test_sale_type_without_customer_is_not_treated_as_product_or_customer(self):
        saved_states = []
        with patch.object(secretary_agent, "_db", return_value=object()), patch.object(
            secretary_agent, "_representative", return_value={"cod_rep": 52, "name": "ELIEZER"}
        ), patch.object(
            secretary_agent, "_conversation", return_value={"id": "conv-1", "state_json": {}}
        ), patch.object(
            secretary_agent, "_add_message", return_value=True
        ), patch.object(
            secretary_agent, "_portfolio_customers"
        ) as portfolio, patch.object(
            secretary_agent, "_resolve_products_with_sales_subagent"
        ) as resolve_products, patch.object(
            secretary_agent, "_save_state", side_effect=lambda _db, _id, state: saved_states.append(state)
        ):
            result = secretary_agent.process_secretary_message("5598981522794", "pedido normal", "secretaria")

        self.assertEqual(result["action"], "secretary_sale_type_selected")
        self.assertIn("pedido normal", result["reply"])
        self.assertEqual(saved_states[-1]["sale_type_code"], "90100")
        portfolio.assert_not_called()
        resolve_products.assert_not_called()

    def test_sale_type_with_customer_does_not_go_to_product_resolver(self):
        customer = {"code": "16069", "name": "IGOR MIRANDA BORGES", "document": "42423525818", "price_table_code": "205"}
        saved_states = []
        with patch.object(secretary_agent, "_db", return_value=object()), patch.object(
            secretary_agent, "_representative", return_value={"cod_rep": 52, "name": "ELIEZER"}
        ), patch.object(
            secretary_agent,
            "_conversation",
            return_value={"id": "conv-1", "state_json": {"customer": customer}},
        ), patch.object(
            secretary_agent, "_add_message", return_value=True
        ), patch.object(
            secretary_agent, "_portfolio_customers", return_value=[customer]
        ), patch.object(
            secretary_agent, "_resolve_products_with_sales_subagent"
        ) as resolve_products, patch.object(
            secretary_agent, "_save_state", side_effect=lambda _db, _id, state: saved_states.append(state)
        ):
            result = secretary_agent.process_secretary_message("5598981522794", "pedido normal", "secretaria")

        self.assertEqual(result["action"], "secretary_sale_type_selected")
        self.assertIn("Quer adicionar alguma observação", result["reply"])
        self.assertEqual(saved_states[-1]["sale_type_code"], "90100")
        self.assertTrue(saved_states[-1]["awaiting_observation"])
        resolve_products.assert_not_called()

    def test_natural_sale_type_phrase_with_customer_is_not_product(self):
        customer = {"code": "16069", "name": "IGOR MIRANDA BORGES", "document": "42423525818", "price_table_code": "205"}
        saved_states = []
        with patch.object(secretary_agent, "_db", return_value=object()), patch.object(
            secretary_agent, "_representative", return_value={"cod_rep": 52, "name": "ELIEZER"}
        ), patch.object(
            secretary_agent,
            "_conversation",
            return_value={"id": "conv-1", "state_json": {"customer": customer}},
        ), patch.object(
            secretary_agent, "_add_message", return_value=True
        ), patch.object(
            secretary_agent, "_portfolio_customers", return_value=[customer]
        ), patch.object(
            secretary_agent, "_resolve_products_with_sales_subagent"
        ) as resolve_products, patch.object(
            secretary_agent, "_save_state", side_effect=lambda _db, _id, state: saved_states.append(state)
        ):
            result = secretary_agent.process_secretary_message("5598981522794", "Pedido normal mesmo", "secretaria")

        self.assertEqual(result["action"], "secretary_sale_type_selected")
        self.assertIn("pedido normal", result["reply"])
        self.assertEqual(saved_states[-1]["sale_type_code"], "90100")
        self.assertTrue(saved_states[-1]["awaiting_observation"])
        resolve_products.assert_not_called()

    def test_observation_no_after_sale_type_asks_for_products(self):
        customer = {"code": "16069", "name": "IGOR MIRANDA BORGES", "document": "42423525818", "price_table_code": "205"}
        saved_states = []
        with patch.object(secretary_agent, "_db", return_value=object()), patch.object(
            secretary_agent, "_representative", return_value={"cod_rep": 52, "name": "ELIEZER"}
        ), patch.object(
            secretary_agent,
            "_conversation",
            return_value={
                "id": "conv-1",
                "state_json": {
                    "customer": customer,
                    "sale_type_code": "90100",
                    "awaiting_observation": True,
                },
            },
        ), patch.object(
            secretary_agent, "_add_message", return_value=True
        ), patch.object(
            secretary_agent, "_save_state", side_effect=lambda _db, _id, state: saved_states.append(state)
        ):
            result = secretary_agent.process_secretary_message("5598981522794", "nao", "secretaria")

        self.assertEqual(result["action"], "secretary_observation_skipped")
        self.assertIn("Agora me envie os produtos", result["reply"])
        self.assertTrue(saved_states[-1]["observation_step_done"])
        self.assertNotIn("awaiting_observation", saved_states[-1])

    def test_observation_text_is_saved_before_products(self):
        customer = {"code": "16069", "name": "IGOR MIRANDA BORGES", "document": "42423525818", "price_table_code": "205"}
        saved_states = []
        with patch.object(secretary_agent, "_db", return_value=object()), patch.object(
            secretary_agent, "_representative", return_value={"cod_rep": 52, "name": "ELIEZER"}
        ), patch.object(
            secretary_agent,
            "_conversation",
            return_value={
                "id": "conv-1",
                "state_json": {
                    "customer": customer,
                    "sale_type_code": "90100",
                    "awaiting_observation": True,
                },
            },
        ), patch.object(
            secretary_agent, "_add_message", return_value=True
        ), patch.object(
            secretary_agent, "_save_state", side_effect=lambda _db, _id, state: saved_states.append(state)
        ):
            result = secretary_agent.process_secretary_message(
                "5598981522794",
                "entregar pela manhã",
                "secretaria",
            )

        self.assertEqual(result["action"], "secretary_observation_saved")
        self.assertEqual(saved_states[-1]["observations"], "entregar pela manhã")
        self.assertIn("Agora me envie os produtos", result["reply"])

    def test_observation_edit_updates_ready_order_without_resolving_products(self):
        customer = {"code": "16069", "name": "IGOR MIRANDA BORGES", "document": "42423525818", "price_table_code": "205"}
        item = {
            "nome": "SUCO GARRAFA LARANJA",
            "cod_produto": "SGRSSLAR",
            "derivacao": "900",
            "quantidade": 2,
            "unidade": "UN",
            "preco_unitario": 8.0,
            "subtotal": 16.0,
        }
        saved_states = []
        with patch.object(secretary_agent, "_db", return_value=object()), patch.object(
            secretary_agent, "_representative", return_value={"cod_rep": 52, "name": "ELIEZER"}
        ), patch.object(
            secretary_agent,
            "_conversation",
            return_value={
                "id": "conv-1",
                "state_json": {
                    "customer": customer,
                    "sale_type_code": "90100",
                    "items": [item],
                    "observations": "e e so",
                    "order_id": "order-1",
                    "ready_to_submit": True,
                    "observation_step_done": True,
                },
            },
        ), patch.object(
            secretary_agent, "_add_message", return_value=True
        ), patch.object(
            secretary_agent, "_save_draft", return_value={"id": "order-1", "protocol": "MSE-1"}
        ) as save_draft, patch.object(
            secretary_agent, "_resolve_products_with_sales_subagent"
        ) as resolve_products, patch.object(
            secretary_agent, "_save_state", side_effect=lambda _db, _id, state: saved_states.append(state)
        ):
            result = secretary_agent.process_secretary_message(
                "5598981522794",
                "mudar observacao para favor abastecer",
                "secretaria",
            )

        self.assertEqual(result["action"], "secretary_observation_updated")
        self.assertEqual(saved_states[-1]["observations"], "favor abastecer")
        self.assertIn("Observações: favor abastecer", result["reply"])
        save_draft.assert_called_once()
        resolve_products.assert_not_called()

    def test_observation_edit_can_ask_for_new_text_then_save(self):
        customer = {"code": "16069", "name": "IGOR MIRANDA BORGES", "document": "42423525818", "price_table_code": "205"}
        item = {
            "nome": "SUCO GARRAFA LARANJA",
            "cod_produto": "SGRSSLAR",
            "derivacao": "900",
            "quantidade": 2,
            "unidade": "UN",
            "preco_unitario": 8.0,
            "subtotal": 16.0,
        }
        saved_states = []
        base_state = {
            "customer": customer,
            "sale_type_code": "90100",
            "items": [item],
            "observations": "antiga",
            "order_id": "order-1",
            "ready_to_submit": True,
            "observation_step_done": True,
        }
        with patch.object(secretary_agent, "_db", return_value=object()), patch.object(
            secretary_agent, "_representative", return_value={"cod_rep": 52, "name": "ELIEZER"}
        ), patch.object(
            secretary_agent, "_conversation", return_value={"id": "conv-1", "state_json": base_state}
        ), patch.object(
            secretary_agent, "_add_message", return_value=True
        ), patch.object(
            secretary_agent, "_save_state", side_effect=lambda _db, _id, state: saved_states.append(state)
        ):
            result = secretary_agent.process_secretary_message("5598981522794", "mudar observacao", "secretaria")

        self.assertEqual(result["action"], "secretary_ask_observation_text")
        self.assertTrue(saved_states[-1]["awaiting_observation_text"])
        self.assertTrue(saved_states[-1]["editing_observation"])

        saved_second = []
        with patch.object(secretary_agent, "_db", return_value=object()), patch.object(
            secretary_agent, "_representative", return_value={"cod_rep": 52, "name": "ELIEZER"}
        ), patch.object(
            secretary_agent, "_conversation", return_value={"id": "conv-1", "state_json": saved_states[-1]}
        ), patch.object(
            secretary_agent, "_add_message", return_value=True
        ), patch.object(
            secretary_agent, "_save_draft", return_value={"id": "order-1", "protocol": "MSE-1"}
        ) as save_draft, patch.object(
            secretary_agent, "_save_state", side_effect=lambda _db, _id, state: saved_second.append(state)
        ):
            second = secretary_agent.process_secretary_message("5598981522794", "entregar ate 10h", "secretaria")

        self.assertEqual(second["action"], "secretary_observation_saved")
        self.assertEqual(saved_second[-1]["observations"], "entregar ate 10h")
        save_draft.assert_called_once()

    def test_created_order_number_reads_nested_clic_response(self):
        response = {
            "resultados": [
                {
                    "body": {
                        "objeto": {
                            "numero": "742269263",
                        }
                    }
                }
            ]
        }
        self.assertEqual(secretary_agent._created_order_number(response), "742269263")

    def test_senior_observation_payload_uses_inserir_observacoes(self):
        with patch.dict(
            "os.environ",
            {
                "SENIOR_BASE_URL": "https://senior.example.test",
                "SENIOR_USER": "usuario",
                "SENIOR_PASSWORD": "senha",
                "SENIOR_ENCRYPTION": "0",
                "SENIOR_COD_EMP": "1",
                "SENIOR_COD_FIL": "1",
            },
            clear=False,
        ):
            client = senior_order_client.SeniorOrderClient()
            payload = client.build_masked_observation_payload("352881", "Entregar pela manha")
        self.assertEqual(payload["operation"], "inserirObservacoes")
        self.assertIn("<ser:inserirObservacoes>", payload["xml"])
        self.assertIn("<numeroPedido>352881</numeroPedido>", payload["xml"])
        self.assertIn("<observacao>Entregar pela manha</observacao>", payload["xml"])
        self.assertIn("***MASKED***", payload["xml"])

    def test_senior_order_payload_sends_sale_type_as_tns_pro(self):
        with patch.dict(
            "os.environ",
            {
                "SENIOR_BASE_URL": "https://senior.example.test",
                "SENIOR_USER": "usuario",
                "SENIOR_PASSWORD": "senha",
                "SENIOR_ENCRYPTION": "0",
                "SENIOR_COD_EMP": "1",
                "SENIOR_COD_FIL": "1",
            },
            clear=False,
        ):
            client = senior_order_client.SeniorOrderClient()
            payload = client.build_masked_payload(
                {
                    "customer_code": "28764",
                    "sale_type_code": "BONIF4",
                    "items_json": [
                        {"cod_produto": "SANDBRIOC", "derivacao": "FRAN", "quantidade": 8},
                    ],
                }
            )

        self.assertIn("<tnsPro>BONIF4</tnsPro>", payload["xml"])
        self.assertIn("<tipPed>1</tipPed>", payload["xml"])

    def test_senior_order_payload_maps_legacy_normal_sale_type_to_numeric_code(self):
        with patch.dict(
            "os.environ",
            {
                "SENIOR_BASE_URL": "https://senior.example.test",
                "SENIOR_USER": "usuario",
                "SENIOR_PASSWORD": "senha",
                "SENIOR_ENCRYPTION": "0",
                "SENIOR_COD_EMP": "1",
                "SENIOR_COD_FIL": "1",
            },
            clear=False,
        ):
            client = senior_order_client.SeniorOrderClient()
            payload = client.build_masked_payload(
                {
                    "customer_code": "28764",
                    "sale_type_code": "9010O",
                    "items_json": [
                        {"cod_produto": "SANDBRIOC", "derivacao": "FRAN", "quantidade": 8},
                    ],
                }
            )

        self.assertIn("<tnsPro>90100</tnsPro>", payload["xml"])
        self.assertNotIn("<tnsPro>9010O</tnsPro>", payload["xml"])

    def test_senior_order_payload_requires_sale_type(self):
        with patch.dict(
            "os.environ",
            {
                "SENIOR_BASE_URL": "https://senior.example.test",
                "SENIOR_USER": "usuario",
                "SENIOR_PASSWORD": "senha",
                "SENIOR_ENCRYPTION": "0",
                "SENIOR_COD_EMP": "1",
                "SENIOR_COD_FIL": "1",
            },
            clear=False,
        ):
            client = senior_order_client.SeniorOrderClient()
            with self.assertRaisesRegex(ValueError, "Tipo de venda"):
                client.build_masked_payload(
                    {
                        "customer_code": "28764",
                        "items_json": [
                            {"cod_produto": "SANDBRIOC", "derivacao": "FRAN", "quantidade": 8},
                        ],
                    }
                )

    def test_save_draft_requires_valid_sale_type(self):
        db = _FakeDb({"secretary_orders": []})
        with self.assertRaisesRegex(ValueError, "Tipo de venda"):
            secretary_agent._save_draft(
                db,
                {"id": "conv-1", "instance_name": "secretaria", "representative_phone": "5516"},
                {"cod_rep": 52},
                {
                    "customer": {"code": "28764", "name": "POSTO FLAMBOYANT"},
                    "items": [
                        {
                            "nome": "SANDUICHE BRIOCHE",
                            "cod_produto": "SANDBRIOC",
                            "derivacao": "FRAN",
                            "quantidade": 8,
                            "subtotal": 76.08,
                        }
                    ],
                },
            )

    def test_order_summary_displays_sale_type(self):
        reply = secretary_agent._order_summary(
            {"name": "POSTO FLAMBOYANT"},
            [
                {
                    "nome": "SANDUICHE BRIOCHE",
                    "cod_produto": "SANDBRIOC",
                    "derivacao": "FRAN",
                    "quantidade": 8,
                    "unidade": "UN",
                    "preco_unitario": 9.51,
                    "subtotal": 76.08,
                }
            ],
            "Troca por validade",
            sale_type_code="BONIF4",
        )

        self.assertIn("Tipo: *bonificação*", reply)

    def test_parse_senior_observation_response(self):
        parsed = senior_order_client.parse_inserir_observacoes_response(
            """<S:Envelope xmlns:S="http://schemas.xmlsoap.org/soap/envelope/"><S:Body>
            <ns2:inserirObservacoesResponse xmlns:ns2="http://services.senior.com.br"><result>
            <codigoResultado>1</codigoResultado><resultado>OK</resultado>
            <retorno><codigoEmpresa>1</codigoEmpresa><codigoFilial>1</codigoFilial>
            <numeroPedido>352881</numeroPedido></retorno>
            </result></ns2:inserirObservacoesResponse></S:Body></S:Envelope>"""
        )
        self.assertEqual(parsed["codigoResultado"], "1")
        self.assertEqual(parsed["numeroPedido"], "352881")

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

    def test_secretary_reply_shows_partial_draft_and_missing_items(self):
        reply = secretary_agent._secretary_resolution_reply(
            {
                "itens": [
                    {
                        "status": "encontrado",
                        "cod_produto": "SGPSSLAR",
                        "nome_catalogo": "SUCO GALAO LARANJA PET",
                        "formato": "galao",
                        "tamanho": "5L",
                        "quantidade": 20,
                        "unidade": "UN",
                        "preco_unitario": 28.88,
                    },
                    {
                        "status": "nao_encontrado",
                        "produto": "uva",
                        "formato": "bag",
                        "tamanho": "5L",
                        "alternativas": ["Uva bolsa 5L", "Uva copo 200ml"],
                    },
                ]
            }
        )
        self.assertIn("Pedido conferido:", reply)
        self.assertIn("Encontrados:", reply)
        self.assertIn("SGPSSLAR - SUCO GALAO LARANJA PET | 5L | 20 un", reply)
        self.assertIn("Total parcial encontrado: R$ 577,60", reply)
        self.assertIn("Não encontrados:", reply)
        self.assertIn("- uva | bag 5L", reply)
        self.assertIn("Sugestoes na tabela:", reply)
        self.assertIn("Uva bolsa 5L", reply)
        self.assertIn("correção dos itens não encontrados", reply)

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

    def test_promotes_simple_orange_gallon_without_explicit_size(self):
        resolution = {
            "itens": [
                {
                    "status": "nao_encontrado",
                    "produto": "suco laranja",
                    "formato": "galao",
                    "texto_original": "5 suco galao laranja",
                    "quantidade": 5,
                    "alternativas": [
                        "Galao Laranja Pet: galao 5L",
                        "SGPSSLAR - SUCO GALAO LARANJA PET | 05L | R$ 42,37",
                        "SGPSSCLA - SUCO GALÃO PET LARANJA ADOCADO | 05L | R$ 31,25",
                    ],
                }
            ]
        }
        catalog = [
            {"cod_produto": "SGPSSLAR", "nome_produto": "SUCO GALAO LARANJA PET", "variacao": "05L", "preco": 42.37},
            {"cod_produto": "SGPSSCLA", "nome_produto": "SUCO GALÃO PET LARANJA ADOCADO", "variacao": "05L", "preco": 31.25},
        ]
        promoted = secretary_agent._promote_safe_catalog_matches(resolution, catalog)
        item = promoted["itens"][0]
        self.assertEqual(item["status"], "encontrado")
        self.assertEqual(item["cod_produto"], "SGPSSLAR")
        self.assertEqual(item["codigo_variacao"], "05L")
        self.assertAlmostEqual(item["subtotal"], 211.85)

    def test_promotes_orange_pet_gallon_from_correction_reply(self):
        resolution = {
            "itens": [
                {
                    "status": "nao_encontrado",
                    "produto": "laranja",
                    "formato": "galao",
                    "texto_original": "Galao laranja pet",
                    "quantidade": 5,
                    "alternativas": [
                        "Galao Laranja Pet: galao 5L",
                        "SGPSSLAR - SUCO GALAO LARANJA PET | 05L | R$ 42,37",
                        "SGPSSCLA - SUCO GALÃO PET LARANJA ADOCADO | 05L | R$ 31,25",
                    ],
                }
            ]
        }
        catalog = [
            {"cod_produto": "SGPSSLAR", "nome_produto": "SUCO GALAO LARANJA PET", "variacao": "05L", "preco": 42.37},
            {"cod_produto": "SGPSSCLA", "nome_produto": "SUCO GALÃO PET LARANJA ADOCADO", "variacao": "05L", "preco": 31.25},
        ]
        promoted = secretary_agent._promote_safe_catalog_matches(resolution, catalog)
        item = promoted["itens"][0]
        self.assertEqual(item["status"], "encontrado")
        self.assertEqual(item["cod_produto"], "SGPSSLAR")

    def test_pending_compound_product_is_not_dropped_as_plain_orange(self):
        resolution = {
            "itens": [
                {
                    "status": "encontrado",
                    "produto": "Galao Laranja Pet",
                    "nome_catalogo": "SUCO GALAO LARANJA PET",
                    "formato": "galao",
                    "tamanho": "5L",
                    "quantidade": 10,
                    "cod_produto": "SGPSSLAR",
                    "preco_unitario": 28.88,
                },
                {
                    "status": "nao_encontrado",
                    "produto": "laranja composto",
                    "formato": "galao",
                    "tamanho": "5L",
                    "quantidade": 20,
                    "texto_original": "20 galoes laranja composto 5l",
                    "alternativas": ["Composto De Laranja: bolsa 5L"],
                },
            ]
        }
        cleaned = secretary_agent._drop_resolved_pending_items(resolution)
        self.assertEqual(len(cleaned["itens"]), 2)
        reply = secretary_agent._secretary_resolution_reply(cleaned)
        self.assertIn("Não encontrados", reply)
        self.assertIn("laranja composto", reply)
        self.assertIn("Composto De Laranja: bolsa 5L", reply)

    def test_missing_product_suggestions_use_catalog_flavor_and_size(self):
        resolution = {
            "itens": [
                {
                    "status": "nao_encontrado",
                    "produto": "laranja composto",
                    "formato": "galao",
                    "tamanho": "5L",
                    "texto_original": "galao de laranja composto 5l",
                    "alternativas": ["CBPSSLAR - COMPOSTO DE LARANJA BOLSA | 5L | R$ 24,00"],
                },
            ]
        }
        catalog = [
            {
                "cod_produto": "SGPSSLAR",
                "nome_produto": "SUCO GALAO LARANJA PET",
                "variacao": "05L",
                "preco": 28.88,
            },
            {
                "cod_produto": "SCPSSLAR",
                "nome_produto": "SUCO COPO LARANJA",
                "variacao": "200ML",
                "preco": 0.36,
            },
        ]
        enriched = secretary_agent._augment_resolution_suggestions(resolution, catalog)
        reply = secretary_agent._secretary_resolution_reply(enriched)
        self.assertIn("CBPSSLAR - COMPOSTO DE LARANJA BOLSA | 5L", reply)
        self.assertIn("SGPSSLAR - SUCO GALAO LARANJA PET | 05L", reply)
        self.assertNotIn("SCPSSLAR - SUCO COPO LARANJA", reply)

    def test_reconcile_handles_product_and_format_inverted_for_cup_orange_115(self):
        resolution = {
            "itens": [
                {
                    "status": "nao_encontrado",
                    "produto": "copo",
                    "formato": "laranja",
                    "tamanho": "115ml",
                    "quantidade": 120,
                    "unidade": "unidades",
                    "texto_original": "copo laranja 115 ml 120 unidades",
                    "alternativas": ["SCPSSLAR - SUCO COPO LARANJA 115ML | 115 | R$ 1,33"],
                }
            ]
        }
        catalog = [
            {
                "cod_produto": "SCPSSLAR",
                "nome_produto": "SUCO COPO LARANJA 115ML",
                "variacao": "115",
                "preco": 1.33,
            }
        ]

        reconciled = secretary_agent._reconcile_catalog_resolution(resolution, catalog)
        item = reconciled["itens"][0]

        self.assertEqual(item["status"], "encontrado")
        self.assertEqual(item["cod_produto"], "SCPSSLAR")
        self.assertEqual(item["formato"], "copo")
        self.assertEqual(item["tamanho"], "115ml")
        self.assertEqual(item["quantidade"], 120)
        self.assertAlmostEqual(item["subtotal"], 159.6)

    def test_secretary_promotes_cremoso_frango_suggestion_to_catalog_item(self):
        resolution = {
            "itens": [
                {
                    "status": "nao_encontrado",
                    "produto": "cremoso frango",
                    "texto_original": "7 cremoso frango",
                    "quantidade": 7,
                    "alternativas": [
                        "Sanduiche Cremoso Cr00001:  ATUM",
                        "Sanduiche Cremoso Cr00002:  FRAN",
                        "Sanduiche Cremoso Cr00004:  PEPE",
                        "Sanduiche Cremoso Cr00010:  SALP",
                    ],
                }
            ]
        }
        catalog = [
            {"cod_produto": "SANDCREMO", "nome_produto": "SANDUICHE CREMOSO CR00001", "variacao": "ATUM", "preco": 7.82},
            {"cod_produto": "SANDCREMO", "nome_produto": "SANDUICHE CREMOSO CR00002", "variacao": "FRAN", "preco": 7.82},
            {"cod_produto": "SANDCREMO", "nome_produto": "SANDUICHE CREMOSO CR00004", "variacao": "PEPE", "preco": 7.82},
            {"cod_produto": "SANDCREMO", "nome_produto": "SANDUICHE CREMOSO CR00010", "variacao": "SALP", "preco": 7.82},
        ]

        promoted = secretary_agent._promote_safe_catalog_matches(resolution, catalog)
        item = promoted["itens"][0]

        self.assertEqual(item["status"], "encontrado")
        self.assertEqual(item["cod_produto"], "SANDCREMO")
        self.assertEqual(item["codigo_variacao"], "FRAN")
        self.assertEqual(item["quantidade"], 7)
        self.assertAlmostEqual(item["subtotal"], 54.74)

    def test_secretary_promotes_cremoso_fran_without_matching_mini(self):
        resolution = {
            "itens": [
                {
                    "status": "nao_encontrado",
                    "produto": "sanduíche cremoso fran",
                    "texto_original": "4 sanduíche cremoso fran",
                    "tamanho": "FRAN",
                    "quantidade": 4,
                    "alternativas": [
                        "Sanduiche Cremoso Cr00002:  FRAN",
                        "SANDCREMO - SANDUICHE CREMOSO CR00002 | FRAN | R$ 7,82",
                        "Sanduiche Cremoso Mini:  FRAN",
                        "Sanduiche Brioche:  FRAN",
                    ],
                }
            ]
        }
        catalog = [
            {"cod_produto": "SANDCMINI", "nome_produto": "SANDUICHE CREMOSO MINI", "variacao": "FRAN", "preco": 6.48},
            {"cod_produto": "SANDCREMO", "nome_produto": "SANDUICHE CREMOSO CR00002", "variacao": "FRAN", "preco": 7.82},
            {"cod_produto": "SANDBRIOC", "nome_produto": "SANDUICHE BRIOCHE", "variacao": "FRAN", "preco": 9.51},
        ]

        promoted = secretary_agent._promote_safe_catalog_matches(resolution, catalog)
        item = promoted["itens"][0]

        self.assertEqual(item["status"], "encontrado")
        self.assertEqual(item["cod_produto"], "SANDCREMO")
        self.assertEqual(item["codigo_variacao"], "FRAN")
        self.assertEqual(item["quantidade"], 4)
        self.assertAlmostEqual(item["subtotal"], 31.28)

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

    def test_product_message_during_items_does_not_try_to_change_customer(self):
        current_customer = {"code": "1233", "name": "Cliente Atual", "document": "1", "price_table_code": "205"}
        confusing_customer = {"code": "10", "name": "POSTO JASMIN DE FRANCA LTDA", "document": "2", "price_table_code": "205"}
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
                    "sale_type_code": "90100",
                    "items": [{"cod_produto": "A"}],
                    "product_history": [],
                },
            },
        ), patch.object(secretary_agent, "_add_message", return_value=True), patch.object(
            secretary_agent, "_portfolio_customers", return_value=[current_customer, confusing_customer]
        ), patch.object(secretary_agent, "_catalog", return_value=[{"cod_produto": "SGRSSLAR"}]), patch.object(
            secretary_agent,
            "_resolve_products_with_sales_subagent",
            return_value={
                "itens": [
                    {
                        "status": "encontrado",
                        "cod_produto": "SGRSSLAR",
                        "nome_catalogo": "SUCO GARRAFA PASTEURIZADO DE LARANJA",
                        "formato": "garrafa",
                        "tamanho": "900",
                        "quantidade": 10,
                        "preco_unitario": 5.92,
                    }
                ]
            },
        ) as resolve_products, patch.object(
            secretary_agent, "_save_draft", return_value={"id": "order-1", "protocol": "MSE-1"}
        ), patch.object(
            secretary_agent, "_save_state", side_effect=lambda _db, _id, state: saved_states.append(state)
        ):
            result = secretary_agent.process_secretary_message("5516991377335", "10 suco de laranja de 900", "secretaria")

        self.assertNotEqual(result["action"], "secretary_confirm_customer_change")
        resolve_products.assert_called_once()
        self.assertNotIn("pending_action", saved_states[-1])

    def test_keep_current_customer_and_product_in_same_message_continues_order(self):
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
                    "sale_type_code": "90100",
                    "items": [{"cod_produto": "A"}],
                    "product_history": [],
                    "pending_action": {"type": "change_customer", "customer": new_customer},
                },
            },
        ), patch.object(secretary_agent, "_add_message", return_value=True), patch.object(
            secretary_agent, "_portfolio_customers", return_value=[current_customer, new_customer]
        ), patch.object(secretary_agent, "_catalog", return_value=[{"cod_produto": "SGRSSLAR"}]), patch.object(
            secretary_agent,
            "_resolve_products_with_sales_subagent",
            return_value={
                "itens": [
                    {
                        "status": "encontrado",
                        "cod_produto": "SGRSSLAR",
                        "nome_catalogo": "SUCO GARRAFA PASTEURIZADO DE LARANJA",
                        "formato": "garrafa",
                        "tamanho": "900",
                        "quantidade": 10,
                        "preco_unitario": 5.92,
                    }
                ]
            },
        ) as resolve_products, patch.object(
            secretary_agent, "_save_draft", return_value={"id": "order-1", "protocol": "MSE-1"}
        ), patch.object(
            secretary_agent, "_save_state", side_effect=lambda _db, _id, state: saved_states.append(state)
        ):
            result = secretary_agent.process_secretary_message(
                "5516991377335",
                "Nao quero mudar o cliente. Quero suco de laranja de 900",
                "secretaria",
            )

        self.assertNotEqual(result["action"], "secretary_confirm_customer_change")
        resolve_products.assert_called_once()
        self.assertNotIn("pending_action", saved_states[-1])

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

    def test_ready_order_accepts_sim_as_confirmation_to_submit(self):
        customer = {"code": "16069", "name": "IGOR MIRANDA BORGES", "document": "42423525818", "price_table_code": "205"}
        db = _FakeDb({"secretary_orders": [{"id": "order-1"}]})
        with patch.object(secretary_agent, "_db", return_value=db), patch.object(
            secretary_agent, "_representative", return_value={"cod_rep": 52, "name": "ELIEZER"}
        ), patch.object(
            secretary_agent,
            "_conversation",
            return_value={
                "id": "conv-1",
                "state_json": {
                    "customer": customer,
                    "items": [{"cod_produto": "SGRSSLAR", "quantidade": 10, "subtotal": 59.20}],
                    "order_id": "order-1",
                    "ready_to_submit": True,
                },
            },
        ), patch.object(secretary_agent, "_add_message", return_value=True), patch.object(
            secretary_agent, "_save_state"
        ), patch.object(
            secretary_agent, "_resolve_products_with_sales_subagent"
        ) as resolve_products, patch.object(
            secretary_agent, "_submit", return_value=(True, "Pedido enviado ao Senior ERP com sucesso. Pedido numero *123*."),
        ) as submit:
            result = secretary_agent.process_secretary_message("5598981522794", "sim", "secretaria")

        self.assertEqual(result["action"], "secretary_submitted")
        self.assertIn("Pedido enviado", result["reply"])
        submit.assert_called_once()
        resolve_products.assert_not_called()

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

    def test_portfolio_includes_profile_only_customer_for_representative(self):
        db = _FakeDb(
            {
                "rep_order_base": [],
                "system_settings": [
                    {
                        "value": {
                            "29232": {
                                "cod_cli": 29232,
                                "cod_rep": 106,
                                "documento": "20813167000774",
                                "nome": "ELDI SUPERMERCADO LTDA",
                                "fantasia": "ELDI LOJA 07",
                                "telefone": "1632114455",
                                "tabela_preco_codigo": "201",
                                "cidade": "RIBEIRAO PRETO",
                                "uf": "SP",
                            }
                        }
                    }
                ],
                "clic_clientes": [
                    {
                        "cpf_cnpj": "20813167000774",
                        "telefone": "1632114455",
                        "tabela_preco_codigo": "201",
                    }
                ],
            }
        )
        customers = secretary_agent._portfolio_customers(db, 106)
        self.assertEqual(customers[0]["code"], "29232")
        self.assertEqual(customers[0]["document"], "20813167000774")
        self.assertEqual(customers[0]["name"], "ELDI SUPERMERCADO LTDA")
        self.assertEqual(customers[0]["price_table_code"], "201")

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
