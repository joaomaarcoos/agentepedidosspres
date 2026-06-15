from __future__ import annotations

import argparse
import json
import sys

from secretary_agent import secretary_dashboard, secretary_metrics


def main() -> int:
    parser = argparse.ArgumentParser(description="Metricas da Marcela Secretaria")
    sub = parser.add_subparsers(dest="command", required=True)
    metrics = sub.add_parser("metrics")
    metrics.add_argument("--date-from", default=None)
    metrics.add_argument("--date-to", default=None)
    metrics.add_argument("--cod-rep", type=int, default=None)
    dashboard = sub.add_parser("dashboard")
    dashboard.add_argument("--date-from", default=None)
    dashboard.add_argument("--date-to", default=None)
    dashboard.add_argument("--status", default=None)
    dashboard.add_argument("--search", default=None)
    dashboard.add_argument("--page", type=int, default=1)
    dashboard.add_argument("--page-size", type=int, default=25)
    dashboard.add_argument("--cod-rep", type=int, default=None)
    args = parser.parse_args()
    try:
        if args.command == "dashboard":
            data = secretary_dashboard(
                args.date_from,
                args.date_to,
                args.status,
                args.search,
                args.page,
                args.page_size,
                args.cod_rep,
            )
        else:
            data = secretary_metrics(args.date_from, args.date_to, args.cod_rep)
        payload = {"ok": True, "data": data}
    except Exception as exc:
        payload = {"ok": False, "error": str(exc)}
    sys.stdout.write(json.dumps(payload, ensure_ascii=False))
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
