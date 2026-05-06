# Agente de Validação de Recompra

## Objetivo

Receber candidatos gerados pelo script (`status='candidate'` em `recurrence_targets`) e decidir:

- Se deve disparar contato com o cliente (`ai_approved`)
- Se deve descartar o candidato (`ai_rejected`)

O agente NÃO lê banco, NÃO busca dados adicionais, NÃO executa ações externas.
Ele apenas valida o padrão e decide com base nos dados já montados pelo script.

---

## Script

`execution/agent_validacao_recompra.py` — subcomando `run`

```bash
py execution/agent_validacao_recompra.py run
py execution/agent_validacao_recompra.py run --limit 5
py execution/agent_validacao_recompra.py run --id <uuid>   # validar um candidato específico
```

---

## Modelo de IA

- **Modelo:** `claude-haiku-4-5-20251001`
- **Temperatura:** 0 (respostas determinísticas)
- **Max tokens:** 1024
- **API key:** `ANTHROPIC_API_KEY` no `.env`

---

## Entrada

Para cada candidato em `recurrence_targets` com `status='candidate'`, o agente recebe:

- Nome do cliente
- Nível de recorrência (tier)
- Intervalo médio entre pedidos (dias)
- Data prevista do próximo pedido
- Quantidade de pedidos nos últimos 30 dias
- Últimos 3 pedidos com itens detalhados (`codPro`, `desPro`, `qtdPed`, `vlrTotal`)
- Top produtos mais comprados

---

## Regras de Decisão

### Retornar `"decisao": "sim"` quando:

- Cliente tem 2 ou mais pedidos recentes
- Existe repetição de produtos (`codPro`) entre pedidos
- Quantidades são semelhantes entre pedidos
- Intervalo entre pedidos é consistente
- Está dentro da janela de recompra

### Retornar `"decisao": "nao"` quando:

- Pedidos são muito diferentes entre si
- Não há repetição de produtos
- Quantidades variam demais
- Intervalos são irregulares
- Cliente parece comprar de forma ocasional

---

## Formato de Resposta (JSON obrigatório)

**Se aprovado:**
```json
{
  "decisao": "sim",
  "nivel_confianca": "alto",
  "motivo": "Cliente compra SUCO BOLSA LARANJA toda semana em quantidade estável",
  "pedido_sugerido": [
    {"codPro": "SBSSSLAR", "desPro": "SUCO BOLSA LARANJA", "qtdPed": 13}
  ],
  "valor_medio": 442.0,
  "mensagem": "Olá! Vi que seus pedidos costumam acontecer por essa época.\n\nNo último pedido você levou:\n13x Suco Bolsa Laranja\n\nQuer repetir o pedido ou ajustar algo?"
}
```

**Se rejeitado:**
```json
{
  "decisao": "nao",
  "nivel_confianca": "baixo",
  "motivo": "Produtos variam muito entre pedidos, sem padrão claro",
  "pedido_sugerido": [],
  "valor_medio": 0,
  "mensagem": ""
}
```

---

## Persistência após validação

| Campo | Valor |
|---|---|
| `ai_validated` | `true` |
| `ai_decision` | `"sim"` ou `"nao"` |
| `ai_reasoning` | JSON completo da resposta (string) |
| `status` | `"ai_approved"` ou `"ai_rejected"` |
| `updated_at` | timestamp atual |

---

## Regras Obrigatórias

O agente NÃO pode:

- Inventar produtos fora do histórico
- Sugerir itens que não aparecem nos pedidos reais
- Alterar quantidades sem base no histórico
- Assumir padrões inexistentes
- Responder fora do formato JSON

---

## Saída do Script

```json
{
  "ok": true,
  "data": {
    "processed": 5,
    "approved": 3,
    "rejected": 2,
    "errors": []
  }
}
```

---

## Edge Cases

| Situação | Comportamento |
|---|---|
| Resposta da IA fora do JSON | Logar erro, pular candidato, não atualizar status |
| ANTHROPIC_API_KEY ausente | Falha imediata com mensagem clara |
| Candidato sem itens nos pedidos | IA decide com base no valor e intervalo apenas |
| `nivel_confianca = "baixo"` com `decisao = "sim"` | Aprovado mesmo assim; disparo decide se envia |
