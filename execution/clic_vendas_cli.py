import argparse
import json
import logging
import os
import re
import sys
import time
import uuid
from collections import defaultdict
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(__file__))

from clic_vendas_client import ClicVendasClient
from fetch_pedidos_clic import _parse_pedidos
from supabase_client import SupabaseClient

logger = logging.getLogger(__name__)

REP_DOCUMENT = os.getenv("CLIC_VENDAS_REP_DOCUMENT", "18325136880")
SECRETARY_REFERENCE_RE = re.compile(r"\b(MSE-\d{6}-[A-Z0-9]{6})\b", re.I)
CUSTOMER_PROFILES_KEY = "clic_customer_profiles"
REPRESENTATIVE_PROFILES_KEY = "clic_representative_profiles"


def emit(payload: dict) -> None:
    sys.stdout.write(json.dumps(payload, ensure_ascii=False))
    sys.stdout.write("\n")


def success(data: dict) -> int:
    emit({"ok": True, "data": data})
    return 0


def failure(message: str) -> int:
    emit({"ok": False, "error": message})
    return 0


def _ensure_representatives(pedidos: list[dict], _db_client=None) -> None:
    """Garante que os representantes dos pedidos existam na tabela representatives."""
    from dotenv import load_dotenv as _ldenv
    _ldenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

    url = os.getenv("SUPABASE_URL", "").rstrip("/")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_ANON_KEY", "")
    if not url or not key:
        return

    from supabase import create_client
    client = create_client(url, key)

    # Coleta cod_rep e nomes únicos dos pedidos
    reps_to_create = {}
    for pedido in pedidos:
        cod_rep = pedido.get("codRep")
        if cod_rep and cod_rep not in reps_to_create:
            reps_to_create[cod_rep] = pedido.get("nomeRep") or f"Rep {cod_rep}"

    if not reps_to_create:
        return

    # Busca representantes existentes
    try:
        existing = client.table("representatives").select("cod_rep").in_("cod_rep", list(reps_to_create.keys())).execute()
        existing_codes = {r["cod_rep"] for r in (existing.data or [])}
    except Exception:
        existing_codes = set()

    # Insere os que não existem
    new_reps = [
        {"cod_rep": cod, "name": name, "active": True, "whatsapp_number": ""}
        for cod, name in reps_to_create.items()
        if cod not in existing_codes
    ]

    if new_reps:
        try:
            client.table("representatives").insert(new_reps).execute()
            logger.info("Criados %d representantes automaticamente", len(new_reps))
        except Exception as exc:
            logger.warning("Erro ao criar representantes: %s", exc)


def _upsert_tabela_preco_clientes(pedidos: list[dict]) -> None:
    """Persiste tabela de preço e telefone de cada cliente em clic_clientes."""
    from dotenv import load_dotenv as _ldenv
    _ldenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

    url = os.getenv("SUPABASE_URL", "").rstrip("/")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_ANON_KEY", "")
    if not url or not key:
        return

    from supabase import create_client
    client = create_client(url, key)

    # clic_clientes é indexada por documento (cpf_cnpj), a mesma chave usada em
    # clic_pedidos_integrados e nos fluxos de recorrência.
    customer_map: dict[str, dict] = {}
    for pedido in pedidos:
        cpf_cnpj = re.sub(r"\D", "", str(pedido.get("cpfCnpj") or ""))
        tabela_codigo = pedido.get("tabelaPreco")
        if not cpf_cnpj or not tabela_codigo:
            continue
        telefone = re.sub(r"\D", "", str(pedido.get("telefone") or ""))
        customer_map[cpf_cnpj] = {
            "cpf_cnpj": cpf_cnpj,
            "tabela_preco_codigo": tabela_codigo,
            "tabela_preco_nome": pedido.get("tabelaPrecoNome"),
            "tabelas_especiais_json": pedido.get("tabelasEspeciais") or None,
            "telefone": telefone or None,
        }

    if not customer_map:
        return

    rows = list(customer_map.values())
    try:
        client.table("clic_clientes").upsert(rows, on_conflict="cpf_cnpj").execute()
        logger.info("Tabela de preço: %d clientes atualizados em clic_clientes", len(rows))
    except Exception as exc:
        logger.warning("Erro ao upsert tabela de preço em clic_clientes: %s", exc)


