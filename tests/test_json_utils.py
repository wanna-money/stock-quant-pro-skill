"""Regression tests for scripts/json_utils.safe_json_dumps.

Ensures non-finite floats are scrubbed from output so downstream strict
parsers (browsers, jq, Go encoding/json) don't choke on `NaN`/`Infinity`.
"""
import json

import pytest

from json_utils import safe_json_dumps


pytestmark = pytest.mark.unit


def test_nan_becomes_null():
    out = safe_json_dumps({"x": float("nan")})
    assert json.loads(out) == {"x": None}


def test_positive_infinity_becomes_null():
    out = safe_json_dumps({"x": float("inf")})
    assert json.loads(out) == {"x": None}


def test_negative_infinity_becomes_null():
    out = safe_json_dumps({"x": float("-inf")})
    assert json.loads(out) == {"x": None}


def test_finite_floats_preserved():
    out = safe_json_dumps({"a": 1.5, "b": -0.0, "c": 1e10})
    parsed = json.loads(out)
    assert parsed["a"] == 1.5
    assert parsed["c"] == 1e10


def test_nested_dict_sanitized():
    out = safe_json_dumps({"outer": {"inner": float("nan"), "ok": 1.0}})
    assert json.loads(out) == {"outer": {"inner": None, "ok": 1.0}}


def test_nested_list_sanitized():
    out = safe_json_dumps({"items": [1.0, float("nan"), float("inf"), 2.0]})
    assert json.loads(out) == {"items": [1.0, None, None, 2.0]}


def test_tuple_becomes_list_and_sanitized():
    out = safe_json_dumps({"t": (1.0, float("nan"))})
    assert json.loads(out) == {"t": [1.0, None]}


def test_deeply_nested_structure():
    payload = {
        "level1": {
            "level2": [
                {"v": float("nan")},
                {"v": [float("inf"), 3.14]},
            ],
        }
    }
    parsed = json.loads(safe_json_dumps(payload))
    assert parsed["level1"]["level2"][0]["v"] is None
    assert parsed["level1"]["level2"][1]["v"] == [None, 3.14]


def test_strict_json_no_nan_token():
    out = safe_json_dumps({"a": float("nan"), "b": float("inf"), "c": float("-inf")})
    assert "NaN" not in out
    assert "Infinity" not in out


def test_kwargs_passthrough():
    out = safe_json_dumps({"k": "中文"}, ensure_ascii=False, indent=2)
    assert "中文" in out
    assert "\n" in out


def test_default_callback_still_works():
    class Custom:
        def __str__(self):
            return "custom-obj"

    out = safe_json_dumps({"obj": Custom()}, default=str)
    assert json.loads(out) == {"obj": "custom-obj"}


def test_non_dict_root_list():
    out = safe_json_dumps([1.0, float("nan")])
    assert json.loads(out) == [1.0, None]


def test_primitive_root():
    assert json.loads(safe_json_dumps(float("nan"))) is None
    assert json.loads(safe_json_dumps(42)) == 42
    assert json.loads(safe_json_dumps("hello")) == "hello"


class TestNumpyScalarSerialization:
    def test_np_int64_serializes(self):
        import numpy as np
        out = safe_json_dumps({"v": np.int64(42)})
        assert json.loads(out) == {"v": 42}

    def test_np_float64_nan_becomes_null(self):
        import numpy as np
        out = safe_json_dumps({"v": np.float64(float("nan"))})
        assert json.loads(out) == {"v": None}

    def test_np_bool_serializes(self):
        import numpy as np
        out = safe_json_dumps({"v": np.bool_(True)})
        assert json.loads(out) == {"v": True}

    def test_np_float64_finite_preserved(self):
        import numpy as np
        out = safe_json_dumps({"v": np.float64(3.14)})
        assert abs(json.loads(out)["v"] - 3.14) < 1e-9
