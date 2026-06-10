import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "execution"))

import ai_agent


class AiAgentRegressionTests(unittest.TestCase):
    def test_catalog_entry_for_order_subagent_uses_public_product_label(self):
        entry = ai_agent._catalog_entry_for_agent(
            {
                "nome_produto": "SUCO GARRAFA LARANJA",
                "variacao": "900",
                "preco": 9.17,
            }
        )

        self.assertEqual(entry["produto_publico"], "Laranja")
        self.assertEqual(entry["formato"], "garrafa")
        self.assertEqual(entry["tamanho"], "900ml")

    def test_common_words_are_not_catalog_tokens(self):
        produtos = [{"nome_produto": "ALFAJOR 40G | CHOMEA"}]

        tokens = ai_agent._requested_catalog_tokens(
            "Então, eu te perguntei se você não tem só suco, além de suco quais outros tipos de produtos você vende?",
            produtos,
        )

        self.assertNotIn("voce", tokens)
        self.assertNotIn("alem", tokens)
        self.assertNotIn("perguntei", tokens)

    def test_non_suco_product_reply_lists_available_items(self):
        produtos = [
            {"nome_produto": "SUCO BOLSA LARANJA", "preco": 41.67},
            {"nome_produto": "ALFAJOR 40G | CHOMEA", "preco": 3.69},
            {"nome_produto": "POLVILHO 090G | UNICA", "preco": 8.29},
        ]

        reply = ai_agent.non_suco_products_reply(produtos)

        self.assertIn("ALFAJOR 40G | CHOMEA", reply)
        self.assertIn("POLVILHO 090G | UNICA", reply)
        self.assertNotIn("SUCO BOLSA LARANJA", reply)

    def test_last_confirmed_order_items_are_source_of_truth(self):
        history = [
            {
                "role": "assistant",
                "content": (
                    "Ainda nao registrei o pedido.\n\n"
                    "So para confirmar, ficou assim:\n"
                    "- *SUCO BOLSA LARANJA*: tipo bolsa | tamanho 5L | quantidade 10 | unidade unidades | unit. R$ 41,67 | subtotal R$ 416,70\n"
                    "- *AGUA GARRAFA DE COCO*: tipo garrafa | tamanho 900ml | quantidade 40 | unidade unidades | unit. R$ 10,20 | subtotal R$ 408,00\n\n"
                    "Total do pedido: *R$ 824,70*"
                ),
            }
        ]

        items = ai_agent._last_confirmed_order_items(history)

        self.assertEqual(len(items), 2)
        self.assertEqual(items[1]["tipo"], "garrafa")
        self.assertEqual(items[1]["tamanho"], "900ml")
        self.assertEqual(items[1]["quantidade"], 40.0)
        self.assertEqual(items[1]["subtotal"], 408.0)

    def test_missing_fields_prompt_uses_item_label(self):
        reply = ai_agent.missing_order_fields_prompt(
            [{"produto": "Agua de coco", "quantidade": 40, "unidade": "unidades"}]
        )

        self.assertIn("AGUA DE COCO", reply)
        self.assertNotIn("Item 1", reply)

    def test_full_product_catalog_lists_products_instead_of_format_prompt(self):
        produtos = [
            {"nome_produto": "SUCO BOLSA LARANJA", "variacao": "5L", "preco": 41.67},
            {"nome_produto": "ALFAJOR 40G | CHOMEA", "preco": 3.69},
            {"nome_produto": "POLVILHO 090G | UNICA", "preco": 8.29},
        ]

        reply = ai_agent.full_product_catalog_reply(produtos, text="quais produtos voce tem e os precos?")

        upper_reply = reply.upper()
        self.assertIn("ALFAJOR", upper_reply)
        self.assertIn("POLVILHO", upper_reply)
        self.assertNotIn("Sugiro comecar pelas garrafas", reply)

    def test_common_send_confirmation_is_final(self):
        self.assertTrue(ai_agent.is_final_order_confirmation("Pode mandar aí."))
        self.assertTrue(ai_agent.is_final_order_confirmation("Nada mais, pode mandar."))

    def test_registered_order_reply_never_requests_confirmation_again(self):
        reply = ai_agent.order_registered_prompt(
            [
                {
                    "produto": "Água de Coco",
                    "tipo": "copo",
                    "tamanho": "200ml",
                    "quantidade": 20,
                    "unidade": "copos",
                    "preco_unitario": 2.60,
                    "subtotal": 52.0,
                }
            ],
            "SP-260609-ABC123",
        )

        self.assertIn("registrado para revisão", reply)
        self.assertIn("SP-260609-ABC123", reply)
        self.assertNotIn("me confirma", reply.lower())
        self.assertNotIn("se estiver tudo certo", reply.lower())

    def test_inbound_message_id_is_idempotent(self):
        store = ai_agent.AgentStore.__new__(ai_agent.AgentStore)
        store.use_local = True
        rows = []
        store._local_read = lambda _table: list(rows)
        store._local_write = lambda _table, values: rows.__setitem__(slice(None), values)

        first, first_duplicate = store.add_inbound_message_once(
            "conversation-1",
            "pedido por áudio",
            {"data": {"key": {"id": "AUDIO-1"}}},
            "AUDIO-1",
        )
        second, second_duplicate = store.add_inbound_message_once(
            "conversation-1",
            "pedido por áudio",
            {"data": {"key": {"id": "AUDIO-1"}}},
            "AUDIO-1",
        )

        self.assertFalse(first_duplicate)
        self.assertTrue(second_duplicate)
        self.assertEqual(first["id"], second["id"])
        self.assertEqual(len(rows), 1)

    def test_open_sales_question_uses_catalog_path(self):
        classification = ai_agent.classify_intent("O que voce vende ai?", [])

        self.assertEqual(classification["intent"], "product_query")
        self.assertTrue(ai_agent.is_full_product_list_request("O que voce vende ai?", classification))

    def test_unknown_order_product_is_blocked_by_catalog(self):
        produtos = [
            {"nome_produto": "SUCO GARRAFA PASTEURIZADO DE LARANJA", "variacao": "900", "preco": 8.60},
            {"nome_produto": "SUCO COPO UVA", "variacao": "200", "preco": 3.20},
        ]

        unavailable = ai_agent._unavailable_order_items(
            [{"produto": "limao", "tipo": "garrafa", "tamanho": "900ml", "quantidade": 10, "unidade": "unidades"}],
            produtos,
        )

        self.assertTrue(unavailable)
        self.assertIn("LIMAO", unavailable[0])

    def test_invalid_size_combination_is_blocked_by_catalog(self):
        produtos = [
            {"nome_produto": "SUCO GARRAFA PASTEURIZADO DE LARANJA", "variacao": "900", "preco": 8.60},
        ]

        unavailable = ai_agent._unavailable_order_items(
            [{"produto": "laranja", "tipo": "garrafa", "tamanho": "200ml", "quantidade": 10, "unidade": "unidades"}],
            produtos,
        )

        self.assertTrue(unavailable)

    def test_catalog_unavailable_prompt_blocks_blind_order_save(self):
        reply = ai_agent.catalog_unavailable_prompt()

        self.assertIn("Não consegui consultar a tabela de produtos", reply)
        self.assertIn("evitar registrar um item incorreto", reply)

    def test_conversation_guard_lists_same_type_size_alternatives_for_missing_product(self):
        produtos = [
            {"nome_produto": "SUCO COPO UVA", "variacao": "200", "preco": 3.20},
            {"nome_produto": "SUCO COPO LARANJA", "variacao": "200", "preco": 3.10},
            {"nome_produto": "SUCO GARRAFA COCO", "variacao": "900", "preco": 10.20},
        ]

        reply = ai_agent.catalog_guard_prompt("tem copo de abacate 200ml?", produtos)

        self.assertIn("Não temos abacate", reply)
        self.assertIn("opções de copo 200ml", reply)
        self.assertIn("SUCO COPO UVA", reply)
        self.assertIn("SUCO COPO LARANJA", reply)
        self.assertNotIn("- SUCO GARRAFA COCO | garrafa 900ml", reply)

    def test_conversation_guard_lists_alternatives_for_invalid_product_combination(self):
        produtos = [
            {"nome_produto": "SUCO GARRAFA COCO", "variacao": "900", "preco": 10.20},
            {"nome_produto": "SUCO COPO UVA", "variacao": "200", "preco": 3.20},
            {"nome_produto": "SUCO COPO LARANJA", "variacao": "200", "preco": 3.10},
        ]

        reply = ai_agent.catalog_guard_prompt("quero copo de coco 200ml", produtos)

        self.assertIn("não existe nessa combinação", reply)
        self.assertIn("Opções reais: garrafa 900ml", reply)
        self.assertIn("opções de copo 200ml", reply)
        self.assertIn("SUCO COPO UVA", reply)
        self.assertIn("SUCO COPO LARANJA", reply)

    def test_customer_facing_ptbr_normalizer_fixes_common_unaccented_words(self):
        text = "Nao encontrei opcoes disponiveis. Voce quer ver precos ou revisao?"

        reply = ai_agent.normalize_customer_facing_ptbr(text)

        self.assertEqual(reply, "Não encontrei opções disponíveis. Você quer ver preços ou revisão?")

    def test_catalog_replies_are_accented(self):
        produtos = [{"nome_produto": "SUCO COPO LARANJA", "variacao": "200", "preco": 3.20}]

        reply = ai_agent.product_options_reply("tem laranja?", produtos)

        self.assertIn("opções", reply)
        self.assertIn("você", reply)
        self.assertNotIn("opcoes", reply)
        self.assertNotIn("voce", reply)

    def test_compound_product_is_preserved_as_single_catalog_term(self):
        produtos = [
            {"nome_produto": "AGUA COPO DE COCO", "variacao": "200", "preco": 2.60},
            {"nome_produto": "AGUA GARRAFA DE COCO", "variacao": "900", "preco": 10.20},
        ]

        tokens = ai_agent._requested_catalog_tokens("água de coco 10 também", produtos)

        self.assertIn("agua de coco", tokens)
        self.assertNotIn("agua", tokens)
        self.assertNotIn("coco", tokens)
        self.assertNotIn("tambem", tokens)

    def test_multi_item_catalog_guard_does_not_split_agua_de_coco_or_use_common_words(self):
        produtos = [
            {"nome_produto": "SUCO BOLSA LARANJA", "variacao": "05L", "preco": 29.46},
            {"nome_produto": "CONC BOLSA LARANJA", "variacao": "05L", "preco": 41.67},
            {"nome_produto": "SUCO BOLSA GOIABA", "variacao": "05L", "preco": 27.04},
            {"nome_produto": "SUCO BOLSA CAJU", "variacao": "05L", "preco": 28.08},
            {"nome_produto": "SUCO GARRAFA HIBISCO", "variacao": "900", "preco": 10.78},
            {"nome_produto": "SUCO BOLSA MARACUJA", "variacao": "05L", "preco": 39.05},
            {"nome_produto": "AGUA COPO DE COCO", "variacao": "200", "preco": 2.60},
            {"nome_produto": "AGUA GARRAFA DE COCO", "variacao": "900", "preco": 10.20},
        ]

        reply = ai_agent.catalog_guard_prompt(
            "Beleza, então vai ser laranja concentrado 10, goiaba garrafa 20, "
            "caju bolsa 10, hibisco garrafa 10, maracujá 10, água de coco 10 também",
            produtos,
        )

        self.assertEqual("", reply)

    def test_backend_order_validation_accepts_compound_product_when_catalog_has_it(self):
        produtos = [
            {"nome_produto": "AGUA COPO DE COCO", "variacao": "200", "preco": 2.60},
            {"nome_produto": "AGUA GARRAFA DE COCO", "variacao": "900", "preco": 10.20},
        ]

        unavailable = ai_agent._unavailable_order_items(
            [{"produto": "água de coco", "tipo": "garrafa", "tamanho": "900ml", "quantidade": 10, "unidade": "unidades"}],
            produtos,
        )

        self.assertEqual([], unavailable)

    def test_complex_unpunctuated_order_is_not_intercepted_by_conversation_guard(self):
        produtos = [
            {"nome_produto": "SUCO BOLSA LARANJA", "variacao": "05L", "preco": 40.58},
            {"nome_produto": "SUCO GARRAFA LARANJA", "variacao": "900", "preco": 9.17},
            {"nome_produto": "SUCO GARRAFA LARANJA", "variacao": "1L7", "preco": 16.26},
            {"nome_produto": "SUCO GARRAFA GOIABA", "variacao": "900", "preco": 10.78},
            {"nome_produto": "SUCO GARRAFA MANGA E MARACUJA", "variacao": "900", "preco": 7.90},
        ]
        text = (
            "tá beleza então faz o seguinte vê para mim 10 bolsa laranja "
            "40 garrafa laranja de 900 40 garrafas laranja 1.7 "
            "e 10 goiaba 900 e 10 manga maracujá 900 também"
        )

        reply = ai_agent.catalog_guard_prompt(text, produtos)

        self.assertEqual("", reply)
        tokens = ai_agent._requested_catalog_tokens(text, produtos)
        self.assertNotIn("seguinte", tokens)
        self.assertNotIn("beleza", tokens)

    def test_simple_invalid_product_request_is_still_blocked_by_backend_guard(self):
        produtos = [
            {"nome_produto": "SUCO COPO LARANJA", "variacao": "200", "preco": 2.24},
            {"nome_produto": "SUCO COPO UVA", "variacao": "200", "preco": 2.60},
        ]

        reply = ai_agent.catalog_guard_prompt("quero copo de limão 200ml", produtos)

        self.assertIn("Não temos limão", reply)
        self.assertIn("opções de copo 200ml", reply)

    def test_comma_separated_product_list_validates_segments_without_requiring_repeated_trigger(self):
        produtos = [
            {"nome_produto": "SUCO GARRAFA CAJU", "variacao": "900", "preco": 6.66},
            {"nome_produto": "SUCO GARRAFA GOIABA COM HIBISCO", "variacao": "900", "preco": 10.78},
        ]

        reply = ai_agent.catalog_guard_prompt(
            "quero cajá, caju, hibisco, tamarindo",
            produtos,
        )

        self.assertIn("Não temos cajá", reply)
        self.assertIn("Não temos tamarindo", reply)

    def test_subagent_resolution_is_reconciled_against_exact_catalog_size(self):
        produtos = [
            {"cod_produto": "SGRSSUVA", "nome_produto": "NECTAR GARRAFA UVA", "variacao": "1L7", "preco": 15.81},
            {"cod_produto": "SGRSSMAR", "nome_produto": "SUCO GARRAFA MARACUJA", "variacao": "900", "preco": 8.80},
        ]
        resolution = {
            "itens": [
                {
                    "status": "ambiguo",
                    "produto": "Uva",
                    "formato": "garrafa",
                    "tamanho": "900ml",
                    "quantidade": 10,
                },
                {
                    "status": "ambiguo",
                    "produto": "Maracuja",
                    "formato": "garrafa",
                    "tamanho": "900ml",
                    "quantidade": 10,
                },
            ]
        }

        reconciled = ai_agent._reconcile_catalog_resolution(resolution, produtos)

        self.assertEqual(reconciled["itens"][0]["status"], "nao_encontrado")
        self.assertIn("garrafa 1,7L", reconciled["itens"][0]["alternativas"][0])
        self.assertEqual(reconciled["itens"][1]["status"], "encontrado")
        self.assertEqual(reconciled["itens"][1]["nome_catalogo"], "SUCO GARRAFA MARACUJA")

    def test_standalone_hibisco_does_not_match_compound_product_as_exact(self):
        produtos = [
            {
                "cod_produto": "SGRSSGOH",
                "nome_produto": "SUCO GARRAFA GOIABA COM HIBISCO",
                "variacao": "900",
                "preco": 10.78,
            }
        ]
        resolution = {
            "itens": [
                {
                    "status": "encontrado",
                    "produto": "Hibisco",
                    "formato": "garrafa",
                    "tamanho": "900ml",
                    "quantidade": 5,
                }
            ]
        }

        reconciled = ai_agent._reconcile_catalog_resolution(resolution, produtos)
        reply = ai_agent.catalog_resolution_reply(reconciled)

        self.assertEqual(reconciled["itens"][0]["status"], "nao_encontrado")
        self.assertIn("Goiaba Com Hibisco", reconciled["itens"][0]["alternativas"][0])
        self.assertIn("Não temos Hibisco em garrafa 900ml", reply)

    def test_resolved_multi_item_order_generates_single_confirmation(self):
        produtos = [
            {"cod_produto": "SCPSSCAJ", "nome_produto": "SUCO COPO CAJU", "variacao": "200", "preco": 1.72},
            {"cod_produto": "SCPSSGOI", "nome_produto": "SUCO COPO GOIABA", "variacao": "200", "preco": 1.72},
            {"cod_produto": "SCPSSLAR", "nome_produto": "SUCO COPO LARANJA 200ML", "variacao": "200", "preco": 2.24},
        ]
        resolution = {
            "itens": [
                {"produto": "Caju", "formato": "copo", "tamanho": "200ml", "quantidade": 5},
                {"produto": "Goiaba", "formato": "copo", "tamanho": "200ml", "quantidade": 5},
                {"produto": "Laranja", "formato": "copo", "tamanho": "200ml", "quantidade": 5},
            ]
        }

        reconciled = ai_agent._reconcile_catalog_resolution(resolution, produtos)
        reply = ai_agent.catalog_resolution_reply(reconciled)

        self.assertEqual([item["status"] for item in reconciled["itens"]], ["encontrado"] * 3)
        self.assertIn("Só para confirmar, ficou assim:", reply)
        self.assertNotIn("Qual formato", reply)
        self.assertNotIn("Qual tamanho", reply)

    def test_catalog_search_reaches_products_after_old_160_item_limit(self):
        produtos = [
            {
                "cod_produto": f"ITEM{i:03d}",
                "nome_produto": f"SUCO GARRAFA SABOR{i:03d}",
                "variacao": "900",
                "preco": 5.0,
            }
            for i in range(200)
        ]
        produtos.append(
            {
                "cod_produto": "SGRSSUVA",
                "nome_produto": "NECTAR GARRAFA UVA",
                "variacao": "1L7",
                "preco": 15.81,
            }
        )

        candidates = ai_agent._catalog_candidates_for_extracted_item(
            {"produto": "uva", "formato": "garrafa", "tamanho": "1,7L"},
            produtos,
        )

        self.assertEqual(candidates[0]["nome_produto"], "NECTAR GARRAFA UVA")

    def test_missing_subagent_result_is_completed_without_dropping_item(self):
        extraction = {
            "itens_solicitados": [
                {"produto": "caju", "formato": "copo", "tamanho": "200ml", "quantidade": 5},
                {"produto": "goiaba", "formato": "copo", "tamanho": "200ml", "quantidade": 10},
                {"produto": "uva", "formato": "garrafa", "tamanho": "1,7L", "quantidade": 3},
            ]
        }
        partial = {
            "itens": [
                {
                    "indice_item": 0,
                    "produto": "caju",
                    "status": "encontrado",
                    "formato": "copo",
                    "tamanho": "200ml",
                    "quantidade": 5,
                },
                {
                    "indice_item": 2,
                    "produto": "uva",
                    "status": "encontrado",
                    "formato": "garrafa",
                    "tamanho": "1,7L",
                    "quantidade": 3,
                },
            ]
        }
        produtos = [
            {"nome_produto": "SUCO COPO CAJU", "variacao": "200", "preco": 1.72},
            {"nome_produto": "SUCO COPO GOIABA", "variacao": "200", "preco": 1.72},
            {"nome_produto": "NECTAR GARRAFA UVA", "variacao": "1L7", "preco": 15.81},
        ]

        completed = ai_agent._complete_resolution_items(partial, extraction, produtos)

        self.assertEqual(len(completed["itens"]), 3)
        self.assertEqual(completed["itens"][1]["produto"], "goiaba")
        self.assertEqual(completed["itens"][1]["status"], "ambiguo")
        self.assertTrue(completed["completion_repaired"])


if __name__ == "__main__":
    unittest.main()
