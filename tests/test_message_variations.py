import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "execution"))

import ai_agent


CATALOG = [
    {"nome_produto": "SUCO BOLSA LARANJA", "variacao": "05L", "preco": 40.58},
    {"nome_produto": "CONC BOLSA LARANJA", "variacao": "05L", "preco": 41.67},
    {"nome_produto": "SUCO COPO LARANJA 200ML", "variacao": "200", "preco": 2.24},
    {"nome_produto": "SUCO GARRAFA LARANJA", "variacao": "900", "preco": 9.17},
    {"nome_produto": "SUCO GARRAFA LARANJA", "variacao": "1L7", "preco": 16.26},
    {"nome_produto": "SUCO GARRAFA CAJU", "variacao": "900", "preco": 6.66},
    {"nome_produto": "SUCO GARRAFA GOIABA", "variacao": "900", "preco": 6.66},
    {"nome_produto": "SUCO GARRAFA GOIABA COM HIBISCO", "variacao": "900", "preco": 10.78},
    {"nome_produto": "SUCO GARRAFA MANGA E MARACUJA", "variacao": "900", "preco": 7.90},
    {"nome_produto": "SUCO GARRAFA MARACUJA 900 ML", "variacao": "900", "preco": 8.80},
    {"nome_produto": "AGUA COPO DE COCO", "variacao": "200", "preco": 2.60},
    {"nome_produto": "AGUA GARRAFA DE COCO", "variacao": "900", "preco": 10.20},
    {"nome_produto": "ALFAJOR 40G | CHOMEA", "variacao": "CHOMEA", "preco": 3.69},
]


