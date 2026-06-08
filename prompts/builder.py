"""
Monta o system prompt da Marcela a partir dos arquivos em prompts/marcela/*.md.

Uso:
    from prompts.builder import build_prompt

    prompt = build_prompt()
    prompt = build_prompt(context={"module": "recorrencia", "customer_name": "João", ...})

Chaves de context (todas opcionais):
    module                  "recorrencia" | "ativacao"
    customer_name           str
    top_items               list[dict]  — de top_items_json
    last_3_orders           list[dict]  — de last_3_orders_json
    predicted_next_order_date str
    tipo_abordagem          str         — classificação do módulo de ativação
    ai_mensagem_inicial     str         — mensagem que foi enviada ao cliente
"""
from __future__ import annotations

import logging
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

_MARCELA_DIR = Path(__file__).parent / "marcela"

# Ordem preferencial dos arquivos conhecidos
_KNOWN_ORDER = [
    "system.md",
    "personality.md",
    "business_rules.md",
    "order_flow.md",
    "sales_strategy.md",
    "examples.md",
]


def _ordered_parts() -> list[str]:
    """Retorna todos os .md do diretório marcela, conhecidos na ordem certa primeiro."""
    if not _MARCELA_DIR.exists():
        return []
    all_files = {p.name for p in _MARCELA_DIR.glob("*.md")}
    ordered = [f for f in _KNOWN_ORDER if f in all_files]
    return ordered


def _read(filename: str) -> str:
    path = _MARCELA_DIR / filename
    if not path.exists():
        logger.warning("Arquivo de prompt não encontrado: %s", path)
        return ""
    return path.read_text(encoding="utf-8").strip()


def build_prompt(context: dict | None = None) -> str:
    parts = [_read(f) for f in _ordered_parts()]
    base = "\n\n---\n\n".join(p for p in parts if p)
    base += f"\n\n---\n\n{_runtime_time_section()}"

    if not context:
        return base

    produtos = context.get("produtos") or []
    if produtos:
        base += f"\n\n---\n\n{_catalogo_section(produtos)}"

    section = _module_section(context.get("module", ""), context)
    if section:
        base += f"\n\n---\n\n{section}"

    decision_section = _decision_section(context)
    if decision_section:
        base += f"\n\n---\n\n{decision_section}"

    catalog_resolution_section = _catalog_resolution_section(context)
    if catalog_resolution_section:
        base += f"\n\n---\n\n{catalog_resolution_section}"

    forecast_section = _forecast_section(context)
    if forecast_section:
        base += f"\n\n---\n\n{forecast_section}"

    customer_section = _customer_section(context)
    if customer_section:
        base += f"\n\n---\n\n{customer_section}"

    return base


def _runtime_time_section() -> str:
    now = datetime.now(ZoneInfo("America/Sao_Paulo"))
    weekday_names = [
        "segunda-feira",
        "terca-feira",
        "quarta-feira",
        "quinta-feira",
        "sexta-feira",
        "sabado",
        "domingo",
    ]
    return "\n".join([
        "## DATA E HORA ATUAL",
        "",
        f"Data local: {now.strftime('%d/%m/%Y')}",
        f"Hora local: {now.strftime('%H:%M')}",
        f"Dia da semana: {weekday_names[now.weekday()]}",
        "Fuso horario: America/Sao_Paulo",
        "",
        "Use esta data e hora para interpretar hoje, amanha, proximo dia util e prazo de entrega.",
        "Nao invente outra data/hora.",
    ])


