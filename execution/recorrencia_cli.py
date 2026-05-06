"""
recorrencia_cli.py  (v2)
========================
Pipeline diário de recompra com persistência em recurrence_targets.

Subcomandos:
  run       [--dry-run]                              Job diário: calcula e persiste candidatos
  overview  [--status S] [--page N] [--page-size N]  Lê recurrence_targets para o frontend
  detail    [--cpf S] [--id UUID]                    Detalhe de um target
"""

import argparse
import json
import logging
import os
import re
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from statistics import mean, pstdev

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


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


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


def _extract_name(raw_json: dict) -> str:
    c = (raw_json or {}).get("cliente") or {}
    return c.get("fantasia") or c.get("razaoSocial") or c.get("nome") or ""


def _extract_phone(raw_json: dict) -> str:
    c = (raw_json or {}).get("cliente") or {}
    telefones = c.get("telefones") or []
    if telefones and isinstance(telefones, list):
        valor = (telefones[0] or {}).get("valor") or ""
    else:
        valor = c.get("fone") or c.get("celular") or c.get("telefone") or ""
    return re.sub(r"\D", "", str(valor))


def _extract_cod_cli(raw_json: dict) -> int | None:
    c = (raw_json or {}).get("cliente") or {}
    codigo = (c.get("backoffice") or {}).get("codigo") or c.get("cpCodigoClienteErp") or ""
    try:
        return int(str(codigo).strip()) if codigo else None
    except (ValueError, TypeError):
        return None


def _classify_tier(pedidos_30d: int) -> str:
    if pedidos_30d >= 4:
        return "semanal_forte"
    if pedidos_30d == 3:
        return "alta"
    return "media"


def _calc_score(pedidos_30d: int, intervals: list[float], orders: list[dict]) -> int:
    score = 0

    if pedidos_30d >= 3:
        score += 30

    if len(intervals) >= 2:
        avg = mean(intervals)
        sd = pstdev(intervals)
        if avg > 0 and (sd / avg) < 0.30:
            score += 25
    elif len(intervals) == 1:
        score += 25

    # +20 se codPro se repete entre pedidos
    item_sets = []
    for o in orders:
        items = o.get("itens_json") or []
        codes = {str(item.get("codPro") or "").strip() for item in items if item.get("codPro")}
        if codes:
            item_sets.append(codes)
    if len(item_sets) >= 2:
        intersection = item_sets[0].copy()
        for s in item_sets[1:]:
            intersection &= s
        if intersection:
            score += 20

    # +15 sempre (passou pelo filtro de janela)
    score += 15

    # +10 se valor dos pedidos é estável (cv < 30%)
    values = [float(o.get("valor_total") or 0) for o in orders if o.get("valor_total")]
    if len(values) >= 2:
        avg_val = mean(values)
        sd_val = pstdev(values)
        if avg_val > 0 and (sd_val / avg_val) < 0.30:
            score += 10
    elif len(values) == 1:
        score += 10

    return score


def _build_last3(orders: list[dict]) -> list[dict]:
    recent = sorted(orders, key=lambda o: o.get("criado_em") or "", reverse=True)[:3]
    result = []
    for o in recent:
        items = o.get("itens_json") or []
        result.append({
            "numero": o.get("numero"),
            "data": (o.get("criado_em") or "")[:10],
            "valor_total": float(o.get("valor_total") or 0),
            "situacao": o.get("situacao_id"),
            "itens": [
                {
                    "codPro": str(item.get("codPro") or ""),
                    "desPro": str(item.get("desPro") or ""),
                    "qtdPed": float(item.get("qtdPed") or 0),
                    "vlrTotal": float(item.get("vlrTotal") or 0),
                }
                for item in items
            ],
        })
    return result


def _build_top_items(orders: list[dict]) -> list[dict]:
    counter: dict[str, dict] = {}
    for o in orders:
        for item in (o.get("itens_json") or []):
            code = str(item.get("codPro") or "").strip()
            if not code:
                continue
            if code not in counter:
                counter[code] = {
                    "codPro": code,
                    "desPro": str(item.get("desPro") or code),
                    "total_qtd": 0.0,
                    "aparicoes": 0,
                }
            counter[code]["total_qtd"] += float(item.get("qtdPed") or 0)
            counter[code]["aparicoes"] += 1
    return sorted(counter.values(), key=lambda x: x["aparicoes"], reverse=True)[:5]


