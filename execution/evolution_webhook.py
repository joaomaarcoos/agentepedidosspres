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
import re
import sys
import time
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
REPLY_SPLIT_MAX_CHARS = int(os.getenv("AI_REPLY_SPLIT_MAX_CHARS", "450"))
REPLY_SPLIT_DELAY_SECONDS = float(os.getenv("AI_REPLY_SPLIT_DELAY_SECONDS", "0.8"))


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


def _jid_phone(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    return normalize_phone(raw.split("@", 1)[0])


def _message_remote_jid(payload: dict, data: dict, key: dict) -> str:
    return str(
        key.get("remoteJid")
        or data.get("remoteJid")
        or _dig(data, "contact", "remoteJid")
        or _dig(payload, "contact", "remoteJid")
        or _dig(data, "message", "key", "remoteJid")
        or ""
    )


def _message_participant_jid(payload: dict, data: dict, key: dict) -> str:
    return str(
        key.get("participant")
        or data.get("participant")
        or _dig(data, "contextInfo", "participant")
        or _dig(payload, "participant")
        or ""
    )


def _get_audio_base64(payload: dict, instance: str) -> tuple[str, str] | None:
    """Baixa mídia de áudio da Evolution API e retorna (base64, mimetype) ou None."""
    try:
        api_url, api_key = _evolution_config()
        data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
        body = {"message": {"key": data.get("key") or {}, "message": data.get("message") or {}}}
        resp = requests.post(
            f"{api_url}/chat/getBase64FromMediaMessage/{instance}",
            json=body,
            headers={"apikey": api_key, "Content-Type": "application/json"},
            timeout=30,
        )
        resp.raise_for_status()
        result = resp.json()
        b64 = result.get("base64") or _dig(result, "data", "base64") or ""
        mimetype = result.get("mimetype") or "audio/ogg"
        if b64:
            return b64, mimetype
    except Exception as exc:
        logger.warning("Falha ao baixar áudio da Evolution API: %s", exc)
    return None


def _transcribe_audio(base64_str: str, mimetype: str = "audio/ogg") -> str | None:
    """Transcreve áudio com OpenAI Whisper. Retorna texto ou None."""
    import base64 as _b64
    import tempfile

    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        logger.warning("OPENAI_API_KEY ausente — transcrição de áudio desativada")
        return None
    try:
        from openai import OpenAI

        audio_bytes = _b64.b64decode(base64_str)
        ext = "ogg"
        if "mp4" in mimetype or "mpeg" in mimetype:
            ext = "mp3"
        elif "wav" in mimetype:
            ext = "wav"
        elif "webm" in mimetype:
            ext = "webm"

        with tempfile.NamedTemporaryFile(suffix=f".{ext}", delete=False) as f:
            f.write(audio_bytes)
            tmp_path = f.name
        try:
            client = OpenAI(api_key=api_key)
            with open(tmp_path, "rb") as audio_file:
                transcript = client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    language="pt",
                )
            text = transcript.text.strip()
            logger.info("Áudio transcrito (%d chars): %s", len(text), text[:120])
            return text
        finally:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass
    except Exception as exc:
        logger.warning("Falha na transcrição Whisper: %s", exc)
        return None


def extract_message(payload: dict, instance: str = "") -> dict:
    data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
    key = data.get("key") if isinstance(data.get("key"), dict) else {}
    message = data.get("message") if isinstance(data.get("message"), dict) else {}

    remote_jid = _message_remote_jid(payload, data, key)
    participant_jid = _message_participant_jid(payload, data, key)
    from_me = bool(key.get("fromMe") or data.get("fromMe"))
    text = (
        message.get("conversation")
        or _dig(message, "extendedTextMessage", "text")
        or data.get("messageText")
        or data.get("text")
        or ""
    )

    is_audio = False
    if not text and (message.get("audioMessage") or message.get("pttMessage")):
        is_audio = True
        if instance:
            audio_data = _get_audio_base64(payload, instance)
            if audio_data:
                transcribed = _transcribe_audio(*audio_data)
                if transcribed:
                    text = transcribed

    # Em conversas diretas, remoteJid é o cliente. Em grupos, remoteJid é o grupo
    # e participant é o remetente real. Nunca use payload.sender aqui: na Evolution
    # ele pode ser o número/identificador da instância (a Marcela).
    if "@g.us" in str(remote_jid) and participant_jid:
        phone = _jid_phone(participant_jid)
    else:
        phone = _jid_phone(remote_jid)
    message_id = key.get("id") or data.get("id") or data.get("messageId")

    return {
        "phone": phone,
        "text": str(text or "").strip(),
        "from_me": from_me,
        "message_id": message_id,
        "remote_jid": remote_jid,
        "participant_jid": participant_jid,
        "is_audio": is_audio,
    }


