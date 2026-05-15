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
