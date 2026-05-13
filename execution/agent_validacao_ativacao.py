"""
agent_validacao_ativacao.py
============================
Agente de validação do pipeline de Ativação Comercial.

Lê recurrence_targets com target_type='ativacao' e status='activation_candidate'.
Usa abordagem consultiva — NÃO assume padrão previsível de recompra.
Decide se vale abordar comercialmente e monta mensagem aberta.

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
    "Você é um agente de ativação comercial consultivo para uma distribuidora B2B. "
    "Analise o histórico do cliente e decida se vale fazer uma abordagem comercial aberta. "
    "NUNCA assuma padrão previsível de compra. Use linguagem consultiva e natural. "
    "Responda APENAS com um objeto JSON válido, sem texto extra."
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
    pedidos_30d = target.get("orders_count_30d") or 0
    ultimo_pedido = target.get("last_order_date") or "desconhecido"
    last3 = target.get("last_3_orders_json") or []
    top_items = target.get("top_items_json") or []

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

    return f"""Cliente: {nome}
Pedidos recentes (30d): {pedidos_30d}
Último pedido: {ultimo_pedido}
Produtos do histórico: {top_txt}

Últimos 3 pedidos:{pedidos_txt if pedidos_txt else " sem histórico disponível"}

Contexto: Este cliente não tem padrão previsível de recompra (foi descartado pelo pipeline
de recorrência). Avalie se ainda faz sentido uma abordagem comercial consultiva e aberta.

REGRAS OBRIGATÓRIAS:
- NÃO mencione "seu pedido costuma acontecer nessa época" ou variantes
- NÃO assuma padrão de compra ou frequência previsível
- Use abordagem consultiva: ofereça ajuda, não assuma necessidade
- Mensagem deve ser curta, natural e útil (máx 2-3 linhas)
- Se não houver dados suficientes, retorne decisao=nao

Responda APENAS com JSON válido neste formato exato:
{{
  "decisao": "sim" ou "nao",
  "tipo_abordagem": "cliente_irregular" | "cliente_adormecido" | "cliente_novo_potencial" | "descartar",
  "nivel_confianca": "alto" | "medio" | "baixo",
  "motivo": "explicação breve",
  "mensagem": "mensagem para o cliente (apenas se decisao=sim, senão string vazia)"
}}"""


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
        max_tokens=512,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
    )
    raw = response.choices[0].message.content.strip()
    return json.loads(raw)


# ─── Validação da resposta da IA ──────────────────────────────────────────────

VALID_TIPOS = {"cliente_irregular", "cliente_adormecido", "cliente_novo_potencial", "descartar"}


def _validate_response(decision: dict) -> str:
    decisao = str(decision.get("decisao") or "").lower()
    confianca = str(decision.get("nivel_confianca") or "").lower()
    tipo = str(decision.get("tipo_abordagem") or "").lower()

    if decisao not in ("sim", "nao"):
        raise ValueError(f"Campo 'decisao' inválido: {decisao!r}")
    if confianca not in ("alto", "medio", "baixo"):
        raise ValueError(f"Campo 'nivel_confianca' inválido: {confianca!r}")
    if tipo not in VALID_TIPOS:
        raise ValueError(f"Campo 'tipo_abordagem' inválido: {tipo!r}")

    if decisao == "nao":
        return "activation_rejected"

    return "activation_approved"


# ─── Comando principal ────────────────────────────────────────────────────────

def cmd_run(limit: int, target_id: str | None) -> dict:
    db = _db()
    now = datetime.now(timezone.utc)

    query = (
        db.table("recurrence_targets")
        .select("*")
        .eq("target_type", "ativacao")
        .eq("status", "activation_candidate")
    )
    if target_id:
        query = query.eq("id", target_id)
    query = query.order("updated_at", desc=False).limit(limit)
    res = query.execute()
    candidates = res.data or []

    logger.info("Candidatos de ativação para validar: %d", len(candidates))

    processed = 0
    approved = 0
    rejected = 0
    errors: list[dict] = []

    for target in candidates:
        tid = target.get("id")
        nome = target.get("customer_name") or tid
        try:
            prompt = _build_prompt(target)
            logger.info("Validando ativação: %s", nome)

            decision = _call_ai(prompt)
            new_status = _validate_response(decision)

            db.table("recurrence_targets").update({
                "ai_validated": True,
                "ai_decision": decision.get("decisao", "nao").lower(),
                "ai_reasoning": json.dumps(decision, ensure_ascii=False),
                "status": new_status,
                "updated_at": now.isoformat(),
            }).eq("id", tid).execute()

            if new_status == "activation_approved":
                approved += 1
                logger.info(
                    "APROVADO: %s | tipo=%s | confianca=%s",
                    nome, decision.get("tipo_abordagem"), decision.get("nivel_confianca"),
                )
            else:
                rejected += 1
                logger.info("REJEITADO: %s | motivo=%s", nome, decision.get("motivo", "")[:80])

            processed += 1

        except json.JSONDecodeError as exc:
            logger.error("Resposta da IA fora do JSON para %s: %s", nome, exc)
            errors.append({"id": tid, "nome": nome, "error": f"JSON inválido: {exc}"})

        except ValueError as exc:
            logger.error("Resposta inválida da IA para %s: %s", nome, exc)
            errors.append({"id": tid, "nome": nome, "error": str(exc)})

        except Exception as exc:
            logger.error("Erro ao validar %s: %s", nome, exc)
            errors.append({"id": tid, "nome": nome, "error": str(exc)})

    return {
        "processed": processed,
        "approved": approved,
        "rejected": rejected,
        "errors": errors,
    }


# ─── CLI ──────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(description="Agente de validação de ativação comercial (OpenAI)")
    subparsers = parser.add_subparsers(dest="command", required=True)

    p_run = subparsers.add_parser("run")
    p_run.add_argument("--limit", type=int, default=20)
    p_run.add_argument("--id", dest="target_id", default=None)

    args = parser.parse_args()

    try:
        if args.command == "run":
            return success(cmd_run(limit=args.limit, target_id=args.target_id))
        return failure("Comando não suportado")
    except Exception as exc:
        logger.exception("Falha no agente de validação de ativação")
        return failure(str(exc))


if __name__ == "__main__":
    raise SystemExit(main())
