# Requisicoes do ClicVendas

Este arquivo documenta somente as requisicoes que o projeto faz para o **ClicVendas**.

## Visao geral

Hoje o fluxo real do projeto usa estas chamadas:

1. `POST /login` no servidor de autenticacao
2. `POST /refresh` no servidor de autenticacao
3. `GET /extpedidos` na API principal

Arquivos envolvidos:

- `execution/clic_vendas_client.py`
- `execution/fetch_pedidos_clic.py`
- `openapi-clicvendas.txt` como referencia local de endpoints

Configuracao lida do `.env`:

- `CLIC_VENDAS_URL`
- `CLIC_VENDAS_AUTH_URL`
- `CLIC_VENDAS_USER`
- `CLIC_VENDAS_PASSWORD`
- `CLIC_VENDAS_SUBDOMAIN`

Observacao:

- Se `CLIC_VENDAS_SUBDOMAIN` nao existir no `.env`, o codigo usa o valor padrao `sucosspres`.

## 1. Login

### O que e
Autenticacao inicial para obter `accessToken` e `refreshToken`.

### Como e feita

- Metodo: `POST`
- URL:
  - `{CLIC_VENDAS_AUTH_URL}/login`
- Headers:
  - `Content-Type: application/json`
  - `Accept: application/json`
  - `subdominio: {CLIC_VENDAS_SUBDOMAIN ou sucosspres}`
- Body:

```json
{
  "login": "{CLIC_VENDAS_USER}",
  "senha": "{CLIC_VENDAS_PASSWORD}",
  "subdominio": "{CLIC_VENDAS_SUBDOMAIN ou sucosspres}"
}
```

### Como e usada

- Implementada em `execution/clic_vendas_client.py` no metodo `_login()`.
- E chamada automaticamente antes da primeira requisicao autenticada.

### Resposta esperada

```json
{
  "accessToken": "...",
  "refreshToken": "..."
}
```

## 2. Refresh de token

### O que e
Renovacao do token JWT quando o access token expira.

### Como e feita

- Metodo: `POST`
- URL:
  - `{CLIC_VENDAS_AUTH_URL}/refresh`
- Headers:
  - `Content-Type: application/json`
  - `Accept: application/json`
  - `subdominio: {CLIC_VENDAS_SUBDOMAIN ou sucosspres}`
- Body:

```json
{
  "refreshToken": "{refreshToken_atual}"
}
```

### Como e usada

- Implementada em `execution/clic_vendas_client.py` no metodo `_refresh_access_token()`.
- O cliente tenta refresh antes de fazer novo login.

## 3. Buscar pedidos

### O que e
Consulta de pedidos no endpoint externo do ClicVendas.

### Como e feita

- Metodo: `GET`
- URL:
  - `{CLIC_VENDAS_URL}/extpedidos`
- Headers:
  - `Accept: application/json`
  - `subdominio: {CLIC_VENDAS_SUBDOMAIN ou sucosspres}`
  - `Authorization: Bearer {accessToken}`
- Query params:
  - `numeroDocumentoRepresentante`
  - `dataAlteracao`
  - `sortBy`
  - `sortDescAsc`
  - `fetch`
  - `skip`
- Body:
  - sem body no uso validado em Postman

### Como e usada

- `execution/fetch_pedidos_clic.py`
- Fluxo:
  - chama `client.get('/extpedidos')`
  - recebe a resposta JSON
  - extrai `dados[]`
  - filtra localmente por janela de dias
  - opcionalmente filtra localmente por `cod_cli`

### Comportamento validado

Embora a documentacao visual do endpoint mostre um schema de `body` para o `GET`,
o comportamento que funcionou no teste manual foi:

- enviar os filtros em `Params`
- nao enviar `body`
- remover o header `Content-Type`
- usar `numeroDocumentoRepresentante` com o **documento** do representante
- usar `sortBy=dataCriacao`
- usar `sortDescAsc=DESC`
- usar `fetch=0`
- usar `skip=0`

### Exemplo funcional validado

Headers:

```text
Accept: application/json
subdominio: sucosspres
Authorization: Bearer {ACCESS_TOKEN}
```

Params:

```text
numeroDocumentoRepresentante={DOCUMENTO_DO_REPRESENTANTE}
dataAlteracao=2026-02-23T00:00:00.000Z
sortBy=dataCriacao
sortDescAsc=DESC
fetch=0
skip=0
```

### Estrutura esperada da resposta

O codigo espera algo neste formato:

```json
{
  "dados": [
    {
      "_id": "...",
      "numero": 12345,
      "dataCriacao": "2026-03-25T10:00:00.000Z",
      "cliente": {
        "backoffice": {
          "codigo": 999
        }
      },
      "representante": {
        "backoffice": {
          "codigo": 4
        }
      },
      "totais": {
        "valorTotalLiquido": 150.75
      },
      "situacao": {
        "id": "aprovado"
      },
      "itens": []
    }
  ],
  "totalGeral": 1
}
```

## 4. Reautenticacao automatica em caso de 401

### O que e
Comportamento automatico do cliente quando uma chamada autenticada retorna `401`.

### Como funciona

1. A requisicao autenticada falha com `401`
2. O cliente chama `_login()` novamente
3. Repete a mesma requisicao uma vez

### Onde existe

- `execution/clic_vendas_client.py`
- Vale tanto para `get()` quanto para `post()`

## 5. Metodo POST generico do cliente

### O que e
O cliente tambem possui um metodo `post(endpoint, data)` para chamadas autenticadas.

### Situacao atual

- Existe em `execution/clic_vendas_client.py`
- No fluxo atual do projeto, nao encontrei nenhum endpoint ClicVendas sendo usado por esse metodo

### Formato

- Metodo: `POST`
- URL:
  - `{CLIC_VENDAS_URL}{endpoint}`
- Headers:
  - `Content-Type: application/json`
  - `Accept: application/json`
  - `subdominio: {CLIC_VENDAS_SUBDOMAIN ou sucosspres}`
  - `Authorization: Bearer {accessToken}`
- Body:
  - JSON enviado em `data`

## 6. Resumo rapido

- Autenticar:
  - `POST {CLIC_VENDAS_AUTH_URL}/login`
- Renovar token:
  - `POST {CLIC_VENDAS_AUTH_URL}/refresh`
- Puxar pedidos:
  - `GET {CLIC_VENDAS_URL}/extpedidos` com filtros em `Params`

## 7. Requisicao montada para puxar pedidos

Sem executar a API, o projeto montaria a chamada assim:

```http
GET /api/extpedidos HTTP/1.1
Host: sucosspres.clictecnologia.com.br
Accept: application/json
subdominio: sucosspres
Authorization: Bearer {ACCESS_TOKEN_OBTIDO_NO_LOGIN}
```

Equivalente em `curl`:

```bash
curl --request GET \
  --url "https://sucosspres.clictecnologia.com.br/api/extpedidos?numeroDocumentoRepresentante={DOCUMENTO_DO_REPRESENTANTE}&dataAlteracao=2026-02-23T00:00:00.000Z&sortBy=dataCriacao&sortDescAsc=DESC&fetch=0&skip=0" \
  --header "Accept: application/json" \
  --header "subdominio: sucosspres" \
  --header "Authorization: Bearer {ACCESS_TOKEN_OBTIDO_NO_LOGIN}"
```

Observacao:

- O unico campo que nao pode ficar literalmente preenchido sem chamar a autenticacao e o `Bearer token`.
- O uso em `Params` e a remocao do `Content-Type` vieram do teste manual validado.
- O campo `numeroDocumentoRepresentante` deve receber o documento do representante, nao o codigo interno.
