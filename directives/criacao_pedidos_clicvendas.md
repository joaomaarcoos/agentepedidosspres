# Diretriz - Criacao de Pedidos no Clic Vendas

## Objetivo

Definir o fluxo conversacional e o contrato de dados para a futura tool que monta e envia pedidos para o Clic Vendas.

Esta diretriz ainda e preparatoria. A tool de envio so deve ser implementada depois de confirmar os campos pendentes da API.

## Caso atual mapeado

- Nome: Eliezer Gonzaga dos Reis
- Documento: `34501704810`
- Telefone autorizado da secretaria: `5516991377335`

## Tipos de pedido

Existem tres tipos de pedido no fluxo atualmente mapeado:

| Tipo falado pelo representante | Codigo Clic | Nome visto no Clic | Observacao obrigatoria |
| --- | --- | --- | --- |
| Normal com nota fiscal | `9010O` | `9010O - Entrada pedido normal` | Nao |
| PDV sem nota | `9010P` | `9010P - Entrada pedido PDV` | Sim |
| Bonificacao | `BONIF4` | `BONIF4 - Bonificacao - Acordo Comercial` | Sim |

O preco dos itens nao muda por ser bonificacao. A bonificacao e identificada pelo tipo de venda, e o Clic/Senior trata a regra a partir desse tipo.

Tipos de venda ativos vistos no Clic:

| ID | Nome | ID Externo | Situacao |
| --- | --- | --- | --- |
| `BONIF5` | `Bonificacao - Outros` | `BONIF` | `A` |
| `BONIF4` | `Bonificacao - Acordo Comercial` | `BONIF` | `A` |
| `BONIF3` | `Bonificacao - Problema de qualidade` | `BONIF` | `A` |
| `BONIF2` | `Bonificacao - Avaria` | `BONIF` | `A` |
| `9010M` | `Entrada pedido RPMG` | `9010M` | `A` |
| `BONIF1` | `Bonificacao - Vencimento` | `BONIF` | `A` |
| `9010P` | `Entrada pedido PDV` | `9010P` | `A` |
| `9010O` | `Entrada pedido normal` | `9010O` | `A` |

## Regras gerais de preenchimento

- Forma de pagamento: nao enviar; deixar o Clic/Senior preencher automaticamente.
- Condicao de pagamento: nao enviar; deixar o Clic/Senior preencher automaticamente.
- Frete: nao enviar `tipoFrete` e nao enviar `valorFrete`, nem como zero.
- Situacao: nao enviar; deixar o Clic/Senior definir automaticamente.
- Ordem de compra: nao enviar.
- Endereco de entrega: nao enviar.
- Previsao de entrega: nao enviar no payload do Clic Vendas; deixar o Clic/Senior preencher automaticamente.
- Observacao: coletar no fluxo para PDV/bonificacao, mas nao enviar no payload do Clic Vendas porque o schema de criacao nao possui campo de observacao.
- Tipo de observacao: nao enviar.
- Data/hora da observacao: pode ser guardada internamente, mas nao enviar ao Clic Vendas.
- Itens: usar preco unitario da tabela correta do cliente.
- Tabela de preco: usar a tabela do cliente; se houver tabela especial por produto/variacao, ela deve prevalecer para aquele item.

## Fluxo conversacional

O fluxo possui tres etapas obrigatorias e uma etapa condicional:

1. Dados do cliente
2. Dados gerais
3. Itens do pedido
4. Observacao do cliente, somente para PDV sem nota e bonificacao

Depois dessas etapas, a secretaria deve montar um resumo completo e pedir confirmacao final antes de enviar a requisicao.

## Arquitetura da tool

A tool de criacao de pedido deve ser tratada como um fluxo de subagente da secretaria.

Responsabilidades do subagente/secretaria:

