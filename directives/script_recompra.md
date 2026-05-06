# Script de Identificação de Recompra

## Objetivo

Analisar diariamente a base de pedidos e identificar clientes com potencial de realizar
um novo pedido, gerando candidatos persistidos em `recurrence_targets` para validação por IA.

O script NÃO toma decisão final. Ele apenas filtra, calcula e persiste dados.

---

## Frequência de Execução

- Rodar 1x por dia
- Preferencialmente fora do horário comercial

---

## Script

`execution/recorrencia_cli.py` — subcomando `run`

```bash
py execution/recorrencia_cli.py run
py execution/recorrencia_cli.py run --dry-run   # não persiste, apenas loga
```

---

## Fonte de Dados

- Tabela: `clic_pedidos_integrados`
- Campos usados: `cpf_cnpj, numero, valor_total, situacao_id, criado_em, itens_json, raw_json`
- Estrutura de `itens_json`: `[{codPro, desPro, preUni, qtdPed, vlrTotal}]`
- Nome do cliente: `raw_json.cliente.fantasia` ou `razaoSocial`
- Telefone: `raw_json.cliente.telefones[0].valor`
- Cod CLI: `raw_json.cliente.backoffice.codigo`

---

## Etapa 1 — Seleção de Clientes Elegíveis

- Analisar pedidos dos últimos 45 dias
- Contar pedidos dos últimos 30 dias por cliente

**Regra:**
```
Se orders_count_30d >= 2 → cliente elegível

Classificação (recurrence_tier):
  2 pedidos → 'media'
  3 pedidos → 'alta'
  4+ pedidos → 'semanal_forte'
```

Clientes com menos de 2 pedidos nos últimos 30 dias são ignorados.

---

## Etapa 2 — Cálculo de Recorrência

Para cada cliente elegível:

1. Ordenar pedidos por data
2. Calcular intervalos entre pedidos consecutivos (em dias)
3. `avg_interval = mean(intervalos)`
4. `last_order = data do pedido mais recente`
5. `next_expected = last_order + avg_interval`
6. `days_until = (next_expected - hoje).days`

---

## Etapa 3 — Janela de Alerta

Gerar candidato apenas se:

```
days_until <= 2  (today >= next_expected - 2 dias)
E last_order não foi nos últimos 3 dias (acabou de comprar)
```

---

## Etapa 4 — Histórico para IA

Para cada candidato, montar:

- `last_3_orders_json`: últimos 3 pedidos com `{numero, data, valor_total, situacao, itens}`
  - Itens: `{codPro, desPro, qtdPed, vlrTotal}`
- `top_items_json`: top 5 produtos por número de aparições entre pedidos

---

## Etapa 5 — Score do Script

Score inicial (0-100) baseado em regras:

| Critério | Pontos |
|---|---|
| `orders_count_30d >= 3` | +30 |
| Intervalos consistentes (cv < 30%) | +25 |
| Produtos se repetem entre pedidos (codPro em comum) | +20 |
| Dentro da janela de recompra (sempre verdadeiro aqui) | +15 |
| Valor dos pedidos estável (cv < 30%) | +10 |

---

## Etapa 6 — Persistência em `recurrence_targets`

**Regras de upsert (chave: `cpf_cnpj`):**

| Status atual | Comportamento |
|---|---|
| Não existe | INSERT com `status='candidate'` |
| `candidate` ou `ai_rejected` | UPDATE tudo + reset `status='candidate'`, `ai_validated=False` |
| `ai_approved`, `dispatched`, `responded`, `converted` | UPDATE apenas métricas, **preservar status** |

---

## Regras de Segurança

- Não gerar candidato duplicado para o mesmo dia (upsert por cpf_cnpj)
- Não incluir cliente que comprou nos últimos 3 dias
- Não incluir cliente com menos de 2 pedidos nos últimos 30 dias
- `--dry-run` não persiste nada, apenas loga

---

## Saída

```json
{
  "ok": true,
  "data": {
    "inserted_or_updated": 5,
    "skipped": 12,
    "errors": [],
    "dry_run": false
  }
}
```

---

## Edge Cases

| Situação | Comportamento |
|---|---|
| `itens_json` vazio ou null | Monta pedido sem itens, score sem +20 |
| Telefone não encontrado | `customer_phone = null`, disparo será rejeitado depois |
| Apenas 1 intervalo disponível | `avg_interval = intervalo único`, score +25 (consistente) |
| `avg_interval <= 0` | Pular cliente |
