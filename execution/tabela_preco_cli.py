"""
tabela_preco_cli.py
===================
Busca tabelas de preço do Senior ERP via SOAP e persiste no Supabase.
Faz uma requisição SOAP separada por tabela.

Uso:
    python tabela_preco_cli.py --cod-tpr 201 202   # Sincroniza tabelas 201 e 202
    python tabela_preco_cli.py --cod-tpr 201       # Sincroniza só a 201
    python tabela_preco_cli.py --dry-run --cod-tpr 201 202  # Testa sem salvar
"""

import argparse
import json
import logging
import os
import re
import sys
import time
import xml.etree.ElementTree as ET
from datetime import datetime
from decimal import Decimal, InvalidOperation

import requests
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)],
)
logger = logging.getLogger(__name__)

# Credenciais do Senior ERP (todas do .env)
SENIOR_BASE_URL = os.getenv("SENIOR_BASE_URL", "").rstrip("/")
SENIOR_USER = os.getenv("SENIOR_USER", "")
SENIOR_PASSWORD = os.getenv("SENIOR_PASSWORD", "")
SENIOR_ENCRYPTION = os.getenv("SENIOR_ENCRYPTION", "0")
SENIOR_COD_EMP = os.getenv("SENIOR_COD_EMP", "1")
SENIOR_COD_FIL = os.getenv("SENIOR_COD_FIL", "1")
SENIOR_SYSTEM_ID = os.getenv("SENIOR_SYSTEM_ID", "TESTE")

ENDPOINT = f"{SENIOR_BASE_URL}/g5-senior-services/sapiens_Synccom_senior_g5_co_cad_tabelapreco"
SOAP_HEADERS = {
    "Content-Type": "text/xml; charset=utf-8",
    "SOAPAction": '""',
}
PAGE_SIZE = 300
REQUEST_TIMEOUT = 60  # segundos
BATCH_SIZE = 500


# ── Helpers XML ─────────────────────────────────────────────────────────────

def _strip_ns(tag: str) -> str:
    return re.sub(r"\{[^}]*\}", "", tag)


def _child_text(elem, tag: str) -> str:
    """Texto do filho direto com match de tag (sem namespace)."""
    for child in elem:
        if _strip_ns(child.tag).lower() == tag.lower():
            return (child.text or "").strip()
    return ""


def _safe_float(val: str) -> float | None:
    if not val:
        return None
    try:
        return float(val.replace(",", "."))
    except ValueError:
        return None


def _text(value) -> str:
    return str(value or "").strip()


def _norm(value) -> str:
    return _text(value).upper()


def _item_key(item: dict) -> tuple[str, str]:
    return (_norm(item.get("cod_produto")), _norm(item.get("variacao")))


def _same_number(left, right, places: int = 4) -> bool:
    try:
        left_dec = Decimal(str(left or 0)).quantize(Decimal(10) ** -places)
        right_dec = Decimal(str(right or 0)).quantize(Decimal(10) ** -places)
    except (InvalidOperation, ValueError):
        return False
    return left_dec == right_dec


# ── SOAP request ─────────────────────────────────────────────────────────────

def _build_body(cod_tpr: str | None, page: int) -> str:
    cod_tpr_block = ""
    if cod_tpr:
        cod_tpr_block = f"""
            <codTpr>
               <codTpr>{cod_tpr}</codTpr>
            </codTpr>"""

    return f"""<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
                  xmlns:ser="http://services.senior.com.br">
   <soapenv:Header/>
   <soapenv:Body>
      <ser:ConsultarGeral>
         <user>{SENIOR_USER}</user>
         <password>{SENIOR_PASSWORD}</password>
         <encryption>{SENIOR_ENCRYPTION}</encryption>
         <parameters>
            <codEmp>{SENIOR_COD_EMP}</codEmp>
            <codFil>{SENIOR_COD_FIL}</codFil>
            <identificadorSistema>{SENIOR_SYSTEM_ID}</identificadorSistema>
            <sitReg>A</sitReg>
            <sitRegVal>A</sitRegVal>
            <sitRegItp>A</sitRegItp>
            <indicePagina>{page}</indicePagina>
            <limitePagina>{PAGE_SIZE}</limitePagina>{cod_tpr_block}
         </parameters>
      </ser:ConsultarGeral>
   </soapenv:Body>
</soapenv:Envelope>"""


