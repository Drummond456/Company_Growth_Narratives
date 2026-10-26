# Why Costco (COST)'s PVGO share moved: January 2024 to December 2024

### How each month is split

Each month opens with its bridge: the growth-share change (PVGO / price, in pp) split exactly into the price's **market** part (S&P 500 and sector) and its **company-specific** part, the **EPS update** at an earnings release, and the cost of equity's **rates**. Then its timeline: the month cut into consecutive periods by code (a day at least 2.5x its normal company-specific move alone, the rest in swings of the price-driven path), each labelled by how much of its price move the market explains:

- **market-driven:** the market explains 70% or more;
- **within noise:** less than that, but the company-specific move is under 1.5x its normal size over that many days;
- **divergent:** the market explains 30%-70%, and the company-specific move stands out;
- **outlier:** the market explains 30% or less, and the company-specific move stands out.

### How each period is explained

Every period is explained the same way: one call reads the period's news (from the day before to the day after) and the stock's own daily moves, without the market's figures or the label, and names the change in expectations that most likely caused the move, with its confidence. A cause is the model's reading of the news, not a tested fact, and its confidence is the model's own: the placebo check below is the test of how often it finds causes that aren't there. The labels are computed.

### Citations

Each cause ends with the refs it cites, in brackets: `A0077-S01` is a statement, `A0077-H` a headline, and a bare `A0065` an analyst article read as headline plus opening, from the month's run (a ref from another month starts with its `YYYY-MM/`). Dates are written out; refs keep their own form.

### Findings and the placebo check

44 periods, 12 months, 4 earnings releases, from 12 runs.

| Label | Periods | Cause found, medium or high confidence | Answers |
|---|---|---|---|
| market-driven (suspect if explained) | 7 | 0 | no cause found 7 |
| within noise (suspect if explained) | 27 | 1 | medium confidence 1, low confidence 3, no cause found 23 |
| divergent | 2 | 0 | no cause found 2 |
| outlier | 8 | 2 | medium confidence 2, low confidence 1, no cause found 4, no news collected 1 |

**Placebo check:** in the 34 market-driven or within-noise periods with news, the period call found a cause with medium or high confidence in 1; in the 9 divergent or outlier periods, in 2. The news is company-specific, so a cause where the market explains the move, or where the company-specific move is ordinary noise, is suspect: the first count is how often the explanations find causes that aren't there.

### Earnings releases

Each earnings release has a block after the period holding its measurement day: the EPS change and the quarters behind it (filings); the one-time items the press releases name, entering or leaving the TTM, and the change less them (the release call extracts the items, code checks each amount against the press-release text and does the arithmetic; each block cites the press releases, `R` and the release date); and the market reaction, by code: a **results surprise** when the company-specific stock return from the release to the measurement day is at least 1.5x its normal size over those days, else **results expected**.

Levels: the growth share's level depends on the EPS basis. One-time charges kept in the TTM lower the EPS and raise the growth share for the four quarters they're in (the Release blocks name those the press releases name), so compare levels across years or companies with them in mind.

| Release | Growth-share effect of the EPS update (pp, price held still) | Company-specific stock return, release to measurement day (%) |
|---|---|---|
| March 7, 2024 | -1.07 | -6.4 |
| May 30, 2024 | -1.24 | +0.1 |
| September 26, 2024 | -0.61 | -2.7 |
| December 12, 2024 | -0.55 | -0.1 |

### Settings

EPS basis: Adjusted TTM EPS; cost of equity: 10-year Treasury + own beta (60 monthly returns vs the S&P 500, Blume-adjusted) x a fixed ERP of 4.60%; market model: S&P 500 + RSPS; statements: Qwen/Qwen3-235B-A22B-Instruct-2507; explanations: claude-sonnet-5-5, collected October 26, 2026 04:53 UTC.

## January 2024: growth share 71.3% -> 73.4% (+2.14pp)

| Part | pp |
|---|---|
| Price: market (S&P 500 and sector) | +0.22 |
| Price: company-specific | +1.18 |
| Rates: 10-year Treasury | +0.67 |
| Rates: beta re-estimate | +0.07 |
| **Total** | **+2.14** |

