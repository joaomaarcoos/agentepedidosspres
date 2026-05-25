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
    """Preenche nome_produto dos itens a partir da tabela produtos do Supabase."""
    try:
        res = db.table("produtos").select("cod_produto, nome").eq("ativo", True).execute()
        nome_map = {
            p["cod_produto"]: p["nome"]
            for p in (res.data or [])
            if p.get("nome")
        }
        for item in itens:
            if not item.get("nome_produto"):
                item["nome_produto"] = nome_map.get(item["cod_produto"])
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
        BATCH = 500
        for i in range(0, len(itens), BATCH):
            db.table("tabelas_preco_itens").insert(itens[i : i + BATCH]).execute()
        logger.info("Itens inseridos: %d", len(itens))

    return {"tabelas_upserted": len(tabelas), "itens_upserted": len(itens)}


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


# ── Queries Supabase ──────────────────────────────────────────────────────────

def list_tabelas() -> dict:
    """Lista tabelas de preço com contagem de itens."""
    db = _db()
    tabelas = db.table("tabelas_preco").select("id, codigo_tabela, nome_tabela, synced_at").order("codigo_tabela").execute().data or []

    codigos = [t["codigo_tabela"] for t in tabelas]
    contagem_map: dict[str, int] = {}
    if codigos:
        itens_count = db.table("tabelas_preco_itens").select("codigo_tabela").in_("codigo_tabela", codigos).execute().data or []
        for row in itens_count:
            cod = row["codigo_tabela"]
            contagem_map[cod] = contagem_map.get(cod, 0) + 1

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