# ─────────────────────────────────────────────────────────────────────────────

def cmd_run(dry_run: bool = False) -> dict:
    db = _db()
    now = _utc_now()
    today = now.date()
    from_45d = now - timedelta(days=45)
    from_30d = now - timedelta(days=30)

    logger.info("Buscando pedidos dos últimos 45 dias...")
    res = (
        db.table("clic_pedidos_integrados")
        .select("cpf_cnpj, numero, valor_total, situacao_id, criado_em, itens_json, raw_json")
        .gte("criado_em", from_45d.isoformat())
        .order("criado_em", desc=True)
        .limit(5000)
        .execute()
    )
    orders = res.data or []
    logger.info("Pedidos encontrados: %d", len(orders))

    # Agrupar por cpf_cnpj
    grouped: dict[str, list[dict]] = defaultdict(list)
    for o in orders:
        cpf = (o.get("cpf_cnpj") or "").strip()
        if cpf:
            grouped[cpf].append(o)

    # Buscar targets existentes para merge de status
    existing: dict[str, dict] = {}
    cpf_list = list(grouped.keys())
    for i in range(0, len(cpf_list), 200):
        batch = cpf_list[i:i + 200]
        r = (
            db.table("recurrence_targets")
            .select("id, cpf_cnpj, status")
            .in_("cpf_cnpj", batch)
            .execute()
        )
        for t in r.data or []:
            existing[t["cpf_cnpj"]] = t

    inserted = 0
    skipped = 0
    errors: list[dict] = []

    for cpf, cpf_orders in grouped.items():
        try:
            # Contar pedidos nos últimos 30 dias
            orders_30d = [
                o for o in cpf_orders
                if (_parse_date(o.get("criado_em")) or now) >= from_30d
            ]
            if len(orders_30d) < 2:
                skipped += 1
                continue

            sorted_orders = sorted(cpf_orders, key=lambda o: o.get("criado_em") or "")
            dates = [_parse_date(o.get("criado_em")) for o in sorted_orders]
            dates = [d for d in dates if d]

            if len(dates) < 2:
                skipped += 1
                continue

            intervals = [(dates[i] - dates[i - 1]).days for i in range(1, len(dates))]
            avg_interval = mean(intervals)

            if avg_interval <= 0:
                skipped += 1
                continue

            last_order_dt = dates[-1]
            last_order_date = last_order_dt.date()

            # Pular quem comprou nos últimos 3 dias
            if (today - last_order_date).days < 3:
                skipped += 1
                continue

            next_expected_date = (last_order_dt + timedelta(days=round(avg_interval))).date()
            days_until = (next_expected_date - today).days

            # Janela: today >= next_expected - 2 → days_until <= 2
            if days_until > 2:
                skipped += 1
                continue

            # Extrair dados do cliente
            nome = ""
            phone = ""
            cod_cli = None
            for o in sorted(cpf_orders, key=lambda x: x.get("criado_em") or "", reverse=True):
                raw = o.get("raw_json") or {}
                if not nome:
                    nome = _extract_name(raw)
                if not phone:
                    phone = _extract_phone(raw)
                if cod_cli is None:
                    cod_cli = _extract_cod_cli(raw)
                if nome and phone and cod_cli:
                    break

            tier = _classify_tier(len(orders_30d))
            score = _calc_score(len(orders_30d), [float(x) for x in intervals], sorted_orders)
            last3 = _build_last3(sorted_orders)
            top_items = _build_top_items(sorted_orders)

            if dry_run:
                logger.info(
                    "[DRY-RUN] %s | tier=%s | score=%d | days_until=%d | phone=%s",
                    nome or cpf, tier, score, days_until, phone or "—",
                )
                inserted += 1
                continue

            metrics_update = {
                "customer_name": nome or f"Cliente {cpf}",
                "customer_phone": phone or None,
                "cod_rep": None,
                "recurrence_interval_days": round(avg_interval, 1),
                "recurrence_tier": tier,
                "last_order_date": last_order_date.isoformat(),
                "predicted_next_order_date": next_expected_date.isoformat(),
                "days_until_predicted": days_until,
                "orders_count_30d": len(orders_30d),
                "last_3_orders_json": last3,
                "top_items_json": top_items,
                "updated_at": now.isoformat(),
            }

            ex = existing.get(cpf)
            if not ex:
                row = {
                    **metrics_update,
                    "cpf_cnpj": cpf,
                    "status": "candidate",
                    "ai_validated": False,
                    "created_at": now.isoformat(),
                }
                db.table("recurrence_targets").insert(row).execute()
            else:
                current_status = ex.get("status", "candidate")
                if current_status in ("candidate", "ai_rejected"):
                    metrics_update["status"] = "candidate"
                    metrics_update["ai_validated"] = False
                    metrics_update["ai_decision"] = None
                    metrics_update["ai_reasoning"] = None
                db.table("recurrence_targets").update(metrics_update).eq("id", ex["id"]).execute()

            inserted += 1

        except Exception as exc:
            logger.error("Erro ao processar %s: %s", cpf, exc)
            errors.append({"cpf_cnpj": cpf, "error": str(exc)})

    return {
        "inserted_or_updated": inserted,
        "skipped": skipped,
        "errors": errors,
        "dry_run": dry_run,
    }


