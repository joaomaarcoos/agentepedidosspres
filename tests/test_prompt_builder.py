import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from prompts.builder import _ordered_parts, build_prompt


class PromptBuilderTests(unittest.TestCase):
    def test_prompt_order_is_official(self):
        self.assertEqual(
            _ordered_parts(),
            [
                "system.md",
                "personality.md",
                "business_rules.md",
                "order_flow.md",
                "sales_strategy.md",
                "examples.md",
            ],
        )

    def test_tools_prompt_is_not_included(self):
        prompt = build_prompt()

        self.assertNotIn("# Capacidades Operacionais", prompt)
        self.assertNotIn("tools.md", _ordered_parts())

    def test_conflicting_product_list_instruction_is_removed(self):
        prompt = build_prompt()

        self.assertNotIn('nao envie a lista completa direto', prompt.lower())
        self.assertIn("Em pergunta aberta sobre produtos, liste poucas opcoes reais", prompt)

    def test_base_prompt_size_stays_bounded(self):
        prompt = build_prompt()

        self.assertLess(len(prompt), 22000)

    def test_dynamic_decision_section_is_not_full_manual(self):
        prompt = build_prompt(
            {
                "classified_intent": {"intent": "order_request", "confidence": 0.75, "entities": {}},
                "conversation_state": {"order_in_progress": True},
            }
        )

        self.assertIn("## DECISAO OPERACIONAL DO ATENDIMENTO", prompt)
        self.assertNotIn("Nunca escolha a primeira variacao da lista como padrao", prompt)

    def test_catalog_resolution_subagent_section_is_included(self):
        prompt = build_prompt(
            {
                "catalog_resolution": {
                    "source": "order_resolution_subagent",
                    "itens": [
                        {
                            "status": "encontrado",
                            "nome_catalogo": "SUCO COPO AGUA COCO",
                            "formato": "copo",
                            "tamanho": "200ml",
                            "quantidade": 10,
                        }
                    ],
                    "orientacao_para_marcela": "Monte o resumo do pedido.",
                }
            }
        )

        self.assertIn("## ANALISE DO SUBAGENTE DE PRODUTOS E PEDIDO", prompt)
        self.assertIn("SUCO COPO AGUA COCO", prompt)
        self.assertIn("Nao exponha ao cliente que existe subagente", prompt)


if __name__ == "__main__":
    unittest.main()
