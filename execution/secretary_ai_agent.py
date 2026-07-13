"""
Camada central de intencao da Secretaria IA.

Este modulo nao executa banco nem envia pedido. Ele interpreta a mensagem e
devolve uma decisao estruturada para o backend chamar as tools seguras.
"""

from __future__ import annotations

import json
import os
import re
import unicodedata
from typing import Any


SALE_TYPE_LABELS = {
    "90100": "pedido normal",
    "9010P": "pedido PDV",
    "BONIF4": "bonificacao - acordo comercial",
}

INTENTS = {
    "start_order",
    "inform_customer",
    "confirm_customer",
    "select_sale_type",
    "inform_products",
    "correct_products",
    "keep_current_customer",
    "change_customer",
    "show_summary",
    "confirm_submit",
    "cancel_order",
    "check_status",
    "smalltalk",
    "unknown",
}

SECRETARY_AI_SYSTEM_PROMPT = """
Voce e a Secretaria IA de pedidos da Sucos SPRES no WhatsApp.
Seu papel e entender a mensagem do representante e decidir a intencao.
Nao invente cliente, produto, preco, tabela ou numero de pedido.
O backend fara as validacoes e chamara tools seguras.

Responda somente JSON valido com:
{
  "intent": "uma_intencao",
  "sale_type_code": "90100|9010P|BONIF4|null",
  "sale_type_only": true|false,
  "looks_like_product": true|false,
  "keep_current_customer": true|false,
  "product_text": "texto do produto quando houver",
  "customer_query": "codigo/nome/documento quando houver",
  "confidence": 0.0
}

Codigos de tipo:
- pedido normal/com nota: 90100
- pedido PDV/sem nota: 9010P
- bonificacao: BONIF4

Se o representante disser que nao quer trocar/mudar cliente e tambem informar produto,
use intent "inform_products", keep_current_customer true e product_text somente com o trecho dos produtos.
"""


def _norm(value: Any) -> str:
    normalized = unicodedata.normalize("NFKD", str(value or ""))
    return "".join(ch for ch in normalized if not unicodedata.combining(ch)).lower().strip()


def _sale_type_code_from_text(text: Any) -> str | None:
    value = _norm(text)
    if re.search(r"\b(pdv|sem nota)\b", value):
        return "9010P"
    if re.search(r"\b(bonificacao|bonifica[cç][aã]o|bonif)\b", value):
        return "BONIF4"
    if re.search(r"\b(normal|nota fiscal|com nota)\b", value):
        return "90100"
    return None


def _sale_type_only_message(text: Any) -> bool:
    value = re.sub(r"[^\w\s/]+", " ", _norm(text))
    value = re.sub(r"\s+", " ", value).strip()
    simplified = value
    for prefix in ("entrada pedido ", "pedido ", "ficou pedido ", "e pedido ", "é pedido "):
        if simplified.startswith(prefix):
            simplified = simplified[len(prefix) :].strip()
            break
    for suffix in (" mesmo", "?", " ok"):
        if simplified.endswith(suffix.strip()):
            simplified = simplified[: -len(suffix.strip())].strip()
    return simplified in {
        "normal",
        "com nota",
        "nota fiscal",
        "pdv",
        "sem nota",
        "bonificacao",
        "bonif",
        "bonificacao acordo",
    }


def _looks_like_product_message(text: Any) -> bool:
    value = _norm(text)
    if not value:
        return False
    has_quantity = bool(re.search(r"\b\d+([,.]\d+)?\b", value))
    has_product_word = bool(
        re.search(
            r"\b(suco|laranja|uva|caju|manga|maracuja|morango|abacaxi|copo|garrafa|galao|gal[aã]o|bolsa|bag|nectar|concentrado)\b",
            value,
        )
    )
    has_size = bool(re.search(r"\b\d+\s*(ml|l|litro|litros)\b", value))
    return has_product_word and (has_quantity or has_size)


def _wants_keep_current_customer(text: Any) -> bool:
    value = _norm(text)
    return bool(
        re.search(r"\b(nao|não)\b.*\b(mudar|trocar|altera|alterar)\b.*\bcliente\b", value)
        or re.search(r"\b(continuar|continua|mantem|manter|fica nesse|seguir nesse)\b", value)
    )


def _strip_keep_current_customer_prefix(text: str) -> str:
    cleaned = re.sub(
        r"(?i)\b(n[aã]o\s+quero\s+(mudar|trocar|alterar)\s+o?\s*cliente\.?)",
        "",
        str(text or ""),
    )
    cleaned = re.sub(
        r"(?i)\b(quero\s+continuar\s+(com|nesse)\s+cliente\.?|continuar\.?)",
        "",
        cleaned,
    )
    return cleaned.strip(" .,-")


