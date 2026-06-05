# Prompts Da Marcela

## Estrutura Oficial

Os arquivos em `prompts/marcela` entram no system prompt nesta ordem:

1. `system.md`: identidade, escopo e prioridade.
2. `personality.md`: tom, formato WhatsApp e estilo.
3. `business_rules.md`: regras comerciais criticas.
4. `order_flow.md`: montagem, ajuste, confirmacao e registro de pedido.
5. `sales_strategy.md`: conducao comercial sem roteiro fixo.
6. `examples.md`: poucos exemplos alinhados ao comportamento atual.

`tools.md` nao deve fazer parte do prompt. Se existir material de ferramenta ou documentacao interna, mantenha fora de `prompts/marcela` ou fora da ordem oficial do `builder.py`.

## Onde Colocar Regra Nova

- Regra de identidade, escopo ou seguranca: `system.md`.
- Tom, tamanho de mensagem ou formatacao: `personality.md`.
- Regra comercial obrigatoria: `business_rules.md`.
- Fluxo de montar/alterar/confirmar pedido: `order_flow.md`.
- Tecnica de venda e condução: `sales_strategy.md`.
- Exemplo curto de comportamento: `examples.md`.

## O Que Evitar

- Duplicar a mesma regra em varios arquivos.
- Colocar frases fixas longas que virem template.
- Contradizer o backend: se o backend lista produtos reais, o prompt nao pode mandar perguntar apenas formato.
- Misturar documentacao tecnica de ferramenta com instrucao para o cliente.
- Colocar regras extensas na secao dinamica `DECISAO OPERACIONAL`; ela deve trazer estado atual, nao repetir o manual.

## Validacao

Antes de publicar mudancas, rode:

```powershell
python -m unittest tests.test_ai_agent_regressions tests.test_prompt_builder
python -m py_compile execution\ai_agent.py prompts\builder.py
```
