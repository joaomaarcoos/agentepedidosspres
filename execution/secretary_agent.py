"""
Atendimento da Marcela Secretaria para representantes em uma instancia central.

O modulo mantem estado separado do agente de vendas e somente envia pedidos
depois de uma confirmacao explicita do representante.
"""

from __future__ import annotations

import json
import os
import re
import time
import unicodedata
import uuid
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Callable

from dotenv import load_dotenv

from senior_order_client import SeniorOrderClient
from ai_agent import (
    _reconcile_catalog_resolution,
    resolve_order_with_subagent,
)
from secretary_ai_agent import analyze_secretary_message
from secretary_tools import (
    resolve_products_tool,
    select_sale_type_tool,
    show_summary_tool,
    submit_order_tool,
)

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

CONFIRM_RE = re.compile(r"\b(confirmo|confirmado|pode enviar|pode mandar|pode fechar|esta tudo certo|est[aá] certo)\b", re.I)
CANCEL_RE = re.compile(r"\b(cancelar|cancela|desistir|apagar pedido)\b", re.I)
STATUS_RE = re.compile(r"\b(status|situa[cç][aã]o|acompanhar|pedidos?|hist[oó]rico|atualiza[cç][aã]o)\b", re.I)
STATUS_CREATE_GUARD_RE = re.compile(r"\b(quero|fazer|montar|criar|abrir|novo|nova|entrada)\b", re.I)
NEW_ORDER_RE = re.compile(r"\b(novo pedido|outro pedido|recomecar|recomeçar|comecar de novo|começar de novo|refazer pedido)\b", re.I)
CHANGE_CUSTOMER_RE = re.compile(r"\b(trocar cliente|mudar cliente|alterar cliente|cliente errado|corrigir cliente)\b", re.I)
KEEP_CURRENT_RE = re.compile(r"\b(continuar|continua|manter|fica nesse|seguir nesse|nao trocar|não trocar)\b", re.I)
REFERENCE_RE = re.compile(r"\bMSE-\d{6}-[A-Z0-9]{6}\b", re.I)
OBSERVATION_NO_RE = re.compile(r"^\s*(n[aã]o|nao|sem|sem observacao|sem observa[cç][aã]o|nenhuma|nao precisa|não precisa)\s*[.!]?\s*$", re.I)
OBSERVATION_YES_RE = re.compile(r"^\s*(sim|quero|pode adicionar|adicionar|tenho|tem)\s*[.!]?\s*$", re.I)
DEFAULT_SECRETARY_ALLOWED_PHONE = "5516991377335,98981522794,559881422794"
ELIEZER_REP_DOCUMENT = "34501704810"
ELIEZER_FALLBACK_COD_REP = 52
REPRESENTATIVE_PROFILES_KEY = "clic_representative_profiles"
CUSTOMER_PROFILES_KEY = "clic_customer_profiles"
REPLY_SPLIT_MARKER = "\n<<<SPLIT_REPLY>>>\n"
CONFIRM_RE = re.compile(
    r"\b(sim|ok|okay|confirmo|confirmado|pode enviar|pode mandar|pode fechar|manda|envia|fechar|esta tudo certo|est[aÃ¡] certo|correto|certo)\b",
    re.I,
)

def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _digits(value: Any) -> str:
    return re.sub(r"\D", "", str(value or ""))


def _norm(value: Any) -> str:
    normalized = unicodedata.normalize("NFKD", str(value or ""))
    return "".join(ch for ch in normalized if not unicodedata.combining(ch)).lower().strip()


def _safe_float(value: Any) -> float:
    try:
        return float(str(value or 0).replace(",", "."))
    except (TypeError, ValueError):
        return 0.0


def _norm_size(value: Any) -> str:
    raw = _norm(value).replace(",", ".").replace(" ", "")
    if raw.endswith("ml"):
        raw = raw[:-2]
    if raw in {"05l", "5.0l"}:
        return "5l"
    if raw in {"1l7", "1.7l", "17l"}:
        return "1.7l"
    return raw


def _sale_type_code_from_text(text: Any) -> str | None:
    value = _norm(text)
    if re.search(r"\b(pdv|sem nota)\b", value):
        return "9010P"
    if re.search(r"\b(bonificacao|bonifica[cç][aã]o|bonif)\b", value):
        return "BONIF4"
    if re.search(r"\b(normal|nota fiscal|com nota)\b", value):
        return "90100"
    return None


SALE_TYPE_LABELS = {
    "90100": "pedido normal",
    "9010P": "pedido PDV",
    "BONIF4": "bonificacao - acordo comercial",
}
VALID_SALE_TYPE_CODES = set(SALE_TYPE_LABELS)


def _sale_type_prompt() -> str:
    return "Qual é o tipo do pedido? Responda *normal*, *PDV* ou *bonificação*."


def _sale_type_label(code: Any) -> str:
    return SALE_TYPE_LABELS.get(str(code or ""), str(code or ""))


def _validated_sale_type_code(value: Any) -> str:
    code = str(value or "").strip()
    if code == "9010O":
        code = "90100"
    if code not in VALID_SALE_TYPE_CODES:
        raise ValueError("Tipo de venda não definido. Informe *normal*, *PDV* ou *bonificação* antes de enviar.")
    return code


def _sale_type_only_message(text: Any) -> bool:
    value = re.sub(r"[^\w\s/]+", " ", _norm(text))
    value = re.sub(r"\s+", " ", value).strip()
    simplified = value
    for prefix in ("entrada pedido ", "pedido ", "entrada "):
        if simplified.startswith(prefix):
            simplified = simplified[len(prefix) :].strip()
            break
    if simplified in {
        "normal",
        "com nota",
        "nota fiscal",
        "pdv",
        "sem nota",
        "bonificacao",
        "bonif",
        "bonificacao acordo",
    }:
        return True
    return bool(
        re.fullmatch(
            r"(pedido\s+)?(normal|pdv|sem nota|com nota|nota fiscal|bonificacao|bonifica[cÃ§][aÃ£]o|bonif)(\s+acordo)?",
            value,
        )
    )


def _generic_chat_message(text: Any) -> bool:
    value = _norm(text)
    if not value:
        return True
    if re.fullmatch(r"(oi|ola|bom dia|boa tarde|boa noite|teste|testando|alo|e ai|eai)", value):
        return True
    return bool(re.search(r"\b(ajuda|comecar|começar|pedido|fazer pedido)\b", value)) and not re.search(r"\d{2,}", value)


def _status_request_message(text: Any) -> bool:
    value = _norm(text)
    if not STATUS_RE.search(text):
        return False
    if STATUS_CREATE_GUARD_RE.search(value):
        return False
    return bool(
        re.search(
            r"\b(status|situacao|acompanhar|historico|atualizacao|ultimos pedidos|pedidos recentes|meus pedidos)\b",
            value,
        )
    )


def _summary_request_message(text: Any) -> bool:
    value = _norm(text)
    return bool(
        re.search(r"\b(mostra|mostrar|resumo|rever|revisar|conferir|confirmar)\b", value)
        and re.search(r"\b(pedido|rascunho)\b", value)
    )


def _after_observation_reply(state: dict) -> str:
    if state.get("items"):
        return _order_summary(
            state["customer"],
            state.get("items") or [],
            state.get("observations") or "",
            sale_type_code=state.get("sale_type_code"),
        )
    return "Certo. Agora me envie os produtos e quantidades do pedido."


def _handle_observation_response(
    text: str,
    state: dict,
    save_draft: Callable[[dict], dict] | None = None,
) -> tuple[str, str] | None:
    if not (state.get("awaiting_observation") or state.get("awaiting_observation_text")):
        return None
    value = str(text or "").strip()
    if not value:
        return ("Pode me dizer a observação, ou responder *não* para seguir sem observação.", "secretary_ask_observation")
    if state.get("awaiting_observation_text"):
        if OBSERVATION_NO_RE.search(value):
            state["observations"] = ""
        else:
            state["observations"] = value
        editing_observation = bool(state.pop("editing_observation", None))
        state.pop("awaiting_observation_text", None)
        state.pop("awaiting_observation", None)
        state["observation_step_done"] = True
        if editing_observation and state.get("customer") and state.get("items") and save_draft:
            order = save_draft(state)
            state["order_id"] = order.get("id")
            state["protocol"] = order.get("protocol")
            state["ready_to_submit"] = True
        return (_after_observation_reply(state), "secretary_observation_saved")
    if OBSERVATION_NO_RE.search(value):
        state["observations"] = ""
        state.pop("awaiting_observation", None)
        state["observation_step_done"] = True
        return (_after_observation_reply(state), "secretary_observation_skipped")
    if OBSERVATION_YES_RE.search(value):
        state["awaiting_observation_text"] = True
        return ("Qual observação devo adicionar nesse pedido?", "secretary_ask_observation_text")
    state["observations"] = value
    state.pop("awaiting_observation", None)
    state["observation_step_done"] = True
    return (_after_observation_reply(state), "secretary_observation_saved")