def _heuristic_analysis(text: str, state: dict | None = None) -> dict:
    state = state or {}
    sale_type_code = _sale_type_code_from_text(text)
    sale_type_only = bool(sale_type_code and _sale_type_only_message(text))
    looks_like_product = _looks_like_product_message(text)
    keep_current = _wants_keep_current_customer(text)
    product_text = _strip_keep_current_customer_prefix(text) if keep_current else str(text or "")

    if sale_type_only:
        intent = "select_sale_type"
    elif keep_current and looks_like_product:
        intent = "inform_products"
    elif looks_like_product and state.get("customer"):
        intent = "inform_products"
    elif keep_current:
        intent = "keep_current_customer"
    else:
        intent = "unknown"

    return {
        "intent": intent,
        "sale_type_code": sale_type_code,
        "sale_type_only": sale_type_only,
        "looks_like_product": looks_like_product,
        "keep_current_customer": keep_current,
        "product_text": product_text,
        "customer_query": "",
        "confidence": 0.65 if intent != "unknown" else 0.25,
        "source": "heuristic",
    }


def _ai_enabled() -> bool:
    return os.getenv("SECRETARY_AI_BRAIN_ENABLED", "false").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _json_from_ai(content: str) -> dict:
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", content or "", re.S)
        if not match:
            return {}
        try:
            data = json.loads(match.group(0))
        except json.JSONDecodeError:
            return {}
    return data if isinstance(data, dict) else {}


def _sanitize_ai_decision(raw: dict, fallback: dict, text: str) -> dict:
    intent = str(raw.get("intent") or fallback.get("intent") or "unknown")
    if intent not in INTENTS:
        intent = fallback.get("intent") or "unknown"
    sale_type_code = raw.get("sale_type_code") or fallback.get("sale_type_code")
    if sale_type_code not in {"90100", "9010P", "BONIF4", None, ""}:
        sale_type_code = fallback.get("sale_type_code")
    product_text = str(raw.get("product_text") or "").strip()
    if not product_text and (raw.get("keep_current_customer") or fallback.get("keep_current_customer")):
        product_text = _strip_keep_current_customer_prefix(text)
    if not product_text:
        product_text = fallback.get("product_text") or str(text or "")
    try:
        confidence = float(raw.get("confidence", fallback.get("confidence", 0.5)))
    except (TypeError, ValueError):
        confidence = fallback.get("confidence", 0.5)
    return {
        **fallback,
        "intent": intent,
        "sale_type_code": sale_type_code or None,
        "sale_type_only": bool(raw.get("sale_type_only", fallback.get("sale_type_only"))),
        "looks_like_product": bool(raw.get("looks_like_product", fallback.get("looks_like_product"))),
        "keep_current_customer": bool(raw.get("keep_current_customer", fallback.get("keep_current_customer"))),
        "product_text": product_text,
        "customer_query": str(raw.get("customer_query") or fallback.get("customer_query") or "").strip(),
        "confidence": max(0.0, min(1.0, confidence)),
        "source": "gpt",
    }


def _analyze_with_gpt(text: str, state: dict, fallback: dict) -> dict | None:
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key or not _ai_enabled():
        return None
    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key)
        model = os.getenv("SECRETARY_AI_MODEL", os.getenv("OPENAI_MODEL", "gpt-4.1-mini")).strip()
        compact_state = {
            "has_customer": bool(state.get("customer")),
            "customer": (state.get("customer") or {}).get("name") if isinstance(state.get("customer"), dict) else None,
            "sale_type_code": state.get("sale_type_code"),
            "has_items": bool(state.get("items")),
            "ready_to_submit": bool(state.get("ready_to_submit")),
            "pending_action": (state.get("pending_action") or {}).get("type") if isinstance(state.get("pending_action"), dict) else None,
        }
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SECRETARY_AI_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "mensagem": text,
                            "estado": compact_state,
                            "fallback": fallback,
                        },
                        ensure_ascii=False,
                    ),
                },
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
        )
        content = response.choices[0].message.content or "{}"
        return _sanitize_ai_decision(_json_from_ai(content), fallback, text)
    except Exception:
        return None


def analyze_secretary_message(text: str, state: dict | None = None) -> dict:
    state = state or {}
    fallback = _heuristic_analysis(text, state)
    return _analyze_with_gpt(text, state, fallback) or fallback
