"""
fetch_pedidos_clic.py
=====================
Busca pedidos da API Clic Vendas (REST).

Uso:
    from fetch_pedidos_clic import fetch_pedidos_clic
    pedidos = fetch_pedidos_clic(dias=90)
"""

import os
import sys
import logging
from datetime import datetime, timedelta

# Adiciona o diretorio execution ao path para imports locais
sys.path.insert(0, os.path.dirname(__file__))

from clic_vendas_client import ClicVendasClient

logger = logging.getLogger(__name__)


def fetch_pedidos_clic(
    dias: int = 90,
    dry_run: bool = False,
    cod_cli: int | None = None,
) -> list[dict]:
    """
    Busca pedidos dos ultimos N dias via API Clic Vendas.

    Args:
        dias: Janela de dias para buscar (padrao: 90)
        dry_run: Se True, apenas imprime os parametros sem chamar a API
        cod_cli: Se informado, filtra apenas pedidos do cliente informado

    Returns:
        Lista de dicts com pedidos no formato padronizado.
    """
    data_limite = datetime.now() - timedelta(days=dias)

    if dry_run:
        logger.info('[DRY RUN] Buscaria pedidos dos ultimos %s dias', dias)
        logger.info('[DRY RUN] Data limite: %s', data_limite.strftime('%Y-%m-%d'))
        if cod_cli is not None:
            logger.info('[DRY RUN] Filtro por cliente: %s', cod_cli)
        return []

    logger.info('Buscando pedidos dos ultimos %s dias via Clic Vendas...', dias)

    try:
        client = ClicVendasClient()
        raw_pedidos = client.get('/extpedidos')
    except Exception as exc:
        logger.error('Erro ao buscar pedidos: %s', exc)
        raise

    # Normaliza e filtra pedidos
    pedidos = _parse_pedidos(raw_pedidos, data_limite)

    # Filtro por cliente se especificado
    if cod_cli is not None:
        pedidos = [p for p in pedidos if p.get('codCli') == cod_cli]

    logger.info('Total de pedidos encontrados: %s', len(pedidos))
    return pedidos


def _parse_pedidos(raw_pedidos: list | dict, data_limite: datetime) -> list[dict]:
    """
    Parseia e normaliza pedidos da API Clic Vendas.

    Estrutura da API Clic Vendas:
    - dados[]: array de pedidos
    - numero: numero do pedido
    - dataCriacao: data de criacao
    - cliente.backoffice.codigo: codigo do cliente
    - representante.backoffice.codigo ou autor.backoffice.codigo: codigo do rep
    - situacao: situacao do pedido
    - totais: valores totais
    - itens[]: itens do pedido

    Converte para o formato interno usado pelo projeto atual.
    """
    pedidos = []

    # API Clic Vendas retorna {dados: [...], totalGeral: N, ...}
    if isinstance(raw_pedidos, dict):
        raw_pedidos = raw_pedidos.get('dados') or []

    if not isinstance(raw_pedidos, list):
        raw_pedidos = [raw_pedidos] if raw_pedidos else []

    for raw in raw_pedidos:
        if not raw:
            continue

        # Extrai data do pedido
        dat_emi = _parse_date(raw)
        if dat_emi and dat_emi < data_limite:
            continue  # Pedido fora da janela de dias

        # Extrai codigo do cliente (backoffice.codigo ou _id)
        cliente = raw.get('cliente') or {}
        cod_cli = _safe_int(
            cliente.get('backoffice', {}).get('codigo') or
            cliente.get('codigo') or
            cliente.get('_id')
        )

        # Extrai codigo do representante (pode estar em representante ou autor)
        representante = raw.get('representante') or raw.get('autor') or {}
        cod_rep = _safe_int(
            representante.get('backoffice', {}).get('codigo') or
            representante.get('codigo') or
            representante.get('acesso', {}).get('login')
        )

        # Extrai valor total
        totais = raw.get('totais') or {}
        vlr_tot = _safe_float(
            totais.get('valorTotalLiquido') or
            totais.get('valorTotalBruto') or
            totais.get('totalPedido') or
            raw.get('valorTotal')
        )

        # Extrai situacao
        situacao = raw.get('situacao') or {}
        sit_ped = situacao.get('id') if isinstance(situacao, dict) else str(situacao)

        # Monta pedido normalizado
        pedido = {
            'numPed': _safe_int(raw.get('numero') or raw.get('_id')),
            'codCli': cod_cli,
            'codRep': cod_rep,
            'datEmi': dat_emi.strftime('%Y-%m-%d') if dat_emi else None,
            'sitPed': str(sit_ped or ''),
            'vlrTot': vlr_tot,
            'itens': _parse_itens(raw),
            # Campos extras do Clic Vendas
            '_id': raw.get('_id'),
            'nomeCliente': cliente.get('razaoSocial') or cliente.get('fantasia'),
            'nomeRep': representante.get('razaoSocial') or representante.get('fantasia'),
        }

        # So inclui se tiver pelo menos numero do pedido
        if pedido['numPed']:
            pedidos.append(pedido)

    return pedidos