class MessageVariationTests(unittest.TestCase):
    def test_intent_variations(self):
        cases = [
            ("oi", "greeting"),
            ("bom dia marcela", "greeting"),
            ("quero fazer um pedido", "order_request"),
            ("monta um pedido para mim", "order_request"),
            ("quanto custa a garrafa de laranja?", "price_query"),
            ("tem água de coco?", "product_query"),
            ("quais produtos vocês têm?", "product_query"),
            ("quero ver as opções de garrafa", "product_query"),
            ("qual foi meu último pedido?", "history_query"),
            ("repete o mesmo pedido", "repeat_order"),
            ("qual o prazo de entrega?", "delivery_query"),
        ]
        for text, expected in cases:
            with self.subTest(text=text):
                self.assertEqual(expected, ai_agent.classify_intent(text, [])["intent"])

    def test_simple_valid_specific_requests_are_not_blocked(self):
        cases = [
            "quero garrafa de laranja 900ml",
            "tem copo de laranja 200ml?",
            "adicione água de coco garrafa 900ml",
            "quero manga e maracujá garrafa 900ml",
        ]
        for text in cases:
            with self.subTest(text=text):
                self.assertEqual("", ai_agent.catalog_guard_prompt(text, CATALOG))

    def test_exploratory_queries_do_not_trigger_order_validation(self):
        cases = [
            "oi Marcela, tudo bem?",
            "quais sabores vocês têm?",
            "tem água de coco?",
        ]
        for text in cases:
            with self.subTest(text=text):
                self.assertEqual("", ai_agent.catalog_guard_prompt(text, CATALOG))

        reply = ai_agent.product_options_reply("tem água de coco?", CATALOG)
        self.assertIn("água de coco", reply)
        self.assertIn("copo 200ml", reply)
        self.assertIn("garrafa 900ml", reply)

    def test_simple_invalid_requests_are_blocked_with_relevant_alternatives(self):
        cases = [
            ("quero copo de limão 200ml", "Não temos limão", "copo 200ml"),
            ("tem água de coco em bolsa?", "não existe nessa combinação", "água de coco"),
            ("quero garrafa de caju 200ml", "não existe nessa combinação", "garrafa 900ml"),
            ("tem tamarindo em garrafa?", "Não temos tamarindo", "garrafa"),
        ]
        for text, expected_error, expected_option in cases:
            with self.subTest(text=text):
                reply = ai_agent.catalog_guard_prompt(text, CATALOG)
                self.assertIn(expected_error, reply)
                self.assertIn(expected_option, reply.lower())
                self.assertNotIn("ALFAJOR", reply)

    def test_compound_product_variations_are_preserved(self):
        cases = [
            ("água de coco", "agua de coco"),
            ("agua de coco", "agua de coco"),
            ("manga e maracujá", "manga e maracuja"),
            ("manga com maracujá", "manga com maracuja"),
        ]
        for text, expected in cases:
            with self.subTest(text=text):
                tokens = ai_agent._requested_catalog_tokens(
                    f"quero {text} 10 unidades",
                    CATALOG,
                )
                self.assertIn(expected, tokens)

    def test_conversational_fillers_never_become_products(self):
        text = (
            "tá beleza então faz o seguinte vê para mim 10 de laranja "
            "e também coloca água de coco"
        )
        tokens = ai_agent._requested_catalog_tokens(text, CATALOG)
        for forbidden in ("beleza", "seguinte", "tambem", "entao", "faz", "mim"):
            with self.subTest(token=forbidden):
                self.assertNotIn(forbidden, tokens)

    def test_complex_spoken_orders_bypass_conversation_guard(self):
        cases = [
            (
                "10 bolsa laranja 40 garrafa laranja 900 "
                "40 garrafa laranja 1.7 e 10 goiaba 900"
            ),
            (
                "coloca 10 laranja bolsa depois 20 caju garrafa 900 "
                "e mais 10 água de coco garrafa 900"
            ),
            (
                "quero laranja bolsa 10 goiaba garrafa 20 "
                "manga e maracujá garrafa 10 tudo 900"
            ),
        ]
        for text in cases:
            with self.subTest(text=text):
                self.assertTrue(ai_agent._catalog_request_is_complex(text, CATALOG))
                self.assertEqual("", ai_agent.catalog_guard_prompt(text, CATALOG))

    def test_real_audio_multi_item_order_is_not_blocked_by_catalog_guard(self):
        produtos = CATALOG + [
            {"nome_produto": "SUCO COPO LARANJA 115ML", "variacao": "115", "preco": 1.33},
            {"nome_produto": "SUCO COPO MACA 115ML", "variacao": "115", "preco": 1.37},
            {"nome_produto": "SUCO COPO GOIABA", "variacao": "200", "preco": 1.72},
            {"nome_produto": "SUCO COPO CAJU", "variacao": "200", "preco": 1.72},
        ]
        cases = [
            (
                "Eu quero água de coco, copo de 200ml, eu quero 10 unidades, "
                "quero 10 unidades de laranja de 115ml e 10 unidades de maracujá de 200ml."
            ),
            (
                "Água de coco, eu quero o copo de 200ml, 10 unidades. "
                "E quero também o copo de maçã de 115ml, 10 unidades também. "
                "O mesmo coisa para o copo de laranja, também quero esse."
            ),
        ]

        for text in cases:
            with self.subTest(text=text):
                self.assertTrue(ai_agent._catalog_request_is_complex(text, produtos))
                self.assertEqual("", ai_agent.catalog_guard_prompt(text, produtos))

    def test_number_words_are_not_catalog_products(self):
        produtos = CATALOG + [
            {"nome_produto": "SUCO COPO GOIABA", "variacao": "200", "preco": 1.72},
            {"nome_produto": "SUCO COPO CAJU", "variacao": "200", "preco": 1.72},
        ]
        cases = [
            "Quero cinco copos de goiaba de 200ml.",
            "Eu quero um copo de caju, vinte unidades.",
        ]

        for text in cases:
            with self.subTest(text=text):
                reply = ai_agent.catalog_guard_prompt(text, produtos)
                self.assertNotIn("Não temos cinco", reply)
                self.assertNotIn("Não temos vinte", reply)

    def test_order_resolution_subagent_trigger_is_specific(self):
        self.assertTrue(
            ai_agent._should_run_order_resolution_agent(
                "quero água de coco copo 200ml, 10 unidades",
                {"intent": "order_request"},
                CATALOG,
            )
        )
        self.assertFalse(
            ai_agent._should_run_order_resolution_agent(
                "quais produtos vocês têm?",
                {"intent": "product_query"},
                CATALOG,
            )
        )

    def test_comma_separated_lists_validate_each_segment(self):
        reply = ai_agent.catalog_guard_prompt(
            "quero cajá, caju, tamarindo, água de coco",
            CATALOG,
        )
        self.assertIn("Não temos cajá", reply)
        self.assertIn("Não temos tamarindo", reply)
        self.assertNotIn("Não temos caju", reply)
        self.assertNotIn("- agua:", reply.lower())
        self.assertNotIn("- coco:", reply.lower())

    def test_backend_save_guard_accepts_only_exact_catalog_combinations(self):
        valid_items = [
            {"produto": "laranja", "tipo": "garrafa", "tamanho": "900ml", "quantidade": 10, "unidade": "unidades"},
            {"produto": "água de coco", "tipo": "copo", "tamanho": "200ml", "quantidade": 10, "unidade": "unidades"},
            {"produto": "manga e maracujá", "tipo": "garrafa", "tamanho": "900ml", "quantidade": 10, "unidade": "unidades"},
        ]
        invalid_items = [
            {"produto": "limão", "tipo": "copo", "tamanho": "200ml", "quantidade": 10, "unidade": "unidades"},
            {"produto": "água de coco", "tipo": "bolsa", "tamanho": "5L", "quantidade": 10, "unidade": "unidades"},
            {"produto": "caju", "tipo": "garrafa", "tamanho": "200ml", "quantidade": 10, "unidade": "unidades"},
        ]

        self.assertEqual([], ai_agent._unavailable_order_items(valid_items, CATALOG))
        self.assertEqual(3, len(ai_agent._unavailable_order_items(invalid_items, CATALOG)))

    def test_confirmation_language_variations(self):
        positive = [
            "sim",
            "pode mandar",
            "pode registrar",
            "está tudo certo",
            "confirmo",
            "nada mais, pode fechar",
        ]
        negative = [
            "adiciona mais 10",
            "troca o tamanho",
            "qual é o preço?",
            "tira a água de coco",
        ]
        for text in positive:
            with self.subTest(text=text):
                self.assertTrue(ai_agent.is_final_order_confirmation(text))
        for text in negative:
            with self.subTest(text=text):
                self.assertFalse(ai_agent.is_final_order_confirmation(text))


if __name__ == "__main__":
    unittest.main()
