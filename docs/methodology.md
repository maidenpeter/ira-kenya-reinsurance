# Methodology

## Data

Full-year figures from IRA's quarterly industry statistics: the Q4 year-to-date general business revenue account, the 31 December general business balance sheet and profit and loss account, and the gross premium by class. All come from `ira-kenya-data`, which validates them before they reach this repo. 2017 is missing because IRA's Q4 2017 workbook is not online.

## Peer group

General insurers only: no reinsurers and no micro insurers. A company must have at least KSh 500m of written premium that year. Written premium is gross direct premium plus inward reinsurance. Companies left out, and why, are in `output/not_scored.csv`.

## Metrics

| Metric | Definition | Better when |
|---|---|---|
| capital_cover | Total equity over IRA's minimum capital for a general insurer: the higher of KSh 600m and 20% of net earned premium (Insurance Act capital requirements) | higher |
| liquidity_cover | Cash, term deposits and government securities over insurance liabilities (underwriting provisions and actuarial liabilities under IFRS 4; insurance contract liabilities under IFRS 17) | higher |
| receivables_share | Outstanding premiums and other receivables over total assets. IFRS 4 years only: under IFRS 17 premiums receivable are netted into insurance contract liabilities, most insurers report almost no receivables, and the ratio no longer measures credit exposure. From 2024 the balance sheet pillar rests on capital and liquidity. | lower |
| combined_ratio_3y | Mean of the last three full-year net combined ratios: claims, commissions and management expenses over net earned premium. Each year is capped at 300% so one tiny year cannot dominate | lower |
| loss_ratio_volatility_5y | Standard deviation of the net loss ratio over up to five full years, with at least three needed | lower |
| return_on_equity_3y | Mean of profit after tax over equity over the last three years. A company with negative equity takes the bottom rank | higher |
| scale | Log of written premium | higher |
| diversification | 1 minus the Herfindahl index of gross premium across IRA's 14 classes | higher |
| retention | Net premium written over written premium. A cedant that keeps little of its own business has little at stake in how it performs | higher |
| reliability | 100 less 30 for each error, 10 for each warning and 10 for each missed filing in `ira-kenya-data`'s quality flags over the last three years, floored at 0 | higher |

"The last three years" means the three calendar years to date. Because 2017 is missing, 2018 and 2019 use fewer years.

## Scoring

1. Each metric except reliability is turned into a percentile rank within the year's peer group, with direction applied. Reliability is already on a 0 to 100 scale and is used as it is.
2. Pillar score: the weighted mean of its metrics' percentiles. A missing metric is left out of the average.
3. Total score: the weighted mean of the pillars, with balance sheet 35, operating performance 35, business profile 15 and return quality 15.
4. Grade: A 70+, B 55 to 70, C 40 to 55, D 25 to 40, E under 25.
5. Cap: negative equity, or equity below the capital floor, caps the grade at D.

The weights mirror the rating-agency view that balance sheet strength and operating performance carry most of the weight, with business profile and risk management as adjustments (Best's Credit Rating Methodology).

## Sensitivity

The scorecard is rerun with equal metric weights and with equal pillar weights. `output/sensitivity.csv` gives the rank correlation with the base case and how many grades change, by year.

## Back-test

Five insurers were placed under statutory management or liquidation between 2022 and 2026. Each is checked against its last scorecard before the regulator acted (`output/backtest.csv`, with sources). This is a sanity check, not a validated early-warning model. The sample is small, and false positives, meaning low grades for insurers that carried on, cannot be measured this way.

## Limits

- IRA's figures are unaudited quarterly returns.
- Equity stands in for the risk-based capital adequacy ratio, which IRA does not publish per company. Cross-check: IRA reported 15 of 35 general insurers short of required capital at December 2023 (Business Daily, 8 December 2024, https://www.businessdailyafrica.com/bd/corporate/companies/eyes-on-ira-as-23-insurers-breach-minimum-capital-position-4850574). The equity floor flags 9 of 34 in 2023, so it understates capital shortfalls.
- The capital floor uses the current rule for every year. The risk-based part of Kenya's capital regime was postponed to 30 June 2020 (Bowmans, 30 June 2017, https://bowmanslaw.com/insights/key-amendments-insurance-act-cap-487/), so for 2016 to 2019 the floor is stricter than the rule then in force. It caps six grades in those years (AAR 2018, Monarch 2016 and 2018, Saham 2016, Takaful 2018 and 2019) and none of the back-test grades.
- The balance sheet is the general business return. For composite insurers it covers the general fund only.
- The IFRS 17 switch from Q1 2024 changes the balance sheet lines. Ranking within each year keeps comparisons like for like, but levels before and after 2024 should not be compared directly.
