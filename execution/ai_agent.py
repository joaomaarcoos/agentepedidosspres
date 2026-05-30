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
CONTEXT_MESSAGE_LIMIT = int(os.getenv("AI_CONTEXT_MESSAGE_LIMIT", "15"))
DEFAULT_MESSAGE_BUFFER_SECONDS = float(os.getenv("AI_MESSAGE_BUFFER_SECONDS", "5"))
LOCAL_DATA_DIR = Path(__file__).resolve().parent.parent / ".tmp" / "data"
CONVERSATIONS_TABLE = "ai_conversations"
MESSAGES_TABLE = "ai_conversation_messages"
STATE_TABLE = "system_settings"
BUFFER_SETTING_KEY = "ai_message_buffer_seconds"
LOCAL_TIMEZONE = ZoneInfo(os.getenv("AI_LOCAL_TIMEZONE", "America/Sao_Paulo"))


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


def is_simple_greeting(text: str) -> bool:
    value = _lower_ascii(text).strip(" .,!?\n\t")
    return value in {
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
    elif contains_any(value, ("quero fazer um pedido", "fazer pedido", "montar pedido", "comprar", "pedido")):
        intent = "order_request"
    elif state.get("order_in_progress") and contains_any(value, ("tira", "remove", "coloca", "inclui", "mais", "menos", "troca", "altera")):
        intent = "order_adjustment"
    elif entities["products"] or contains_any(value, ("quais tem", "quais voces tem", "opcoes", "sabores", "modelos", "embalagens")):
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
    return "Esse assunto foge um pouco do atendimento da Sucos SPRES. Posso te ajudar com produtos, precos ou montar um pedido."


def direct_reply_for_intent(classification: dict) -> str:
    intent = classification.get("intent")
    has_order_context = bool(classification.get("has_order_context"))
    if intent == "prompt_attack":
        return scoped_redirect_reply(has_order_context)
    if intent == "complaint":
        return "Entendo. Vou te conectar com um atendente agora para resolver isso direto."
    return ""


def is_final_order_confirmation(text: str) -> bool:
    value = _lower_ascii(text)
    if not value:
        return False

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
    if contains_any(value, adjustment_terms) or contains_any(value, question_terms):
        return False

    confirmation_terms = (
        "esta certo",
        "ta certo",
        "tudo certo",
        "pode registrar",
        "pode enviar",
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


def order_confirmation_prompt(itens: list[dict] | None = None) -> str:
    lines = ["Ainda nao registrei o pedido.", "", "So para confirmar, ficou assim:"]
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
        "Se estiver tudo certo, me responda com *pode registrar* que eu envio para aprovacao do representante.",
    ]
    return "\n".join(lines)


def _item_value(item: dict, *keys: str) -> str:
    for key in keys:
        value = item.get(key)
        if value is not None and normalize_text(value):
            return normalize_text(value)
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
        "Ainda nao consigo enviar esse pedido para aprovacao porque faltam dados obrigatorios.",
        "",
        "Para cada item preciso de: produto, tipo, tamanho, quantidade e unidade.",
    ]
    if missing:
        lines.append("")
        lines.append("Faltou:")
        for entry in missing:
            fields = ", ".join(entry["campos"])
            lines.append(f"- Item {entry['item']}: {fields}")
    lines += [
        "",
        "Me passe esses dados que eu atualizo o resumo completo antes de enviar para o representante.",
    ]
    return "\n".join(lines)


