"""
produtos_cli.py
===============
Retorna o catálogo de produtos ativos do Supabase como JSON.

Uso:
    python produtos_cli.py
    python produtos_cli.py --filial "Ribeirão Preto"
    python produtos_cli.py --busca laranja
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip()
SUPABASE_KEY = (os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_ANON_KEY") or "").strip()
PRICE_TABLE_CODES = ("201", "201P", "202", "205", "206")


def _text(value) -> str:
    return str(value or "").strip()


def _price_map(client) -> dict[tuple[str, str], dict[str, float | None]]:
    rows = (
        client.table("tabelas_preco_itens")
        .select("codigo_tabela, cod_produto, variacao, preco")
        .in_("codigo_tabela", list(PRICE_TABLE_CODES))
        .execute()
        .data
        or []
    )
    prices: dict[tuple[str, str], dict[str, float | None]] = {}
    for row in rows:
        key = (_text(row.get("cod_produto")).upper(), _text(row.get("variacao")).upper())
        table_code = _text(row.get("codigo_tabela"))
        if not key[0] or not table_code:
            continue
        prices.setdefault(key, {})[table_code] = row.get("preco")
    return prices


def fetch_produtos(filial: str | None = None, busca: str | None = None) -> list[dict]:
    if not (SUPABASE_URL and SUPABASE_KEY):
        return []

    from supabase import create_client

    client = create_client(SUPABASE_URL, SUPABASE_KEY)
    query = (
        client.table("produtos")
        .select("id, filial, cod_produto, nome, derivacao, preco_base, preco_inst_299, ativo")
        .eq("ativo", True)
        .order("nome")
    )
    if filial:
        query = query.eq("filial", filial)
    result = query.execute()
    rows: list[dict] = result.data or []
    prices = _price_map(client)

    for row in rows:
        key = (_text(row.get("cod_produto")).upper(), _text(row.get("derivacao")).upper())
        row_prices = prices.get(key, {})
        for table_code in PRICE_TABLE_CODES:
            row[f"preco_tabela_{table_code.lower()}"] = row_prices.get(table_code)

    if busca:
        termo = busca.lower()
        rows = [
            r for r in rows
            if termo in r.get("nome", "").lower()
            or termo in r.get("cod_produto", "").lower()
        ]
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Catálogo de produtos SPRES")
    parser.add_argument("--filial", default=None)
    parser.add_argument("--busca", default=None)
    args = parser.parse_args()

    try:
        produtos = fetch_produtos(filial=args.filial, busca=args.busca)
        print(json.dumps({"ok": True, "produtos": produtos, "total": len(produtos)}, ensure_ascii=False))
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc), "produtos": [], "total": 0}, ensure_ascii=False))
        sys.exit(1)


if __name__ == "__main__":
    main()