def _extract_observation_edit_text(text: str) -> str | None:
    value = str(text or "").strip()
    if not value:
        return None
    patterns = [
        r"(?:mudar|trocar|alterar|corrigir|atualizar|editar)\s+(?:a\s+)?observa\S*\s*(?:para|pra|por|:|-)\s*(.+)$",
        r"observa\S*\s*(?:para|pra|por|:|-)\s*(.+)$",
    ]
    for pattern in patterns:
        match = re.search(pattern, value, re.I | re.S)
        if match:
            extracted = str(match.group(1) or "").strip(" .,\n\t")
            return extracted or None
    return None


def _handle_observation_edit_request(text: str, state: dict, save_draft: Callable[[dict], dict] | None = None) -> tuple[str, str] | None:
    if not (state.get("customer") and state.get("items")):
        return None
    normalized = _norm(text)
    if "observacao" not in normalized:
        return None
    wants_edit = any(
        word in normalized
        for word in ("mudar", "trocar", "alterar", "corrigir", "atualizar", "editar")
    )
    if not wants_edit and not re.search(r"\bobservacao\s*(para|pra|por)\b", normalized):
        return None

    new_observation = _extract_observation_edit_text(text)
    if new_observation is None:
        state["awaiting_observation_text"] = True
        state["editing_observation"] = True
        state.pop("awaiting_observation", None)
        return ("Qual é a nova observação desse pedido?", "secretary_ask_observation_text")

    if OBSERVATION_NO_RE.search(new_observation):
        state["observations"] = ""
    else:
        state["observations"] = new_observation
    state["observation_step_done"] = True
    state.pop("editing_observation", None)
    state.pop("awaiting_observation", None)
    state.pop("awaiting_observation_text", None)
    if save_draft:
        order = save_draft(state)
        state["order_id"] = order.get("id")
        state["protocol"] = order.get("protocol")
        state["ready_to_submit"] = True
    return (_after_observation_reply(state), "secretary_observation_updated")


def _representative_display_name(representative: dict | None) -> str:
    name = str((representative or {}).get("name") or "").strip()
    return name or "esse representante"


def _representative_first_name(representative: dict | None) -> str:
    name = _representative_display_name(representative)
    if name == "esse representante":
        return ""
    return name.split()[0].title()


def _start_conversation_reply(state: dict, representative: dict | None = None) -> str:
    if state.get("sale_type_code"):
        return (
            f"Perfeito, vou montar como *{_sale_type_label(state.get('sale_type_code'))}*. "
            "Me envie o código, nome ou documento do cliente para eu localizar na sua carteira."
        )
    first_name = _representative_first_name(representative)
    greeting = f"Oi, {first_name}, " if first_name else "Oi, "
    return (
        f"{greeting}sou a secretaria de pedidos. "
        "Me envie o código, nome ou documento do cliente para começarmos."
    )


def _next_order_step_message(state: dict, product_wording: str = "Agora envie os produtos e quantidades do pedido.") -> str:
    if not state.get("sale_type_code"):
        return _sale_type_prompt()
    if not state.get("observation_step_done"):
        state["awaiting_observation"] = True
        return "Quer adicionar alguma observação nesse pedido? Se não quiser, responda *não*."
    return product_wording


def _db():
    url = os.getenv("SUPABASE_URL", "").rstrip("/")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_ANON_KEY", "")
    if not url or not key:
        raise RuntimeError("Supabase nao configurado para a Marcela Secretaria")
    from supabase import create_client

    return create_client(url, key)


def _phone_candidates(phone: str) -> list[str]:
    value = _digits(phone)
    values = {value}
    if value.startswith("55") and len(value) > 11:
        values.add(value[2:])
    elif len(value) in (10, 11):
        values.add(f"55{value}")
    for item in list(values):
        if item.startswith("55") and len(item) == 13 and item[4] == "9":
            values.add(f"{item[:4]}{item[5:]}")
        elif item.startswith("55") and len(item) == 12:
            values.add(f"{item[:4]}9{item[4:]}")
        elif len(item) == 11 and item[2] == "9":
            values.add(f"{item[:2]}{item[3:]}")
        elif len(item) == 10:
            values.add(f"{item[:2]}9{item[2:]}")
    return [item for item in values if item]


def _allowed_secretary_phones() -> set[str]:
    raw = os.getenv("SECRETARY_ALLOWED_PHONES", DEFAULT_SECRETARY_ALLOWED_PHONE).strip()
    if not raw:
        raw = DEFAULT_SECRETARY_ALLOWED_PHONE
    allowed: set[str] = set()
    for item in re.split(r"[,;\s]+", raw):
        for candidate in _phone_candidates(item):
            allowed.add(candidate)
    return allowed


def _is_secretary_phone_allowed(phone: str) -> bool:
    allowed = _allowed_secretary_phones()
    return bool(set(_phone_candidates(phone)) & allowed)


def is_secretary_phone_allowed(phone: str) -> bool:
    if _is_secretary_phone_allowed(phone):
        return True
    try:
        return _representative_from_registry(_db(), phone) is not None
    except Exception:
        return False


def _representative_from_registry(db, phone: str) -> dict | None:
    rows = (
        db.table("representatives")
        .select("cod_rep,name,active,whatsapp_number")
        .eq("active", True)
        .limit(5000)
        .execute()
        .data
        or []
    )
    candidates = set(_phone_candidates(phone))
    active = [
        row
        for row in rows
        if row.get("active") is not False
        and row.get("cod_rep") is not None
        and _digits(row.get("whatsapp_number")) in candidates
    ]
    if len(active) == 1:
        return active[0]
    return None


def _representative(db, phone: str) -> dict | None:
    representative = _representative_from_registry(db, phone)
    if representative:
        return representative
    if not _is_secretary_phone_allowed(phone):
        return None

    try:
        profile_rows = (
            db.table("system_settings")
            .select("value")
            .eq("key", REPRESENTATIVE_PROFILES_KEY)
            .limit(1)
            .execute()
            .data
            or []
        )
        profiles = profile_rows[0].get("value") if profile_rows else {}
        if isinstance(profiles, dict):
            for profile in profiles.values():
                if not isinstance(profile, dict):
                    continue
                if _digits(profile.get("documento")) == ELIEZER_REP_DOCUMENT:
                    return {
                        "cod_rep": int(profile.get("cod_rep") or ELIEZER_FALLBACK_COD_REP),
                        "name": profile.get("nome") or "ELIEZER GONZAGA DOS REIS",
                        "active": True,
                        "whatsapp_number": DEFAULT_SECRETARY_ALLOWED_PHONE,
                    }
    except Exception:
        pass

    return {
        "cod_rep": ELIEZER_FALLBACK_COD_REP,
        "name": "ELIEZER GONZAGA DOS REIS",
        "active": True,
        "whatsapp_number": DEFAULT_SECRETARY_ALLOWED_PHONE,
    }


def _representative_document(db, cod_rep: Any) -> str:
    code = str(cod_rep or "").strip()
    if not code:
        return ""
    try:
        rows = (
            db.table("system_settings")
            .select("value")
            .eq("key", REPRESENTATIVE_PROFILES_KEY)
            .limit(1)
            .execute()
            .data
            or []
        )
        profiles = rows[0].get("value") if rows else {}
        if isinstance(profiles, dict):
            profile = profiles.get(code) or profiles.get(str(int(float(code))))
            if isinstance(profile, dict):
                return _digits(profile.get("documento"))
    except Exception:
        return ""
    return ""


def _conversation(db, instance: str, phone: str, cod_rep: int) -> dict:
    key = f"{instance}:{_digits(phone)}"
    rows = (
        db.table("secretary_conversations")
        .select("*")
        .eq("conversation_key", key)
        .limit(1)
        .execute()
        .data
        or []
    )
    if rows:
        return rows[0]
    payload = {
        "conversation_key": key,
        "instance_name": instance,
        "representative_phone": _digits(phone),
        "cod_rep": cod_rep,
        "state_json": {},
    }
    created = db.table("secretary_conversations").insert(payload).execute().data or []
    return created[0] if created else payload


def _save_state(db, conversation_id: str, state: dict) -> None:
    db.table("secretary_conversations").update(
        {"state_json": state, "updated_at": _now()}
    ).eq("id", conversation_id).execute()


def _add_message(
    db,
    conversation_id: str,
    role: str,
    content: str,
    external_message_id: str | None = None,
    payload: dict | None = None,
) -> bool:
    row = {
        "conversation_id": conversation_id,
        "external_message_id": external_message_id or None,
        "role": role,
        "content": content,
        "payload_json": payload or {},
    }
    try:
        db.table("secretary_messages").insert(row).execute()
        return True
    except Exception as exc:
        if external_message_id and any(token in str(exc).lower() for token in ("duplicate", "23505", "unique")):
            return False
        raise