def update_commercial_state(state: dict | None, classification: dict, user_text: str) -> dict:
    state = {**(state or {})}
    intent = classification.get("intent", "")
    if intent in {"order_request", "repeat_order", "order_adjustment", "price_query", "product_query"}:
        state["order_in_progress"] = True
    if intent == "disengage":
        state["order_in_progress"] = False
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
                text = f"{text}\n\nSe estiver tudo certo, me responda com *pode registrar* que eu envio para aprovacao do representante."
            else:
                text = "Se estiver tudo certo, me responda com *pode registrar* que eu envio para aprovacao do representante."
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
    ) -> dict:
        missing_fields = _missing_order_fields(itens)
        if missing_fields:
            raise ValueError(f"Itens do pedido incompletos: {missing_fields}")

        order_id = str(uuid.uuid4())
        now = iso_z(utc_now())
        payload = {
            "id": order_id,
            "cliente_telefone": phone,
            "cliente_nome": customer_name,
            "conversation_id": conversation_id,
            "itens_json": itens,
            "observacoes": observacoes or "",
            "mensagem_cliente": mensagem_cliente or "",
            "status": "pendente",
            "created_at": now,
            "updated_at": now,
        }

        if self.use_local:
            rows = self._local_read("pedidos_revisao")
            for index, row in enumerate(rows):
                same_conversation = conversation_id and row.get("conversation_id") == conversation_id
                same_phone = phone and row.get("cliente_telefone") == phone
                if (same_conversation or same_phone) and row.get("status") in {"pendente", "em_revisao"}:
                    updated = {
                        **row,
                        "cliente_nome": customer_name or row.get("cliente_nome"),
                        "itens_json": itens,
                        "observacoes": observacoes or "",
                        "mensagem_cliente": mensagem_cliente or "",
                        "updated_at": now,
                    }
                    rows[index] = updated
                    self._local_write("pedidos_revisao", rows)
                    return {"id": row.get("id", order_id), "action": "updated"}
            self._local_append("pedidos_revisao", payload)
            return {"id": order_id, "action": "created"}

        try:
            existing_rows = []
            lookup_filters = []
            if conversation_id:
                lookup_filters.append(("conversation_id", conversation_id))
            if phone:
                lookup_filters.append(("cliente_telefone", phone))

            for field, value in lookup_filters:
                existing = (
                    self.client.table("pedidos_revisao")
                    .select("id,status,created_at")
                    .in_("status", ["pendente", "em_revisao"])
                    .eq(field, value)
                    .order("created_at", desc=True)
                    .limit(1)
                    .execute()
                )
                existing_rows = existing.data or []
                if existing_rows:
                    break

            if existing_rows:
                existing_id = existing_rows[0]["id"]
                update_payload = {
                    "itens_json": itens,
                    "observacoes": observacoes or "",
                    "mensagem_cliente": mensagem_cliente or "",
                    "updated_at": now,
                }
                if customer_name:
                    update_payload["cliente_nome"] = customer_name
                result = (
                    self.client.table("pedidos_revisao")
                    .update(update_payload)
                    .eq("id", existing_id)
                    .execute()
                )
                return {"id": (result.data or [{"id": existing_id}])[0].get("id", existing_id), "action": "updated"}

            result = self.client.table("pedidos_revisao").insert(payload).execute()
            return {"id": (result.data or [payload])[0].get("id", order_id), "action": "created"}
        except Exception as exc:
            logger.warning("Falha ao salvar pedido_revisao; usando local: %s", exc)
            self.use_local = True
            self._local_append("pedidos_revisao", payload)
            return {"id": order_id, "action": "created"}

    def get_open_order_for_review(self, phone: str, conversation_id: str | None = None) -> dict | None:
        editable_statuses = {"pendente", "em_revisao"}
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
            return matches[0] if matches else None

        try:
            lookup_filters = []
            if conversation_id:
                lookup_filters.append(("conversation_id", conversation_id))
            if phone:
                lookup_filters.append(("cliente_telefone", phone))

            for field, value in lookup_filters:
                result = (
                    self.client.table("pedidos_revisao")
                    .select("id,status,itens_json,observacoes,created_at,updated_at")
                    .in_("status", list(editable_statuses))
                    .eq(field, value)
                    .order("updated_at", desc=True)
                    .limit(1)
                    .execute()
                )
                rows = result.data or []
                if rows:
                    return rows[0]
            return None
        except Exception as exc:
            logger.warning("Falha ao buscar pedido em revisao aberto: %s", exc)
            return None

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
            return result.data or []
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
            "Se ja houver pedido pendente ou em revisao para a conversa, a ferramenta atualiza esse pedido. "
            "Cada item deve ter produto, tipo/formato, tamanho/derivacao, quantidade e unidade. "
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
                            "tamanho": {"type": "string", "description": "Tamanho/derivacao/volume exatamente como confirmado, ex: 200ml, 300ml, 1,7L, 5L"},
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
                if _missing_order_fields(itens):
                    return missing_order_fields_prompt(itens)
                if not is_final_order_confirmation(last_user_message or ""):
                    return order_confirmation_prompt(itens)
                order_result = store.save_order_for_review(
                    phone=phone,
                    conversation_id=conversation_id,
                    itens=itens,
                    observacoes=args.get("observacoes", ""),
                    customer_name=customer_name or (module_context or {}).get("customer_name"),
                    mensagem_cliente=last_user_message or "",
                )
                order_id = order_result.get("id") if isinstance(order_result, dict) else str(order_result)
                order_action = order_result.get("action") if isinstance(order_result, dict) else "created"
                result_message = (
                    "Pedido atualizado para revisao do representante."
                    if order_action == "updated"
                    else "Pedido registrado para revisao do representante."
                )
                tool_result = json.dumps(
                    {
                        "sucesso": True,
                        "id": order_id,
                        "acao": order_action,
                        "mensagem": result_message,
                        "itens": itens,
                        "total_pedido": args.get("total_pedido"),
                        "instrucao_resposta": (
                            "Responda ao cliente dizendo se o pedido foi registrado ou atualizado, "
                            "com o resumo final incluindo preco unitario, "
                            "subtotal por item e total geral quando esses valores estiverem nos itens."
                        ),
                    },
                    ensure_ascii=False,
                )
                logger.info("Pedido %s para revisao: %s (telefone: %s)", order_action, order_id, phone)
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
    codigo_tabela = (customer or {}).get("tabela_preco_codigo") or store.get_tabela_preco_for_phone(safe_phone)
    recent_orders = store.get_recent_orders_for_customer(customer, limit=4)
    if customer or recent_orders:
        module_context = {**(module_context or {})}
        if customer:
            module_context["customer_profile"] = {
                "nome": customer.get("nome") or customer.get("fantasia") or customer.get("razao_social"),
                "cod_cli": customer.get("cod_cli") or customer.get("cpf_cnpj"),
                "tabela_preco_codigo": customer.get("tabela_preco_codigo"),
                "tabela_preco_nome": customer.get("tabela_preco_nome"),
                "cidade": customer.get("cidade"),
                "uf": customer.get("uf"),
            }
            module_context["customer_name"] = module_context.get("customer_name") or module_context["customer_profile"].get("nome")
        if recent_orders:
            module_context["recent_orders"] = recent_orders
    module_context = {**(module_context or {})}
    open_review_order = store.get_open_order_for_review(safe_phone, str(conversation["id"]))
    if open_review_order:
        module_context["open_review_order"] = open_review_order
    module_context["classified_intent"] = classification
    module_context["conversation_state"] = conversation_state
    if codigo_tabela:
        produtos = store.get_produtos_tabela(codigo_tabela)
    else:
        produtos = store.get_produtos()
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