def _decision_section(ctx: dict) -> str:
    classified = ctx.get("classified_intent") or {}
    state = ctx.get("conversation_state") or {}
    if not classified and not state:
        return ""

    linhas = ["## DECISAO OPERACIONAL DO ATENDIMENTO", ""]
    if classified:
        linhas += [
            f"Intencao classificada: {classified.get('intent') or '-'}",
            f"Confianca: {classified.get('confidence') or '-'}",
            f"Requer humano: {bool(classified.get('requires_human'))}",
            f"Fora do escopo: {bool(classified.get('out_of_scope'))}",
        ]
        entities = classified.get("entities") or {}
        if entities:
            linhas += [
                f"Produtos detectados: {', '.join(entities.get('products') or []) or '-'}",
                f"Embalagens detectadas: {', '.join(entities.get('packages') or []) or '-'}",
                f"Quantidades detectadas: {', '.join(entities.get('quantities') or []) or '-'}",
            ]
        linhas.append("")

    if state:
        linhas += [
            "Estado comercial atual:",
            f"- Pedido em andamento: {bool(state.get('order_in_progress'))}",
            f"- Ultima intencao: {state.get('last_intent') or '-'}",
        ]
        if state.get("selected_product_type"):
            linhas.append(f"- Formato/tipo escolhido na conversa: {state.get('selected_product_type')}")
        last_entities = state.get("last_entities") or {}
        if last_entities:
            linhas.append(f"- Ultimos produtos detectados: {', '.join(last_entities.get('products') or []) or '-'}")
        linhas.append("")

    linhas += [
        "Use esta decisao para responder de forma objetiva.",
        "Nao trate a intencao como roteiro fixo; use-a apenas para escolher o rumo da conversa.",
        "Varie a redacao e evite repetir a mesma pergunta em atendimentos diferentes.",
        "Se houver pedido em andamento, mantenha continuidade e use o fluxo de pedido definido no prompt.",
        "Se a intencao for history_query, responda com pedidos reais; nao trate pedido interno em revisao como ultimo pedido finalizado.",
        "Se a mensagem atual adicionar, remover, trocar item ou fizer pergunta, mantenha o pedido aberto.",
        "Se o cliente confirmar claramente o resumo completo, registre para revisao do representante.",
    ]
    return "\n".join(linhas)


def _catalog_resolution_section(ctx: dict) -> str:
    resolution = ctx.get("catalog_resolution") or {}
    if not isinstance(resolution, dict):
        return ""

    payload = json.dumps(resolution, ensure_ascii=False, default=str)
    if len(payload) > 6000:
        payload = payload[:6000] + "...(truncado)"

    return "\n".join(
        [
            "## ANALISE DO SUBAGENTE DE PRODUTOS E PEDIDO",
            "",
            "Esta analise foi feita antes da sua resposta, usando a mensagem do cliente e o catalogo real.",
            "Use esta analise como guia operacional principal para interpretar produtos, formatos, tamanhos e quantidades.",
            "Se houver itens com status encontrado, use esses itens para montar ou atualizar o resumo do pedido.",
            "Se houver itens ambiguos, pergunte somente os campos em faltando; nao reinicie a conversa.",
            "Se houver produtos nao encontrados, diga que nao temos esse produto e ofereca apenas alternativas listadas.",
            "Nao exponha ao cliente que existe subagente, JSON, validacao interna ou catalogo interno.",
            "",
            payload,
        ]
    )


