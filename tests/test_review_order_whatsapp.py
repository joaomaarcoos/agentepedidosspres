import sys
import unittest
import os
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "execution"))

import review_order_whatsapp


class _FakeResult:
    def __init__(self, data):
        self.data = data


class _FakeTable:
    def __init__(self, db, name):
        self.db = db
        self.name = name
        self.filters = {}

    def select(self, *_args, **_kwargs):
        return self

    def eq(self, key, value):
        self.filters[key] = value
        return self

    def in_(self, key, value):
        self.filters[key] = value
        return self

    def limit(self, *_args, **_kwargs):
        return self

    def order(self, *_args, **_kwargs):
        return self

    def execute(self):
        self.db.queries.append((self.name, dict(self.filters)))
        if self.name == "system_settings":
            key = self.filters.get("key")
            return _FakeResult(self.db.settings.get(key, []))
        if self.name == "pedidos_revisao":
            protocolo = self.filters.get("protocolo")
            return _FakeResult(self.db.orders.get(protocolo, []))
        if self.name == "clic_clientes":
            phone = self.filters.get("telefone")
            phones = phone if isinstance(phone, list) else [phone]
            rows = []
            for candidate in phones:
                rows.extend(self.db.customers_by_phone.get(candidate, []))
            return _FakeResult(rows)
        if self.name == "clic_pedidos_integrados":
            cpf = self.filters.get("cpf_cnpj")
            return _FakeResult(self.db.integrated_orders_by_cpf.get(cpf, []))
        return _FakeResult([])


class _FakeDb:
    def __init__(self):
        self.queries = []
        self.settings = {
            "evolution_instance_owner__rep-01": [
                {"key": "evolution_instance_owner__rep-01", "value": {"cod_rep": 123}}
            ]
        }
        self.orders = {}
        self.customers_by_phone = {
            "5511888888888": [{"cpf_cnpj": "00000000000200", "telefone": "5511888888888"}]
        }
        self.integrated_orders_by_cpf = {
            "00000000000200": [
                {
                    "raw_json": {
                        "cliente": {"fantasia": "João Fake"},
                        "representante": {"backoffice": {"codigo": "205"}},
                    }
                }
            ]
        }

    def table(self, name):
        return _FakeTable(self, name)


class ReviewOrderWhatsappTests(unittest.TestCase):
    def test_customer_like_command_is_not_treated_as_representative(self):
        db = _FakeDb()

        with patch.object(review_order_whatsapp, "_db", return_value=db), patch.object(
            review_order_whatsapp,
            "_fetch_instances",
            return_value=[{"instanceName": "rep-01", "phoneNumber": "5511999999999"}],
        ):
            result = review_order_whatsapp.process_representative_order_command(
                phone="5511888888888",
                text="pode aprovar SP-260608-ABC123?",
                instance_name="rep-01",
            )

        self.assertIsNone(result)
        self.assertNotIn(("pedidos_revisao", {"protocolo": "SP-260608-ABC123"}), db.queries)

    def test_instance_owner_keeps_representative_operational_flow(self):
        db = _FakeDb()

        with patch.object(review_order_whatsapp, "_db", return_value=db), patch.object(
            review_order_whatsapp,
            "_fetch_instances",
            return_value=[{"instanceName": "rep-01", "phoneNumber": "5511999999999"}],
        ):
            result = review_order_whatsapp.process_representative_order_command(
                phone="5511999999999",
                text="aprovado SP-260608-ABC123",
                instance_name="rep-01",
            )

        self.assertEqual(result["action"], "review_order_not_found")
        self.assertIn("SP-260608-ABC123", result["reply"])

    def test_latest_rep_uses_integrated_order_history(self):
        db = _FakeDb()

        cod_rep = review_order_whatsapp._latest_rep_for_customer(
            db,
            {"cliente_telefone": "5511888888888"},
        )

        self.assertEqual(cod_rep, 205)

    def test_customer_name_falls_back_to_integrated_order_history(self):
        db = _FakeDb()

        name = review_order_whatsapp._customer_name_from_history(
            db,
            {"cliente_telefone": "5511888888888"},
        )

        self.assertEqual(name, "João Fake")

    def test_representative_assistant_uses_operational_context(self):
        db = _FakeDb()
        db.settings["evolution_instance_owner__rep-01"] = [
            {
                "key": "evolution_instance_owner__rep-01",
                "value": {"cod_rep": 205, "owner_phone": "5511999999999"},
            }
        ]
        order = {
            "id": "order-1",
            "protocolo": "SP-260608-ABC123",
            "status": "pendente",
            "cliente_nome": "João Fake",
            "cliente_telefone": "5511888888888",
            "itens_json": [],
        }

        with patch.object(review_order_whatsapp, "_db", return_value=db), patch.object(
            review_order_whatsapp, "_fetch_instances", return_value=[]
        ), patch.object(
            review_order_whatsapp, "_representative_review_orders", return_value=[order]
        ), patch.dict(os.environ, {"OPENAI_API_KEY": ""}):
            result = review_order_whatsapp.process_representative_message(
                phone="5511999999999",
                text="Quais pedidos estão pendentes?",
                instance_name="rep-01",
            )

        self.assertEqual(result["action"], "representative_assistant_reply")
        self.assertIn("SP-260608-ABC123", result["reply"])
        self.assertNotIn("produto", result["reply"].lower())


if __name__ == "__main__":
    unittest.main()