def _post_soap(body: str) -> str:
    resp = requests.post(
        ENDPOINT,
        data=body.encode("utf-8"),
        headers=SOAP_HEADERS,
        timeout=REQUEST_TIMEOUT,
    )
    resp.raise_for_status()
    logger.debug("RAW RESPONSE:\n%s", resp.text)
    return resp.text


# ── Response parser ───────────────────────────────────────────────────────────

def _parse_page(xml_text: str, synced_at: str) -> tuple[list[dict], list[dict], bool]:
    """
    Parseia uma página da resposta SOAP.
    Retorna (tabelas, itens, tem_mais_paginas).

    Estrutura confirmada do Senior ERP (tabelapreco ConsultarGeral):
      result
        erroExecucao [xsi:nil="true"]  ← nil = sem erro; texto = mensagem de erro
        mensagemRetorno = "Processado com sucesso."
        tabelaPreco                    ← cabeçalho da tabela
          codTpr                       ← código
          desTpr                       ← nome
          validade                     ← bloco de validade
            produto                    ← itens (um por produto/derivação)
              codPro                   ← código do produto
              codDer                   ← variação/derivação
              preBas                   ← preço base
              perDsc                   ← % desconto
              uniMed                   ← unidade de medida
    """
    try:
        root = ET.fromstring(xml_text.encode("utf-8"))
    except ET.ParseError as exc:
        raise ValueError(f"XML inválido: {exc}") from exc

    # Detecção de erro: erroExecucao com texto (não nil) = erro
    for el in root.iter():
        if _strip_ns(el.tag) == "erroExecucao":
            nil = any("nil" in k for k in el.attrib)
            texto = (el.text or "").strip()
            if not nil and texto:
                raise RuntimeError(f"Senior ERP: {texto}")
            break

    tabelas: list[dict] = []
    itens: list[dict] = []

    # Cada <tabelaPreco> é um cabeçalho de tabela
    for tab in root.iter():
        if _strip_ns(tab.tag) != "tabelaPreco":
            continue

        cod_tpr = _child_text(tab, "codTpr")
        if not cod_tpr:
            continue

        tabelas.append({
            "codigo_tabela": cod_tpr,
            "nome_tabela": _child_text(tab, "desTpr") or None,
            "synced_at": synced_at,
        })

        # Itens estão em tabelaPreco > validade > produto
        for validade in tab:
            if _strip_ns(validade.tag) != "validade":
                continue
            for produto in validade:
                if _strip_ns(produto.tag) != "produto":
                    continue

                cod_pro = _child_text(produto, "codPro")
                if not cod_pro:
                    continue

                # Ignora itens inativos
                if _child_text(produto, "sitReg") == "I":
                    continue

                preco = _safe_float(_child_text(produto, "preBas"))
                if preco is None:
                    continue

                itens.append({
                    "codigo_tabela": cod_tpr,
                    "cod_produto": cod_pro,
                    "nome_produto": None,  # Senior não retorna nome no serviço de tabela
                    "variacao": _child_text(produto, "codDer") or None,
                    "quantidade_minima": 1,
                    "preco": preco,
                    "desconto": _safe_float(_child_text(produto, "perDsc")) or 0,
                    "synced_at": synced_at,
                })

    # Paginação: há mais se temos PAGE_SIZE ou mais tabelaPreco na resposta
    tem_mais = len(tabelas) >= PAGE_SIZE
    return tabelas, itens, tem_mais


# ── Supabase upsert ──────────────────────────────────────────────────────────

def _db():
    url = os.getenv("SUPABASE_URL", "").rstrip("/")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_ANON_KEY", "")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY não configurados")
    from supabase import create_client
    return create_client(url, key)


def _enrich_nomes(db, itens: list[dict]) -> list[dict]:
    """Preenche nome_produto dos itens a partir da tabela produtos do Supabase.
    Usa (cod_produto, derivacao) como chave composta para diferenciar tamanhos."""
    try:
        res = db.table("produtos").select("cod_produto, derivacao, nome").eq("ativo", True).execute()
        # chave exata: (cod_produto, derivacao)
        nome_map_comp: dict[tuple, str] = {}
        # fallback: só cod_produto (quando não há derivação cadastrada)
        nome_map_base: dict[str, str] = {}
        for p in (res.data or []):
            nome = p.get("nome") or ""
            if not nome:
                continue
            der = (p.get("derivacao") or "").strip()
            cod = (p.get("cod_produto") or "").strip()
            if cod and der:
                nome_map_comp[(cod, der)] = nome
            if cod:
                nome_map_base.setdefault(cod, nome)

        for item in itens:
            if not item.get("nome_produto"):
                cod = item["cod_produto"]
                var = (item.get("variacao") or "").strip()
                item["nome_produto"] = (
                    nome_map_comp.get((cod, var))
                    or nome_map_base.get(cod)
                )
    except Exception as exc:
        logger.warning("Falha ao enriquecer nomes de produtos: %s", exc)
    return itens