def _customer_section(ctx: dict) -> str:
    linhas: list[str] = []
    profile = ctx.get("customer_profile") or {}
    if profile:
        linhas += [
            "## CONTEXTO DO CLIENTE IDENTIFICADO",
            "",
            f"Nome: {profile.get('nome') or '-'}",
            f"Codigo do cliente: {profile.get('cod_cli') or '-'}",
        ]
        cidade = profile.get("cidade")
        uf = profile.get("uf")
        if cidade or uf:
            linhas.append(f"Localidade: {cidade or '-'} / {uf or '-'}")
        linhas.append("")

    pedido = _fmt_pedido_sugerido(ctx.get("pedido_sugerido") or [])
    if pedido:
        if not linhas:
            linhas += ["## CONTEXTO DO CLIENTE IDENTIFICADO", ""]
        linhas += [
            "Pedido sugerido pelo modulo comercial:",
            pedido,
            "",
            "Use como sugestao ajustavel. Nao diga que ja esta fechado.",
            "",
        ]

    pedido_aberto = _fmt_open_review_order(ctx.get("open_review_order") or {})
    if pedido_aberto:
        if not linhas:
            linhas += ["## CONTEXTO DO CLIENTE IDENTIFICADO", ""]
        linhas += [
            "Pedido interno mais recente em revisao e ainda editavel:",
            pedido_aberto,
            "",
            "Este pedido ainda nao e um pedido real finalizado; nao use como resposta para 'ultimo pedido' ou historico de compras.",
            "Ele tem protocolo interno proprio e ainda nao tem numero do Clic Vendas.",
            "Se o cliente pedir alteracao deste pedido/protocolo, ajuste este pedido e peca confirmacao do resumo completo.",
            "Se o cliente disser que quer novo/outro pedido, crie um novo protocolo em vez de atualizar este.",
            "Antes de adicionar ou alterar item, confirme produto, tipo/formato e tamanho/derivacao.",
            "Se o cliente citar apenas sabor/produto generico e houver mais de um item possivel, pergunte qual item exato deve mudar.",
            "Depois da confirmacao final, use a ferramenta com acao='editar' para atualizar o mesmo pedido em revisao.",
            "",
        ]

    pedidos_abertos = _fmt_open_review_orders(ctx.get("open_review_orders") or [])
    if pedidos_abertos:
        if not linhas:
            linhas += ["## CONTEXTO DO CLIENTE IDENTIFICADO", ""]
        linhas += [
            "Pedidos internos abertos pelo atendimento, ainda nao enviados ao Clic Vendas:",
            pedidos_abertos,
            "",
            "Use estes protocolos para diferenciar pedidos internos pendentes dos pedidos reais do Clic Vendas.",
            "Quando o cliente mencionar protocolo SP-..., altere exatamente esse protocolo.",
            "Quando o cliente pedir novo/outro pedido, mantenha os protocolos existentes e registre um novo com acao='criar'.",
            "",
        ]

    pedidos = _fmt_recent_orders(ctx.get("recent_orders") or [], ctx.get("produtos") or [])
    if pedidos:
        if not linhas:
            linhas += ["## CONTEXTO DO CLIENTE IDENTIFICADO", ""]
        linhas += [
            "Ultimos 4 pedidos reais do cliente:",
            pedidos,
            "",
            "Use estes dados para responder sobre historico, repetir pedido ou sugerir recompra.",
            "Ao mencionar historico ou repetir pedido, preserve produto, formato e tamanho/derivacao quando existirem. Exemplo: copo laranja 115ml, copo uva 200ml, garrafa caju 900ml.",
            "Nao use valores historicos para calcular ou prometer preco de pedido novo.",
        ]

    return "\n".join(linhas).strip()


def _forecast_section(ctx: dict) -> str:
    forecast = ctx.get("sales_forecast") or {}
    if not forecast:
        return ""

    top = _fmt_previsao_produtos(forecast.get("forecast_products") or [])
    seasonal = _fmt_previsao_produtos(forecast.get("seasonal_products") or [])
    if not top and not seasonal:
        return ""

    linhas = [
        "## CONTEXTO DE PREVISAO E SAZONALIDADE",
        "",
        f"Ano analisado: {forecast.get('year') or '-'}",
        f"Mes de referencia sazonal: {forecast.get('seasonal_reference_label') or '-'}",
        "",
    ]
    if seasonal:
        linhas += [
            "Produtos com maior saida sazonal no mes atual:",
            seasonal,
            "",
        ]
    if top:
        linhas += [
            "Produtos com maior saida geral no periodo analisado:",
            top,
            "",
        ]
    linhas += [
        "Use este contexto apenas para sugestoes comerciais quando o cliente pedir recomendacao, estiver indeciso ou abrir espaco para sugestao.",
        "Antes de oferecer como item do pedido, confirme que o produto existe no catalogo/tabela injetada para esse cliente e siga o fluxo de tipo/formato, tamanho e quantidade.",
        "Nao diga ao cliente que existe um modulo de previsao, ranking interno, analise ou sazonalidade. Fale de forma natural, como sugestao de produto com boa saida.",
        "Nao use esses dados para prometer estoque, preco, desconto ou condicao comercial.",
    ]
    return "\n".join(linhas).strip()


def _module_section(module: str, ctx: dict) -> str:
    if module == "recorrencia":
        return _recorrencia_section(ctx)
    if module == "ativacao":
        return _ativacao_section(ctx)
    return ""


