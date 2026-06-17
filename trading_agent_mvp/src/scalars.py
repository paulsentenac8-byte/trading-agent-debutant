from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


def coerce_scalar(value: Any) -> Any:
    if isinstance(value, pd.Series):
        clean = value.dropna()
        if not clean.empty:
            return clean.iloc[0]
        return value.iloc[0] if len(value) > 0 else np.nan
    if isinstance(value, (list, tuple)):
        return value[0] if value else np.nan
    return value


def to_float(value: Any, default: float = 0.0) -> float:
    scalar = coerce_scalar(value)
    try:
        if pd.isna(scalar):
            return float(default)
    except Exception:
        pass
    try:
        return float(scalar)
    except Exception:
        return float(default)


def to_int(value: Any, default: int = 0) -> int:
    scalar = coerce_scalar(value)
    try:
        if pd.isna(scalar):
            return int(default)
    except Exception:
        pass
    try:
        return int(float(scalar))
    except Exception:
        return int(default)