def _upsert_supabase(tabelas: list[dict], itens: list[dict]) -> dict:
    if not tabelas:
        return {"tabelas_upserted": 0, "itens_upserted": 0}

    db = _db()

    # Upsert metadados das tabelas
    db.table("tabelas_preco").upsert(tabelas, on_conflict="codigo_tabela").execute()
    logger.info("Tabelas upsertadas: %d", len(tabelas))

    # Apaga itens existentes das tabelas sincronizadas e re-insere (evita duplicatas)
    codigos = list({t["codigo_tabela"] for t in tabelas})
    db.table("tabelas_preco_itens").delete().in_("codigo_tabela", codigos).execute()

    if itens:
        itens = _enrich_nomes(db, itens)
        sem_nome = sum(1 for i in itens if not i.get("nome_produto"))
        if sem_nome:
            logger.warning("%d produto(s) sem nome — catálogo Senior ERP não sincronizado", sem_nome)
        for i in range(0, len(itens), BATCH_SIZE):
            db.table("tabelas_preco_itens").insert(itens[i : i + BATCH_SIZE]).execute()
        logger.info("Itens inseridos: %d", len(itens))

    return {"tabelas_upserted": len(tabelas), "itens_upserted": len(itens)}


def _get_registered_codigos(db) -> list[str]:
    """Retorna todos os codigos de tabela conhecidos pelo sistema."""
    codigos: set[str] = set()

    rows = (
        db.table("tabelas_preco")
        .select("codigo_tabela")
        .order("codigo_tabela")
        .execute()
        .data
        or []
    )
    for row in rows:
        codigo = _text(row.get("codigo_tabela"))
        if codigo:
            codigos.add(codigo)

    # Clientes podem carregar codigos ainda nao cadastrados em tabelas_preco.
    try:
        customer_rows = (
            db.table("clic_clientes")
            .select("tabela_preco_codigo")
            .not_.is_("tabela_preco_codigo", "null")
            .execute()
            .data
            or []
        )
        for row in customer_rows:
            codigo = _text(row.get("tabela_preco_codigo"))
            if codigo:
                codigos.add(codigo)
    except Exception as exc:
        logger.warning("Nao foi possivel ler codigos em clic_clientes: %s", exc)

    return sorted(codigos)


def _current_items_map(db, codigo_tabela: str) -> dict[tuple[str, str], dict]:
    rows = (
        db.table("tabelas_preco_itens")
        .select("id,codigo_tabela,cod_produto,nome_produto,variacao,quantidade_minima,preco,desconto,synced_at")
        .eq("codigo_tabela", codigo_tabela)
        .execute()
        .data
        or []
    )
    return {_item_key(row): row for row in rows}


def _plan_table_changes(db, codigo_tabela: str, senior_itens: list[dict], prune: bool = True) -> dict:
    current = _current_items_map(db, codigo_tabela)
    wanted = {_item_key(item): item for item in senior_itens}

    inserts: list[dict] = []
    updates: list[dict] = []

    for key, item in wanted.items():
        existing = current.get(key)
        if not existing:
            inserts.append(item)
            continue

        changed_fields = {}
        for field in ("nome_produto", "quantidade_minima", "preco", "desconto"):
            current_value = existing.get(field)
            wanted_value = item.get(field)
            if field in {"preco", "desconto"}:
                if _same_number(current_value, wanted_value):
                    continue
            elif _norm(current_value) == _norm(wanted_value):
                continue
            changed_fields[field] = wanted_value

        if changed_fields:
            updates.append(
                {
                    "id": existing.get("id"),
                    "cod_produto": key[0],
                    "variacao": key[1],
                    "antes": {
                        "nome_produto": existing.get("nome_produto"),
                        "preco": existing.get("preco"),
                        "desconto": existing.get("desconto"),
                    },
                    "depois": {
                        "nome_produto": item.get("nome_produto"),
                        "preco": item.get("preco"),
                        "desconto": item.get("desconto"),
                    },
                    "changes": {**changed_fields, "synced_at": item.get("synced_at")},
                }
            )

    deletes: list[dict] = []
    if prune:
        for key, item in current.items():
            if key not in wanted:
                deletes.append(item)

    return {
        "codigo_tabela": codigo_tabela,
        "senior_items": len(wanted),
        "current_items": len(current),
        "inserts": inserts,
        "updates": updates,
        "deletes": deletes,
    }


