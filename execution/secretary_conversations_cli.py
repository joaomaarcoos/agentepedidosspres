import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")


def emit(payload: dict) -> None:
    sys.stdout.write(json.dumps(payload, ensure_ascii=False, default=str))
    sys.stdout.write("\n")


def success(data: dict) -> int:
    emit({"ok": True, "data": data})
    return 0


def failure(message: str) -> int:
    emit({"ok": False, "error": message})
    return 0


def _db():
    url = os.getenv("SUPABASE_URL", "").rstrip("/")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_ANON_KEY", "")
    if not url or not key:
        raise RuntimeError("Supabase nao configurado")
    from supabase import create_client

    return create_client(url, key)


def _digits(value: Any) -> str:
    return re.sub(r"\D", "", str(value or ""))


def _parse_dt(value: Any) -> datetime:
    if not value:
        return datetime.min.replace(tzinfo=timezone.utc)
    text = str(value).replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return datetime.min.replace(tzinfo=timezone.utc)


def _message_summary(message: dict | None) -> str:
    content = str((message or {}).get("content") or "")
    return content[:140]


def _state_error_hint(state: dict) -> str | None:
    history = state.get("product_history") if isinstance(state, dict) else None
    if not isinstance(history, list):
        return None
    for item in reversed(history):
        if not isinstance(item, dict):
            continue
        content = str(item.get("content") or "")
        if (
            "Nao consegui identificar os produtos" in content
            or "Nao encontrei" in content
            or "Preciso confirmar" in content
        ):
            return content
    return None


def list_conversations(search: str | None, page: int, page_size: int) -> dict:
    db = _db()
    safe_page = max(1, page)
    safe_page_size = min(max(1, page_size), 100)
    rows = (
        db.table("secretary_conversations")
        .select("*")
        .order("updated_at", desc=True)
        .limit(1000)
        .execute()
        .data
        or []
    )
    conversation_ids = [row["id"] for row in rows if row.get("id")]
    latest_by_conversation: dict[str, dict] = {}
    if conversation_ids:
        for index in range(0, len(conversation_ids), 200):
            batch = conversation_ids[index : index + 200]
            messages = (
                db.table("secretary_messages")
                .select("id,conversation_id,role,content,created_at")
                .in_("conversation_id", batch)
                .order("created_at", desc=True)
                .limit(1000)
                .execute()
                .data
                or []
            )
            for message in messages:
                conversation_id = str(message.get("conversation_id") or "")
                current = latest_by_conversation.get(conversation_id)
                if not current or _parse_dt(message.get("created_at")) > _parse_dt(current.get("created_at")):
                    latest_by_conversation[conversation_id] = message

    normalized_search = (search or "").strip().lower()
    normalized_digits = _digits(search)
    result = []
    for row in rows:
        state = row.get("state_json") if isinstance(row.get("state_json"), dict) else {}
        latest = latest_by_conversation.get(str(row.get("id")))
        haystack = " ".join(
            str(part or "")
            for part in (
                row.get("instance_name"),
                row.get("representative_phone"),
                row.get("cod_rep"),
                row.get("conversation_key"),
                _message_summary(latest),
                (state.get("customer") or {}).get("name") if isinstance(state.get("customer"), dict) else "",
                (state.get("customer") or {}).get("code") if isinstance(state.get("customer"), dict) else "",
            )
        ).lower()
        if normalized_search and normalized_search not in haystack and normalized_digits not in _digits(haystack):
            continue
        result.append(
            {
                "id": row.get("id"),
                "conversation_key": row.get("conversation_key"),
                "instance_name": row.get("instance_name"),
                "representative_phone": row.get("representative_phone"),
                "cod_rep": row.get("cod_rep"),
                "state_json": state,
                "created_at": row.get("created_at"),
                "updated_at": row.get("updated_at"),
                "latest_message": latest,
                "error_hint": _state_error_hint(state),
            }
        )

    total = len(result)
    pages = max(1, (total + safe_page_size - 1) // safe_page_size)
    start = (safe_page - 1) * safe_page_size
    return {
        "conversations": result[start : start + safe_page_size],
        "total": total,
        "page": safe_page,
        "page_size": safe_page_size,
        "pages": pages,
    }


def detail_conversation(conversation_id: str) -> dict:
    db = _db()
    rows = (
        db.table("secretary_conversations")
        .select("*")
        .eq("id", conversation_id)
        .limit(1)
        .execute()
        .data
        or []
    )
    if not rows:
        raise ValueError("Conversa nao encontrada")
    conversation = rows[0]
    messages = (
        db.table("secretary_messages")
        .select("*")
        .eq("conversation_id", conversation_id)
        .order("created_at", desc=False)
        .limit(500)
        .execute()
        .data
        or []
    )
    orders = (
        db.table("secretary_orders")
        .select("*")
        .eq("conversation_id", conversation_id)
        .order("created_at", desc=True)
        .limit(20)
        .execute()
        .data
        or []
    )
    state = conversation.get("state_json") if isinstance(conversation.get("state_json"), dict) else {}
    return {
        "conversation": conversation,
        "messages": messages,
        "orders": orders,
        "error_hint": _state_error_hint(state),
    }


def main() -> int:
    parser = argparse.ArgumentParser(prog="secretary_conversations_cli")
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list")
    list_parser.add_argument("--search", default=None)
    list_parser.add_argument("--page", type=int, default=1)
    list_parser.add_argument("--page-size", dest="page_size", type=int, default=30)

    detail_parser = subparsers.add_parser("detail")
    detail_parser.add_argument("id")

    args = parser.parse_args()
    try:
        if args.command == "list":
            return success(list_conversations(args.search, args.page, args.page_size))
        if args.command == "detail":
            return success(detail_conversation(args.id))
        return failure("Comando nao suportado")
    except Exception as exc:
        return failure(str(exc))


if __name__ == "__main__":
    raise SystemExit(main())
