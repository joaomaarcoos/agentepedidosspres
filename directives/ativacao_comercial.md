# Ativação Comercial — Diretiva

## Objetivo

Transformar clientes com `status='ai_rejected'` no pipeline de recorrência em candidatos
de ativação comercial consultiva. Não assume padrão previsível de recompra.

Esta é a **segunda vertente** do pipeline de relacionamento:

- **Recorrência** → clientes com padrão previsível (`ai_approved`)
- **Ativação Comercial** → clientes sem padrão forte, mas com histórico de compras (`ai_rejected`)

---

## Quando usar

Após o pipeline de recorrência rejeitar um cliente (`ai_rejected`, `target_type='recorrencia'`),
se ele possuir histórico de pedidos suficiente para uma abordagem comercial aberta.

---

## Scripts

| Script | Subcomando | Função |
|--------|-----------|--------|
| `execution/ativacao_cli.py` | `run` | Gera candidatos de ativação a partir dos ai_rejected |
| `execution/ativacao_cli.py` | `overview` | Lista candidatos de ativação com paginação |
| `execution/agent_validacao_ativacao.py` | `run` | Valida com IA e monta mensagem consultiva |

```bash
# Gerar candidatos
py execution/ativacao_cli.py run
py execution/ativacao_cli.py run --dry-run
py execution/ativacao_cli.py run --limit 50

# Validar com IA
py execution/agent_validacao_ativacao.py run
py execution/agent_validacao_ativacao.py run --limit 10
py execution/agent_validacao_ativacao.py run --id <uuid>
```

---

## Cooldown

30 dias entre ativações para o mesmo cliente (campo `updated_at` do registro de ativação).

---

## Regras Obrigatórias

- **NÃO** mencionar "seu pedido costuma acontecer nessa época" ou variantes
- **NÃO** assumir padrão de compra ou frequência previsível
- Usar abordagem consultiva e aberta: oferecer ajuda, não impor necessidade
- **Não enviar mensagem neste módulo** — apenas preparar o pipeline
- **Não reler tabela de pedidos** — usar dados já presentes em `recurrence_targets`
- **Não criar duplicatas** — cooldown de 30 dias como proteção
- **Separar claramente** recorrência de ativação via campo `target_type`

---

## Fluxo no Banco (`recurrence_targets`, `target_type='ativacao'`)

```
ai_rejected (recorrencia)
    ↓
activation_candidate   ← ativacao_cli.py run
    ↓
activation_approved    ← agent_validacao_ativacao.py run
activation_rejected    ←
    ↓
dispatched             ← (futuro: disparos_ativacao.py)
```

---

## Tipos de Abordagem (`tipo_abordagem` no `ai_reasoning`)

| Tipo | Quando usar |
|------|-------------|
| `cliente_irregular` | Tem pedidos mas sem frequência definida |
| `cliente_adormecido` | Último pedido há muito tempo, sem compras recentes |
| `cliente_novo_potencial` | Poucos pedidos, mas recentes — relação ainda em construção |
| `descartar` | Dados insuficientes para qualquer abordagem segura |

---

## Formato de Resposta da IA (JSON obrigatório)

### Aprovado (`decisao=sim`)

```json
{
  "decisao": "sim",
  "tipo_abordagem": "cliente_irregular",
  "nivel_confianca": "medio",
  "motivo": "Cliente possui pedidos recentes, mas sem padrão suficiente para recorrência previsível.",
  "mensagem": "Olá! Tudo bem? Vi que você já comprou conosco anteriormente. Posso te ajudar a montar uma nova reposição ou repetir algum item do seu último pedido?"
}
```

### Rejeitado (`decisao=nao`)

```json
{
  "decisao": "nao",
  "tipo_abordagem": "descartar",
  "nivel_confianca": "baixo",
  "motivo": "Cliente não possui dados suficientes para uma abordagem comercial segura.",
  "mensagem": ""
}
```

---

## Persistência após Validação

| Campo | Valor |
|-------|-------|
| `ai_validated` | `true` |
| `ai_decision` | `"sim"` ou `"nao"` |
| `ai_reasoning` | JSON completo da resposta (string) |
| `status` | `"activation_approved"` ou `"activation_rejected"` |
| `updated_at` | timestamp atual |

---

## Saída do Script de Geração (`ativacao_cli.py run`)

```json
{
  "ok": true,
  "data": {
    "processed": 15,
    "eligible": 6,
    "skipped_cooldown": 7,
    "skipped_no_data": 2,
    "inserted": 4,
    "updated": 2,
    "errors": [],
    "dry_run": false
  }
}
```

## Saída do Agente (`agent_validacao_ativacao.py run`)

```json
{
  "ok": true,
  "data": {
    "processed": 6,
    "approved": 4,
    "rejected": 2,
    "errors": []
  }
}
```

---

## Edge Cases

| Situação | Comportamento |
|----------|---------------|
| Cliente sem histórico de pedidos | `skipped_no_data` — não cria registro de ativação |
| Registro de ativação dentro do cooldown (30d) | `skipped_cooldown` — pula sem atualizar |
| Resposta da IA fora do JSON | Logar erro, pular candidato, não atualizar status |
| `tipo_abordagem` inválido | Rejeitar resposta inteira, não atualizar status |
| `OPENAI_API_KEY` ausente | Falha imediata com mensagem clara |

---

## Automação

Os scripts aceitam os mesmos padrões do pipeline principal:

- `--dry-run`: simula sem persistir
- `--limit N`: limita candidatos processados
- `--id UUID`: processa apenas um registro específico

O endpoint `/api/ativacao/pipeline` executa o ciclo completo (geração + validação IA)
e aceita `triggered_by: "manual" | "schedule" | "auto"` para futura integração com cron.
