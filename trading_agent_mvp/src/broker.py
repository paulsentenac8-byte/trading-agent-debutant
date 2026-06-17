from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

import pandas as pd


@dataclass
class BrokerOrder:
    symbol: str
    side: str
    qty: int
    order_type: str
    reference_price: float
    stop_loss: float
    take_profit: float
    rationale: str
    tif: str = "DAY"
    approved: bool = False


class ManualApprovalBroker:
    """Écrit des ordres à relire au lieu de les envoyer à un broker réel."""

    def submit_orders(self, orders: Iterable[BrokerOrder], output_path: str) -> Path:
        records = [asdict(order) for order in orders]
        df = pd.DataFrame(records)
        if not df.empty:
            df["limit_price"] = df["reference_price"].round(4)
            df["broker_status"] = "PENDING_REVIEW"
            df["review_comment"] = ""
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(path, index=False)
        return path


class IBKRManualApprovalBroker:
    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 7497,
        client_id: int = 7,
        account: str | None = None,
        paper_only: bool = True,
        currency: str = "USD",
        exchange: str = "SMART",
    ) -> None:
        self.host = host
        self.port = port
        self.client_id = client_id
        self.account = account
        self.paper_only = paper_only
        self.currency = currency
        self.exchange = exchange

    @staticmethod
    def _truthy(value: Any) -> bool:
        return str(value).strip().lower() in {"1", "true", "yes", "y", "oui"}

    def build_payloads_from_review_df(self, review_df: pd.DataFrame) -> list[dict[str, Any]]:
        if review_df.empty:
            return []
        approved = review_df[review_df["approved"].apply(self._truthy)].copy()
        payloads: list[dict[str, Any]] = []

        for _, row in approved.iterrows():
            qty = int(row["qty"])
            limit_price = float(row.get("limit_price", row.get("reference_price", 0.0)))
            reference_price = float(row.get("reference_price", row.get("limit_price", 0.0)))
            stop_loss = float(row["stop_loss"])
            take_profit = float(row["take_profit"])
            if qty <= 0 or limit_price <= 0 or reference_price <= 0 or stop_loss <= 0 or take_profit <= 0:
                continue
            payloads.append(
                {
                    "symbol": str(row["symbol"]),
                    "side": str(row.get("side", "BUY")).upper(),
                    "qty": qty,
                    "order_type": str(row.get("order_type", "LMT")).upper(),
                    "limit_price": limit_price,
                    "reference_price": reference_price,
                    "stop_loss": stop_loss,
                    "take_profit": take_profit,
                    "tif": str(row.get("tif", "DAY")).upper(),
                    "rationale": str(row.get("rationale", "")),
                }
            )
        return payloads

    def save_payloads(self, payloads: list[dict[str, Any]], output_path: str) -> Path:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payloads, indent=2, ensure_ascii=False), encoding="utf-8")
        return path

    def submit_approved_orders(
        self,
        review_csv: str,
        payload_output_path: str,
        dry_run: bool = True,
    ) -> tuple[Path, list[dict[str, Any]]]:
        review_df = pd.read_csv(review_csv)
        payloads = self.build_payloads_from_review_df(review_df)
        payload_path = self.save_payloads(payloads, payload_output_path)

        if dry_run or not payloads:
            return payload_path, payloads

        if self.paper_only and self.port not in {7497, 4002}:
            raise ValueError("paper_only=True mais le port IBKR ne ressemble pas à un port paper.")

        try:
            from ib_insync import IB, MarketOrder, Stock
        except ImportError as exc:
            raise ImportError("ib_insync n'est pas installé. Lance `pip install -r requirements.txt`.") from exc

        ib = IB()
        ib.connect(self.host, self.port, clientId=self.client_id)
        submission_log: list[dict[str, Any]] = []

        try:
            for payload in payloads:
                contract = Stock(payload["symbol"], self.exchange, self.currency)
                ib.qualifyContracts(contract)

                if payload["order_type"] == "MKT":
                    parent = MarketOrder(payload["side"], payload["qty"], tif=payload["tif"])
                    trade = ib.placeOrder(contract, parent)
                    submission_log.append(
                        {
                            "symbol": payload["symbol"],
                            "order_type": "MKT",
                            "order_id": getattr(trade.order, "orderId", None),
                            "status": getattr(trade.orderStatus, "status", "SUBMITTED"),
                        }
                    )
                else:
                    bracket = ib.bracketOrder(
                        action=payload["side"],
                        quantity=payload["qty"],
                        limitPrice=payload["limit_price"],
                        takeProfitPrice=payload["take_profit"],
                        stopLossPrice=payload["stop_loss"],
                    )
                    for order in bracket:
                        order.tif = payload["tif"]
                        trade = ib.placeOrder(contract, order)
                        submission_log.append(
                            {
                                "symbol": payload["symbol"],
                                "order_type": getattr(order, "orderType", payload["order_type"]),
                                "order_id": getattr(trade.order, "orderId", None),
                                "status": getattr(trade.orderStatus, "status", "SUBMITTED"),
                            }
                        )
        finally:
            if ib.isConnected():
                ib.disconnect()

        log_path = Path(payload_output_path).with_name("ibkr_submission_log.json")
        log_path.write_text(json.dumps(submission_log, indent=2, ensure_ascii=False), encoding="utf-8")
        return payload_path, payloads
