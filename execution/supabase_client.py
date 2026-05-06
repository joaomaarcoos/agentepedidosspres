"""
supabase_client.py
==================
Persistencia enxuta para o fluxo atual de ClicVendas.

Mantem apenas:
- pedidos sincronizados em `rep_order_base`
- logs de sincronizacao em `clic_sync_logs`
- clientes sincronizados em `clic_customers`
- resumo de clientes em `clic_clientes`

Quando `SUPABASE_URL` nao esta configurado, faz fallback para JSON em
`.tmp/data/`, o que permite rodar o projeto com `npm run dev` sem um
servico Python separado.
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

logger = logging.getLogger(__name__)

LOCAL_DATA_DIR = Path(__file__).resolve().parent.parent / ".tmp" / "data"
ORDERS_TABLE = "rep_order_base"
SYNC_LOGS_TABLE = "clic_sync_logs"
CUSTOMERS_TABLE = "clic_customers"
CUSTOMER_SUMMARY_TABLE = "clic_clientes"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class SupabaseClient:
    """Cliente minimo com fallback local para o modulo ClicVendas."""

    def __init__(self) -> None:
        self.supabase_url = os.getenv("SUPABASE_URL", "").strip()
        self.supabase_key = os.getenv(
            "SUPABASE_SERVICE_ROLE_KEY",
            os.getenv("SUPABASE_ANON_KEY", ""),
        ).strip()
        self.use_local = not (self.supabase_url and self.supabase_key)
        self.client = None

        if self.use_local:
            LOCAL_DATA_DIR.mkdir(parents=True, exist_ok=True)
            logger.warning(
                "SUPABASE_URL ou chave ausente; usando persistencia local em %s",
                LOCAL_DATA_DIR,
            )
            return

        try:
            from supabase import create_client

            self.client = create_client(self.supabase_url, self.supabase_key)
        except Exception as exc:
            logger.warning(
                "Falha ao inicializar Supabase; usando persistencia local. Erro: %s",
                exc,
            )
            self.use_local = True
            LOCAL_DATA_DIR.mkdir(parents=True, exist_ok=True)

    def upsert_rep_order_base(self, rows: list[dict]) -> int:
        """Insere ou atualiza pedidos sincronizados do ClicVendas."""
        if not rows:
            return 0

        if self.use_local:
            return self._local_upsert_composite(
                ORDERS_TABLE,
                rows,
                keys=["cod_rep", "num_ped"],
            )

        try:
            result = (
                self.client.table(ORDERS_TABLE)
                .upsert(rows, on_conflict="cod_rep,num_ped")
                .execute()
            )
            return len(result.data) if result.data else len(rows)
        except Exception as exc:
            logger.error("Erro no upsert de pedidos ClicVendas: %s", exc)
            return 0

    def get_orders_by_source(self, source: str, limit: int = 5000) -> list[dict]:
        """Lista pedidos por origem, mais recentes primeiro."""
        if self.use_local:
            rows = self._local_read(ORDERS_TABLE)
            rows = [row for row in rows if str(row.get("source", "")) == source]
            rows.sort(
                key=lambda row: (
                    str(row.get("dat_emi") or ""),
                    str(row.get("updated_at") or ""),
                ),
                reverse=True,
            )
            return rows[:limit]

        try:
            result = (
                self.client.table(ORDERS_TABLE)
                .select("*")
                .eq("source", source)
                .order("dat_emi", desc=True)
                .limit(max(1, min(limit, 20000)))
                .execute()
            )
            return result.data or []
        except Exception as exc:
            logger.error("Erro ao buscar pedidos por source=%s: %s", source, exc)
            return []

    def upsert_clic_customers(self, rows: list[dict]) -> int:
        """Insere ou atualiza clientes sincronizados do ClicVendas em cache local."""
        if not rows:
            return 0

        return self._local_upsert_key(CUSTOMERS_TABLE, rows, key="external_id")

    def get_clic_customers(self, query: str | None = None, limit: int = 5000) -> list[dict]:
        """Lista clientes sincronizados do ClicVendas a partir do cache local."""
        return self._get_local_customers(query, limit)

    def get_clic_customer(self, cod_cli: int) -> dict | None:
        """Busca um cliente sincronizado por codigo interno no cache local."""
        rows = self._local_read(CUSTOMERS_TABLE)
        for row in rows:
            if str(row.get("cod_cli") or "") == str(cod_cli):
                return row
        return None

    def get_clic_client_summaries(self, limit: int = 5000) -> list[dict]:
        """Lista o resumo persistido de clientes ja consolidado no banco."""
        if self.use_local:
            rows = self._local_read(CUSTOMER_SUMMARY_TABLE)
            rows.sort(key=lambda row: str(row.get("ultimo_pedido_em") or ""), reverse=True)
            return rows[:limit]

        try:
            result = (
                self.client.table(CUSTOMER_SUMMARY_TABLE)
                .select("*")
                .order("ultimo_pedido_em", desc=True)
                .limit(max(1, min(limit, 20000)))
                .execute()
            )
            return result.data or []
        except Exception as exc:
            logger.error("Erro ao buscar resumo de clientes ClicVendas: %s", exc)
            return self._local_read(CUSTOMER_SUMMARY_TABLE)[:limit]

    def insert_clic_sync_log(self, row: dict) -> str:
        """Cria um log de sincronizacao e retorna seu id."""
        payload = {
            "id": str(uuid.uuid4()),
            "triggered_at": row.get("triggered_at") or _utc_now(),
            "triggered_by": row.get("triggered_by", "manual"),
            "status": row.get("status", "running"),
            "rep_document": row.get("rep_document"),
            "date_from": row.get("date_from"),
            "total_fetched": row.get("total_fetched", 0),
            "total_upserted": row.get("total_upserted", 0),
            "total_errors": row.get("total_errors", 0),
            "duration_ms": row.get("duration_ms"),
            "error_message": row.get("error_message"),
            "result_summary_json": row.get("result_summary_json"),
            "created_at": row.get("created_at") or _utc_now(),
            "updated_at": row.get("updated_at") or _utc_now(),
        }

        if self.use_local:
            self._local_append(SYNC_LOGS_TABLE, payload)
            return payload["id"]

        try:
            self.client.table(SYNC_LOGS_TABLE).insert(payload).execute()
            return payload["id"]
        except Exception as exc:
            logger.error("Erro ao inserir clic_sync_log: %s", exc)
            if self.use_local:
                self._local_append(SYNC_LOGS_TABLE, payload)
            return payload["id"]

    def update_clic_sync_log(self, log_id: str, updates: dict) -> bool:
        """Atualiza um log de sincronizacao existente."""
        payload = {**updates, "updated_at": _utc_now()}

        if self.use_local:
            return self._local_update(SYNC_LOGS_TABLE, "id", log_id, payload)

        try:
            self.client.table(SYNC_LOGS_TABLE).update(payload).eq("id", log_id).execute()
            return True
        except Exception as exc:
            logger.error("Erro ao atualizar clic_sync_log %s: %s", log_id, exc)
            return False

    def get_clic_sync_logs(self, date_str: str | None = None, limit: int = 50) -> list[dict]:
        """Lista logs de sincronizacao, opcionalmente filtrando por data."""
        safe_limit = max(1, min(limit, 200))

        if self.use_local:
            rows = self._local_read(SYNC_LOGS_TABLE)
            if date_str:
                rows = [
                    row
                    for row in rows
                    if str(row.get("created_at") or row.get("triggered_at") or "").startswith(date_str)
                ]
            rows.sort(
                key=lambda row: str(row.get("created_at") or row.get("triggered_at") or ""),
                reverse=True,
            )
            return rows[:safe_limit]

        try:
            query = (
                self.client.table(SYNC_LOGS_TABLE)
                .select("*")
                .order("created_at", desc=True)
                .limit(safe_limit)
            )
            if date_str:
                day_start = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                day_end = day_start + timedelta(days=1)
                query = query.gte("created_at", day_start.isoformat()).lt(
                    "created_at",
                    day_end.isoformat(),
                )
            result = query.execute()
            return result.data or []
        except Exception as exc:
            logger.error("Erro ao buscar clic_sync_logs: %s", exc)
            return []

    def _local_file(self, table: str) -> Path:
        LOCAL_DATA_DIR.mkdir(parents=True, exist_ok=True)
        return LOCAL_DATA_DIR / f"{table}.json"

    def _get_local_customers(self, query: str | None, limit: int) -> list[dict]:
        normalized_query = (query or "").strip().lower()
        rows = self._local_read(CUSTOMERS_TABLE)
        if normalized_query:
            rows = [
                row
                for row in rows
                if normalized_query in " ".join(
                    [
                        str(row.get("cod_cli") or ""),
                        str(row.get("documento") or ""),
                        str(row.get("nome") or ""),
                        str(row.get("razao_social") or ""),
                        str(row.get("fantasia") or ""),
                        str(row.get("email") or ""),
                        str(row.get("cidade") or ""),
                        str(row.get("uf") or ""),
                    ]
                ).lower()
            ]
        rows.sort(
            key=lambda row: (
                str(row.get("nome") or row.get("razao_social") or row.get("fantasia") or ""),
                str(row.get("cod_cli") or ""),
            )
        )
        return rows[:limit]

    def _local_read(self, table: str) -> list[dict]:
        path = self._local_file(table)
        if not path.exists():
            return []

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            logger.warning("Arquivo local invalido em %s; resetando tabela %s", path, table)
            return []

        return data if isinstance(data, list) else []

    def _local_write(self, table: str, rows: list[dict]) -> None:
        path = self._local_file(table)
        path.write_text(
            json.dumps(rows, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _local_append(self, table: str, row: dict) -> None:
        rows = self._local_read(table)
        rows.append(row)
        self._local_write(table, rows)

    def _local_update(self, table: str, key: str, value: str, updates: dict) -> bool:
        rows = self._local_read(table)
        updated = False
        for index, row in enumerate(rows):
            if str(row.get(key)) != str(value):
                continue
            rows[index] = {**row, **updates}
            updated = True
            break

        if updated:
            self._local_write(table, rows)
        return updated

    def _local_upsert_composite(self, table: str, records: list[dict], keys: list[str]) -> int:
        rows = self._local_read(table)
        index_by_key = {
            tuple(str(row.get(key) or "") for key in keys): position
            for position, row in enumerate(rows)
        }

        for record in records:
            composite_key = tuple(str(record.get(key) or "") for key in keys)
            current_index = index_by_key.get(composite_key)
            if current_index is None:
                rows.append(record)
                index_by_key[composite_key] = len(rows) - 1
            else:
                rows[current_index] = {**rows[current_index], **record}

        self._local_write(table, rows)
        return len(records)

    def _local_upsert_key(self, table: str, records: list[dict], key: str) -> int:
        rows = self._local_read(table)
        index_by_key = {
            str(row.get(key) or ""): position
            for position, row in enumerate(rows)
        }

        for record in records:
            record_key = str(record.get(key) or "")
            if not record_key:
                rows.append(record)
                continue

            current_index = index_by_key.get(record_key)
            if current_index is None:
                rows.append(record)
                index_by_key[record_key] = len(rows) - 1
            else:
                rows[current_index] = {**rows[current_index], **record}

        self._local_write(table, rows)
        return len(records)