def _customer_from_raw(raw: dict) -> dict:
    customer = raw.get("cliente") if isinstance(raw.get("cliente"), dict) else {}
    backoffice = customer.get("backoffice") if isinstance(customer.get("backoffice"), dict) else {}
    phones = customer.get("telefones") or []
    tables = customer.get("tabelasPreco") or []
    return {
        "code": str(backoffice.get("codigo") or customer.get("codigo") or ""),
        "document": _digits(
            customer.get("cpfCnpj")
            or customer.get("numeroDocumento")
            or customer.get("documento")
        ),
        "name": str(customer.get("fantasia") or customer.get("razaoSocial") or "").strip(),
        "city": str(customer.get("cidade") or "").strip(),
        "uf": str(customer.get("uf") or "").strip(),
        "phone": _digits((phones[0] or {}).get("valor")) if phones else "",
        "price_table_code": str((tables[0] or {}).get("codigoTabela") or "") if tables else "",
    }


def _customer_profiles(db) -> dict[str, dict]:
    try:
        rows = (
            db.table("system_settings")
            .select("value")
            .eq("key", CUSTOMER_PROFILES_KEY)
            .limit(1)
            .execute()
            .data
            or []
        )
    except Exception:
        return {}
    value = rows[0].get("value") if rows else {}
    return value if isinstance(value, dict) else {}


def _customer_metrics(db, documents: list[str]) -> dict[str, dict]:
    result: dict[str, dict] = {}
    clean_documents = [doc for doc in {_digits(item) for item in documents} if doc]
    for index in range(0, len(clean_documents), 200):
        batch = clean_documents[index : index + 200]
        try:
            rows = (
                db.table("clic_clientes")
                .select("cpf_cnpj,telefone,tabela_preco_codigo,tabela_preco_nome,tabelas_especiais_json")
                .in_("cpf_cnpj", batch)
                .execute()
                .data
                or []
            )
        except Exception:
            continue
        for row in rows:
            document = _digits(row.get("cpf_cnpj"))
            if document:
                result[document] = row
    return result


def _portfolio_customers(db, cod_rep: int) -> list[dict]:
    """Carteira da secretária baseada na mesma fonte do módulo Clientes.

    O vínculo representante-cliente vem de rep_order_base(cod_rep, cod_cli).
    Dados cadastrais complementares vêm de system_settings.clic_customer_profiles
    e clic_clientes, quando disponíveis.
    """
    select_fields = (
        "cod_cli,cod_rep,customer_document,customer_name,num_ped,dat_emi,"
        "sit_ped,order_total_value,source,erp_synced_at,updated_at"
    )
    fallback_fields = "cod_cli,cod_rep,num_ped,dat_emi,sit_ped,order_total_value,source,erp_synced_at,updated_at"

    def execute(fields: str) -> list[dict]:
        return (
            db.table("rep_order_base")
            .select(fields)
            .eq("cod_rep", cod_rep)
            .order("dat_emi", desc=True)
            .limit(10000)
            .execute()
            .data
            or []
        )

    try:
        rows = execute(select_fields)
    except Exception as exc:
        if "customer_document" not in str(exc) and "customer_name" not in str(exc):
            raise
        rows = execute(fallback_fields)

    profiles = _customer_profiles(db)
    documents: list[str] = []
    latest: dict[str, dict] = {}
    for row in rows:
        cod_cli = str(row.get("cod_cli") or "")
        if not cod_cli or cod_cli in latest:
            continue
        profile = profiles.get(cod_cli) or {}
        document = _digits(profile.get("documento") or row.get("customer_document"))
        if document:
            documents.append(document)
        latest[cod_cli] = {**row, "_profile": profile, "_document": document}

    metrics = _customer_metrics(db, documents)
    customers: list[dict] = []
    for cod_cli, row in latest.items():
        profile = row.get("_profile") or {}
        document = row.get("_document") or _digits(row.get("customer_document"))
        metric = metrics.get(document, {})
        name = (
            profile.get("nome")
            or profile.get("razao_social")
            or profile.get("fantasia")
            or row.get("customer_name")
            or f"Cliente {cod_cli}"
        )
        customers.append(
            {
                "code": cod_cli,
                "document": document,
                "name": str(name or "").strip(),
                "city": str(profile.get("cidade") or "").strip(),
                "uf": str(profile.get("uf") or "").strip(),
                "phone": _digits(profile.get("telefone") or metric.get("telefone")),
                "price_table_code": str(
                    profile.get("tabela_preco_codigo")
                    or metric.get("tabela_preco_codigo")
                    or ""
                ),
            }
        )
    return customers


def _customer_score(customer: dict, query: str) -> float:
    wanted = _norm(query)
    if not wanted:
        return 0
    wanted_digits = _digits(wanted)
    haystacks = [
        _norm(customer.get("name")),
        _norm(customer.get("city")),
        _digits(customer.get("code")),
        _digits(customer.get("document")),
    ]
    digit_haystacks = [value for value in haystacks[-2:] if value]
    if wanted_digits and any(wanted_digits == value for value in digit_haystacks):
        return 1.0
    if wanted_digits and any(wanted_digits in value for value in digit_haystacks):
        return 0.95
    if any(wanted == value for value in haystacks if value):
        return 1.0
    if any(wanted in value for value in haystacks if value):
        return 0.92
    return max((SequenceMatcher(None, wanted, value).ratio() for value in haystacks if value), default=0)


def _search_customers(customers: list[dict], query: str) -> list[dict]:
    query = re.sub(
        r"^\s*(?:cliente|c[oó]digo|cod\.?|para\s+o\s+cliente|pedido\s+para|pedido)\s+",
        "",
        str(query or ""),
        flags=re.I,
    )
    scored = [(customer, _customer_score(customer, query)) for customer in customers]
    return [customer for customer, score in sorted(scored, key=lambda item: item[1], reverse=True) if score >= 0.45][:5]


def _masked_customer(customer: dict, index: int) -> str:
    document = _digits(customer.get("document"))
    phone = _digits(customer.get("phone"))
    suffix = document[-4:] if document else phone[-4:]
    location = " / ".join(part for part in (customer.get("city"), customer.get("uf")) if part)
    details = " | ".join(part for part in (location, f"final {suffix}" if suffix else "") if part)
    return f"{index}. {customer.get('name') or customer.get('code')}{f' | {details}' if details else ''}"


def _has_order_context(state: dict) -> bool:
    return bool(
        state.get("customer")
        or state.get("items")
        or state.get("catalog_resolution")
        or state.get("order_id")
    )


def _cancel_current_draft(db, state: dict) -> None:
    if not state.get("order_id"):
        return
    db.table("secretary_orders").update(
        {"status": "cancelled", "updated_at": _now()}
    ).eq("id", state["order_id"]).in_(
        "status", ["draft", "awaiting_confirmation", "failed"]
    ).execute()


def _clear_order_state(db, state: dict, keep_sale_type: bool = True) -> dict:
    sale_type_code = state.get("sale_type_code") if keep_sale_type else None
    _cancel_current_draft(db, state)
    new_state: dict = {}
    if sale_type_code:
        new_state["sale_type_code"] = sale_type_code
    return new_state


def _start_customer_state(customer: dict, previous_state: dict | None = None) -> dict:
    state: dict = {"customer": customer}
    sale_type_code = (previous_state or {}).get("sale_type_code")
    if sale_type_code:
        state["sale_type_code"] = sale_type_code
    return state


def _customer_change_candidate(customers: list[dict], text: str, current_customer: dict | None) -> dict | None:
    value = str(text or "").strip()
    normalized = _norm(value)
    digits = _digits(value)
    explicit_customer_text = bool(CHANGE_CUSTOMER_RE.search(value)) or normalized.startswith(("cliente ", "codigo ", "cod "))
    if not explicit_customer_text and (not digits or len(digits) < 3):
        return None
    if digits and not explicit_customer_text and re.fullmatch(r"\D*\d+\D*", value):
        exact_matches = [
            customer
            for customer in customers
            if digits in {_digits(customer.get("code")), _digits(customer.get("document"))}
        ]
        if len(exact_matches) != 1:
            return None
        candidate = exact_matches[0]
        if current_customer and str(candidate.get("code")) == str(current_customer.get("code")):
            return None
        return candidate
    matches = _search_customers(customers, value)
    if len(matches) != 1:
        return None
    candidate = matches[0]
    if current_customer and str(candidate.get("code")) == str(current_customer.get("code")):
        return None
    return candidate