def _parse_date(raw: dict) -> datetime | None:
    """Extrai e parseia data do pedido."""
    # Tenta varios campos possiveis (Clic Vendas usa dataCriacao)
    date_fields = ['dataCriacao', 'dataRegistroEnvio', 'datEmi', 'dataEmissao', 'createdAt', 'data']
    date_str = None

    for field in date_fields:
        if raw.get(field):
            date_str = raw[field]
            break

    if not date_str:
        return None

    # Tenta varios formatos
    formats = [
        '%Y-%m-%dT%H:%M:%S.%fZ',  # ISO com ms
        '%Y-%m-%dT%H:%M:%SZ',     # ISO sem ms
        '%Y-%m-%dT%H:%M:%S',      # ISO local
        '%Y-%m-%d',               # Apenas data
        '%d/%m/%Y',               # BR
        '%d/%m/%Y %H:%M:%S',      # BR com hora
    ]

    for fmt in formats:
        try:
            return datetime.strptime(str(date_str)[:26], fmt)
        except (ValueError, TypeError):
            continue

    logger.warning('Data invalida no pedido: %s', date_str)
    return None


def _parse_itens(pedido_raw: dict) -> list[dict]:
    """Extrai itens/produtos do pedido no formato Clic Vendas."""
    itens = []

    raw_itens = pedido_raw.get('itens') or []

    if not isinstance(raw_itens, list):
        raw_itens = [raw_itens] if raw_itens else []

    for item in raw_itens:
        if not item:
            continue

        # Produto pode estar aninhado
        produto = item.get('produto') or {}

        itens.append({
            'codPro': str(
                produto.get('codigo') or
                produto.get('backoffice', {}).get('codigo') or
                item.get('codigoProduto') or
                ''
            ),
            'desPro': str(
                item.get('nome') or
                produto.get('nome') or
                produto.get('descricao') or
                ''
            ),
            'qtdPed': _safe_float(
                item.get('quantidade') or
                produto.get('quantidade')
            ),
            'preUni': _safe_float(
                item.get('valorVenda') or
                item.get('valorOriginal') or
                produto.get('valorVenda')
            ),
            'uniMed': str(
                produto.get('unidadeMedida') or
                item.get('unidadeMedida') or
                'UN'
            ),
            'vlrTotal': _safe_float(
                item.get('totalItem') or
                produto.get('totalItem')
            ),
        })

    return itens


def _safe_int(val) -> int | None:
    """Converte para int de forma segura."""
    if val is None:
        return None
    try:
        return int(val)
    except (ValueError, TypeError):
        return None


def _safe_float(val) -> float | None:
    """Converte para float de forma segura, tratando virgula BR."""
    if val is None:
        return None
    try:
        if isinstance(val, str):
            val = val.replace(',', '.')
        return float(val)
    except (ValueError, TypeError):
        return None


# ============================================
# CLI
# ============================================
if __name__ == '__main__':
    import argparse

    logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

    parser = argparse.ArgumentParser(description='Busca pedidos na API Clic Vendas')
    parser.add_argument('--dias', type=int, default=90, help='Janela de dias (padrao: 90)')
    parser.add_argument('--cod-cli', type=int, default=None, help='Filtrar por codigo do cliente')
    parser.add_argument('--dry-run', action='store_true', help='Somente simula')
    args = parser.parse_args()

    pedidos = fetch_pedidos_clic(
        dias=args.dias,
        dry_run=args.dry_run,
        cod_cli=args.cod_cli,
    )

    if pedidos:
        print(f"\n{'='*60}")
        print(f"Pedidos encontrados: {len(pedidos)}")
        print(f"{'='*60}")

        # Agrupa por cliente
        clientes = {}
        for pedido in pedidos:
            cod = pedido['codCli']
            clientes.setdefault(cod, []).append(pedido)

        print(f"Clientes unicos: {len(clientes)}")

        # Mostra primeiros 5 clientes
        for cod_cli, peds in list(clientes.items())[:5]:
            ultimo = max(peds, key=lambda x: x['datEmi'] or '')
            print(f"  Cliente {cod_cli}: {len(peds)} pedidos, ultimo em {ultimo['datEmi']}")

        # Mostra exemplo de pedido completo
        print(f"\n{'='*60}")
        print("Exemplo de pedido:")
        print(f"{'='*60}")
        import json
        print(json.dumps(pedidos[0], indent=2, ensure_ascii=False))

    elif not args.dry_run:
        print('Nenhum pedido encontrado.')