def _upsert_customer_profiles(pedidos: list[dict]) -> None:
    """Persiste cadastro de clientes em system_settings sem depender de novas colunas."""
    from dotenv import load_dotenv as _ldenv
    _ldenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

    url = os.getenv("SUPABASE_URL", "").rstrip("/")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_ANON_KEY", "")
    if not url or not key:
        return

    from supabase import create_client
    client = create_client(url, key)

    profiles: dict[str, dict] = {}
    for pedido in pedidos:
        cod_cli = pedido.get("codCli")
        if not cod_cli:
            continue
        document = re.sub(r"\D", "", str(pedido.get("cpfCnpj") or "")) or None
        telefone = re.sub(r"\D", "", str(pedido.get("telefone") or "")) or None
        razao_social = str(pedido.get("razaoSocialCliente") or "").strip() or None
        fantasia = str(pedido.get("fantasiaCliente") or "").strip() or None
        nome = razao_social or fantasia or str(pedido.get("nomeCliente") or "").strip() or None
        profiles[str(cod_cli)] = {
            "cod_cli": cod_cli,
            "documento": document,
            "nome": nome,
            "razao_social": razao_social,
            "fantasia": fantasia,
            "email": str(pedido.get("emailCliente") or "").strip() or None,
            "telefone": telefone,
            "cidade": str(pedido.get("cidadeCliente") or "").strip() or None,
            "uf": str(pedido.get("ufCliente") or "").strip() or None,
            "tabela_preco_codigo": pedido.get("tabelaPreco"),
            "tabela_preco_nome": pedido.get("tabelaPrecoNome"),
            "updated_at": datetime.utcnow().isoformat() + "Z",
        }

    if not profiles:
        return

    try:
        rows = (
            client.table("system_settings")
            .select("value")
            .eq("key", CUSTOMER_PROFILES_KEY)
            .limit(1)
            .execute()
            .data
            or []
        )
        current = rows[0].get("value") if rows else {}
        if not isinstance(current, dict):
            current = {}
        current.update(profiles)
        client.table("system_settings").upsert(
            {"key": CUSTOMER_PROFILES_KEY, "value": current},
            on_conflict="key",
        ).execute()
        logger.info("Perfis de clientes: %d clientes atualizados em system_settings", len(profiles))
    except Exception as exc:
        logger.warning("Erro ao persistir perfis de clientes em system_settings: %s", exc)


def _upsert_representative_profiles(pedidos: list[dict]) -> None:
    """Persiste documento e nome de representantes em system_settings."""
    from dotenv import load_dotenv as _ldenv
    _ldenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

    url = os.getenv("SUPABASE_URL", "").rstrip("/")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_ANON_KEY", "")
    if not url or not key:
        return

    from supabase import create_client
    client = create_client(url, key)

    profiles: dict[str, dict] = {}
    for pedido in pedidos:
        cod_rep = pedido.get("codRep")
        if not cod_rep:
            continue
        document = re.sub(r"\D", "", str(pedido.get("documentoRep") or "")) or None
        razao_social = str(pedido.get("razaoSocialRep") or "").strip() or None
        fantasia = str(pedido.get("fantasiaRep") or "").strip() or None
        nome = razao_social or fantasia or str(pedido.get("nomeRep") or "").strip() or f"Rep {cod_rep}"
        profiles[str(cod_rep)] = {
            "cod_rep": cod_rep,
            "documento": document,
            "nome": nome,
            "razao_social": razao_social,
            "fantasia": fantasia,
            "updated_at": datetime.utcnow().isoformat() + "Z",
        }

    if not profiles:
        return

    try:
        rows = (
            client.table("system_settings")
            .select("value")
            .eq("key", REPRESENTATIVE_PROFILES_KEY)
            .limit(1)
            .execute()
            .data
            or []
        )
        current = rows[0].get("value") if rows else {}
        if not isinstance(current, dict):
            current = {}
        current.update(profiles)
        client.table("system_settings").upsert(
            {"key": REPRESENTATIVE_PROFILES_KEY, "value": current},
            on_conflict="key",
        ).execute()
        logger.info("Perfis de representantes: %d representantes atualizados", len(profiles))
    except Exception as exc:
        logger.warning("Erro ao persistir perfis de representantes em system_settings: %s", exc)


