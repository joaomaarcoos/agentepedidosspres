"""
clientes_cli.py
===============
Lista e detalha clientes a partir de clic_pedidos_integrados + clic_clientes.
Saída em JSON no stdout; logs no stderr.

Subcomandos:
  list   --query Q --page N --page-size N
  sync   --query Q
  detail --cod-cli N
"""

import argparse
import json
import logging
import os
import re
import sys
import time

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


def _extract_info(raw_json: dict) -> dict:
    c = (raw_json or {}).get("cliente") or {}
    telefones = c.get("telefones") or []
    return {
        "nome": c.get("fantasia") or c.get("razaoSocial") or "",
        "razao_social": c.get("razaoSocial") or "",
        "fantasia": c.get("fantasia") or "",
        "email": c.get("email") or "",
        "telefone": telefones[0].get("valor") if telefones else "",
        "cidade": c.get("cidade") or "",
        "uf": c.get("uf") or "",
        "ativo": True,
    }


def _build_row(cpf: str, pedido: dict, metricas: dict) -> dict:
    info = _extract_info(pedido.get("raw_json") or {})
    return {
        "external_id": cpf,
        "cod_cli": _cpf_to_int(cpf),
        "documento": cpf,
        "source": "clicvendas",
        "synced_at": pedido.get("criado_em"),
        **info,
        "total_pedidos": metricas.get("total_pedidos"),
        "valor_total_acumulado": float(metricas.get("valor_total_acumulado") or 0) if metricas.get("valor_total_acumulado") is not None else None,
        "ultimo_pedido_em": str(metricas.get("ultimo_pedido_em") or pedido.get("criado_em") or ""),
        "ultimo_pedido_valor": float(pedido.get("valor_total") or 0),
        "ultimo_pedido_numero": pedido.get("numero"),
        "ultimo_pedido_status": pedido.get("situacao_id"),
        "primeiro_pedido_em": str(metricas.get("primeiro_pedido_em") or ""),
        "dias_entre_pedidos_media": float(metricas.get("dias_entre_pedidos_media") or 0) if metricas.get("dias_entre_pedidos_media") is not None else None,
        "proximo_pedido_estimado_em": str(metricas.get("proximo_pedido_estimado_em") or ""),
        "top_produtos_json": metricas.get("top_produtos_json"),
        "historico_situacoes_json": metricas.get("historico_situacoes_json"),
    }


def _latest_by_cpf(db) -> dict[str, dict]:
    """Retorna o pedido mais recente por cpf_cnpj."""
    res = (
        db.table("clic_pedidos_integrados")
        .select("cpf_cnpj, numero, valor_total, situacao_id, criado_em, raw_json")
        .order("criado_em", desc=True)
        .limit(2000)
        .execute()
    )
    latest: dict[str, dict] = {}
    for p in res.data or []:
        cpf = p.get("cpf_cnpj") or ""
        if cpf and cpf not in latest:
            latest[cpf] = p
    return latest


def _metricas_map(db, cpfs: list[str]) -> dict[str, dict]:
    result: dict[str, dict] = {}
    for i in range(0, len(cpfs), 200):
        batch = cpfs[i: i + 200]
        res = (
            db.table("clic_clientes")
            .select("cpf_cnpj, total_pedidos, valor_total_acumulado, primeiro_pedido_em, ultimo_pedido_em, dias_entre_pedidos_media, proximo_pedido_estimado_em, top_produtos_json, historico_situacoes_json")
            .in_("cpf_cnpj", batch)
            .execute()
        )
        for m in res.data or []:
            result[m["cpf_cnpj"]] = m
    return result


def list_customers(query: str | None, page: int, page_size: int) -> dict:
    db = _db()
    latest = _latest_by_cpf(db)

    rows = list(latest.items())

    if query:
        q = query.strip().lower()
        def matches(item: tuple) -> bool:
            cpf, p = item
            info = _extract_info(p.get("raw_json") or {})
            return (
                q in (info.get("razao_social") or "").lower()
                or q in (info.get("fantasia") or "").lower()
                or q in cpf.lower()
                or q in (info.get("email") or "").lower()
                or q in (info.get("telefone") or "").lower()
            )
        rows = [item for item in rows if matches(item)]

    total = len(rows)
    pages = max(1, (total + page_size - 1) // page_size)
    page_rows = rows[(page - 1) * page_size: page * page_size]

    cpfs = [cpf for cpf, _ in page_rows]
    metricas = _metricas_map(db, cpfs)

    clientes = [_build_row(cpf, p, metricas.get(cpf, {})) for cpf, p in page_rows]
    active = sum(1 for c in clientes if c.get("ativo", True))

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": pages,
        "active": active,
        "inactive": total - active,
        "clientes": clientes,
    }


def sync_customers(query: str | None) -> dict:
    t0 = time.perf_counter()
    db = _db()
    latest = _latest_by_cpf(db)
    cpfs = list(latest.keys())
    metricas = _metricas_map(db, cpfs)

    count = 0
    for cpf, p in latest.items():
        _build_row(cpf, p, metricas.get(cpf, {}))
        count += 1

    duration_ms = int((time.perf_counter() - t0) * 1000)
    return {
        "status": "success",
        "message": f"{count} clientes carregados da base local.",
        "total_fetched": count,
        "total_upserted": 0,
        "duration_ms": duration_ms,
    }


def get_customer(cod_cli: int) -> dict:
    db = _db()
    cpf_str = str(cod_cli)
    res = (
        db.table("clic_pedidos_integrados")
        .select("cpf_cnpj, numero, valor_total, situacao_id, criado_em, raw_json")
        .eq("cpf_cnpj", cpf_str)
        .order("criado_em", desc=True)
        .limit(1)
        .execute()
    )
    row = (res.data or [None])[0]
    if not row:
        raise ValueError(f"Cliente {cod_cli} não encontrado")
    cpf = row["cpf_cnpj"]
    metricas = _metricas_map(db, [cpf])
    return _build_row(cpf, row, metricas.get(cpf, {}))


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s",
                        handlers=[logging.StreamHandler(sys.stderr)])

    parser = argparse.ArgumentParser(description="CLI interna do modulo Clientes")
    subparsers = parser.add_subparsers(dest="command", required=True)

    p_list = subparsers.add_parser("list")
    p_list.add_argument("--query", default=None)
    p_list.add_argument("--page", type=int, default=1)
    p_list.add_argument("--page-size", dest="page_size", type=int, default=50)

    p_sync = subparsers.add_parser("sync")
    p_sync.add_argument("--query", default=None)

    p_detail = subparsers.add_parser("detail")
    p_detail.add_argument("--cod-cli", dest="cod_cli", type=int, required=True)

    args = parser.parse_args()

    try:
        if args.command == "list":
            return success(list_customers(args.query, args.page, args.page_size))
        if args.command == "sync":
            return success(sync_customers(args.query))
        if args.command == "detail":
            return success(get_customer(args.cod_cli))
        return failure("Comando nao suportado")
    except Exception as exc:
        logger.exception("Falha no modulo clientes")
        return failure(str(exc))


if __name__ == "__main__":
    raise SystemExit(main())
