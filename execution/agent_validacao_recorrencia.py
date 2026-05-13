"""
agent_validacao_recorrencia.py (v2)
===================================
Valida candidatos de recorrência usando OpenAI.
Lê recurrence_targets com status='candidate' e target_type='recorrencia'
e decide sim/não/needs_review.

Subcomandos:
  run  [--limit N] [--id UUID]

Modelo padrão: gpt-4o-mini (configurável via OPENAI_MODEL no .env)
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

SYSTEM_PROMPT = (
    "Você é um analista de padrões de compra B2B especializado em recorrência. "
    "Sua função é avaliar se um cliente tem padrão claro de recorrência e se o momento "
    "é adequado para contato. Responda APENAS com um objeto JSON válido, sem texto extra."
)


# ─── I/O ─────────────────────────────────────────────────────────────────────

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


# ─── Construção do prompt ─────────────────────────────────────────────────────

def _build_prompt(target: dict) -> str:
    nome = target.get("customer_name") or "Cliente"
    tier = target.get("recurrence_tier") or "media"
    intervalo = target.get("recurrence_interval_days")
    proxima = target.get("predicted_next_order_date")
    days_until = target.get("days_until_predicted")
    pedidos_30d = target.get("orders_count_30d") or 0
    last3 = target.get("last_3_orders_json") or []
    top_items = target.get("top_items_json") or []

    tier_label = {
        "media": "média (2 pedidos/mês)",
        "alta": "alta (3 pedidos/mês)",
        "semanal_forte": "semanal forte (4+ pedidos/mês)",
    }.get(tier, tier)

    pedidos_txt = ""
    for i, p in enumerate(last3, 1):
        itens = p.get("itens") or []
        itens_txt = ", ".join(
            f"{it.get('desPro') or it.get('codPro')} [{it.get('codPro')}] x{it.get('qtdPed', 0):.0f}"
            for it in itens
        ) or "sem itens"
        pedidos_txt += (
            f"\n  Pedido {i}: {p.get('data', '?')} | "
            f"R$ {p.get('valor_total', 0):.2f} | {itens_txt}"
        )

    top_txt = ", ".join(
        f"{it.get('desPro') or it.get('codPro')} [{it.get('codPro')}] ({it.get('aparicoes', 0)}x)"
        for it in top_items[:3]
    ) or "não identificados"

    atraso = abs(days_until) if days_until is not None and days_until < 0 else 0
    janela_txt = (
        f"ATRASADO há {atraso} dias (era esperado em {proxima})" if atraso > 0
        else f"dentro da janela (próxima compra prevista: {proxima})"
    )

    return f"""Cliente: {nome}
Recorrência: {tier_label}
Intervalo médio entre pedidos: {intervalo} dias
Situação: {janela_txt}
Pedidos últimos 30 dias: {pedidos_30d}
Produtos mais comprados: {top_txt}

Últimos 3 pedidos:{pedidos_txt}

Avalie se este cliente deve receber contato de recorrência agora.
Responda APENAS com JSON válido, sem texto adicional, exatamente neste formato:
{{
  "decisao": "sim" ou "nao",
  "nivel_confianca": "alto", "medio" ou "baixo",
  "motivo": "explicação breve",
  "pedido_sugerido": [{{"codPro": "...", "desPro": "...", "qtdPed": 0}}],
  "valor_medio": 0.0,
  "mensagem": "mensagem personalizada para o cliente (apenas se decisao=sim, senão string vazia)"
}}