def _apply_audit_changes(db, tabela: dict | None, changes: dict, prune: bool) -> dict:
    codigo_tabela = changes["codigo_tabela"]
    synced_at = datetime.utcnow().isoformat() + "Z"
    db.table("tabelas_preco").upsert(
        {
            "codigo_tabela": codigo_tabela,
            "nome_tabela": (tabela or {}).get("nome_tabela") or f"Tabela {codigo_tabela}",
            "synced_at": synced_at,
        },
        on_conflict="codigo_tabela",
    ).execute()

    inserted = 0
    inserts = changes["inserts"]
    if inserts:
        for start in range(0, len(inserts), BATCH_SIZE):
            batch = inserts[start : start + BATCH_SIZE]
            db.table("tabelas_preco_itens").insert(batch).execute()
            inserted += len(batch)

    updated = 0
    for row in changes["updates"]:
        db.table("tabelas_preco_itens").update(row["changes"]).eq("id", row["id"]).execute()
        updated += 1

    deleted = 0
    if prune:
        for row in changes["deletes"]:
            db.table("tabelas_preco_itens").delete().eq("id", row["id"]).execute()
            deleted += 1

    return {"inserted": inserted, "updated": updated, "deleted": deleted}


# ── Sync principal ────────────────────────────────────────────────────────────

def _sync_one_tabela(cod_tpr: str, synced_at: str) -> tuple[list[dict], list[dict]]:
    """Faz requisições paginadas para uma tabela específica e retorna (tabelas, itens)."""
    all_tabelas: list[dict] = []
    all_itens: list[dict] = []
    page = 1

    while True:
        logger.info("Tabela %s — página %d...", cod_tpr, page)
        body = _build_body(cod_tpr, page)

        try:
            xml_text = _post_soap(body)
        except requests.RequestException as exc:
            raise RuntimeError(f"Erro HTTP ao chamar Senior ERP (tabela {cod_tpr}): {exc}") from exc

        tabelas, itens, tem_mais = _parse_page(xml_text, synced_at)
        all_tabelas.extend(tabelas)
        all_itens.extend(itens)

        logger.info(
            "Tabela %s — página %d: %d registros de tabela, %d itens",
            cod_tpr, page, len(tabelas), len(itens),
        )

        if not tem_mais or not tabelas:
            break
        page += 1

    return all_tabelas, all_itens


def sync_tabelas(codigos: list[str], dry_run: bool = False) -> dict:
    """
    Sincroniza as tabelas de preço informadas.
    Faz UMA requisição SOAP separada por código de tabela.
    """
    if not SENIOR_BASE_URL or not SENIOR_USER:
        raise RuntimeError("Credenciais do Senior ERP não configuradas (SENIOR_BASE_URL, SENIOR_USER, SENIOR_PASSWORD)")

    if not codigos:
        raise ValueError("Informe pelo menos um código de tabela (--cod-tpr 201 202)")

    t0 = time.perf_counter()
    synced_at = datetime.utcnow().isoformat() + "Z"

    all_tabelas: list[dict] = []
    all_itens: list[dict] = []
    erros: list[dict] = []

    for cod in codigos:
        try:
            tabelas, itens = _sync_one_tabela(cod, synced_at)
            all_tabelas.extend(tabelas)
            all_itens.extend(itens)
        except Exception as exc:
            logger.error("Erro na tabela %s: %s", cod, exc)
            erros.append({"cod_tpr": cod, "erro": str(exc)})

    duration_ms = int((time.perf_counter() - t0) * 1000)

    if dry_run:
        return {
            "dry_run": True,
            "codigos_solicitados": codigos,
            "tabelas_encontradas": len(all_tabelas),
            "itens_encontrados": len(all_itens),
            "erros": erros,
            "duration_ms": duration_ms,
            "tabelas": [
                {"codigo": t["codigo_tabela"], "nome": t["nome_tabela"]}
                for t in all_tabelas
            ],
        }

    resultado = _upsert_supabase(all_tabelas, all_itens)
    resultado["duration_ms"] = duration_ms
    resultado["codigos_solicitados"] = codigos
    resultado["erros"] = erros

    logger.info(
        "Sync concluída: %d tabelas, %d itens em %dms",
        resultado["tabelas_upserted"],
        resultado["itens_upserted"],
        duration_ms,
    )

    return resultado