def _catalog(db, customer: dict) -> list[dict]:
    code = str(customer.get("price_table_code") or "")
    if not code and customer.get("document"):
        rows = (
            db.table("clic_clientes")
            .select("tabela_preco_codigo")
            .eq("cpf_cnpj", customer["document"])
            .limit(1)
            .execute()
            .data
            or []
        )
        code = str((rows[0] if rows else {}).get("tabela_preco_codigo") or "")
        customer["price_table_code"] = code
    if not code:
        return []
    return (
        db.table("tabelas_preco_itens")
        .select("cod_produto,nome_produto,variacao,quantidade_minima,preco")
        .eq("codigo_tabela", code)
        .order("nome_produto")
        .execute()
        .data
        or []
    )


def _resolve_products_with_sales_subagent(
    text: str,
    catalog: list[dict],
    state: dict,
) -> dict | None:
    history = state.get("product_history") or []
    history = [
        item
        for item in history[-10:]
        if isinstance(item, dict) and item.get("role") in {"user", "assistant"}
    ]
    history.append({"role": "user", "content": text})
    resolution = resolve_order_with_subagent(
        text=text,
        produtos=catalog,
        classification={
            "intent": "order_request",
            "confidence": 1.0,
            "has_order_context": True,
        },
        history=history,
        previous_resolution=state.get("catalog_resolution"),
    )
    if not resolution:
        return None
    reconciled = _reconcile_catalog_resolution(resolution, catalog)
    state["catalog_resolution"] = reconciled
    state["product_history"] = history
    return reconciled


def _product_words(value: Any) -> set[str]:
    stopwords = {"suco", "natural", "pasteurizado", "pet", "de", "do", "da", "com", "e"}
    return {
        word
        for word in re.findall(r"[a-z0-9]+", _norm(value))
        if len(word) > 2 and word not in stopwords
    }


def _suggestion_score(option: str, item: dict) -> int:
    option_norm = _norm(option)
    option_size = _norm_size(option)
    wanted_size = _norm_size(item.get("tamanho") or item.get("derivacao"))
    wanted_words = _product_words(
        " ".join(
            str(item.get(key) or "")
            for key in ("produto", "nome_catalogo", "texto_original")
        )
    )
    option_words = _product_words(option)
    score = 0
    if wanted_size and wanted_size == option_size:
        score += 4
    if wanted_size and wanted_size in option_norm.replace(" ", ""):
        score += 4
    score += len(wanted_words & option_words) * 3
    requested_format = _norm(item.get("formato"))
    if requested_format and requested_format in option_norm:
        score += 2
    return score


def _filtered_suggestions(item: dict, limit: int = 4) -> list[str]:
    options = [str(option).strip() for option in item.get("alternativas") or [] if str(option).strip()]
    if not options:
        return []
    scored = [(option, _suggestion_score(option, item)) for option in options]
    positive = [pair for pair in scored if pair[1] > 0]
    ranked = sorted(positive or scored, key=lambda pair: pair[1], reverse=True)
    result = []
    for option, _score in ranked:
        if option not in result:
            result.append(option)
        if len(result) >= limit:
            break
    return result


def _catalog_option_text(row: dict) -> str:
    code = str(row.get("cod_produto") or "").strip()
    name = str(row.get("nome_produto") or row.get("nome") or "").strip()
    variation = str(row.get("variacao") or row.get("derivacao") or "").strip()
    price = _safe_float(row.get("preco") or row.get("preco_unitario"))
    parts = [part for part in (f"{code} - {name}".strip(" -"), variation, _money_br(price) if price else "") if part]
    return " | ".join(parts)


def _augment_resolution_suggestions(resolution: dict | None, catalog: list[dict], limit: int = 6) -> dict | None:
    if not isinstance(resolution, dict) or not catalog:
        return resolution
    enriched_items = []
    for item in resolution.get("itens") or []:
        if not isinstance(item, dict):
            enriched_items.append(item)
            continue
        if item.get("status") == "encontrado":
            enriched_items.append(item)
            continue

        wanted_size = _norm_size(item.get("tamanho") or item.get("derivacao") or item.get("formato"))
        wanted_words = _product_words(
            " ".join(
                str(item.get(key) or "")
                for key in ("produto", "nome_catalogo", "texto_original", "formato")
            )
        )
        requested_flavors = wanted_words & {
            "laranja",
            "uva",
            "caju",
            "manga",
            "maracuja",
            "morango",
            "abacaxi",
            "goiaba",
            "maca",
            "limonada",
        }
        suggestions = [str(option).strip() for option in item.get("alternativas") or [] if str(option).strip()]
        scored: list[tuple[str, int]] = []
        for row in catalog:
            row_text = " ".join(
                str(row.get(key) or "")
                for key in ("cod_produto", "nome_produto", "nome", "variacao", "derivacao")
            )
            row_norm = _norm(row_text)
            row_words = _product_words(row_text)
            row_size = _norm_size(row.get("variacao") or row.get("derivacao"))
            same_size = bool(wanted_size and (row_size == wanted_size or wanted_size in row_norm.replace(" ", "")))
            same_flavor = bool(requested_flavors and requested_flavors & row_words)
            if wanted_size and not same_size:
                continue
            if requested_flavors and not same_flavor:
                continue
            if not same_size and not same_flavor:
                continue
            score = 0
            if same_size:
                score += 8
            if same_flavor:
                score += 8
            score += len(wanted_words & row_words) * 2
            option = _catalog_option_text(row)
            if option and option not in suggestions:
                scored.append((option, score))
        for option, _score in sorted(scored, key=lambda pair: pair[1], reverse=True):
            if option not in suggestions:
                suggestions.append(option)
            if len(suggestions) >= limit:
                break
        enriched_items.append({**item, "alternativas": suggestions})
    return {**resolution, "itens": enriched_items}


def _same_pending_product(pending: dict, found: dict) -> bool:
    pending_format = _norm(pending.get("formato"))
    found_format = _norm(found.get("formato"))
    if pending_format and found_format and pending_format != found_format:
        return False
    pending_size = _norm_size(pending.get("tamanho") or pending.get("derivacao"))
    found_size = _norm_size(found.get("tamanho") or found.get("derivacao"))
    if pending_size and found_size and pending_size != found_size:
        return False
    pending_words = _product_words(pending.get("produto") or pending.get("texto_original"))
    found_words = _product_words(
        " ".join(
            str(part or "")
            for part in (
                found.get("produto"),
                found.get("nome_catalogo"),
                found.get("texto_original"),
            )
        )
    )
    if not pending_words and pending_format and pending_size and found_format and found_size:
        return True
    return bool(pending_words and found_words and pending_words <= found_words)


def _drop_resolved_pending_items(resolution: dict | None) -> dict | None:
    if not isinstance(resolution, dict):
        return resolution
    items = [item for item in resolution.get("itens") or [] if isinstance(item, dict)]
    found_items = [item for item in items if item.get("status") == "encontrado"]
    if not found_items:
        return resolution
    filtered = []
    changed = False
    for item in items:
        if item.get("status") != "encontrado" and any(_same_pending_product(item, found) for found in found_items):
            changed = True
            continue
        filtered.append(item)
    if not changed:
        return resolution
    return {**resolution, "itens": filtered}


def _resolution_items(resolution: dict | None) -> list[dict]:
    items = []
    for item in (resolution or {}).get("itens") or []:
        if not isinstance(item, dict) or item.get("status") != "encontrado":
            continue
        quantity = _safe_float(item.get("quantidade"))
        price = _safe_float(item.get("preco_unitario"))
        items.append(
            {
                "cod_produto": str(item.get("cod_produto") or ""),
                "nome": str(item.get("nome_catalogo") or item.get("produto") or ""),
                "derivacao": str(item.get("codigo_variacao") or item.get("derivacao") or item.get("tamanho") or ""),
                "formato": str(item.get("formato") or ""),
                "quantidade": quantity,
                "unidade": str(item.get("unidade") or "UN"),
                "preco_unitario": price,
                "subtotal": round(quantity * price, 2) if quantity and price else 0,
            }
        )
    return items


def _money_br(value: Any) -> str:
    return f"R$ {_safe_float(value):.2f}".replace(".", ",")