Regras obrigatórias:
- Use APENAS codPro presentes nos pedidos acima. Nunca invente produtos.
- Quantidades devem ser baseadas no histórico real.
- Se não houver padrão claro, retorne decisao=nao."""


# ─── Chamada à IA ─────────────────────────────────────────────────────────────

def _call_ai(prompt: str) -> dict:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY não configurado no .env")

    from openai import OpenAI

    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    client = OpenAI(api_key=api_key)

    response = client.chat.completions.create(
        model=model,
        temperature=0,
        max_tokens=1024,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
    )
    raw = response.choices[0].message.content.strip()
    return json.loads(raw)


# ─── Validação da resposta da IA ──────────────────────────────────────────────

def _known_codes(target: dict) -> set[str]:
    """Retorna todos os codPro presentes no histórico real do target."""
    codes: set[str] = set()
    for p in (target.get("last_3_orders_json") or []):
        for item in (p.get("itens") or []):
            c = str(item.get("codPro") or "").strip()
            if c:
                codes.add(c)
    for item in (target.get("top_items_json") or []):
        c = str(item.get("codPro") or "").strip()
        if c:
            codes.add(c)
    return codes


def _validate_response(decision: dict, known: set[str]) -> str:
    """
    Valida a resposta da IA e retorna o status a persistir.
    Lança ValueError se a resposta for estruturalmente inválida ou contiver
    produtos inventados — nesses casos o candidato não deve ser atualizado.
    """
    decisao = str(decision.get("decisao") or "").lower()
    confianca = str(decision.get("nivel_confianca") or "").lower()

    if decisao not in ("sim", "nao"):
        raise ValueError(f"Campo 'decisao' inválido: {decisao!r}")
    if confianca not in ("alto", "medio", "baixo"):
        raise ValueError(f"Campo 'nivel_confianca' inválido: {confianca!r}")

    pedido = decision.get("pedido_sugerido") or []

    if decisao == "nao":
        return "ai_rejected"

    # decisao == "sim" — validações adicionais

    # Produto inventado → rejeitar a resposta inteira
    for item in pedido:
        code = str(item.get("codPro") or "").strip()
        if code and known and code not in known:
            raise ValueError(
                f"IA sugeriu produto fora do histórico: codPro={code!r}. "
                "Resposta rejeitada para evitar sugestão inventada."
            )

    # Confiança baixa com aprovação → revisão humana
    if confianca == "baixo":
        return "needs_review"

    # Aprovação sem pedido sugerido → revisão humana (contato genérico aceitável,
    # mas não pode ir direto para disparo automático)
    if not pedido:
        return "needs_review"

    return "ai_approved"


def _has_order_items(target: dict) -> bool:
    for p in (target.get("last_3_orders_json") or []):
        if p.get("itens"):
            return True
    return False


# ─── Comando principal ────────────────────────────────────────────────────────

def cmd_run(limit: int, target_id: str | None) -> dict:
    db = _db()
    now = datetime.now(timezone.utc)

    query = (
        db.table("recurrence_targets")
        .select("*")
        .eq("status", "candidate")
        .eq("target_type", "recorrencia")
    )
    if target_id:
        query = query.eq("id", target_id)
    query = query.order("updated_at", desc=False).limit(limit)
    res = query.execute()
    candidates = res.data or []

    logger.info("Candidatos para validar: %d", len(candidates))

    processed = 0
    approved = 0
    rejected = 0
    needs_review = 0
    errors: list[dict] = []

    for target in candidates:
        tid = target.get("id")
        nome = target.get("customer_name") or tid
        try:
            # Candidato sem itens nos pedidos → rejeitar por dados insuficientes
            if not _has_order_items(target):
                logger.warning("Candidato %s sem itens nos pedidos — rejeitando", nome)
                db.table("recurrence_targets").update({
                    "ai_validated": True,
                    "ai_decision": "nao",
                    "ai_reasoning": json.dumps(
                        {"motivo": "Sem itens nos pedidos — dados insuficientes para análise"},
                        ensure_ascii=False,
                    ),
                    "status": "ai_rejected",
                    "updated_at": now.isoformat(),
                }).eq("id", tid).execute()
                rejected += 1
                processed += 1
                continue

            known = _known_codes(target)
            prompt = _build_prompt(target)
            logger.info("Validando: %s", nome)

            decision = _call_ai(prompt)

            new_status = _validate_response(decision, known)

            db.table("recurrence_targets").update({
                "ai_validated": True,
                "ai_decision": decision.get("decisao", "nao").lower(),
                "ai_reasoning": json.dumps(decision, ensure_ascii=False),
                "status": new_status,
                "updated_at": now.isoformat(),
            }).eq("id", tid).execute()

            if new_status == "ai_approved":
                approved += 1
                logger.info("APROVADO: %s | confianca=%s", nome, decision.get("nivel_confianca"))
            elif new_status == "needs_review":
                needs_review += 1
                logger.info("REVISAO: %s | motivo=%s", nome, decision.get("motivo", "")[:80])
            else:
                rejected += 1
                logger.info("REJEITADO: %s | motivo=%s", nome, decision.get("motivo", "")[:80])

            processed += 1

        except json.JSONDecodeError as exc:
            logger.error("Resposta da IA fora do JSON para %s: %s", nome, exc)
            errors.append({"id": tid, "nome": nome, "error": f"JSON inválido: {exc}"})

        except ValueError as exc:
            # Resposta da IA estruturalmente inválida (produto inventado, campo ausente, etc.)
            logger.error("Resposta inválida da IA para %s: %s", nome, exc)
            errors.append({"id": tid, "nome": nome, "error": str(exc)})

        except Exception as exc:
            logger.error("Erro ao validar %s: %s", nome, exc)
            errors.append({"id": tid, "nome": nome, "error": str(exc)})

    return {
        "processed": processed,
        "approved": approved,
        "rejected": rejected,
        "needs_review": needs_review,
        "errors": errors,
    }


# ─── CLI ──────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(description="Agente de validação de recorrência (OpenAI)")
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
