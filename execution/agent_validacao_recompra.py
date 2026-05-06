"""
agent_validacao_recompra.py
===========================
Valida candidatos de recompra usando Claude (Haiku).
Lê recurrence_targets com status='candidate' e decide sim/não.

Subcomandos:
  run  [--limit N] [--id UUID]
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timezone

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


def _build_prompt(target: dict) -> str:
    nome = target.get("customer_name") or "Cliente"
    tier = target.get("recurrence_tier") or "media"
    intervalo = target.get("recurrence_interval_days")
    proxima = target.get("predicted_next_order_date")
    days_until = target.get("days_until_predicted")
    pedidos_30d = target.get("orders_count_30d") or 0
    last3 = target.get("last_3_orders_json") or []
    top_items = target.get("top_items_json") or []

    tier_label = {"media": "média (2 pedidos/mês)", "alta": "alta (3 pedidos/mês)",
                  "semanal_forte": "semanal forte (4+ pedidos/mês)"}.get(tier, tier)

    # Formatar últimos pedidos
    pedidos_txt = ""
    for i, p in enumerate(last3, 1):
        itens = p.get("itens") or []
        itens_txt = ", ".join(
            f"{it.get('desPro') or it.get('codPro')} x{it.get('qtdPed', 0):.0f}"
            for it in itens
        ) or "sem itens"
        pedidos_txt += (
            f"\n  Pedido {i}: {p.get('data', '?')} | "
            f"R$ {p.get('valor_total', 0):.2f} | {itens_txt}"
        )

    top_txt = ", ".join(
        f"{it.get('desPro') or it.get('codPro')} ({it.get('aparicoes', 0)}x)"
        for it in top_items[:3]
    ) or "não identificados"

    atraso = abs(days_until) if days_until is not None and days_until < 0 else 0
    janela_txt = (
        f"ATRASADO há {atraso} dias" if atraso > 0
        else f"na janela (próxima: {proxima})"
    )

    return f"""Cliente: {nome}
Recorrência: {tier_label}
Intervalo médio entre pedidos: {intervalo} dias
Situação: {janela_txt}
Pedidos últimos 30 dias: {pedidos_30d}
Produtos mais comprados: {top_txt}

Últimos 3 pedidos:{pedidos_txt}

Avalie se este cliente deve receber um contato de recompra agora.
Responda APENAS com JSON válido, sem texto adicional, no formato:
{{
  "decisao": "sim" ou "nao",
  "nivel_confianca": "alto", "medio" ou "baixo",
  "motivo": "explicação breve",
  "pedido_sugerido": [{{"codPro": "...", "desPro": "...", "qtdPed": 0}}],
  "valor_medio": 0.0,
  "mensagem": "mensagem personalizada para o cliente (apenas se decisao=sim)"
}}"""


def _call_ai(prompt: str) -> dict:
    import anthropic

    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1024,
        temperature=0,
        system=(
            "Você é um analista de padrões de compra B2B especializado em recompra. "
            "Sua função é avaliar se um cliente tem padrão claro de recompra e se o momento "
            "é adequado para contato. Responda APENAS em JSON válido, sem texto extra."
        ),
        messages=[{"role": "user", "content": prompt}],
    )
    raw = response.content[0].text.strip()

    # Extrair JSON mesmo se houver markdown
    if "```" in raw:
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw.strip())


def cmd_run(limit: int, target_id: str | None) -> dict:
    db = _db()
    now = datetime.now(timezone.utc)

    # Buscar candidatos pendentes
    query = db.table("recurrence_targets").select("*").eq("status", "candidate")
    if target_id:
        query = query.eq("id", target_id)
    query = query.order("updated_at", desc=False).limit(limit)
    res = query.execute()
    candidates = res.data or []

    logger.info("Candidatos para validar: %d", len(candidates))

    processed = 0
    approved = 0
    rejected = 0
    errors: list[dict] = []

    for target in candidates:
        tid = target.get("id")
        nome = target.get("customer_name") or tid
        try:
            prompt = _build_prompt(target)
            logger.info("Validando: %s", nome)
            decision = _call_ai(prompt)

            decisao = decision.get("decisao", "nao").lower()
            new_status = "ai_approved" if decisao == "sim" else "ai_rejected"

            db.table("recurrence_targets").update({
                "ai_validated": True,
                "ai_decision": decisao,
                "ai_reasoning": json.dumps(decision, ensure_ascii=False),
                "status": new_status,
                "updated_at": now.isoformat(),
            }).eq("id", tid).execute()

            if new_status == "ai_approved":
                approved += 1
                logger.info("✓ APROVADO: %s | confiança=%s", nome, decision.get("nivel_confianca"))
            else:
                rejected += 1
                logger.info("✗ REJEITADO: %s | motivo=%s", nome, decision.get("motivo", "")[:80])

            processed += 1

        except Exception as exc:
            logger.error("Erro ao validar %s: %s", nome, exc)
            errors.append({"id": tid, "nome": nome, "error": str(exc)})

    return {
        "processed": processed,
        "approved": approved,
        "rejected": rejected,
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Agente de validação de recompra")
    subparsers = parser.add_subparsers(dest="command", required=True)

    p_run = subparsers.add_parser("run")
    p_run.add_argument("--limit", type=int, default=20, help="Máx de candidatos a processar")
    p_run.add_argument("--id", dest="target_id", default=None, help="Processar ID específico")

    args = parser.parse_args()

    try:
        if args.command == "run":
            return success(cmd_run(limit=args.limit, target_id=args.target_id))
        return failure("Comando não suportado")
    except Exception as exc:
        logger.exception("Falha no agente de validação")
        return failure(str(exc))


if __name__ == "__main__":
    raise SystemExit(main())
