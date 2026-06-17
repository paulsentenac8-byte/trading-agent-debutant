from __future__ import annotations

import json
import os
import socket
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def write_json(path: str | Path, payload: dict[str, Any]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def hostname() -> str:
    try:
        return socket.gethostname()
    except Exception:
        return "unknown-host"


@contextmanager
def exclusive_lock(lock_path: str | Path) -> Iterator[bool]:
    path = Path(lock_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd: int | None = None
    acquired = False
    try:
        fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(fd, f"locked_at={utc_now_iso()}\nhost={hostname()}\npid={os.getpid()}\n".encode("utf-8"))
        acquired = True
    except FileExistsError:
        acquired = False

    try:
        yield acquired
    finally:
        if fd is not None:
            os.close(fd)
        if acquired and path.exists():
            path.unlink(missing_ok=True)
