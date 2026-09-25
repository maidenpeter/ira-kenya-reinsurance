"""Score every Kenyan general insurer the way a reinsurer screens a cedant.

Structure follows the building blocks of Best's Credit Rating Methodology (balance sheet strength,
operating performance, business profile, and a data and risk management block), using only what IRA
publishes. Scores are relative: each metric is ranked against the year's peer group, so a grade says
where a company stands among Kenyan general insurers that year, not an absolute credit opinion.

Peer group: insurers (not reinsurers, not micro insurers) with at least KSh 500m written premium that year.

Metric                     Pillar                 Weight  Better when
capital_cover              Balance sheet          15      higher   equity over IRA's floor: higher of KSh 600m and 20% of NEP
liquidity_cover            Balance sheet          10      higher   cash, deposits and government paper over insurance liabilities
receivables_share          Balance sheet          10      lower    receivables over total assets
combined_ratio_3y          Operating performance  15      lower    average of the last three full years
loss_ratio_volatility_5y   Operating performance  10      lower    spread of the loss ratio over up to five years
return_on_equity_3y        Operating performance  10      higher   average profit after tax over equity
scale                      Business profile        5      higher   written premium (log)
diversification            Business profile        5      higher   1 minus the Herfindahl index of the class mix
retention                  Business profile        5      higher   net written over written premium; a cedant keeping little risk has little at stake
reliability                Return quality         15      higher   100 less 30 per error, 10 per warning, 10 per missed filing, last three years

Percentile ranks run 0 to 100, except return quality, which is already an absolute 0 to 100 score. Missing metrics are left out of their pillar's average; a company with
negative equity takes the bottom rank for return on equity.

Grade bands on the weighted score: A 70+, B 55-70, C 40-55, D 25-40, E below 25.
Watch flags are absolute tests reported beside the grade. Two of them cap the grade at D:
negative equity, and equity below IRA's minimum capital floor.
"""
import os
import numpy as np
import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
OUT = os.path.join(ROOT, "output")

METRICS = [  # name, pillar, weight, higher_is_better
    ("capital_cover", "balance_sheet", 15, True),
    ("liquidity_cover", "balance_sheet", 10, True),
    ("receivables_share", "balance_sheet", 10, False),
    ("combined_ratio_3y", "operating", 15, False),
    ("loss_ratio_volatility_5y", "operating", 10, False),
    ("return_on_equity_3y", "operating", 10, True),
    ("scale", "business_profile", 5, True),
    ("diversification", "business_profile", 5, True),
    ("retention", "business_profile", 5, True),
    ("reliability", "return_quality", 15, True),
]
PILLARS = {"balance_sheet": "Balance sheet", "operating": "Operating performance",
           "business_profile": "Business profile", "return_quality": "Return quality"}
BANDS = [(70, "A"), (55, "B"), (40, "C"), (25, "D"), (-1, "E")]
MIN_PREMIUM = 500.0


def grade(s):
    return next(g for cut, g in BANDS if s >= cut)


def score(m, metrics=METRICS, cap=True):
    m = m.copy()
    m["scale"] = np.log(m.written_premium)
    m["diversification"] = 1 - m.hhi
    m["reliability"] = (100 - 30 * m.errors_3y - 10 * m.warnings_3y - 10 * m.missed_filings_3y).clip(lower=0)
    peer = m[(m.written_premium >= MIN_PREMIUM) & (m.is_micro == 0)].copy()
    for name, _, _, hib in metrics:
        if name == "reliability":  # already an absolute 0-100 score; ranking it would flatten the ties
            peer["pct_" + name] = peer[name]
            continue
        r = peer.groupby("year")[name].rank(pct=True, ascending=hib) * 100
        if name == "return_on_equity_3y":
            r = r.where(peer.equity > 0, 0.0)
        peer["pct_" + name] = r
    total_w = sum(w for _, _, w, _ in metrics)
    for p in PILLARS:
        ms = [(n, w) for n, pp, w, _ in metrics if pp == p]
        num = sum(peer["pct_" + n].fillna(0) * w for n, w in ms)
        den = sum(peer["pct_" + n].notna() * w for n, w in ms)
        peer["pillar_" + p] = num / den.replace(0, np.nan)
    pw = {p: sum(w for _, pp, w, _ in metrics if pp == p) for p in PILLARS}
    num = sum(peer["pillar_" + p].fillna(0) * pw[p] for p in PILLARS)
    den = sum(peer["pillar_" + p].notna() * pw[p] for p in PILLARS)
    peer["score"] = num / den
    # watch flags: absolute tests
    flags = []
    for _, r in peer.iterrows():
        f = []
        if r.equity is not None and r.equity < 0: f.append("negative_equity")
        elif r.capital_cover < 1: f.append("below_capital_floor")
        if r.combined_ratio_3y > 1.10: f.append("combined_ratio_above_110")
        if r.uw_loss_years_3y >= 3: f.append("three_underwriting_losses")
        if r.errors_3y > 0: f.append("unreliable_return")
        if r.retention < 0.25: f.append("low_retention")
        flags.append(";".join(f))
    peer["watch_flags"] = flags
    peer["grade_uncapped"] = peer.score.apply(grade)
    capped = peer.watch_flags.str.contains("negative_equity|below_capital_floor")
    order = "ABCDE"
    peer["grade"] = ["D" if (cap and c and order.index(g) < order.index("D")) else g
                     for g, c in zip(peer.grade_uncapped, capped)]
    peer["rank"] = peer.groupby("year").score.rank(ascending=False, method="min").astype(int)
    peer["peers"] = peer.groupby("year").company_id.transform("count")
    return peer


def main():
    m = pd.read_csv(os.path.join(OUT, "cedant_metrics.csv"))
    s = score(m)
    s.to_csv(os.path.join(OUT, "cedant_scorecard.csv"), index=False, lineterminator="\n", float_format="%.4f")
    # sensitivity: equal weights for every metric, and equal pillar weights
    eq_metric = [(n, p, 1, h) for n, p, _, h in METRICS]
    counts = {p: sum(1 for _, pp, _, _ in METRICS if pp == p) for p in PILLARS}
    eq_pillar = [(n, p, 25 / counts[p], h) for n, p, _, h in METRICS]
    rows = []
    for label, alt in [("equal metric weights", eq_metric), ("equal pillar weights", eq_pillar)]:
        a = score(m, alt)
        j = s[["company_id", "year", "score", "grade"]].merge(a[["company_id", "year", "score", "grade"]],
                                                                on=["company_id", "year"], suffixes=("", "_alt"))
        for y, g in j.groupby("year"):
            rows.append(dict(alternative=label, year=y, spearman=round(g.score.rank().corr(g.score_alt.rank()), 3),
                             grade_changes=int((g.grade != g.grade_alt).sum()), peers=len(g)))
    sens = pd.DataFrame(rows)
    sens.to_csv(os.path.join(OUT, "sensitivity.csv"), index=False, lineterminator="\n")
    print(sens.to_string(index=False))
    pd.set_option("display.width", 250)
    y = s.year.max()
    print(s[s.year == y].sort_values("score", ascending=False)[
        ["rank", "company_name", "grade", "score", "pillar_balance_sheet", "pillar_operating", "pillar_business_profile",
         "pillar_return_quality", "watch_flags"]].round(1).to_string(index=False))


if __name__ == "__main__":
    main()