def _recorrencia_section(ctx: dict) -> str:
    nome = ctx.get("customer_name") or "o cliente"
    data_prev = ctx.get("predicted_next_order_date", "")
    top_items = ctx.get("top_items") or []
    mensagem = ctx.get("ai_mensagem_inicial", "")

    linhas = [
        "## CONTEXTO INJETADO: MÓDULO RECORRÊNCIA",
        "",
        f"Esta conversa foi iniciada pelo sistema porque {nome} está na janela "
        "esperada de recompra. Facilite a confirmação ou ajuste do pedido.",
        "",
    ]
    if data_prev:
        linhas.append(f"Data prevista do próximo pedido: {data_prev}")
        linhas.append("")
    produtos = _fmt_produtos(top_items)
    if produtos:
        linhas += ["Produtos do histórico do cliente:", produtos, ""]
    if mensagem:
        linhas += [f'Mensagem que foi enviada ao cliente: "{mensagem}"', ""]
    linhas.append("Não mencione padrão de compra, análise de dados ou termos técnicos.")

    return "\n".join(linhas)


def _ativacao_section(ctx: dict) -> str:
    nome = ctx.get("customer_name") or "o cliente"
    tipo = ctx.get("tipo_abordagem", "")
    mensagem = ctx.get("ai_mensagem_inicial", "")
    top_items = ctx.get("top_items") or []

    _desc = {
        "cliente_irregular": "cliente com pedidos mas sem padrão definido",
        "cliente_adormecido": "cliente que não compra há muito tempo",
        "cliente_novo_potencial": "cliente com poucos pedidos recentes",
    }
    desc = _desc.get(tipo, "cliente em reativação")

    linhas = [
        "## CONTEXTO INJETADO: MÓDULO ATIVAÇÃO COMERCIAL",
        "",
        f"Esta conversa foi iniciada pelo módulo de ativação para {nome} ({desc}).",
        "Este cliente NÃO tem padrão previsível. Use abordagem consultiva — não assuma compra.",
        "",
    ]
    produtos = _fmt_produtos(top_items)
    if produtos:
        linhas += [
            "Produtos que o cliente costumava pedir (use APENAS se ele perguntar sobre histórico):",
            produtos,
            "",
        ]
    if mensagem:
        linhas += [f'Mensagem que foi enviada ao cliente: "{mensagem}"', ""]
    linhas.append("Objetivo: reativar o relacionamento. Facilite a conversa, não force um pedido.")

    return "\n".join(linhas)


def _fmt_preco(valor) -> str:
    try:
        return f"R$ {float(valor):.2f}".replace(".", ",")
    except (TypeError, ValueError):
        return "-"


def _fmt_number(valor) -> str:
    try:
        number = float(valor)
    except (TypeError, ValueError):
        return str(valor or "-")
    if number.is_integer():
        return f"{int(number):,}".replace(",", ".")
    return f"{number:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")


def _display_variation(value) -> str:
    raw = str(value or "").strip()
    upper = raw.upper()
    if upper == "05L":
        return "5L"
    if upper == "1L7":
        return "1,7L"
    if upper.isdigit():
        return f"{int(upper)}ml"
    return raw


def _product_format_from_name(name: str) -> str:
    upper = _norm_text(name)
    if "BOLSA" in upper and "CONCENTRADO" in upper:
        return "bolsa concentrada"
    if "BOLSA" in upper:
        return "bolsa"
    if "COPO" in upper:
        return "copo"
    if "GARRAFA" in upper:
        return "garrafa"
    if "GALAO" in upper:
        return "galao"
    return "outros"


def _format_size_summary(produtos: list[dict]) -> str:
    grouped: dict[str, set[str]] = {}
    for p in produtos:
        name = p.get("nome_produto") or p.get("nome") or ""
        variation = p.get("variacao") or p.get("derivacao") or ""
        if not name or not variation:
            continue
        fmt = _product_format_from_name(name)
        if fmt == "outros":
            continue
        grouped.setdefault(fmt, set()).add(_display_variation(variation))

    if not grouped:
        return ""

    order = ["copo", "garrafa", "bolsa", "bolsa concentrada", "galao"]
    lines = ["Resumo de formatos e tamanhos disponiveis nesta tabela:"]
    for fmt in order:
        sizes = sorted(grouped.get(fmt, []))
        if sizes:
            lines.append(f"- {fmt}: {', '.join(sizes)}")
    return "\n".join(lines)


