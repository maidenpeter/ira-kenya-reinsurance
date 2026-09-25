"""Build the scorecard page: page/scorecard_data.json and page/kenya-cedant-scorecard.html.

The page is page/template.html with the data inlined, so it opens as a single file.
"""
import json
import os
import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
OUT = os.path.join(ROOT, "output")
PAGE = os.path.join(ROOT, "page")
DATA_DIR = os.environ.get("IRA_DATA_DIR", os.path.join(ROOT, "..", "ira-kenya-data"))

METRICS = ["capital_cover", "liquidity_cover", "receivables_share", "combined_ratio_3y",
           "loss_ratio_volatility_5y", "return_on_equity_3y", "written_premium", "diversification",
           "retention", "reliability"]
PCT = ["capital_cover", "liquidity_cover", "receivables_share", "combined_ratio_3y",
       "loss_ratio_volatility_5y", "return_on_equity_3y", "scale", "diversification", "retention", "reliability"]
PILLARS = ["balance_sheet", "operating", "business_profile", "return_quality"]


def num(v, nd=4):
    return None if pd.isna(v) else round(float(v), nd)


def short(name):
    name = name.split(" (")[0]
    for tail in [" Insurance Company", " Assurance Company", " Insurance Kenya", " Insurance", " Assurance", " Company"]:
        if name.endswith(tail) and len(name) > len(tail) + 3:
            return name[: -len(tail)]
    return name


def main():
    s = pd.read_csv(os.path.join(OUT, "cedant_scorecard.csv"))
    bt = pd.read_csv(os.path.join(OUT, "backtest.csv"))
    ns = pd.read_csv(os.path.join(OUT, "not_scored.csv"))
    sens = pd.read_csv(os.path.join(OUT, "sensitivity.csv"))
    cw = pd.read_csv(os.path.join(DATA_DIR, "reference", "company_crosswalk.csv"))
    names = cw.drop_duplicates("company_id").set_index("company_id").company_name.to_dict()
    names.update(s.drop_duplicates("company_id").set_index("company_id").company_name.to_dict())

    years = sorted(int(y) for y in s.year.unique())
    rows = []
    for _, r in s.sort_values(["year", "rank"]).iterrows():
        rows.append(dict(
            id=r.company_id, y=int(r.year), score=num(r.score, 1), g=r.grade, gu=r.grade_uncapped,
            rank=int(r["rank"]), peers=int(r.peers),
            p=[num(r["pillar_" + p], 1) for p in PILLARS],
            pct=[num(r["pct_" + m], 1) for m in PCT],
            m=[num(r[m]) for m in METRICS],
            flags=[] if pd.isna(r.watch_flags) else r.watch_flags.split(";"),
            share=num(r.market_share), equity=num(r.equity, 1), basis=r.reporting_basis,
        ))
    comp = {c: dict(name=names.get(c, c), short=short(names.get(c, c))) for c in sorted(set(s.company_id) | set(ns.company_id) | set(bt.company_id))}
    backtest = []
    for _, r in bt.iterrows():
        backtest.append(dict(id=r.company_id, event=r.event, date=r.event_date, source=r.source,
                             last=int(r.last_scored_year), grade=r.grade, rank=r["rank"],
                             bottom=bool(r.bottom_quintile),
                             after=None if pd.isna(r.after_last_score) else r.after_last_score))
    not_scored = [dict(y=int(r.year), id=r.company_id, reason=r.reason, note=None if pd.isna(r.note) else r.note)
                  for _, r in ns.iterrows()]
    sensitivity = [dict(alt=r.alternative, y=int(r.year), rho=float(r.spearman), changes=int(r.grade_changes),
                        peers=int(r.peers)) for _, r in sens.iterrows()]
    data = dict(years=years, companies=comp, rows=rows, backtest=backtest, not_scored=not_scored,
                sensitivity=sensitivity, metrics=METRICS, pct=PCT, pillars=PILLARS)
    js = json.dumps(data, separators=(",", ":"), ensure_ascii=False)
    with open(os.path.join(PAGE, "scorecard_data.json"), "w", encoding="utf-8", newline="\n") as f:
        f.write(js)
    tpl = open(os.path.join(PAGE, "template.html"), encoding="utf-8").read()
    html = tpl.replace("/*__DATA__*/null", js.replace("</", "<\\/"))
    with open(os.path.join(PAGE, "kenya-cedant-scorecard.html"), "w", encoding="utf-8", newline="\n") as f:
        f.write(html)
    print(f"{len(rows)} rows, {len(years)} years, page {len(html) / 1024:.0f} KB")


if __name__ == "__main__":
    main()
