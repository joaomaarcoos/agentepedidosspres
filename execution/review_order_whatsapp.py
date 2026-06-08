from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

logger = logging.getLogger(__name__)

OWNER_KEY_PREFIX = "evolution_instance_owner__"
APPROVE_RE = re.compile(r"\b(?:aprovar|aprova|aprovado|enviar|manda|mandar)\b.*?\b(SP-\d{6}-[A-Z0-9]{6})\b", re.I)
CANCEL_RE = re.compile(r"\b(?:cancelar|cancela|recusar|reprovar)\b.*?\b(SP-\d{6}-[A-Z0-9]{6})\b", re.I)


def normalize_phone(value: str | None) -> str:
    digits = re.sub(r"\D", "", str(value or ""))
    if not digits:
        return ""
    if len(digits) in (10, 11):
        return f"55{digits}"
    return digits


def _db():
    url = os.getenv("SUPABASE_URL", "").rstrip("/")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_ANON_KEY", "")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY não configurados")
    from supabase import create_client

    return create_client(url, key)


def _evolution_config() -> tuple[str, str]:
    api_url = os.getenv("EVOLUTION_API_URL", "").rstrip("/")
    api_key = os.getenv("EVOLUTION_API_KEY", "")
    if not api_url or not api_key:
        raise RuntimeError("EVOLUTION_API_URL / EVOLUTION_API_KEY não configurados")
    return api_url, api_key


def send_whatsapp(phone: str, text: str, instance: str) -> dict:
    api_url, api_key = _evolution_config()
    response = requests.post(
        f"{api_url}/message/sendText/{instance}",
        json={"number": f"{normalize_phone(phone)}@s.whatsapp.net", "text": text},
        headers={"apikey": api_key, "Content-Type": "application/json"},
        timeout=20,
    )
    response.raise_for_status()
    try:
        return response.json()
    except ValueError:
        return {"status_code": response.status_code, "text": response.text[:500]}


def _fetch_instances() -> list[dict]:
    from conexao_cli import _cfg, _extract_instance_list, _headers

    base_url, api_key, _, _ = _cfg()
    if not base_url or not api_key:
        return []
    response = requests.get(f"{base_url}/instance/fetchInstances", headers=_headers(api_key), timeout=30)
    response.raise_for_status()
    return _extract_instance_list(response.json())


def _text(value: Any) -> str:
    return str(value or "").strip()


def _phone_candidates(phone: str) -> set[str]:
    value = normalize_phone(phone)
    if not value:
        return set()
    candidates = {value}
    if value.startswith("55") and len(value) > 11:
        candidates.add(value[2:])
    return candidates


def _order_by_protocol(db, protocolo: str) -> dict | None:
    rows = (
        db.table("pedidos_revisao")
        .select("*")
        .eq("protocolo", protocolo.upper())
        .limit(1)
        .execute()
        .data
        or []
    )
    return rows[0] if rows else None


def _customer_by_phone(db, phone: str) -> dict | None:
    candidates = list(_phone_candidates(phone))
    if not candidates:
        return None
    rows = (
        db.table("clic_clientes")
        .select("*")
        .in_("telefone", candidates)
        .limit(1)
        .execute()
        .data
        or []
    )
    return rows[0] if rows else None


def _latest_rep_for_customer(db, order: dict) -> int | None:
    customer = _customer_by_phone(db, _text(order.get("cliente_telefone")))
    cod_cli = (customer or {}).get("cod_cli")
    if cod_cli:
        rows = (
            db.table("rep_order_base")
            .select("cod_rep")
            .eq("cod_cli", int(cod_cli))
            .order("dat_emi", desc=True)
            .limit(1)
            .execute()
            .data
            or []
        )
        if rows and rows[0].get("cod_rep") is not None:
            return int(rows[0]["cod_rep"])
    return None


def _instance_owner_rows(db) -> list[dict]:
    try:
        return (
            db.table("system_settings")
            .select("key,value")
            .like("key", f"{OWNER_KEY_PREFIX}%")
            .execute()
            .data
            or []
        )
    except Exception as exc:
        logger.warning("Falha ao buscar donos das instâncias: %s", exc)
        return []


