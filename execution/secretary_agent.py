"""
Atendimento da Marcela Secretaria para representantes em uma instancia central.

O modulo mantem estado separado do agente de vendas e somente envia pedidos
depois de uma confirmacao explicita do representante.
"""

from __future__ import annotations

import json
import os
import re
import unicodedata
import uuid
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from clic_vendas_client import ClicVendasClient
from ai_agent import (
    _reconcile_catalog_resolution,
    resolve_order_with_subagent,
)

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

CONFIRM_RE = re.compile(r"\b(confirmo|confirmado|pode enviar|pode mandar|pode fechar|esta tudo certo|est[aá] certo)\b", re.I)
CANCEL_RE = re.compile(r"\b(cancelar|cancela|desistir|apagar pedido)\b", re.I)
STATUS_RE = re.compile(r"\b(status|situa[cç][aã]o|acompanhar|pedidos?|hist[oó]rico|atualiza[cç][aã]o)\b", re.I)
REFERENCE_RE = re.compile(r"\bMSE-\d{6}-[A-Z0-9]{6}\b", re.I)


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
    return [item for item in values if item]


def _allowed_secretary_phones() -> set[str]:
    raw = os.getenv("SECRETARY_ALLOWED_PHONES", "").strip()
    if not raw:
        return set()
    allowed: set[str] = set()
    for item in re.split(r"[,;\s]+", raw):
        for candidate in _phone_candidates(item):
            allowed.add(candidate)
    return allowed


def _is_secretary_phone_allowed(phone: str) -> bool:
    allowed = _allowed_secretary_phones()
    if not allowed:
        return True
    return bool(set(_phone_candidates(phone)) & allowed)


def _representative(db, phone: str) -> dict | None:
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
    return active[0] if len(active) == 1 else None


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


def _portfolio_customers(db, cod_rep: int) -> list[dict]:
    rows = (
        db.table("clic_pedidos_integrados")
        .select("raw_json,criado_em")
        .order("criado_em", desc=True)
        .limit(5000)
        .execute()
        .data
        or []
    )
    result: dict[str, dict] = {}
    for row in rows:
        raw = row.get("raw_json") or {}
        representative = raw.get("representante") or raw.get("autor") or {}
        backoffice = representative.get("backoffice") if isinstance(representative, dict) else {}
        try:
            row_rep = int(
                (backoffice or {}).get("codigo")
                or representative.get("codigo")
                or (representative.get("acesso") or {}).get("login")
            )
        except (TypeError, ValueError):
            continue
        if row_rep != cod_rep:
            continue
        customer = _customer_from_raw(raw)
        key = customer["code"] or customer["document"]
        if key and key not in result:
            result[key] = customer
    return list(result.values())


def _customer_score(customer: dict, query: str) -> float:
    wanted = _norm(query)
    if not wanted:
        return 0
    haystacks = [
        _norm(customer.get("name")),
        _norm(customer.get("city")),
        _digits(customer.get("code")),
        _digits(customer.get("document")),
    ]
    if any(wanted == value for value in haystacks if value):
        return 1.0
    if any(wanted in value for value in haystacks if value):
        return 0.92
    return max((SequenceMatcher(None, wanted, value).ratio() for value in haystacks if value), default=0)


def _search_customers(customers: list[dict], query: str) -> list[dict]:
    query = re.sub(
        r"^\s*(?:cliente|para\s+o\s+cliente|pedido\s+para)\s+",
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
                "derivacao": str(item.get("tamanho") or ""),
                "formato": str(item.get("formato") or ""),
                "quantidade": quantity,
                "unidade": str(item.get("unidade") or "UN"),
                "preco_unitario": price,
                "subtotal": round(quantity * price, 2) if quantity and price else 0,
            }
        )
    return items


def _secretary_resolution_reply(resolution: dict | None) -> str:
    items = [
        item for item in (resolution or {}).get("itens") or [] if isinstance(item, dict)
    ]
    if not items:
        return "Nao consegui identificar os produtos. Informe produto, formato, tamanho e quantidade."
    lines = ["Conferi os produtos na tabela oficial do cliente:"]
    for item in items:
        lines.append("")
        product = str(item.get("produto") or item.get("nome_catalogo") or "Produto")
        if item.get("status") == "encontrado":
            quantity = item.get("quantidade")
            unit = item.get("unidade") or "UN"
            lines.extend(
                [
                    f"- *{item.get('nome_catalogo') or product}*",
                    f"  Codigo: *{item.get('cod_produto') or '-'}*",
                    f"  Formato/tamanho: {item.get('formato') or '-'} {item.get('tamanho') or '-'}",
                    f"  Quantidade: {quantity if quantity is not None else 'falta informar'} {unit}",
                    f"  Preco unitario: R$ {_safe_float(item.get('preco_unitario')):.2f}",
                ]
            )
            continue
        requested = " ".join(
            str(item.get(key) or "") for key in ("formato", "tamanho")
        ).strip()
        if item.get("status") == "nao_encontrado":
            lines.append(f"- Nao encontrei *{product}*{f' em {requested}' if requested else ''}.")
        else:
            missing = ", ".join(item.get("faltando") or [])
            lines.append(f"- Preciso confirmar {missing or 'a opcao exata'} de *{product}*.")
        alternatives = item.get("alternativas") or []
        if alternatives:
            lines.append("  Opcoes reais:")
            lines.extend(f"  - {option}" for option in alternatives[:8])
    if any(item.get("status") != "encontrado" for item in items):
        lines += ["", "Responda somente com a opcao correta dos itens pendentes."]
    elif any(not item.get("quantidade") for item in items):
        lines += ["", "Informe a quantidade dos itens que ainda estao sem quantidade."]
    return "\n".join(lines).replace(".", ",")


