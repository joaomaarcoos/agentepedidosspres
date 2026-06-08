import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "execution"))

import evolution_webhook


class EvolutionWebhookTests(unittest.TestCase):
    def _payload(self):
        return {
            "instance": "rep-01",
            "data": {
                "key": {
                    "remoteJid": "5511999999999@s.whatsapp.net",
                    "fromMe": True,
                    "id": "MSG1",
                },
                "message": {"conversation": "Oi, Marcela"},
            },
        }

    def test_from_me_owner_can_talk_to_ai(self):
        with patch.object(evolution_webhook, "_is_agent_enabled", return_value=True), patch.object(
            evolution_webhook, "process_representative_order_command", return_value=None
        ), patch.object(evolution_webhook, "is_instance_owner_phone", return_value=True), patch.object(
            evolution_webhook,
            "process_inbound_message",
            return_value={"action": "ai_reply", "should_reply": False, "reply": "Olá"},
        ) as process_inbound:
            result = evolution_webhook.handle_payload(self._payload(), send_reply=False)

        self.assertEqual(result["action"], "ai_reply")
        process_inbound.assert_called_once()

    def test_from_me_non_owner_stays_ignored(self):
        with patch.object(evolution_webhook, "_is_agent_enabled", return_value=True), patch.object(
            evolution_webhook, "process_representative_order_command", return_value=None
        ), patch.object(evolution_webhook, "is_instance_owner_phone", return_value=False), patch.object(
            evolution_webhook, "process_inbound_message"
        ) as process_inbound:
            result = evolution_webhook.handle_payload(self._payload(), send_reply=False)

        self.assertEqual(result["action"], "ignored_from_me")
        process_inbound.assert_not_called()


if __name__ == "__main__":
    unittest.main()
