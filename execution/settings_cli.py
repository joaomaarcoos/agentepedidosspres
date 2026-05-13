"""
settings_cli.py
===============
Lê e grava configurações globais na tabela system_settings do Supabase.

Subcomandos:
  get                                       Retorna todas as chaves de disparo
  set  --key <chave>  --value true|false    Atualiza uma chave

Fallback: .tmp/data/settings.json quando Supabase não está disponível.
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

FALLBACK_PATH = Path(__file__).resolve().parent.parent / ".tmp" / "data" / "settings.json"

ALLOWED_KEYS = {
    "disparo_recorrencia_enabled",
    "disparo_ativacao_enabled",
}

DEFAULT_SETTINGS = {
    "disparo_recorrencia_enabled": True,
    "disparo_ativacao_enabled": True,
}


def emit(payload: dict) -> None:
    sys.stdout.write(json.dumps(payload, ensure_ascii=False))
    sys.stdout.write("\n")


def _db():
    url = os.getenv("SUPABASE_URL", "").rstrip("/")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_ANON_KEY", "")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY não configurados")
    from supabase import create_client
    return create_client(url, key)


def _read_fallback() -> dict:
    if FALLBACK_PATH.exists():
        try:
            return json.loads(FALLBACK_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return dict(DEFAULT_SETTINGS)


def _write_fallback(data: dict) -> None:
    FALLBACK_PATH.parent.mkdir(parents=True, exist_ok=True)
    FALLBACK_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def cmd_get() -> dict:
    try:
        sb = _db()
        rows = sb.table("system_settings").select("key, value").in_("key", list(ALLOWED_KEYS)).execute()
        raw = {r["key"]: r["value"] for r in (rows.data or [])}
    except Exception:
        raw = _read_fallback()

    return {
        "disparo_recorrencia": bool(raw.get("disparo_recorrencia_enabled", True)),
        "disparo_ativacao": bool(raw.get("disparo_ativacao_enabled", True)),
    }


def cmd_set(key: str, value: bool) -> dict:
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    try:
        sb = _db()
        sb.table("system_settings").upsert(
            {"key": key, "value": value, "updated_at": now}
        ).execute()
    except Exception:
        data = _read_fallback()
        data[key] = value
        _write_fallback(data)

    return {"key": key, "value": value}


def main() -> int:
    parser = argparse.ArgumentParser(prog="settings_cli")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("get")

    set_p = sub.add_parser("set")
    set_p.add_argument("--key", required=True, choices=list(ALLOWED_KEYS))
    set_p.add_argument("--value", required=True)

    args = parser.parse_args()

    try:
        if args.command == "get":
            result = cmd_get()
        elif args.command == "set":
            value_bool = args.value.lower() in ("true", "1", "yes")
            result = cmd_set(args.key, value_bool)
        else:
            parser.print_help()
            return 1

        emit({"ok": True, "data": result})
        return 0
    except Exception as exc:
        emit({"ok": False, "error": str(exc)})
        return 1


if __name__ == "__main__":
    sys.exit(main())
