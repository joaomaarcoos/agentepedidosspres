"""
ativacao_cli.py
===============
Pipeline de Ativação Comercial.

Transforma clientes com status='ai_rejected' (target_type='recorrencia') em candidatos
de ativação comercial consultiva (target_type='ativacao').

Não assume padrão de recompra previsível. Aplica cooldown de 30 dias.
Não relê a tabela de pedidos — usa dados já presentes em recurrence_targets.

Subcomandos:
  run      [--dry-run] [--limit N]
  overview [--status S] [--page N] [--page-size N]
  detail   [--id UUID]
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)],
)
logger = logging.getLogger(__name__)

COOLDOWN_DAYS = 30

ACTIVATION_STATUSES = {"activation_candidate", "activation_approved", "activation_rejected"}


# ─── I/O ─────────────────────────────────────────────────────────────────────

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


# ─── Lógica principal ─────────────────────────────────────────────────────────

def cmd_run(dry_run: bool, limit: int) -> dict:
    db = _db()
    now = datetime.now(timezone.utc)
    cooldown_threshold = now - timedelta(days=COOLDOWN_DAYS)

    # 1. Buscar registros ai_rejected do pipeline de recorrência
    res = (
        db.table("recurrence_targets")
        .select("*")
        .eq("status", "ai_rejected")
        .eq("target_type", "recorrencia")
        .order("updated_at", desc=False)
        .limit(limit * 3)  # busca mais para compensar os que serão filtrados por cooldown
        .execute()
    )
    rejected = res.data or []
    logger.info("ai_rejected encontrados: %d", len(rejected))

    if not rejected:
        return {
            "processed": 0, "eligible": 0,
            "skipped_cooldown": 0, "skipped_no_data": 0,
            "inserted": 0, "updated": 0, "errors": [], "dry_run": dry_run,
        }

    # 2. Buscar registros de ativação existentes para os CPFs encontrados
    cpfs = list({r["cpf_cnpj"] for r in rejected if r.get("cpf_cnpj")})
    existing_map: dict[str, dict] = {}
    if cpfs:
        chunk_size = 100
        for i in range(0, len(cpfs), chunk_size):
            chunk = cpfs[i:i + chunk_size]
            ex_res = (
                db.table("recurrence_targets")
                .select("id, cpf_cnpj, status, updated_at")
                .eq("target_type", "ativacao")
                .in_("cpf_cnpj", chunk)
                .execute()
            )
            for row in (ex_res.data or []):
                existing_map[row["cpf_cnpj"]] = row

    processed = 0
    eligible = 0
    skipped_cooldown = 0
    skipped_no_data = 0
    inserted = 0
    updated = 0
    errors: list[dict] = []

    seen_cpfs: set[str] = set()

    for source in rejected:
        if processed >= limit:
            break

        cpf = source.get("cpf_cnpj")
        if not cpf or cpf in seen_cpfs:
            continue
        seen_cpfs.add(cpf)
        processed += 1

        nome = source.get("customer_name") or cpf

        # Verificar se tem dados suficientes
        has_orders = bool(source.get("last_3_orders_json") or source.get("top_items_json"))
        if not has_orders:
            logger.info("Pulando %s — sem dados de pedidos", nome)
            skipped_no_data += 1
            continue

        # Verificar cooldown
        existing = existing_map.get(cpf)
        if existing:
            upd = existing.get("updated_at")
            if upd:
                try:
                    upd_dt = datetime.fromisoformat(upd.replace("Z", "+00:00"))
                    if upd_dt > cooldown_threshold:
                        logger.info(
                            "Cooldown ativo para %s (última ativação: %s)",
                            nome, upd[:10],
                        )
                        skipped_cooldown += 1
                        continue
                except (ValueError, TypeError):
                    pass

        eligible += 1

        if dry_run:
            logger.info("[DRY-RUN] Elegível: %s", nome)
            continue

        # Montar registro de ativação
        record = {
            "cpf_cnpj": cpf,
            "target_type": "ativacao",
            "status": "activation_candidate",
            "customer_name": source.get("customer_name"),
            "customer_phone": source.get("customer_phone"),
            "cod_rep": source.get("cod_rep"),
            "last_order_date": source.get("last_order_date"),
            "orders_count_30d": source.get("orders_count_30d"),
            "last_3_orders_json": source.get("last_3_orders_json"),
            "top_items_json": source.get("top_items_json"),
            # Campos de recorrência não aplicáveis
            "recurrence_interval_days": None,
            "recurrence_tier": None,
            "predicted_next_order_date": None,
            "days_until_predicted": None,
            "ai_validated": False,
            "ai_decision": None,
            "ai_reasoning": None,
            "dispatched_at": None,
            "updated_at": now.isoformat(),
        }

        try:
            if existing:
                # Atualizar registro existente (fora do cooldown)
                db.table("recurrence_targets").update(record).eq("id", existing["id"]).execute()
                updated += 1
                logger.info("Atualizado: %s", nome)
            else:
                record["created_at"] = now.isoformat()
                db.table("recurrence_targets").insert(record).execute()
                inserted += 1
                logger.info("Inserido: %s", nome)

        except Exception as exc:
            logger.error("Erro ao processar %s: %s", nome, exc)
            errors.append({"cpf_cnpj": cpf, "error": str(exc)})

    return {
        "processed": processed,
        "eligible": eligible,
        "skipped_cooldown": skipped_cooldown,
        "skipped_no_data": skipped_no_data,
        "inserted": inserted,
        "updated": updated,
        "errors": errors,
        "dry_run": dry_run,
    }


def cmd_overview(status: str | None, page: int, page_size: int) -> dict:
    db = _db()

    # Contar totais por status para ativação
    stats_res = (
        db.table("recurrence_targets")
        .select("status")
        .eq("target_type", "ativacao")
        .execute()
    )
    all_rows = stats_res.data or []
    stats: dict[str, int] = {
        "activation_candidate": 0,
        "activation_approved": 0,
        "activation_rejected": 0,
        "dispatched": 0,
    }
    for row in all_rows:
        s = row.get("status", "")
        if s in stats:
            stats[s] += 1

    total = len(all_rows)

    # Filtro por status
    query = db.table("recurrence_targets").select("*").eq("target_type", "ativacao")
    if status:
        query = query.eq("status", status)
        total = stats.get(status, 0)

    offset = (page - 1) * page_size
    res = query.order("updated_at", desc=True).range(offset, offset + page_size - 1).execute()
    targets = res.data or []

    pages = max(1, (total + page_size - 1) // page_size)

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": pages,
        "stats": stats,
        "targets": targets,
    }


def cmd_detail(target_id: str) -> dict:
    db = _db()
    res = (
        db.table("recurrence_targets")
        .select("*")
        .eq("id", target_id)
        .eq("target_type", "ativacao")
        .limit(1)
        .execute()
    )
    data = res.data or []
    if not data:
        raise RuntimeError(f"Target {target_id!r} não encontrado")
    return data[0]


# ─── CLI ──────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(description="Pipeline de Ativação Comercial")
    subparsers = parser.add_subparsers(dest="command", required=True)

    p_run = subparsers.add_parser("run")
    p_run.add_argument("--dry-run", action="store_true")
    p_run.add_argument("--limit", type=int, default=100)

    p_ov = subparsers.add_parser("overview")
    p_ov.add_argument("--status", default=None)
    p_ov.add_argument("--page", type=int, default=1)
    p_ov.add_argument("--page-size", type=int, default=50)

    p_det = subparsers.add_parser("detail")
    p_det.add_argument("--id", dest="target_id", required=True)

    args = parser.parse_args()

    try:
        if args.command == "run":
            return success(cmd_run(dry_run=args.dry_run, limit=args.limit))
        if args.command == "overview":
            return success(cmd_overview(
                status=args.status,
                page=args.page,
                page_size=args.page_size,
            ))
        if args.command == "detail":
            return success(cmd_detail(target_id=args.target_id))
        return failure("Comando não suportado")
    except Exception as exc:
        logger.exception("Falha no pipeline de ativação")
        return failure(str(exc))


if __name__ == "__main__":
    raise SystemExit(main())