def _secretary_resolution_reply(resolution: dict | None) -> str:
    items = [
        item for item in (resolution or {}).get("itens") or [] if isinstance(item, dict)
    ]
    if not items:
        return "Não consegui identificar os produtos. Informe produto, formato, tamanho e quantidade."

    found = [item for item in items if item.get("status") == "encontrado"]
    pending = [item for item in items if item.get("status") != "encontrado"]
    found_lines = ["Pedido conferido:"]

    if found:
        found_lines += ["", "Encontrados:"]
    total_found = 0.0
    for index, item in enumerate(found, 1):
        product = str(item.get("nome_catalogo") or item.get("produto") or "Produto")
        code = item.get("cod_produto") or "-"
        size = item.get("tamanho") or item.get("formato") or "-"
        quantity = item.get("quantidade")
        unit = str(item.get("unidade") or "UN").lower()
        price = _safe_float(item.get("preco_unitario"))
        subtotal = _safe_float(item.get("subtotal"))
        if not subtotal and quantity is not None:
            subtotal = _safe_float(quantity) * price
        total_found += subtotal
        quantity_text = f"{quantity} {unit}" if quantity is not None else "falta quantidade"
        found_lines.append(
            f"{index}. {code} - {product} | {size} | {quantity_text} | "
            f"{_money_br(price)} | subtotal {_money_br(subtotal)}"
        )
    if found:
        found_lines.append(f"Total parcial encontrado: {_money_br(total_found)}")

    pending_lines = ["Pedido conferido:"]
    if pending:
        pending_lines += ["", "Não encontrados:"]
    for item in pending:
        product = str(item.get("produto") or item.get("nome_catalogo") or "Produto")
        requested = " ".join(
            str(item.get(key) or "") for key in ("formato", "tamanho")
        ).strip()
        if item.get("status") == "nao_encontrado":
            pending_lines.append(f"- {product}{f' | {requested}' if requested else ''}")
            suggestions = _filtered_suggestions(item)
            if suggestions:
                pending_lines.append("  Sugestoes na tabela:")
                for option in suggestions:
                    pending_lines.append(f"  - {option}")
        else:
            missing = ", ".join(item.get("faltando") or [])
            pending_lines.append(f"- {product}: falta confirmar {missing or 'a opcao exata'}")
            suggestions = _filtered_suggestions(item)
            if suggestions:
                pending_lines.append("  Sugestoes na tabela:")
                for option in suggestions:
                    pending_lines.append(f"  - {option}")

    if any(not item.get("quantidade") for item in found):
        found_lines += ["", "Informe a quantidade dos itens que ainda estão sem quantidade."]
    if pending:
        pending_lines += ["", "Me envie a correção dos itens não encontrados ou diga qual deles devo remover."]

    sections = []
    if found:
        sections.append("\n".join(found_lines))
    if pending:
        sections.append("\n".join(pending_lines))
    return REPLY_SPLIT_MARKER.join(sections)


def _order_summary(
    customer: dict,
    items: list[dict],
    observations: str = "",
    ask_confirmation: bool = True,
    sale_type_code: Any = None,
) -> str:
    lines = [f"Cliente: *{customer.get('name')}*"]
    if sale_type_code:
        lines += [f"Tipo: *{_sale_type_label(sale_type_code)}*"]
    lines += ["", "Pedido:"]
    total = 0.0
    for index, item in enumerate(items, 1):
        subtotal = _safe_float(item.get("subtotal"))
        total += subtotal
        lines.append(
            f"{index}. {item.get('nome')} | código {item.get('cod_produto')} | "
            f"{item.get('formato') or ''} {item.get('derivacao')} | "
            f"{_safe_float(item.get('quantidade')):g} {item.get('unidade')} | "
            f"R$ {_safe_float(item.get('preco_unitario')):.2f} | subtotal R$ {subtotal:.2f}"
        )
    lines += ["", f"Total: *R$ {total:.2f}*"]
    if observations:
        lines += ["", f"Observações: {observations}"]
    if ask_confirmation:
        lines += ["", "Se estiver correto, responda *sim*, *confirmo* ou *pode enviar* para enviar ao Senior ERP."]
    return "\n".join(lines).replace(".", ",")


def _new_protocol() -> str:
    return f"MSE-{datetime.now().strftime('%y%m%d')}-{uuid.uuid4().hex[:6].upper()}"


def _save_draft(db, conversation: dict, representative: dict, state: dict) -> dict:
    current_id = state.get("order_id")
    items = state.get("items") or []
    total = round(sum(_safe_float(item.get("subtotal")) for item in items), 2)
    customer = state["customer"]
    sale_type_code = _validated_sale_type_code(state.get("sale_type_code"))
    payload = {
        "conversation_id": conversation.get("id"),
        "instance_name": conversation.get("instance_name"),
        "cod_rep": int(representative["cod_rep"]),
        "representative_phone": conversation.get("representative_phone"),
        "customer_code": str(customer.get("code") or customer.get("document")),
        "customer_document": customer.get("document") or None,
        "customer_name": customer.get("name"),
        "price_table_code": customer.get("price_table_code") or None,
        "sale_type_code": sale_type_code,
        "items_json": items,
        "observations": state.get("observations") or "",
        "total": total,
        "status": "awaiting_confirmation",
        "updated_at": _now(),
    }
    if current_id:
        rows = db.table("secretary_orders").update(payload).eq("id", current_id).in_(
            "status", ["draft", "awaiting_confirmation", "failed"]
        ).execute().data or []
        if rows:
            return rows[0]
    protocol = _new_protocol()
    payload.update(
        {
            "protocol": protocol,
            "idempotency_key": f"secretary:{protocol}",
        }
    )
    rows = db.table("secretary_orders").insert(payload).execute().data or []
    return rows[0] if rows else payload


def _created_order_number(response: Any) -> str:
    if isinstance(response, list):
        for item in response:
            number = _created_order_number(item)
            if number:
                return number
        return ""
    if not isinstance(response, dict):
        return ""
    for key in ("numeroPedidoClicVenda", "numero", "numPed", "num_ped", "id"):
        if response.get(key) not in (None, ""):
            return str(response[key])
    for key in ("resultados", "body", "objeto", "pedido"):
        nested = response.get(key)
        number = _created_order_number(nested)
        if number:
            return number
    return ""


REQUISITION_LOGS_TABLE = "requisition_logs"
LEGACY_REQUISITION_LOGS_TABLE = "clic_request_logs"


def _requisition_log_create(db, order: dict, payload: dict) -> tuple[str | None, float]:
    started = time.perf_counter()
    is_senior = isinstance(payload, dict) and payload.get("provider") == "senior"
    record = {
        "source": "secretary_senior" if is_senior else "secretary",
        "operation": payload.get("operation") if is_senior else "create_order",
        "endpoint": payload.get("endpoint") if is_senior else "/extpedidos",
        "method": "POST",
        "status": "pending",
        "order_id": order.get("id"),
        "protocol": order.get("protocol"),
        "cod_rep": order.get("cod_rep"),
        "representative_document": order.get("representative_document"),
        "customer_code": order.get("customer_code"),
        "customer_document": order.get("customer_document"),
        "request_payload": payload,
        "created_at": _now(),
        "sent_at": _now(),
    }
    for table in (REQUISITION_LOGS_TABLE, LEGACY_REQUISITION_LOGS_TABLE):
        try:
            rows = db.table(table).insert(record).execute().data or []
            return (rows[0].get("id") if rows else None), started
        except Exception:
            continue
    return None, started


def _clic_error_payload(exc: Exception) -> tuple[int | None, dict | None, str]:
    response = getattr(exc, "response", None)
    status = getattr(response, "status_code", None)
    if response is None:
        return status, None, str(exc)
    try:
        body = response.json()
    except Exception:
        body = {"text": getattr(response, "text", "")}
    return status, body, str(exc)


def _clic_variation_code(value: Any) -> str:
    raw = str(value or "").strip()
    compact = raw.replace(" ", "").replace(",", ".")
    lower = compact.lower()
    if lower.endswith("ml") and lower[:-2].replace(".", "", 1).isdigit():
        number = lower[:-2]
        return str(int(float(number))) if "." in number else number
    if lower in {"5l", "5.0l"}:
        return "05L"
    if lower in {"1.7l", "17l"}:
        return "1L7"
    return compact.upper() if compact.lower().endswith("l") else compact


def _requisition_log_finish(
    db,
    log_id: str | None,
    started: float,
    status: str,
    response_payload: dict | None = None,
    http_status: int | None = None,
    error_message: str | None = None,
) -> None:
    if not log_id:
        return
    update = {
        "status": status,
        "http_status": http_status,
        "response_payload": response_payload,
        "error_message": error_message,
        "responded_at": _now(),
        "duration_ms": int((time.perf_counter() - started) * 1000),
    }
    for table in (REQUISITION_LOGS_TABLE, LEGACY_REQUISITION_LOGS_TABLE):
        try:
            db.table(table).update(update).eq("id", log_id).execute()
            return
        except Exception:
            continue


def _build_clic_order_payload(order: dict, representative_document: str | None = None) -> list[dict]:
    """Payload legado do ClicVendas, mantido para consulta/fallback manual."""
    sale_type_code = str(order.get("sale_type_code") or "").strip()
    if not sale_type_code:
        raise ValueError("Tipo de venda nao definido para envio ao ClicVendas.")
    rep_document = _digits(representative_document or order.get("representative_document"))
    if not rep_document:
        raise ValueError("Documento do representante nao definido para envio ao ClicVendas.")
    items = []
    for item in order.get("items_json") or []:
        items.append(
            {
                "codigoProduto": str(item.get("cod_produto") or ""),
                "codigoVariacao": _clic_variation_code(item.get("derivacao")),
                "quantidade": _safe_float(item.get("quantidade")),
                "precoVenda": _safe_float(item.get("preco_unitario")),
                "codigoTabelaPreco": str(order.get("price_table_code") or ""),
                "percentualDesconto": 0,
                "percentualAcrescimo": 0,
            }
        )
    return [
        {
            "numeroDocumentoCliente": str(order.get("customer_document") or ""),
            "numeroDocumentoRepresentante": rep_document,
            "codigoTipoVenda": sale_type_code,
            "itens": items,
        }
    ]