def _secretary_order_maps(db: SupabaseClient) -> tuple[dict[str, dict], dict[str, dict]]:
    if db.use_local or not db.client:
        return {}, {}
    try:
        rows = (
            db.client.table("secretary_orders")
            .select("id,protocol,instance_name,cod_rep,clic_order_number,status")
            .in_("status", ["submitted", "synced"])
            .limit(10000)
            .execute()
            .data
            or []
        )
    except Exception as exc:
        logger.warning("Falha ao carregar pedidos da Secretaria: %s", exc)
        return {}, {}
    by_number = {
        str(row.get("clic_order_number")): row
        for row in rows
        if row.get("clic_order_number") not in (None, "")
    }
    by_protocol = {
        str(row.get("protocol") or "").upper(): row
        for row in rows
        if row.get("protocol")
    }
    return by_number, by_protocol


def _secretary_origin(
    pedido: dict,
    by_number: dict[str, dict],
    by_protocol: dict[str, dict],
) -> dict | None:
    number = str(pedido.get("numPed") or "")
    if number and number in by_number:
        return by_number[number]
    match = SECRETARY_REFERENCE_RE.search(str(pedido.get("observacao") or ""))
    return by_protocol.get(match.group(1).upper()) if match else None


def _mark_secretary_orders_synced(
    db: SupabaseClient,
    matches: list[tuple[dict, dict]],
    synced_at: str,
) -> None:
    if db.use_local or not db.client:
        return
    for origin, pedido in matches:
        try:
            db.client.table("secretary_orders").update(
                {
                    "status": "synced",
                    "clic_order_number": str(
                        pedido.get("numPed") or origin.get("clic_order_number") or ""
                    ) or None,
                    "clic_external_id": pedido.get("externalId") or None,
                    "clic_status": pedido.get("sitPed") or None,
                    "synced_at": synced_at,
                    "updated_at": synced_at,
                }
            ).eq("id", origin["id"]).execute()
        except Exception as exc:
            logger.warning(
                "Falha ao reconciliar pedido da Secretaria %s: %s",
                origin.get("protocol"),
                exc,
            )


def _fetch_pedidos_paginated(
    client: ClicVendasClient,
    date_from: str,
    data_limite: datetime,
    rep_document: str | None = None,
    page_size: int = 100,
) -> tuple[list[dict], dict]:
    pedidos: list[dict] = []
    seen: set[tuple[int | None, int | None]] = set()
    skip = 0
    total_geral = None
    pages = 0

    while True:
        params = {
            "dataAlteracao": date_from,
            "sortBy": "dataCriacao",
            "sortDescAsc": "DESC",
            "fetch": 0,
            "skip": skip,
        }
        if rep_document:
            params["numeroDocumentoRepresentante"] = rep_document

        raw = client.get("/extpedidos", params=params)
        raw_rows = raw.get("dados") if isinstance(raw, dict) else raw
        raw_count = len(raw_rows or [])
        if isinstance(raw, dict) and raw.get("totalGeral") is not None:
            total_geral = raw.get("totalGeral")

        page_pedidos = _parse_pedidos(raw, data_limite)
        for pedido in page_pedidos:
            key = (pedido.get("codRep"), pedido.get("numPed"))
            if key in seen:
                continue
            seen.add(key)
            pedidos.append(pedido)

        pages += 1
        logger.info(
            "ClicVendas pagina %s: skip=%s raw=%s parsed=%s total=%s",
            pages,
            skip,
            raw_count,
            len(page_pedidos),
            total_geral,
        )

        if raw_count <= 0 or raw_count < page_size:
            break
        skip += page_size
        if total_geral is not None and skip >= int(total_geral):
            break
        if pages >= 100:
            logger.warning("Interrompendo paginacao do ClicVendas apos %d paginas", pages)
            break

    return pedidos, {"pages": pages, "total_geral": total_geral}


