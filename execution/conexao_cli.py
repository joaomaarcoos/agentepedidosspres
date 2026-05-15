"""
conexao_cli.py
==============
Gerencia instâncias da Evolution API.
Saída em JSON no stdout; logs no stderr.

Subcomandos:
  status                                          — saúde da API
  list                                            — lista instâncias
  create --name N [--webhook-url U] [--msg-call M] — cria instância
  qrcode        --name N                          — lê QR code
  delete        --name N                          — apaga instância
  disconnect    --name N                          — logout/desconecta
  restart       --name N                          — reinicia/reconecta
  agent-status  --name N                          — estado do agente Marcela
  agent-toggle  --name N --enabled true|false     — liga/desliga agente
"""

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone

import requests
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


def _first_env(*names: str) -> str:
    for name in names:
        value = os.getenv(name, "").strip()
        if value:
            return value
    return ""


def _mask_url(value: str) -> str | None:
    if not value:
        return None
    if "://" not in value:
        return value
    scheme, rest = value.split("://", 1)
    host = rest.split("/", 1)[0]
    return f"{scheme}://{host}"


def _cfg() -> tuple[str, str, str, dict[str, bool]]:
    """Returns (base_url, api_key, instance_name, env_status)."""
    base_url = _first_env("EVOLUTION_API_URL", "EVOLUTION_BASE_URL", "EVOLUTION_URL")
    api_key = _first_env("EVOLUTION_API_KEY", "EVOLUTION_KEY", "EVOLUTION_APIKEY")
    instance_name = _first_env("EVOLUTION_INSTANCE_NAME", "EVOLUTION_INSTANCE", "EVOLUTION_INSTANCE_ID")
    env_status = {
        "EVOLUTION_API_URL": bool(base_url),
        "EVOLUTION_API_KEY": bool(api_key),
        "EVOLUTION_INSTANCE_NAME": bool(instance_name),
    }
    return base_url.rstrip("/"), api_key, instance_name, env_status


def _headers(api_key: str) -> dict:
    return {"apikey": api_key, "Accept": "application/json", "Content-Type": "application/json"}


def _extract_instance_list(payload: object) -> list[dict]:
    """Normalise fetchInstances response into a flat list."""
    items: list[dict] = []
    if isinstance(payload, list):
        raw_list = payload
    elif isinstance(payload, dict):
        raw_list = payload.get("instances") or [payload]
    else:
        return items

    for item in raw_list:
        if not isinstance(item, dict):
            continue
        inst = item.get("instance") or item
        if not isinstance(inst, dict):
            continue
        name = inst.get("instanceName") or inst.get("name") or ""
        if not name:
            continue
        state = (
            item.get("state")
            or item.get("connectionStatus")
            or inst.get("state")
            or inst.get("status")
            or inst.get("connectionStatus")
            or "unknown"
        )
        items.append({
            "instanceName": name,
            "instanceId": inst.get("instanceId") or inst.get("id") or "",
            "status": state,
            "profilePictureUrl": inst.get("profilePictureUrl") or None,
            "phoneNumber": inst.get("owner") or inst.get("profileName") or None,
        })
    return items


# ---------------------------------------------------------------------------
# Subcommand handlers
# ---------------------------------------------------------------------------

