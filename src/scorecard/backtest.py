"""Who was left out of each year's scorecard, and did the scorecard see the failures coming?

Writes output/not_scored.csv and output/backtest.csv.

Failures used (insurers placed under statutory management or liquidation, with sources):
  Resolution Insurance   statutory management, April 2022
  Xplico Insurance       statutory management, December 2023
  Invesco Assurance      handed to the Official Receiver for liquidation, December 2023
  Trident Insurance      statutory management, March 2026
  Corporate Insurance    statutory management, March 2026
"""
import os
import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DATA = os.environ.get("IRA_DATA_DIR", os.path.join(ROOT, "..", "ira-kenya-data"))
OUT = os.path.join(ROOT, "output")

FAILURES = [
    ("resolution", "2022-04", "statutory management", "https://www.capitalfm.co.ke/business/2022/04/resolution-insurance-placed-under-statutory-management-over-unsettled-claims/"),
    ("xplico", "2023-12", "statutory management", "https://www.capitalfm.co.ke/business/2023/12/xplico-insurance-placed-under-statutory-management-as-invesco-liquidated/"),
    ("invesco", "2023-12", "liquidation by the Official Receiver", "https://www.capitalfm.co.ke/business/2023/12/xplico-insurance-placed-under-statutory-management-as-invesco-liquidated/"),
    ("trident", "2026-03", "statutory management", "https://x.com/ira_kenya/status/2031600557375344841"),
    ("corporate", "2026-03", "statutory management", "https://x.com/ira_kenya/status/2031600557375344841"),
]

# listings that are not distress: explained so they are not read as warning signs
NOTES = {("sanlam_general", 2025): "business transferred to Jubilee Allianz, now Sanlam Allianz General",
         ("sanlam_allianz_general", 2024): "IRA printed zeros for Jubilee Allianz General in every 2024 quarter; a gap in IRA's tables, cause not known"}

pan = pd.read_csv(os.path.join(DATA, "data", "processed", "general_revenue_panel.csv"))
sc = pd.read_csv(os.path.join(OUT, "cedant_scorecard.csv"))
met = pd.read_csv(os.path.join(OUT, "cedant_metrics.csv"))
ins = pan[(pan.segment == "insurer") & (pan.line == "gross_direct_premium")]
years = sorted(sc.year.unique())
rows = []
for y in years:
    listed = ins[ins.year == y]
    scored = set(sc[sc.year == y].company_id)
    for cid, g in listed.groupby("company_id"):
        if cid in scored:
            continue
        q4 = g[g.quarter == 4]
        mm = met[(met.company_id == cid) & (met.year == y)]
        filed_q = sorted(g[g.quarter_basis != "not_filed"].quarter.unique())
        if mm.empty or q4.empty or (q4.quarter_basis == "not_filed").all():
            reason = "no full-year return" + (f" (filed Q{', Q'.join(map(str, filed_q))} only)" if filed_q else " (no returns filed all year)")
        elif int(mm.is_micro.iloc[0]) == 1:
            reason = "micro insurer"
        else:
            reason = f"below KSh 500m written premium ({mm.written_premium.iloc[0]:,.0f}m)"
        note = NOTES.get((cid, y), "")
        rows.append(dict(year=y, company_id=cid, reason=reason, note=note))
ns = pd.DataFrame(rows)
ns.to_csv(os.path.join(OUT, "not_scored.csv"), index=False, lineterminator="\n")

bt = []
for cid, when, what, src in FAILURES:
    ev_year = int(when[:4])
    hist = sc[(sc.company_id == cid) & (sc.year < ev_year)].sort_values("year")
    last = hist.iloc[-1] if len(hist) else None
    later = ns[(ns.company_id == cid) & (ns.year < ev_year) & ((last is None) | (ns.year > (last.year if last is not None else 0)))]
    bt.append(dict(company_id=cid, event=what, event_date=when, source=src,
                   last_scored_year=None if last is None else int(last.year),
                   grade=None if last is None else last.grade,
                   rank=None if last is None else f"{int(last['rank'])} of {int(last.peers)}",
                   bottom_quintile=None if last is None else bool(last["rank"] > 0.8 * last.peers),
                   grades_history=" ".join(f"{int(r.year)}:{r.grade}" for r in hist.itertuples()),
                   after_last_score="; ".join(f"{int(r.year)} {r.reason}" for r in later.itertuples())))
bt = pd.DataFrame(bt)
bt.to_csv(os.path.join(OUT, "backtest.csv"), index=False, lineterminator="\n")
pd.set_option("display.width", 250); pd.set_option("display.max_colwidth", 120)
print(bt.drop(columns="source").to_string(index=False))
print(); print(ns[ns.year >= 2023].to_string(index=False))