def audit_tabelas(
    codigos: list[str] | None = None,
    all_registered: bool = False,
    apply: bool = False,
    prune: bool = True,
) -> dict:
    """
    Compara as tabelas registradas no sistema com o Senior ERP ao vivo.
    Por padrao nao altera o banco; use apply=True para aplicar diferencas.
    """
    if not SENIOR_BASE_URL or not SENIOR_USER:
        raise RuntimeError("Credenciais do Senior ERP nao configuradas (SENIOR_BASE_URL, SENIOR_USER, SENIOR_PASSWORD)")

    db = _db()
    if all_registered:
        codigos = _get_registered_codigos(db)

    codigos = [_text(cod) for cod in (codigos or []) if _text(cod)]
    if not codigos:
        raise ValueError("Nenhum codigo de tabela informado ou registrado no sistema")

    t0 = time.perf_counter()
    synced_at = datetime.utcnow().isoformat() + "Z"
    summaries: list[dict] = []
    erros: list[dict] = []
    total_insert = 0
    total_update = 0
    total_delete = 0
    total_senior_items = 0
    total_current_items = 0

    for codigo in codigos:
        try:
            tabelas, itens = _sync_one_tabela(codigo, synced_at)
            itens = _enrich_nomes(db, itens)
            tabela = tabelas[0] if tabelas else None
            changes = _plan_table_changes(db, codigo, itens, prune=prune)
            applied = None
            if apply:
                applied = _apply_audit_changes(db, tabela, changes, prune=prune)

            to_insert = len(changes["inserts"])
            to_update = len(changes["updates"])
            to_delete = len(changes["deletes"])
            total_insert += to_insert
            total_update += to_update
            total_delete += to_delete
            total_senior_items += changes["senior_items"]
            total_current_items += changes["current_items"]

            summaries.append(
                {
                    "codigo_tabela": codigo,
                    "nome_tabela": (tabela or {}).get("nome_tabela"),
                    "senior_items": changes["senior_items"],
                    "current_items": changes["current_items"],
                    "to_insert": to_insert,
                    "to_update": to_update,
                    "to_delete": to_delete,
                    "sample_inserts": changes["inserts"][:10],
                    "sample_updates": changes["updates"][:10],
                    "sample_deletes": changes["deletes"][:10],
                    "applied": applied,
                }
            )
        except Exception as exc:
            logger.error("Erro ao auditar tabela %s: %s", codigo, exc)
            erros.append({"cod_tpr": codigo, "erro": str(exc)})

    duration_ms = int((time.perf_counter() - t0) * 1000)
    return {
        "dry_run": not apply,
        "apply": apply,
        "prune": prune,
        "codigos_solicitados": codigos,
        "tables_checked": len(summaries),
        "tables_with_differences": sum(
            1
            for item in summaries
            if item["to_insert"] or item["to_update"] or item["to_delete"]
        ),
        "senior_items": total_senior_items,
        "current_items": total_current_items,
        "to_insert": total_insert,
        "to_update": total_update,
        "to_delete": total_delete,
        "erros": erros,
        "duration_ms": duration_ms,
        "tabelas": summaries,
    }


# ── Queries Supabase ──────────────────────────────────────────────────────────

def list_tabelas() -> dict:
    """Lista tabelas de preço com contagem de itens."""
    db = _db()
    tabelas = db.table("tabelas_preco").select("id, codigo_tabela, nome_tabela, synced_at").order("codigo_tabela").execute().data or []

    contagem_map: dict[str, int] = {}
    for tabela in tabelas:
        codigo = tabela["codigo_tabela"]
        try:
            count_res = (
                db.table("tabelas_preco_itens")
                .select("id", count="exact")
                .eq("codigo_tabela", codigo)
                .limit(1)
                .execute()
            )
            contagem_map[codigo] = count_res.count or 0
        except Exception as exc:
            logger.warning("Falha ao contar itens da tabela %s: %s", codigo, exc)
            contagem_map[codigo] = 0

    result = [
        {**t, "total_itens": contagem_map.get(t["codigo_tabela"], 0)}
        for t in tabelas
    ]
    return {"tabelas": result, "total": len(result)}