def cmd_status() -> int:
    checked_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    base_url, api_key, instance_name, env_status = _cfg()

    if not base_url or not api_key:
        return success({
            "service": "Evolution API",
            "checked_at": checked_at,
            "configured": False,
            "api_online": False,
            "instance_found": False,
            "instance_name": instance_name or None,
            "connection_state": None,
            "latency_ms": 0,
            "error_message": "Variaveis da Evolution nao configuradas",
            "api_url": _mask_url(base_url),
            "env": env_status,
        })

    headers = _headers(api_key)
    start = time.perf_counter()

    for endpoint in [
        f"{base_url}/instance/connectionState/{instance_name}",
        f"{base_url}/instance/fetchInstances",
    ]:
        try:
            r = requests.get(endpoint, headers=headers, timeout=30)
            r.raise_for_status()
            payload = r.json()
            latency_ms = int((time.perf_counter() - start) * 1000)

            # Try to extract state
            connection_state = None
            instance_found = False
            if isinstance(payload, dict):
                inner = payload.get("instance") or payload
                connection_state = (
                    inner.get("state")
                    or inner.get("connectionStatus")
                    or payload.get("state")
                )
                instance_found = bool(inner.get("instanceName") or connection_state)
            elif isinstance(payload, list) and instance_name:
                for item in payload:
                    inst = (item.get("instance") or item) if isinstance(item, dict) else {}
                    if str(inst.get("instanceName") or "") == instance_name:
                        connection_state = item.get("state") or inst.get("state") or inst.get("connectionStatus")
                        instance_found = True
                        break

            return success({
                "service": "Evolution API",
                "checked_at": checked_at,
                "configured": True,
                "api_online": True,
                "instance_found": instance_found,
                "instance_name": instance_name or None,
                "connection_state": str(connection_state) if connection_state else None,
                "latency_ms": latency_ms,
                "error_message": None if instance_found else "Instancia nao localizada",
                "api_url": _mask_url(base_url),
                "env": env_status,
            })
        except Exception as exc:
            logger.debug("endpoint %s falhou: %s", endpoint, exc)

    latency_ms = int((time.perf_counter() - start) * 1000)
    return success({
        "service": "Evolution API",
        "checked_at": checked_at,
        "configured": True,
        "api_online": False,
        "instance_found": False,
        "instance_name": instance_name or None,
        "connection_state": None,
        "latency_ms": latency_ms,
        "error_message": "Falha ao conectar com a Evolution API",
        "api_url": _mask_url(base_url),
        "env": env_status,
    })


def cmd_list() -> int:
    base_url, api_key, _, env_status = _cfg()
    if not base_url or not api_key:
        return failure("EVOLUTION_API_URL / EVOLUTION_API_KEY não configurados")

    checked_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    try:
        r = requests.get(f"{base_url}/instance/fetchInstances", headers=_headers(api_key), timeout=30)
        r.raise_for_status()
        instances = _extract_instance_list(r.json())
        return success({
            "instances": instances,
            "total": len(instances),
            "api_online": True,
            "api_url": _mask_url(base_url),
            "checked_at": checked_at,
            "env": env_status,
        })
    except requests.HTTPError as exc:
        return failure(f"Evolution API erro {exc.response.status_code}: {exc.response.text[:200]}")
    except Exception as exc:
        return failure(str(exc))


def _default_webhook_url() -> str:
    app_url = os.getenv("APP_URL", "").rstrip("/")
    if app_url:
        return f"{app_url}/api/evolution/webhook"
    return ""


def cmd_create(name: str, webhook_url: str, msg_call: str) -> int:
    base_url, api_key, _, _ = _cfg()
    if not base_url or not api_key:
        return failure("EVOLUTION_API_URL / EVOLUTION_API_KEY não configurados")

    if not webhook_url:
        webhook_url = _default_webhook_url()

    # 1. Criar instância com webhook aninhado (estrutura correta do Evolution API v2)
    body: dict = {
        "instanceName": name,
        "integration": "WHATSAPP-BAILEYS",
        "qrcode": False,
        "rejectCall": True,
        "msgCall": msg_call or "No momento nao consigo atender. Envie uma mensagem!",
        "groupsIgnore": False,
        "alwaysOnline": False,
        "readMessages": False,
        "readStatus": False,
    }

    if webhook_url:
        body["webhook"] = {
            "url": webhook_url,
            "byEvents": False,
            "base64": True,
            "events": ["MESSAGES_UPSERT"],
        }

    try:
        r = requests.post(f"{base_url}/instance/create", headers=_headers(api_key), json=body, timeout=30)
        r.raise_for_status()
        payload = r.json()
        inst = payload.get("instance") or {}
        instance_name = inst.get("instanceName") or name
    except requests.HTTPError as exc:
        return failure(f"Erro ao criar instancia ({exc.response.status_code}): {exc.response.text[:300]}")
    except Exception as exc:
        return failure(str(exc))

    # 2. Reforçar webhook via /webhook/set (garantia extra)
    webhook_warning = None
    if webhook_url:
        webhook_body = {
            "enabled": True,
            "url": webhook_url,
            "webhookByEvents": False,
            "webhookBase64": True,
            "events": ["MESSAGES_UPSERT"],
        }
        try:
            rw = requests.post(
                f"{base_url}/webhook/set/{instance_name}",
                headers=_headers(api_key),
                json=webhook_body,
                timeout=30,
            )
            rw.raise_for_status()
        except Exception as exc:
            webhook_warning = f"Instância criada, mas webhook/set falhou: {exc}"
            logger.warning(webhook_warning)

    return success({
        "instanceName": instance_name,
        "instanceId": inst.get("instanceId") or "",
        "status": inst.get("status") or "created",
        "webhookConfigured": webhook_url != "" and webhook_warning is None,
        "webhookUrl": webhook_url or None,
        "warning": webhook_warning,
        "qrcode": None,
    })


