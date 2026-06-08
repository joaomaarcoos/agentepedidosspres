"""
ai_agent.py
===========
Core de atendimento WhatsApp com controle de pausa.

Regras:
- "##" pausa a IA por 5 horas.
- "###" despausa imediatamente.
- Pausa expirada e removida automaticamente no proximo evento.
- O contexto enviado para a IA usa apenas as ultimas 15 mensagens salvas.
"""

from __future__ import annotations

import json
import logging
import os
import re
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_ROOT / ".env")

sys.path.insert(0, str(_ROOT))
from prompts.builder import build_prompt

logger = logging.getLogger(__name__)

PAUSE_TRIGGER = "##"
RESUME_TRIGGER = "###"
PAUSE_HOURS = int(os.getenv("AI_PAUSE_HOURS", "5"))
CONTEXT_MESSAGE_LIMIT = int(os.getenv("AI_CONTEXT_MESSAGE_LIMIT", "40"))
DEFAULT_MESSAGE_BUFFER_SECONDS = float(os.getenv("AI_MESSAGE_BUFFER_SECONDS", "5"))
BACKEND_CATALOG_GUARD_ENABLED = os.getenv("AI_BACKEND_CATALOG_GUARD", "true").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}
BACKEND_ORDER_SPECIFICS_GUARD_ENABLED = os.getenv("AI_BACKEND_ORDER_SPECIFICS_GUARD", "true").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}
AVAILABLE_PRICE_TABLES = {
    code.strip()
    for code in os.getenv("AVAILABLE_PRICE_TABLES", "201,202").split(",")
    if code.strip()
}
FALLBACK_PRICE_TABLE = os.getenv("FALLBACK_PRICE_TABLE", "201").strip()
LOCAL_DATA_DIR = Path(__file__).resolve().parent.parent / ".tmp" / "data"
CONVERSATIONS_TABLE = "ai_conversations"
MESSAGES_TABLE = "ai_conversation_messages"
STATE_TABLE = "system_settings"
BUFFER_SETTING_KEY = "ai_message_buffer_seconds"
LOCAL_TIMEZONE = ZoneInfo(os.getenv("AI_LOCAL_TIMEZONE", "America/Sao_Paulo"))


def _notify_order_review(order_id: str | None) -> None:
    if not order_id:
        return
    try:
        from review_order_whatsapp import notify_representative_order_review

        result = notify_representative_order_review(str(order_id))
        if result.get("sent"):
            logger.info("Pedido %s notificado ao representante: %s", order_id, result)
        else:
            logger.warning("Pedido %s nao notificado ao representante: %s", order_id, result)
    except Exception as exc:
        logger.warning("Falha ao notificar representante sobre pedido %s: %s", order_id, exc)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def local_now() -> datetime:
    return datetime.now(LOCAL_TIMEZONE)


def format_local_datetime(value: datetime) -> str:
    weekday_names = [
        "segunda-feira",
        "terca-feira",
        "quarta-feira",
        "quinta-feira",
        "sexta-feira",
        "sabado",
        "domingo",
    ]
    return f"{weekday_names[value.weekday()]}, {value.strftime('%d/%m/%Y')} as {value.strftime('%H:%M')}"


def next_business_day(value: datetime | None = None) -> datetime:
    current = value or local_now()
    candidate = current + timedelta(days=1)
    while candidate.weekday() >= 5:
        candidate += timedelta(days=1)
    return candidate


