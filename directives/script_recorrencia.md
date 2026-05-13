# Script de Identificação de Recorrência

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

## Etapa 1 — Filtro de Pedidos Inválidos

Antes de qualquer cálculo, pedidos com `situacao_id` inválido são excluídos da análise inteiramente.

Situações ignoradas:

| Código | Significado       |
|--------|-------------------|
| C, CA, CANC | Cancelado    |
| D, DEV      | Devolvido    |
| R, REP      | Reprovado    |
| T, TST      | Teste        |
| I, INATIVO  | Inativo      |

> A comparação é case-insensitive. Pedidos inválidos filtrados são contados em `skipped_invalid_orders` na saída.

---

## Etapa 2 — Seleção de Clientes Elegíveis

- Analisar pedidos válidos dos últimos 45 dias
- Contar pedidos válidos dos últimos 30 dias por cliente

**Regra:**
```
Se orders_count_30d >= 2 → cliente elegível

Classificação (recurrence_tier):
  2 pedidos → 'media'
  3 pedidos → 'alta'
  4+ pedidos → 'semanal_forte'
```

Clientes com menos de 2 pedidos válidos nos últimos 30 dias são ignorados.

---

## Etapa 3 — Cálculo de Recorrência

Para cada cliente elegível:

1. Ordenar pedidos válidos por data
2. Calcular intervalos entre pedidos consecutivos (em dias)
3. `avg_interval = mean(intervalos)`
4. `last_order = data do pedido mais recente`
5. `next_expected = last_order + avg_interval`
6. `days_until = (next_expected - hoje).days`

---

## Etapa 4 — Janela de Alerta

Gerar candidato apenas se:

```
-30 <= days_until <= 2
E last_order não foi nos últimos 3 dias
```

- `days_until > 2`: cliente ainda não chegou na janela → ignorar
- `days_until < -30`: cliente extremamente atrasado (> 30 dias vencido) → sai do funil
- Compra nos últimos 3 dias: acabou de comprar → ignorar

Configurável via constante `DAYS_OVERDUE_LIMIT` no script.

---

## Etapa 5 — Histórico para IA

Para cada candidato, montar:

- `last_3_orders_json`: últimos 3 pedidos válidos com `{numero, data, valor_total, situacao, itens}`
  - Itens: `{codPro, desPro, qtdPed, vlrTotal}`
- `top_items_json`: top 5 produtos por número de aparições entre pedidos válidos

> Expansão futura planejada: score composto por frequência + quantidade média + valor movimentado.

---

## Etapa 6 — Score do Script

Score inicial (0-100) baseado em regras:

| Critério | Pontos | Observação |
|---|---|---|
| `orders_count_30d >= 3` | +30 | |
| Intervalos consistentes (cv < 30%) | +25 | **Exige >= 2 intervalos (>= 3 pedidos)** |
| Produtos se repetem entre pedidos (codPro em comum) | +20 | |
| Dentro da janela de recompra (sempre verdadeiro aqui) | +15 | |
| Valor dos pedidos estável (cv < 30%) | +10 | **Exige >= 2 valores; outliers removidos antes do cálculo** |

**Bônus de consistência NÃO são aplicados com apenas 1 intervalo ou 1 valor.**
Com 2 pedidos você sabe que houve recompra, não que há consistência.

### Filtro de outliers de valor

Antes de calcular estabilidade de preço, valores extremamente fora do padrão são removidos:

- Requer >= 4 valores para aplicar o filtro
- Remove valores > 4× a mediana dos pedidos
- Evita que uma compra excepcional (atacado, sazonalidade) distorça a métrica

---

## Etapa 7 — Persistência em `recurrence_targets` (por ciclo)

**A chave de unicidade é `(cpf_cnpj + predicted_next_order_date)`, não apenas `cpf_cnpj`.**

Isso preserva o histórico completo de ciclos do cliente: ele pode entrar no funil, sair, voltar depois e terá múltiplos registros representando cada ciclo detectado.

### Lógica por cliente:

**1. Cooldown após rejeição**

Se o ciclo mais recente do cliente tem `status = 'ai_rejected'` e foi atualizado há menos de 7 dias, o cliente é pulado (cooldown ativo). Configurável via `COOLDOWN_DAYS`.

**2. Busca de ciclo compatível**

Procurar registro existente com `predicted_next_order_date` dentro de ±3 dias da data prevista atual (`CYCLE_MATCH_TOLERANCE_DAYS`).

**3. Regras de persistência:**

| Situação | Comportamento |
|---|---|
| Ciclo compatível com status terminal (`converted`, `opted_out`) | Ignorar — não recriar |
| Ciclo compatível com status ativo (`candidate`, `ai_rejected`, `ai_approved`, `dispatched`, `responded`) | UPDATE métricas; se `candidate`/`ai_rejected` → reset para `candidate` |
| Nenhum ciclo compatível encontrado | INSERT novo ciclo com `status='candidate'` |

---

## Regras de Segurança

- Não incluir cliente que comprou nos últimos 3 dias
- Não incluir cliente com menos de 2 pedidos válidos nos últimos 30 dias
- Não incluir pedidos cancelados, devolvidos, reprovados ou de teste
- Não criar novo ciclo para cliente em cooldown (rejeitado recentemente)
- Não recriar ciclo terminal (converted/opted_out)
- `--dry-run` não persiste nada, apenas loga

---

## Saída

```json
{
  "ok": true,
  "data": {
    "inserted": 3,
    "updated": 2,
    "skipped": 12,
    "skipped_invalid_orders": 4,
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
| Apenas 1 intervalo disponível (2 pedidos) | `avg_interval = intervalo único`, **sem bônus de consistência** |
| `avg_interval <= 0` | Pular cliente |
| Pedido com `situacao_id` inválido | Excluído de todos os cálculos |
| Ciclo encontrado mas terminal | Ignorado silenciosamente |
| Cliente em cooldown | Pulado (`skipped++`) |