def _rep_order_base_items(order: dict) -> list[dict]:
    rows = []
    for item in order.get("items_json") or []:
        if not isinstance(item, dict):
            continue
        quantity = _safe_float(item.get("quantidade") or item.get("qtdPed"))
        unit_price = _safe_float(item.get("preco_unitario"))
        total = _safe_float(item.get("subtotal"))
        if not total and quantity and unit_price:
            total = round(quantity * unit_price, 2)
        rows.append(
            {
                "codPro": str(item.get("cod_produto") or item.get("codPro") or item.get("codigo") or ""),
                "codDer": str(item.get("derivacao") or item.get("variacao") or item.get("codDer") or ""),
                "desPro": str(item.get("nome") or item.get("produto") or item.get("nome_catalogo") or ""),
                "qtdPed": quantity,
                "vlrUnit": unit_price,
                "vlrTotal": total,
                "unidade": str(item.get("unidade") or "UN"),
            }
        )
    return rows


def _save_senior_order_to_rep_order_base(db, order: dict, number: str, result: Any) -> bool:
    if not number:
        return False
    try:
        cod_rep = int(order.get("cod_rep"))
    except (TypeError, ValueError):
        return False
    try:
        cod_cli = int(order.get("customer_code"))
    except (TypeError, ValueError):
        cod_cli = None
    now = _now()
    row = {
        "id": str(uuid.uuid4()),
        "cod_rep": cod_rep,
        "cod_cli": cod_cli,
        "customer_document": order.get("customer_document"),
        "customer_name": order.get("customer_name"),
        "rep_name": order.get("representative_name")
        or ("ELIEZER GONZAGA DOS REIS" if cod_rep == ELIEZER_FALLBACK_COD_REP else f"Representante {cod_rep}"),
        "num_ped": str(number),
        "dat_emi": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "sit_ped": str((getattr(result, "parsed", {}) or {}).get("sitPed") or "1"),
        "order_total_value": _safe_float(order.get("total")),
        "items_json": _rep_order_base_items(order),
        "has_items": bool(order.get("items_json")),
        "source": "senior_erp",
        "external_id": str(number),
        "observation": order.get("observations") or None,
        "origin_agent": "marcela_secretaria",
        "origin_order_id": order.get("id"),
        "origin_instance": order.get("instance_name"),
        "origin_cod_rep": cod_rep,
        "origin_protocol": order.get("protocol"),
        "erp_synced_at": now,
        "created_at": now,
        "updated_at": now,
    }
    try:
        db.table("rep_order_base").upsert(row, on_conflict="cod_rep,num_ped").execute()
        return True
    except Exception as exc:
        missing_optional = {
            "customer_document",
            "customer_name",
            "rep_name",
        }
        if not any(column in str(exc) for column in missing_optional):
            return False
        compatible_row = {
            key: value
            for key, value in row.items()
            if key not in missing_optional
        }
        try:
            db.table("rep_order_base").upsert(compatible_row, on_conflict="cod_rep,num_ped").execute()
            return True
        except Exception:
            return False


def _submit(db, order: dict) -> tuple[bool, str]:
    if order.get("status") in {"submitted", "synced"}:
        number = order.get("clic_order_number")
        return True, f"Esse pedido ja foi enviado{f' como numero {number}' if number else ''}."
    now = _now()
    claimed = db.table("secretary_orders").update(
        {"status": "submitting", "confirmed_at": now, "error_message": None, "updated_at": now}
    ).eq("id", order["id"]).in_("status", ["awaiting_confirmation", "failed"]).execute().data or []
    if not claimed:
        return False, "O pedido já está sendo processado. Aguarde a confirmação."
    order = claimed[0]
    try:
        senior_client = SeniorOrderClient()
        payload = senior_client.build_masked_payload(order)
    except ValueError as exc:
        db.table("secretary_orders").update(
            {"status": "failed", "error_message": str(exc), "updated_at": _now()}
        ).eq("id", order["id"]).execute()
        return False, str(exc)
    log_id, log_started = _requisition_log_create(db, order, payload)
    try:
        result = senior_client.submit_order(order)
        response = result.to_response_payload()
        _requisition_log_finish(
            db,
            log_id,
            log_started,
            "success" if result.ok else "error",
            response_payload=response,
            http_status=result.http_status,
            error_message=None if result.ok else (result.parsed.get("msgRet") or result.parsed.get("retorno")),
        )
        number = result.order_number
        db.table("secretary_orders").update(
            {
                "status": "submitted" if result.ok else "failed",
                "submit_payload": payload,
                "submit_response": response,
                "clic_order_number": number or None,
                "clic_external_id": number or None,
                "clic_status": str(result.parsed.get("sitPed") or "") or None,
                "error_message": None if result.ok else (result.parsed.get("msgRet") or result.parsed.get("retorno")),
                "submitted_at": now if result.ok else None,
                "updated_at": now,
            }
        ).eq("id", order["id"]).execute()
        if not result.ok:
            return False, f"Senior ERP retornou erro ao enviar o pedido.{f' Pedido numero {number}.' if number else ''}"
        if not number:
            db.table("secretary_orders").update(
                {
                    "status": "failed",
                    "error_message": "Senior ERP retornou sucesso sem numero de pedido.",
                    "updated_at": _now(),
                }
            ).eq("id", order["id"]).execute()
            return False, "Senior ERP retornou sucesso sem numero de pedido. Verifique os logs antes de reenviar."
        observation = str(order.get("observations") or "").strip()
        observation_error = None
        if observation:
            try:
                observation_payload = senior_client.build_masked_observation_payload(number, observation)
                obs_log_id, obs_log_started = _requisition_log_create(db, order, observation_payload)
                obs_result = senior_client.submit_observation(number, observation)
                observation_response = obs_result.to_response_payload()
                response["inserirObservacoes"] = observation_response
                _requisition_log_finish(
                    db,
                    obs_log_id,
                    obs_log_started,
                    "success" if obs_result.ok else "error",
                    response_payload=observation_response,
                    http_status=obs_result.http_status,
                    error_message=None
                    if obs_result.ok
                    else (obs_result.parsed.get("mensagemErro") or obs_result.parsed.get("erroExecucao")),
                )
                if not obs_result.ok:
                    observation_error = (
                        obs_result.parsed.get("mensagemErro")
                        or obs_result.parsed.get("erroExecucao")
                        or "Senior não confirmou a observação."
                    )
            except Exception as exc:
                status, body, message = _clic_error_payload(exc)
                response["inserirObservacoes"] = {
                    "http_status": status,
                    "senior": body,
                    "error": message,
                }
                observation_error = message
                try:
                    _requisition_log_finish(
                        db,
                        locals().get("obs_log_id"),
                        locals().get("obs_log_started", time.perf_counter()),
                        "error",
                        response_payload=body,
                        http_status=status,
                        error_message=message,
                    )
                except Exception:
                    pass
            db.table("secretary_orders").update(
                {
                    "submit_response": response,
                    "error_message": f"Pedido enviado, mas observação não foi gravada no Senior: {observation_error}"
                    if observation_error
                    else None,
                    "updated_at": _now(),
                }
            ).eq("id", order["id"]).execute()
        mirrored = _save_senior_order_to_rep_order_base(db, order, number, result)
        if not mirrored:
            db.table("secretary_orders").update(
                {
                    "error_message": "Pedido enviado ao Senior, mas não foi espelhado em rep_order_base.",
                    "updated_at": _now(),
                }
            ).eq("id", order["id"]).execute()
        if observation_error:
            return True, f"Pedido enviado ao Senior ERP com sucesso. Pedido número *{number}*. A observação não foi gravada: {observation_error}"
        if observation:
            return True, f"Pedido enviado ao Senior ERP com sucesso. Pedido numero *{number}*. Observacao enviada junto."
        return True, f"Pedido enviado ao Senior ERP com sucesso. Pedido numero *{number}*."
    except Exception as exc:
        http_status, response_payload, error_message = _clic_error_payload(exc)
        _requisition_log_finish(
            db,
            log_id,
            log_started,
            "error",
            response_payload=response_payload,
            http_status=http_status,
            error_message=error_message,
        )
        db.table("secretary_orders").update(
            {
                "status": "failed",
                "submit_payload": payload,
                "submit_response": response_payload,
                "error_message": error_message,
                "updated_at": _now(),
            }
        ).eq("id", order["id"]).execute()
        return False, "Não consegui enviar o pedido ao Senior ERP. Ele ficou salvo para uma nova tentativa."


