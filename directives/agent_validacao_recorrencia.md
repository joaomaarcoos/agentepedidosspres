# Agente de Validação de Recorrência

## Objetivo

Receber candidatos gerados pelo script (`status='candidate'` em `recurrence_targets`) e decidir:

- Se deve disparar contato com o cliente (`ai_approved`)
- Se deve descartar o candidato (`ai_rejected`)
- Se precisa de revisão manual (`needs_review`)

O agente **NÃO** lê banco, **NÃO** busca dados adicionais, **NÃO** executa ações externas. Ele apenas valida o padrão e decide com base nos dados já montados pelo script.

---

## Script

`execution/agent_validacao_recorrencia.py` — subcomando `run`

```bash
py execution/agent_validacao_recorrencia.py run
py execution/agent_validacao_recorrencia.py run --limit 5
py execution/agent_validacao_recorrencia.py run --id <uuid>
```

---

## Modelo de IA

| Parâmetro   | Valor                                           |
|-------------|-------------------------------------------------|
| Provedor    | OpenAI                                          |
| Modelo      | `gpt-4o-mini` (padrão; configurável via `OPENAI_MODEL` no `.env`) |
| Temperatura | `0`                                             |
| Max tokens  | `1024`                                          |
| Formato     | `response_format: json_object` (JSON garantido) |
| API key     | `OPENAI_API_KEY` no `.env`                      |

As respostas são determinísticas e sempre em JSON válido (forçado pela API).

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

> Os `codPro` são incluídos explicitamente no prompt para que a IA não invente produtos.

---

## Objetivo da Análise

O agente deve identificar:

1. Se existe padrão real de recompra
2. Se os produtos possuem recorrência
3. Se as quantidades possuem consistência
4. Se o comportamento é previsível
5. Se o momento é adequado para contato
6. Se existe base suficiente para sugerir um pedido

---

## Regras de Decisão

### `"decisao": "sim"` — Aprovar quando:

- Cliente possui 2 ou mais pedidos recentes
- Existe repetição clara de produtos (`codPro`)
- Quantidades possuem variações pequenas e aceitáveis
- Intervalo entre pedidos é consistente
- Cliente está dentro da janela prevista de recompra

### `"decisao": "nao"` — Rejeitar quando:

- Pedidos são muito diferentes entre si
- Não existe repetição clara de produtos
- Quantidades variam excessivamente
- Intervalos são muito irregulares
- Cliente parece comprar de forma ocasional
- Não existe padrão confiável de recompra

---

## Consistência de Quantidade

Variações pequenas são aceitáveis.

| Padrão          | Exemplo         |
|-----------------|-----------------|
| ✅ Consistente   | `10 → 12 → 11`  |
| ❌ Inconsistente | `10 → 40 → 3`   |

---

## Consistência de Produtos

- Priorizar produtos presentes em **múltiplos pedidos**
- Priorizar produtos com **maior recorrência**
- Priorizar produtos com **quantidades mais estáveis**
- Produtos que aparecem **apenas uma vez** não devem ser tratados como recorrentes

---

## Recorrência Parcial

Ter múltiplos pedidos **não** significa necessariamente recorrência válida. O agente deve validar:

- Consistência dos produtos
- Consistência das quantidades
- Consistência do intervalo

### Casos de Aprovação Parcial

Se houver **forte recorrência de intervalo** mas **baixa consistência de produtos**, o agente pode aprovar contato genérico, sem sugerir pedido fechado. Nesse caso `pedido_sugerido` fica vazio e o script marca como `needs_review`.

---

## Janela de Análise

Considerar principalmente os pedidos recentes enviados pelo script. Pedidos antigos fora da janela analisada não devem influenciar fortemente a decisão.

---

## Construção do Pedido Sugerido

O `pedido_sugerido` deve ser montado:

- Com base nos produtos recorrentes
- Usando média ou repetição das quantidades
- **Somente com `codPro` presentes no histórico enviado no prompt**
- Sem inventar produtos
- Sem alterar quantidades sem base real

