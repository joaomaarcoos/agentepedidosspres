"""
recorrencia_cli.py
==================
Calcula métricas de recorrência de clientes a partir de
clic_pedidos_integrados + clic_clientes.
Saída em JSON no stdout; logs no stderr.

Subcomandos:
  overview  --dias N --min-pedidos N --page N --page-size N
  detail    --cod-cli N --dias N
"""

import argparse
import json
import logging
import os
import re
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

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


def _db():
    url = os.getenv("SUPABASE_URL", "").rstrip("/")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_ANON_KEY", "")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY não configurados")
    from supabase import create_client
    return create_client(url, key)


def _cpf_to_int(cpf: str) -> int | None:
    digits = re.sub(r"\D", "", cpf or "")
    try:
        return int(digits) if digits else None
    except ValueError:
        return None


def _extract_nome(raw_json: dict) -> str:
    c = (raw_json or {}).get("cliente") or {}
    return c.get("fantasia") or c.get("razaoSocial") or ""


def _parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except (ValueError, TypeError):
        pass
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(value[:26], fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _classify(days_since_last: int, avg_interval: float | None) -> str:
    if avg_interval is None or avg_interval <= 0:
        return "novo"
    if days_since_last > avg_interval * 1.5:
        return "critico"
    if days_since_last > avg_interval * 1.15:
        return "atrasado"
    if days_since_last > avg_interval * 0.85:
        return "em_janela"
    return "cedo"


def _fetch_orders(db, from_date: datetime) -> list[dict]:
    res = (
        db.table("clic_pedidos_integrados")
        .select("cpf_cnpj, numero, valor_total, situacao_id, criado_em, raw_json")
        .gte("criado_em", from_date.isoformat())
        .order("criado_em", desc=True)
        .limit(5000)
        .execute()
    )
    return res.data or []


def _fetch_metricas(db, cpfs: list[str]) -> dict[str, dict]:
    result: dict[str, dict] = {}
    for i in range(0, len(cpfs), 200):
        batch = cpfs[i: i + 200]
        res = (
            db.table("clic_clientes")
            .select("cpf_cnpj, dias_entre_pedidos_media, ultimo_pedido_em, primeiro_pedido_em, total_pedidos")
            .in_("cpf_cnpj", batch)
            .execute()
        )
        for m in res.data or []:
            result[m["cpf_cnpj"]] = m
    return result


def _build_metrics(cpf: str, orders: list[dict], metricas: dict, now: datetime) -> dict:
    cod_cli = _cpf_to_int(cpf)
    m = metricas.get(cpf) or {}

    avg_interval_raw = m.get("dias_entre_pedidos_media")
    avg_interval = float(avg_interval_raw) if avg_interval_raw is not None else None

    last_order = _parse_date(m.get("ultimo_pedido_em") or "")
    first_order = _parse_date(m.get("primeiro_pedido_em") or "")

    days_since_last = (
        int((now - last_order).total_seconds() // 86400) if last_order else None
    )
    expected_next = (
        (last_order + timedelta(days=round(avg_interval))).date().isoformat()
        if last_order and avg_interval
        else None
    )
    overdue_days = (
        max(0, round(days_since_last - avg_interval))
        if days_since_last is not None and avg_interval
        else 0
    )
    status = _classify(days_since_last or 0, avg_interval)

    nome = ""
    for o in orders:
        n = _extract_nome(o.get("raw_json") or {})
        if n:
            nome = n
            break

    total_value = sum(float(o.get("valor_total") or 0) for o in orders)
    pedido_count = len(orders)
    avg_order_value = total_value / pedido_count if pedido_count else 0.0

    recent = sorted(orders, key=lambda x: x.get("criado_em") or "", reverse=True)[:5]
    recent_orders = [
        {
            "cod_cli": cod_cli,
            "num_ped": o.get("numero"),
            "dat_emi": (o.get("criado_em") or "")[:10],
            "sit_ped": o.get("situacao_id"),
            "order_total_value": float(o.get("valor_total") or 0),
        }
        for o in recent
    ]

    return {
        "cod_cli": cod_cli,
        "cliente_nome": nome or f"Cliente {cod_cli}",
        "pedido_count": pedido_count,
        "first_order_at": first_order.date().isoformat() if first_order else None,
        "last_order_at": last_order.date().isoformat() if last_order else None,
        "avg_interval_days": round(avg_interval, 1) if avg_interval is not None else None,
        "days_since_last": days_since_last,
        "expected_next_order_at": expected_next,
        "overdue_days": overdue_days,
        "confidence": round(min(1.0, pedido_count / 5.0), 2),
        "status": status,
        "total_value": round(total_value, 2),
        "avg_order_value": round(avg_order_value, 2),
        "recent_orders": recent_orders,
    }


def recurrence_overview(dias: int, min_pedidos: int, page: int, page_size: int) -> dict:
    db = _db()
    now = datetime.now(timezone.utc)
    from_date = now - timedelta(days=dias)

    orders = _fetch_orders(db, from_date)

    grouped: dict[str, list[dict]] = defaultdict(list)
    for o in orders:
        cpf = o.get("cpf_cnpj") or ""
        if cpf:
            grouped[cpf].append(o)

    eligible_cpfs = [cpf for cpf, ords in grouped.items() if len(ords) >= min_pedidos]
    metricas = _fetch_metricas(db, eligible_cpfs)

    metrics = [
        _build_metrics(cpf, grouped[cpf], metricas, now)
        for cpf in eligible_cpfs
    ]
    metrics.sort(
        key=lambda r: (
            {"critico": 0, "atrasado": 1, "em_janela": 2, "cedo": 3, "novo": 4}.get(r["status"], 9),
            -int(r.get("overdue_days") or 0),
            r.get("cliente_nome") or "",
        )
    )

    total = len(metrics)
    start = (page - 1) * page_size
    paginated = metrics[start: start + page_size]

    status_counts: dict[str, int] = defaultdict(int)
    for r in metrics:
        status_counts[r["status"]] += 1

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": max(1, -(-total // page_size)),
        "dias": dias,
        "min_pedidos": min_pedidos,
        "stats": {
            "criticos": status_counts["critico"],
            "atrasados": status_counts["atrasado"],
            "em_janela": status_counts["em_janela"],
            "cedo": status_counts["cedo"],
            "novos": status_counts["novo"],
        },
        "clientes": paginated,
    }


def recurrence_detail(cod_cli: int, dias: int) -> dict:
    db = _db()
    now = datetime.now(timezone.utc)
    from_date = now - timedelta(days=dias)

    orders = _fetch_orders(db, from_date)
    client_orders = [
        o for o in orders
        if _cpf_to_int(o.get("cpf_cnpj") or "") == cod_cli
    ]

    if not client_orders:
        raise ValueError(f"Cliente {cod_cli} sem pedidos nos últimos {dias} dias")

    cpf = client_orders[0]["cpf_cnpj"]
    metricas = _fetch_metricas(db, [cpf])
    return _build_metrics(cpf, client_orders, metricas, now)


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[logging.StreamHandler(sys.stderr)],
    )

    parser = argparse.ArgumentParser(description="CLI interna do modulo Recorrencia")
    subparsers = parser.add_subparsers(dest="command", required=True)

    p_overview = subparsers.add_parser("overview")
    p_overview.add_argument("--dias", type=int, default=180)
    p_overview.add_argument("--min-pedidos", dest="min_pedidos", type=int, default=2)
    p_overview.add_argument("--page", type=int, default=1)
    p_overview.add_argument("--page-size", dest="page_size", type=int, default=50)

    p_detail = subparsers.add_parser("detail")
    p_detail.add_argument("--cod-cli", dest="cod_cli", type=int, required=True)
    p_detail.add_argument("--dias", type=int, default=180)

    args = parser.parse_args()

    try:
        if args.command == "overview":
            return success(
                recurrence_overview(
                    dias=args.dias,
                    min_pedidos=args.min_pedidos,
                    page=args.page,
                    page_size=args.page_size,
                )
            )
        if args.command == "detail":
            return success(recurrence_detail(args.cod_cli, args.dias))
        return failure("Comando nao suportado")
    except Exception as exc:
        logger.exception("Falha no modulo recorrencia")
        return failure(str(exc))


if __name__ == "__main__":
    raise SystemExit(main())