def run_sync(dias: int, triggered_by: str, rep_document: str | None = None) -> dict:
    db = SupabaseClient()
    start = time.time()
    date_from = (datetime.utcnow() - timedelta(days=dias)).strftime("%Y-%m-%dT00:00:00.000Z")
    rep_document = re.sub(r"\D", "", str(rep_document or "")) or None

    log_id = db.insert_clic_sync_log(
        {
            "triggered_by": triggered_by,
            "status": "running",
            "rep_document": rep_document,
            "date_from": date_from,
        }
    )

    try:
        client = ClicVendasClient()
        pedidos, fetch_meta = _fetch_pedidos_paginated(
            client,
            date_from,
            datetime.utcnow() - timedelta(days=dias),
            rep_document,
        )
        total_fetched = len(pedidos)
        synced_at = datetime.utcnow().isoformat() + "Z"

        # Garante que os representantes existam antes de inserir pedidos
        _ensure_representatives(pedidos, db)
        secretary_by_number, secretary_by_protocol = _secretary_order_maps(db)

        order_rows = []
        secretary_matches: list[tuple[dict, dict]] = []
        for pedido in pedidos:
            origin = _secretary_origin(
                pedido,
                secretary_by_number,
                secretary_by_protocol,
            )
            if origin:
                secretary_matches.append((origin, pedido))
            order_rows.append(
                {
                    "id": str(uuid.uuid4()),
                    "cod_rep": pedido.get("codRep"),
                    "cod_cli": pedido.get("codCli"),
                    "customer_document": pedido.get("cpfCnpj"),
                    "num_ped": pedido.get("numPed"),
                    "dat_emi": pedido.get("datEmi"),
                    "sit_ped": pedido.get("sitPed"),
                    "order_total_value": pedido.get("vlrTot"),
                    "items_json": pedido.get("itens", []),
                    "has_items": bool(pedido.get("itens")),
                    "source": "clic_vendas",
                    "customer_name": pedido.get("nomeCliente"),
                    "rep_name": pedido.get("nomeRep"),
                    "external_id": pedido.get("externalId"),
                    "observation": pedido.get("observacao"),
                    "origin_agent": "marcela_secretaria" if origin else None,
                    "origin_order_id": origin.get("id") if origin else None,
                    "origin_instance": origin.get("instance_name") if origin else None,
                    "origin_cod_rep": origin.get("cod_rep") if origin else None,
                    "origin_protocol": origin.get("protocol") if origin else None,
                    "erp_synced_at": synced_at,
                    "created_at": synced_at,
                    "updated_at": synced_at,
                }
            )

        total_upserted = db.upsert_rep_order_base(order_rows) if order_rows else 0
        _mark_secretary_orders_synced(db, secretary_matches, synced_at)

        # Persiste tabela de preço por cliente em clic_clientes (mais recente vence)
        _upsert_tabela_preco_clientes(pedidos)
        _upsert_customer_profiles(pedidos)
        _upsert_representative_profiles(pedidos)

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
                    "rep_document": rep_document,
                    "pages": fetch_meta.get("pages"),
                    "total_geral": fetch_meta.get("total_geral"),
                    "secretary_orders_reconciled": len(secretary_matches),
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


