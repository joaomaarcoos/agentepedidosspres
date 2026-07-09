# Diretriz - Criacao de Pedidos no Senior ERP

## Objetivo

Mapear a requisicao SOAP direta para gravar pedidos no Senior ERP.

Esta diretriz define o contrato inicial. Antes de ligar em producao, ainda faltam confirmar alguns codigos comerciais do ambiente Senior.

## Web service correto

Servico Senior:

- Web service: `com.senior.g5.co.mcm.ven.pedidos`
- Porta de criacao: `GravarPedidos`
- Porta de observacao: `inserirObservacoes`
- Descricao Senior: Mercado - Gestao de Vendas - Pedidos - Gravar Pedidos
- Endpoint sincrono: `${SENIOR_BASE_URL}/g5-senior-services/sapiens_Synccom_senior_g5_co_mcm_ven_pedidos`
- WSDL: `${SENIOR_BASE_URL}/g5-senior-services/sapiens_Synccom_senior_g5_co_mcm_ven_pedidos?wsdl`
- SOAPAction: vazio (`""`)
- Content-Type: `text/xml; charset=utf-8`

Validacao feita em 2026-07-01: o WSDL do ambiente configurado respondeu HTTP 200.

## Fontes consultadas

- Documentacao oficial Senior: `Web service Com.senior.g5.co.mcm.ven.pedidos`.
- WSDL/XSD do ambiente configurado em `SENIOR_BASE_URL`.
- Print de exemplo com `ser:GravarPedidos`.
- Fluxo atual da secretaria em `execution/secretary_agent.py`.
- Exemplo historico de pedido sincronizado em `outputs/payload_pedido_clic_84475545_com_tabela_preco.json`.

## Decisao atual

Usar inicialmente o mesmo payload minimo do teste validado no Senior, conforme print enviado.

Esse payload ja funcionou gravando pedido por usuario/senha e deve ser tratado como o contrato inicial. Campos extras so devem ser adicionados depois de uma necessidade real em teste ou por regra comercial confirmada.

Em 2026-07-01, o envio real com usuario Senior autorizado gravou e fechou o pedido `352739` com retorno:

- `mensagemRetorno`: `Processado com Sucesso.`
- `tipRet`: `1`
- `sitPed`: `1`
- itens com `retorno=OK` e `sitIpd=1`

O fluxo ativo da secretaria deve enviar pedidos direto ao Senior ERP. A criacao de pedidos nao usa ClicVendas.

## Requisicao SOAP base minima validada

```xml
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
                  xmlns:ser="http://services.senior.com.br">
  <soapenv:Header/>
  <soapenv:Body>
    <ser:GravarPedidos>
      <user>${SENIOR_USER}</user>
      <password>${SENIOR_PASSWORD}</password>
      <encryption>${SENIOR_ENCRYPTION}</encryption>
      <parameters>
        <pedido>
          <opeExe>I</opeExe>
          <codEmp>${SENIOR_COD_EMP}</codEmp>
          <codFil>${SENIOR_COD_FIL}</codFil>
          <tipPed>1</tipPed>
          <codCli>${CODIGO_CLIENTE_SENIOR}</codCli>
          <fecPed>S</fecPed>

          <produto>
            <opeExe>I</opeExe>
            <codPro>${CODIGO_PRODUTO}</codPro>
            <codDer>${CODIGO_VARIACAO}</codDer>
            <qtdPed>${QUANTIDADE}</qtdPed>
          </produto>
        </pedido>
      </parameters>
    </ser:GravarPedidos>
  </soapenv:Body>
</soapenv:Envelope>
```

## Campos usados no payload minimo

Autenticacao e ambiente:

- `SENIOR_BASE_URL`: ja existe no `.env`.
- `SENIOR_USER`: ja existe no `.env`.
- `SENIOR_PASSWORD`: ja existe no `.env`.
- `SENIOR_ENCRYPTION`: ja existe no `.env`.
- `SENIOR_COD_EMP`: ja existe no `.env`.
- `SENIOR_COD_FIL`: ja existe no `.env`.
- `SENIOR_SYSTEM_ID`: ja existe no `.env`, mas nao sera enviado no payload minimo.

Pedido:

