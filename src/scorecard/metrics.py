"""Cedant metrics for every Kenyan general insurer, every full year.

Reads the processed tables from the ira-kenya-data repo (set IRA_DATA_DIR, default ../ira-kenya-data)
and writes output/cedant_metrics.csv: one row per insurer and year with every metric the scorecard uses.

All money in KSh millions. A year means the full year, taken from the Q4 year-to-date figures and the
31 December balance sheet.
"""
import os
import numpy as np
import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DATA = os.environ.get("IRA_DATA_DIR", os.path.join(ROOT, "..", "ira-kenya-data"))
P = os.path.join(DATA, "data", "processed")
OUT = os.path.join(ROOT, "output")

LIQUID = ["Cash and Cash Balances", "Term Deposits", "Government Securities"]
INS_LIAB = {"IFRS 4": ["Underwriting Provisions", "Actuarial Contract Liabilities"], "IFRS 17": ["Insurance Contract Liabilities"]}
RECEIV = {"IFRS 4": ["Outstanding Premiums", "Other Receivables"], "IFRS 17": ["Insurance Contract Assets", "Other Receivables"]}


def load():
    pan = pd.read_csv(os.path.join(P, "general_revenue_panel.csv"))
    cls = pd.read_csv(os.path.join(P, "general_by_class_panel.csv"))
    bs = pd.read_csv(os.path.join(P, "general_balance_sheets.csv"))
    pl = pd.read_csv(os.path.join(P, "general_profit_loss.csv"))
    qf = pd.read_csv(os.path.join(DATA, "validation", "quality_flags.csv"))
    cw = pd.read_csv(os.path.join(DATA, "reference", "company_crosswalk.csv"))
    return pan, cls, bs, pl, qf, cw