- **P01 January 2–3, 2024 (2 days) · within noise** · stock -2.3% (S&P -1.4%, RSPS +0.3%) · market -0.19pp, company-specific -0.49pp (the market explains 28%; 1.0x normal noise) · **no cause found** (3 statements)
- **P02 January 4–18, 2024 (10 days) · outlier** · stock +6.4% (S&P +1.6%, RSPS -1.3%) · market +0.19pp, company-specific +1.60pp (the market explains 10%; 1.6x normal noise) · **no cause found** (13 statements, 2 articles)
- **P03 January 19–25, 2024 (5 days) · within noise** · stock -1.1% (S&P +2.4%, RSPS -0.4%) · market +0.36pp, company-specific -0.65pp (the market explains 36%; 0.9x normal noise) · **no cause found** (13 statements, 3 articles)
- **P04 January 26–31, 2024 (4 days) · within noise** · stock +2.2% (S&P -1.0%, RSPS +0.5%) · market -0.14pp, company-specific +0.72pp (the market explains 16%; 1.2x normal noise) · big market day: S&P -1.6%, 2.5x normal on January 31, 2024 · **no cause found** (9 statements)

## February 2024: growth share 73.4% -> 75.7% (+2.24pp)

| Part | pp |
|---|---|
| Price: market (S&P 500 and sector) | +0.93 |
| Price: company-specific | +0.80 |
| Rates: 10-year Treasury | +0.44 |
| Rates: beta re-estimate | +0.07 |
| **Total** | **+2.24** |

- **P05 February 1–14, 2024 (10 days) · within noise** · stock +3.9% (S&P +3.2%, RSPS -1.2%) · market +0.48pp, company-specific +0.52pp (the market explains 48%; 0.6x normal noise) · **no cause found** (18 statements, 8 articles)
- **P06 February 15–29, 2024 (10 days) · within noise** · stock +3.0% (S&P +1.9%, RSPS +3.2%) · market +0.45pp, company-specific +0.28pp (the market explains 62%; 0.4x normal noise) · big market day: S&P +2.1%, 3.3x normal on February 22, 2024 · **no cause found** (11 statements, 1 article)

## March 2024: growth share 75.7% -> 74.2% (-1.50pp)

| Part | pp |
|---|---|
| Price: market (S&P 500 and sector) | +0.68 |
| Price: company-specific | -1.06 |
| EPS update: release March 7, 2024 | -1.07 |
| Rates: 10-year Treasury | +0.04 |
| Rates: beta re-estimate | -0.08 |
| **Total** | **-1.50** |

- **P07 March 1–7, 2024 (5 days) · outlier** · stock +5.5% (S&P +1.2%, RSPS +1.0%) · market +0.22pp, company-specific +1.08pp (the market explains 17%; 2.0x normal noise) · **no cause found** (27 statements, 4 articles)
- **P08 March 8, 2024 · outlier** · stock -7.6% (S&P -0.7%, RSPS +0.1%) · market -0.10pp, company-specific -1.83pp (the market explains 5%; 7.0x normal noise) · **medium confidence** (25 statements, 2 articles) · Cause: Costco missed second-quarter revenue expectations, with gasoline price deflation dragging reported comparable sales, and signaled price cuts on several items. The market read this as softer top-line growth and possible pressure on margins, and the shares had their worst day since May 2022. An EPS beat, 5.8% comparable sales growth excluding gas and FX, and strong membership growth did not offset the miss on a richly valued stock. [A0073-H, A0077-S01, A0077-S02, A0081-S01, A0076]

<div class="release">

**Release March 7, 2024** · quarter ended February 18, 2024 · in P07, P08 [R2024-03-07]

*TTM EPS change*

- +$0.62 (14.67 -> 15.29): the quarter ended February 18, 2024 ($3.92) replaces the one ended February 12, 2023 ($3.30); growth-share effect -1.07pp (price held still)

*One-time items identified*

- Entering: Tax benefit from deductibility of special dividend to 401(k) participants, benefit $0.21 (+0.21 to the step)
- TTM EPS change less one-time items: +$0.41

*Market reaction*

- Results surprise: company-specific stock return -6.4% over 2 trading days (March 7, 2024 +0.9%, March 8, 2024 -7.3%), against the market model, 4.3x normal noise

</div>