def cmd_qrcode(name: str) -> int:
    base_url, api_key, _, _ = _cfg()
    if not base_url or not api_key:
        return failure("EVOLUTION_API_URL / EVOLUTION_API_KEY não configurados")

    try:
        r = requests.get(f"{base_url}/instance/connect/{name}", headers=_headers(api_key), timeout=30)
        r.raise_for_status()
        payload = r.json()
        code = payload.get("code") or payload.get("qrcode", {}).get("code") or ""
        base64 = payload.get("base64") or payload.get("qrcode", {}).get("base64") or ""
        if not base64:
            return failure("QR code nao disponivel — instancia pode ja estar conectada")
        return success({
            "instanceName": name,
            "code": code,
            "base64": base64,
        })
    except requests.HTTPError as exc:
        return failure(f"Erro ao buscar QR code ({exc.response.status_code}): {exc.response.text[:200]}")
    except Exception as exc:
        return failure(str(exc))


def cmd_delete(name: str) -> int:
    base_url, api_key, _, _ = _cfg()
    if not base_url or not api_key:
        return failure("EVOLUTION_API_URL / EVOLUTION_API_KEY não configurados")

    try:
        r = requests.delete(f"{base_url}/instance/delete/{name}", headers=_headers(api_key), timeout=30)
        r.raise_for_status()
        return success({"instanceName": name, "success": True, "message": "Instancia apagada"})
    except requests.HTTPError as exc:
        return failure(f"Erro ao apagar instancia ({exc.response.status_code}): {exc.response.text[:200]}")
    except Exception as exc:
        return failure(str(exc))


def cmd_disconnect(name: str) -> int:
    base_url, api_key, _, _ = _cfg()
    if not base_url or not api_key:
        return failure("EVOLUTION_API_URL / EVOLUTION_API_KEY não configurados")

    try:
        r = requests.delete(f"{base_url}/instance/logout/{name}", headers=_headers(api_key), timeout=30)
        r.raise_for_status()
        return success({"instanceName": name, "success": True, "message": "Instancia desconectada"})
    except requests.HTTPError as exc:
        return failure(f"Erro ao desconectar ({exc.response.status_code}): {exc.response.text[:200]}")
    except Exception as exc:
        return failure(str(exc))


def cmd_restart(name: str) -> int:
    base_url, api_key, _, _ = _cfg()
    if not base_url or not api_key:
        return failure("EVOLUTION_API_URL / EVOLUTION_API_KEY não configurados")

    try:
        r = requests.put(f"{base_url}/instance/restart/{name}", headers=_headers(api_key), timeout=30)
        r.raise_for_status()
        return success({"instanceName": name, "success": True, "message": "Instancia reiniciada"})
    except requests.HTTPError as exc:
        return failure(f"Erro ao reiniciar ({exc.response.status_code}): {exc.response.text[:200]}")
    except Exception as exc:
        return failure(str(exc))