def get_tabela_itens(codigo_tabela: str) -> dict:
    """Retorna itens de uma tabela de preço específica."""
    db = _db()

    tabela_res = db.table("tabelas_preco").select("codigo_tabela, nome_tabela").eq("codigo_tabela", codigo_tabela).limit(1).execute()
    tabela_rows = tabela_res.data or []
    if not tabela_rows:
        raise ValueError(f'Tabela "{codigo_tabela}" não encontrada')
    tabela = tabela_rows[0]

    itens = db.table("tabelas_preco_itens").select(
        "id, codigo_tabela, cod_produto, nome_produto, variacao, quantidade_minima, preco, desconto, synced_at"
    ).eq("codigo_tabela", codigo_tabela).order("cod_produto").execute().data or []

    return {
        "codigo_tabela": tabela["codigo_tabela"],
        "nome_tabela": tabela["nome_tabela"],
        "itens": itens,
        "total": len(itens),
    }


# ── CLI ────────────────────────────────────────────────────────────────────────

def emit(payload: dict) -> None:
    sys.stdout.write(json.dumps(payload, ensure_ascii=False, default=str))
    sys.stdout.write("\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="CLI de tabelas de preço do Senior ERP")
    subparsers = parser.add_subparsers(dest="command")

    # sync (default sem subcomando, mantém compatibilidade)
    sync_p = subparsers.add_parser("sync", help="Sincroniza tabelas via Senior ERP SOAP")
    sync_p.add_argument("--cod-tpr", dest="cod_tpr", nargs="+", default=["201", "202"])
    sync_p.add_argument("--dry-run", action="store_true")

    # list
    subparsers.add_parser("list", help="Lista tabelas de preço do Supabase")

    # detail
    detail_p = subparsers.add_parser("detail", help="Itens de uma tabela de preço")
    detail_p.add_argument("--cod-tpr", dest="cod_tpr", required=True)

    # audit
    audit_p = subparsers.add_parser("audit", help="Compara tabelas registradas com Senior ERP")
    audit_p.add_argument("--cod-tpr", dest="cod_tpr", nargs="+")
    audit_p.add_argument("--all", dest="all_registered", action="store_true", help="Audita todos os codigos registrados")
    audit_p.add_argument("--apply", action="store_true", help="Aplica inserts/updates no Supabase")
    audit_p.add_argument("--no-prune", dest="prune", action="store_false", help="Nao aponta/remove itens ausentes no Senior")
    audit_p.set_defaults(prune=True)

    # parse com fallback ao comportamento antigo (sem subcomando = sync)
    args, remaining = parser.parse_known_args()

    if args.command is None:
        # Compatibilidade: sem subcomando usa o parser antigo
        legacy = argparse.ArgumentParser()
        legacy.add_argument("--cod-tpr", dest="cod_tpr", nargs="+", default=["201", "202"])
        legacy.add_argument("--dry-run", action="store_true")
        largs = legacy.parse_args(remaining)
        args.cod_tpr = largs.cod_tpr
        args.dry_run = largs.dry_run
        args.command = "sync"

    try:
        if args.command == "list":
            result = list_tabelas()
            emit({"ok": True, "data": result})
        elif args.command == "detail":
            result = get_tabela_itens(args.cod_tpr)
            emit({"ok": True, "data": result})
        elif args.command == "audit":
            result = audit_tabelas(
                codigos=getattr(args, "cod_tpr", None),
                all_registered=getattr(args, "all_registered", False),
                apply=getattr(args, "apply", False),
                prune=getattr(args, "prune", True),
            )
            emit({"ok": True, "data": result})
        else:  # sync
            dry_run = getattr(args, "dry_run", False)
            result = sync_tabelas(codigos=args.cod_tpr, dry_run=dry_run)
            emit({"ok": True, "data": result})
        return 0
    except Exception as exc:
        logger.exception("Falha no CLI de tabelas de preço")
        emit({"ok": False, "error": str(exc)})
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
