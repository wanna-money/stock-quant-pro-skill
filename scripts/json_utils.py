"""JSON serialization helpers for the stock-quant-pro-skill scripts.

Stdlib `json.dumps` emits the bareword token `NaN` (and `Infinity`) for
non-finite floats. These tokens are invalid per RFC 8259 and are rejected
by strict parsers (`JSON.parse` in browsers, Go `encoding/json`, jq, etc.).

`safe_json_dumps` walks the structure first and replaces non-finite floats
with `None`, then emits standards-compliant JSON.
"""
from __future__ import annotations

import json
import math
from typing import Any

try:
    import numpy as np
    _NP_FLOATING = np.floating
    _NP_INTEGER = np.integer
    _NP_BOOL = np.bool_
except ImportError:
    _NP_FLOATING = None
    _NP_INTEGER = None
    _NP_BOOL = None


def _sanitize(obj: Any) -> Any:
    if _NP_FLOATING is not None and isinstance(obj, _NP_FLOATING):
        f = float(obj)
        return f if math.isfinite(f) else None
    if _NP_INTEGER is not None and isinstance(obj, _NP_INTEGER):
        return int(obj)
    if _NP_BOOL is not None and isinstance(obj, _NP_BOOL):
        return bool(obj)
    if isinstance(obj, float):
        return obj if math.isfinite(obj) else None
    if isinstance(obj, dict):
        return {k: _sanitize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_sanitize(v) for v in obj]
    return obj


def safe_json_dumps(obj: Any, **kwargs: Any) -> str:
    """Drop-in replacement for json.dumps that produces strict JSON.

    Non-finite floats (NaN / +inf / -inf) become null. All other behavior
    (ensure_ascii, indent, default=) is preserved.
    """
    cleaned = _sanitize(obj)
    return json.dumps(cleaned, allow_nan=False, **kwargs)
