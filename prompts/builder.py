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
from pathlib import Path

logger = logging.getLogger(__name__)

_MARCELA_DIR = Path(__file__).parent / "marcela"

# Ordem preferencial dos arquivos conhecidos
_KNOWN_ORDER = [
    "system.md",
    "personality.md",
    "business_rules.md",
    "sales_strategy.md",
    "examples.md",
    "tools.md",
]


def _ordered_parts() -> list[str]:
    """Retorna todos os .md do diretório marcela, conhecidos na ordem certa primeiro."""
    if not _MARCELA_DIR.exists():
        return []
    all_files = {p.name for p in _MARCELA_DIR.glob("*.md")}
    ordered = [f for f in _KNOWN_ORDER if f in all_files]
    extras = sorted(all_files - set(_KNOWN_ORDER))
    return ordered + extras


def _read(filename: str) -> str:
    path = _MARCELA_DIR / filename
    if not path.exists():
        logger.warning("Arquivo de prompt não encontrado: %s", path)
        return ""
    return path.read_text(encoding="utf-8").strip()


def build_prompt(context: dict | None = None) -> str:
    parts = [_read(f) for f in _ordered_parts()]
    base = "\n\n---\n\n".join(p for p in parts if p)

    if not context:
        return base

    produtos = context.get("produtos") or []
    if produtos:
        base += f"\n\n---\n\n{_catalogo_section(produtos)}"

    section = _module_section(context.get("module", ""), context)
    if section:
        base += f"\n\n---\n\n{section}"

    return base


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


def _catalogo_section(produtos: list[dict]) -> str:
    if not produtos:
        return ""

    # Detecta formato: tabelas_preco_itens tem 'nome_produto'; produtos tem 'nome'
    is_tabela = "nome_produto" in (produtos[0] if produtos else {})

    if is_tabela:
        linhas = [
            "## TABELA DE PREÇOS DO CLIENTE",
            "",
            "Estes são os produtos e preços desta tabela de preços específica do cliente.",
            "Use estes valores ao falar sobre preços — nunca invente valores fora desta lista.",
            "",
            "| Código | Produto | Variação | Qtd. Mín. | Preço | Desconto |",
            "|--------|---------|----------|-----------|-------|----------|",
        ]
        for p in produtos:
            cod = p.get("cod_produto", "")
            nome = p.get("nome_produto", "")
            variacao = p.get("variacao") or "-"
            qtd_min = p.get("quantidade_minima") or "-"
            preco = _fmt_preco(p.get("preco"))
            desc = p.get("desconto")
            desc_str = f"{float(desc):.1f}%".replace(".", ",") if desc else "-"
            linhas.append(f"| {cod} | {nome} | {variacao} | {qtd_min} | {preco} | {desc_str} |")
    else:
        linhas = [
            "## CATÁLOGO DE PRODUTOS DISPONÍVEIS",
            "",
            "Use estas informações quando o cliente perguntar sobre produtos, preços ou disponibilidade.",
            "Preço base = tabela padrão. Preço Inst.299 = tabela instalação 299.",
            "",
            "| Código | Produto | Deriv. | Preço Base | Preço Inst.299 |",
            "|--------|---------|--------|------------|----------------|",
        ]
        for p in produtos:
            cod = p.get("cod_produto", "")
            nome = p.get("nome", "")
            deriv = p.get("derivacao") or "-"
            base_str = _fmt_preco(p.get("preco_base"))
            inst_str = _fmt_preco(p.get("preco_inst_299"))
            linhas.append(f"| {cod} | {nome} | {deriv} | {base_str} | {inst_str} |")

    linhas.append("")
    linhas.append("Ao citar preços, use sempre os valores da tabela acima. Nunca invente preços.")
    return "\n".join(linhas)


def _fmt_produtos(items: list[dict]) -> str:
    linhas = []
    for it in items[:5]:
        nome = it.get("desPro") or it.get("codPro", "")
        if nome:
            linhas.append(f"- {nome}")
    return "\n".join(linhas)