- `opeExe`: fixo `I` para incluir.
- `codEmp`: temos em `SENIOR_COD_EMP`.
- `codFil`: temos em `SENIOR_COD_FIL`.
- `codCli`: temos como `customer_code` em `secretary_orders` e `cod_cli` em `rep_order_base`. A origem operacional desse codigo e o cadastro/pedido sincronizado do Senior.
- `tipPed`: no teste validado foi `1`.
- `fecPed`: usar `S` para fechar o pedido.

Itens:

- `produto.opeExe`: fixo `I` para incluir item.
- `codPro`: temos nos itens do pedido (`cod_produto`) e no catalogo/tabela.
- `codDer`: temos como `derivacao`/`variacao`; ja existe normalizacao em `secretary_agent.py`.
- `qtdPed`: temos como `quantidade`.

## Codigos necessarios para o payload minimo

- Codigo da empresa Senior: ja temos (`SENIOR_COD_EMP`).
- Codigo da filial Senior: ja temos (`SENIOR_COD_FIL`).
- Codigo do cliente Senior: temos pelo cadastro/pedido sincronizado (`codCli`/`customer_code`).
- Tipo do pedido Senior: no teste validado, `tipPed=1`.
- Codigo do produto Senior: temos (`codPro`/`cod_produto`).
- Codigo da derivacao Senior: temos (`codDer`/`derivacao`).

Nao falta outro codigo para reproduzir o payload do print.

Os codigos de tipo de venda (`9010O`, `9010P`, `BONIF4` etc.) ficam fora do payload minimo. Eles so entram se descobrirmos, em teste, qual campo o Senior exige para diferenciar normal, PDV e bonificacao na gravacao direta. O principal candidato e `tnsPro`, mas o payload validado nao precisou dele.

## Observacao do pedido

Confirmado no XSD do proprio servico Senior em 2026-07-03: a observacao nao deve ser enviada dentro de `GravarPedidos`.

O servico possui uma operacao separada chamada `inserirObservacoes`.

Campos de entrada da operacao `inserirObservacoes`:

- `pedido.codigoEmpresa`: empresa Senior. Origem: `SENIOR_COD_EMP`.
- `pedido.codigoFilial`: filial Senior. Origem: `SENIOR_COD_FIL`.
- `pedido.numeroPedido`: numero retornado por `GravarPedidos` em `respostaPedido.numPed`.
- `pedido.observacao`: texto informado pelo representante no WhatsApp.
- `pedido.sequenciaItemProduto`: opcional. Usar vazio para observacao geral do pedido.
- `pedido.sequenciaItemServico`: opcional. Usar vazio para observacao geral do pedido.

Fluxo correto:

1. Chamar `GravarPedidos` para criar o pedido.
2. Ler `respostaPedido.numPed`.
3. Se o representante informou observacao, chamar `inserirObservacoes` usando o numero do pedido retornado.
4. Salvar log separado para `GravarPedidos` e para `inserirObservacoes`.

Payload SOAP de observacao geral do pedido:

```xml
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
                  xmlns:ser="http://services.senior.com.br">
  <soapenv:Header/>
  <soapenv:Body>
    <ser:inserirObservacoes>
      <user>${SENIOR_USER}</user>
      <password>${SENIOR_PASSWORD}</password>
      <encryption>${SENIOR_ENCRYPTION}</encryption>
      <parameters>
        <pedido>
          <codigoEmpresa>${SENIOR_COD_EMP}</codigoEmpresa>
          <codigoFilial>${SENIOR_COD_FIL}</codigoFilial>
          <numeroPedido>${NUMERO_PEDIDO_RETORNADO}</numeroPedido>
          <observacao>${OBSERVACAO_DO_REPRESENTANTE}</observacao>
        </pedido>
      </parameters>
    </ser:inserirObservacoes>
  </soapenv:Body>
</soapenv:Envelope>
```

Regra: nao inventar campo `obsPed` em `GravarPedidos`. `obsPed` aparece em estruturas de exportacao/consulta, mas a gravacao direta de observacao confirmada para este servico e `inserirObservacoes`.

## Implementacao atual

- Cliente SOAP: `execution/senior_order_client.py`.
- Envio ativo da secretaria: `_submit` em `execution/secretary_agent.py`.
- Payload salvo em `secretary_orders.submit_payload` com senha mascarada.
- Resposta salva em `secretary_orders.submit_response`.
- Numero Senior salvo provisoriamente em `secretary_orders.clic_order_number` por compatibilidade com schema/UI existente.
- Logs usam a tabela neutra `requisition_logs`, com fallback temporario para a tabela legada `clic_request_logs` enquanto a migracao nao tiver sido aplicada. Pedidos Senior devem registrar `source=secretary_senior` e `operation=GravarPedidos` ou `operation=inserirObservacoes`.

