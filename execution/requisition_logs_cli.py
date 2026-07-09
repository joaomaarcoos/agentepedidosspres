from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

REQUISITION_LOGS_TABLE = "requisition_logs"
LEGACY_REQUISITION_LOGS_TABLE = "clic_request_logs"


def emit(payload: dict) -> None:
    sys.stdout.write(json.dumps(payload, ensure_ascii=False, default=str))
    sys.stdout.write("\n")


def _db():
    url = os.getenv("SUPABASE_URL", "").rstrip("/")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_ANON_KEY", "")
    if not url or not key:
        raise RuntimeError("Supabase nao configurado")
    from supabase import create_client

    return create_client(url, key)


def _dashboard_date_to(value: str | None) -> str | None:
    if not value:
        return None
    if len(value) == 10:
        return (datetime.strptime(value, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
    return value


def _row_summary(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row.get("id"),
        "source": row.get("source"),
        "operation": row.get("operation"),
        "endpoint": row.get("endpoint"),
        "method": row.get("method"),
        "status": row.get("status"),
        "http_status": row.get("http_status"),
        "order_id": row.get("order_id"),
        "protocol": row.get("protocol"),
        "cod_rep": row.get("cod_rep"),
        "representative_document": row.get("representative_document"),
        "customer_code": row.get("customer_code"),
        "customer_document": row.get("customer_document"),
        "error_message": row.get("error_message"),
        "created_at": row.get("created_at"),
        "sent_at": row.get("sent_at"),
        "responded_at": row.get("responded_at"),
        "duration_ms": row.get("duration_ms"),
    }


def _secretary_order_to_log(row: dict[str, Any], detail: bool = False) -> dict[str, Any]:
    status = "success" if row.get("status") in {"submitted", "synced"} else "error"
    payload = row.get("submit_payload") if isinstance(row.get("submit_payload"), dict) else {}
    is_senior = payload.get("provider") == "senior"
    log = {
        "id": f"secretary_order:{row.get('id')}",
        "source": "secretary_orders_senior" if is_senior else "secretary_orders",
        "operation": "GravarPedidos" if is_senior else "create_order",
        "endpoint": payload.get("endpoint") if is_senior else "/extpedidos",
        "method": "POST",
        "status": status,
        "http_status": 200 if status == "success" else None,
        "order_id": row.get("id"),
        "protocol": row.get("protocol"),
        "cod_rep": row.get("cod_rep"),
        "representative_document": None,
        "customer_code": row.get("customer_code"),
        "customer_document": row.get("customer_document"),
        "error_message": row.get("error_message"),
        "created_at": row.get("created_at"),
        "sent_at": row.get("submitted_at") or row.get("updated_at"),
        "responded_at": row.get("submitted_at") or row.get("updated_at"),
        "duration_ms": None,
    }
    if detail:
        log["request_payload"] = row.get("submit_payload")
        log["response_payload"] = row.get("submit_response")
    return log


def _list_secretary_order_logs(
    status: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    search: str | None = None,
    page: int = 1,
    page_size: int = 30,
) -> dict:
    db = _db()
    query = db.table("secretary_orders").select("*")
    if date_from:
        query = query.gte("created_at", date_from)
    end_date = _dashboard_date_to(date_to)
    if end_date:
        query = query.lt("created_at", end_date)
    rows = [
        row
        for row in (query.order("created_at", desc=True).limit(5000).execute().data or [])
        if row.get("submit_payload") is not None
    ]
    mapped = [_secretary_order_to_log(row) for row in rows]
    if status:
        mapped = [row for row in mapped if row.get("status") == status]
    if search:
        needle = str(search).lower().strip()
        mapped = [
            row
            for row in mapped
            if needle
            in " ".join(
                str(row.get(key) or "")
                for key in (
                    "protocol",
                    "endpoint",
                    "cod_rep",
                    "representative_document",
                    "customer_code",
                    "customer_document",
                    "error_message",
                )
            ).lower()
        ]
    total = len(mapped)
    safe_page_size = min(max(int(page_size or 30), 1), 100)
    safe_page = max(int(page or 1), 1)
    start = (safe_page - 1) * safe_page_size
    stats: dict[str, int] = {}
    for row in mapped:
        key = str(row.get("status") or "")
        stats[key] = stats.get(key, 0) + 1
    return {
        "logs": mapped[start : start + safe_page_size],
        "total": total,
        "page": safe_page,
        "page_size": safe_page_size,
        "pages": max(1, (total + safe_page_size - 1) // safe_page_size),
        "stats": stats,
    }


def list_logs(
    status: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    search: str | None = None,
    page: int = 1,
    page_size: int = 30,
) -> dict:
    db = _db()
    rows = None
    for table in (REQUISITION_LOGS_TABLE, LEGACY_REQUISITION_LOGS_TABLE):
        try:
            query = db.table(table).select("*")
            if status:
                query = query.eq("status", status)
            if date_from:
                query = query.gte("created_at", date_from)
            end_date = _dashboard_date_to(date_to)
            if end_date:
                query = query.lt("created_at", end_date)
            rows = query.order("created_at", desc=True).limit(5000).execute().data or []
            break
        except Exception:
            continue
    if rows is None:
        return _list_secretary_order_logs(status, date_from, date_to, search, page, page_size)

    if search:
        needle = str(search).lower().strip()
        rows = [
            row
            for row in rows
            if needle
            in " ".join(
                str(row.get(key) or "")
                for key in (
                    "protocol",
                    "endpoint",
                    "cod_rep",
                    "representative_document",
                    "customer_code",
                    "customer_document",
                    "error_message",
                )
            ).lower()
        ]

    total = len(rows)
    safe_page_size = min(max(int(page_size or 30), 1), 100)
    safe_page = max(int(page or 1), 1)
    start = (safe_page - 1) * safe_page_size
    page_rows = rows[start : start + safe_page_size]
    stats: dict[str, int] = {}
    for row in rows:
        key = str(row.get("status") or "")
        stats[key] = stats.get(key, 0) + 1

    return {
        "logs": [_row_summary(row) for row in page_rows],
        "total": total,
        "page": safe_page,
        "page_size": safe_page_size,
        "pages": max(1, (total + safe_page_size - 1) // safe_page_size),
        "stats": stats,
    }


def get_log(log_id: str) -> dict:
    db = _db()
    if log_id.startswith("secretary_order:"):
        order_id = log_id.split(":", 1)[1]
        rows = db.table("secretary_orders").select("*").eq("id", order_id).limit(1).execute().data or []
        if not rows:
            raise RuntimeError("Log nao encontrado")
        return _secretary_order_to_log(rows[0], detail=True)
    rows = []
    for table in (REQUISITION_LOGS_TABLE, LEGACY_REQUISITION_LOGS_TABLE):
        try:
            rows = db.table(table).select("*").eq("id", log_id).limit(1).execute().data or []
            if rows:
                break
        except Exception:
            continue
    if not rows:
        fallback = db.table("secretary_orders").select("*").eq("id", log_id).limit(1).execute().data or []
        if fallback:
            return _secretary_order_to_log(fallback[0], detail=True)
        raise RuntimeError("Log nao encontrado")
    return rows[0]


def main() -> int:
    parser = argparse.ArgumentParser(description="Requisition Logs")
    sub = parser.add_subparsers(dest="command", required=True)

    list_parser = sub.add_parser("list")
    list_parser.add_argument("--status", default=None)
    list_parser.add_argument("--date-from", default=None)
    list_parser.add_argument("--date-to", default=None)
    list_parser.add_argument("--search", default=None)
    list_parser.add_argument("--page", type=int, default=1)
    list_parser.add_argument("--page-size", type=int, default=30)

    detail_parser = sub.add_parser("detail")
    detail_parser.add_argument("id")

    args = parser.parse_args()
    try:
        if args.command == "detail":
            data = get_log(args.id)
        else:
            data = list_logs(
                status=args.status,
                date_from=args.date_from,
                date_to=args.date_to,
                search=args.search,
                page=args.page,
                page_size=args.page_size,
            )
        emit({"ok": True, "data": data})
    except Exception as exc:
        emit({"ok": False, "error": str(exc)})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