def _evolution_config() -> tuple[str, str]:
    api_url = os.getenv("EVOLUTION_API_URL", "").rstrip("/")
    api_key = os.getenv("EVOLUTION_API_KEY", "")
    if not api_url or not api_key:
        raise RuntimeError("EVOLUTION_API_URL e EVOLUTION_API_KEY nao configurados")
    return api_url, api_key


def send_whatsapp(phone: str, text: str, instance: str) -> dict:
    api_url, api_key = _evolution_config()
    text = normalize_whatsapp_markdown(text)
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


def normalize_whatsapp_markdown(text: str) -> str:
    text = str(text or "")
    text = re.sub(r"\*\*([^\n*][^*]*?[^\n*])\*\*", r"*\1*", text)
    text = re.sub(r"__([^\n_][^_]*?[^\n_])__", r"_\1_", text)
    return text


def split_reply(text: str, max_chars: int = REPLY_SPLIT_MAX_CHARS) -> list[str]:
    text = str(text or "").strip()
    if not text:
        return []
    text = re.sub(r"<br\s*/?>", "\n\n", text, flags=re.IGNORECASE)
    if max_chars <= 0 or len(text) <= max_chars:
        return [part.strip() for part in re.split(r"\n{2,}", text) if part.strip()] or [text]

    chunks: list[str] = []
    paragraphs = [p.strip() for p in re.split(r"\n{2,}", text) if p.strip()]
    current = ""

    def flush_current() -> None:
        nonlocal current
        if current.strip():
            chunks.append(current.strip())
            current = ""

    for paragraph in paragraphs or [text]:
        if len(paragraph) > max_chars:
            flush_current()
            sentences = re.split(r"(?<=[.!?])\s+", paragraph)
            sentence_current = ""
            for sentence in sentences:
                sentence = sentence.strip()
                if not sentence:
                    continue
                if len(sentence) > max_chars:
                    if sentence_current:
                        chunks.append(sentence_current.strip())
                        sentence_current = ""
                    for index in range(0, len(sentence), max_chars):
                        chunks.append(sentence[index : index + max_chars].strip())
                    continue
                candidate = f"{sentence_current} {sentence}".strip()
                if len(candidate) <= max_chars:
                    sentence_current = candidate
                else:
                    chunks.append(sentence_current.strip())
                    sentence_current = sentence
            if sentence_current:
                chunks.append(sentence_current.strip())
            continue

        candidate = f"{current}\n\n{paragraph}".strip() if current else paragraph
        if len(candidate) <= max_chars:
            current = candidate
        else:
            flush_current()
            current = paragraph

    flush_current()
    return [chunk for chunk in chunks if chunk]


def _is_agent_enabled(instance: str) -> bool:
    if not instance:
        return True

    key = f"agent_instance__{instance}"
    supabase_url = os.getenv("SUPABASE_URL", "").rstrip("/")
    supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_ANON_KEY", "")

    if supabase_url and supabase_key:
        try:
            from supabase import create_client
            sb = create_client(supabase_url, supabase_key)
            res = sb.table("system_settings").select("value").eq("key", key).limit(1).execute()
            rows = res.data or []
            if rows:
                return bool(rows[0]["value"])
        except Exception as exc:
            logger.warning("Falha ao checar agent_enabled no Supabase: %s", exc)

    fallback_path = Path(__file__).resolve().parent.parent / ".tmp" / "data" / "agent_settings.json"
    if fallback_path.exists():
        try:
            import json as _json
            data = _json.loads(fallback_path.read_text(encoding="utf-8"))
            if key in data:
                return bool(data[key])
        except Exception:
            pass

    return True


def handle_payload(payload: dict, send_reply: bool = True) -> dict:
    # Instance name comes from the payload — no hardcoded prefix
    instance = (
        payload.get("instance")
        or payload.get("instanceName")
        or payload.get("sender")
        or ""
    )

    incoming = extract_message(payload, instance=instance)

    if incoming["from_me"]:
        return {"action": "ignored_from_me", "should_reply": False}
    if not incoming["phone"] or not incoming["text"]:
        return {"action": "ignored_empty", "should_reply": False}

    if not _is_agent_enabled(instance):
        return {"action": "agent_disabled", "should_reply": False}

    result = process_inbound_message(
        phone=incoming["phone"],
        text=incoming["text"],
        payload_json=payload,
        conversation_key=incoming["phone"],
    )

    if send_reply and result.get("should_reply") and result.get("reply"):
        reply_parts = split_reply(result["reply"])
        responses = []
        for index, part in enumerate(reply_parts):
            if index > 0 and REPLY_SPLIT_DELAY_SECONDS > 0:
                time.sleep(REPLY_SPLIT_DELAY_SECONDS)
            responses.append(send_whatsapp(incoming["phone"], part, instance))
        result["reply_parts"] = reply_parts
        result["evolution_response"] = responses[0] if len(responses) == 1 else responses

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