O agente **não pode**:

- Inventar itens
- Sugerir produtos fora do histórico
- Assumir padrões inexistentes

> `valor_medio` deve representar a média dos pedidos recorrentes. Não usar pedidos claramente fora do padrão para o cálculo.

### Validação de produtos no script

O script verifica que todos os `codPro` em `pedido_sugerido` existem nos pedidos reais do target. Se a IA sugerir um produto fora do histórico, a resposta inteira é **rejeitada** — o candidato não é atualizado e o erro é logado.

---

## Nível de Confiança

| Nível  | Critérios                                                              |
|--------|------------------------------------------------------------------------|
| Alto   | Produtos muito recorrentes, quantidades estáveis, intervalos consistentes |
| Médio  | Alguma recorrência, pequenas variações, padrão parcialmente previsível |
| Baixo  | Pouca repetição, alta variação, padrão fraco ou inconsistente          |

---

## Determinação do Status Final

| `decisao` | `nivel_confianca` | `pedido_sugerido` | Status persistido |
|-----------|-------------------|-------------------|-------------------|
| `nao`     | qualquer          | qualquer          | `ai_rejected`     |
| `sim`     | `baixo`           | qualquer          | `needs_review`    |
| `sim`     | `alto` / `medio`  | vazio             | `needs_review`    |
| `sim`     | `alto` / `medio`  | preenchido        | `ai_approved`     |

---

## Formato de Resposta (JSON obrigatório)

### Aprovado

```json
{
  "decisao": "sim",
  "nivel_confianca": "alto",
  "motivo": "Cliente compra SUCO BOLSA LARANJA semanalmente com padrão estável",
  "pedido_sugerido": [
    {
      "codPro": "SBSSSLAR",
      "desPro": "SUCO BOLSA LARANJA",
      "qtdPed": 13
    }
  ],
  "valor_medio": 442.0,
  "mensagem": "Olá! Vi que seus pedidos costumam acontecer por essa época.\n\nNo último padrão de compra você levou:\n13x Suco Bolsa Laranja\n\nQuer repetir o pedido ou ajustar algo?"
}
```

### Rejeitado

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

## Persistência após Validação

| Campo          | Valor                                                  |
|----------------|--------------------------------------------------------|
| `ai_validated` | `true`                                                 |
| `ai_decision`  | `"sim"` ou `"nao"`                                     |
| `ai_reasoning` | JSON completo da resposta (string)                     |
| `status`       | `"ai_approved"`, `"ai_rejected"` ou `"needs_review"`  |
| `updated_at`   | timestamp atual                                        |

---

## Saída do Script

```json
{
  "ok": true,
  "data": {
    "processed": 5,
    "approved": 3,
    "rejected": 2,
    "needs_review": 1,
    "errors": []
  }
}
```

---

## Edge Cases

| Situação                                            | Comportamento                                                        |
|-----------------------------------------------------|----------------------------------------------------------------------|
| Resposta da IA fora do JSON                         | Logar erro, pular candidato, **não atualizar status**               |
| `OPENAI_API_KEY` ausente                            | Falha imediata com mensagem clara                                    |
| Candidato sem itens nos pedidos                     | Rejeitar (`ai_rejected`) com motivo "dados insuficientes"           |
| `nivel_confianca = "baixo"` com `decisao = "sim"`   | Marcar como `needs_review`                                          |
| `decisao = "sim"` sem `pedido_sugerido`             | Marcar como `needs_review` (contato genérico possível, sem auto-disparo) |
| Produto sugerido com `codPro` fora do histórico     | **Rejeitar resposta inteira** — candidato não é atualizado          |
| Campo `decisao` ou `nivel_confianca` inválido       | Logar erro, pular candidato, não atualizar status                   |
| Valor médio inconsistente                           | Aceitar o que a IA retornar — não é motivo de rejeição              |