def _catalogo_section(produtos: list[dict]) -> str:
    if not produtos:
        return ""

    # Detecta formato: tabelas_preco_itens tem 'nome_produto'; produtos tem 'nome'
    is_tabela = "nome_produto" in (produtos[0] if produtos else {})

    if is_tabela:
        linhas = [
            "## OPCOES COMERCIAIS DISPONIVEIS",
            "",
            "Use estes produtos, tamanhos e preços para responder. Nunca invente valores fora desta lista.",
            "Estes dados sao internos: nao diga numero/nome de tabela, codigo interno, quantidade minima ou desconto.",
            "Ao responder ao cliente, use linguagem comercial curta: produto + formato/tamanho + preco quando necessario.",
            "Se o cliente pedir produto ou sabor ausente da lista, nao adicione ao pedido e nao calcule preco.",
            "",
        ]
        summary = _format_size_summary(produtos)
        if summary:
            linhas += ["", summary, ""]
        for p in produtos:
            nome = p.get("nome_produto", "")
            variacao = _display_variation(p.get("variacao") or "-")
            qtd_min = p.get("quantidade_minima") or "-"
            preco = _fmt_preco(p.get("preco"))
            linhas.append(f"- {nome} | tamanho {variacao} | preco {preco}")
    else:
        linhas = [
            "## OPCOES COMERCIAIS DISPONIVEIS",
            "",
            "Use estas informações quando o cliente perguntar sobre produtos, preços ou disponibilidade.",
            "Nao diga numero/nome de tabela, codigo interno, quantidade minima ou desconto.",
            "Nao deduza sabores por codigo ou abreviacao. Se o produto ou sabor nao aparecer na lista, nao adicione ao pedido e nao calcule preco.",
            "",
        ]
        for p in produtos:
            nome = p.get("nome", "")
            deriv = _display_variation(p.get("derivacao") or "-")
            base_str = _fmt_preco(p.get("preco_base"))
            linhas.append(f"- {nome} | tamanho {deriv} | preco {base_str}")

    linhas.append("")
    linhas.append("Ao citar precos, use apenas os valores acima. Nunca invente precos e nunca exponha dados internos.")
    return "\n".join(linhas)


def _fmt_produtos(items: list[dict]) -> str:
    linhas = []
    for it in items[:5]:
        nome = it.get("desPro") or it.get("codPro", "")
        if nome:
            linhas.append(f"- {nome}")
    return "\n".join(linhas)


def _fmt_previsao_produtos(items: list[dict]) -> str:
    linhas = []
    for it in items[:6]:
        nome = it.get("desPro") or it.get("nome") or it.get("codPro", "")
        if not nome:
            continue
        qtd = it.get("total_qtd")
        pedidos = it.get("pedidos")
        detalhe = str(nome)
        extras = []
        if qtd not in (None, ""):
            extras.append(f"{_fmt_number(qtd)} unidades")
        if pedidos not in (None, ""):
            extras.append(f"{pedidos} pedidos")
        if extras:
            detalhe += f" ({', '.join(extras)})"
        linhas.append(f"- {detalhe}")
    return "\n".join(linhas)


def _fmt_pedido_sugerido(items: list[dict]) -> str:
    linhas = []
    for it in items[:10]:
        cod = it.get("codPro") or it.get("cod_produto") or ""
        nome = it.get("desPro") or it.get("nome") or cod
        qtd = it.get("qtdPed") or it.get("quantidade") or ""
        partes = [str(nome)]
        if cod:
            partes.append(f"codigo {cod}")
        if qtd:
            partes.append(f"quantidade sugerida {qtd}")
        linhas.append(f"- {'; '.join(partes)}")
    return "\n".join(linhas)


def _fmt_open_review_order(order: dict) -> str:
    if not order:
        return ""
    linhas = [
        f"- Protocolo interno: {order.get('protocolo') or '-'}",
        f"- ID: {order.get('id') or '-'}",
        f"- Origem: {order.get('origem') or 'ia_whatsapp'}",
        f"- Status: {order.get('status') or '-'}",
    ]
    items = order.get("itens_json") or []
    if isinstance(items, list) and items:
        linhas.append("- Itens atuais:")
        for item in items[:20]:
            nome = item.get("nome") or item.get("produto") or item.get("desPro") or "Item"
            tipo = item.get("tipo") or item.get("formato") or item.get("embalagem")
            tamanho = item.get("tamanho") or item.get("derivacao") or item.get("variacao") or item.get("volume")
            qtd = item.get("quantidade") or item.get("qtdPed") or ""
            detalhe = f"  - {nome}"
            if tipo:
                detalhe += f", tipo {tipo}"
            if tamanho:
                detalhe += f", tamanho {tamanho}"
            if qtd:
                detalhe += f": {qtd}"
            preco = item.get("preco_unitario") or item.get("preco") or item.get("preUni")
            subtotal = item.get("subtotal") or item.get("vlrTotal")
            if preco:
                detalhe += f", unitario {_fmt_preco(preco)}"
            if subtotal:
                detalhe += f", subtotal {_fmt_preco(subtotal)}"
            linhas.append(detalhe)
    obs = order.get("observacoes")
    if obs:
        linhas.append(f"- Observacoes: {obs}")
    return "\n".join(linhas)