- **P09 March 11, 2024 · within noise** · stock -1.6% (S&P -0.1%, RSPS +0.9%) · market +0.01pp, company-specific -0.44pp (the market explains 3%; 1.2x normal noise) · **no cause found** (1 statement, 2 articles)
- **P10 March 12–25, 2024 (10 days) · within noise** · stock +2.4% (S&P +2.0%, RSPS -0.3%) · market +0.36pp, company-specific +0.25pp (the market explains 58%; 0.2x normal noise) · **no cause found** (31 statements, 7 articles) · No new company-specific information in this period. The statements recycle the March 7 Q2 results (comps accelerating to 5.6%, membership fees up 8%, 93% renewal rate, store openings). The one new item, the BMO price target raise to $800, is a modest analyst update. The +3.2% jump on March 12 looks like a rebound after the 7.4% post-earnings drop, not a change in fundamentals. The rest of the period was flat, so the +2.4% net is within normal noise. [A0065, A0066]
- **P11 March 26–28, 2024 (3 days) · within noise** · stock +0.2% (S&P +0.7%, RSPS +2.0%) · market +0.18pp, company-specific -0.13pp (the market explains 60%; 0.2x normal noise) · **no cause found** (6 statements, 1 article)

## April 2024: growth share 74.2% -> 75.0% (+0.82pp)

| Part | pp |
|---|---|
| Price: market (S&P 500 and sector) | -0.91 |
| Price: company-specific | +0.55 |
| Rates: 10-year Treasury | +1.17 |
| Rates: beta re-estimate | +0.01 |
| **Total** | **+0.82** |

- **P12 April 1–4, 2024 (4 days) · within noise** · stock -3.8% (S&P -2.0%, RSPS -2.4%) · market -0.47pp, company-specific -0.54pp (the market explains 46%; 0.8x normal noise) · **no cause found** (15 statements, 4 articles) · Only a mild, indirect explanation exists: a Gordon Haskett downgrade from buy to accumulate on April 4 cited near-term uncertainties (rising gas prices, a shorter holiday season), but it came on the last day when the stock was nearly flat (-0.1%), so it does not explain the -3.8% decline over the four days. Other items (the Sesame weight-loss partnership, opinion pieces about margins and growth, local store news) are minor or repeated older information and do not plausibly explain the drop. The move looks like general market or sector weakness or noise. [A0075]
- **P13 April 5–18, 2024 (10 days) · within noise** · stock +0.9% (S&P -2.6%, RSPS -2.0%) · market -0.56pp, company-specific +0.80pp (the market explains 41%; 0.8x normal noise) · **no cause found** (29 statements, 5 articles)
- **P14 April 19–30, 2024 (8 days) · within noise** · stock +1.6% (S&P +0.5%, RSPS +1.7%) · market +0.12pp, company-specific +0.28pp (the market explains 30%; 0.3x normal noise) · **no cause found** (21 statements, 4 articles)

## May 2024: growth share 75.0% -> 76.5% (+1.48pp)

| Part | pp |
|---|---|
| Price: market (S&P 500 and sector) | +0.87 |
| Price: company-specific | +1.84 |
| EPS update: release May 30, 2024 | -1.24 |
| Rates: 10-year Treasury | -0.19 |
| Rates: beta re-estimate | +0.20 |
| **Total** | **+1.48** |

