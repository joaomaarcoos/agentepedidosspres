"""
Tools internas da Secretaria IA.

As tools recebem estado/dados estruturados, executam uma tarefa objetiva e
devolvem um resultado estruturado para o agente central decidir a resposta.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass
class ToolResult:
    action: str
    reply: str
    state: dict


def select_sale_type_tool(
    state: dict,
    sale_type_code: str,
    sale_type_label: Callable[[Any], str],
    order_summary: Callable[[dict, list[dict], str], str],
    save_draft: Callable[[dict], dict] | None = None,
) -> ToolResult:
    state["sale_type_code"] = sale_type_code
    if state.get("items"):
        if save_draft:
            order = save_draft(state)
            state["order_id"] = order.get("id")
            state["protocol"] = order.get("protocol")
            state["ready_to_submit"] = True
        reply = (
            f"Tipo de pedido definido: *{sale_type_label(state.get('sale_type_code'))}*.\n\n"
            + order_summary(
                state["customer"],
                state.get("items") or [],
                state.get("observations") or "",
            )
        )
    else:
        state["awaiting_observation"] = True
        reply = (
            f"Perfeito, pedido *{sale_type_label(state.get('sale_type_code'))}*. "
            "Quer adicionar alguma observacao nesse pedido? Se nao quiser, responda *nao*."
        )
    return ToolResult("secretary_sale_type_selected", reply, state)


def show_summary_tool(
    state: dict,
    order_summary: Callable[[dict, list[dict], str], str],
) -> ToolResult:
    reply = order_summary(
        state["customer"],
        state.get("items") or [],
        state.get("observations") or "",
    )
    return ToolResult("secretary_order_summary", reply, state)


def resolve_products_tool(
    *,
    text: str,
    state: dict,
    customer: dict,
    catalog_lookup: Callable[[dict], list[dict]],
    resolver: Callable[[str, list[dict], dict], dict | None],
    drop_resolved_pending_items: Callable[[dict | None], dict | None],
    resolution_items: Callable[[dict | None], list[dict]],
    safe_float: Callable[[Any], float],
    resolution_reply: Callable[[dict | None], str],
    suggestions_enricher: Callable[[dict | None, list[dict]], dict | None] | None = None,
    save_draft: Callable[[dict], dict],
    order_summary: Callable[[dict, list[dict], str], str],
) -> ToolResult:
    catalog = catalog_lookup(customer)
    if not catalog:
        return ToolResult(
            "secretary_reply",
            "Nao encontrei a tabela de precos desse cliente. O pedido nao pode ser enviado sem essa validacao.",
            state,
        )

    resolution = resolver(text, catalog, state)
    if not resolution:
        return ToolResult(
            "secretary_reply",
            "Nao consegui identificar os produtos. Informe produto, formato, tamanho e quantidade.",
            state,
        )

    resolution = drop_resolved_pending_items(resolution) or resolution
    if suggestions_enricher:
        resolution = suggestions_enricher(resolution, catalog) or resolution
    state["catalog_resolution"] = resolution
    current = resolution_items(resolution)
    issues = [
        item
        for item in resolution.get("itens") or []
        if isinstance(item, dict) and item.get("status") != "encontrado"
    ]
    missing_quantities = [
        item for item in current if safe_float(item.get("quantidade")) <= 0
    ]
    if issues or missing_quantities:
        reply = resolution_reply(resolution)
        state["items"] = current
        state["ready_to_submit"] = False
        state.setdefault("product_history", []).append({"role": "assistant", "content": reply})
        return ToolResult("secretary_reply", reply, state)

    state["items"] = current
    order = save_draft(state)
    state["order_id"] = order.get("id")
    state["protocol"] = order.get("protocol")
    state["ready_to_submit"] = True
    reply = order_summary(
        customer,
        current,
        state.get("observations") or "",
    )
    state.setdefault("product_history", []).append({"role": "assistant", "content": reply})
    return ToolResult("secretary_reply", reply, state)


def submit_order_tool(
    *,
    state: dict,
    load_order: Callable[[str], dict | None],
    save_draft: Callable[[dict], dict],
    submit: Callable[[dict], tuple[bool, str]],
) -> ToolResult:
    order_id = state.get("order_id")
    if not order_id or not state.get("ready_to_submit"):
        if state.get("customer") and state.get("items"):
            order = save_draft(state)
            state["order_id"] = order.get("id")
            state["protocol"] = order.get("protocol")
            state["ready_to_submit"] = True
            submitted, reply = submit(order)
            if submitted:
                state = {}
            return ToolResult("secretary_submitted", reply, state)
        return ToolResult(
            "secretary_reply",
            "Nao ha pedido pronto para confirmacao. Informe primeiro o cliente e os itens.",
            state,
        )

    order = load_order(str(order_id))
    if not order:
        return ToolResult("secretary_reply", "Nao encontrei o rascunho desse pedido.", state)
    submitted, reply = submit(order)
    if submitted:
        state = {}
    return ToolResult("secretary_submitted", reply, state)
