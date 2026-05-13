# Módulo de Disparos — Recorrência

## Objetivo

Executar o disparo de mensagens WhatsApp para os candidatos de recorrência que foram
aprovados pela IA (`status = 'ai_approved'` na tabela `recurrence_targets`).

O módulo NÃO decide quem deve receber mensagem. Ele apenas executa o envio dos
candidatos que já passaram pelo funil (script → validação IA).

---

## Posição no Funil

```
[Script Recorrência]       → recurrence_targets (candidate)
[Agente Validação IA]   → recurrence_targets (ai_approved | ai_rejected)
[Módulo de Disparos]    → executa envio → recurrence_targets (dispatched)
                        → registra em message_events
```

---

## Entrada

Lê da tabela `recurrence_targets`:

- `status = 'ai_approved'`
- `cooldown_until IS NULL OR cooldown_until < now()`
- `dispatched_at IS NULL` (nunca enviado antes)

---

## Ferramentas e Scripts

- `execution/disparos_recorrencia.py`
- Subcomando: `run [--dry-run] [--limit N] [--target-id UUID]`
- Integração: Evolution API (WhatsApp) via variáveis em `.env`

Variáveis necessárias no `.env`:
```
EVOLUTION_API_URL=
EVOLUTION_API_KEY=
EVOLUTION_INSTANCE=
```

---

## Etapas de Execução

### 1. Buscar candidatos aprovados

```sql
SELECT * FROM recurrence_targets
WHERE status = 'ai_approved'
  AND (cooldown_until IS NULL OR cooldown_until < now())
  AND dispatched_at IS NULL
ORDER BY created_at ASC
LIMIT :limit
```

### 2. Validar dados do candidato

Para cada candidato:
- `customer_phone` deve estar preenchido e ser um número válido (apenas dígitos, 10-13 chars)
- `ai_decision` deve estar presente
- Se dados inválidos → marcar `status = 'ai_rejected'`, registrar motivo em `ai_reasoning`, pular

### 3. Montar mensagem

Recuperar a mensagem gerada pelo agente de validação de `ai_decision.mensagem`.

Se `ai_decision.mensagem` estiver vazia → montar fallback simples:
```
Olá! Que tal repetirmos seu último pedido?
```

### 4. Enviar via Evolution API

```http
POST {EVOLUTION_API_URL}/message/sendText/{EVOLUTION_INSTANCE}
Authorization: {EVOLUTION_API_KEY}
{
  "number": "{customer_phone}@s.whatsapp.net",
  "text": "{mensagem}"
}
```

### 5. Registrar em `message_events`

```json
{
  "entity_type": "target",
  "entity_id": "{recurrence_targets.id}",
  "direction": "outbound",
  "to_number": "{customer_phone}",
  "message_type": "text",
  "payload_json": {
    "canal": "whatsapp",
    "funil de recorrência",
    "ai_decision": "{ai_decision resumido}"
  }
}
```

### 6. Atualizar `recurrence_targets`

```sql
UPDATE recurrence_targets SET
  status = 'dispatched',
  dispatched_at = now(),
  last_contact_at = now(),
  updated_at = now()
WHERE id = :target_id
```

---

## Saída Final

```json
{
  "ok": true,
  "data": {
    "processed": 5,
    "dispatched": 4,
    "skipped": 1,
    "errors": []
  }
}
```

---

## Regras de Segurança

- **Não disparar** se `cooldown_until` ainda não venceu
- **Não disparar** se `customer_phone` inválido → marcar como `ai_rejected`
- **Não disparar duplicado** — checar `dispatched_at IS NULL` antes de enviar
- **--dry-run** não envia nada, apenas imprime o que seria enviado
- **Limite padrão**: 50 disparos por execução para evitar banimento no WhatsApp

---

## Responsabilidade do Módulo

O módulo NÃO:
- decide se deve enviar (essa decisão é do agente IA)
- gera nem altera o conteúdo da mensagem
- processa respostas do cliente

O módulo APENAS:
- lê candidatos aprovados
- envia a mensagem já pronta
- registra o evento de envio
- atualiza o status para `dispatched`

---

## Tabelas Utilizadas

| Tabela | Operação |
|---|---|
| `recurrence_targets` | SELECT (leitura de candidatos) + UPDATE (status dispatched) |
| `message_events` | INSERT (log do envio) |

---

## Edge Cases

| Situação | Comportamento |
|---|---|
| Evolution API indisponível | Logar erro, NÃO atualizar status, retornar no próximo run |
| Número de telefone inválido | Marcar `ai_rejected`, registrar motivo |
| Candidato sem mensagem na IA | Usar mensagem fallback genérica |
| Timeout na requisição HTTP | Retry 1x com 3s de espera; se falhar → logar e pular |
| Evolution retorna erro 429 | Parar execução, logar aviso de rate limit |