- **P15 May 1, 2024 · within noise** · stock -0.1% (S&P -0.3%, RSPS -1.3%) · market -0.08pp, company-specific +0.06pp (the market explains 58%; 0.2x normal noise) · **no cause found** (6 statements, 1 article)
- **P16 May 2–15, 2024 (10 days) · within noise** · stock +8.7% (S&P +5.6%, RSPS +2.2%) · market +1.09pp, company-specific +0.99pp (the market explains 52%; 1.0x normal noise) · **no cause found** (30 statements, 5 articles)
- **P17 May 16–30, 2024 (10 days) · within noise** · stock +3.6% (S&P -1.4%, RSPS -3.9%) · market -0.31pp, company-specific +1.12pp (the market explains 22%; 1.3x normal noise) · **low confidence** (45 statements, 8 articles) · Cause, suspect in a within noise period: Costco's fiscal Q3 results, reported after the close on May 30, beat expectations on revenue ($58.52B vs ~$58.0B est.), comparable sales (+6.5%) and e-commerce (+20.7%). That supports revenue growth expectations. However, the +1.1% on May 30 came before the report. Most of the period's gain came from drift higher toward all-time highs, with no clear news catalyst, and the post-earnings reaction (a drop on May 31) falls outside the period. The earnings beat itself therefore does not explain the move. [A0009-S01, A0009-S02, A0009-S03, A0010-S02, A0003]
- **P18 May 31, 2024 · within noise** · stock -0.7% (S&P +0.8%, RSPS +2.1%) · market +0.17pp, company-specific -0.32pp (the market explains 35%; 1.2x normal noise) · **low confidence** (15 statements, 2 articles) · Cause, suspect in a within noise period: Costco reported a Q3 beat (revenue $58.52B vs about $58.0B expected, comparable sales +6.5%, e-commerce +20.7%), but the stock had closed at an all-time high before the report. Investors judged the strong quarter already priced in, so the shares slipped, down as much as 3.4% intraday and closing -0.7%. The hot dog price pledge and gold bar sales are not new information. [A0009-S01, A0009-S02, A0010-S01, A0010-S02, A0003]

<div class="release">

**Release May 30, 2024** · quarter ended May 12, 2024 · in P17, P18 [R2024-05-30, R2023-05-25]

*TTM EPS change*

- +$0.85 (15.29 -> 16.14): the quarter ended May 12, 2024 ($3.78) replaces the one ended May 7, 2023 ($2.93); growth-share effect -1.24pp (price held still)

*One-time items identified*

- Leaving: Non-recurring charge to merchandise costs (discontinuation of charter shipping activities), charge $0.50 (+0.50 to the step)
- TTM EPS change less one-time items: +$0.35

*Market reaction*

- Results expected: company-specific stock return +0.1% over 2 trading days (May 30, 2024 +1.6%, May 31, 2024 -1.4%), against the market model, 0.1x normal noise

</div>


## June 2024: growth share 76.5% -> 77.1% (+0.61pp)

| Part | pp |
|---|---|
| Price: market (S&P 500 and sector) | +0.59 |
| Price: company-specific | +0.53 |
| Rates: 10-year Treasury | -0.41 |
| Rates: beta re-estimate | -0.10 |
| **Total** | **+0.61** |

- **P19 June 3–14, 2024 (10 days) · within noise** · stock +5.5% (S&P +2.9%, RSPS -2.9%) · market +0.50pp, company-specific +0.77pp (the market explains 40%; 1.4x normal noise) · **low confidence** (22 statements, 8 articles) · Cause, suspect in a within noise period: Investors kept rewarding Costco's fiscal Q3 results (reported late May, before the period): revenue up 9%, EPS up 29% and a beat of consensus, same-store sales up 6.6%, and share gains in discretionary spending while Walmart and Target noted pullbacks. Management's hint at a future membership-fee increase added to the case. The statements only recap this earnings news and offer commentary, with no new event in the period, so the drift higher is a modest, partly momentum-driven continuation. [A0067-S01, A0067-S02, A0067-S03, A0060-S01, A0060-S02, A0043-S03, A0041-S02, A0062]
- **P20 June 17–28, 2024 (9 days) · within noise** · stock -0.6% (S&P +0.5%, RSPS -0.6%) · market +0.09pp, company-specific -0.24pp (the market explains 26%; 0.4x normal noise) · **no cause found** (19 statements, 2 articles)

## July 2024: growth share 77.1% -> 74.9% (-2.14pp)

| Part | pp |
|---|---|
| Price: market (S&P 500 and sector) | +0.24 |
| Price: company-specific | -1.03 |
| Rates: 10-year Treasury | -1.34 |
| Rates: beta re-estimate | +0.00 |
| **Total** | **-2.14** |