def _fmt_open_review_orders(orders: list[dict]) -> str:
    linhas = []
    for order in orders[:5]:
        protocolo = order.get("protocolo") or order.get("id") or "-"
        status = order.get("status") or "-"
        created = order.get("created_at") or "-"
        items = order.get("itens_json") or []
        resumo = []
        if isinstance(items, list):
            for item in items[:4]:
                nome = item.get("nome") or item.get("produto") or item.get("desPro") or "Item"
                qtd = item.get("quantidade") or item.get("qtdPed") or ""
                unidade = item.get("unidade") or item.get("uniMed") or ""
                resumo.append(f"{nome} ({' '.join(str(part) for part in (qtd, unidade) if part)})")
        linhas.append(f"- {protocolo} | status {status} | criado {created} | itens: {', '.join(resumo) or '-'}")
    return "\n".join(linhas)


def _norm_text(value) -> str:
    import unicodedata

    normalized = unicodedata.normalize("NFKD", str(value or ""))
    return "".join(ch for ch in normalized if not unicodedata.combining(ch)).strip().upper()


def _norm_price(value) -> float | None:
    try:
        return round(float(value), 2)
    except (TypeError, ValueError):
        return None


def _catalog_match(item: dict, produtos: list[dict]) -> dict | None:
    cod = _norm_text(item.get("codPro") or item.get("cod_produto"))
    if not cod:
        return None

    candidates = [
        row for row in produtos
        if _norm_text(row.get("cod_produto")) == cod
    ]
    if not candidates:
        return None
    if len(candidates) == 1:
        return candidates[0]

    item_price = _norm_price(item.get("preUni") or item.get("preco_unitario") or item.get("preco"))
    if item_price is not None:
        for row in candidates:
            for key in ("preco", "preco_base", "preco_inst_299"):
                row_price = _norm_price(row.get(key))
                if row_price is not None and abs(row_price - item_price) <= 0.01:
                    return row

    item_variation = _norm_text(item.get("variacao") or item.get("derivacao") or item.get("tamanho"))
    if item_variation:
        for row in candidates:
            row_variation = _norm_text(row.get("variacao") or row.get("derivacao"))
            if row_variation == item_variation:
                return row

    return None


def _fmt_recent_orders(orders: list[dict], produtos: list[dict] | None = None) -> str:
    linhas = []
    produtos = produtos or []
    for order in orders[:4]:
        numero = order.get("num_ped") or "-"
        data = order.get("dat_emi") or "-"
        status = order.get("sit_ped") or "-"
        linhas.append(f"- Pedido {numero} | data {data} | status {status}")

        items = order.get("items_json") or []
        if not isinstance(items, list):
            continue
        for item in items[:12]:
            catalog_item = _catalog_match(item, produtos)
            cod = item.get("codPro") or item.get("cod_produto") or ""
            nome = (
                (catalog_item or {}).get("nome_produto")
                or (catalog_item or {}).get("nome")
                or item.get("desPro")
                or item.get("nome")
                or cod
                or "Produto"
            )
            variacao = (
                (catalog_item or {}).get("variacao")
                or (catalog_item or {}).get("derivacao")
                or item.get("variacao")
                or item.get("derivacao")
                or item.get("tamanho")
                or ""
            )
            qtd = item.get("qtdPed") or item.get("quantidade") or "-"
            unidade = item.get("uniMed") or item.get("unidade") or ""
            detalhe = f"  - {nome}"
            if variacao:
                detalhe += f" | derivacao/tamanho {variacao}"
            if cod:
                detalhe += f" [{cod}]"
            detalhe += f": qtd {qtd}"
            if unidade:
                detalhe += f" {unidade}"
            linhas.append(detalhe)
    return "\n".join(linhas)
