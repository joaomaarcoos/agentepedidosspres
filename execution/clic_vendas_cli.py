import argparse
import json
import logging
import os
import sys
import time
import uuid
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(__file__))

from clic_vendas_client import ClicVendasClient
from fetch_pedidos_clic import _parse_pedidos
from supabase_client import SupabaseClient

logger = logging.getLogger(__name__)

REP_DOCUMENT = os.getenv("CLIC_VENDAS_REP_DOCUMENT", "18325136880")


def emit(payload: dict) -> None:
    sys.stdout.write(json.dumps(payload, ensure_ascii=False))
    sys.stdout.write("\n")


def success(data: dict) -> int:
    emit({"ok": True, "data": data})
    return 0


def failure(message: str) -> int:
    emit({"ok": False, "error": message})
    return 0


def run_sync(dias: int, triggered_by: str) -> dict:
    db = SupabaseClient()
    start = time.time()
    date_from = (datetime.utcnow() - timedelta(days=dias)).strftime("%Y-%m-%dT00:00:00.000Z")

    log_id = db.insert_clic_sync_log(
        {
            "triggered_by": triggered_by,
            "status": "running",
            "rep_document": REP_DOCUMENT,
            "date_from": date_from,
        }
    )

    try:
        client = ClicVendasClient()
        raw = client.get(
            "/extpedidos",
            params={
                "numeroDocumentoRepresentante": REP_DOCUMENT,
                "dataAlteracao": date_from,
                "sortBy": "dataCriacao",
                "sortDescAsc": "DESC",
                "fetch": 0,
                "skip": 0,
            },
        )

        pedidos = _parse_pedidos(raw, datetime.utcnow() - timedelta(days=dias))
        total_fetched = len(pedidos)
        synced_at = datetime.utcnow().isoformat() + "Z"

        order_rows = []
        for pedido in pedidos:
            order_rows.append(
                {
                    "id": str(uuid.uuid4()),
                    "cod_rep": pedido.get("codRep"),
                    "cod_cli": pedido.get("codCli"),
                    "customer_name": pedido.get("nomeCliente"),
                    "rep_name": pedido.get("nomeRep"),
                    "num_ped": pedido.get("numPed"),
                    "dat_emi": pedido.get("datEmi"),
                    "sit_ped": pedido.get("sitPed"),
                    "order_total_value": pedido.get("vlrTot"),
                    "items_json": pedido.get("itens", []),
                    "has_items": bool(pedido.get("itens")),
                    "source": "clic_vendas",
                    "erp_synced_at": synced_at,
                    "created_at": synced_at,
                    "updated_at": synced_at,
                }
            )

        total_upserted = db.upsert_rep_order_base(order_rows) if order_rows else 0

        status_breakdown: dict[str, int] = {}
        clients_set = set()
        for pedido in pedidos:
            sit = str(pedido.get("sitPed") or "desconhecido")
            status_breakdown[sit] = status_breakdown.get(sit, 0) + 1
            if pedido.get("codCli"):
                clients_set.add(pedido["codCli"])

        duration_ms = int((time.time() - start) * 1000)

        db.update_clic_sync_log(
            log_id,
            {
                "status": "success",
                "total_fetched": total_fetched,
                "total_upserted": total_upserted,
                "total_errors": 0,
                "duration_ms": duration_ms,
                "result_summary_json": {
                    "total_clientes": len(clients_set),
                    "status_breakdown": status_breakdown,
                    "date_from": date_from,
                    "dias": dias,
                },
            },
        )

        return {
            "id": log_id,
            "status": "success",
            "message": f"Sync concluída: {total_fetched} pedidos processados.",
            "total_fetched": total_fetched,
            "total_upserted": total_upserted,
            "duration_ms": duration_ms,
        }
    except Exception as exc:
        duration_ms = int((time.time() - start) * 1000)
        db.update_clic_sync_log(
            log_id,
            {
                "status": "error",
                "duration_ms": duration_ms,
                "error_message": str(exc),
            },
        )
        raise RuntimeError(str(exc)) from exc


def list_sync_logs(date_str: str | None, limit: int) -> dict:
    db = SupabaseClient()
    if not date_str:
        date_str = datetime.utcnow().strftime("%Y-%m-%d")
    logs = db.get_clic_sync_logs(date_str=date_str, limit=limit)
    return {"date": date_str, "logs": logs, "total": len(logs)}