def list_pedidos(cod_cli: int | None, dias: int, page: int, page_size: int, cod_rep: int | None = None) -> dict:
    """Lista pedidos sincronizados da tabela rep_order_base."""
    db = _db_direct()

    select_fields = "id, num_ped, cod_cli, cod_rep, customer_name, rep_name, dat_emi, sit_ped, order_total_value, items_json, has_items, source"
    fallback_select_fields = "id, num_ped, cod_cli, cod_rep, dat_emi, sit_ped, order_total_value, items_json, has_items, source"

    def filtered_query(fields: str, *, count: str | None = None):
        q = (
            db.table("rep_order_base")
            .select(fields, count=count)
            .order("dat_emi", desc=True)
        )
        if dias > 0:
            from_date = (datetime.utcnow() - timedelta(days=dias)).strftime("%Y-%m-%d")
            q = q.gte("dat_emi", from_date)
        if cod_cli is not None:
            q = q.eq("cod_cli", cod_cli)
        if cod_rep is not None:
            q = q.eq("cod_rep", cod_rep)
        return q

    def execute_page(fields: str):
        start = max(0, (page - 1) * page_size)
        end = start + page_size - 1
        return filtered_query(fields, count="exact").range(start, end).execute()

    def fetch_metric_rows(max_rows: int = 50000) -> tuple[list[dict], bool]:
        batch_size = 1000
        offset = 0
        all_rows: list[dict] = []
        while offset < max_rows:
            end = min(offset + batch_size - 1, max_rows - 1)
            batch = filtered_query("cod_cli, order_total_value").range(offset, end).execute().data or []
            all_rows.extend(batch)
            if len(batch) < batch_size:
                return all_rows, False
            offset += batch_size
        return all_rows, True

    try:
        result = execute_page(select_fields)
    except Exception as exc:
        if "customer_name" not in str(exc) and "rep_name" not in str(exc):
            raise
        result = execute_page(fallback_select_fields)

    rows = result.data or []
    total = int(getattr(result, "count", None) or 0)

    metric_rows, metrics_truncated = fetch_metric_rows()
    unique_clients = len({row.get("cod_cli") for row in metric_rows if row.get("cod_cli") is not None})
    total_value = sum(float(row.get("order_total_value") or 0) for row in metric_rows)
    if total == 0:
        total = len(metric_rows)

    pedidos = []
    for r in rows:
        pedidos.append({
            "num_ped": r.get("num_ped"),
            "cod_cli": r.get("cod_cli"),
            "cod_rep": r.get("cod_rep"),
            "customer_name": r.get("customer_name"),
            "rep_name": r.get("rep_name"),
            "dat_emi": r.get("dat_emi") or "",
            "sit_ped": r.get("sit_ped") or "",
            "order_total_value": float(r.get("order_total_value") or 0),
            "items_json": r.get("items_json") or [],
            "has_items": bool(r.get("has_items")),
            "source": r.get("source") or "clic_vendas",
        })

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": max(1, -(-total // page_size)),
        "metrics": {
            "unique_clients": unique_clients,
            "total_value": round(total_value, 2),
            "metrics_limit": 50000,
            "metrics_truncated": metrics_truncated,
        },
        "pedidos": pedidos,
    }


