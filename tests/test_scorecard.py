"""Tests for the scoring rules and guards on the published outputs.

The synthetic tests pin down the rules a reader would check first: which direction each metric counts,
the grade bands, the capital cap, and who is left out of the peer group. The output tests make sure the
committed scorecard obeys the same rules.
"""
import os
import sys

import numpy as np
import pandas as pd
import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "src", "scorecard"))
import score as sc  # noqa: E402

OUT = os.path.join(ROOT, "output")


def peers(n=10, year=2025):
    """n ordinary insurers, company i slightly better than company i-1 on every metric."""
    i = np.arange(n)
    return pd.DataFrame(dict(
        company_id=[f"c{k}" for k in i], year=year, is_micro=0,
        written_premium=1000.0 + 100 * i, hhi=0.5 - 0.02 * i, retention=0.5 + 0.03 * i,
        equity=1000.0 + 100 * i, capital_cover=1.2 + 0.1 * i, liquidity_cover=0.8 + 0.05 * i,
        receivables_share=0.30 - 0.02 * i, combined_ratio_3y=1.08 - 0.01 * i,
        loss_ratio_volatility_5y=0.10 - 0.005 * i, return_on_equity_3y=0.02 * i,
        uw_loss_years_3y=0, errors_3y=0, warnings_3y=0, missed_filings_3y=0,
    ))


def test_grade_bands():
    assert [sc.grade(s) for s in (70, 69.99, 55, 54.99, 40, 25, 24.99, 0)] == list("ABBCCDEE")


def test_better_on_every_metric_ranks_first():
    s = sc.score(peers())
    assert s.sort_values("rank").company_id.tolist() == [f"c{k}" for k in range(9, -1, -1)]
    assert s.set_index("company_id").loc["c9", "grade"] == "A"


def test_lower_is_better_metrics_rank_the_right_way():
    s = sc.score(peers()).set_index("company_id")
    for m in ["receivables_share", "combined_ratio_3y", "loss_ratio_volatility_5y"]:
        assert s.loc["c9", "pct_" + m] > s.loc["c0", "pct_" + m], m


def test_negative_equity_caps_the_grade_at_d():
    m = peers()
    m.loc[m.company_id == "c9", ["equity", "capital_cover"]] = [-50.0, -0.1]
    s = sc.score(m).set_index("company_id")
    assert s.loc["c9", "grade"] == "D"
    assert "negative_equity" in s.loc["c9", "watch_flags"]
    assert s.loc["c9", "return_on_equity_3y"] == pytest.approx(0.18)  # the raw metric is kept
    assert s.loc["c9", "pct_return_on_equity_3y"] == 0  # but earns nothing without equity


def test_equity_below_the_floor_caps_the_grade_at_d():
    m = peers()
    m.loc[m.company_id == "c8", "capital_cover"] = 0.9
    s = sc.score(m).set_index("company_id")
    assert s.loc["c8", "grade"] == "D" and "below_capital_floor" in s.loc["c8", "watch_flags"]


def test_small_and_micro_insurers_are_not_scored():
    m = peers()
    m.loc[m.company_id == "c0", "written_premium"] = 499.0
    m.loc[m.company_id == "c1", "is_micro"] = 1
    s = sc.score(m)
    assert not {"c0", "c1"} & set(s.company_id)
    assert (s.peers == 8).all()


def test_return_quality_is_absolute():
    m = peers()
    m.loc[m.company_id == "c5", ["errors_3y", "warnings_3y", "missed_filings_3y"]] = [1, 1, 1]
    s = sc.score(m).set_index("company_id")
    assert s.loc["c5", "pct_reliability"] == 50  # 100 - 30 - 10 - 10
    assert s.loc["c4", "pct_reliability"] == 100


@pytest.fixture(scope="module")
def card():
    return pd.read_csv(os.path.join(OUT, "cedant_scorecard.csv"))


def test_published_grades_follow_the_rules(card):
    assert set(card.grade) <= set("ABCDE")
    capped = card[card.grade != card.grade_uncapped]
    assert (capped.grade == "D").all()
    assert capped.watch_flags.str.contains("negative_equity|below_capital_floor").all()
    assert ((card["rank"] >= 1) & (card["rank"] <= card.peers)).all()
    assert (card.written_premium >= 500).all() and (card.is_micro == 0).all()


def test_backtest_cases_carry_sources():
    b = pd.read_csv(os.path.join(OUT, "backtest.csv"))
    assert len(b) == 5
    assert b.source.str.startswith("https://").all()