def get_sync_log(log_id: str) -> dict:
    db = SupabaseClient()
    logs = db.get_clic_sync_logs(limit=200)
    for log in logs:
        if str(log.get("id")) == str(log_id):
            return log
    raise ValueError("Log não encontrado")


def _db_direct():
    import re as _re
    from dotenv import load_dotenv as _ldenv
    _ldenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
    url = os.getenv("SUPABASE_URL", "").rstrip("/")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_ANON_KEY", "")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY nao configurados")
    from supabase import create_client
    return create_client(url, key)


def _cpf_digits_int(cpf: str):
    import re as _re
    digits = _re.sub(r"\D", "", cpf or "")
    try:
        return int(digits) if digits else None
    except ValueError:
        return None


def _nome_from_raw(raw_json) -> str:
    c = (raw_json or {}).get("cliente") or {}
    return c.get("fantasia") or c.get("razaoSocial") or ""


def _map_row(row: dict) -> dict:
    cpf = row.get("cpf_cnpj") or ""
    criado_em = row.get("criado_em") or ""
    return {
        "num_ped": row.get("numero"),
        "cod_cli": _cpf_digits_int(cpf) or cpf,
        "customer_name": _nome_from_raw(row.get("raw_json") or {}) or cpf,
        "dat_emi": criado_em[:10] if criado_em else "",
        "sit_ped": row.get("situacao_id") or "",
        "order_total_value": float(row.get("valor_total") or 0),
        "items_json": row.get("itens_json") or [],
        "has_items": bool(row.get("itens_json")),
        "source": "clic_vendas",
        "cpf_cnpj": cpf,
    }


def list_pedidos(cod_cli: int | None, dias: int, page: int, page_size: int) -> dict:
    db = _db_direct()

    q = (
        db.table("clic_pedidos_integrados")
        .select("id, numero, cpf_cnpj, valor_total, situacao_id, criado_em, itens_json, raw_json")
        .order("criado_em", desc=True)
        .limit(5000)
    )
    if dias > 0:
        from_date = (datetime.utcnow() - timedelta(days=dias)).strftime("%Y-%m-%dT00:00:00.000Z")
        q = q.gte("criado_em", from_date)

    pedidos = [_map_row(r) for r in (q.execute().data or [])]

    if cod_cli is not None:
        pedidos = [p for p in pedidos if _cpf_digits_int(str(p.get("cpf_cnpj") or "")) == cod_cli]

    total = len(pedidos)
    start = (page - 1) * page_size

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": max(1, -(-total // page_size)),
        "pedidos": pedidos[start: start + page_size],
    }


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    parser = argparse.ArgumentParser(description="CLI interna do módulo ClicVendas")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("status")

    sync_parser = subparsers.add_parser("sync")
    sync_parser.add_argument("--dias", type=int, default=30)
    sync_parser.add_argument("--triggered-by", default="manual")

    sync_logs_parser = subparsers.add_parser("sync-logs")
    sync_logs_parser.add_argument("--date", default=None)
    sync_logs_parser.add_argument("--limit", type=int, default=50)

    sync_log_parser = subparsers.add_parser("sync-log")
    sync_log_parser.add_argument("--log-id", required=True)

    pedidos_parser = subparsers.add_parser("pedidos")
    pedidos_parser.add_argument("--cod-cli", type=int, default=None)
    pedidos_parser.add_argument("--dias", type=int, default=0)
    pedidos_parser.add_argument("--page", type=int, default=1)
    pedidos_parser.add_argument("--page-size", type=int, default=50)

    args = parser.parse_args()

    try:
        if args.command == "status":
            return success(
                {
                    "ok": True,
                    "service": "AgentePedidos Next.js API",
                    "version": "1.0.0",
                    "mode": "python-internal-script",
                }
            )
        if args.command == "sync":
            return success(run_sync(args.dias, args.triggered_by))
        if args.command == "sync-logs":
            return success(list_sync_logs(args.date, args.limit))
        if args.command == "sync-log":
            return success(get_sync_log(args.log_id))
        if args.command == "pedidos":
            return success(list_pedidos(args.cod_cli, args.dias, args.page, args.page_size))
        return failure("Comando não suportado")
    except Exception as exc:
        logger.exception("Falha no CLI do ClicVendas")
        return failure(str(exc))


if __name__ == "__main__":
    raise SystemExit(main())
