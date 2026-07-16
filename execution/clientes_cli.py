"""
clientes_cli.py
===============
Lista e detalha clientes a partir de rep_order_base + clic_clientes.
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
CUSTOMER_PROFILES_KEY = "clic_customer_profiles"


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
    tabelas_preco = c.get("tabelasPreco") or []
    tabela_principal = tabelas_preco[0] if tabelas_preco else {}
    tabela_especial = c.get("tabelaEspecial") or None
    return {
        "nome": c.get("fantasia") or c.get("razaoSocial") or "",
        "razao_social": c.get("razaoSocial") or "",
        "fantasia": c.get("fantasia") or "",
        "email": c.get("email") or "",
        "telefone": telefones[0].get("valor") if telefones else "",
        "cidade": c.get("cidade") or "",
        "uf": c.get("uf") or "",
        "ativo": True,
        "tabela_preco_codigo": tabela_principal.get("codigoTabela") or None,
        "tabela_preco_nome": tabela_principal.get("nomeTabela") or None,
        "tabelas_especiais_json": tabela_especial if tabela_especial else None,
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


def _build_row_from_order(order: dict, metricas: dict, profile: dict | None = None) -> dict:
    profile = profile or {}
    cod_cli = order.get("cod_cli")
    document = re.sub(
        r"\D",
        "",
        str(profile.get("documento") or order.get("customer_document") or ""),
    ) or None
    external_id = document or str(cod_cli or "")
    name = (
        profile.get("nome")
        or profile.get("razao_social")
        or profile.get("fantasia")
        or order.get("customer_name")
        or f"Cliente {cod_cli or external_id}"
    )
    return {
        "external_id": external_id,
        "cod_cli": cod_cli,
        "documento": document or str(cod_cli or ""),
        "source": order.get("source") or "clic_vendas",
        "synced_at": order.get("updated_at") or order.get("erp_synced_at"),
        "nome": name,
        "razao_social": profile.get("razao_social") or name,
        "fantasia": profile.get("fantasia") or name,
        "email": profile.get("email") or "",
        "telefone": profile.get("telefone") or metricas.get("telefone") or "",
        "cidade": profile.get("cidade") or "",
        "uf": profile.get("uf") or "",
        "ativo": True,
        "tabela_preco_codigo": profile.get("tabela_preco_codigo") or metricas.get("tabela_preco_codigo"),
        "tabela_preco_nome": profile.get("tabela_preco_nome") or metricas.get("tabela_preco_nome"),
        "tabelas_especiais_json": metricas.get("tabelas_especiais_json"),
        "total_pedidos": metricas.get("total_pedidos") or order.get("total_pedidos"),
        "valor_total_acumulado": float(metricas.get("valor_total_acumulado") or order.get("valor_total_acumulado") or 0),
        "ultimo_pedido_em": str(metricas.get("ultimo_pedido_em") or order.get("dat_emi") or ""),
        "ultimo_pedido_valor": float(order.get("order_total_value") or 0),
        "ultimo_pedido_numero": order.get("num_ped"),
        "ultimo_pedido_status": order.get("sit_ped"),
        "primeiro_pedido_em": str(metricas.get("primeiro_pedido_em") or ""),
        "dias_entre_pedidos_media": float(metricas.get("dias_entre_pedidos_media") or 0) if metricas.get("dias_entre_pedidos_media") is not None else None,
        "proximo_pedido_estimado_em": str(metricas.get("proximo_pedido_estimado_em") or ""),
        "top_produtos_json": metricas.get("top_produtos_json"),
        "historico_situacoes_json": metricas.get("historico_situacoes_json"),
    }


def _build_row_from_profile(profile: dict, metricas: dict | None = None) -> dict:
    metricas = metricas or {}
    cod_cli = profile.get("cod_cli")
    document = re.sub(r"\D", "", str(profile.get("documento") or ""))
    name = (
        profile.get("nome")
        or profile.get("razao_social")
        or profile.get("fantasia")
        or f"Cliente {cod_cli or document}"
    )
    return {
        "external_id": document or str(cod_cli or ""),
        "cod_cli": cod_cli,
        "documento": document or str(cod_cli or ""),
        "source": profile.get("source") or "clic_vendas_profile",
        "synced_at": profile.get("updated_at"),
        "nome": name,
        "razao_social": profile.get("razao_social") or name,
        "fantasia": profile.get("fantasia") or name,
        "email": profile.get("email") or "",
        "telefone": profile.get("telefone") or metricas.get("telefone") or "",
        "cidade": profile.get("cidade") or "",
        "uf": profile.get("uf") or "",
        "ativo": profile.get("situacao") != "I",
        "tabela_preco_codigo": profile.get("tabela_preco_codigo") or metricas.get("tabela_preco_codigo"),
        "tabela_preco_nome": profile.get("tabela_preco_nome") or metricas.get("tabela_preco_nome"),
        "tabelas_especiais_json": metricas.get("tabelas_especiais_json"),
        "total_pedidos": metricas.get("total_pedidos") or 0,
        "valor_total_acumulado": float(metricas.get("valor_total_acumulado") or 0),
        "ultimo_pedido_em": str(metricas.get("ultimo_pedido_em") or ""),
        "ultimo_pedido_valor": 0,
        "ultimo_pedido_numero": None,
        "ultimo_pedido_status": None,
        "primeiro_pedido_em": str(metricas.get("primeiro_pedido_em") or ""),
        "dias_entre_pedidos_media": float(metricas.get("dias_entre_pedidos_media") or 0) if metricas.get("dias_entre_pedidos_media") is not None else None,
        "proximo_pedido_estimado_em": str(metricas.get("proximo_pedido_estimado_em") or ""),
        "top_produtos_json": metricas.get("top_produtos_json"),
        "historico_situacoes_json": metricas.get("historico_situacoes_json"),
    }


def _extract_rep_code(raw_json: dict) -> int | None:
    representante = (raw_json or {}).get("representante") or (raw_json or {}).get("autor") or {}
    candidates = (
        representante.get("backoffice", {}).get("codigo") if isinstance(representante.get("backoffice"), dict) else None,
        representante.get("codigo"),
        representante.get("acesso", {}).get("login") if isinstance(representante.get("acesso"), dict) else None,
    )
    for candidate in candidates:
        try:
            return int(str(candidate).strip())
        except (TypeError, ValueError):
            continue
    return None


def _latest_by_cpf(db, cod_rep: int | None = None) -> dict[str, dict]:
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
        if cod_rep is not None and _extract_rep_code(p.get("raw_json") or {}) != cod_rep:
            continue
        cpf = p.get("cpf_cnpj") or ""
        if cpf and cpf not in latest:
            latest[cpf] = p
    return latest


def _latest_orders_by_customer(db, cod_rep: int | None = None) -> dict[str, dict]:
    """Retorna o pedido mais recente por cliente a partir da base oficial por representante."""
    select_fields = "cod_cli,cod_rep,customer_document,customer_name,num_ped,dat_emi,sit_ped,order_total_value,source,erp_synced_at,updated_at"
    fallback_select_fields = "cod_cli,cod_rep,num_ped,dat_emi,sit_ped,order_total_value,source,erp_synced_at,updated_at"

    def execute(fields: str):
        q = (
            db.table("rep_order_base")
            .select(fields)
            .order("dat_emi", desc=True)
            .limit(10000)
        )
        if cod_rep is not None:
            q = q.eq("cod_rep", cod_rep)
        return q.execute().data or []

    try:
        rows = execute(select_fields)
    except Exception as exc:
        if "customer_document" not in str(exc) and "customer_name" not in str(exc):
            raise
        rows = execute(fallback_select_fields)

    latest: dict[str, dict] = {}
    totals: dict[str, dict] = {}
    for order in rows:
        key = str(order.get("cod_cli") or order.get("customer_document") or "")
        if not key:
            continue
        total = totals.setdefault(key, {"total_pedidos": 0, "valor_total_acumulado": 0.0})
        total["total_pedidos"] += 1
        total["valor_total_acumulado"] += float(order.get("order_total_value") or 0)
        if key not in latest:
            latest[key] = order

    for key, order in latest.items():
        order.update(totals.get(key, {}))
    return latest


def _metricas_map(db, cpfs: list[str]) -> dict[str, dict]:
    result: dict[str, dict] = {}
    for i in range(0, len(cpfs), 200):
        batch = cpfs[i: i + 200]
        res = (
            db.table("clic_clientes")
            .select("cpf_cnpj, telefone, tabela_preco_codigo, tabela_preco_nome, tabelas_especiais_json, total_pedidos, valor_total_acumulado, primeiro_pedido_em, ultimo_pedido_em, dias_entre_pedidos_media, proximo_pedido_estimado_em, top_produtos_json, historico_situacoes_json")
            .in_("cpf_cnpj", batch)
            .execute()
        )
        for m in res.data or []:
            result[m["cpf_cnpj"]] = m
    return result


def _profiles_map(db) -> dict[str, dict]:
    try:
        rows = (
            db.table("system_settings")
            .select("value")
            .eq("key", CUSTOMER_PROFILES_KEY)
            .limit(1)
            .execute()
            .data
            or []
        )
    except Exception as exc:
        logger.warning("Falha ao buscar perfis de clientes: %s", exc)
        return {}

    value = rows[0].get("value") if rows else {}
    return value if isinstance(value, dict) else {}


def list_customers(query: str | None, page: int, page_size: int, cod_rep: int | None = None) -> dict:
    db = _db()
    latest = _latest_orders_by_customer(db, cod_rep)
    profiles = _profiles_map(db)

    rows = list(latest.items())
    order_codes = {str((order or {}).get("cod_cli") or "") for _, order in rows}
    for code, profile in profiles.items():
        if not isinstance(profile, dict) or str(code) in order_codes:
            continue
        if cod_rep is not None:
            try:
                profile_rep = int(str(profile.get("cod_rep") or "").strip())
            except (TypeError, ValueError):
                continue
            if profile_rep != cod_rep:
                continue
        rows.append((str(code), {"cod_cli": profile.get("cod_cli") or code, "_profile_only": True}))

    if query:
        q = query.strip().lower()
        def matches(item: tuple) -> bool:
            key, p = item
            profile = profiles.get(str(p.get("cod_cli") or "")) or {}
            return (
                q in (profile.get("nome") or "").lower()
                or q in (profile.get("razao_social") or "").lower()
                or q in (profile.get("fantasia") or "").lower()
                or q in str(profile.get("documento") or "").lower()
                or q in (p.get("customer_name") or "").lower()
                or q in str(p.get("cod_cli") or "").lower()
                or q in str(p.get("customer_document") or "").lower()
                or q in key.lower()
            )
        rows = [item for item in rows if matches(item)]

    total = len(rows)
    pages = max(1, (total + page_size - 1) // page_size)
    page_rows = rows[(page - 1) * page_size: page * page_size]

    cpfs = []
    for _, order in page_rows:
        profile = profiles.get(str(order.get("cod_cli") or "")) or {}
        document = re.sub(
            r"\D",
            "",
            str(profile.get("documento") or order.get("customer_document") or ""),
        )
        if document:
            cpfs.append(document)
    metricas = _metricas_map(db, cpfs)

    clientes = [
        (
            _build_row_from_profile(
                profiles.get(str(order.get("cod_cli") or "")) or {},
                metricas.get(
                    re.sub(r"\D", "", str((profiles.get(str(order.get("cod_cli") or "")) or {}).get("documento") or "")),
                    {},
                ),
            )
            if order.get("_profile_only")
            else _build_row_from_order(
                order,
                metricas.get(
                    re.sub(
                        r"\D",
                        "",
                        str(
                            (profiles.get(str(order.get("cod_cli") or "")) or {}).get("documento")
                            or order.get("customer_document")
                            or ""
                        ),
                    ),
                    {},
                ),
                profiles.get(str(order.get("cod_cli") or "")),
            )
        )
        for _, order in page_rows
    ]
    active = total

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": pages,
        "active": active,
        "inactive": 0,
        "clientes": clientes,
    }


def sync_customers(query: str | None) -> dict:
    t0 = time.perf_counter()
    db = _db()
    latest = _latest_orders_by_customer(db)

    count = 0
    for _key, _order in latest.items():
        count += 1

    duration_ms = int((time.perf_counter() - t0) * 1000)
    return {
        "status": "success",
        "message": f"{count} clientes carregados da base local.",
        "total_fetched": count,
        "total_upserted": 0,
        "duration_ms": duration_ms,
    }


def get_customer(cod_cli: int, cod_rep: int | None = None) -> dict:
    db = _db()
    select_fields = "cod_cli,cod_rep,customer_document,customer_name,num_ped,dat_emi,sit_ped,order_total_value,source,erp_synced_at,updated_at"
    fallback_select_fields = "cod_cli,cod_rep,num_ped,dat_emi,sit_ped,order_total_value,source,erp_synced_at,updated_at"

    def execute(fields: str):
        query = (
            db.table("rep_order_base")
            .select(fields)
            .eq("cod_cli", cod_cli)
            .order("dat_emi", desc=True)
            .limit(1)
        )
        if cod_rep is not None:
            query = query.eq("cod_rep", cod_rep)
        return query.execute()

    try:
        res = execute(select_fields)
    except Exception as exc:
        if "customer_document" not in str(exc) and "customer_name" not in str(exc):
            raise
        res = execute(fallback_select_fields)
    row = (res.data or [None])[0]
    if not row:
        profile = _profiles_map(db).get(str(cod_cli)) or {}
        if not profile:
            raise ValueError(f"Cliente {cod_cli} nÃ£o encontrado")
        if cod_rep is not None:
            try:
                profile_rep = int(str(profile.get("cod_rep") or "").strip())
            except (TypeError, ValueError):
                profile_rep = None
            if profile_rep != cod_rep:
                raise ValueError(f"Cliente {cod_cli} nÃ£o encontrado")
        document = re.sub(r"\D", "", str(profile.get("documento") or ""))
        metricas = _metricas_map(db, [document]) if document else {}
        return _build_row_from_profile(profile, metricas.get(document, {}))
    profile = _profiles_map(db).get(str(cod_cli)) or {}
    document = re.sub(r"\D", "", str(profile.get("documento") or row.get("customer_document") or ""))
    metricas = _metricas_map(db, [document]) if document else {}
    return _build_row_from_order(row, metricas.get(document, {}), profile)


def get_customer_from_integrated_history(cod_cli: int, cod_rep: int | None = None) -> dict:
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
    if cod_rep is not None and _extract_rep_code(row.get("raw_json") or {}) != cod_rep:
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
    p_list.add_argument("--cod-rep", dest="cod_rep", type=int, default=None)

    p_sync = subparsers.add_parser("sync")
    p_sync.add_argument("--query", default=None)

    p_detail = subparsers.add_parser("detail")
    p_detail.add_argument("--cod-cli", dest="cod_cli", type=int, required=True)
    p_detail.add_argument("--cod-rep", dest="cod_rep", type=int, default=None)

    args = parser.parse_args()

    try:
        if args.command == "list":
            return success(list_customers(args.query, args.page, args.page_size, args.cod_rep))
        if args.command == "sync":
            return success(sync_customers(args.query))
        if args.command == "detail":
            return success(get_customer(args.cod_cli, args.cod_rep))
        return failure("Comando nao suportado")
    except Exception as exc:
        logger.exception("Falha no modulo clientes")
        return failure(str(exc))


if __name__ == "__main__":
    raise SystemExit(main())