def iso_z(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_dt(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def normalize_phone(value: str | None) -> str:
    digits = re.sub(r"\D", "", str(value or ""))
    if digits.startswith("55") and len(digits) >= 12:
        return digits
    return digits


def normalize_text(value: str | None) -> str:
    return str(value or "").strip()


def resolve_price_table(codigo_tabela: str | None) -> tuple[str | None, bool]:
    codigo = str(codigo_tabela or "").strip()
    if codigo and codigo in AVAILABLE_PRICE_TABLES:
        return codigo, False
    if FALLBACK_PRICE_TABLE:
        return FALLBACK_PRICE_TABLE, True
    return codigo or None, False


def _safe_float_setting(value: Any, default: float) -> float:
    try:
        parsed = float(value)
        if parsed < 0:
            return default
        return parsed
    except (TypeError, ValueError):
        return default


def _lower_ascii(value: str) -> str:
    import unicodedata

    normalized = unicodedata.normalize("NFKD", value or "")
    return "".join(ch for ch in normalized if not unicodedata.combining(ch)).lower()


def _product_text(row: dict) -> str:
    return _lower_ascii(
        " ".join(
            str(row.get(key) or "")
            for key in ("cod_produto", "nome_produto", "nome", "variacao", "derivacao")
        )
    )


def _catalog_name(row: dict) -> str:
    return normalize_text(row.get("nome_produto") or row.get("nome") or "")


def _catalog_variation(row: dict) -> str:
    return normalize_text(row.get("variacao") or row.get("derivacao") or "")


def _catalog_product_type(row: dict) -> str:
    name = _lower_ascii(_catalog_name(row))
    if "bolsa" in name and ("concentr" in name or "conc" in name):
        return "bolsa concentrada"
    if "bolsa" in name:
        return "bolsa"
    if "copo" in name:
        return "copo"
    if "garrafa" in name:
        return "garrafa"
    if "galao" in name:
        return "galao"
    return ""


def _display_variation(value: str) -> str:
    raw = normalize_text(value)
    upper = raw.upper()
    if upper == "05L":
        return "5L"
    if upper == "1L7":
        return "1,7L"
    if upper.isdigit():
        return f"{int(upper)}ml"
    return raw


def _public_variation(value: str) -> str:
    raw = normalize_text(value)
    upper = raw.upper()
    if upper in {"05L", "5L", "1L7"} or "ML" in upper or re.fullmatch(r"\d+", upper):
        return _display_variation(raw)
    if re.fullmatch(r"\d+(?:,\d+|\.\d+)?L", upper):
        return raw.replace(".", ",")
    return ""


def _public_product_label(row: dict) -> str:
    name = _catalog_name(row)
    value = _lower_ascii(name)
    public_tokens = []
    ignored = {
        "suco",
        "nectar",
        "copo",
        "garrafa",
        "bolsa",
        "conc",
        "concentrada",
        "concentrado",
        "integral",
        "152700",
        "152698",
        "152699",
    }
    for token in re.findall(r"[a-z0-9]+", value):
        if token in ignored:
            continue
        if token.isdigit() and len(token) >= 4:
            continue
        public_tokens.append(token)
    return " ".join(public_tokens).title() or name.title()


def _catalog_flavor_tokens(row: dict) -> set[str]:
    name = _lower_ascii(_catalog_name(row))
    ignored = {
        "suco",
        "nectar",
        "nectar",
        "copo",
        "garrafa",
        "bolsa",
        "concentrada",
        "concentrado",
        "integral",
        "com",
        "sem",
        "polpa",
        "unidade",
        "unidades",
        "ml",
        "litro",
        "litros",
    }
    tokens = set(re.findall(r"[a-z0-9]+", name))
    return {token for token in tokens if len(token) >= 4 and token not in ignored and not token.isdigit()}


def _catalog_flavor_token_list(row: dict) -> list[str]:
    name = _lower_ascii(_catalog_name(row))
    ignored = {
        "suco",
        "nectar",
        "copo",
        "garrafa",
        "bolsa",
        "concentrada",
        "concentrado",
        "integral",
        "com",
        "sem",
        "de",
        "da",
        "do",
        "e",
        "polpa",
        "unidade",
        "unidades",
        "ml",
        "litro",
        "litros",
    }
    result = []
    for token in re.findall(r"[a-z0-9]+", name):
        if len(token) < 4 or token in ignored or token.isdigit():
            continue
        result.append(token)
    return result


def _catalog_public_phrases(row: dict) -> set[str]:
    tokens = _catalog_flavor_token_list(row)
    token_set = set(tokens)
    phrases = set(tokens)

    if "agua" in token_set and "coco" in token_set:
        phrases.update({"agua de coco", "agua coco"})
    if "manga" in token_set and "maracuja" in token_set:
        phrases.update({"manga e maracuja", "manga maracuja"})
    if "abacaxi" in token_set and "hortela" in token_set:
        phrases.update({"abacaxi com hortela", "abacaxi hortela"})
    if "laranja" in token_set and "morango" in token_set:
        phrases.update({"laranja com morango", "laranja morango"})

    if len(tokens) >= 2:
        joined = " ".join(tokens)
        phrases.add(joined)
        phrases.add(" e ".join(tokens))
        phrases.add(" com ".join(tokens))

    return {phrase for phrase in phrases if phrase}


def _catalog_options_for_token(token: str, produtos: list[dict] | None) -> list[dict]:
    wanted = _lower_ascii(token)
    if not wanted or not produtos:
        return []
    matches = []
    for row in produtos:
        if (
            wanted in _catalog_public_phrases(row)
            or wanted in _catalog_flavor_tokens(row)
            or wanted in _lower_ascii(_catalog_name(row))
        ):
            matches.append(row)
    return matches


def _format_catalog_options(rows: list[dict]) -> str:
    grouped: dict[tuple[str, str], list[dict]] = {}
    for row in rows:
        product_type = _catalog_product_type(row) or "produto"
        variation = _display_variation(_catalog_variation(row)) or "-"
        grouped.setdefault((product_type, variation), []).append(row)
    parts = []
    for product_type, variation in sorted(grouped):
        sample = grouped[(product_type, variation)][0]
        price = _format_brl(sample.get("preco") or sample.get("preco_base") or sample.get("preco_tabela_201"))
        suffix = f" ({price})" if price else ""
        public_variation = _public_variation(variation)
        if product_type == "produto":
            label = f"opção {public_variation}".strip()
        else:
            label = f"{product_type} {public_variation or variation}".strip()
        parts.append(f"{label}{suffix}")
    return ", ".join(parts)


def _format_catalog_options_lines(rows: list[dict]) -> list[str]:
    grouped: dict[tuple[str, str], list[dict]] = {}
    for row in rows:
        product_type = _catalog_product_type(row) or "produto"
        variation = _display_variation(_catalog_variation(row)) or "-"
        grouped.setdefault((product_type, variation), []).append(row)

    lines = []
    for product_type, variation in sorted(grouped):
        sample = grouped[(product_type, variation)][0]
        price = _format_brl(sample.get("preco") or sample.get("preco_base") or sample.get("preco_tabela_201"))
        suffix = f" - {price}" if price else ""
        public_variation = _public_variation(variation)
        if product_type == "produto":
            label = f"opção {public_variation}".strip()
        else:
            label = f"{product_type} {public_variation or variation}".strip()
        lines.append(f"- {label}{suffix}")
    return lines


def _format_catalog_product_lines(rows: list[dict], limit: int = 8) -> list[str]:
    lines = []
    seen: set[tuple[str, str, str]] = set()
    for row in rows:
        name = _catalog_name(row)
        if not name:
            continue
        product_type = _catalog_product_type(row) or "produto"
        variation = _display_variation(_catalog_variation(row)) or "-"
        key = (name, product_type, variation)
        if key in seen:
            continue
        seen.add(key)
        price = _format_brl(row.get("preco") or row.get("preco_base") or row.get("preco_tabela_201"))
        suffix = f" - {price}" if price else ""
        public_variation = _public_variation(variation) or variation
        lines.append(f"- {name} | {product_type} {public_variation}{suffix}".strip())
        if len(lines) >= limit:
            break
    return lines


def _display_catalog_term(term: str) -> str:
    value = normalize_text(term)
    replacements = {
        "agua": "água",
        "caja": "cajá",
        "maracuja": "maracujá",
        "limao": "limão",
        "hortela": "hortelã",
    }
    for raw, accented in replacements.items():
        value = re.sub(rf"\b{raw}\b", accented, value, flags=re.IGNORECASE)
    return value


def _requested_type_from_text(text: str) -> str:
    value = _lower_ascii(text)
    if "bolsa" in value and ("concentrada" in value or "concentrado" in value or "conc" in value):
        return "bolsa concentrada"
    if "bolsa" in value:
        return "bolsa"
    if "copo" in value:
        return "copo"
    if "garrafa" in value:
        return "garrafa"
    if "galao" in value or "galão" in value:
        return "galao"
    return ""


def _selected_product_type_from_text(text: str) -> str:
    value = _lower_ascii(text)
    if "bolsa" in value and ("concentrada" in value or "concentrado" in value or "conc" in value):
        return "bolsa concentrada"
    if "copo" in value:
        return "copo"
    if "garrafa" in value:
        return "garrafa"
    if "bolsa" in value:
        return "bolsa"
    if "galao" in value or "galao" in value:
        return "galao"
    return ""


def _requested_size_from_text(text: str) -> str:
    value = _lower_ascii(text)
    match = re.search(r"\b(115|200|300|900)\s*(?:ml)?\b", value)
    if match:
        return _norm_size(match.group(1))
    if re.search(r"\b(?:1\s*,?\s*7|1l7)\s*l?\b", value):
        return "1.7l"
    if re.search(r"\b(?:05|5)\s*l\b", value):
        return "5l"
    return ""


def _filter_catalog_options_by_request(rows: list[dict], text: str) -> list[dict]:
    requested_type = _requested_type_from_text(text)
    requested_size = _requested_size_from_text(text)
    filtered = []
    for row in rows:
        row_type = _lower_ascii(_catalog_product_type(row))
        row_size = _norm_size(_display_variation(_catalog_variation(row)))
        type_ok = not requested_type or requested_type in row_type or row_type in requested_type
        size_ok = not requested_size or requested_size == row_size
        if type_ok and size_ok:
            filtered.append(row)
    return filtered


def _catalog_alternatives_for_request(text: str, produtos: list[dict] | None) -> tuple[str, list[dict]]:
    if not produtos:
        return "", []

    requested_type = _requested_type_from_text(text)
    requested_size = _requested_size_from_text(text)
    if not requested_type and not requested_size:
        return "", []

    exact: list[dict] = []
    same_type: list[dict] = []
    same_size: list[dict] = []
    beverage_context = bool(requested_type) or contains_any(
        _lower_ascii(text),
        ("suco", "nectar", "sabor", "agua de coco"),
    )
    rows = [
        row
        for row in produtos
        if not beverage_context
        or _catalog_product_type(row)
        or contains_any(_lower_ascii(_catalog_name(row)), ("suco", "nectar", "agua"))
    ]
    for row in rows:
        row_type = _lower_ascii(_catalog_product_type(row))
        row_size = _norm_size(_display_variation(_catalog_variation(row)))
        type_ok = not requested_type or requested_type in row_type or row_type in requested_type
        size_ok = not requested_size or requested_size == row_size
        if type_ok and size_ok:
            exact.append(row)
        if requested_type and type_ok:
            same_type.append(row)
        if requested_size and size_ok:
            same_size.append(row)

    if exact:
        label_parts = []
        if requested_type:
            label_parts.append(requested_type)
        if requested_size:
            label_parts.append(_display_variation(requested_size))
        return " ".join(label_parts).strip(), exact
    if same_type:
        return requested_type, same_type
    if same_size:
        return _display_variation(requested_size), same_size
    return "", []


def _catalog_stop_tokens() -> set[str]:
    return {
        "adicione",
        "adicionar",
        "adiciona",
        "comprar",
        "compra",
        "come",
        "comecar",
        "começar",
        "ai",
        "alem",
        "alguma",
        "algum",
        "beleza",
        "cotacao",
        "cotar",
        "entao",
        "faz",
        "fazer",
        "fzer",
        "fzr",
        "inclui",
        "incluir",
        "coloca",
        "tambem",
        "também",
        "tamb",
        "quero",
        "queria",
        "pedido",
        "pedid",
        "pedi",
        "pedir",
        "pela",
        "pelas",
        "pelo",
        "pelos",
        "primeiro",
        "produto",
        "produtos",
        "sabor",
        "sabores",
        "suco",
        "nectar",
        "unidade",
        "unidades",
        "copo",
        "copos",
        "garrafa",
        "garrafas",
        "bolsa",
        "bolsas",
        "concentrada",
        "concentrado",
        "tamanho",
        "tamanhos",
        "preco",
        "valor",
        "mais",
        "menos",
        "novo",
        "outro",
        "outros",
        "outra",
        "outras",
        "mesmo",
        "anterior",
        "revisao",
        "protocolo",
        "para",
        "com",
        "sem",
        "de",
        "da",
        "do",
        "das",
        "dos",
        "uma",
        "umas",
        "uns",
        "vai",
        "ser",
        "seguinte",
        "ve",
        "mim",
        "ta",
        "que",
        "qual",
        "quais",
        "respondeu",
        "saber",
        "so",
        "tipo",
        "tipos",
        "voce",
        "voces",
        "perguntei",
        "vende",
        "coisa",
        "coisas",
        "express",
    }


def _catalog_phrases_in_text(text: str, produtos: list[dict] | None) -> list[str]:
    value = _lower_ascii(text)
    if not value or not produtos:
        return []

    phrases: set[str] = set()
    for row in produtos:
        for phrase in _catalog_public_phrases(row):
            if " " not in phrase:
                continue
            if re.search(rf"(?<![a-z0-9]){re.escape(phrase)}(?![a-z0-9])", value):
                phrases.add(phrase)
    return sorted(phrases, key=lambda phrase: (-len(phrase), phrase))


def _requested_catalog_tokens(text: str, produtos: list[dict] | None, require_trigger: bool = True) -> list[str]:
    value = _lower_ascii(text)
    if not produtos:
        return []
    if require_trigger and not (
        _has_order_adjustment_terms(text)
        or contains_any(value, ("quero", "produto", "produtos", "preco", "valor", "tem", "voces tem", "vocês tem"))
        or infer_entities(text).get("quantities")
    ):
        return []

    stop = _catalog_stop_tokens()
    phrases = _catalog_phrases_in_text(text, produtos)
    consumed_tokens = {
        token
        for phrase in phrases
        for token in re.findall(r"[a-z0-9]+", phrase)
    }
    tokens = re.findall(r"[a-z0-9]+", value)
    candidates = list(phrases)
    for token in tokens:
        if token in consumed_tokens:
            continue
        if len(token) < 4 or any(ch.isdigit() for ch in token) or token in stop:
            continue
        if re.fullmatch(r"\d+(?:ml|l)?", token):
            continue
        candidates.append(token)
    return list(dict.fromkeys(candidates))


def _asks_non_suco_products(text: str) -> bool:
    value = _lower_ascii(text)
    return (
        contains_any(value, ("alem de suco", "sem ser suco", "nao tem so suco", "outros produtos"))
        or (
            "suco" in value
            and contains_any(value, ("alem", "sem ser", "outro", "outros"))
            and contains_any(value, ("produto", "produtos", "vende", "tem", "tipo"))
        )
    )


def _is_non_suco_catalog_item(row: dict) -> bool:
    text = _lower_ascii(_catalog_name(row))
    return bool(text) and "suco" not in text and "nectar" not in text


def non_suco_products_reply(produtos: list[dict] | None) -> str:
    rows = [row for row in produtos or [] if _is_non_suco_catalog_item(row)]
    if not rows:
        return "Aqui eu não encontrei outros produtos além dos sucos na tabela disponível. Quer ver as opções de suco por formato?"

    grouped: dict[str, list[dict]] = {}
    for row in rows:
        label = _catalog_name(row).strip()
        if label:
            grouped.setdefault(label, []).append(row)

    lines = ["Além dos sucos, tenho estas opções na tabela:", ""]
    for label in sorted(grouped)[:10]:
        sample = grouped[label][0]
        price = _format_brl(sample.get("preco") or sample.get("preco_base") or sample.get("preco_tabela_201"))
        lines.append(f"- {label}{f' - {price}' if price else ''}")
    lines += ["", "Qual item e quantidade você quer incluir?"]
    return "\n".join(lines)


def _catalog_request_segments(text: str) -> list[str]:
    segments = [
        segment.strip(" .,!?\n\t")
        for segment in re.split(r"[,;\n]+", text or "")
        if segment.strip(" .,!?\n\t")
    ]
    return segments or [text]


def _catalog_request_is_complex(text: str, produtos: list[dict] | None) -> bool:
    requested = _requested_catalog_tokens(text, produtos)
    if len(requested) <= 1:
        return False

    value = _lower_ascii(text)
    quantity_count = len(infer_entities(text).get("quantities") or [])
    package_count = len(
        re.findall(
            r"\b(?:bolsas?|copos?|garrafas?|galoes?|galões?|concentrad[ao]s?)\b",
            value,
        )
    )
    size_count = len(
        re.findall(
            r"\b(?:115|200|300|900)\s*(?:ml)?\b|\b1\s*[,.]?\s*7\s*l?\b|\b(?:05|5)\s*l\b",
            value,
        )
    )
    return quantity_count > 1 or package_count > 1 or size_count > 1


def catalog_guard_prompt(text: str, produtos: list[dict] | None) -> str:
    if not _requested_catalog_tokens(text, produtos):
        return ""

    segments = _catalog_request_segments(text)
    if len(segments) <= 1:
        if _catalog_request_is_complex(text, produtos):
            return ""
        return _catalog_guard_prompt_for_segment(text, produtos)

    replies = []
    for segment in segments:
        reply = _catalog_guard_prompt_for_segment(segment, produtos, require_trigger=False)
        if reply:
            replies.append(reply)
    return "\n\n".join(dict.fromkeys(replies))


def _catalog_guard_prompt_for_segment(
    text: str,
    produtos: list[dict] | None,
    require_trigger: bool = True,
) -> str:
    requested = _requested_catalog_tokens(text, produtos, require_trigger=require_trigger)
    if not requested:
        return ""

    unavailable = []
    ambiguous_lines = []
    invalid_lines = []
    request_has_type = bool(_requested_type_from_text(text))
    request_has_size = bool(_requested_size_from_text(text))
    for token in requested:
        options = _catalog_options_for_token(token, produtos)
        if not options:
            unavailable.append(token)
            continue
        narrowed_options = _filter_catalog_options_by_request(options, text)
        if (request_has_type or request_has_size) and not narrowed_options:
            invalid_lines.append(f"- {_display_catalog_term(token)}: não existe nessa combinação. Opções reais: {_format_catalog_options(options)}")
            continue
        option_text = _format_catalog_options(narrowed_options or options)
        if option_text and (not request_has_type or not request_has_size):
            ambiguous_lines.append(f"- {_display_catalog_term(token)}: {option_text}")

    if unavailable or invalid_lines:
        lines = []
        if unavailable:
            labels = [_display_catalog_term(item) for item in unavailable]
            lines.append(f"Não temos {', '.join(labels)} nas opções disponíveis.")
        if invalid_lines:
            lines += ["Essa combinação de produto, formato e tamanho não está disponível:", *invalid_lines]
        if ambiguous_lines:
            lines += ["", "Dos outros produtos citados, temos estas opções:", *ambiguous_lines]

        alternative_label, alternatives = _catalog_alternatives_for_request(text, produtos)
        alternative_lines = _format_catalog_product_lines(alternatives)
        if alternative_lines:
            if alternative_label:
                lines += ["", f"Mas temos estas opções de {alternative_label}:"]
            else:
                lines += ["", "Mas temos estas opções disponíveis:"]
            lines.extend(alternative_lines)

        lines.append("Posso seguir com alguma dessas opções?")
        return "\n".join(lines)

    if ambiguous_lines:
        value = _lower_ascii(text)
        is_availability_query = (
            not infer_entities(text).get("quantities")
            and not _has_order_adjustment_terms(text)
            and not contains_any(
                value,
                ("quero", "pedido", "comprar", "adicione", "adicionar", "inclua", "incluir"),
            )
            and contains_any(value, ("tem", "possui", "vende", "disponivel"))
        )
        if is_availability_query:
            return ""
        return "\n".join(
            [
                "Para eu não adicionar produto errado, confirme qual formato e tamanho você quer.",
                "",
                *ambiguous_lines,
                "",
                "Me diga a opção e a quantidade para eu atualizar o resumo.",
            ]
        )

    return ""


def product_options_reply(text: str, produtos: list[dict] | None) -> str:
    requested = _requested_catalog_tokens(text, produtos)
    if not requested:
        return ""

    lines: list[str] = []
    for token in requested[:4]:
        options = _catalog_options_for_token(token, produtos)
        if not options:
            lines.append(f"Não encontrei {token} nas opções disponíveis.")
            continue
        lines.append(f"Para {_display_catalog_term(token)}, tenho estas opções:")
        lines.extend(_format_catalog_options_lines(options))
        lines.append("")

    if not lines:
        return ""
    lines.append("Qual formato e tamanho você quer?")
    return "\n".join(lines).strip()


def detect_unavailable_requested_products(text: str, produtos: list[dict] | None) -> list[str]:
    if not produtos:
        return []

    catalog_text = "\n".join(_product_text(row) for row in produtos)
    normalized = _lower_ascii(text)
    unavailable: list[str] = []

    # Termos comuns que podem ser confundidos com abreviacoes/codigos internos.
    # Ex.: "LAR" no codigo da tabela significa laranja, nunca limao.
    known_terms = {"limao": "limão"}
    for token, label in known_terms.items():
        if token in normalized and token not in catalog_text:
            unavailable.append(label)

    return unavailable


def unavailable_products_prompt(products: list[str]) -> str:
    lines = ["Não posso adicionar produto fora das opções disponíveis."]
    if products:
        lines += ["", "Itens que não conferem com a tabela:"]
        lines.extend(f"- {product}" for product in products[:8])
    lines += [
        "",
        "Me confirme um produto, tipo/formato e tamanho disponíveis para eu atualizar o pedido.",
    ]
    return "\n".join(lines)


def catalog_unavailable_prompt() -> str:
    return "\n".join(
        [
            "Não consegui consultar a tabela de produtos agora.",
            "",
            "Para evitar registrar um item incorreto, vou precisar confirmar o produto na tabela antes de adicionar ao pedido.",
        ]
    )


def is_full_product_list_request(text: str, classification: dict) -> bool:
    if classification.get("intent") != "product_query":
        return False

    value = _lower_ascii(text)
    if _requested_type_from_text(text) and contains_any(value, ("qual", "quais", "opcoes", "produtos", "tem", "quero", "prefiro", "comecar", "começar", "mostrar", "ver")):
        return True
    if _requested_catalog_tokens(text, [{"nome_produto": token} for token in re.findall(r"[a-z0-9]+", value)]):
        return False
    if value.strip(" .,!?\n\t") in {"produto", "produtos", "os produtos"}:
        return True

    return contains_any(
        value,
        (
            "quais tem",
            "quais voces tem",
            "quais produtos",
            "produtos tem",
            "manda os produtos",
            "mande os produtos",
            "mandar os produtos",
            "todos os produtos",
            "ver produtos",
            "lista de produtos",
            "catalogo",
            "opcoes",
            "opcoes de produto",
            "o que voce vende",
            "o que vende",
            "vende ai",
            "sabores",
            "modelos",
            "embalagens",
        ),
    )


def is_simple_greeting(text: str) -> bool:
    value = _lower_ascii(text).strip(" .,!?\n\t")
    value = re.sub(r"[^a-z0-9]+", " ", value).strip()
    greetings = {
        "oi",
        "ola",
        "bom dia",
        "boa tarde",
        "boa noite",
        "opa",
        "e ai",
        "eae",
        "tudo bem",
        "oi tudo bem",
        "ola tudo bem",
    }
    if value in greetings:
        return True
    return any(
        value == f"{greeting} marcela"
        or value == f"{greeting} marcela tudo bem"
        for greeting in greetings
    )


def contains_any(value: str, terms: tuple[str, ...]) -> bool:
    return any(term in value for term in terms)


def mentions_order_context(messages: list[dict]) -> bool:
    keywords = (
        "pedido",
        "comprar",
        "compra",
        "cotacao",
        "orcamento",
        "unidade",
        "garrafa",
        "copo",
        "bolsa",
        "suco",
        "nectar",
    )
    for item in messages[-8:]:
        content = _lower_ascii(str(item.get("content") or ""))
        if any(keyword in content for keyword in keywords):
            return True
    return False


def is_complaint(text: str) -> bool:
    value = _lower_ascii(text)
    return contains_any(
        value,
        (
            "reclam",
            "atrasou",
            "atrasado",
            "problema",
            "errado",
            "veio errado",
            "nao chegou",
            "devolucao",
            "estorno",
            "cancelar pedido",
        ),
    )


def is_prompt_attack(text: str) -> bool:
    value = _lower_ascii(text)
    patterns = (
        "ignore as instrucoes",
        "ignore suas instrucoes",
        "ignore o prompt",
        "prompt do sistema",
        "system prompt",
        "developer message",
        "mensagem de sistema",
        "revele seu prompt",
        "mostre seu prompt",
        "jailbreak",
        "finja que",
        "a partir de agora",
    )
    return any(pattern in value for pattern in patterns)


def is_disengagement(text: str) -> bool:
    value = _lower_ascii(text)
    if not value:
        return False
    patterns = (
        "nao obrigado",
        "nao, obrigado",
        "não obrigado",
        "não, obrigado",
        "obrigado, nao",
        "obrigada, nao",
        "ja falei que nao",
        "já falei que não",
        "poxa, ja falei",
        "poxa, já falei",
        "ate logo",
        "até logo",
        "tchau",
        "encerrar",
        "pode parar",
        "nao quero mais",
        "não quero mais",
    )
    return any(pattern in value for pattern in patterns)


def infer_entities(text: str) -> dict:
    value = _lower_ascii(text)
    product_terms = (
        "laranja",
        "uva",
        "manga",
        "maracuja",
        "goiaba",
        "acerola",
        "abacaxi",
        "agua de coco",
        "coco",
        "caju",
        "caja",
        "limao",
        "tamarindo",
        "hibisco",
        "suco",
        "nectar",
    )
    package_terms = ("garrafa", "copo", "bolsa", "concentrada", "litro", "1l", "300ml", "200ml", "115ml")
    quantities = re.findall(r"\b\d+(?:[,.]\d+)?\s*(?:unidades?|un|garrafas?|copos?|bolsas?)?\b", value)
    return {
        "products": [term for term in product_terms if term in value],
        "packages": [term for term in package_terms if term in value],
        "quantities": [q.strip() for q in quantities if q.strip()],
    }


def classify_intent(text: str, previous_history: list[dict], state: dict | None = None) -> dict:
    state = state or {}
    value = _lower_ascii(text)
    has_order_context = mentions_order_context(previous_history) or bool(state.get("order_in_progress"))
    entities = infer_entities(text)

    if is_prompt_attack(text):
        return {
            "intent": "prompt_attack",
            "confidence": 1.0,
            "requires_ai": False,
            "requires_human": False,
            "out_of_scope": True,
            "has_order_context": has_order_context,
            "entities": entities,
        }
    if is_disengagement(text):
        return {
            "intent": "disengage",
            "confidence": 0.95,
            "requires_ai": False,
            "requires_human": False,
            "out_of_scope": False,
            "has_order_context": has_order_context,
            "entities": entities,
        }
    if is_out_of_scope(text):
        return {
            "intent": "out_of_scope",
            "confidence": 0.95,
            "requires_ai": False,
            "requires_human": False,
            "out_of_scope": True,
            "has_order_context": has_order_context,
            "entities": entities,
        }
    if is_complaint(text):
        return {
            "intent": "complaint",
            "confidence": 0.9,
            "requires_ai": False,
            "requires_human": True,
            "out_of_scope": False,
            "has_order_context": has_order_context,
            "entities": entities,
        }
    if contains_any(value, ("ultimo pedido", "ultima vez", "comprei antes", "pedi antes", "historico")):
        intent = "history_query"
    elif contains_any(value, ("repetir", "repete", "igual ao ultimo", "mesmo pedido")):
        intent = "repeat_order"
    elif contains_any(value, ("entrega", "entregar", "prazo", "chega hoje", "chega amanha")):
        intent = "delivery_query"
    elif contains_any(value, ("que horas", "hora atual", "horario", "horário", "que dia e hoje", "que dia eh hoje", "data de hoje")):
        intent = "time_query"
    elif contains_any(value, ("preco", "valor", "quanto custa", "quanto esta", "tabela")):
        intent = "price_query"
    elif contains_any(value, ("quero fazer um pedido", "fazer pedido", "fzer um pedid", "fzer pedido", "fzr pedido", "montar pedido", "comprar", "pedido", "pedid")):
        intent = "order_request"
    elif state.get("order_in_progress") and contains_any(value, ("tira", "remove", "coloca", "inclui", "mais", "menos", "troca", "altera")):
        intent = "order_adjustment"
    elif entities["packages"] and contains_any(value, ("comecar", "começar", "ver", "mostrar", "opcoes", "opções", "prefiro", "quero")):
        intent = "product_query"
    elif (
        entities["products"]
        or (entities["packages"] and contains_any(value, ("qual", "quais", "opcoes", "opcoes", "produtos")))
        or contains_any(value, ("produto", "produtos", "quais tem", "quais voces tem", "opcoes", "sabores", "modelos", "embalagens", "o que voce vende", "o que vende", "vende ai", "vende"))
    ):
        intent = "product_query"
    elif is_simple_greeting(text) or (len(value) <= 40 and contains_any(value, ("fala", "e ai", "e aí"))):
        intent = "greeting"
    else:
        intent = "commercial_unknown"

    return {
        "intent": intent,
        "confidence": 0.75,
        "requires_ai": True,
        "requires_human": False,
        "out_of_scope": False,
        "has_order_context": has_order_context,
        "entities": entities,
    }


def is_out_of_scope(text: str) -> bool:
    value = _lower_ascii(text)
    commercial_terms = (
        "pedido",
        "comprar",
        "preco",
        "valor",
        "produto",
        "suco",
        "nectar",
        "garrafa",
        "copo",
        "bolsa",
        "entrega",
        "representante",
        "vende",
        "vender",
        "vendem",
    )
    if any(term in value for term in commercial_terms):
        return False

    if re.search(r"\b(que|qual)\b.{0,16}\b(?:dia|d\s*i\s*a)\b.{0,24}\bhoje\b", value):
        return False

    out_patterns = (
        "quem e o presidente",
        "presidente do brasil",
        "previsao do tempo",
        "resultado do jogo",
        "cotacao do dolar",
        "me conte uma piada",
        "receita de",
        "programa em python",
        "codigo em",
        "noticia",
    )
    return any(pattern in value for pattern in out_patterns)


def scoped_redirect_reply(has_order_context: bool = False) -> str:
    if has_order_context:
        return "Esse assunto foge um pouco do que eu consigo cuidar por aqui. Sobre a Sucos SPRES, quer seguir com o pedido que a gente estava montando?"
    return "Esse assunto foge um pouco do atendimento da Sucos SPRES. Posso te ajudar com produtos, preços ou montar um pedido."


def direct_reply_for_intent(classification: dict) -> str:
    intent = classification.get("intent")
    has_order_context = bool(classification.get("has_order_context"))
    if intent == "prompt_attack":
        return scoped_redirect_reply(has_order_context)
    if intent == "complaint":
        return "Entendo. Vou te conectar com um atendente agora para resolver isso direto."
    return ""


def normalize_customer_facing_ptbr(text: str) -> str:
    """Corrige termos comuns sem acento antes de enviar/salvar resposta ao cliente."""
    if not text:
        return ""

    replacements = [
        (r"\bNao\b", "Não"),
        (r"\bnao\b", "não"),
        (r"\bVoce\b", "Você"),
        (r"\bvoce\b", "você"),
        (r"\bVoces\b", "Vocês"),
        (r"\bvoces\b", "vocês"),
        (r"\bopcao\b", "opção"),
        (r"\bopcoes\b", "opções"),
        (r"\bpreco\b", "preço"),
        (r"\bprecos\b", "preços"),
        (r"\bcatalogo\b", "catálogo"),
        (r"\bdisponivel\b", "disponível"),
        (r"\bdisponiveis\b", "disponíveis"),
        (r"\bAlem\b", "Além"),
        (r"\balem\b", "além"),
        (r"\btambem\b", "também"),
        (r"\bSo\b", "Só"),
        (r"\bso\b", "só"),
        (r"\bconfirmacao\b", "confirmação"),
        (r"\baprovacao\b", "aprovação"),
        (r"\brevisao\b", "revisão"),
        (r"\bderivacao\b", "derivação"),
        (r"\bproximo\b", "próximo"),
        (r"\bhistorico\b", "histórico"),
        (r"\bduvida\b", "dúvida"),
        (r"\bduvidas\b", "dúvidas"),
        (r"\bobservacao\b", "observação"),
        (r"\bate\b", "até"),
        (r"\bestao\b", "estão"),
        (r"\bsao\b", "são"),
        (r"\butil\b", "útil"),
    ]
    normalized = text
    for pattern, replacement in replacements:
        normalized = re.sub(pattern, replacement, normalized)
    return normalized


def is_final_order_confirmation(text: str) -> bool:
    value = _lower_ascii(text).strip(" .,!?\n\t")
    if not value:
        return False

    value_for_adjustment = re.sub(r"\b(?:nada|sem)\s+mais\b", "", value)
    adjustment_terms = (
        "inclui",
        "incluir",
        "adiciona",
        "adicionar",
        "coloca",
        "mais",
        "faltou",
        "tira",
        "remove",
        "troca",
        "altera",
        "muda",
        "veja",
    )
    question_terms = (
        "?",
        "qual",
        "quais",
        "tamanho",
        "tamanhos",
        "preco",
        "valor",
        "como assim",
    )
    if contains_any(value_for_adjustment, adjustment_terms) or contains_any(value, question_terms):
        return False

    short_confirmations = {
        "s",
        "sim",
        "ok",
        "okay",
        "blz",
        "beleza",
        "isso",
        "isso mesmo",
        "certo",
        "certinho",
        "confirmado",
        "pode",
        "pode sim",
        "manda",
        "manda ai",
        "fecha",
        "fechado",
        "aprovado",
    }
    if value in short_confirmations:
        return True

    confirmation_terms = (
        "esta certo",
        "ta certo",
        "tudo certo",
        "pode registrar",
        "pode enviar",
        "pode mandar",
        "pode finalizar",
        "pode fechar",
        "confirmo",
        "confirmado",
        "fechado",
        "isso mesmo",
        "pode sim",
        "sim pode",
        "sim, pode",
        "sim por favor",
        "pode ser",
    )
    return contains_any(value, confirmation_terms)


def _format_brl(value: Any) -> str:
    try:
        return f"R$ {float(value):.2f}".replace(".", ",")
    except (TypeError, ValueError):
        return ""


def _format_catalog_price(value: Any) -> str:
    formatted = _format_brl(value)
    return formatted or "-"


def product_catalog_type_prompt() -> str:
    return (
        "Tenho opções em copo, garrafa, bolsa e bolsa concentrada. "
        "Qual formato você quer ver primeiro?"
    )


def _catalog_type_reply(text: str, produtos: list[dict] | None) -> str:
    requested_type = _requested_type_from_text(text)
    if not requested_type:
        return product_catalog_type_prompt()
    if not produtos:
        return "Não encontrei as opções disponíveis agora. Posso deixar para o representante validar?"

    rows = [
        row for row in produtos
        if _lower_ascii(_catalog_product_type(row)) == _lower_ascii(requested_type)
    ]
    if not rows:
        return f"Não encontrei opções de {requested_type} disponíveis agora. Quer ver copo, garrafa, bolsa ou bolsa concentrada?"

    grouped: dict[str, list[dict]] = {}
    for item in rows:
        label = _public_product_label(item)
        if not label:
            continue
        grouped.setdefault(label, []).append(item)

    lines = [f"Estas são as opções de {requested_type}:", ""]
    for label in sorted(grouped):
        options = _format_catalog_options(grouped[label])
        if options:
            lines.append(f"- {label}: {options}")
    lines += ["", "Qual produto e tamanho você quer?"]
    return "\n".join(lines)


def full_product_catalog_reply(produtos: list[dict] | None, codigo_tabela: str | None = None, text: str = "") -> str:
    if not produtos:
        return "Não encontrei a lista de produtos disponível aqui agora. Posso deixar para o representante validar?"

    requested_type = _requested_type_from_text(text)
    if requested_type:
        return _catalog_type_reply(text, produtos)

    grouped: dict[str, list[dict]] = {}
    for item in produtos:
        label = _public_product_label(item)
        if not label:
            continue
        grouped.setdefault(label, []).append(item)

    lines = ["Estas são algumas opções disponíveis na tabela:", ""]
    for label in sorted(grouped)[:14]:
        options = _format_catalog_options(grouped[label])
        if options:
            lines.append(f"- {label}: {options}")

    lines += [
        "",
        "Me diga o produto, formato e quantidade para eu montar o pedido.",
    ]
    return "\n".join(lines)


def order_confirmation_prompt(itens: list[dict] | None = None) -> str:
    lines = ["Ainda não registrei o pedido.", "", "Só para confirmar, ficou assim:"]
    total = 0.0
    has_subtotal = False
    for item in itens or []:
        nome = _item_value(item, "nome") or _item_value(item, "produto") or "Item"
        tipo = _item_value(item, "tipo", "formato", "embalagem")
        tamanho = _item_value(item, "tamanho", "derivacao", "variacao", "volume")
        quantidade = _item_value(item, "quantidade")
        unidade = _item_value(item, "unidade")
        preco_unitario = _format_brl(item.get("preco_unitario"))
        subtotal_value = item.get("subtotal")
        subtotal = _format_brl(subtotal_value)
        try:
            total += float(subtotal_value)
            has_subtotal = True
        except (TypeError, ValueError):
            pass

        parts = []
        if tipo:
            parts.append(f"tipo {tipo}")
        if tamanho:
            parts.append(f"tamanho {tamanho}")
        if quantidade:
            parts.append(f"quantidade {quantidade}")
        if unidade:
            parts.append(f"unidade {unidade}")
        if preco_unitario:
            parts.append(f"unit. {preco_unitario}")
        if subtotal:
            parts.append(f"subtotal {subtotal}")
        if parts:
            lines.append(f"- *{nome}*: {' | '.join(parts)}")
        else:
            lines.append(f"- *{nome}*")
    if has_subtotal:
        lines += ["", f"Total do pedido: *{_format_brl(total)}*"]
    lines += [
        "",
        "Se estiver tudo certo, me confirma por aqui que eu envio para aprovação do representante.",
    ]
    return "\n".join(lines)


def _item_value(item: dict, *keys: str) -> str:
    for key in keys:
        value = item.get(key)
        if value is not None and normalize_text(value):
            return normalize_text(value)
    return ""


def _customer_display_name(customer: dict | None) -> str:
    if not customer:
        return ""
    for key in ("nome", "fantasia", "razao_social", "customer_name"):
        value = normalize_text(customer.get(key))
        if value:
            return value
    return normalize_text(customer.get("cod_cli") or customer.get("cpf_cnpj") or customer.get("documento"))


def _has_order_adjustment_terms(text: str) -> bool:
    value = _lower_ascii(text)
    return contains_any(
        value,
        (
            "troca",
            "troque",
            "altera",
            "alterar",
            "muda",
            "mude",
            "corrige",
            "corrigir",
            "quantidade",
            "coloca",
            "inclui",
            "incluir",
            "adiciona",
            "adicione",
            "adicionar",
            "mais",
            "menos",
            "tira",
            "remove",
            "remover",
        ),
    )


def _wants_new_order(text: str) -> bool:
    value = _lower_ascii(text)
    return contains_any(
        value,
        (
            "novo pedido",
            "fazer outro pedido",
            "lancar outro pedido",
            "lançar outro pedido",
            "abrir outro pedido",
            "criar outro pedido",
            "mais um pedido",
            "outro pedido",
        ),
    )


def _mentions_repeat_previous_order(text: str) -> bool:
    value = _lower_ascii(text)
    return contains_any(
        value,
        (
            "mesmo pedido anterior",
            "mesmo pedido de antes",
            "pedido anterior",
            "ultimo pedido",
            "último pedido",
            "repetir",
            "repete",
            "igual ao ultimo",
            "igual ao último",
        ),
    )


def _has_product_type(text: str) -> bool:
    value = _lower_ascii(text)
    return contains_any(value, ("copo", "garrafa", "bolsa", "concentrada", "galao", "galão"))


def _has_product_size(text: str) -> bool:
    value = _lower_ascii(text)
    return bool(
        re.search(r"\b(?:115|200|300|900)\s*(?:ml)?\b", value)
        or re.search(r"\b(?:1\s*,?\s*7|1l7)\s*l?\b", value)
        or re.search(r"\b(?:05|5)\s*l\b", value)
    )


def _order_item_label(item: dict) -> str:
    explicit = _item_value(item, "nome")
    if explicit:
        return explicit

    produto = _item_value(item, "produto", "desPro")
    tipo = _item_value(item, "tipo", "formato", "embalagem")
    tamanho = _item_value(item, "tamanho", "derivacao", "variacao", "volume")
    return " ".join(part for part in (tipo, produto, tamanho) if part).strip()


def _meaningful_user_tokens(text: str) -> list[str]:
    value = _lower_ascii(text)
    stop = {
        "mantenha",
        "todos",
        "so",
        "só",
        "troque",
        "troca",
        "quantidade",
        "para",
        "unidade",
        "unidades",
        "pedido",
        "produto",
        "produtos",
        "coloca",
        "inclui",
        "adiciona",
        "altera",
        "muda",
        "mais",
        "menos",
        "de",
        "da",
        "do",
        "das",
        "dos",
        "a",
        "o",
        "e",
    }
    tokens = re.findall(r"[a-z0-9]+", value)
    return [token for token in tokens if len(token) >= 4 and token not in stop and not token.isdigit()]


def _matching_open_order_items(text: str, open_review_order: dict | None) -> list[dict]:
    items = (open_review_order or {}).get("itens_json") or []
    if not isinstance(items, list):
        return []

    tokens = _meaningful_user_tokens(text)
    if not tokens:
        return []

    matches: list[dict] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        label = _lower_ascii(_order_item_label(item))
        if label and any(token in label for token in tokens):
            matches.append(item)
    return matches


def product_specifics_guard_prompt(text: str, open_review_order: dict | None) -> str:
    if _wants_new_order(text) or _mentions_repeat_previous_order(text):
        return ""
    if not _has_order_adjustment_terms(text) and not infer_entities(text).get("quantities"):
        return ""
    if _has_product_type(text) and _has_product_size(text):
        return ""

    matches = _matching_open_order_items(text, open_review_order)
    if len(matches) > 1:
        lines = [
            "Para eu não alterar o item errado, me confirma qual deles você quer ajustar:",
            "",
        ]
        for item in matches[:8]:
            label = _order_item_label(item) or "Item"
            qtd = _item_value(item, "quantidade", "qtdPed")
            unidade = _item_value(item, "unidade", "uniMed")
            suffix = f" - atual: {' '.join(part for part in (qtd, unidade) if part)}" if qtd or unidade else ""
            lines.append(f"- {label}{suffix}")
        lines += [
            "",
            "Me diga o tipo/formato e o tamanho, por exemplo: garrafa laranja 900ml ou copo laranja 200ml.",
        ]
        return "\n".join(lines)

    has_product = bool(infer_entities(text).get("products")) or bool(_meaningful_user_tokens(text))
    if has_product and (not _has_product_type(text) or not _has_product_size(text)):
        missing = []
        if not _has_product_type(text):
            missing.append("tipo/formato")
        if not _has_product_size(text):
            missing.append("tamanho")
        return (
            "Para eu montar o pedido certo, preciso confirmar "
            f"{' e '.join(missing)} antes de adicionar ou alterar esse produto. "
            "Você quer copo, garrafa, bolsa ou bolsa concentrada? E qual tamanho?"
        )

    return ""


def _missing_order_fields(itens: list[dict] | None) -> list[dict]:
    missing: list[dict] = []
    for index, item in enumerate(itens or [], start=1):
        if not isinstance(item, dict):
            missing.append({"item": index, "campos": ["produto", "tipo", "tamanho", "quantidade", "unidade"]})
            continue

        item_missing = []
        if not _item_value(item, "produto", "nome"):
            item_missing.append("produto")
        if not _item_value(item, "tipo", "formato", "embalagem"):
            item_missing.append("tipo")
        if not _item_value(item, "tamanho", "derivacao", "variacao", "volume"):
            item_missing.append("tamanho")
        if not _item_value(item, "quantidade"):
            item_missing.append("quantidade")
        if not _item_value(item, "unidade"):
            item_missing.append("unidade")
        if item_missing:
            missing.append({"item": index, "campos": item_missing})
    return missing


def missing_order_fields_prompt(itens: list[dict] | None) -> str:
    missing = _missing_order_fields(itens)
    lines = [
        "Ainda não consigo enviar esse pedido para aprovação porque falta confirmar alguns detalhes.",
        "",
        "Para cada item preciso de produto, formato, tamanho, quantidade e unidade.",
    ]
    if missing:
        lines.append("")
        lines.append("Preciso confirmar:")
        for entry in missing:
            fields = ", ".join(entry["campos"])
            item_index = int(entry.get("item") or 0) - 1
            item = (itens or [])[item_index] if 0 <= item_index < len(itens or []) else {}
            label = _display_item_name(item) if isinstance(item, dict) else "um dos itens"
            lines.append(f"- {label}: {fields}")
    lines += [
        "",
        "Me confirme esses dados que eu atualizo o resumo completo antes de enviar para o representante.",
    ]
    return "\n".join(lines)


def _unavailable_order_items(itens: list[dict] | None, produtos: list[dict] | None) -> list[str]:
    unavailable: list[str] = []
    for item in itens or []:
        if not isinstance(item, dict):
            continue
        if not _catalog_item_exists(item, produtos):
            label = _display_item_name(item)
            options = _catalog_options_for_item(item, produtos)
            if options:
                unavailable.append(f"{label} (opções reais: {_format_catalog_options(options)})")
            else:
                unavailable.append(label)
    return sorted(set(unavailable))


def _norm_size(value: str) -> str:
    raw = _lower_ascii(value).replace(" ", "").replace(",", ".")
    if raw in {"05l", "5l", "5.0l"}:
        return "5l"
    if raw in {"1l7", "1.7l", "17l"}:
        return "1.7l"
    match = re.fullmatch(r"(\d+)(?:ml)?", raw)
    if match:
        return f"{int(match.group(1))}ml"
    return raw


def _catalog_options_for_item(item: dict, produtos: list[dict] | None) -> list[dict]:
    if not produtos:
        return []
    text = _lower_ascii(" ".join(_item_value(item, key) for key in ("produto", "nome")))
    terms = _requested_catalog_tokens(text, produtos, require_trigger=False)
    if not terms:
        return []
    matches: list[dict] = []
    for row in produtos:
        row_tokens = _catalog_flavor_tokens(row)
        row_phrases = _catalog_public_phrases(row)
        row_text = _product_text(row)
        if any(term in row_phrases or term in row_tokens or term in row_text for term in terms):
            matches.append(row)
    return matches


def _catalog_item_exists(item: dict, produtos: list[dict] | None) -> bool:
    if not produtos:
        return True
    candidates = _catalog_options_for_item(item, produtos)
    if not candidates:
        return False

    wanted_type = _lower_ascii(_item_value(item, "tipo", "formato", "embalagem"))
    wanted_size = _norm_size(_item_value(item, "tamanho", "derivacao", "variacao", "volume"))

    for row in candidates:
        row_type = _lower_ascii(_catalog_product_type(row))
        row_size = _norm_size(_display_variation(_catalog_variation(row)))
        type_ok = not wanted_type or wanted_type in row_type or row_type in wanted_type
        size_ok = not wanted_size or wanted_size == row_size
        if type_ok and size_ok:
            return True
    return False


def _display_item_name(item: dict) -> str:
    explicit = _item_value(item, "nome")
    if explicit:
        return explicit

    produto = _item_value(item, "produto", "desPro")
    tipo = _item_value(item, "tipo", "formato", "embalagem")
    tamanho = _item_value(item, "tamanho", "derivacao", "variacao", "volume")
    parts = [part for part in (tipo, produto, tamanho) if part]
    return " ".join(parts).strip().upper() or produto or "Item"


def _normalize_order_items(itens: list[dict]) -> list[dict]:
    normalized: list[dict] = []
    for item in itens:
        if not isinstance(item, dict):
            continue
        row = {**item}
        row["nome"] = _display_item_name(row)
        normalized.append(row)
    return normalized


def _parse_brl_number(value: str) -> float | None:
    raw = normalize_text(value)
    if not raw:
        return None
    match = re.search(r"R\$\s*([\d.]+,\d{2}|\d+(?:[.,]\d+)?)", raw, flags=re.IGNORECASE)
    if match:
        raw = match.group(1)
    raw = raw.replace("R$", "").replace("*", "").replace(" ", "").replace(".", "").replace(",", ".")
    try:
        return float(raw)
    except ValueError:
        return None


def _extract_confirmed_order_items(text: str) -> list[dict]:
    items: list[dict] = []
    if not contains_any(_lower_ascii(text), ("so para confirmar", "resumo do seu pedido", "total do pedido")):
        return items

    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("-"):
            continue
        match = re.match(r"^-\s+\*{1,2}(.+?)\*{1,2}\s*:\s*(.+)$", stripped)
        if not match:
            continue
        nome = normalize_text(match.group(1))
        details = normalize_text(match.group(2))
        if not nome or not details:
            continue

        item: dict[str, Any] = {"nome": nome, "produto": nome}
        for part in [segment.strip() for segment in details.split("|")]:
            lower = _lower_ascii(part)
            if lower.startswith("tipo "):
                item["tipo"] = part[5:].strip()
            elif lower.startswith("tamanho "):
                item["tamanho"] = part[8:].strip()
            elif lower.startswith("quantidade "):
                qty = re.search(r"quantidade\s+([\d.,]+)", part, flags=re.IGNORECASE)
                item["quantidade"] = float(qty.group(1).replace(",", ".")) if qty else part[11:].strip()
            elif lower.startswith("unidade "):
                item["unidade"] = part[8:].strip()
            elif lower.startswith("unit."):
                price = _parse_brl_number(part)
                if price is not None:
                    item["preco_unitario"] = price
            elif lower.startswith("subtotal"):
                subtotal = _parse_brl_number(part)
                if subtotal is not None:
                    item["subtotal"] = subtotal

        if not item.get("tipo"):
            item["tipo"] = _selected_product_type_from_text(nome)
        if not item.get("tamanho"):
            item["tamanho"] = _requested_size_from_text(nome)
        if not item.get("quantidade"):
            qty = re.search(r"([\d.,]+)\s+(?:unidades?|copos?|garrafas?|bolsas?)", details, flags=re.IGNORECASE)
            if qty:
                item["quantidade"] = float(qty.group(1).replace(",", "."))
        if not item.get("unidade"):
            unit = re.search(r"[\d.,]+\s+(unidades?|copos?|garrafas?|bolsas?)", details, flags=re.IGNORECASE)
            item["unidade"] = unit.group(1) if unit else "unidades"

        items.append(item)
    return items


def _last_confirmed_order_items(history: list[dict]) -> list[dict]:
    for message in reversed(history):
        if message.get("role") != "assistant":
            continue
        items = _extract_confirmed_order_items(normalize_text(message.get("content")))
        if items and not _missing_order_fields(items):
            return items
    return []


def update_commercial_state(state: dict | None, classification: dict, user_text: str) -> dict:
    state = {**(state or {})}
    intent = classification.get("intent", "")
    if intent in {"order_request", "repeat_order", "order_adjustment", "price_query", "product_query"}:
        state["order_in_progress"] = True
    selected_type = _selected_product_type_from_text(user_text)
    if selected_type:
        state["selected_product_type"] = selected_type
    if intent == "disengage":
        state["order_in_progress"] = False
        state.pop("selected_product_type", None)
    if intent in {"complaint", "out_of_scope", "prompt_attack"}:
        state["order_in_progress"] = bool(state.get("order_in_progress"))
    state["last_intent"] = intent
    state["last_user_message"] = user_text
    state["last_entities"] = classification.get("entities") or {}
    state["updated_at"] = iso_z(utc_now())
    return state


def sanitize_ai_reply(reply: str, classification: dict, has_order_context: bool) -> str:
    text = normalize_text(reply)
    if not text:
        return ""
    intent = classification.get("intent")
    if intent == "prompt_attack":
        return scoped_redirect_reply(has_order_context)

    lowered = _lower_ascii(text)
    if not is_final_order_confirmation(classification.get("raw_text", "")):
        premature_register_terms = (
            "vou registrar isso",
            "vou registrar esse pedido",
            "pedido foi registrado",
            "registrado para revisao",
            "registrado para revisão",
        )
        if any(term in lowered for term in premature_register_terms):
            text = re.sub(
                r"\n*\s*(Vou registrar|Seu pedido foi registrado|Pedido registrado).*?(representante|revis[aã]o).*?(\n|$)",
                "\n",
                text,
                flags=re.IGNORECASE | re.DOTALL,
            ).strip()
            if text:
                text = f"{text}\n\nSe estiver tudo certo, me confirma por aqui que eu envio para aprovação do representante."
            else:
                text = "Se estiver tudo certo, me confirma por aqui que eu envio para aprovação do representante."
            lowered = _lower_ascii(text)

    return text

class AgentStore:
    def __init__(self) -> None:
        self.supabase_url = os.getenv("SUPABASE_URL", "").strip()
        self.supabase_key = (
            os.getenv("SUPABASE_SERVICE_ROLE_KEY")
            or os.getenv("SUPABASE_ANON_KEY")
            or ""
        ).strip()
        self.use_local = not (self.supabase_url and self.supabase_key)
        self.client = None

        if self.use_local:
            LOCAL_DATA_DIR.mkdir(parents=True, exist_ok=True)
            return

        try:
            from supabase import create_client

            self.client = create_client(self.supabase_url, self.supabase_key)
        except Exception as exc:
            logger.warning("Falha ao inicializar Supabase; usando JSON local: %s", exc)
            self.use_local = True
            LOCAL_DATA_DIR.mkdir(parents=True, exist_ok=True)

    def get_or_create_conversation(self, conversation_key: str, phone: str) -> dict:
        if self.use_local:
            return self._local_get_or_create_conversation(conversation_key, phone)

        try:
            result = (
                self.client.table(CONVERSATIONS_TABLE)
                .select("*")
                .eq("conversation_key", conversation_key)
                .limit(1)
                .execute()
            )
            rows = result.data or []
            if rows:
                return rows[0]

            now = iso_z(utc_now())
            payload = {
                "conversation_key": conversation_key,
                "phone": phone,
                "ai_paused": False,
                "created_at": now,
                "updated_at": now,
            }
            created = self.client.table(CONVERSATIONS_TABLE).insert(payload).execute()
            if created.data:
                return created.data[0]

            retry = (
                self.client.table(CONVERSATIONS_TABLE)
                .select("*")
                .eq("conversation_key", conversation_key)
                .limit(1)
                .execute()
            )
            return (retry.data or [payload])[0]
        except Exception as exc:
            logger.warning("Falha no Supabase para conversa; usando JSON local: %s", exc)
            self.use_local = True
            LOCAL_DATA_DIR.mkdir(parents=True, exist_ok=True)
            return self._local_get_or_create_conversation(conversation_key, phone)

    def _local_get_or_create_conversation(self, conversation_key: str, phone: str) -> dict:
        if self.use_local:
            rows = self._local_read(CONVERSATIONS_TABLE)
            for row in rows:
                if row.get("conversation_key") == conversation_key:
                    return row

            now = iso_z(utc_now())
            row = {
                "id": str(uuid.uuid4()),
                "conversation_key": conversation_key,
                "phone": phone,
                "ai_paused": False,
                "paused_at": None,
                "paused_until": None,
                "pause_reason": None,
                "created_at": now,
                "updated_at": now,
            }
            rows.append(row)
            self._local_write(CONVERSATIONS_TABLE, rows)
            return row
        raise RuntimeError("Estado local indisponivel")

    def update_conversation(self, conversation_id: str, updates: dict) -> dict:
        payload = {**updates, "updated_at": iso_z(utc_now())}
        if self.use_local:
            rows = self._local_read(CONVERSATIONS_TABLE)
            for index, row in enumerate(rows):
                if str(row.get("id")) == str(conversation_id):
                    rows[index] = {**row, **payload}
                    self._local_write(CONVERSATIONS_TABLE, rows)
                    return rows[index]
            return payload

        try:
            result = (
                self.client.table(CONVERSATIONS_TABLE)
                .update(payload)
                .eq("id", conversation_id)
                .execute()
            )
            return (result.data or [payload])[0]
        except Exception as exc:
            logger.warning("Falha ao atualizar Supabase; usando JSON local: %s", exc)
            self.use_local = True
            return self.update_conversation(conversation_id, updates)

    def add_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        payload_json: dict | None = None,
    ) -> dict:
        now = iso_z(utc_now())
        payload = {
            "id": str(uuid.uuid4()),
            "conversation_id": conversation_id,
            "role": role,
            "content": content,
            "payload_json": payload_json or {},
            "created_at": now,
        }

        if self.use_local:
            self._local_append(MESSAGES_TABLE, payload)
            return payload

        try:
            result = self.client.table(MESSAGES_TABLE).insert(payload).execute()
            return (result.data or [payload])[0]
        except Exception as exc:
            logger.warning("Falha ao gravar mensagem no Supabase; usando JSON local: %s", exc)
            self.use_local = True
            self._local_append(MESSAGES_TABLE, payload)
            return payload

    def get_module_context(self, phone: str) -> dict | None:
        """
        Busca o contexto de módulo para um telefone consultando message_events.
        Retorna dict com module, customer_name, top_items, etc. — ou None se não houver.
        Janela de busca: últimas 72 horas (disparo recente que gerou esta conversa).
        """
        if self.use_local:
            return None

        try:
            cutoff = iso_z(utc_now() - timedelta(hours=72))
            result = (
                self.client.table("message_events")
                .select("entity_id, payload_json, created_at")
                .eq("to_number", phone)
                .eq("direction", "outbound")
                .gte("created_at", cutoff)
                .order("created_at", desc=True)
                .limit(1)
                .execute()
            )
            rows = result.data or []
            if not rows:
                return None

            row = rows[0]
            payload = row.get("payload_json") or {}
            funil = payload.get("funil")
            if funil not in ("recorrencia", "ativacao"):
                return None

            entity_id = row.get("entity_id")
            target_data: dict = {}
            if entity_id:
                t_res = (
                    self.client.table("recurrence_targets")
                    .select(
                        "customer_name, top_items_json, last_3_orders_json, "
                        "predicted_next_order_date, ai_reasoning"
                    )
                    .eq("id", entity_id)
                    .limit(1)
                    .execute()
                )
                target_data = (t_res.data or [{}])[0]

            tipo = ""
            mensagem_inicial = payload.get("mensagem", "")
            pedido_sugerido = []
            raw_reasoning = target_data.get("ai_reasoning")
            if raw_reasoning:
                try:
                    reasoning = json.loads(raw_reasoning)
                    tipo = reasoning.get("tipo_abordagem", "")
                    mensagem_inicial = reasoning.get("mensagem") or mensagem_inicial
                    pedido_sugerido = reasoning.get("pedido_sugerido") or []
                except (json.JSONDecodeError, TypeError):
                    pass

            return {
                "module": funil,
                "customer_name": target_data.get("customer_name"),
                "top_items": target_data.get("top_items_json") or [],
                "last_3_orders": target_data.get("last_3_orders_json") or [],
                "pedido_sugerido": pedido_sugerido,
                "predicted_next_order_date": target_data.get("predicted_next_order_date"),
                "tipo_abordagem": tipo,
                "ai_mensagem_inicial": mensagem_inicial,
            }
        except Exception as exc:
            logger.warning("Falha ao buscar contexto de módulo para %s: %s", phone, exc)
            return None

    def save_order_for_review(
        self,
        phone: str,
        conversation_id: str | None,
        itens: list[dict],
        observacoes: str,
        customer_name: str | None,
        mensagem_cliente: str,
        acao: str = "editar",
        protocolo: str | None = None,
    ) -> dict:
        missing_fields = _missing_order_fields(itens)
        if missing_fields:
            return {"id": None, "action": "blocked_missing_fields", "missing_fields": missing_fields}

        itens = _normalize_order_items(itens)
        resolved_customer_name = normalize_text(customer_name) or _customer_display_name(self.get_customer_for_phone(phone))
        order_id = str(uuid.uuid4())
        now = iso_z(utc_now())
        protocolo_interno = self._generate_order_protocol(now)
        payload = {
            "id": order_id,
            "protocolo": protocolo_interno,
            "origem": "ia_whatsapp",
            "cliente_telefone": phone,
            "cliente_nome": resolved_customer_name or None,
            "conversation_id": conversation_id,
            "itens_json": itens,
            "observacoes": observacoes or "",
            "mensagem_cliente": mensagem_cliente or "",
            "status": "pendente",
            "created_at": now,
            "updated_at": now,
        }
        should_create = normalize_text(acao).lower() in {"criar", "novo", "new", "create"}
        target_protocol = normalize_text(protocolo).upper()

        if self.use_local:
            rows = self._local_read("pedidos_revisao")
            if not should_create:
                candidates = []
                for index, row in enumerate(rows):
                    if row.get("status") not in {"pendente", "em_revisao"}:
                        continue
                    same_protocol = target_protocol and normalize_text(row.get("protocolo")).upper() == target_protocol
                    same_conversation = conversation_id and row.get("conversation_id") == conversation_id
                    same_phone = phone and row.get("cliente_telefone") == phone
                    if same_protocol or (not target_protocol and (same_conversation or same_phone)):
                        candidates.append((index, row))
                if not target_protocol and len(candidates) > 1:
                    return {
                        "id": None,
                        "action": "blocked_ambiguous_order",
                        "open_orders": [row for _, row in candidates[:5]],
                    }
                if candidates:
                    index, row = candidates[0]
                    updated = {
                        **row,
                        "protocolo": row.get("protocolo") or self._generate_order_protocol(str(row.get("created_at") or now)),
                        "origem": row.get("origem") or "ia_whatsapp",
                        "cliente_nome": resolved_customer_name or row.get("cliente_nome"),
                        "itens_json": itens,
                        "observacoes": observacoes or "",
                        "mensagem_cliente": mensagem_cliente or "",
                        "status": "pendente",
                        "revisado_em": None,
                        "updated_at": now,
                    }
                    rows[index] = updated
                    self._local_write("pedidos_revisao", rows)
                    return {"id": row.get("id", order_id), "protocolo": updated["protocolo"], "action": "updated"}
            self._local_append("pedidos_revisao", payload)
            return {"id": order_id, "protocolo": protocolo_interno, "action": "created"}

        try:
            existing_rows = []
            if not should_create:
                if target_protocol:
                    existing = (
                        self.client.table("pedidos_revisao")
                        .select("id,protocolo,status,created_at")
                        .in_("status", ["pendente", "em_revisao"])
                        .eq("protocolo", target_protocol)
                        .limit(1)
                        .execute()
                    )
                    existing_rows = existing.data or []
                else:
                    rows_by_id: dict[str, dict] = {}
                    lookup_filters = []
                    if conversation_id:
                        lookup_filters.append(("conversation_id", conversation_id))
                    if phone:
                        lookup_filters.append(("cliente_telefone", phone))

                    for field, value in lookup_filters:
                        existing = (
                            self.client.table("pedidos_revisao")
                            .select("id,protocolo,status,created_at")
                            .in_("status", ["pendente", "em_revisao"])
                            .eq(field, value)
                            .order("updated_at", desc=True)
                            .limit(5)
                            .execute()
                        )
                        for row in existing.data or []:
                            rows_by_id[str(row.get("id"))] = row
                    existing_rows = list(rows_by_id.values())
                    existing_rows.sort(key=lambda row: str(row.get("created_at") or ""), reverse=True)
                    if len(existing_rows) > 1:
                        return {"id": None, "action": "blocked_ambiguous_order", "open_orders": existing_rows[:5]}

            if existing_rows:
                existing_id = existing_rows[0]["id"]
                update_payload = {
                    "itens_json": itens,
                    "observacoes": observacoes or "",
                    "mensagem_cliente": mensagem_cliente or "",
                    "status": "pendente",
                    "revisado_em": None,
                    "updated_at": now,
                }
                if resolved_customer_name:
                    update_payload["cliente_nome"] = resolved_customer_name
                result = (
                    self.client.table("pedidos_revisao")
                    .update(update_payload)
                    .eq("id", existing_id)
                    .execute()
                )
                row = (result.data or [{"id": existing_id, "protocolo": existing_rows[0].get("protocolo")}])[0]
                return {"id": row.get("id", existing_id), "protocolo": row.get("protocolo"), "action": "updated"}

            result = self.client.table("pedidos_revisao").insert(payload).execute()
            row = (result.data or [payload])[0]
            return {"id": row.get("id", order_id), "protocolo": row.get("protocolo", protocolo_interno), "action": "created"}
        except Exception as exc:
            logger.warning("Falha ao salvar pedido_revisao; usando local: %s", exc)
            self.use_local = True
            self._local_append("pedidos_revisao", payload)
            return {"id": order_id, "protocolo": protocolo_interno, "action": "created"}

    def _generate_order_protocol(self, created_at: str | None = None) -> str:
        parsed = parse_dt(created_at)
        local_date = (parsed.astimezone(LOCAL_TIMEZONE) if parsed else local_now()).strftime("%y%m%d")
        return f"SP-{local_date}-{uuid.uuid4().hex[:6].upper()}"

    def get_open_order_for_review(self, phone: str, conversation_id: str | None = None) -> dict | None:
        matches = self.get_open_orders_for_review(phone, conversation_id, limit=1)
        return matches[0] if matches else None

    def get_open_orders_for_review(self, phone: str, conversation_id: str | None = None, limit: int = 5) -> list[dict]:
        editable_statuses = {"pendente", "em_revisao"}
        safe_limit = max(1, min(limit, 10))
        if self.use_local:
            rows = self._local_read("pedidos_revisao")
            matches = [
                row for row in rows
                if row.get("status") in editable_statuses
                and (
                    (conversation_id and row.get("conversation_id") == conversation_id)
                    or (phone and row.get("cliente_telefone") == phone)
                )
            ]
            matches.sort(key=lambda row: str(row.get("updated_at") or row.get("created_at") or ""), reverse=True)
            return matches[:safe_limit]

        try:
            rows_by_id: dict[str, dict] = {}
            lookup_filters = []
            if conversation_id:
                lookup_filters.append(("conversation_id", conversation_id))
            if phone:
                lookup_filters.append(("cliente_telefone", phone))

            for field, value in lookup_filters:
                result = (
                    self.client.table("pedidos_revisao")
                    .select("id,protocolo,origem,status,itens_json,observacoes,created_at,updated_at")
                    .in_("status", list(editable_statuses))
                    .eq(field, value)
                    .order("updated_at", desc=True)
                    .limit(safe_limit)
                    .execute()
                )
                for row in result.data or []:
                    rows_by_id[str(row.get("id"))] = row
            rows = list(rows_by_id.values())
            rows.sort(key=lambda row: str(row.get("updated_at") or row.get("created_at") or ""), reverse=True)
            return rows[:safe_limit]
        except Exception as exc:
            logger.warning("Falha ao buscar pedidos em revisao abertos: %s", exc)
            return []

    def recent_messages(self, conversation_id: str, limit: int = CONTEXT_MESSAGE_LIMIT) -> list[dict]:
        safe_limit = max(1, min(limit, 50))
        if self.use_local:
            rows = [
                row
                for row in self._local_read(MESSAGES_TABLE)
                if str(row.get("conversation_id")) == str(conversation_id)
            ]
            rows.sort(key=lambda row: str(row.get("created_at") or ""), reverse=True)
            return list(reversed(rows[:safe_limit]))

        try:
            result = (
                self.client.table(MESSAGES_TABLE)
                .select("role, content, created_at")
                .eq("conversation_id", conversation_id)
                .order("created_at", desc=True)
                .limit(safe_limit)
                .execute()
            )
            return list(reversed(result.data or []))
        except Exception as exc:
            logger.warning("Falha ao buscar historico no Supabase; usando JSON local: %s", exc)
            self.use_local = True
            return self.recent_messages(conversation_id, safe_limit)

    def has_newer_user_message(self, conversation_id: str, created_at: str) -> bool:
        if self.use_local:
            rows = [
                row
                for row in self._local_read(MESSAGES_TABLE)
                if str(row.get("conversation_id")) == str(conversation_id)
                and row.get("role") == "user"
                and str(row.get("created_at") or "") > str(created_at or "")
            ]
            return bool(rows)

        try:
            result = (
                self.client.table(MESSAGES_TABLE)
                .select("id")
                .eq("conversation_id", conversation_id)
                .eq("role", "user")
                .gt("created_at", created_at)
                .limit(1)
                .execute()
            )
            return bool(result.data)
        except Exception as exc:
            logger.warning("Falha ao verificar buffer de mensagens; prosseguindo: %s", exc)
            return False

    def _state_key(self, conversation_id: str) -> str:
        return f"ai_state__{conversation_id}"

    def get_conversation_state(self, conversation_id: str) -> dict:
        key = self._state_key(conversation_id)
        if self.use_local:
            rows = self._local_read("conversation_state")
            for row in rows:
                if row.get("key") == key:
                    value = row.get("value")
                    return value if isinstance(value, dict) else {}
            return {}

        try:
            result = (
                self.client.table(STATE_TABLE)
                .select("value")
                .eq("key", key)
                .limit(1)
                .execute()
            )
            rows = result.data or []
            value = rows[0].get("value") if rows else {}
            return value if isinstance(value, dict) else {}
        except Exception as exc:
            logger.warning("Falha ao ler estado da conversa; usando vazio: %s", exc)
            return {}

    def save_conversation_state(self, conversation_id: str, state: dict) -> None:
        key = self._state_key(conversation_id)
        if self.use_local:
            rows = self._local_read("conversation_state")
            payload = {"key": key, "value": state, "updated_at": iso_z(utc_now())}
            for index, row in enumerate(rows):
                if row.get("key") == key:
                    rows[index] = payload
                    self._local_write("conversation_state", rows)
                    return
            rows.append(payload)
            self._local_write("conversation_state", rows)
            return

        try:
            self.client.table(STATE_TABLE).upsert(
                {"key": key, "value": state, "updated_at": iso_z(utc_now())}
            ).execute()
        except Exception as exc:
            logger.warning("Falha ao salvar estado da conversa: %s", exc)

    def get_agent_runtime_settings(self) -> dict:
        defaults = {"message_buffer_seconds": DEFAULT_MESSAGE_BUFFER_SECONDS}
        if self.use_local:
            rows = self._local_read("agent_runtime_settings")
            values = {row.get("key"): row.get("value") for row in rows if isinstance(row, dict)}
            return {
                "message_buffer_seconds": _safe_float_setting(
                    values.get(BUFFER_SETTING_KEY),
                    defaults["message_buffer_seconds"],
                )
            }

        try:
            result = (
                self.client.table(STATE_TABLE)
                .select("key,value")
                .eq("key", BUFFER_SETTING_KEY)
                .limit(1)
                .execute()
            )
            rows = result.data or []
            value = rows[0].get("value") if rows else defaults["message_buffer_seconds"]
            return {
                "message_buffer_seconds": _safe_float_setting(value, defaults["message_buffer_seconds"])
            }
        except Exception as exc:
            logger.warning("Falha ao ler configuracoes runtime do agente; usando padrao: %s", exc)
            return defaults

    def _local_file(self, table: str) -> Path:
        LOCAL_DATA_DIR.mkdir(parents=True, exist_ok=True)
        return LOCAL_DATA_DIR / f"{table}.json"

    def _local_read(self, table: str) -> list[dict]:
        path = self._local_file(table)
        if not path.exists():
            return []
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return []
        return data if isinstance(data, list) else []

    def _local_write(self, table: str, rows: list[dict]) -> None:
        self._local_file(table).write_text(
            json.dumps(rows, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _local_append(self, table: str, row: dict) -> None:
        rows = self._local_read(table)
        rows.append(row)
        self._local_write(table, rows)

    def get_produtos(self) -> list[dict]:
        """Retorna catálogo de produtos ativos. Vazio se Supabase indisponível."""
        if self.use_local:
            return []
        try:
            result = (
                self.client.table("produtos")
                .select("cod_produto, nome, derivacao, preco_base, preco_inst_299")
                .eq("ativo", True)
                .order("nome")
                .execute()
            )
            return result.data or []
        except Exception as exc:
            logger.warning("Falha ao buscar produtos: %s", exc)
            return []

    def get_tabela_preco_for_phone(self, phone: str) -> str | None:
        """Retorna o codigo_tabela de preço vinculado ao telefone do cliente."""
        if self.use_local or not phone:
            return None
        try:
            result = (
                self.client.table("clic_clientes")
                .select("tabela_preco_codigo")
                .eq("telefone", phone)
                .limit(1)
                .execute()
            )
            rows = result.data or []
            return rows[0]["tabela_preco_codigo"] if rows else None
        except Exception as exc:
            logger.warning("Falha ao buscar tabela de preço para %s: %s", phone, exc)
            return None

    def get_customer_for_phone(self, phone: str) -> dict | None:
        """Retorna o cliente vinculado ao telefone normalizado, quando existir."""
        if self.use_local or not phone:
            return None

        candidates = {phone}
        if phone.startswith("55") and len(phone) > 11:
            candidates.add(phone[2:])
        elif len(phone) in (10, 11):
            candidates.add(f"55{phone}")

        try:
            result = (
                self.client.table("clic_clientes")
                .select("*")
                .in_("telefone", list(candidates))
                .limit(1)
                .execute()
            )
            rows = result.data or []
            return rows[0] if rows else None
        except Exception as exc:
            logger.warning("Falha ao buscar cliente para %s: %s", phone, exc)
            return None

    def get_produtos_tabela(self, codigo_tabela: str) -> list[dict]:
        """Retorna itens da tabela de preço do Senior ERP para o cliente."""
        if self.use_local or not codigo_tabela:
            return []
        try:
            result = (
                self.client.table("tabelas_preco_itens")
                .select("cod_produto, nome_produto, variacao, quantidade_minima, preco, desconto")
                .eq("codigo_tabela", codigo_tabela)
                .order("cod_produto")
                .execute()
            )
            return [
                row
                for row in (result.data or [])
                if str(row.get("nome_produto") or "").strip()
            ]
        except Exception as exc:
            logger.warning("Falha ao buscar itens da tabela %s: %s", codigo_tabela, exc)
            return []

    def get_recent_orders_for_customer(self, customer: dict | None, limit: int = 4) -> list[dict]:
        """Busca os ultimos pedidos reais do cliente em rep_order_base."""
        if self.use_local or not customer:
            return []

        cod_cli = customer.get("cod_cli") or customer.get("cpf_cnpj") or customer.get("external_id")
        if not cod_cli:
            return []

        try:
            result = (
                self.client.table("rep_order_base")
                .select("num_ped, dat_emi, sit_ped, order_total_value, items_json")
                .eq("cod_cli", int(cod_cli))
                .order("dat_emi", desc=True)
                .limit(max(1, min(limit, 8)))
                .execute()
            )
            return result.data or []
        except Exception as exc:
            logger.warning("Falha ao buscar ultimos pedidos do cliente %s: %s", cod_cli, exc)
            return []

    def get_sales_forecast_context(self, limit: int = 6) -> dict | None:
        """Resumo compacto do modulo de previsao para sugestoes comerciais."""
        if self.use_local:
            return None
        try:
            from clic_vendas_cli import list_previsao

            safe_limit = max(3, min(limit, 10))
            data = list_previsao(year=None, period_count=4, limit=safe_limit)
            return {
                "year": data.get("year"),
                "latest_period": data.get("latest_period"),
                "seasonal_reference_month": data.get("seasonal_reference_month"),
                "seasonal_reference_label": data.get("seasonal_reference_label"),
                "forecast_products": (data.get("forecast_products") or [])[:safe_limit],
                "seasonal_products": (data.get("seasonal_products") or [])[:safe_limit],
                "summary": data.get("summary") or {},
            }
        except Exception as exc:
            logger.warning("Falha ao buscar contexto de previsao de vendas: %s", exc)
            return None


def maybe_expire_pause(store: AgentStore, conversation: dict) -> dict:
    if not conversation.get("ai_paused"):
        return conversation

    paused_until = parse_dt(conversation.get("paused_until"))
    if paused_until and paused_until <= utc_now():
        return store.update_conversation(
            str(conversation["id"]),
            {
                "ai_paused": False,
                "paused_at": None,
                "paused_until": None,
                "pause_reason": "expired",
            },
        )
    return conversation


def apply_pause_command(store: AgentStore, conversation: dict, text: str) -> dict | None:
    normalized = normalize_text(text)
    now = utc_now()

    if normalized == RESUME_TRIGGER:
        updated = store.update_conversation(
            str(conversation["id"]),
            {
                "ai_paused": False,
                "paused_at": None,
                "paused_until": None,
                "pause_reason": "manual_resume",
            },
        )
        return {
            "action": "resumed",
            "should_reply": False,
            "conversation": updated,
        }

    if normalized == PAUSE_TRIGGER:
        paused_until = now + timedelta(hours=PAUSE_HOURS)
        updated = store.update_conversation(
            str(conversation["id"]),
            {
                "ai_paused": True,
                "paused_at": iso_z(now),
                "paused_until": iso_z(paused_until),
                "pause_reason": "manual_pause",
            },
        )
        return {
            "action": "paused",
            "should_reply": False,
            "paused_until": iso_z(paused_until),
            "conversation": updated,
        }

    return None


REGISTRAR_PEDIDO_TOOL: dict = {
    "type": "function",
    "function": {
        "name": "registrar_pedido",
        "description": (
            "Registra ou atualiza o pedido confirmado do cliente para revisão do representante antes de enviar ao sistema. "
            "Use somente depois que o cliente confirmar o resumo completo. "
            "Use acao='criar' quando o cliente pediu novo/outro pedido, mesmo que ja exista pedido pendente. "
            "Use acao='editar' somente quando o cliente quer alterar um pedido interno ja em revisao; informe o protocolo quando disponivel. "
            "Cada item deve ter produto, tipo/formato, tamanho/derivacao, quantidade e unidade. "
            "Nao escolha tamanho por padrao: se o produto tiver mais de um tamanho no formato escolhido, pergunte antes e nao registre ate o cliente confirmar. "
            "Registre preco unitario, subtotal e total do pedido quando estiverem claros na tabela, alem de observacoes espontaneas."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "itens": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "produto": {"type": "string", "description": "Nome do produto/sabor, sem inventar variacao"},
                            "tipo": {"type": "string", "description": "Formato comercial: bolsa, bolsa concentrada, copo ou garrafa"},
                            "tamanho": {"type": "string", "description": "Tamanho/derivacao/volume exatamente como confirmado pelo cliente ou unico tamanho disponivel para aquele produto/formato, ex: 200ml, 300ml, 1,7L, 5L"},
                            "quantidade": {"type": "number", "description": "Quantidade numerica confirmada pelo cliente"},
                            "unidade": {"type": "string", "description": "Unidade da quantidade, ex: unidades, copos, garrafas, bolsas"},
                            "nome": {"type": "string", "description": "Nome completo opcional do item para exibicao"},
                            "preco_unitario": {"type": "number", "description": "Preco unitario da tabela do cliente, quando claro"},
                            "subtotal": {"type": "number", "description": "Quantidade vezes preco unitario, quando claro"},
                        },
                        "required": ["produto", "tipo", "tamanho", "quantidade", "unidade"],
                    },
                    "description": "Lista de itens confirmados com produto, tipo, tamanho, quantidade, unidade, precos unitarios e subtotais",
                },
                "observacoes": {
                    "type": "string",
                    "description": "Observacoes que o cliente informou espontaneamente, incluindo total do pedido quando houver. Nao pergunte sobre frete, pagamento ou entrega.",
                },
                "total_pedido": {
                    "type": "number",
                    "description": "Soma dos subtotais dos itens, quando todos os precos estiverem claros",
                },
                "acao": {
                    "type": "string",
                    "enum": ["criar", "editar"],
                    "description": "criar para abrir um novo protocolo interno; editar para alterar pedido pendente/em revisao existente.",
                },
                "protocolo": {
                    "type": "string",
                    "description": "Protocolo interno SP-... do pedido a editar, quando o cliente estiver alterando um pedido em revisao existente.",
                },
            },
            "required": ["itens"],
        },
    },
}


