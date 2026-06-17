from __future__ import annotations

import argparse
from pathlib import Path

from src.broker import IBKRManualApprovalBroker
from src.config import load_config


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Soumission manuelle d'ordres approuvés vers IBKR")
    parser.add_argument("--config", default="config.json", help="Chemin vers le fichier config")
    parser.add_argument("--orders", default="reports/orders_to_review.csv", help="CSV des ordres revus")
    parser.add_argument("--dry-run", action="store_true", help="Prépare seulement les payloads IBKR")
    parser.add_argument("--submit", action="store_true", help="Soumet réellement les ordres approuvés à IBKR")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = load_config(args.config)
    orders_path = Path(args.orders)
    if not orders_path.exists():
        raise FileNotFoundError(f"Fichier introuvable: {orders_path}")

    if args.submit and not config.broker.paper_only:
        raise ValueError("Pour la sécurité, garde broker.paper_only=true tant que tu n'as pas validé le flux en paper trading.")

    dry_run = True
    if args.submit:
        dry_run = False
    elif args.dry_run:
        dry_run = True

    broker = IBKRManualApprovalBroker(
        host=config.broker.ibkr_host,
        port=config.broker.ibkr_port,
        client_id=config.broker.client_id,
        account=config.broker.account,
        paper_only=config.broker.paper_only,
        currency=config.broker.currency,
        exchange=config.broker.exchange,
    )
    payload_path, payloads = broker.submit_approved_orders(
        review_csv=str(orders_path),
        payload_output_path=str(orders_path.parent / "ibkr_order_payloads_preview.json"),
        dry_run=dry_run,
    )

    mode = "DRY RUN" if dry_run else "SUBMIT"
    print(f"Mode: {mode}")
    print(f"Payloads générés: {len(payloads)}")
    print(f"Fichier preview: {payload_path}")
    if not dry_run:
        print(f"Si disponible, consulte aussi: {orders_path.parent / 'ibkr_submission_log.json'}")


if __name__ == "__main__":
    main()
