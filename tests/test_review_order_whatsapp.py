import sys
import unittest
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

    def limit(self, *_args, **_kwargs):
        return self

    def execute(self):
        self.db.queries.append((self.name, dict(self.filters)))
        if self.name == "system_settings":
            key = self.filters.get("key")
            return _FakeResult(self.db.settings.get(key, []))
        if self.name == "pedidos_revisao":
            protocolo = self.filters.get("protocolo")
            return _FakeResult(self.db.orders.get(protocolo, []))
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


if __name__ == "__main__":
    unittest.main()