- conduzir a conversa com o representante;
- coletar codigo do cliente, tipo de pedido e itens;
- buscar os dados reais do cliente, produtos, variacoes, tabela de preco e precos;
- montar o pedido em estrutura interna;
- calcular subtotal por item e total geral;
- pedir confirmacao final ao representante;
- somente depois da confirmacao, chamar o backend para tentar criar o pedido.

Responsabilidades da trava do backend:

- validar que o telefone autorizado esta correto;
- validar que o cliente pertence ao representante correto;
- validar que o representante do payload e o documento esperado;
- validar que todos os produtos e variacoes existem;
- validar que os precos batem com a tabela correta do cliente;
- validar tabela especial por produto, quando existir;
- validar que o tipo de venda existe e esta ativo;
- remover/recusar campos que nao devem ser enviados, como forma de pagamento, condicao de pagamento, frete, situacao, numero externo, observacao, previsao de entrega, ordem de compra e endereco de entrega;
- montar o payload final permitido;
- enviar ao Clic Vendas somente se todas as validacoes passarem.

O subagente nao deve ter permissao de enviar livremente qualquer JSON para o Clic. Ele monta uma intencao de pedido; o backend confere e transforma isso no payload final.

## 1. Dados do cliente

### Pergunta

A secretaria pergunta o codigo do cliente.

Exemplo:

```text
Qual e o codigo do cliente?
```

### Acao

Ao receber o codigo, a secretaria busca o cliente na base.

Campos esperados:

- codigo externo do cliente;
- numero do documento;
- nome/razao social;
- endereco;
- tabela de preco padrao;
- eventuais tabelas especiais.

### Confirmacao ao representante

A secretaria retorna os dados encontrados e pede confirmacao.

Exemplo:

```text
Encontrei este cliente:

Codigo: 1233
Documento: 05.482.507/0001-42
Nome: BIUNESSA & GAZZOTTI DISTRIBUIDORA DE ALIMENTOS LTDA
Endereco: R ATILIO BATISTON - CRAVINHOS

Esse e o cliente correto?
```

Se o representante negar, a secretaria deve pedir outro codigo e nao seguir para os dados gerais.

## 2. Dados gerais

### Forma e condicao de pagamento

Nao enviar forma de pagamento nem condicao de pagamento no payload.

Esses campos sao preenchidos automaticamente quando o representante cria pedido pela web no Clic. Para manter o mesmo comportamento, a tool deve omitir:

- `codigoFormaPagamento`
- `codigoCondicaoPagamento`

Catalogo de condicoes de pagamento ativas visto no Clic, mantido apenas como referencia operacional:

Condicoes de pagamento ativas vistas no Clic, considerando somente situacao `A`:

