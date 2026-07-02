"""
senior_order_client.py
======================
Cliente SOAP minimo para gravar pedidos no Senior ERP.

Usa o payload validado em teste para a porta GravarPedidos:
pedido com cliente, tipo, fechamento e itens com produto/derivacao/quantidade.
"""

from __future__ import annotations

import os
import re
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=True)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _number_br(value: Any) -> str:
    try:
        number = float(str(value or 0).replace(",", "."))
    except (TypeError, ValueError):
        number = 0.0
    return f"{number:.2f}".replace(".", ",")


def _strip_ns(tag: str) -> str:
    return re.sub(r"\{[^}]*\}", "", tag)


@dataclass
class SeniorOrderResult:
    http_status: int
    duration_ms: int
    endpoint: str
    request_xml_masked: str
    response_xml: str
    parsed: dict[str, Any]

    @property
    def order_number(self) -> str:
        value = self.parsed.get("numPed")
        return str(value or "").strip()

    @property
    def ok(self) -> bool:
        return (
            str(self.parsed.get("tipoRetorno") or "") == "1"
            and str(self.parsed.get("tipRet") or "") == "1"
            and str(self.parsed.get("retorno") or "").upper() == "OK"
        )

    def to_response_payload(self) -> dict[str, Any]:
        return {
            "http_status": self.http_status,
            "duration_ms": self.duration_ms,
            "endpoint": self.endpoint,
            "senior": self.parsed,
            "response_xml": self.response_xml,
        }


class SeniorOrderClient:
    def __init__(self) -> None:
        self.base_url = os.getenv("SENIOR_BASE_URL", "").rstrip("/")
        self.user = os.getenv("SENIOR_USER", "")
        self.password = os.getenv("SENIOR_PASSWORD", "")
        self.encryption = os.getenv("SENIOR_ENCRYPTION", "0")
        self.cod_emp = os.getenv("SENIOR_COD_EMP", "1")
        self.cod_fil = os.getenv("SENIOR_COD_FIL", "1")
        if not all([self.base_url, self.user, self.password]):
            raise ValueError("Configuracao Senior incompleta. Verifique SENIOR_BASE_URL, SENIOR_USER e SENIOR_PASSWORD.")
        self.endpoint = f"{self.base_url}/g5-senior-services/sapiens_Synccom_senior_g5_co_mcm_ven_pedidos"

    def _build_xml(self, order: dict[str, Any], masked: bool = False) -> str:
        password = "***MASKED***" if masked else self.password
        customer_code = escape(_text(order.get("customer_code")))
        if not customer_code:
            raise ValueError("Codigo do cliente Senior nao definido.")

        item_blocks: list[str] = []
        for item in order.get("items_json") or []:
            cod_pro = escape(_text(item.get("cod_produto") or item.get("codPro") or item.get("codigo")))
            cod_der = escape(_text(item.get("derivacao") or item.get("variacao") or item.get("codDer")))
            quantity = _number_br(item.get("quantidade") or item.get("qtdPed"))
            if not cod_pro:
                raise ValueError("Item sem codigo de produto Senior.")
            if not cod_der:
                raise ValueError(f"Item {cod_pro} sem derivacao Senior.")
            if quantity == "0,00":
                raise ValueError(f"Item {cod_pro}-{cod_der} sem quantidade.")
            item_blocks.append(
                f"""
          <produto>
            <opeExe>I</opeExe>
            <codPro>{cod_pro}</codPro>
            <codDer>{cod_der}</codDer>
            <qtdPed>{quantity}</qtdPed>
          </produto>"""
            )

        if not item_blocks:
            raise ValueError("Pedido sem itens para envio ao Senior.")

        return f"""<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
                  xmlns:ser="http://services.senior.com.br">
  <soapenv:Header/>
  <soapenv:Body>
    <ser:GravarPedidos>
      <user>{escape(self.user)}</user>
      <password>{escape(password)}</password>
      <encryption>{escape(self.encryption)}</encryption>
      <parameters>
        <pedido>
          <opeExe>I</opeExe>
          <codEmp>{escape(self.cod_emp)}</codEmp>
          <codFil>{escape(self.cod_fil)}</codFil>
          <codCli>{customer_code}</codCli>
          <tipPed>1</tipPed>
          <fecPed>S</fecPed>
{''.join(item_blocks)}
        </pedido>
      </parameters>
    </ser:GravarPedidos>
  </soapenv:Body>
</soapenv:Envelope>"""

    def build_masked_payload(self, order: dict[str, Any]) -> dict[str, Any]:
        return {
            "provider": "senior",
            "operation": "GravarPedidos",
            "endpoint": self.endpoint,
            "xml": self._build_xml(order, masked=True),
        }

    def submit_order(self, order: dict[str, Any]) -> SeniorOrderResult:
        body = self._build_xml(order, masked=False)
        masked_body = self._build_xml(order, masked=True)
        headers = {
            "Content-Type": "text/xml; charset=utf-8",
            "SOAPAction": '""',
        }
        started = time.perf_counter()
        response = requests.post(self.endpoint, data=body.encode("utf-8"), headers=headers, timeout=60)
        duration_ms = int((time.perf_counter() - started) * 1000)
        response.raise_for_status()
        return SeniorOrderResult(
            http_status=response.status_code,
            duration_ms=duration_ms,
            endpoint=self.endpoint,
            request_xml_masked=masked_body,
            response_xml=response.text,
            parsed=parse_gravar_pedidos_response(response.text),
        )


def parse_gravar_pedidos_response(xml_text: str) -> dict[str, Any]:
    root = ET.fromstring(xml_text.encode("utf-8"))
    parsed: dict[str, Any] = {}
    wanted = {"erroExecucao", "mensagemRetorno", "tipoRetorno"}
    response_wanted = {"numPed", "tipRet", "retorno", "msgRet", "sitPed", "ideExt"}

    for el in root.iter():
        name = _strip_ns(el.tag)
        text = (el.text or "").strip()
        if text and name in wanted:
            parsed[name] = text

    for resposta in root.iter():
        if _strip_ns(resposta.tag) != "respostaPedido":
            continue
        for child in resposta:
            name = _strip_ns(child.tag)
            text = (child.text or "").strip()
            if text and name in response_wanted and name not in parsed:
                parsed[name] = text

    grid_pro = []
    for grid in root.iter():
        if _strip_ns(grid.tag) != "gridPro":
            continue
        row = {_strip_ns(child.tag): (child.text or "").strip() for child in grid}
        if row:
            grid_pro.append(row)
    if grid_pro:
        parsed["gridPro"] = grid_pro

    return parsed