## Campos pendentes ou a confirmar

Obrigatorios pela documentacao ou pela regra comercial:

- `codCpg`: condicao de pagamento. Para Senior direto, precisa vir do cadastro do cliente/pedido ou de uma regra padrao.
- `cifFob`: frete CIF/FOB. Precisamos confirmar regra por cliente/pedido.
- `tnsPro`: transacao de pedido para produto. Deve ser mapeada por tipo de pedido.
- `pgtAnt`: pagamento antecipado. Sugestao inicial `N`, mas precisa confirmacao comercial.
- `uniMed`: unidade de medida por item. Sugestao inicial `UN`, mas precisa vir do cadastro do produto.
- `datEnt`: data de entrega do item. O Senior aceita no item; precisamos decidir se usamos data prevista calculada, data atual + regra, ou omitimos/testamos.
- `fecPed`: para fechar o pedido apos inserir, deve ir como `S`. Se omitido, o pedido pode ficar como situacao 9 - Nao Fechado.
- `numPed`: documentacao marca como obrigatorio; para inclusao provavelmente pode ir `0` ou vazio conforme regra do ambiente. Confirmar em teste homologado.
- `catCli`: documentacao marca como obrigatorio, mas informa que, se nao enviada, o Senior assume a categoria padrao do cliente. Confirmar se o ambiente aceita omitir.
- `codFpg`: forma de pagamento. Opcional no WSDL geral, mas pode ser obrigatoria conforme parametrizacao; hoje nao temos no fluxo da secretaria.
- `codTra`: transportadora. Opcional; hoje nao temos regra definida.
- `codDep`: deposito por item. Opcional, mas pode ser necessario se a transacao exigir baixa/reserva por deposito.
- `SENIOR_TNS_PRO_NORMAL`, `SENIOR_TNS_PRO_PDV`, `SENIOR_TNS_PRO_BONIFICACAO`: variaveis novas recomendadas para nao hardcodar transacoes.

Mapeamento de tipo de pedido:

- Normal com nota: confirmar se o correto no Senior e `9010O`, `90100` ou outro codigo/transacao.
- PDV sem nota: hoje mapeado como `9010P`; confirmar transacao Senior.
- Bonificacao: hoje mapeado como `BONIF4`; confirmar se entra em `tnsPro` ou se exige outro campo/regra.
- `tipPed`: usar `1` para pedido normal inicialmente. Bonificacao/PDV provavelmente continuam `1`; o diferencial deve ser `tnsPro`, mas falta confirmar.

## Resposta esperada

Campos principais do retorno:

- `tipoRetorno`: retorno geral do web service.
- `mensagemRetorno`: mensagem geral.
- `erroExecucao`: erro tecnico/servidor.
- `respostaPedido.numPed`: numero do pedido gravado.
- `respostaPedido.sitPed`: situacao do pedido.
- `respostaPedido.tipRet`: `1` processado com sucesso, `2` erro.
- `respostaPedido.retorno` / `msgRet`: detalhe do processamento.
- `respostaPedido.gridPro[]`: retorno por item, com `seqIpd`, `sitIpd` e `retorno`.

## Regras de seguranca para implementacao

- Nunca enviar XML livre montado pela IA.
- A secretaria monta uma intencao de pedido; o backend valida e gera o XML final.
- Validar representante, cliente, produto, derivacao, tabela, preco e quantidade antes de chamar o Senior.
- Logar payload e resposta com mascaramento de credenciais.
- Usar idempotencia por `secretary_orders.protocol`/`idempotency_key` para evitar duplicidade.
- Comecar com modo `dry-run` que apenas monta XML e, em seguida, teste homologado com pedido controlado.

## Proxima decisao tecnica

Antes de implementar o cliente SOAP final, precisamos confirmar:

1. Codigos `tnsPro` para normal, PDV e bonificacao.
2. Origem de `codCpg`, `codFpg`, `cifFob`, `uniMed`, `datEnt` e possivelmente `codDep`.
3. Se `numPed=0` e omissao de `catCli` sao aceitos no ambiente atual para inclusao.
4. Resultado real de homologacao da operacao `inserirObservacoes` no ambiente de producao controlado.