def _latest_orders(db, cod_rep: int, limit: int = 5) -> str:
    rows = (
        db.table("rep_order_base")
        .select("num_ped,cod_cli,dat_emi,sit_ped,order_total_value,origin_protocol")
        .eq("cod_rep", cod_rep)
        .order("dat_emi", desc=True)
        .limit(limit)
        .execute()
        .data
        or []
    )
    if not rows:
        return "Não encontrei pedidos sincronizados para sua carteira."
    profiles = _customer_profiles(db)
    lines = ["Pedidos mais recentes:"]
    for row in rows:
        total = _safe_float(row.get("order_total_value"))
        origin = f" | {row.get('origin_protocol')}" if row.get("origin_protocol") else ""
        customer_code = str(row.get("cod_cli") or "")
        profile = profiles.get(customer_code) or {}
        customer_name = (
            profile.get("nome")
            or profile.get("fantasia")
            or profile.get("razao_social")
            or f"Cliente {customer_code or '-'}"
        )
        lines.append(
            f"- {row.get('num_ped')} | {customer_name} | "
            f"{row.get('sit_ped') or '-'} | R$ {total:.2f}{origin}"
        )
    return "\n".join(lines).replace(".", ",")


def process_secretary_message(
    phone: str,
    text: str,
    instance_name: str,
    external_message_id: str | None = None,
    payload_json: dict | None = None,
) -> dict:
    db = _db()
    representative = _representative(db, phone)
    if not representative:
        return {
            "action": "secretary_unauthorized",
            "should_reply": True,
            "reply": "Este número não está cadastrado como representante autorizado. Solicite o vínculo do seu WhatsApp ao administrador.",
        }
    conversation = _conversation(db, instance_name, phone, int(representative["cod_rep"]))
    if not _add_message(
        db,
        str(conversation["id"]),
        "user",
        text,
        external_message_id=external_message_id,
        payload=payload_json,
    ):
        return {"action": "ignored_duplicate_message", "should_reply": False}

    state = dict(conversation.get("state_json") or {})
    reply = ""
    action = "secretary_reply"
    brain = analyze_secretary_message(text, state)
    if (
        (state.get("awaiting_observation") or state.get("awaiting_observation_text"))
        and brain.get("looks_like_product")
    ):
        state.pop("awaiting_observation", None)
        state.pop("awaiting_observation_text", None)
        state["observations"] = state.get("observations") or ""
        state["observation_step_done"] = True

    def save_current_draft(current_state: dict) -> dict:
        return _save_draft(db, conversation, representative, current_state)

    def load_current_order(order_id: str) -> dict | None:
        rows = db.table("secretary_orders").select("*").eq("id", order_id).limit(1).execute().data or []
        return rows[0] if rows else None

    if (
        state.get("pending_action")
        and brain.get("keep_current_customer")
        and brain.get("looks_like_product")
        and state.get("customer")
    ):
        state.pop("pending_action", None)
        text = str(brain.get("product_text") or text)
        brain = analyze_secretary_message(text, state)
        action = "secretary_kept_current_order"

    if _status_request_message(text) and not _sale_type_code_from_text(text) and not state.get("items"):
        reply = _latest_orders(db, int(representative["cod_rep"]))
        action = "secretary_status"
    elif CANCEL_RE.search(text):
        _cancel_current_draft(db, state)
        state = {}
        reply = "Pedido cancelado. Quando quiser, informe o cliente para iniciar outro."
        action = "secretary_cancelled"
    elif state.get("awaiting_observation") or state.get("awaiting_observation_text"):
        observation_result = _handle_observation_response(text, state, save_current_draft)
        if observation_result:
            reply, action = observation_result
        else:
            reply = "Pode me dizer a observação, ou responder *não* para seguir sem observação."
            action = "secretary_ask_observation"
    else:
        observation_edit_result = _handle_observation_edit_request(text, state, save_current_draft)
        if observation_edit_result:
            reply, action = observation_edit_result

    if not reply and state.get("pending_action"):
        pending = state.get("pending_action") or {}
        if pending.get("type") == "change_customer_pending_code" and not KEEP_CURRENT_RE.search(text):
            customers = _portfolio_customers(db, int(representative["cod_rep"]))
            options = state.get("customer_options") or []
            selection = re.fullmatch(r"\s*([1-5])\s*", text)
            matches = []
            if selection and options:
                index = int(selection.group(1)) - 1
                if index < len(options):
                    matches = [options[index]]
                    state.pop("customer_options", None)
            if not matches:
                matches = _search_customers(customers, text)
            if len(matches) == 1:
                candidate = matches[0]
                state["pending_action"] = {
                    "type": "change_customer",
                    "customer": candidate,
                    "prompt": (
                        f"Encontrei *{candidate.get('name')}*. "
                        "Confirmo a troca de cliente e limpo os itens do pedido atual?"
                    ),
                }
                reply = state["pending_action"]["prompt"]
                action = "secretary_confirm_customer_change"
            elif matches:
                state["customer_options"] = matches
                reply = "Encontrei mais de um cliente. Responda com o numero correto:\n\n" + "\n".join(
                    _masked_customer(customer, index)
                    for index, customer in enumerate(matches, 1)
                )
            else:
                reply = "Não encontrei esse cliente na sua carteira. Informe código, nome, documento ou cidade."
        elif KEEP_CURRENT_RE.search(text):
            state.pop("pending_action", None)
            reply = "Certo, mantive o pedido atual. Pode continuar com os itens ou ajustes desse pedido."
            action = "secretary_kept_current_order"
        elif CONFIRM_RE.search(text) or re.search(r"\b(sim|pode|trocar|recomecar|recomeçar)\b", _norm(text)):
            previous_state = dict(state)
            if pending.get("type") == "reset_order":
                state = _clear_order_state(db, state, keep_sale_type=False)
                reply = "Certo, apaguei o rascunho atual. Informe o cliente do novo pedido."
                action = "secretary_order_reset"
            elif pending.get("type") == "change_customer" and pending.get("customer"):
                state = _clear_order_state(db, state, keep_sale_type=True)
                state.update(_start_customer_state(pending["customer"], previous_state))
                reply = (
                    f"Troquei para o cliente *{state['customer']['name']}* e limpei os itens do pedido anterior. "
                    f"{_next_order_step_message(state, 'Agora envie os produtos e quantidades desse pedido.')}"
                )
                action = "secretary_customer_changed"
            else:
                state.pop("pending_action", None)
                reply = "Certo. Informe o código, nome ou documento do cliente correto."
        else:
            reply = pending.get("prompt") or "Confirme se quer continuar com essa mudanca ou manter o pedido atual."
    if not reply and CONFIRM_RE.search(text):
        try:
            tool_result = submit_order_tool(
                state=state,
                load_order=load_current_order,
                save_draft=save_current_draft,
                submit=lambda order: _submit(db, order),
            )
            state = tool_result.state
            reply = tool_result.reply
            action = tool_result.action
        except ValueError as exc:
            reply = str(exc)
    if not reply:
        sale_type_code = _sale_type_code_from_text(text)
        if sale_type_code:
            state["sale_type_code"] = sale_type_code
        sale_type_only = bool(sale_type_code and (brain.get("sale_type_only") or _sale_type_only_message(text)))
        customers = []
        if not state.get("customer") and sale_type_only:
            reply = _start_conversation_reply(state, representative)
            action = "secretary_sale_type_selected"
        elif not state.get("customer") and _generic_chat_message(text):
            reply = _start_conversation_reply(state, representative)
            action = "secretary_greeting"

        if not reply:
            customers = _portfolio_customers(db, int(representative["cod_rep"]))
        if not reply and NEW_ORDER_RE.search(text) and _has_order_context(state):
            state["pending_action"] = {
                "type": "reset_order",
                "prompt": "Voce quer apagar o pedido atual e comecar um novo? Responda *confirmo* para apagar ou *continuar* para manter.",
            }
            reply = state["pending_action"]["prompt"]
            action = "secretary_confirm_reset"
        elif not reply and state.get("customer"):
            if sale_type_only:
                tool_result = select_sale_type_tool(
                    state,
                    sale_type_code,
                    _sale_type_label,
                    _order_summary,
                    save_current_draft,
                )
                state = tool_result.state
                reply = tool_result.reply
                action = tool_result.action
            elif _summary_request_message(text) and state.get("items"):
                tool_result = show_summary_tool(state, _order_summary)
                state = tool_result.state
                reply = tool_result.reply
                action = tool_result.action
            candidate = None if reply or brain.get("looks_like_product") else _customer_change_candidate(customers, text, state.get("customer"))
            if not reply and candidate:
                state["pending_action"] = {
                    "type": "change_customer",
                    "customer": candidate,
                    "prompt": (
                        f"Entendi que talvez você queira trocar o cliente para *{candidate.get('name')}*. "
                        "Se trocar, eu limpo os itens do pedido atual. Responda *confirmo* para trocar ou *continuar* para manter o pedido atual."
                    ),
                }
                reply = state["pending_action"]["prompt"]
                action = "secretary_confirm_customer_change"
            elif not reply and CHANGE_CUSTOMER_RE.search(text):
                state["pending_action"] = {
                    "type": "change_customer_pending_code",
                    "prompt": "Qual é o código, nome ou documento do cliente correto?",
                }
                reply = state["pending_action"]["prompt"]
                action = "secretary_ask_new_customer"
        if not reply and not state.get("customer"):
            options = state.get("customer_options") or []
            selection = re.fullmatch(r"\s*([1-5])\s*", text)
            if selection and options:
                index = int(selection.group(1)) - 1
                if index < len(options):
                    state.update(_start_customer_state(options[index], state))
                    state.pop("customer_options", None)
                    reply = (
                        f"Cliente *{state['customer']['name']}* selecionado. "
                        f"{_next_order_step_message(state)}"
                    )
            if not reply:
                query = text.strip()
                matches = _search_customers(customers, query)
                if len(matches) == 1:
                    state.update(_start_customer_state(matches[0], state))
                    reply = (
                        f"Cliente *{matches[0]['name']}* selecionado. "
                        f"{_next_order_step_message(state)}"
                    )
                elif matches:
                    state["customer_options"] = matches
                    reply = "Encontrei mais de um cliente. Responda com o numero correto:\n\n" + "\n".join(
                        _masked_customer(customer, index)
                        for index, customer in enumerate(matches, 1)
                    )
                else:
                    reply = (
                        "Ainda não consegui localizar esse cliente na sua carteira. "
                        "Me envie o código do cliente, CNPJ/CPF, nome ou cidade que eu procuro de novo."
                    )
        elif not reply:
            customer = state["customer"]
            if sale_type_only:
                tool_result = select_sale_type_tool(
                    state,
                    sale_type_code,
                    _sale_type_label,
                    _order_summary,
                    save_current_draft,
                )
                state = tool_result.state
                reply = tool_result.reply
                action = tool_result.action
            elif _summary_request_message(text) and state.get("items"):
                tool_result = show_summary_tool(state, _order_summary)
                state = tool_result.state
                reply = tool_result.reply
                action = tool_result.action
            else:
                tool_result = resolve_products_tool(
                    text=text,
                    state=state,
                    customer=customer,
                    catalog_lookup=lambda selected_customer: _catalog(db, selected_customer),
                    resolver=_resolve_products_with_sales_subagent,
                    drop_resolved_pending_items=_drop_resolved_pending_items,
                    resolution_items=_resolution_items,
                    safe_float=_safe_float,
                    resolution_reply=_secretary_resolution_reply,
                    suggestions_enricher=_augment_resolution_suggestions,
                    save_draft=save_current_draft,
                    order_summary=_order_summary,
                )
                state = tool_result.state
                reply = tool_result.reply
                action = tool_result.action

    _save_state(db, str(conversation["id"]), state)
    _add_message(db, str(conversation["id"]), "assistant", reply, payload={"action": action})
    return {
        "action": action,
        "should_reply": bool(reply),
        "reply": reply,
        "cod_rep": representative.get("cod_rep"),
    }