# ---------------------------------------------------------------------------
# Agent toggle — persiste em system_settings com key agent_instance__{name}
# ---------------------------------------------------------------------------

_AGENT_FALLBACK = os.path.join(os.path.dirname(__file__), "..", ".tmp", "data", "agent_settings.json")


def _agent_key(name: str) -> str:
    return f"agent_instance__{name}"


def _agent_db():
    url = os.getenv("SUPABASE_URL", "").rstrip("/")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_ANON_KEY", "")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY não configurados")
    from supabase import create_client
    return create_client(url, key)


def _agent_read_fallback(name: str) -> bool:
    path = _AGENT_FALLBACK
    try:
        if os.path.exists(path):
            data = json.loads(open(path, encoding="utf-8").read())
            return bool(data.get(_agent_key(name), True))
    except Exception:
        pass
    return True


def _agent_write_fallback(name: str, enabled: bool) -> None:
    import pathlib
    path = _AGENT_FALLBACK
    pathlib.Path(path).parent.mkdir(parents=True, exist_ok=True)
    try:
        data = json.loads(open(path, encoding="utf-8").read()) if os.path.exists(path) else {}
    except Exception:
        data = {}
    data[_agent_key(name)] = enabled
    open(path, "w", encoding="utf-8").write(json.dumps(data, indent=2))


def cmd_agent_status(name: str) -> int:
    try:
        db = _agent_db()
        key = _agent_key(name)
        res = db.table("system_settings").select("value").eq("key", key).limit(1).execute()
        rows = res.data or []
        enabled = bool(rows[0]["value"]) if rows else True
    except Exception:
        enabled = _agent_read_fallback(name)

    return success({"instanceName": name, "agent_enabled": enabled})


def cmd_agent_toggle(name: str, enabled: bool) -> int:
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    key = _agent_key(name)
    try:
        db = _agent_db()
        db.table("system_settings").upsert(
            {"key": key, "value": enabled, "updated_at": now}
        ).execute()
    except Exception:
        _agent_write_fallback(name, enabled)

    return success({"instanceName": name, "agent_enabled": enabled})


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="CLI de gerenciamento da Evolution API")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("status")
    sub.add_parser("list")

    p_create = sub.add_parser("create")
    p_create.add_argument("--name", required=True)
    p_create.add_argument("--webhook-url", dest="webhook_url", default="")
    p_create.add_argument("--msg-call", dest="msg_call", default="")

    p_qr = sub.add_parser("qrcode")
    p_qr.add_argument("--name", required=True)

    p_del = sub.add_parser("delete")
    p_del.add_argument("--name", required=True)

    p_disc = sub.add_parser("disconnect")
    p_disc.add_argument("--name", required=True)

    p_restart = sub.add_parser("restart")
    p_restart.add_argument("--name", required=True)

    p_agt_status = sub.add_parser("agent-status")
    p_agt_status.add_argument("--name", required=True)

    p_agt_toggle = sub.add_parser("agent-toggle")
    p_agt_toggle.add_argument("--name", required=True)
    p_agt_toggle.add_argument("--enabled", required=True)

    args = parser.parse_args()

    try:
        if args.command == "status":
            return cmd_status()
        if args.command == "list":
            return cmd_list()
        if args.command == "create":
            return cmd_create(args.name, args.webhook_url, args.msg_call)
        if args.command == "qrcode":
            return cmd_qrcode(args.name)
        if args.command == "delete":
            return cmd_delete(args.name)
        if args.command == "disconnect":
            return cmd_disconnect(args.name)
        if args.command == "restart":
            return cmd_restart(args.name)
        if args.command == "agent-status":
            return cmd_agent_status(args.name)
        if args.command == "agent-toggle":
            enabled = args.enabled.lower() in ("true", "1", "yes")
            return cmd_agent_toggle(args.name, enabled)
        return failure("Comando nao suportado")
    except Exception as exc:
        logger.exception("Falha no modulo conexao")
        return failure(str(exc))


if __name__ == "__main__":
    raise SystemExit(main())
