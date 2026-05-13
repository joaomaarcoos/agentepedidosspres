"""
logs_cli.py
===========
Lê logs de disparos da tabela disparo_logs no Supabase.

Subcomandos:
  list  [--flow recorrencia|ativacao] [--status success|partial|error|dry_run]
        [--page N] [--page-size N]
  detail  --id UUID
"""

import argparse
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")


def emit(payload: dict) -> None:
    sys.stdout.write(json.dumps(payload, ensure_ascii=False, default=str))
    sys.stdout.write("\n")


def success(data) -> int:
    emit({"ok": True, "data": data})
    return 0


def failure(message: str) -> int:
    emit({"ok": False, "error": message})
    return 1


def _db():
    url = os.getenv("SUPABASE_URL", "").rstrip("/")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_ANON_KEY", "")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY não configurados")
    from supabase import create_client
    return create_client(url, key)


def cmd_list(flow: str | None, status: str | None, page: int, page_size: int) -> dict:
    db = _db()

    query = db.table("disparo_logs").select("*", count="exact")

    if flow:
        query = query.eq("flow", flow)
    if status:
        query = query.eq("status", status)

    query = query.order("started_at", desc=True)

    offset = (page - 1) * page_size
    query = query.range(offset, offset + page_size - 1)

    res = query.execute()
    total = res.count or 0
    logs = res.data or []

    return {
        "logs": logs,
        "total": total,
        "page": page,
        "pages": max(1, -(-total // page_size)),  # ceiling division
    }


def cmd_detail(log_id: str) -> dict:
    db = _db()
    res = db.table("disparo_logs").select("*").eq("id", log_id).single().execute()
    if not res.data:
        raise RuntimeError(f"Log {log_id} não encontrado")
    return res.data


def main() -> int:
    parser = argparse.ArgumentParser(prog="logs_cli")
    sub = parser.add_subparsers(dest="command")

    list_p = sub.add_parser("list")
    list_p.add_argument("--flow", choices=["recorrencia", "ativacao"], default=None)
    list_p.add_argument("--status", choices=["success", "partial", "error", "dry_run"], default=None)
    list_p.add_argument("--page", type=int, default=1)
    list_p.add_argument("--page-size", type=int, default=30)

    detail_p = sub.add_parser("detail")
    detail_p.add_argument("--id", required=True)

    args = parser.parse_args()

    try:
        if args.command == "list":
            return success(cmd_list(
                flow=args.flow,
                status=args.status,
                page=args.page,
                page_size=args.page_size,
            ))
        if args.command == "detail":
            return success(cmd_detail(args.id))
        parser.print_help()
        return 1
    except Exception as exc:
        return failure(str(exc))


if __name__ == "__main__":
    sys.exit(main())