| Codigo | Descricao | Codigo ERP |
| --- | --- | --- |
| `25E` | `25 DIAS DATAS FIXAS 10/20/30` | `25E` |
| `0714` | `7 14 Dias` | `0714` |
| `RDOR` | `REDE D OR 28D Fixo: 05, 10, 15, 20, 25 ou 30` | `RDOR` |
| `28ESPE` | `28 DDL - Dias Fixo 02, 12 e 22` | `28ESPE` |
| `51530` | `3 dias fixo 02/15/30` | `51530` |
| `D15` | `TODO DIA 15 DO MES` | `D15` |
| `1530E` | `FIXO 15 E 30 COM PRAZO DE 7` | `1530E` |
| `101421` | `parcelas de 10/14/21` | `101421` |
| `35/42` | `35 e 42 dias` | `35/42` |
| `SAV` | `SAVEGNAGO - 10, 20 E 30` | `SAV` |
| `01421` | `Entrada + 14D + 21 D` | `01421` |
| `25D` | `25 DIAS CORRIDOS` | `25D` |
| `21QUA` | `21 Dias Fixo Quarta-Feira` | `21QUA` |
| `AV7D` | `50% A Vista - 50% 7 Dias` | `AV7D` |
| `6X` | `30/60/90/120/150/180` | `6X` |
| `1530` | `15 E 30 DIAS CORRIDOS` | `1530` |
| `3X7` | `7 /14 / 21 dias` | `3X7` |
| `28DOR` | `28 Dias Rede Dor - Dias especiais: 10, 20 ou 30` | `28DOR` |
| `2128DI` | `21 / 28 dias` | `2128DI` |
| `60-150` | `60/90/120/150` | `60-150` |
| `212835` | `21 / 28 / 35 / 42` | `212835` |
| `142842` | `14 / 28 / 42` | `142842` |
| `1530O2` | `15 / 30 / 15` | `1530O2` |
| `2345` | `28 / 35 / 42 / 56` | `2345` |
| `2344` | `28/35/42/49/56` | `2344` |
| `60D` | `60dias` | `60D` |
| `2D5D` | `2 DDL / 5 DDL` | `2D5D` |
| `AV25` | `50% A vista / 2 DDL / 5 DDL` | `AV25` |
| `11020` | `01 / 10 / 20 dias fixos` | `11020` |
| `2135` | `21 / 35 Dias` | `2135` |
| `10X` | `10 PARCELAS A CADA 30 DIAS` | `10X` |
| `3X30` | `30 / 60 / 90` | `3X30` |
| `5XPG` | `21 / 28 / 35 / 42 / 49DIAS` | `5XPG` |
| `01D` | `01 Dia` | `01D` |
| `284560` | `28/ 45/ 60 dias` | `284560` |
| `284256` | `28 / 42 / 56 dias` | `284256` |
| `053060` | `05/ 30/ 60 DIAS` | `053060` |
| `2856` | `28/ 56 dias` | `2856` |
| `285684` | `28/ 56/ 84 dias` | `285684` |
| `08D` | `08 Dias Direto` | `08D` |
| `1421D` | `14/21 Dias` | `1421D` |
| `23E` | `23 Dias - Dia Especial 10/20/30` | `23E` |
| `15E` | `15 Dias Especial - Fixo 10/15/20` | `15E` |
| `354249` | `35 / 42 / 49 Dias` | `354249` |
| `304560` | `30 / 45 / 60 Dias` | `304560` |
| `142128` | `14/21/28DDL` | `142128` |
| `2040` | `20/40ddl` | `2040` |
| `28Q` | `28 DIAS QUARTA-FEIRA` | `28Q` |
| `40FS` | `40 Dias Fora a Semana (5a-Feira)` | `40FS` |
| `07F` | `07 dias Fora o Mes` | `07F` |
| `6P7` | `21 / 28 / 35 / 42 / 49 / 56` | `6P7` |
| `301025` | `30 DIAS VENCTO FIXO 10 OU 25` | `301025` |
| `53D` | `53 Dias Direto` | `53D` |
| `10F` | `10 Dias Fora o Mes` | `10F` |
| `32D` | `32 Dias Direto` | `32D` |
| `4X` | `30/60/90/120 DIAS` | `4X` |
| `45FS` | `45 DIAS FORA SEMANA` | `45FS` |
| `D10` | `TODO DIA 10 DO MES` | `D10` |
| `20F` | `20 Dias Fora o Mes` | `20F` |
| `42D` | `42 DIAS DIRETO` | `42D` |
| `30F` | `30 DIAS FORA MES` | `30F` |
| `45D` | `45 DIAS` | `45D` |
| `37D` | `37 DIAS UTEIS` | `37D` |
| `35D` | `35 DIAS UTEIS` | `35D` |
| `30D` | `30 DIAS UTEIS` | `30D` |
| `28D` | `28 DIAS UTEIS` | `28D` |
| `21D` | `21 DIAS UTEIS` | `21D` |
| `15F` | `15 DIAS FORA QUINZENA` | `15F` |
| `15D` | `15 DIAS UTEIS` | `15D` |
| `14D` | `14 DIAS UTEIS` | `14D` |
| `10D` | `10 DIAS UTEIS` | `10D` |
| `05D` | `05 DIAS UTEIS` | `05D` |
| `03D` | `03 DIAS UTEIS` | `03D` |
| `07D` | `07 DIAS UTEIS` | `07D` |
| `AV` | `A VISTA` | `AV` |
| `2835` | `28/35` | `2835` |
| `2X` | `30/60 DIAS` | `2X` |
| `3X` | `21/28/35 DIAS` | `3X` |