- **P21 July 1–3, 2024 (3 days) · market-driven** · stock +1.5% (S&P +1.4%, RSPS -0.7%) · market +0.26pp, company-specific +0.08pp (the market explains 75%; 0.3x normal noise) · **no cause found** (3 statements, 2 articles)
- **P22 July 5, 2024 · outlier** · stock +2.7% (S&P +0.5%, RSPS +0.5%) · market +0.11pp, company-specific +0.48pp (the market explains 18%; 2.8x normal noise) · **no cause found** (8 statements, 1 article)
- **P23 July 8–10, 2024 (3 days) · within noise** · stock -0.1% (S&P +1.2%, RSPS -0.0%) · market +0.23pp, company-specific -0.27pp (the market explains 47%; 0.9x normal noise) · **no cause found** (22 statements, 1 article)
- **P24 July 11, 2024 · outlier** · stock -4.3% (S&P -0.9%, RSPS +0.6%) · market -0.17pp, company-specific -0.83pp (the market explains 17%; 4.4x normal noise) · **low confidence** (22 statements) · Cause: The stock fell 4.3% on July 11, 2024 despite a positive-looking announcement. Costco raised US and Canada membership fees by about 8% (to $65 and $130) effective Sept. 1, its first hike since 2017, and reported June sales up 7.4%. Fee income is a high-margin source of profit, so the hike should lift operating margins and earnings visibility into 2026. However, the hike had been widely anticipated and the shares had run up, so the move looks like a sell-the-news reaction, with the already-priced-in fee increase and sales failing to add new upside. The statements do not explicitly confirm this reasoning, which makes the cause uncertain. [A0080-S01, A0081-S02, A0083-S01, A0076-S01, A0078-S02, A0073-S01, A0073-S03]
- **P25 July 12–23, 2024 (8 days) · within noise** · stock +0.7% (S&P -0.5%, RSPS +0.5%) · market -0.12pp, company-specific +0.27pp (the market explains 30%; 0.4x normal noise) · **no cause found** (18 statements, 7 articles)
- **P26 July 24–31, 2024 (6 days) · within noise** · stock -3.5% (S&P -0.6%, RSPS +1.1%) · market -0.08pp, company-specific -0.77pp (the market explains 9%; 1.3x normal noise) · big market day: S&P -2.3%, 3.8x normal on July 24, 2024 · **no cause found** (3 statements, 3 articles)

## August 2024: growth share 74.9% -> 77.1% (+2.13pp)

| Part | pp |
|---|---|
| Price: market (S&P 500 and sector) | +0.39 |
| Price: company-specific | +1.59 |
| Rates: 10-year Treasury | -0.00 |
| Rates: beta re-estimate | +0.16 |
| **Total** | **+2.13** |

- **P27 August 1–5, 2024 (3 days) · divergent** · stock -2.5% (S&P -6.2%, RSPS -0.5%) · market -1.45pp, company-specific +0.82pp (the market explains 64%; 1.9x normal noise) · big market day: S&P -1.8%, 2.7x normal on August 2, 2024 · big market day: S&P -3.0%, 4.1x normal on August 5, 2024 · **no cause found** (4 statements, 1 article)
- **P28 August 6–19, 2024 (10 days) · market-driven** · stock +8.6% (S&P +7.9%, RSPS +3.2%) · market +1.69pp, company-specific +0.39pp (the market explains 81%; 0.5x normal noise) · big market day: S&P +2.3%, 2.8x normal on August 8, 2024 · **no cause found** (11 statements, 2 articles) · No clearly new company-specific information explains the +8.6% move. The membership-scanning crackdown (Aug 7) and the fee increase were already announced, so the news mostly repeats older items. The rest is commentary: hedge fund and Cramer bullishness, plus a recap of an earlier earnings beat. The rise likely reflects the broader market rebound after early-August volatility and a rotation into defensive quality names, which these statements do not establish.
- **P29 August 20–30, 2024 (9 days) · within noise** · stock +2.3% (S&P +0.7%, RSPS +0.3%) · market +0.15pp, company-specific +0.39pp (the market explains 28%; 0.6x normal noise) · **no cause found** (13 statements, 7 articles) · No clear new company-specific catalyst. The period's news is mostly recycled commentary (July comps of 5.2%, membership fee pricing power, a routine new warehouse permit filing, Cramer and listicle pieces). The one possible catalyst is an Oppenheimer bullish analyst note on Aug 27, which coincided with a ~1.8% rise but was reversed the next day by a -2.3% drop. The net +2.3% over the period looks like ordinary market and sector drift, not a change in expectations. [A0010]

## September 2024: growth share 77.1% -> 76.1% (-0.94pp)

