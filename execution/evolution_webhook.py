"""
Processa eventos MESSAGES_UPSERT da Evolution API e aplica o atendimento da IA.

Uso:
  python execution/evolution_webhook.py --payload-json "{...}"
  python execution/evolution_webhook.py --payload-file payload.json
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv

from ai_agent import normalize_phone, process_inbound_message

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)],
)
logger = logging.getLogger(__name__)


def emit(payload: dict) -> None:
    sys.stdout.write(json.dumps(payload, ensure_ascii=False, default=str))
    sys.stdout.write("\n")


def success(data: dict) -> int:
    emit({"ok": True, "data": data})
    return 0


def failure(message: str) -> int:
    emit({"ok": False, "error": message})
    return 0


def _dig(data: dict, *path: str) -> Any:
    value: Any = data
    for key in path:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value


def extract_message(payload: dict) -> dict:
    data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
    key = data.get("key") if isinstance(data.get("key"), dict) else {}
    message = data.get("message") if isinstance(data.get("message"), dict) else {}

    remote_jid = (
        key.get("remoteJid")
        or data.get("remoteJid")
        or _dig(payload, "sender")
        or _dig(payload, "contact", "remoteJid")
        or ""
    )
    from_me = bool(key.get("fromMe") or data.get("fromMe"))
    text = (
        message.get("conversation")
        or _dig(message, "extendedTextMessage", "text")
        or data.get("messageText")
        or data.get("text")
        or ""
    )

    phone = normalize_phone(str(remote_jid).split("@", 1)[0])
    message_id = key.get("id") or data.get("id") or data.get("messageId")

    return {
        "phone": phone,
        "text": str(text or "").strip(),
        "from_me": from_me,
        "message_id": message_id,
        "remote_jid": remote_jid,
    }


def _evolution_config() -> tuple[str, str, str]:
    api_url = os.getenv("EVOLUTION_API_URL", "").rstrip("/")
    api_key = os.getenv("EVOLUTION_API_KEY", "")
    instance = (
        os.getenv("EVOLUTION_INSTANCE")
        or os.getenv("EVOLUTION_INSTANCE_NAME")
        or os.getenv("EVOLUTION_INSTANCE_ID")
        or ""
    )
    if not api_url or not api_key or not instance:
        raise RuntimeError("EVOLUTION_API_URL, EVOLUTION_API_KEY e EVOLUTION_INSTANCE nao configurados")
    return api_url, api_key, instance


def send_whatsapp(phone: str, text: str) -> dict:
    api_url, api_key, instance = _evolution_config()
    response = requests.post(
        f"{api_url}/message/sendText/{instance}",
        json={"number": f"{phone}@s.whatsapp.net", "text": text},
        headers={"apikey": api_key, "Content-Type": "application/json"},
        timeout=20,
    )
    response.raise_for_status()
    try:
        return response.json()
    except ValueError:
        return {"status_code": response.status_code, "text": response.text[:500]}


def handle_payload(payload: dict, send_reply: bool = True) -> dict:
    incoming = extract_message(payload)

    if incoming["from_me"]:
        return {"action": "ignored_from_me", "should_reply": False}
    if not incoming["phone"] or not incoming["text"]:
        return {"action": "ignored_empty", "should_reply": False}

    result = process_inbound_message(
        phone=incoming["phone"],
        text=incoming["text"],
        payload_json=payload,
        conversation_key=incoming["phone"],
    )

    if send_reply and result.get("should_reply") and result.get("reply"):
        result["evolution_response"] = send_whatsapp(incoming["phone"], result["reply"])

    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Webhook Evolution -> IA de atendimento")
    parser.add_argument("--payload-json", default="")
    parser.add_argument("--payload-file", default="")
    parser.add_argument("--no-send", action="store_true")
    args = parser.parse_args()

    try:
        if args.payload_file:
            payload = json.loads(Path(args.payload_file).read_text(encoding="utf-8"))
        elif args.payload_json:
            payload = json.loads(args.payload_json)
        else:
            payload = json.loads(sys.stdin.read())

        return success(handle_payload(payload, send_reply=not args.no_send))
    except Exception as exc:
        logger.exception("Falha no webhook da Evolution")
        return failure(str(exc))


if __name__ == "__main__":
    raise SystemExit(main())