### Tipo de venda

A secretaria deve perguntar o tipo de pedido.

Exemplo:

```text
Qual e o tipo do pedido: normal com nota, PDV sem nota ou bonificacao?
```

Mapeamento:

- normal com nota fiscal -> `9010O`
- PDV sem nota -> `9010P`
- bonificacao -> `BONIF4`

### Campos omitidos nos dados gerais

Nao preencher/enviar:

- ordem de compra;
- endereco de entrega;
- tipo de frete;
- valor de frete.

### Previsao de entrega

Nao enviar no payload do Clic Vendas.

A regra operacional conhecida e:

```text
proximo dia util ate 15h
```

Como o schema de criacao nao possui campo de previsao de entrega, a tool deve omitir esse dado e deixar o Clic/Senior preencher automaticamente.

## 3. Itens do pedido

### Pergunta

A secretaria pede os itens do pedido com codigo de produto e quantidade.

Exemplo:

```text
Me envie os itens do pedido com codigo do produto e quantidade.
```

### Acao

Para cada item, a secretaria deve:

1. identificar o produto pelo codigo;
2. identificar a variacao/derivacao;
3. buscar o preco unitario na tabela correta do cliente;
4. calcular o subtotal do item;
5. manter uma lista acumulada do pedido.

Campos por item:

- `codigoProduto`
- `codigoVariacao`
- `quantidade`
- `precoVenda`
- `codigoTabelaPreco`
- `percentualDesconto`
- `percentualAcrescimo`

Regras:

- `precoVenda` vem da tabela do cliente.
- `codigoTabelaPreco` vem da tabela padrao do cliente ou da tabela especial do item, quando existir.
- `percentualDesconto` deve ser `0`, exceto se houver regra/tabela informando desconto.
- `percentualAcrescimo` deve ser `0`, exceto se houver regra/tabela informando acrescimo.

### Confirmacao dos itens

Antes de seguir, a secretaria deve mostrar a lista consolidada:

- codigo do produto;
- nome do produto;
- variacao;
- quantidade;
- preco unitario;
- total do item;
- total geral do pedido.

Exemplo:

```text
Itens do pedido:

1. SGRSSLAR-1L7 - Suco Garrafa Pasteurizado de Laranja 1,7L
   Quantidade: 60
   Preco unitario: R$ 10,78
   Total: R$ 646,80

2. SGRSSCAJ-1L7 - Suco Garrafa Caju 1,7L
   Quantidade: 60
   Preco unitario: R$ 8,63
   Total: R$ 517,80

Total geral: R$ 1.164,60

Os itens estao corretos?
```

Se o representante pedir ajuste, a secretaria altera os itens e mostra o resumo novamente.

## 4. Observacao do cliente

Esta etapa so existe para:

- PDV sem nota;
- bonificacao.

Pedido normal com nota fiscal nao deve pedir observacao por padrao.

### Pergunta

Exemplo:

```text
Qual observacao devo adicionar nesse pedido?
```

### Preenchimento

- Tipo de observacao: vazio/nulo.
- Observacao: texto informado pelo representante.
- Data/hora: momento em que o pedido esta sendo montado.

Exemplo de observacao PDV:

```text
APLICAR 10% DE DESCONTO SOBRE O TOTAL DO PEDIDO
```

Exemplo de observacao bonificacao:

```text
ACORDO COMERCIAL
```

Confirmado: o schema de criacao de pedido nao possui campo para observacao.

Portanto, a observacao deve ser tratada como dado operacional do fluxo da secretaria, mas nao deve ser enviada no payload do Clic Vendas nesta tool.