| Part | pp |
|---|---|
| Price: market (S&P 500 and sector) | +0.38 |
| Price: company-specific | -0.52 |
| EPS update: release September 26, 2024 | -0.61 |
| Rates: 10-year Treasury | -0.18 |
| Rates: beta re-estimate | -0.00 |
| **Total** | **-0.94** |

- **P30 September 3–6, 2024 (4 days) · within noise** · stock -1.7% (S&P -4.3%, RSPS +1.0%) · market -0.92pp, company-specific +0.51pp (the market explains 64%; 1.1x normal noise) · **no cause found** (5 statements, 2 articles)
- **P31 September 9–20, 2024 (10 days) · market-driven** · stock +3.5% (S&P +5.3%, RSPS -0.4%) · market +1.09pp, company-specific -0.29pp (the market explains 79%; 0.4x normal noise) · **no cause found** (11 statements, 3 articles)
- **P32 September 23, 2024 · within noise** · stock +1.1% (S&P +0.3%, RSPS -0.3%) · market +0.06pp, company-specific +0.20pp (the market explains 22%; 0.8x normal noise) · **no cause found** (1 statement, 1 article)
- **P33 September 24–30, 2024 (5 days) · outlier** · stock -3.4% (S&P +0.8%, RSPS +0.5%) · market +0.15pp, company-specific -0.94pp (the market explains 14%; 1.6x normal noise) · **medium confidence** (27 statements, 6 articles) · Cause: Costco reported fiscal Q4 results on Sept. 26 with a small revenue miss ($79.7B vs ~$79.97B), softer big-ticket spending and lower gasoline prices, with same-store sales growth slowing from the prior quarter. A profit beat and a better-than-expected 6.9% comp were offset by a slightly lower renewal rate and port-strike risk. With the stock already at a premium valuation, the miss prompted a modest pullback (Friday down as much as 3% intraday), along with a Truist downgrade on valuation. [A0022-S01, A0018-S01, A0018-S02, A0016-S02, A0020, A0013]

<div class="release">

**Release September 26, 2024** · quarter ended September 1, 2024 · in P33 [R2024-09-26]

*TTM EPS change*

- +$0.42 (16.14 -> 16.56): the quarter ended September 1, 2024 ($5.28) replaces the one ended September 3, 2023 ($4.86); growth-share effect -0.61pp (price held still)

*One-time items identified*

- Entering: Non-recurring tax benefit (transfer pricing settlement and tax reserve true-ups), benefit $0.14 (+0.14 to the step)
- TTM EPS change less one-time items: +$0.28

*Market reaction*

- Results surprise: company-specific stock return -2.7% over 2 trading days (September 26, 2024 -1.1%, September 27, 2024 -1.6%), against the market model, 1.8x normal noise

</div>


## October 2024: growth share 76.1% -> 77.3% (+1.15pp)

| Part | pp |
|---|---|
| Price: market (S&P 500 and sector) | -0.14 |
| Price: company-specific | -0.18 |
| Rates: 10-year Treasury | +1.45 |
| Rates: beta re-estimate | +0.01 |
| **Total** | **+1.15** |

- **P34 October 1–7, 2024 (5 days) · within noise** · stock -1.5% (S&P -1.1%, RSPS -2.7%) · market -0.20pp, company-specific -0.15pp (the market explains 58%; 0.3x normal noise) · **no cause found** (26 statements, 6 articles)
- **P35 October 8–21, 2024 (10 days) · market-driven** · stock +1.6% (S&P +2.8%, RSPS +1.1%) · market +0.55pp, company-specific -0.20pp (the market explains 74%; 0.3x normal noise) · **no cause found** (22 statements, 4 articles)
- **P36 October 22–31, 2024 (8 days) · market-driven** · stock -1.4% (S&P -2.5%, RSPS -3.0%) · market -0.48pp, company-specific +0.16pp (the market explains 75%; 0.3x normal noise) · **no cause found** (16 statements, 3 articles)

## November 2024: growth share 77.3% -> 79.3% (+2.01pp)

| Part | pp |
|---|---|
| Price: market (S&P 500 and sector) | +1.08 |
| Price: company-specific | +1.20 |
| Rates: 10-year Treasury | -0.43 |
| Rates: beta re-estimate | +0.15 |
| **Total** | **+2.01** |

