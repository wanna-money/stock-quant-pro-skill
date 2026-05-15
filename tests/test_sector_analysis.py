"""Mock-based unit tests for scripts/sector_analysis.py — no real network calls."""
from __future__ import annotations

from unittest.mock import patch

import pandas as pd
import pytest

import sector_analysis as sa


pytestmark = pytest.mark.unit


def _fake_industry_df():
    return pd.DataFrame([
        {"板块名称": "半导体", "涨跌幅": 3.5, "总市值": 1e12,
         "换手率": 2.1, "领涨股票": "中芯国际", "领涨股票-涨跌幅": 9.8},
        {"板块名称": "白酒", "涨跌幅": -1.2, "总市值": 3e12,
         "换手率": 0.8, "领涨股票": "贵州茅台", "领涨股票-涨跌幅": -2.5},
        {"板块名称": "银行", "涨跌幅": 0.0, "总市值": 8e12,
         "换手率": 0.4, "领涨股票": "招商银行", "领涨股票-涨跌幅": 0.5},
        {"板块名称": "医药", "涨跌幅": 2.1, "总市值": 5e12,
         "换手率": 1.5, "领涨股票": "恒瑞医药", "领涨股票-涨跌幅": 5.0},
    ])


def _fake_concept_df():
    return pd.DataFrame([
        {"板块名称": "AI算力", "涨跌幅": 5.0},
        {"板块名称": "新能源车", "涨跌幅": 1.5},
    ])


class TestSectorRanking:
    def test_ranking_sorted_descending(self):
        with patch.object(sa, "get_industry_list", return_value=_fake_industry_df()):
            out = sa.sector_ranking(top_n=3)
        assert len(out) == 3
        assert out[0]["name"] == "半导体"
        assert out[0]["change_pct"] == 3.5
        assert out[1]["name"] == "医药"
        changes = [x["change_pct"] for x in out]
        assert changes == sorted(changes, reverse=True)

    def test_ranking_schema(self):
        with patch.object(sa, "get_industry_list", return_value=_fake_industry_df()):
            out = sa.sector_ranking(top_n=1)
        for k in ("name", "change_pct", "total_mv", "turnover_rate",
                  "leading_stock", "leading_stock_change"):
            assert k in out[0]


class TestSectorBreadth:
    def test_breadth_counts(self):
        with patch.object(sa, "get_industry_list", return_value=_fake_industry_df()):
            out = sa.sector_breadth()
        # 2 advancing (半导体, 医药), 1 declining (白酒), 1 flat (银行)
        assert out["total_sectors"] == 4
        assert out["advancing"] == 2
        assert out["declining"] == 1
        assert out["flat"] == 1
        assert out["advance_decline_ratio"] == 2.0
        assert out["breadth_pct"] == 50.0

    def test_breadth_avg_median_present(self):
        with patch.object(sa, "get_industry_list", return_value=_fake_industry_df()):
            out = sa.sector_breadth()
        assert "avg_change_pct" in out
        assert "median_change_pct" in out


class TestHotSectors:
    def test_hot_combines_industry_and_concept(self):
        with patch.object(sa, "get_industry_list", return_value=_fake_industry_df()), \
             patch.object(sa, "get_concept_list", return_value=_fake_concept_df()):
            out = sa.hot_sectors(top_n=2)
        assert len(out["industry"]) == 2
        assert len(out["concept"]) == 2
        assert out["industry"][0]["name"] == "半导体"
        assert out["concept"][0]["name"] == "AI算力"

    def test_hot_tolerates_concept_failure(self):
        with patch.object(sa, "get_industry_list", return_value=_fake_industry_df()), \
             patch.object(sa, "get_concept_list", side_effect=RuntimeError("down")):
            out = sa.hot_sectors(top_n=2)
        assert len(out["industry"]) == 2
        assert out["concept"] == []
        assert "concept_error" in out

    def test_hot_tolerates_industry_failure(self):
        with patch.object(sa, "get_industry_list", side_effect=RuntimeError("down")), \
             patch.object(sa, "get_concept_list", return_value=_fake_concept_df()):
            out = sa.hot_sectors(top_n=2)
        assert out["industry"] == []
        assert "industry_error" in out


class TestSectorRotation:
    def test_rotation_returns_top_sectors(self):
        def fake_perf(name, period="daily", start=None, end=None):
            if name == "半导体":
                closes = [100.0] * 15 + [100, 101, 103, 106, 110]
            else:
                closes = list(range(100, 120))
            return pd.DataFrame({"收盘": closes})

        with patch.object(sa, "get_industry_list", return_value=_fake_industry_df()), \
             patch.object(sa, "get_sector_performance", side_effect=fake_perf):
            out = sa.sector_rotation_analysis(days=20)
        assert isinstance(out, list)
        assert len(out) > 0
        for row in out:
            assert "name" in row and "acceleration" in row
        accels = [r["acceleration"] for r in out]
        assert accels == sorted(accels, reverse=True)

    def test_rotation_skips_insufficient_history(self):
        def fake_perf(name, period="daily", start=None, end=None):
            return pd.DataFrame({"收盘": [100.0, 101.0]})

        with patch.object(sa, "get_industry_list", return_value=_fake_industry_df()), \
             patch.object(sa, "get_sector_performance", side_effect=fake_perf):
            out = sa.sector_rotation_analysis(days=20)
        assert out == []

    def test_rotation_acceleration_scales_with_days_param(self):
        def fake_perf(name, period="daily", start=None, end=None):
            closes = [100.0 + i for i in range(15)]
            return pd.DataFrame({"收盘": closes})

        with patch.object(sa, "get_industry_list", return_value=_fake_industry_df()), \
             patch.object(sa, "get_sector_performance", side_effect=fake_perf):
            out = sa.sector_rotation_analysis(days=10)
        assert len(out) > 0
        first = out[0]
        short_ret = first["5d_return_pct"]
        med_ret = first["10d_return_pct"]
        expected_accel = round(short_ret - (med_ret / max(10 / 5, 1)), 2)
        assert first["acceleration"] == expected_accel
