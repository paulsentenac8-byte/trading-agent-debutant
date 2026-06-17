from __future__ import annotations

import socket
from dataclasses import asdict, dataclass
from typing import Any

from .config import BrokerConfig
from .runtime import utc_now_iso


@dataclass
class BrokerHealthSummary:
    checked_at: str
    mode: str
    host: str
    port: int
    paper_only: bool
    reachable: bool
    message: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def check_broker_health(config: BrokerConfig, timeout: float = 1.0) -> BrokerHealthSummary:
    reachable = False
    message = "Aucune vérification effectuée."

    try:
        with socket.create_connection((config.ibkr_host, int(config.ibkr_port)), timeout=timeout):
            reachable = True
            message = "Port broker accessible depuis l'application."
    except Exception as exc:
        reachable = False
        message = f"Broker non accessible actuellement: {exc}"

    return BrokerHealthSummary(
        checked_at=utc_now_iso(),
        mode=config.mode,
        host=config.ibkr_host,
        port=int(config.ibkr_port),
        paper_only=bool(config.paper_only),
        reachable=reachable,
        message=message,
    )