- **P37 November 1–7, 2024 (5 days) · market-driven** · stock +4.5% (S&P +4.6%, RSPS -0.4%) · market +0.88pp, company-specific +0.11pp (the market explains 88%; 0.2x normal noise) · big market day: S&P +2.5%, 3.2x normal on November 6, 2024 · **no cause found** (2 statements, 2 articles)
- **P38 November 8, 2024 · outlier** · stock +3.3% (S&P +0.4%, RSPS +0.7%) · market +0.07pp, company-specific +0.63pp (the market explains 9%; 3.2x normal noise) · **no cause found** (2 statements, 1 article)
- **P39 November 11–20, 2024 (8 days) · within noise** · stock -1.6% (S&P -1.3%, RSPS -1.0%) · market -0.25pp, company-specific -0.11pp (the market explains 69%; 0.2x normal noise) · **no cause found** (3 statements, 1 article)
- **P40 November 21, 2024 · outlier** · stock +3.0% (S&P +0.5%, RSPS +1.0%) · market +0.10pp, company-specific +0.51pp (the market explains 17%; 2.6x normal noise) · **no news collected**
- **P41 November 22–29, 2024 (5 days) · market-driven** · stock +1.7% (S&P +1.4%, RSPS +2.7%) · market +0.28pp, company-specific +0.06pp (the market explains 82%; 0.1x normal noise) · **no cause found** (0 statements, 1 article)

## December 2024: growth share 79.3% -> 78.6% (-0.69pp)

| Part | pp |
|---|---|
| Price: market (S&P 500 and sector) | -0.52 |
| Price: company-specific | -0.70 |
| EPS update: release December 12, 2024 | -0.55 |
| Rates: 10-year Treasury | +0.96 |
| Rates: beta re-estimate | +0.13 |
| **Total** | **-0.69** |

- **P42 December 2–13, 2024 (10 days) · within noise** · stock +1.8% (S&P +0.3%, RSPS -0.6%) · market +0.04pp, company-specific +0.33pp (the market explains 10%; 0.5x normal noise) · **medium confidence** (15 statements, 4 articles) · Cause, suspect in a within noise period: Costco's fiscal Q1 2025 report on Dec 12 was a modest beat that largely confirmed already-high expectations: revenue of $62.15B vs $62.08B expected, comparable sales ex-fuel of 7.2% vs 6.26%, e-commerce up 13%, and paid members up about 8%. Pre-earnings analyst bullishness (robust core trends, stock-split talk) supported a run to record highs. The stock's gain of +1.8% over the period is small, and the tariff caution from management was minor, so the move reflects a mild confirmation of growth and share gains rather than a major change in expectations. [A0015-S01, A0015-S02, A0002-S01, A0002-S02, A0002-S03, A0012-S01, A0001, A0013]

<div class="release">

**Release December 12, 2024** · quarter ended November 24, 2024 · in P42 [R2024-12-12, R2023-12-14]

*TTM EPS change*

- +$0.46 (16.56 -> 17.02): the quarter ended November 24, 2024 ($4.04) replaces the one ended November 26, 2023 ($3.58); growth-share effect -0.55pp (price held still)

*One-time items identified*

- Entering: Tax benefit related to stock-based compensation, benefit $0.22 (+0.22 to the step)
- Leaving: Tax benefit related to stock-based compensation, benefit $0.10 (-0.10 to the step)
- TTM EPS change less one-time items: +$0.34

*Market reaction*

- Results expected: company-specific stock return -0.1% over 2 trading days (December 12, 2024 -0.2%, December 13, 2024 +0.1%), against the market model, 0.1x normal noise

</div>

- **P43 December 16, 2024 · within noise** · stock +0.4% (S&P +0.4%, RSPS -0.9%) · market +0.04pp, company-specific +0.03pp (the market explains 58%; 0.2x normal noise) · **no cause found** (6 statements, 1 article)
- **P44 December 17–31, 2024 (10 days) · divergent** · stock -8.0% (S&P -3.1%, RSPS -4.0%) · market -0.60pp, company-specific -1.06pp (the market explains 36%; 1.8x normal noise) · big market day: S&P -3.0%, 4.5x normal on December 18, 2024 · **no cause found** (14 statements, 1 article)

Batch cost: $0.161.