def _order_summary(customer: dict, items: list[dict], observations: str = "") -> str:
    lines = [f"Cliente: *{customer.get('name')}*", "", "Pedido:"]
    total = 0.0
    for index, item in enumerate(items, 1):
        subtotal = _safe_float(item.get("subtotal"))
        total += subtotal
        lines.append(
            f"{index}. {item.get('nome')} | codigo {item.get('cod_produto')} | "
            f"{item.get('formato') or ''} {item.get('derivacao')} | "
            f"{_safe_float(item.get('quantidade')):g} {item.get('unidade')} | "
            f"R$ {_safe_float(item.get('preco_unitario')):.2f} | subtotal R$ {subtotal:.2f}"
        )
    lines += ["", f"Total: *R$ {total:.2f}*"]
    if observations:
        lines += ["", f"Observacoes: {observations}"]
    lines += ["", "Se estiver correto, responda *confirmo* para enviar ao ClicVendas."]
    return "\n".join(lines).replace(".", ",")


def _new_protocol() -> str:
    return f"MSE-{datetime.now().strftime('%y%m%d')}-{uuid.uuid4().hex[:6].upper()}"


def _save_draft(db, conversation: dict, representative: dict, state: dict) -> dict:
    current_id = state.get("order_id")
    items = state.get("items") or []
    total = round(sum(_safe_float(item.get("subtotal")) for item in items), 2)
    customer = state["customer"]
    payload = {
        "conversation_id": conversation.get("id"),
        "instance_name": conversation.get("instance_name"),
        "cod_rep": int(representative["cod_rep"]),
        "representative_phone": conversation.get("representative_phone"),
        "customer_code": str(customer.get("code") or customer.get("document")),
        "customer_document": customer.get("document") or None,
        "customer_name": customer.get("name"),
        "price_table_code": customer.get("price_table_code") or None,
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


def _created_order_number(response: dict) -> str:
    for key in ("numero", "numPed", "num_ped", "id"):
        if response.get(key) not in (None, ""):
            return str(response[key])
    nested = response.get("pedido") if isinstance(response.get("pedido"), dict) else {}
    return _created_order_number(nested) if nested else ""


def _submit(db, order: dict) -> tuple[bool, str]:
    if order.get("status") in {"submitted", "synced"}:
        number = order.get("clic_order_number")
        return True, f"Esse pedido ja foi enviado{f' como numero {number}' if number else ''}."
    now = _now()
    claimed = db.table("secretary_orders").update(
        {"status": "submitting", "confirmed_at": now, "error_message": None, "updated_at": now}
    ).eq("id", order["id"]).in_("status", ["awaiting_confirmation", "failed"]).execute().data or []
    if not claimed:
        return False, "O pedido ja esta sendo processado. Aguarde a confirmacao."
    order = claimed[0]
    marker = f"Origem: Marcela Secretaria | Ref: {order['protocol']}"
    observations = " | ".join(part for part in (marker, order.get("observations")) if part)
    items = []
    for item in order.get("items_json") or []:
        row = {
            "produto": {"backoffice": {"codigo": item.get("cod_produto")}},
            "quantidade": _safe_float(item.get("quantidade")),
            "derivacao": item.get("derivacao"),
            "precoUnitario": _safe_float(item.get("preco_unitario")),
            "valorTotal": _safe_float(item.get("subtotal")),
        }
        items.append(row)
    payload = {
        "cliente": {"backoffice": {"codigo": order["customer_code"]}},
        "representante": {"backoffice": {"codigo": order["cod_rep"]}},
        "itens": items,
        "situacao": {"id": "aprovado"},
        "observacao": observations,
        "totais": {"valorTotalLiquido": _safe_float(order.get("total"))},
    }
    try:
        response = ClicVendasClient().post("/extpedidos", payload)
        number = _created_order_number(response)
        db.table("secretary_orders").update(
            {
                "status": "submitted",
                "submit_payload": payload,
                "submit_response": response,
                "clic_order_number": number or None,
                "clic_external_id": str(response.get("_id") or response.get("id") or "") or None,
                "submitted_at": now,
                "updated_at": now,
            }
        ).eq("id", order["id"]).execute()
        detail = f" Pedido numero *{number}*." if number else f" Referencia *{order['protocol']}*."
        return True, f"Pedido enviado ao ClicVendas com sucesso.{detail}"
    except Exception as exc:
        db.table("secretary_orders").update(
            {
                "status": "failed",
                "submit_payload": payload,
                "error_message": str(exc),
                "updated_at": _now(),
            }
        ).eq("id", order["id"]).execute()
        return False, "Nao consegui enviar o pedido ao ClicVendas. Ele ficou salvo para uma nova tentativa."


def _latest_orders(db, cod_rep: int, limit: int = 5) -> str:
    rows = (
        db.table("rep_order_base")
        .select("num_ped,dat_emi,sit_ped,order_total_value,customer_name,origin_protocol")
        .eq("cod_rep", cod_rep)
        .order("dat_emi", desc=True)
        .limit(limit)
        .execute()
        .data
        or []
    )
    if not rows:
        return "Nao encontrei pedidos sincronizados para sua carteira."
    lines = ["Pedidos mais recentes:"]
    for row in rows:
        total = _safe_float(row.get("order_total_value"))
        origin = f" | {row.get('origin_protocol')}" if row.get("origin_protocol") else ""
        lines.append(
            f"- {row.get('num_ped')} | {row.get('customer_name') or 'Cliente'} | "
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
    if not _is_secretary_phone_allowed(phone):
        return {
            "action": "secretary_phone_not_allowed",
            "should_reply": False,
        }

    db = _db()
    representative = _representative(db, phone)
    if not representative:
        return {
            "action": "secretary_unauthorized",
            "should_reply": True,
            "reply": "Este numero nao esta cadastrado como representante autorizado. Solicite o vinculo do seu WhatsApp ao administrador.",
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

    if STATUS_RE.search(text) and not state.get("items"):
        reply = _latest_orders(db, int(representative["cod_rep"]))
        action = "secretary_status"
    elif CANCEL_RE.search(text):
        if state.get("order_id"):
            db.table("secretary_orders").update(
                {"status": "cancelled", "updated_at": _now()}
            ).eq("id", state["order_id"]).in_(
                "status", ["draft", "awaiting_confirmation", "failed"]
            ).execute()
        state = {}
        reply = "Pedido cancelado. Quando quiser, informe o cliente para iniciar outro."
        action = "secretary_cancelled"
    elif CONFIRM_RE.search(text):
        order_id = state.get("order_id")
        if not order_id or not state.get("ready_to_submit"):
            reply = "Nao ha pedido pronto para confirmacao. Informe primeiro o cliente e os itens."
        else:
            rows = db.table("secretary_orders").select("*").eq("id", order_id).limit(1).execute().data or []
            if not rows:
                reply = "Nao encontrei o rascunho desse pedido."
            else:
                _, reply = _submit(db, rows[0])
                state = {}
                action = "secretary_submitted"
    else:
        customers = _portfolio_customers(db, int(representative["cod_rep"]))
        if not state.get("customer"):
            options = state.get("customer_options") or []
            selection = re.fullmatch(r"\s*([1-5])\s*", text)
            if selection and options:
                index = int(selection.group(1)) - 1
                if index < len(options):
                    state["customer"] = options[index]
                    state.pop("customer_options", None)
                    reply = (
                        f"Cliente *{state['customer']['name']}* selecionado. "
                        "Agora envie os produtos e quantidades do pedido."
                    )
            if not reply:
                query = text.strip()
                matches = _search_customers(customers, query)
                if len(matches) == 1:
                    state["customer"] = matches[0]
                    reply = (
                        f"Cliente *{matches[0]['name']}* selecionado. "
                        "Agora envie os produtos e quantidades do pedido."
                    )
                elif matches:
                    state["customer_options"] = matches
                    reply = "Encontrei mais de um cliente. Responda com o numero correto:\n\n" + "\n".join(
                        _masked_customer(customer, index)
                        for index, customer in enumerate(matches, 1)
                    )
                else:
                    reply = "Nao encontrei esse cliente na sua carteira. Informe nome, codigo, documento ou cidade."
        else:
            customer = state["customer"]
            catalog = _catalog(db, customer)
            if not catalog:
                reply = "Nao encontrei a tabela de precos desse cliente. O pedido nao pode ser enviado sem essa validacao."
            else:
                resolution = _resolve_products_with_sales_subagent(text, catalog, state)
                if not resolution:
                    reply = "Nao consegui identificar os produtos. Informe produto, formato, tamanho e quantidade."
                else:
                    current = _resolution_items(resolution)
                    issues = [
                        item
                        for item in resolution.get("itens") or []
                        if isinstance(item, dict) and item.get("status") != "encontrado"
                    ]
                    missing_quantities = [
                        item for item in current if _safe_float(item.get("quantidade")) <= 0
                    ]
                    if issues or missing_quantities:
                        reply = _secretary_resolution_reply(resolution)
                        state["items"] = current
                        state["ready_to_submit"] = False
                        state["product_history"].append(
                            {"role": "assistant", "content": reply}
                        )
                    else:
                        state["items"] = current
                        order = _save_draft(db, conversation, representative, state)
                        state["order_id"] = order.get("id")
                        state["protocol"] = order.get("protocol")
                        state["ready_to_submit"] = True
                        reply = _order_summary(
                            customer,
                            current,
                            state.get("observations") or "",
                        )
                        state["product_history"].append(
                            {"role": "assistant", "content": reply}
                        )

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
