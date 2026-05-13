"""
ai_agent.py
===========
Core de atendimento WhatsApp com controle de pausa.

Regras:
- "##" pausa a IA por 5 horas.
- "###" despausa imediatamente.
- Pausa expirada e removida automaticamente no proximo evento.
- O contexto enviado para a IA usa apenas as ultimas 10 mensagens salvas.
"""

from __future__ import annotations

import json
import logging
import os
import re
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

logger = logging.getLogger(__name__)

PAUSE_TRIGGER = "##"
RESUME_TRIGGER = "###"
PAUSE_HOURS = int(os.getenv("AI_PAUSE_HOURS", "5"))
CONTEXT_MESSAGE_LIMIT = int(os.getenv("AI_CONTEXT_MESSAGE_LIMIT", "10"))
LOCAL_DATA_DIR = Path(__file__).resolve().parent.parent / ".tmp" / "data"
CONVERSATIONS_TABLE = "ai_conversations"
MESSAGES_TABLE = "ai_conversation_messages"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso_z(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_dt(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def normalize_phone(value: str | None) -> str:
    digits = re.sub(r"\D", "", str(value or ""))
    if digits.startswith("55") and len(digits) >= 12:
        return digits
    return digits


def normalize_text(value: str | None) -> str:
    return str(value or "").strip()


class AgentStore:
    def __init__(self) -> None:
        self.supabase_url = os.getenv("SUPABASE_URL", "").strip()
        self.supabase_key = (
            os.getenv("SUPABASE_SERVICE_ROLE_KEY")
            or os.getenv("SUPABASE_ANON_KEY")
            or ""
        ).strip()
        self.use_local = not (self.supabase_url and self.supabase_key)
        self.client = None

        if self.use_local:
            LOCAL_DATA_DIR.mkdir(parents=True, exist_ok=True)
            return

        try:
            from supabase import create_client

            self.client = create_client(self.supabase_url, self.supabase_key)
        except Exception as exc:
            logger.warning("Falha ao inicializar Supabase; usando JSON local: %s", exc)
            self.use_local = True
            LOCAL_DATA_DIR.mkdir(parents=True, exist_ok=True)

    def get_or_create_conversation(self, conversation_key: str, phone: str) -> dict:
        if self.use_local:
            return self._local_get_or_create_conversation(conversation_key, phone)

        try:
            result = (
                self.client.table(CONVERSATIONS_TABLE)
                .select("*")
                .eq("conversation_key", conversation_key)
                .limit(1)
                .execute()
            )
            rows = result.data or []
            if rows:
                return rows[0]

            now = iso_z(utc_now())
            payload = {
                "conversation_key": conversation_key,
                "phone": phone,
                "ai_paused": False,
                "created_at": now,
                "updated_at": now,
            }
            created = self.client.table(CONVERSATIONS_TABLE).insert(payload).execute()
            if created.data:
                return created.data[0]

            retry = (
                self.client.table(CONVERSATIONS_TABLE)
                .select("*")
                .eq("conversation_key", conversation_key)
                .limit(1)
                .execute()
            )
            return (retry.data or [payload])[0]
        except Exception as exc:
            logger.warning("Falha no Supabase para conversa; usando JSON local: %s", exc)
            self.use_local = True
            LOCAL_DATA_DIR.mkdir(parents=True, exist_ok=True)
            return self._local_get_or_create_conversation(conversation_key, phone)

    def _local_get_or_create_conversation(self, conversation_key: str, phone: str) -> dict:
        if self.use_local:
            rows = self._local_read(CONVERSATIONS_TABLE)
            for row in rows:
                if row.get("conversation_key") == conversation_key:
                    return row

            now = iso_z(utc_now())
            row = {
                "id": str(uuid.uuid4()),
                "conversation_key": conversation_key,
                "phone": phone,
                "ai_paused": False,
                "paused_at": None,
                "paused_until": None,
                "pause_reason": None,
                "created_at": now,
                "updated_at": now,
            }
            rows.append(row)
            self._local_write(CONVERSATIONS_TABLE, rows)
            return row
        raise RuntimeError("Estado local indisponivel")

    def update_conversation(self, conversation_id: str, updates: dict) -> dict:
        payload = {**updates, "updated_at": iso_z(utc_now())}
        if self.use_local:
            rows = self._local_read(CONVERSATIONS_TABLE)
            for index, row in enumerate(rows):
                if str(row.get("id")) == str(conversation_id):
                    rows[index] = {**row, **payload}
                    self._local_write(CONVERSATIONS_TABLE, rows)
                    return rows[index]
            return payload

        try:
            result = (
                self.client.table(CONVERSATIONS_TABLE)
                .update(payload)
                .eq("id", conversation_id)
                .execute()
            )
            return (result.data or [payload])[0]
        except Exception as exc:
            logger.warning("Falha ao atualizar Supabase; usando JSON local: %s", exc)
            self.use_local = True
            return self.update_conversation(conversation_id, updates)

    def add_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        payload_json: dict | None = None,
    ) -> dict:
        now = iso_z(utc_now())
        payload = {
            "id": str(uuid.uuid4()),
            "conversation_id": conversation_id,
            "role": role,
            "content": content,
            "payload_json": payload_json or {},
            "created_at": now,
        }

        if self.use_local:
            self._local_append(MESSAGES_TABLE, payload)
            return payload

        try:
            result = self.client.table(MESSAGES_TABLE).insert(payload).execute()
            return (result.data or [payload])[0]
        except Exception as exc:
            logger.warning("Falha ao gravar mensagem no Supabase; usando JSON local: %s", exc)
            self.use_local = True
            self._local_append(MESSAGES_TABLE, payload)
            return payload

    def recent_messages(self, conversation_id: str, limit: int = CONTEXT_MESSAGE_LIMIT) -> list[dict]:
        safe_limit = max(1, min(limit, 50))
        if self.use_local:
            rows = [
                row
                for row in self._local_read(MESSAGES_TABLE)
                if str(row.get("conversation_id")) == str(conversation_id)
            ]
            rows.sort(key=lambda row: str(row.get("created_at") or ""), reverse=True)
            return list(reversed(rows[:safe_limit]))

        try:
            result = (
                self.client.table(MESSAGES_TABLE)
                .select("role, content, created_at")
                .eq("conversation_id", conversation_id)
                .order("created_at", desc=True)
                .limit(safe_limit)
                .execute()
            )
            return list(reversed(result.data or []))
        except Exception as exc:
            logger.warning("Falha ao buscar historico no Supabase; usando JSON local: %s", exc)
            self.use_local = True
            return self.recent_messages(conversation_id, safe_limit)

    def _local_file(self, table: str) -> Path:
        LOCAL_DATA_DIR.mkdir(parents=True, exist_ok=True)
        return LOCAL_DATA_DIR / f"{table}.json"

    def _local_read(self, table: str) -> list[dict]:
        path = self._local_file(table)
        if not path.exists():
            return []
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return []
        return data if isinstance(data, list) else []

    def _local_write(self, table: str, rows: list[dict]) -> None:
        self._local_file(table).write_text(
            json.dumps(rows, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _local_append(self, table: str, row: dict) -> None:
        rows = self._local_read(table)
        rows.append(row)
        self._local_write(table, rows)


def maybe_expire_pause(store: AgentStore, conversation: dict) -> dict:
    if not conversation.get("ai_paused"):
        return conversation

    paused_until = parse_dt(conversation.get("paused_until"))
    if paused_until and paused_until <= utc_now():
        return store.update_conversation(
            str(conversation["id"]),
            {
                "ai_paused": False,
                "paused_at": None,
                "paused_until": None,
                "pause_reason": "expired",
            },
        )
    return conversation


def apply_pause_command(store: AgentStore, conversation: dict, text: str) -> dict | None:
    normalized = normalize_text(text)
    now = utc_now()

    if normalized == RESUME_TRIGGER:
        updated = store.update_conversation(
            str(conversation["id"]),
            {
                "ai_paused": False,
                "paused_at": None,
                "paused_until": None,
                "pause_reason": "manual_resume",
            },
        )
        return {
            "action": "resumed",
            "should_reply": False,
            "conversation": updated,
        }

    if normalized == PAUSE_TRIGGER:
        paused_until = now + timedelta(hours=PAUSE_HOURS)
        updated = store.update_conversation(
            str(conversation["id"]),
            {
                "ai_paused": True,
                "paused_at": iso_z(now),
                "paused_until": iso_z(paused_until),
                "pause_reason": "manual_pause",
            },
        )
        return {
            "action": "paused",
            "should_reply": False,
            "paused_until": iso_z(paused_until),
            "conversation": updated,
        }

    return None


def build_ai_messages(history: list[dict]) -> list[dict]:
    system_prompt = os.getenv(
        "AI_AGENT_SYSTEM_PROMPT",
        (
            "Voce e um atendente comercial por WhatsApp. Responda em portugues do Brasil, "
            "com foco em vender, processar pedidos e tirar duvidas. Seja direto, cordial e "
            "nunca invente disponibilidade, preco ou prazo quando nao houver dado suficiente."
        ),
    )
    messages = [{"role": "system", "content": system_prompt}]
    for item in history[-CONTEXT_MESSAGE_LIMIT:]:
        role = item.get("role")
        if role not in {"user", "assistant"}:
            continue
        content = normalize_text(item.get("content"))
        if content:
            messages.append({"role": role, "content": content})
    return messages


def generate_ai_reply(history: list[dict]) -> str:
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        return ""

    from openai import OpenAI

    model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
    client = OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model=model,
        messages=build_ai_messages(history),
        temperature=0.3,
    )
    return normalize_text(response.choices[0].message.content)


def process_inbound_message(
    phone: str,
    text: str,
    payload_json: dict | None = None,
    conversation_key: str | None = None,
    store: AgentStore | None = None,
) -> dict:
    store = store or AgentStore()
    safe_phone = normalize_phone(phone)
    key = conversation_key or safe_phone
    if not key:
        raise ValueError("Telefone/conversation_key ausente")

    conversation = store.get_or_create_conversation(key, safe_phone)
    conversation = maybe_expire_pause(store, conversation)

    store.add_message(
        str(conversation["id"]),
        "user",
        normalize_text(text),
        payload_json=payload_json,
    )

    command_result = apply_pause_command(store, conversation, text)
    if command_result:
        return command_result

    conversation = maybe_expire_pause(store, conversation)
    if conversation.get("ai_paused"):
        return {
            "action": "ignored_paused",
            "should_reply": False,
            "paused_until": conversation.get("paused_until"),
        }

    history = store.recent_messages(str(conversation["id"]), CONTEXT_MESSAGE_LIMIT)
    reply = generate_ai_reply(history)
    if not reply:
        return {
            "action": "no_reply_generated",
            "should_reply": False,
            "context_messages": len(history),
        }

    store.add_message(str(conversation["id"]), "assistant", reply, payload_json={"source": "ai"})
    return {
        "action": "reply",
        "should_reply": True,
        "reply": reply,
        "context_messages": len(history),
    }
