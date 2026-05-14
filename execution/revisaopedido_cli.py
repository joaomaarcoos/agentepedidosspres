"""
revisaopedido_cli.py
====================
Gerencia pedidos aguardando revisão do representante (tabela pedidos_revisao).

Subcomandos:
  list       [--status pendente|em_revisao|pedido_feito|cancelado]
             [--page N] [--page-size N]
  detail     --id UUID
  set-status --id UUID --status <novo_status>
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)],
)
logger = logging.getLogger(__name__)

VALID_STATUSES = {"pendente", "em_revisao", "pedido_feito", "cancelado"}


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
        raise RuntimeError("SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY não configurados")
    from supabase import create_client
    return create_client(url, key)


def cmd_list(status: str | None, page: int, page_size: int) -> dict:
    db = _db()

    counts_res = db.table("pedidos_revisao").select("status").execute()
    all_rows = counts_res.data or []
    stats: dict[str, int] = {s: 0 for s in VALID_STATUSES}
    for row in all_rows:
        s = row.get("status", "")
        if s in stats:
            stats[s] += 1
    total = len(all_rows) if not status else stats.get(status, 0)

    query = db.table("pedidos_revisao").select(
        "id, cliente_nome, cliente_telefone, itens_json, observacoes, status, created_at, updated_at, revisado_em"
    )
    if status:
        query = query.eq("status", status)

    offset = (page - 1) * page_size
    res = query.order("created_at", desc=True).range(offset, offset + page_size - 1).execute()

    pages = max(1, (total + page_size - 1) // page_size)

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": pages,
        "stats": stats,
        "pedidos": res.data or [],
    }


def cmd_detail(pedido_id: str) -> dict:
    db = _db()

    res = db.table("pedidos_revisao").select("*").eq("id", pedido_id).limit(1).execute()
    rows = res.data or []
    if not rows:
        raise RuntimeError(f"Pedido {pedido_id!r} não encontrado")

    pedido = rows[0]

    # Busca mensagens da conversa para contexto
    conversation_id = pedido.get("conversation_id")
    messages: list[dict] = []
    if conversation_id:
        try:
            msg_res = (
                db.table("ai_conversation_messages")
                .select("role, content, created_at")
                .eq("conversation_id", conversation_id)
                .order("created_at", desc=False)
                .limit(30)
                .execute()
            )
            messages = msg_res.data or []
        except Exception as exc:
            logger.warning("Falha ao buscar mensagens da conversa: %s", exc)

    return {**pedido, "conversation_messages": messages}


def cmd_set_status(pedido_id: str, new_status: str) -> dict:
    if new_status not in VALID_STATUSES:
        raise ValueError(f"Status inválido: {new_status!r}. Válidos: {sorted(VALID_STATUSES)}")

    db = _db()
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    patch: dict = {"status": new_status, "updated_at": now}
    if new_status in ("pedido_feito", "cancelado"):
        patch["revisado_em"] = now

    res = db.table("pedidos_revisao").update(patch).eq("id", pedido_id).execute()
    rows = res.data or []
    if not rows:
        raise RuntimeError(f"Pedido {pedido_id!r} não encontrado ou sem alteração")

    return rows[0]


def main() -> int:
    parser = argparse.ArgumentParser(description="CLI de revisão de pedidos")
    sub = parser.add_subparsers(dest="command", required=True)

    p_list = sub.add_parser("list")
    p_list.add_argument("--status", default=None, choices=list(VALID_STATUSES))
    p_list.add_argument("--page", type=int, default=1)
    p_list.add_argument("--page-size", type=int, default=50)

    p_detail = sub.add_parser("detail")
    p_detail.add_argument("--id", dest="pedido_id", required=True)

    p_status = sub.add_parser("set-status")
    p_status.add_argument("--id", dest="pedido_id", required=True)
    p_status.add_argument("--status", required=True, choices=list(VALID_STATUSES))

    args = parser.parse_args()

    try:
        if args.command == "list":
            return success(cmd_list(args.status, args.page, args.page_size))
        if args.command == "detail":
            return success(cmd_detail(args.pedido_id))
        if args.command == "set-status":
            return success(cmd_set_status(args.pedido_id, args.status))
        return failure("Comando não suportado")
    except Exception as exc:
        logger.exception("Falha no módulo de revisão de pedidos")
        return failure(str(exc))


if __name__ == "__main__":
    raise SystemExit(main())