def build_ai_messages(
    history: list[dict],
    module_context: dict | None = None,
    produtos: list[dict] | None = None,
) -> list[dict]:
    ctx = {**(module_context or {})}
    if produtos:
        ctx["produtos"] = produtos
    system_prompt = build_prompt(context=ctx if ctx else None)
    messages = [{"role": "system", "content": system_prompt}]
    for item in history[-CONTEXT_MESSAGE_LIMIT:]:
        role = item.get("role")
        if role not in {"user", "assistant"}:
            continue
        content = normalize_text(item.get("content"))
        if content:
            messages.append({"role": role, "content": content})
    return messages


def generate_ai_reply(
    history: list[dict],
    module_context: dict | None = None,
    phone: str | None = None,
    conversation_id: str | None = None,
    store: "AgentStore | None" = None,
    customer_name: str | None = None,
    last_user_message: str | None = None,
    produtos: list[dict] | None = None,
) -> str:
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        return ""

    from openai import OpenAI

    model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
    client = OpenAI(api_key=api_key)
    messages = build_ai_messages(history, module_context=module_context, produtos=produtos)

    response = client.chat.completions.create(
        model=model,
        messages=messages,
        tools=[REGISTRAR_PEDIDO_TOOL],
        tool_choice="auto",
        temperature=0.3,
    )

    msg = response.choices[0].message

    if msg.tool_calls:
        tool_call = msg.tool_calls[0]
        if tool_call.function.name == "registrar_pedido" and store and phone:
            try:
                args = json.loads(tool_call.function.arguments)
                itens = args.get("itens", [])
                confirmed_items = _last_confirmed_order_items(history)
                if confirmed_items and is_final_order_confirmation(last_user_message or ""):
                    itens = confirmed_items
                if _missing_order_fields(itens):
                    return missing_order_fields_prompt(itens)
                if BACKEND_CATALOG_GUARD_ENABLED:
                    if not produtos:
                        return catalog_unavailable_prompt()
                    unavailable_items = _unavailable_order_items(itens, produtos)
                    if unavailable_items:
                        return unavailable_products_prompt(unavailable_items)
                if not is_final_order_confirmation(last_user_message or ""):
                    return order_confirmation_prompt(itens)
                acao = normalize_text(args.get("acao") or "").lower()
                if acao not in {"criar", "editar"}:
                    acao = "criar" if _wants_new_order(last_user_message or "") else "editar"
                order_result = store.save_order_for_review(
                    phone=phone,
                    conversation_id=conversation_id,
                    itens=itens,
                    observacoes=args.get("observacoes", ""),
                    customer_name=customer_name or (module_context or {}).get("customer_name"),
                    mensagem_cliente=last_user_message or "",
                    acao=acao,
                    protocolo=args.get("protocolo"),
                )
                order_id = order_result.get("id") if isinstance(order_result, dict) else str(order_result)
                order_protocol = order_result.get("protocolo") if isinstance(order_result, dict) else ""
                order_action = order_result.get("action") if isinstance(order_result, dict) else "created"
                if order_action == "blocked_missing_fields":
                    return missing_order_fields_prompt(itens)
                if order_action == "blocked_ambiguous_order":
                    open_orders = order_result.get("open_orders") if isinstance(order_result, dict) else []
                    lines = [
                        "Encontrei mais de um pedido interno em aberto para voce.",
                        "Para eu nao alterar o pedido errado, me confirma qual protocolo quer editar:",
                        "",
                    ]
                    for order in open_orders[:5]:
                        lines.append(f"- {order.get('protocolo') or order.get('id')} ({order.get('status') or 'em aberto'})")
                    lines += ["", "Se preferir, tambem posso abrir um novo pedido separado."]
                    return "\n".join(lines)
                _notify_order_review(order_id)
                result_message = (
                    "Pedido atualizado para revisao do representante."
                    if order_action == "updated"
                    else "Pedido registrado para revisao do representante."
                )
                tool_result = json.dumps(
                    {
                        "sucesso": True,
                        "id": order_id,
                        "protocolo": order_protocol,
                        "acao": order_action,
                        "mensagem": result_message,
                        "itens": itens,
                        "total_pedido": args.get("total_pedido"),
                        "instrucao_resposta": (
                            "Responda ao cliente dizendo se o pedido foi registrado ou atualizado, "
                            "informe o protocolo interno do pedido, "
                            "com o resumo final incluindo preco unitario, "
                            "subtotal por item e total geral quando esses valores estiverem nos itens."
                        ),
                    },
                    ensure_ascii=False,
                )
                logger.info("Pedido %s para revisao: %s / %s (telefone: %s)", order_action, order_id, order_protocol, phone)
            except Exception as exc:
                logger.warning("Falha ao registrar pedido: %s", exc)
                tool_result = json.dumps({"sucesso": False, "erro": str(exc)}, ensure_ascii=False)

            messages_with_result = messages + [
                {
                    "role": "assistant",
                    "content": msg.content,
                    "tool_calls": [
                        {
                            "id": tool_call.id,
                            "type": "function",
                            "function": {
                                "name": tool_call.function.name,
                                "arguments": tool_call.function.arguments,
                            },
                        }
                    ],
                },
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": tool_result,
                },
            ]
            response2 = client.chat.completions.create(
                model=model,
                messages=messages_with_result,
                temperature=0.3,
            )
            return normalize_text(response2.choices[0].message.content)

    return normalize_text(msg.content or "")


