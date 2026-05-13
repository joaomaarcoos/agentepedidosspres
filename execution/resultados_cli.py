"""
resultados_cli.py
=================
Lê recurrence_targets com status 'dispatched' ou 'converted' e retorna métricas
de impacto dos disparos da IA (esteiras recorrência + ativação).

Subcomandos:
  overview  [--target-type all|recorrencia|ativacao] [--page N] [--page-size N]
"""

import argparse
import json
import os
import sys
from collections import defaultdict

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))


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


def cmd_overview(target_type: str | None, page: int, page_size: int) -> dict:
    db = _db()

    # Busca todos os registros dispatched + converted para calcular stats
    stats_query = (
        db.table("recurrence_targets")
        .select("id, status, target_type, converted_order_value")
        .in_("status", ["dispatched", "converted"])
    )
    if target_type and target_type != "all":
        stats_query = stats_query.eq("target_type", target_type)

    stats_res = stats_query.execute()
    all_items = stats_res.data or []

    # Contadores por pipeline
    counts: dict[str, dict[str, int | float]] = {
        "recorrencia": {"dispatched": 0, "converted": 0, "revenue": 0.0},
        "ativacao":    {"dispatched": 0, "converted": 0, "revenue": 0.0},
    }

    for item in all_items:
        pipeline = item.get("target_type", "recorrencia")
        if pipeline not in counts:
            continue
        if item["status"] == "converted":
            counts[pipeline]["converted"] += 1
            counts[pipeline]["revenue"] += float(item.get("converted_order_value") or 0)
        else:
            counts[pipeline]["dispatched"] += 1

    total_dispatched = sum(c["dispatched"] for c in counts.values())
    total_converted = sum(c["converted"] for c in counts.values())
    total_revenue = sum(c["revenue"] for c in counts.values())
    total_items = len(all_items)

    def rate(converted: int, dispatched: int) -> float:
        total = converted + dispatched
        return round(converted / total * 100, 1) if total > 0 else 0.0

    stats = {
        "dispatched_total": total_dispatched,
        "converted_total": total_converted,
        "conversion_rate": rate(total_converted, total_dispatched),
        "revenue_total": round(total_revenue, 2),
        "by_pipeline": {
            "recorrencia": {
                "dispatched": counts["recorrencia"]["dispatched"],
                "converted": counts["recorrencia"]["converted"],
                "revenue": round(counts["recorrencia"]["revenue"], 2),
            },
            "ativacao": {
                "dispatched": counts["ativacao"]["dispatched"],
                "converted": counts["ativacao"]["converted"],
                "revenue": round(counts["ativacao"]["revenue"], 2),
            },
        },
    }

    # Paginação dos targets
    data_query = (
        db.table("recurrence_targets")
        .select("*")
        .in_("status", ["dispatched", "converted"])
    )
    if target_type and target_type != "all":
        data_query = data_query.eq("target_type", target_type)

    start = (page - 1) * page_size
    end = start + page_size - 1
    res = data_query.order("dispatched_at", desc=True).range(start, end).execute()
    targets = res.data or []

    return {
        "stats": stats,
        "targets": targets,
        "total": total_items,
        "page": page,
        "page_size": page_size,
        "pages": max(1, -(-total_items // page_size)) if total_items else 1,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Resultados dos disparos IA")
    subparsers = parser.add_subparsers(dest="command", required=True)

    p_ov = subparsers.add_parser("overview", help="Métricas e lista de disparos")
    p_ov.add_argument(
        "--target-type",
        dest="target_type",
        default="all",
        choices=["all", "recorrencia", "ativacao"],
    )
    p_ov.add_argument("--page", type=int, default=1)
    p_ov.add_argument("--page-size", dest="page_size", type=int, default=50)

    args = parser.parse_args()

    try:
        if args.command == "overview":
            data = cmd_overview(args.target_type, args.page, args.page_size)
            return success(data)
    except Exception as exc:
        return failure(str(exc))

    return 0


if __name__ == "__main__":
    sys.exit(main())
