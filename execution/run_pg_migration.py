"""
run_pg_migration.py
===================
Aplica um arquivo SQL no Postgres/Supabase usando DATABASE_URL.

Uso:
  python execution/run_pg_migration.py --file execution/ai_conversation_migration.sql
  python execution/run_pg_migration.py --dsn "postgres://..." --file migration.sql
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")


def emit(payload: dict) -> None:
    sys.stdout.write(json.dumps(payload, ensure_ascii=False, default=str))
    sys.stdout.write("\n")


def success(data: dict) -> int:
    emit({"ok": True, "data": data})
    return 0


def failure(message: str) -> int:
    emit({"ok": False, "error": message})
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Aplica migration SQL no Postgres")
    parser.add_argument("--file", required=True, help="Caminho do arquivo SQL")
    parser.add_argument("--dsn", default=os.getenv("DATABASE_URL", ""))
    args = parser.parse_args()

    sql_path = Path(args.file)
    if not sql_path.is_absolute():
        sql_path = Path.cwd() / sql_path

    if not args.dsn:
        return failure("DATABASE_URL ausente")
    if not sql_path.exists():
        return failure(f"Arquivo SQL nao encontrado: {sql_path}")

    try:
        import psycopg
    except ImportError:
        return failure("Pacote psycopg nao instalado. Rode: py -m pip install \"psycopg[binary]\"")

    sql = sql_path.read_text(encoding="utf-8")
    with psycopg.connect(args.dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
        conn.commit()

    return success({"file": str(sql_path), "applied": True})


if __name__ == "__main__":
    raise SystemExit(main())