def process_inbound_message(
    phone: str,
    text: str,
    payload_json: dict | None = None,
    conversation_key: str | None = None,
    store: "AgentStore | None" = None,
) -> dict:
    store = store or AgentStore()
    safe_phone = normalize_phone(phone)
    key = conversation_key or safe_phone
    if not key:
        raise ValueError("Telefone/conversation_key ausente")

    conversation = store.get_or_create_conversation(key, safe_phone)
    conversation = maybe_expire_pause(store, conversation)

    normalized_text = normalize_text(text)
    user_message = store.add_message(
        str(conversation["id"]),
        "user",
        normalized_text,
        payload_json=payload_json,
    )

    command_result = apply_pause_command(store, conversation, text)
    if command_result:
        return command_result

    conversation = maybe_expire_pause(store, conversation)
    if conversation.get("ai_paused"):
        return {
            "action": "ignored_paused",
            "should_reply": False,
            "paused_until": conversation.get("paused_until"),
        }

    runtime_settings = store.get_agent_runtime_settings()
    message_buffer_seconds = float(runtime_settings.get("message_buffer_seconds", DEFAULT_MESSAGE_BUFFER_SECONDS))
    if message_buffer_seconds > 0:
        time.sleep(message_buffer_seconds)
        if store.has_newer_user_message(str(conversation["id"]), str(user_message.get("created_at") or "")):
            return {
                "action": "buffered_waiting_latest_message",
                "should_reply": False,
                "buffer_seconds": message_buffer_seconds,
            }

    history = store.recent_messages(str(conversation["id"]), CONTEXT_MESSAGE_LIMIT)
    previous_history = history[:-1] if history else []
    conversation_state = store.get_conversation_state(str(conversation["id"]))
    classification = classify_intent(normalized_text, previous_history, conversation_state)
    classification["raw_text"] = normalized_text
    conversation_state = update_commercial_state(conversation_state, classification, normalized_text)
    store.save_conversation_state(str(conversation["id"]), conversation_state)

    direct_reply = direct_reply_for_intent(classification)

    if direct_reply:
        store.add_message(str(conversation["id"]), "assistant", direct_reply, payload_json={"source": "guardrail"})
        return {
            "action": "guardrail_reply",
            "should_reply": True,
            "reply": direct_reply,
            "context_messages": len(history),
            "intent": classification.get("intent"),
        }

    module_context = store.get_module_context(safe_phone)
    customer = store.get_customer_for_phone(safe_phone)
    codigo_tabela_original = (customer or {}).get("tabela_preco_codigo") or store.get_tabela_preco_for_phone(safe_phone)
    codigo_tabela, fallback_tabela_aplicado = resolve_price_table(codigo_tabela_original)
    recent_orders = store.get_recent_orders_for_customer(customer, limit=4)
    if customer or recent_orders:
        module_context = {**(module_context or {})}
        if customer:
            module_context["customer_profile"] = {
                "nome": customer.get("nome") or customer.get("fantasia") or customer.get("razao_social"),
                "cod_cli": customer.get("cod_cli") or customer.get("cpf_cnpj"),
                "tabela_preco_codigo": codigo_tabela,
                "tabela_preco_codigo_original": codigo_tabela_original,
                "tabela_preco_fallback_aplicado": fallback_tabela_aplicado,
                "tabela_preco_nome": customer.get("tabela_preco_nome"),
                "cidade": customer.get("cidade"),
                "uf": customer.get("uf"),
            }
            module_context["customer_name"] = module_context.get("customer_name") or module_context["customer_profile"].get("nome")
        if recent_orders:
            module_context["recent_orders"] = recent_orders
    module_context = {**(module_context or {})}
    sales_forecast = store.get_sales_forecast_context(limit=6)
    if sales_forecast:
        module_context["sales_forecast"] = sales_forecast
    open_review_orders = store.get_open_orders_for_review(safe_phone, str(conversation["id"]), limit=5)
    open_review_order = open_review_orders[0] if open_review_orders else None
    if open_review_orders:
        module_context["open_review_orders"] = open_review_orders
        module_context["open_review_order"] = open_review_order
    module_context["classified_intent"] = classification
    module_context["conversation_state"] = conversation_state
    if codigo_tabela:
        produtos = store.get_produtos_tabela(codigo_tabela)
    else:
        produtos = store.get_produtos()

    if classification.get("intent") == "product_query" and _asks_non_suco_products(normalized_text):
        reply = normalize_customer_facing_ptbr(non_suco_products_reply(produtos))
        store.add_message(str(conversation["id"]), "assistant", reply, payload_json={"source": "catalog_non_suco"})
        return {
            "action": "catalog_non_suco_reply",
            "should_reply": True,
            "reply": reply,
            "context_messages": len(history),
            "intent": classification.get("intent"),
        }

    catalog_reply = catalog_guard_prompt(normalized_text, produtos) if BACKEND_CATALOG_GUARD_ENABLED else ""
    if catalog_reply:
        reply = normalize_customer_facing_ptbr(catalog_reply)
        store.add_message(str(conversation["id"]), "assistant", reply, payload_json={"source": "catalog_guardrail"})
        return {
            "action": "catalog_guardrail_reply",
            "should_reply": True,
            "reply": reply,
            "context_messages": len(history),
            "intent": classification.get("intent"),
        }

    has_current_quantities = bool((classification.get("entities") or {}).get("quantities"))
    option_reply = (
        product_options_reply(normalized_text, produtos)
        if classification.get("intent") == "product_query" and not has_current_quantities
        else ""
    )
    if option_reply:
        option_reply = normalize_customer_facing_ptbr(option_reply)
        store.add_message(str(conversation["id"]), "assistant", option_reply, payload_json={"source": "catalog_options"})
        return {
            "action": "catalog_options_reply",
            "should_reply": True,
            "reply": option_reply,
            "context_messages": len(history),
            "intent": classification.get("intent"),
        }

    specifics_reply = (
        product_specifics_guard_prompt(normalized_text, open_review_order)
        if BACKEND_ORDER_SPECIFICS_GUARD_ENABLED
        else ""
    )
    if specifics_reply:
        specifics_reply = normalize_customer_facing_ptbr(specifics_reply)
        store.add_message(str(conversation["id"]), "assistant", specifics_reply, payload_json={"source": "product_specifics_guard"})
        return {
            "action": "product_specifics_guard_reply",
            "should_reply": True,
            "reply": specifics_reply,
            "context_messages": len(history),
            "intent": classification.get("intent"),
        }

    if is_full_product_list_request(normalized_text, classification):
        reply = normalize_customer_facing_ptbr(full_product_catalog_reply(produtos, codigo_tabela=codigo_tabela, text=normalized_text))
        store.add_message(str(conversation["id"]), "assistant", reply, payload_json={"source": "catalog_full_list"})
        return {
            "action": "catalog_full_list_reply",
            "should_reply": True,
            "reply": reply,
            "context_messages": len(history),
            "intent": classification.get("intent"),
        }

    reply = generate_ai_reply(
        history,
        module_context=module_context,
        phone=safe_phone,
        conversation_id=str(conversation["id"]),
        store=store,
        customer_name=(module_context or {}).get("customer_name"),
        last_user_message=normalized_text,
        produtos=produtos,
    )
    reply = sanitize_ai_reply(
        reply,
        classification=classification,
        has_order_context=bool(classification.get("has_order_context")),
    )
    reply = normalize_customer_facing_ptbr(reply)
    if not reply:
        return {
            "action": "no_reply_generated",
            "should_reply": False,
            "context_messages": len(history),
        }

    store.add_message(str(conversation["id"]), "assistant", reply, payload_json={"source": "ai"})
    return {
        "action": "reply",
        "should_reply": True,
        "reply": reply,
        "context_messages": len(history),
        "module_context": module_context.get("module") if module_context else None,
        "intent": classification.get("intent"),
    }
