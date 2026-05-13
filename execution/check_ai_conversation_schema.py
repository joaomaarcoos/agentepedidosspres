from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")


def emit(payload: dict) -> None:
    sys.stdout.write(json.dumps(payload, ensure_ascii=False, default=str))
    sys.stdout.write("\n")


def main() -> int:
    try:
        import psycopg
    except ImportError:
        emit({"ok": False, "error": "psycopg nao instalado"})
        return 0

    dsn = os.getenv("DATABASE_URL", "")
    if not dsn:
        emit({"ok": False, "error": "DATABASE_URL ausente"})
        return 0

    query = """
        select
          (select count(*) from information_schema.tables
           where table_schema = 'public'
             and table_name in ('ai_conversations', 'ai_conversation_messages')) as tables_count,
          (select count(*) from pg_indexes
           where schemaname = 'public'
             and indexname in ('idx_ai_conversations_phone', 'idx_ai_messages_conversation_created')) as indexes_count
    """
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(query)
            row = cur.fetchone()

    emit({
        "ok": True,
        "data": {
            "tables_count": row[0],
            "indexes_count": row[1],
            "expected_tables": 2,
            "expected_indexes": 2,
        },
    })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
