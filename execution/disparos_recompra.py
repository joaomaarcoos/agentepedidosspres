"""
disparos_recompra.py
====================
Envia mensagens WhatsApp para candidatos aprovados pela IA (status='ai_approved').
Registra em message_events e atualiza recurrence_targets para 'dispatched'.

Subcomandos:
  run  [--dry-run] [--limit N] [--id UUID]
"""

import argparse
import json
import logging
import os
import re
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


def _db():
    url = os.getenv("SUPABASE_URL", "").rstrip("/")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_ANON_KEY", "")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY não configurados")
    from supabase import create_client
    return create_client(url, key)


def _evolution_config() -> tuple[str, str, str]:
    api_url = os.getenv("EVOLUTION_API_URL", "").rstrip("/")
    api_key = os.getenv("EVOLUTION_API_KEY", "")
    instance = os.getenv("EVOLUTION_INSTANCE", "")
    if not api_url or not api_key or not instance:
        raise RuntimeError(
            "EVOLUTION_API_URL, EVOLUTION_API_KEY e EVOLUTION_INSTANCE não configurados"
        )
    return api_url, api_key, instance


def _validate_phone(phone: str | None) -> str | None:
    if not phone:
        return None
    digits = re.sub(r"\D", "", str(phone))
    if 10 <= len(digits) <= 13:
        return digits
    return None


def _extract_mensagem(ai_reasoning: str | None) -> str:
    if not ai_reasoning:
        return ""
    try:
        data = json.loads(ai_reasoning)
        return str(data.get("mensagem") or "").strip()
    except (json.JSONDecodeError, TypeError):
        return ""


def _build_mensagem_fallback(target: dict) -> str:
    nome = target.get("customer_name") or "cliente"
    top_items = target.get("top_items_json") or []
    produtos = ", ".join(
        it.get("desPro") or it.get("codPro", "")
        for it in top_items[:2]
        if it.get("desPro") or it.get("codPro")
    )
    if produtos:
        return (
            f"Olá! Tudo bem?\n\n"
            f"Vi que você costuma pedir {produtos} por essa época. "
            f"Quer repetir o pedido ou ajustar algo?"
        )
    return "Olá! Tudo bem? Que tal repetirmos seu último pedido?"


def _send_whatsapp(api_url: str, api_key: str, instance: str, phone: str, text: str) -> dict:
    url = f"{api_url}/message/sendText/{instance}"
    payload = {
        "number": f"{phone}@s.whatsapp.net",
        "text": text,
    }
    headers = {"apikey": api_key, "Content-Type": "application/json"}

    for attempt in range(2):
        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=15)
            if resp.status_code == 429:
                raise RuntimeError("Rate limit da Evolution API atingido (429)")
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.Timeout:
            if attempt == 0:
                logger.warning("Timeout na Evolution API, tentando novamente...")
                time.sleep(3)
                continue
            raise
    return {}


def cmd_run(dry_run: bool, limit: int, target_id: str | None) -> dict:
    db = _db()
    now = datetime.now(timezone.utc)

    if not dry_run:
        api_url, api_key, instance = _evolution_config()

    # Buscar candidatos aprovados
    query = (
        db.table("recurrence_targets")
        .select("*")
        .eq("status", "ai_approved")
        .is_("dispatched_at", "null")
    )
    if target_id:
        query = query.eq("id", target_id)
    query = query.order("updated_at", desc=False).limit(limit)
    res = query.execute()
    candidates = res.data or []

    # Filtrar cooldown vencido em Python (IS NULL já cobre a maioria)
    active = []
    for t in candidates:
        cooldown = t.get("cooldown_until")
        if cooldown:
            try:
                from datetime import datetime as dt
                cd = dt.fromisoformat(cooldown.replace("Z", "+00:00"))
                if cd > now:
                    logger.info("Skipping %s (cooldown até %s)", t.get("customer_name"), cooldown)
                    continue
            except (ValueError, TypeError):
                pass
        active.append(t)

    logger.info("Candidatos aprovados para disparo: %d", len(active))

    processed = 0
    dispatched = 0
    skipped = 0
    errors: list[dict] = []

    for target in active:
        tid = target.get("id")
        nome = target.get("customer_name") or tid
        phone_raw = target.get("customer_phone")

        phone = _validate_phone(phone_raw)
        if not phone:
            logger.warning("Telefone inválido para %s (%s) → marcando ai_rejected", nome, phone_raw)
            if not dry_run:
                db.table("recurrence_targets").update({
                    "status": "ai_rejected",
                    "ai_reasoning": json.dumps({
                        **(json.loads(target.get("ai_reasoning") or "{}") if target.get("ai_reasoning") else {}),
                        "skip_reason": f"telefone inválido: {phone_raw}",
                    }, ensure_ascii=False),
                    "updated_at": now.isoformat(),
                }).eq("id", tid).execute()
            skipped += 1
            continue

        mensagem = _extract_mensagem(target.get("ai_reasoning"))
        if not mensagem:
            mensagem = _build_mensagem_fallback(target)

        if dry_run:
            logger.info(
                "[DRY-RUN] Enviaria para %s (%s):\n%s",
                nome, phone, mensagem,
            )
            dispatched += 1
            processed += 1
            continue

        try:
            result = _send_whatsapp(api_url, api_key, instance, phone, mensagem)
            logger.info("✓ Enviado para %s (%s)", nome, phone)

            # Registrar em message_events
            db.table("message_events").insert({
                "entity_type": "target",
                "entity_id": tid,
                "direction": "outbound",
                "to_number": phone,
                "message_type": "text",
                "payload_json": {
                    "canal": "whatsapp",
                    "funil": "recompra",
                    "mensagem": mensagem,
                    "evolution_response": result,
                },
            }).execute()

            # Atualizar status
            db.table("recurrence_targets").update({
                "status": "dispatched",
                "dispatched_at": now.isoformat(),
                "last_contact_at": now.isoformat(),
                "updated_at": now.isoformat(),
            }).eq("id", tid).execute()

            dispatched += 1

        except RuntimeError as exc:
            # Rate limit — parar tudo
            logger.error("PARADA: %s", exc)
            errors.append({"id": tid, "nome": nome, "error": str(exc)})
            break
        except Exception as exc:
            logger.error("Erro ao enviar para %s: %s", nome, exc)
            errors.append({"id": tid, "nome": nome, "error": str(exc)})

        processed += 1

    return {
        "processed": processed,
        "dispatched": dispatched,
        "skipped": skipped,
        "errors": errors,
        "dry_run": dry_run,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Disparos de recompra via WhatsApp")
    subparsers = parser.add_subparsers(dest="command", required=True)

    p_run = subparsers.add_parser("run")
    p_run.add_argument("--dry-run", action="store_true")
    p_run.add_argument("--limit", type=int, default=50)
    p_run.add_argument("--id", dest="target_id", default=None)

    args = parser.parse_args()

    try:
        if args.command == "run":
            return success(cmd_run(
                dry_run=args.dry_run,
                limit=args.limit,
                target_id=args.target_id,
            ))
        return failure("Comando não suportado")
    except Exception as exc:
        logger.exception("Falha no módulo de disparos")
        return failure(str(exc))


if __name__ == "__main__":
    raise SystemExit(main())
