import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "execution"))

import ai_agent


class AiAgentRegressionTests(unittest.TestCase):
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

        self.assertIn("Nao consegui consultar a tabela de produtos", reply)
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


if __name__ == "__main__":
    unittest.main()