def _parse_order_date(value: str | None) -> datetime | None:
    if not value:
        return None
    text = str(value).strip()
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%d/%m/%Y", "%d/%m/%Y %H:%M:%S"):
        try:
            return datetime.strptime(text[:19], fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None


def _period_for_month(month: int, period_count: int) -> int:
    month = min(12, max(1, month))
    return min(period_count, ((month - 1) * period_count) // 12 + 1)


def _period_label(period: int, period_count: int) -> str:
    if period_count == 2:
        return f"{period}o semestre"
    if period_count == 4:
        return f"{period}o trimestre"
    return f"Periodo {period}"


def _month_label(month: int) -> str:
    labels = [
        "janeiro",
        "fevereiro",
        "marco",
        "abril",
        "maio",
        "junho",
        "julho",
        "agosto",
        "setembro",
        "outubro",
        "novembro",
        "dezembro",
    ]
    return labels[min(12, max(1, month)) - 1]


def list_previsao(year: int | None, period_count: int, limit: int, cod_rep: int | None = None) -> dict:
    """Agrupa itens de pedidos por periodo anual para indicar produtos mais vendidos."""
    if period_count not in (2, 3, 4):
        raise ValueError("period_count deve ser 2, 3 ou 4")

    db = _db_direct()
    rows = (
        db.table("rep_order_base")
        .select("num_ped, cod_rep, dat_emi, sit_ped, order_total_value, items_json, origin_agent")
        .order("dat_emi", desc=True)
        .limit(10000)
        .execute()
        .data
        or []
    )

    parsed_rows = []
    available_years = set()
    for row in rows:
        if cod_rep is not None and row.get("cod_rep") != cod_rep:
            continue
        order_date = _parse_order_date(row.get("dat_emi"))
        if not order_date:
            continue
        available_years.add(order_date.year)
        parsed_rows.append((row, order_date))

    if year is None:
        year = max(available_years) if available_years else datetime.now().year

    period_stats = {}
    month_stats = {}
    product_total = defaultdict(
        lambda: {
            "codPro": "",
            "desPro": "",
            "total_qtd": 0.0,
            "total_valor": 0.0,
            "pedidos": set(),
            "periods": defaultdict(lambda: {"qtd": 0.0, "valor": 0.0, "pedidos": set()}),
            "months": defaultdict(lambda: {"qtd": 0.0, "valor": 0.0, "pedidos": set()}),
        }
    )
    secretary_order_ids: set[str] = set()
    secretary_total_value = 0.0

    for period in range(1, period_count + 1):
        period_stats[period] = {
            "period": period,
            "label": _period_label(period, period_count),
            "orders_count": 0,
            "items_count": 0,
            "total_qtd": 0.0,
            "total_valor": 0.0,
            "top_products": [],
        }

    for month in range(1, 13):
        month_stats[month] = {
            "month": month,
            "label": _month_label(month),
            "orders_count": 0,
            "items_count": 0,
            "total_qtd": 0.0,
            "total_valor": 0.0,
            "top_products": [],
        }

    for row, order_date in parsed_rows:
        if order_date.year != year:
            continue

        period = _period_for_month(order_date.month, period_count)
        month = order_date.month
        items = row.get("items_json") or []
        if not isinstance(items, list):
            continue

        order_key = str(row.get("num_ped") or "")
        if row.get("origin_agent") == "marcela_secretaria":
            secretary_order_ids.add(order_key)
            secretary_total_value += float(row.get("order_total_value") or 0)
        period_stats[period]["orders_count"] += 1
        month_stats[month]["orders_count"] += 1

        for item in items:
            if not isinstance(item, dict):
                continue
            code = str(item.get("codPro") or "").strip()
            name = str(item.get("desPro") or code or "Produto sem codigo").strip()
            if not code and not name:
                continue
            key = code or name.lower()
            qtd = float(item.get("qtdPed") or 0)
            valor = float(item.get("vlrTotal") or 0)

            current = product_total[key]
            current["codPro"] = code
            current["desPro"] = name
            current["total_qtd"] += qtd
            current["total_valor"] += valor
            current["pedidos"].add(order_key)
            current["periods"][period]["qtd"] += qtd
            current["periods"][period]["valor"] += valor
            current["periods"][period]["pedidos"].add(order_key)
            current["months"][month]["qtd"] += qtd
            current["months"][month]["valor"] += valor
            current["months"][month]["pedidos"].add(order_key)

            period_stats[period]["items_count"] += 1
            period_stats[period]["total_qtd"] += qtd
            period_stats[period]["total_valor"] += valor
            month_stats[month]["items_count"] += 1
            month_stats[month]["total_qtd"] += qtd
            month_stats[month]["total_valor"] += valor

    def product_payload(data: dict, period: int | None = None, month: int | None = None) -> dict:
        if period is None:
            if month is None:
                qtd = data["total_qtd"]
                valor = data["total_valor"]
                pedidos = len(data["pedidos"])
            else:
                month_data = data["months"][month]
                qtd = month_data["qtd"]
                valor = month_data["valor"]
                pedidos = len(month_data["pedidos"])
        else:
            period_data = data["periods"][period]
            qtd = period_data["qtd"]
            valor = period_data["valor"]
            pedidos = len(period_data["pedidos"])

        previous_qtd = 0.0
        growth_pct = None
        if period and period > 1:
            previous_qtd = data["periods"][period - 1]["qtd"]
            if previous_qtd > 0:
                growth_pct = round(((qtd - previous_qtd) / previous_qtd) * 100, 1)
            elif qtd > 0:
                growth_pct = 100.0
        if month and month > 1:
            previous_qtd = data["months"][month - 1]["qtd"]
            if previous_qtd > 0:
                growth_pct = round(((qtd - previous_qtd) / previous_qtd) * 100, 1)
            elif qtd > 0:
                growth_pct = 100.0

        return {
            "codPro": data["codPro"],
            "desPro": data["desPro"],
            "total_qtd": round(qtd, 2),
            "total_valor": round(valor, 2),
            "pedidos": pedidos,
            "growth_pct": growth_pct,
        }

    products = list(product_total.values())
    for period in range(1, period_count + 1):
        ranked = [p for p in products if p["periods"][period]["qtd"] > 0 or p["periods"][period]["valor"] > 0]
        ranked.sort(key=lambda p: (p["periods"][period]["qtd"], p["periods"][period]["valor"]), reverse=True)
        period_stats[period]["total_qtd"] = round(period_stats[period]["total_qtd"], 2)
        period_stats[period]["total_valor"] = round(period_stats[period]["total_valor"], 2)
        period_stats[period]["top_products"] = [product_payload(p, period) for p in ranked[:limit]]

    for month in range(1, 13):
        ranked = [p for p in products if p["months"][month]["qtd"] > 0 or p["months"][month]["valor"] > 0]
        ranked.sort(key=lambda p: (p["months"][month]["qtd"], p["months"][month]["valor"]), reverse=True)
        month_stats[month]["total_qtd"] = round(month_stats[month]["total_qtd"], 2)
        month_stats[month]["total_valor"] = round(month_stats[month]["total_valor"], 2)
        month_stats[month]["top_products"] = [product_payload(p, month=month) for p in ranked[:limit]]

    current_month = datetime.now().month
    seasonal_month = current_month
    if month_stats[seasonal_month]["items_count"] == 0:
        seasonal_month = max(
            (month for month in range(1, 13) if month_stats[month]["items_count"] > 0),
            default=current_month,
        )
    seasonal_ranked = [
        p for p in products
        if p["months"][seasonal_month]["qtd"] > 0 or p["months"][seasonal_month]["valor"] > 0
    ]
    seasonal_ranked.sort(
        key=lambda p: (
            p["months"][seasonal_month]["qtd"],
            p["months"][seasonal_month]["valor"],
            p["total_qtd"],
        ),
        reverse=True,
    )

    total_ranked = sorted(products, key=lambda p: (p["total_qtd"], p["total_valor"]), reverse=True)
    latest_period = max(
        (p for p in range(1, period_count + 1) if period_stats[p]["items_count"] > 0),
        default=_period_for_month(datetime.now().month, period_count),
    )

    return {
        "year": year,
        "period_count": period_count,
        "available_years": sorted(available_years, reverse=True),
        "latest_period": latest_period,
        "seasonal_reference_month": seasonal_month,
        "seasonal_reference_label": _month_label(seasonal_month),
        "summary": {
            "orders_count": sum(p["orders_count"] for p in period_stats.values()),
            "items_count": sum(p["items_count"] for p in period_stats.values()),
            "total_qtd": round(sum(p["total_qtd"] for p in period_stats.values()), 2),
            "total_valor": round(sum(p["total_valor"] for p in period_stats.values()), 2),
            "products_count": len(products),
            "secretary_orders_count": len(secretary_order_ids),
            "secretary_total_value": round(secretary_total_value, 2),
        },
        "periods": list(period_stats.values()),
        "months": list(month_stats.values()),
        "seasonal_products": [product_payload(p, month=seasonal_month) for p in seasonal_ranked[:limit]],
        "forecast_products": [product_payload(p) for p in total_ranked[:limit]],
    }


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    parser = argparse.ArgumentParser(description="CLI interna do módulo ClicVendas")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("status")

    sync_parser = subparsers.add_parser("sync")
    sync_parser.add_argument("--dias", type=int, default=30)
    sync_parser.add_argument("--triggered-by", default="manual")
    sync_parser.add_argument("--rep-document", default=None)

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
    pedidos_parser.add_argument("--cod-rep", type=int, default=None)

    previsao_parser = subparsers.add_parser("previsao")
    previsao_parser.add_argument("--year", type=int, default=None)
    previsao_parser.add_argument("--period-count", type=int, default=4)
    previsao_parser.add_argument("--limit", type=int, default=10)
    previsao_parser.add_argument("--cod-rep", type=int, default=None)

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
            return success(run_sync(args.dias, args.triggered_by, args.rep_document))
        if args.command == "sync-logs":
            return success(list_sync_logs(args.date, args.limit))
        if args.command == "sync-log":
            return success(get_sync_log(args.log_id))
        if args.command == "pedidos":
            return success(list_pedidos(args.cod_cli, args.dias, args.page, args.page_size, args.cod_rep))
        if args.command == "previsao":
            return success(list_previsao(args.year, args.period_count, args.limit, args.cod_rep))
        return failure("Comando não suportado")
    except Exception as exc:
        logger.exception("Falha no CLI do ClicVendas")
        return failure(str(exc))


if __name__ == "__main__":
    raise SystemExit(main())