def build():
    pan, cls, bs, pl, qf, cw = load()
    names = cw.drop_duplicates("company_id").set_index("company_id")[["company_name", "is_micro"]]
    # full-year revenue account
    rv = pan[(pan.quarter == 4) & (pan.segment == "insurer")].pivot_table(
        index=["company_id", "year"], columns="line", values="ytd_ksh_000", aggfunc="first") / 1000
    m = pd.DataFrame(index=rv.index)
    m["written_premium"] = rv.gross_direct_premium.fillna(0) + rv.inward_reinsurance.fillna(0)
    m["net_written"] = rv.net_premium_written
    m["net_earned"] = rv.net_earned_premium
    m["claims"] = rv.incurred_claims
    m["expenses"] = rv.net_commissions.fillna(0) + rv.management_expenses.fillna(0)
    m["underwriting_result"] = rv.underwriting_result
    m["investment_income"] = rv.investment_income
    m = m[m.written_premium > 0]
    m["loss_ratio"] = m.claims / m.net_earned
    m["combined_ratio"] = (m.claims + m.expenses) / m.net_earned
    m["retention"] = m.net_written / m.written_premium
    # balance sheet at 31 December
    b = bs[(bs.quarter == 4)].copy()
    rows = {}
    for (cid, y, basis), g in b.groupby(["company_id", "year", "reporting_basis"]):
        v = g.drop_duplicates("line_item").set_index("line_item").value_ksh_000.fillna(0) / 1000
        if v.abs().sum() == 0:
            continue
        rows[(cid, y)] = dict(total_assets=v.get("Total Assets"), equity=v.get("Total Equity"),
                              liquid_assets=sum(v.get(k, 0) for k in LIQUID),
                              insurance_liabilities=sum(v.get(k, 0) for k in INS_LIAB[basis]),
                              receivables=sum(v.get(k, 0) for k in RECEIV[basis]), reporting_basis=basis)
    bsdf = pd.DataFrame.from_dict(rows, orient="index"); bsdf.index = bsdf.index.set_names(["company_id", "year"])
    m = m.join(bsdf)
    # profit after tax
    p = pl[pl.quarter == 4]
    pat = {}
    for (cid, y), g in p.groupby(["company_id", "year"]):
        v = g.drop_duplicates("line_item").set_index("line_item").value_ksh_000
        val = v.get("Profit/(Loss) After Taxation", v.get("Profit for the year"))
        if pd.notna(val):
            pat[(cid, y)] = val / 1000
    ps = pd.Series(pat); ps.index = ps.index.set_names(["company_id", "year"])
    m["profit_after_tax"] = ps
    # class mix: concentration of written premium (Herfindahl) and motor share
    c = cls[(cls.quarter == 4) & (cls.table == "gross_premium") & (cls.class_of_business != "Total")]
    mix = c.groupby(["company_id", "year"]).apply(
        lambda g: pd.Series({"hhi": ((g.ytd_ksh_000.clip(lower=0) / g.ytd_ksh_000.clip(lower=0).sum()) ** 2).sum()
                             if g.ytd_ksh_000.clip(lower=0).sum() > 0 else np.nan,
                             "motor_share": g[g.class_of_business.str.startswith("Motor")].ytd_ksh_000.sum() / g.ytd_ksh_000.sum()
                             if g.ytd_ksh_000.sum() > 0 else np.nan}), include_groups=False)
    m = m.join(mix)
    # derived ratios
    m["capital_floor"] = np.maximum(600.0, 0.20 * m.net_earned.fillna(0))  # IRA general insurer minimum: higher of KSh 600m and 20% of NEP
    m["capital_cover"] = m.equity / m.capital_floor
    m["liquidity_cover"] = m.liquid_assets / m.insurance_liabilities.replace(0, np.nan)
    m["receivables_share"] = m.receivables / m.total_assets
    m["return_on_equity"] = m.profit_after_tax / m.equity.where(m.equity > 0)
    m = m.reset_index()
    m["market_share"] = m.written_premium / m.groupby("year").written_premium.transform("sum")
    # multi-year views: last three full years available (2017 is missing from IRA's site)
    m = m.sort_values(["company_id", "year"])
    def trailing(col, fn, n=3):
        out = []
        for cid, g in m.groupby("company_id"):
            s = g.set_index("year")[col]
            for y in g.year:
                w = s[(s.index <= y) & (s.index > y - n)].dropna()
                out.append(((cid, y), fn(w) if len(w) else np.nan))
        return pd.Series(dict(out))
    idx = list(zip(m.company_id, m.year))
    m["combined_ratio_3y"] = trailing("combined_ratio", lambda w: w.clip(upper=3).mean()).reindex(idx).values
    m["loss_ratio_volatility_5y"] = trailing("loss_ratio", lambda w: w.clip(upper=3).std() if len(w) >= 3 else np.nan, 5).reindex(idx).values
    m["return_on_equity_3y"] = trailing("return_on_equity", lambda w: w.mean()).reindex(idx).values
    m["uw_loss_years_3y"] = trailing("underwriting_result", lambda w: int((w < 0).sum())).reindex(idx).values
    # reporting reliability: flags in the three years to date
    q = qf[qf.segment == "insurer"]
    rel = []
    for cid, y in idx:
        w = q[(q.company_id == cid) & (q.year <= y) & (q.year > y - 3)]
        rel.append(dict(errors_3y=int((w.severity == "error").sum()), warnings_3y=int((w.severity == "warning").sum()),
                        missed_filings_3y=int((w.flag == "not_filed").sum())))
    m = pd.concat([m.reset_index(drop=True), pd.DataFrame(rel)], axis=1)
    m = m.join(names, on="company_id")
    return m


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    m = build()
    m.to_csv(os.path.join(OUT, "cedant_metrics.csv"), index=False, lineterminator="\n", float_format="%.4f")
    print(m.shape)
    pd.set_option("display.width", 250); pd.set_option("display.max_columns", 30)
    print(m[m.year == 2025][["company_id", "written_premium", "combined_ratio", "combined_ratio_3y", "retention", "capital_cover",
                              "liquidity_cover", "receivables_share", "return_on_equity", "hhi", "errors_3y", "missed_filings_3y"]]
          .sort_values("written_premium", ascending=False).round(2).to_string(index=False))