def _instance_for_rep(db, cod_rep: int | None) -> dict | None:
    if cod_rep is None:
        return None
    owner_rows = _instance_owner_rows(db)
    instances = {row.get("instanceName"): row for row in _fetch_instances()}
    for row in owner_rows:
        value = row.get("value") or {}
        if not isinstance(value, dict):
            continue
        try:
            owner_cod_rep = int(value.get("cod_rep"))
        except (TypeError, ValueError):
            continue
        if owner_cod_rep != cod_rep:
            continue
        name = _text(row.get("key")).replace(OWNER_KEY_PREFIX, "", 1)
        if not name:
            continue
        instance = instances.get(name) or {"instanceName": name}
        owner_phone = normalize_phone(instance.get("phoneNumber"))
        return {**instance, "owner_phone": owner_phone, "cod_rep": cod_rep}
    return None


def _instance_owner_info(db, instance_name: str) -> dict | None:
    name = _text(instance_name)
    if not name:
        return None

    rows = (
        db.table("system_settings")
        .select("key,value")
        .eq("key", f"{OWNER_KEY_PREFIX}{name}")
        .limit(1)
        .execute()
        .data
        or []
    )
    if not rows:
        return None

    value = rows[0].get("value") or {}
    if not isinstance(value, dict):
        return None

    cod_rep = None
    try:
        cod_rep = int(value.get("cod_rep")) if value.get("cod_rep") is not None else None
    except (TypeError, ValueError):
        cod_rep = None

    instance = {"instanceName": name}
    for item in _fetch_instances():
        if _text(item.get("instanceName")) == name:
            instance = item
            break

    return {**instance, "owner_phone": normalize_phone(instance.get("phoneNumber")), "cod_rep": cod_rep}


def _fmt_money(value: Any) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return ""
    return f"R$ {number:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _item_quantity(item: dict) -> float:
    value = item.get("quantidade") or item.get("qtdPed") or item.get("qtd") or 0
    try:
        return float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return 0.0


def _item_name(item: dict) -> str:
    return _text(item.get("nome") or item.get("produto") or item.get("desPro") or item.get("nome_produto")) or "Produto"


def format_order_review_message(order: dict) -> str:
    protocolo = _text(order.get("protocolo"))
    cliente_nome = _text(order.get("cliente_nome")) or "Cliente"
    cliente_phone = _text(order.get("cliente_telefone"))
    items = order.get("itens_json") or []
    lines = [
        "Pedido aguardando aprovação",
        "",
        f"Protocolo: {protocolo}",
        f"Cliente: {cliente_nome}",
        f"Telefone: {cliente_phone}",
        "",
        "Itens:",
    ]
    total = 0.0
    for index, item in enumerate(items, 1):
        if not isinstance(item, dict):
            continue
        qty = _item_quantity(item)
        unit = _text(item.get("unidade")) or "un"
        subtotal = item.get("subtotal")
        try:
            total += float(subtotal or 0)
        except (TypeError, ValueError):
            pass
        detail = " ".join(
            part
            for part in (
                _text(item.get("tipo") or item.get("formato")),
                _text(item.get("tamanho") or item.get("derivacao") or item.get("variacao") or item.get("volume")),
            )
            if part
        )
        price = f" - {_fmt_money(subtotal)}" if subtotal else ""
        lines.append(f"{index}. {_item_name(item)}{f' ({detail})' if detail else ''} - {qty:g} {unit}{price}")
    if total > 0:
        lines += ["", f"Total informado: {_fmt_money(total)}"]
    if _text(order.get("observacoes")):
        lines += ["", f"Observações: {_text(order.get('observacoes'))}"]
    lines += [
        "",
        "Lance esse pedido manualmente no Clic Vendas.",
        f"Depois de lançar, responda: aprovar {protocolo}",
        f"Para cancelar, responda: cancelar {protocolo}",
    ]
    return "\n".join(lines)


def notify_representative_order_review(order_id: str) -> dict:
    db = _db()
    rows = db.table("pedidos_revisao").select("*").eq("id", order_id).limit(1).execute().data or []
    if not rows:
        return {"sent": False, "reason": "order_not_found"}
    order = rows[0]
    cod_rep = _latest_rep_for_customer(db, order)
    instance = _instance_for_rep(db, cod_rep)
    if not instance:
        return {"sent": False, "reason": "representative_instance_not_found", "cod_rep": cod_rep}
    owner_phone = normalize_phone(instance.get("owner_phone"))
    if not owner_phone:
        return {"sent": False, "reason": "owner_phone_not_found", "cod_rep": cod_rep, "instance": instance.get("instanceName")}
    result = send_whatsapp(owner_phone, format_order_review_message(order), instance["instanceName"])
    return {
        "sent": True,
        "cod_rep": cod_rep,
        "instance": instance["instanceName"],
        "owner_phone": owner_phone,
        "result": result,
    }


