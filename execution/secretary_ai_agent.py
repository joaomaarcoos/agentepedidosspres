"""
Camada central de intencao da Secretaria IA.

Este modulo nao executa banco nem envia pedido. Ele interpreta a mensagem e
devolve uma decisao estruturada para o backend chamar as tools seguras.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any


SALE_TYPE_LABELS = {
    "9010O": "pedido normal",
    "9010P": "pedido PDV",
    "BONIF4": "bonificacao - acordo comercial",
}


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
        return "9010O"
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


def analyze_secretary_message(text: str, state: dict | None = None) -> dict:
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
    }
