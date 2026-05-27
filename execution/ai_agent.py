"""
ai_agent.py
===========
Core de atendimento WhatsApp com controle de pausa.

Regras:
- "##" pausa a IA por 5 horas.
- "###" despausa imediatamente.
- Pausa expirada e removida automaticamente no proximo evento.
- O contexto enviado para a IA usa apenas as ultimas 10 mensagens salvas.
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

from dotenv import load_dotenv

_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_ROOT / ".env")

sys.path.insert(0, str(_ROOT))
from prompts.builder import build_prompt

logger = logging.getLogger(__name__)

PAUSE_TRIGGER = "##"
RESUME_TRIGGER = "###"
PAUSE_HOURS = int(os.getenv("AI_PAUSE_HOURS", "5"))
CONTEXT_MESSAGE_LIMIT = int(os.getenv("AI_CONTEXT_MESSAGE_LIMIT", "10"))
MESSAGE_BUFFER_SECONDS = float(os.getenv("AI_MESSAGE_BUFFER_SECONDS", "5"))
LOCAL_DATA_DIR = Path(__file__).resolve().parent.parent / ".tmp" / "data"
CONVERSATIONS_TABLE = "ai_conversations"
MESSAGES_TABLE = "ai_conversation_messages"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


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


def mentions_order_context(messages: list[dict]) -> bool:
    keywords = (
        "pedido",
        "comprar",
        "compra",
        "cotacao",
        "orcamento",
        "caixa",
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

    out_patterns = (
        "quem e o presidente",
        "presidente do brasil",
        "que dia e hoje",
        "data de hoje",
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
        return "Consigo te ajudar com assuntos da Sucos SPRES. Quer continuar o pedido que estavamos montando?"
    return "Oi! Sou a Marcela, da Sucos SPRES. Consigo te ajudar com pedidos, produtos e precos. Quer montar um pedido ou consultar algum produto?"


def greeting_reply(has_order_context: bool = False) -> str:
    if has_order_context:
        return "Oi! Sou a Marcela, da Sucos SPRES. Quer continuar seu pedido ou ajustar algum item?"
    return "Oi! Sou a Marcela, da Sucos SPRES. Quer montar um pedido ou consultar algum produto?"


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
    ) -> str:
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
            self._local_append("pedidos_revisao", payload)
            return order_id

        try:
            result = self.client.table("pedidos_revisao").insert(payload).execute()
            return (result.data or [payload])[0].get("id", order_id)
        except Exception as exc:
            logger.warning("Falha ao salvar pedido_revisao; usando local: %s", exc)
            self.use_local = True
            self._local_append("pedidos_revisao", payload)
            return order_id

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
            "Registra o pedido confirmado do cliente para revisão do representante antes de enviar ao sistema. "
            "Use assim que o cliente confirmar os produtos e quantidades desejados."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "itens": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "nome": {"type": "string", "description": "Nome do produto"},
                            "quantidade": {"type": "string", "description": "Quantidade (ex: 2 caixas, 10 unidades)"},
                        },
                        "required": ["nome", "quantidade"],
                    },
                    "description": "Lista de produtos e quantidades do pedido",
                },
                "observacoes": {
                    "type": "string",
                    "description": "Observações extras do cliente: prazo, entrega, forma de pagamento, etc.",
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
                order_id = store.save_order_for_review(
                    phone=phone,
                    conversation_id=conversation_id,
                    itens=args.get("itens", []),
                    observacoes=args.get("observacoes", ""),
                    customer_name=customer_name or (module_context or {}).get("customer_name"),
                    mensagem_cliente=last_user_message or "",
                )
                tool_result = json.dumps(
                    {"sucesso": True, "id": order_id, "mensagem": "Pedido registrado para revisão do representante."},
                    ensure_ascii=False,
                )
                logger.info("Pedido registrado para revisão: %s (telefone: %s)", order_id, phone)
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

    if MESSAGE_BUFFER_SECONDS > 0:
        time.sleep(MESSAGE_BUFFER_SECONDS)
        if store.has_newer_user_message(str(conversation["id"]), str(user_message.get("created_at") or "")):
            return {
                "action": "buffered_waiting_latest_message",
                "should_reply": False,
                "buffer_seconds": MESSAGE_BUFFER_SECONDS,
            }

    history = store.recent_messages(str(conversation["id"]), CONTEXT_MESSAGE_LIMIT)
    previous_history = history[:-1] if history else []
    has_order_context = mentions_order_context(previous_history)

    direct_reply = ""
    if is_prompt_attack(normalized_text):
        direct_reply = scoped_redirect_reply(has_order_context)
    elif is_out_of_scope(normalized_text):
        direct_reply = scoped_redirect_reply(has_order_context)
    elif is_simple_greeting(normalized_text):
        direct_reply = greeting_reply(has_order_context)

    if direct_reply:
        store.add_message(str(conversation["id"]), "assistant", direct_reply, payload_json={"source": "guardrail"})
        return {
            "action": "guardrail_reply",
            "should_reply": True,
            "reply": direct_reply,
            "context_messages": len(history),
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
    }