## Resumo final antes do envio

Depois de coletar todos os dados, a secretaria deve montar um resumo final e pedir confirmacao explicita.

O resumo deve conter:

- cliente;
- documento;
- endereco;
- tipo de pedido;
- itens com quantidade, preco unitario e total;
- total geral;
- observacao, quando aplicavel, deixando claro que ela nao sera enviada ao Clic se o schema atual continuar sem esse campo.

Exemplo de pergunta final:

```text
Confirma o envio desse pedido para o Clic Vendas?
```

Somente depois de uma confirmacao clara, como `confirmo`, `pode enviar`, `esta correto` ou equivalente, a secretaria pode montar e enviar a requisicao.

## Payload base esperado

O schema informado pelo Clic Vendas espera um array de pedidos.

Campos que devem ser enviados quando confirmados:

```json
[
  {
    "numeroDocumentoCliente": "DOCUMENTO_CLIENTE",
    "numeroDocumentoRepresentante": "34501704810",
    "codigoTipoVenda": "9010O_OU_9010P_OU_BONIF4",
    "itens": [
      {
        "codigoProduto": "CODIGO_PRODUTO",
        "codigoVariacao": "CODIGO_VARIACAO",
        "quantidade": 1,
        "precoVenda": 0,
        "codigoTabelaPreco": "CODIGO_TABELA",
        "percentualDesconto": 0,
        "percentualAcrescimo": 0
      }
    ]
  }
]
```

Campos que nao devem ser enviados neste momento:

- `tipoFrete`
- `valorFrete`
- `situacao`
- `codigoFormaPagamento`
- `codigoCondicaoPagamento`
- `numeroPedidoClicVenda`, para pedido novo
- `numeroExternoPedido`
- ordem de compra
- endereco de entrega
- previsao de entrega

Observacao: `numeroExternoPedido` nao deve ser enviado neste fluxo.

## Obrigatoriedade dos campos

Pelo schema informado do Clic Vendas, os campos obrigatorios para criar pedido novo sao:

Pedido:

- `numeroDocumentoCliente`
- `numeroDocumentoRepresentante`
- `itens`

Item:

- `codigoProduto`
- `quantidade`
- `precoVenda`

Campos nao marcados como obrigatorios no schema, mas necessarios pela regra de negocio para o pedido sair correto:

- `codigoTipoVenda`
- `codigoVariacao`, quando o produto tiver variacao/derivacao
- `codigoTabelaPreco`, para garantir preco da tabela correta do cliente
- `percentualDesconto`, enviar `0`
- `percentualAcrescimo`, enviar `0`

## Informacoes ja disponiveis

Ja temos ou sabemos preencher:

- documento do representante: `34501704810`;
- codigo de tipo de venda para normal, PDV e bonificacao;
- codigo do cliente, documento, nome e endereco quando o cliente esta cadastrado;
- tabela de preco do cliente;
- produtos, variacoes e precos;
- quantidade informada pelo representante;
- total por item e total geral;
- observacao para PDV/bonificacao, perguntada na hora;
- data/hora da observacao;
- previsao de entrega nao enviada ao Clic; preenchimento fica automatico pelo Clic/Senior.

## Pendencias antes da tool de envio

Antes de implementar o envio real, confirmar:

1. Se o endpoint aceita omitir completamente `codigoFormaPagamento`, `codigoCondicaoPagamento`, `tipoFrete`, `valorFrete`, `situacao` e `numeroExternoPedido`.

## Comportamento de seguranca

A secretaria nao deve enviar pedido quando faltar qualquer informacao obrigatoria ou quando houver divergencia entre:

- codigo do cliente informado e cliente encontrado;
- tabela de preco do cliente e preco do item;
- produto/variacao informados e produto encontrado;
- tipo de pedido e codigo de tipo de venda.

Nesses casos, deve parar o fluxo e pedir confirmacao/correcao ao representante.