def cmd_overview(status: str | None, page: int, page_size: int) -> dict:
    db = _db()

    # Busca todos os status de uma vez para calcular stats em Python
    all_res = db.table("recurrence_targets").select("id, status").execute()
    all_items = all_res.data or []

    status_counts: dict[str, int] = defaultdict(int)
    for t in all_items:
        status_counts[t.get("status", "candidate")] += 1

    total = status_counts.get(status) if status else sum(status_counts.values())

    query = db.table("recurrence_targets").select("*")
    if status:
        query = query.eq("status", status)

    start = (page - 1) * page_size
    end = start + page_size - 1
    res = query.order("updated_at", desc=True).range(start, end).execute()
    targets = res.data or []

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": max(1, -(-total // page_size)) if total else 1,
        "stats": {
            "candidate": status_counts.get("candidate", 0),
            "ai_approved": status_counts.get("ai_approved", 0),
            "ai_rejected": status_counts.get("ai_rejected", 0),
            "dispatched": status_counts.get("dispatched", 0),
            "responded": status_counts.get("responded", 0),
            "converted": status_counts.get("converted", 0),
            "opted_out": status_counts.get("opted_out", 0),
        },
        "targets": targets,
    }


def cmd_detail(cpf: str | None, target_id: str | None) -> dict:
    db = _db()
    if target_id:
        res = db.table("recurrence_targets").select("*").eq("id", target_id).limit(1).execute()
    elif cpf:
        res = db.table("recurrence_targets").select("*").eq("cpf_cnpj", cpf).limit(1).execute()
    else:
        raise ValueError("Informe --cpf ou --id")

    if not res.data:
        raise ValueError("Target não encontrado")
    return res.data[0]


# ─────────────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(description="Pipeline de recompra — Recorrência")
    subparsers = parser.add_subparsers(dest="command", required=True)

    p_run = subparsers.add_parser("run", help="Job diário: calcula e persiste candidatos")
    p_run.add_argument("--dry-run", action="store_true", help="Apenas loga, não persiste")

    p_ov = subparsers.add_parser("overview", help="Lista targets para o frontend")
    p_ov.add_argument("--status", default=None,
                      choices=["candidate", "ai_approved", "ai_rejected",
                               "dispatched", "responded", "converted", "opted_out"])
    p_ov.add_argument("--page", type=int, default=1)
    p_ov.add_argument("--page-size", dest="page_size", type=int, default=50)

    p_det = subparsers.add_parser("detail", help="Detalhe de um target")
    p_det.add_argument("--cpf", default=None)
    p_det.add_argument("--id", dest="target_id", default=None)

    args = parser.parse_args()

    try:
        if args.command == "run":
            return success(cmd_run(dry_run=args.dry_run))
        if args.command == "overview":
            return success(cmd_overview(args.status, args.page, args.page_size))
        if args.command == "detail":
            return success(cmd_detail(args.cpf, args.target_id))
        return failure("Comando não suportado")
    except Exception as exc:
        logger.exception("Falha no módulo recorrência")
        return failure(str(exc))


if __name__ == "__main__":
    raise SystemExit(main())