def _clic_item_payload(item: dict) -> dict:
    cod = _text(item.get("cod_produto") or item.get("codPro") or item.get("codigo"))
    derivacao = _text(item.get("derivacao") or item.get("variacao") or item.get("tamanho") or item.get("volume"))
    payload: dict[str, Any] = {
        "produto": {"backoffice": {"codigo": cod}} if cod else {"nome": _item_name(item)},
        "quantidade": _item_quantity(item),
    }
    if derivacao:
        payload["derivacao"] = derivacao
    if item.get("preco_unitario") is not None:
        payload["precoUnitario"] = item.get("preco_unitario")
    if item.get("subtotal") is not None:
        payload["valorTotal"] = item.get("subtotal")
    return payload


def _submit_order_to_clic(db, order: dict, cod_rep: int | None) -> dict:
    from clic_vendas_client import ClicVendasClient

    customer = _customer_by_phone(db, _text(order.get("cliente_telefone"))) or {}
    cod_cli = customer.get("cod_cli") or customer.get("cpf_cnpj") or customer.get("documento")
    if not cod_cli:
        raise RuntimeError("Cliente sem código/documento para envio ao Clic Vendas")
    if cod_rep is None:
        raise RuntimeError("Representante sem cod_rep para envio ao Clic Vendas")

    items = [_clic_item_payload(item) for item in order.get("itens_json") or [] if isinstance(item, dict)]
    if not items:
        raise RuntimeError("Pedido sem itens para envio ao Clic Vendas")

    total = sum(float(item.get("valorTotal") or 0) for item in items)
    payload = {
        "cliente": {"backoffice": {"codigo": cod_cli}},
        "representante": {"backoffice": {"codigo": cod_rep}},
        "itens": items,
        "situacao": {"id": "aprovado"},
        "observacao": f"Pedido aprovado via IA. Protocolo interno {order.get('protocolo')}. {order.get('observacoes') or ''}".strip(),
    }
    if total > 0:
        payload["totais"] = {"valorTotalLiquido": round(total, 2)}

    return ClicVendasClient().post("/extpedidos", payload)


def _extract_created_order_number(response: dict) -> str:
    for key in ("numero", "numPed", "num_ped", "id"):
        value = response.get(key) if isinstance(response, dict) else None
        if value:
            return str(value)
    return ""


def _owner_can_act(instance_info: dict | None, phone: str) -> bool:
    if not instance_info:
        return False
    owner_phone = normalize_phone(instance_info.get("owner_phone"))
    return bool(owner_phone and normalize_phone(phone) == owner_phone)


def process_representative_order_command(phone: str, text: str, instance_name: str) -> dict | None:
    text = _text(text)
    approve_match = APPROVE_RE.search(text)
    cancel_match = CANCEL_RE.search(text)
    if not approve_match and not cancel_match:
        return None

    db = _db()
    current_instance = _instance_owner_info(db, instance_name)
    if not _owner_can_act(current_instance, phone):
        return None

    protocolo = (approve_match or cancel_match).group(1).upper()
    order = _order_by_protocol(db, protocolo)
    if not order:
        return {"action": "review_order_not_found", "should_reply": True, "reply": f"Não encontrei o pedido {protocolo}."}

    cod_rep = _latest_rep_for_customer(db, order)
    instance_info = _instance_for_rep(db, cod_rep)
    if instance_info and instance_name and _text(instance_info.get("instanceName")) != instance_name:
        return {"action": "review_wrong_instance", "should_reply": True, "reply": "Esse pedido pertence a outra instância."}
    if not _owner_can_act(instance_info, phone):
        return {"action": "review_unauthorized", "should_reply": True, "reply": "Não posso aprovar esse pedido por este número."}

    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    if cancel_match:
        db.table("pedidos_revisao").update(
            {"status": "cancelado", "revisado_em": now, "revisado_por": normalize_phone(phone), "updated_at": now}
        ).eq("id", order["id"]).execute()
        return {"action": "review_cancelled", "should_reply": True, "reply": f"Pedido {protocolo} cancelado."}

    if order.get("status") == "pedido_feito":
        return {"action": "review_already_done", "should_reply": True, "reply": f"O pedido {protocolo} já está marcado como feito."}

    db.table("pedidos_revisao").update(
        {
            "status": "pedido_feito",
            "revisado_em": now,
            "revisado_por": normalize_phone(phone),
            "updated_at": now,
        }
    ).eq("id", order["id"]).execute()
    return {
        "action": "review_approved_manual",
        "should_reply": True,
        "reply": f"Pedido {protocolo} marcado como feito. Considerei que você subiu esse pedido manualmente no Clic Vendas.",
    }