def _dashboard_date_to(value: str | None) -> str | None:
    if not value:
        return None
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return (datetime.strptime(value, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
    return value


def secretary_metrics(
    date_from: str | None = None,
    date_to: str | None = None,
    cod_rep: int | None = None,
) -> dict:
    db = _db()
    query = db.table("secretary_orders").select("*")
    if date_from:
        query = query.gte("created_at", date_from)
    end_date = _dashboard_date_to(date_to)
    if end_date:
        query = query.lt("created_at", end_date)
    if cod_rep is not None:
        query = query.eq("cod_rep", cod_rep)
    rows = query.order("created_at", desc=True).execute().data or []
    statuses: dict[str, int] = {}
    total_value = 0.0
    sent = []
    products: dict[str, dict] = {}
    daily: dict[str, dict] = {}
    representative_totals: dict[int, dict] = {}
    customers: set[str] = set()
    representatives: set[int] = set()
    instances: set[str] = set()
    for row in rows:
        status = str(row.get("status") or "")
        statuses[status] = statuses.get(status, 0) + 1
        created_day = str(row.get("created_at") or "")[:10]
        day = daily.setdefault(created_day, {"date": created_day, "started": 0, "sent": 0, "value": 0.0})
        day["started"] += 1
        cod_rep = int(row.get("cod_rep") or 0)
        rep = representative_totals.setdefault(
            cod_rep,
            {"cod_rep": cod_rep, "name": f"Representante {cod_rep}", "orders": 0, "value": 0.0},
        )
        if status in {"submitted", "synced"}:
            sent.append(row)
            row_total = _safe_float(row.get("total"))
            total_value += row_total
            day["sent"] += 1
            day["value"] += row_total
            rep["orders"] += 1
            rep["value"] += row_total
            for item in row.get("items_json") or []:
                code = str(item.get("cod_produto") or item.get("nome"))
                entry = products.setdefault(
                    code,
                    {
                        "code": item.get("cod_produto"),
                        "name": item.get("nome"),
                        "quantity": 0.0,
                        "value": 0.0,
                    },
                )
                entry["quantity"] += _safe_float(item.get("quantidade"))
                entry["value"] += _safe_float(item.get("subtotal"))
        customers.add(str(row.get("customer_code") or ""))
        if cod_rep:
            representatives.add(cod_rep)
        instances.add(str(row.get("instance_name") or ""))

    if representatives:
        rep_rows = (
            db.table("representatives")
            .select("cod_rep,name")
            .in_("cod_rep", list(representatives))
            .execute()
            .data
            or []
        )
        for rep_row in rep_rows:
            cod_rep = int(rep_row.get("cod_rep") or 0)
            if cod_rep in representative_totals and rep_row.get("name"):
                representative_totals[cod_rep]["name"] = rep_row["name"]

    return {
        "orders_started": len(rows),
        "orders_confirmed": sum(1 for row in rows if row.get("confirmed_at")),
        "orders_sent": len(sent),
        "orders_synced": statuses.get("synced", 0),
        "orders_failed": statuses.get("failed", 0),
        "total_value": round(total_value, 2),
        "average_ticket": round(total_value / len(sent), 2) if sent else 0,
        "customers": len(customers - {""}),
        "representatives": len(representatives),
        "instances": len(instances - {""}),
        "status_breakdown": statuses,
        "products": sorted(products.values(), key=lambda row: row["value"], reverse=True),
        "daily": sorted(daily.values(), key=lambda row: row["date"]),
        "representative_totals": sorted(
            (row for code, row in representative_totals.items() if code),
            key=lambda row: row["value"],
            reverse=True,
        ),
    }


def secretary_dashboard(
    date_from: str | None = None,
    date_to: str | None = None,
    status: str | None = None,
    search: str | None = None,
    page: int = 1,
    page_size: int = 25,
    cod_rep: int | None = None,
) -> dict:
    db = _db()
    query = db.table("secretary_orders").select(
        "id,protocol,instance_name,cod_rep,representative_phone,customer_code,"
        "customer_name,items_json,total,status,clic_order_number,clic_status,"
        "error_message,confirmed_at,submitted_at,synced_at,created_at,updated_at"
    )
    if date_from:
        query = query.gte("created_at", date_from)
    end_date = _dashboard_date_to(date_to)
    if end_date:
        query = query.lt("created_at", end_date)
    if status:
        query = query.eq("status", status)
    if cod_rep is not None:
        query = query.eq("cod_rep", cod_rep)

    rows = query.order("created_at", desc=True).limit(5000).execute().data or []
    if search:
        needle = _norm(search)
        rows = [
            row
            for row in rows
            if needle
            in _norm(
                " ".join(
                    [
                        str(row.get("protocol") or ""),
                        str(row.get("customer_code") or ""),
                        str(row.get("customer_name") or ""),
                        str(row.get("cod_rep") or ""),
                        str(row.get("clic_order_number") or ""),
                    ]
                )
            )
        ]

    total = len(rows)
    safe_page_size = min(max(int(page_size or 25), 1), 100)
    safe_page = max(int(page or 1), 1)
    start = (safe_page - 1) * safe_page_size
    page_rows = rows[start : start + safe_page_size]
    return {
        "metrics": secretary_metrics(date_from, date_to, cod_rep),
        "orders": page_rows,
        "total": total,
        "page": safe_page,
        "page_size": safe_page_size,
        "pages": max(1, (total + safe_page_size - 1) // safe_page_size),
        "updated_at": _now(),
    }
