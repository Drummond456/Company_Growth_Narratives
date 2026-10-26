# Why Meta Platforms (META)'s PVGO share moved: September 2022 to August 2023

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

90 periods, 12 months, 4 earnings releases, from 12 runs.

| Label | Periods | Cause found, medium or high confidence | Answers |
|---|---|---|---|
| market-driven (suspect if explained) | 29 | 7 | medium confidence 7, low confidence 10, no cause found 11, no news collected 1 |
| within noise (suspect if explained) | 47 | 9 | high confidence 2, medium confidence 7, low confidence 8, no cause found 30 |
| divergent | 6 | 5 | high confidence 3, medium confidence 2, low confidence 1 |
| outlier | 8 | 4 | high confidence 3, medium confidence 1, no cause found 4 |

**Placebo check:** in the 75 market-driven or within-noise periods with news, the period call found a cause with medium or high confidence in 16; in the 14 divergent or outlier periods, in 9. The news is company-specific, so a cause where the market explains the move, or where the company-specific move is ordinary noise, is suspect: the first count is how often the explanations find causes that aren't there.

### Earnings releases

Each earnings release has a block after the period holding its measurement day: the EPS change and the quarters behind it (filings); the one-time items the press releases name, entering or leaving the TTM, and the change less them (the release call extracts the items, code checks each amount against the press-release text and does the arithmetic; each block cites the press releases, `R` and the release date); and the market reaction, by code: a **results surprise** when the company-specific stock return from the release to the measurement day is at least 1.5x its normal size over those days, else **results expected**.

Levels: the growth share's level depends on the EPS basis. One-time charges kept in the TTM lower the EPS and raise the growth share for the four quarters they're in (the Release blocks name those the press releases name), so compare levels across years or companies with them in mind.

| Release | Growth-share effect of the EPS update (pp, price held still) | Company-specific stock return, release to measurement day (%) |
|---|---|---|
| October 26, 2022 | +15.90 | -26.1 |
| February 1, 2023 | +10.72 | +19.1 |
| April 26, 2023 | +2.35 | +12.3 |
| July 26, 2023 | -1.71 | +6.0 |

### Settings

EPS basis: Adjusted TTM EPS; cost of equity: 10-year Treasury + own beta (60 monthly returns vs the S&P 500, Blume-adjusted) x a fixed ERP of 5.09%; market model: S&P 500 + RSPC; statements: Qwen/Qwen3-235B-A22B-Instruct-2507; explanations: claude-sonnet-5-5, collected October 26, 2026 18:59 UTC.

## September 2022: growth share 20.4% -> 11.4% (-8.98pp)

| Part | pp |
|---|---|
| Price: market (S&P 500 and sector) | -19.16 |
| Price: company-specific | +3.73 |
| Rates: 10-year Treasury | +5.91 |
| Rates: beta re-estimate | +0.54 |
| **Total** | **-8.98** |

- **P01 September 1, 2022 · within noise** · stock +1.5% (S&P +0.3%, RSPC +0.0%) · market +0.23pp, company-specific +0.94pp (the market explains 19%; 0.6x normal noise) · **no cause found** (11 statements)
- **P02 September 2–6, 2022 (2 days) · market-driven** · stock -4.2% (S&P -1.5%, RSPC -2.9%) · market -3.60pp, company-specific +0.22pp (the market explains 94%; 0.1x normal noise) · **low confidence** (14 statements) · Cause, suspect in a market-driven period: Two new items point down: the $400 million Irish DPC fine over Instagram's handling of children's privacy (a regulatory cost and risk to the ad model), and continued heavy metaverse spending. The Qualcomm custom-chip deal and the Oct. 11 headset event mean more multi-year VR investment, with Reality Labs losses already widening. The Qualcomm deal is mostly seen as a win for Qualcomm. The fine is small relative to Meta's scale, so the explanation for the move is only partial and the market may also have contributed. [A0001-S01, A0001-S03, A0013-S03, A0004-S02, A0016-S02]
- **P03 September 7–9, 2022 (3 days) · market-driven** · stock +6.6% (S&P +4.0%, RSPC +5.3%) · market +7.14pp, company-specific -2.07pp (the market explains 78%; 0.7x normal noise) · **no cause found** (5 statements)
- **P04 September 12–16, 2022 (5 days) · within noise** · stock -14.0% (S&P -4.8%, RSPC -4.8%) · market -7.85pp, company-specific -3.87pp (the market explains 67%; 1.1x normal noise) · big market day: S&P -4.3%, 3.2x normal on September 13, 2022 · **medium confidence** (13 statements, 1 article) · Cause, suspect in a within noise period: The -9.4% drop on Sept 13 came amid a broad market sell-off and a WSJ report that Instagram Reels is struggling against TikTok, with users spending less than one-tenth of the time TikTok users do. That raised doubts about Meta's ability to win back engagement and ad share. Morgan Stanley flagged declining user engagement trends. Later drift lower came with a South Korea privacy fine and commentary on weak ad targeting and competition, mostly older news. [A0005, A0008-S02, A0024-S02, A0008-S03]
- **P05 September 19, 2022 · within noise** · stock +1.2% (S&P +0.7%, RSPC +0.0%) · market +0.48pp, company-specific +0.52pp (the market explains 48%; 0.3x normal noise) · **no cause found** (6 statements)
- **P06 September 20–27, 2022 (6 days) · market-driven** · stock -9.5% (S&P -6.7%, RSPC -9.9%) · market -14.24pp, company-specific +5.79pp (the market explains 71%; 1.4x normal noise) · **low confidence** (33 statements, 1 article) · Cause, suspect in a market-driven period: No clear company-specific negative catalyst explains the decline. The WSJ report of a 10%+ cost cut was arguably positive for margins (Morgan Stanley applauded it), yet the stock fell 2.7% on that day. The decline over the rest of the period came alongside minor legal and regulatory items (the $174.5M Voxer verdict, Italy's privacy request, the Molly Russell inquest) that are too small to explain a 9.5% drop. It looks mostly like a market-wide selloff, with the cost-cut report hinting at weak underlying business conditions. [A0006-S01, A0006-S02, A0033-S02, A0007]
- **P07 September 28, 2022 · market-driven** · stock +5.4% (S&P +2.0%, RSPC +3.3%) · market +4.48pp, company-specific +0.12pp (the market explains 97%; 0.1x normal noise) · **no cause found** (29 statements)
- **P08 September 29–30, 2022 (2 days) · market-driven** · stock -4.2% (S&P -3.6%, RSPC -3.3%) · market -5.79pp, company-specific +2.06pp (the market explains 74%; 0.9x normal noise) · **medium confidence** (26 statements) · Cause, suspect in a market-driven period: Zuckerberg announced a company-wide hiring freeze, budget cuts and restructuring, with the CFO citing slower revenue growth than anticipated at the start of the year. Investors read this as an admission that ad revenue growth is slowing amid competition for user attention, and the news also suggests the cuts reach teams the company was recently investing in. [A0060-S01, A0060-S02, A0061-H, A0062-S01, A0062-S02, A0063-S03, A0070-S01, A0070-S02]

## October 2022: growth share 11.4% -> -12.3% (-23.67pp)

| Part | pp |
|---|---|
| Price: market (S&P 500 and sector) | +10.81 |
| Price: company-specific | -49.75 |
| EPS update: release October 26, 2022 | +15.90 |
| Rates: 10-year Treasury | +2.34 |
| Rates: beta re-estimate | -2.98 |
| **Total** | **-23.67** |

- **P09 October 3, 2022 · divergent** · stock +2.2% (S&P +2.6%, RSPC +2.7%) · market +4.38pp, company-specific -2.51pp (the market explains 64%; 1.6x normal noise) · **low confidence** (13 statements) · Cause: Investors raised expectations for cost discipline and ad monetization: Meta is backing out of a large New York office deal while slowing hiring, cutting headcount and budgets, and BofA argues there is room to cut expenses, which would lift earnings. Instagram's planned increase in ad load adds a revenue lever. These items are dated just after the move day, so the link to the +2.2% is only partial, and the same-day items (SideQuest funding, scraping settlement) are minor. [A0001-S01, A0035-S01, A0035-S02, A0107-S01, A0107-S02]
- **P10 October 4, 2022 · divergent** · stock +1.2% (S&P +3.1%, RSPC +3.8%) · market +5.57pp, company-specific -4.54pp (the market explains 55%; 3.0x normal noise) · **medium confidence** (13 statements) · Cause: Signs of cost discipline and new ad monetization: BofA argued Meta has room to cut expenses (up over $50B since 2020, with Alphabet) to boost earnings, Meta backed out of a large New York office deal while slowing hiring, cutting headcount and budgets, and Instagram is raising ad load with new ad placements to counter declining ad sales. [A0001-S01, A0035-S01, A0035-S02, A0107-S01, A0107-S02]
- **P11 October 5–12, 2022 (6 days) · market-driven** · stock -9.4% (S&P -5.8%, RSPC -6.2%) · market -9.82pp, company-specific +1.30pp (the market explains 88%; 0.3x normal noise) · **medium confidence** (49 statements, 1 article) · Cause, suspect in a market-driven period: Meta fell about 9% as a downgrade on 10/11 warned of ongoing downside risk to earnings, because cost cuts look harder than expected and decremental margins are high. That came alongside reports of quiet layoffs and cancelled job offers, the $1,500 Quest Pro launch with its heavy metaverse spending, and Russia's 'extremist' designation. The 10/7 drop came on a hawkish jobs report, with yields up and stocks down, which is broad market pressure. It happened despite the Citi bullish note on Reels. [A0004-S02, A0005-S01, A0042-S01, A0058-S01, A0058-S03, A0046-S01, A0002, A0003-S01]
- **P12 October 13, 2022 · within noise** · stock +2.2% (S&P +2.6%, RSPC +2.6%) · market +4.35pp, company-specific -2.36pp (the market explains 65%; 1.4x normal noise) · **no cause found** (15 statements)
- **P13 October 14, 2022 · market-driven** · stock -2.7% (S&P -2.4%, RSPC -1.6%) · market -3.27pp, company-specific +0.74pp (the market explains 82%; 0.4x normal noise) · **low confidence** (12 statements) · Cause, suspect in a market-driven period: Meta fell 2.7% as reports surfaced of heavy metaverse spending (over $15 billion since early last year, with unclear returns) and an FTC challenge to its VR acquisitions. The Horizon Worlds user-shortfall report is dated after the move, so it can't explain it. The market was also broadly weak that day, so much of the decline may be market-driven. [A0058-S01, A0058-S03, A0057-S01, A0110-S02]
- **P14 October 17, 2022 · within noise** · stock +5.7% (S&P +2.6%, RSPC +1.9%) · market +3.52pp, company-specific +1.55pp (the market explains 69%; 0.9x normal noise) · **no cause found** (15 statements)
- **P15 October 18–24, 2022 (5 days) · divergent** · stock -3.3% (S&P +3.2%, RSPC +3.0%) · market +4.69pp, company-specific -7.59pp (the market explains 38%; 2.2x normal noise) · **medium confidence** (30 statements, 2 articles) · Cause: Meta slid about 3% as read-through from Snap's revenue miss and warning (Oct 20-21) raised fears of weaker digital ad spending ahead of Meta's earnings. Added pressure came from the UK order to sell Giphy, the Altimeter open letter criticizing metaverse spending and headcount, and a Bank of America downgrade citing ad pressure and metaverse overhang. [A0073-S03, A0011-S02, A0012-S01, A0077-S01, A0113, A0008-S01, A0082-S02]
- **P16 October 25, 2022 · within noise** · stock +6.0% (S&P +1.6%, RSPC +2.5%) · market +3.35pp, company-specific +1.77pp (the market explains 66%; 1.2x normal noise) · **medium confidence** (39 statements, 3 articles) · Cause, suspect in a within noise period: Activist investor Brad Gerstner (Altimeter) published an open letter on Oct 24 urging Meta to cut headcount by 20%, trim capex by $5B and limit Reality Labs spending to $5B a year. This raised hopes of tighter cost discipline and less metaverse spending, and the stock rebounded about 6% on the day. Alphabet's weak ad results the same day were a headwind, but the investor-pressure story is the plausible driver. [A0012-S01, A0077-S01, A0114-S02, A0114-S03, A0113]
- **P17 October 26, 2022 · outlier** · stock -5.6% (S&P -0.7%, RSPC -0.9%) · market -1.29pp, company-specific -3.78pp (the market explains 26%; 2.4x normal noise) · **medium confidence** (61 statements, 7 articles) · Cause: The -5.6% move on October 26, 2022 came before Meta's earnings were released after the close. It most plausibly reflects the read-through from Alphabet's disappointing results and ad spending slowdown on October 25, 2022, which stoked fears of weak Meta earnings. The Q3 results and weak Q4 guidance hit in after-hours trading and the following day, so they do not explain this day's move. [A0082-S01, A0082-S02, A0017-S01, A0017-S02, A0018-S02]
- **P18 October 27, 2022 · outlier** · stock -24.6% (S&P -0.6%, RSPC -1.8%) · market -3.10pp, company-specific -26.53pp (the market explains 10%; 12.1x normal noise) · **high confidence** (65 statements, 6 articles) · Cause: Meta's Q3 report and guidance disappointed: Q4 revenue guidance of $30-32.5B was below the ~$32.2B expected, and revenue fell 4% for a second straight quarterly decline. Costs rose 19%, operating margin fell sharply, and 2023 expense growth of about 13% was guided against a Street forecast of 7%. Management also said Reality Labs losses would grow significantly in 2023 after a Q3 loss of $3.67B against $3.09B expected. Analysts downgraded the stock, citing higher operating and capital expenses. [A0015-S01, A0015-S02, A0015-S03, A0083-S01, A0083-S03, A0022-S02, A0092-H, A0104-S02, A0104-S03, A0105-S01, A0105-S03, A0024]

<div class="release">

**Release October 26, 2022** · quarter ended September 30, 2022 · in P17, P18 [R2022-10-26, R2021-10-25]

*TTM EPS change*

- -$1.58 (12.04 -> 10.46): the quarter ended September 30, 2022 ($1.64) replaces the one ended September 30, 2021 ($3.22); growth-share effect +15.90pp (price held still)

*One-time items identified*

- Entering: Impairment loss for certain operating leases, charge $413M pre-tax, about $0.12 per share (-0.12 to the step; estimated: less 25% tax, over the quarter's 2.69B diluted shares)
- TTM EPS change less one-time items: -$1.46 (estimated: some items are stated in dollars only)

*Market reaction*

- Results surprise: company-specific stock return -26.1% over 2 trading days (October 26, 2022 -4.2%, October 27, 2022 -22.0%), against the market model, 10.2x normal noise

</div>

- **P19 October 28, 2022 · within noise** · stock +1.3% (S&P +2.5%, RSPC +2.1%) · market +3.88pp, company-specific -2.54pp (the market explains 60%; 0.7x normal noise) · **no cause found** (40 statements, 5 articles)
- **P20 October 31, 2022 · within noise** · stock -6.1% (S&P -0.7%, RSPC -0.8%) · market -1.45pp, company-specific -5.25pp (the market explains 22%; 1.4x normal noise) · **low confidence** (6 statements) · Cause, suspect in a within noise period: Meta fell 6.1% as investors kept reacting to the post-earnings worry that heavy metaverse spending will keep pressuring returns. Statement 3 says the metaverse spending is the biggest weight on the stock after a 72% decline this year, and investors want less Zuckerberg-driven spending. Nothing in the statements is a new event dated within the period. [A0122-S01]

## November 2022: growth share -12.3% -> 4.6% (+16.86pp)

| Part | pp |
|---|---|
| Price: market (S&P 500 and sector) | +4.82 |
| Price: company-specific | +20.21 |
| Rates: 10-year Treasury | -5.81 |
| Rates: beta re-estimate | -2.36 |
| **Total** | **+16.86** |

- **P21 November 1, 2022 · within noise** · stock +2.2% (S&P -0.4%, RSPC +0.2%) · market +0.29pp, company-specific +2.12pp (the market explains 12%; 0.6x normal noise) · **no cause found** (10 statements)
- **P22 November 2–3, 2022 (2 days) · market-driven** · stock -6.7% (S&P -3.6%, RSPC -5.5%) · market -10.68pp, company-specific +2.84pp (the market explains 79%; 0.5x normal noise) · **medium confidence** (13 statements) · Cause, suspect in a market-driven period: Continued fallout from Meta's late-October earnings: a second straight quarterly sales decline, weak Q4 guidance below expectations, and Zuckerberg doubling down on metaverse spending (~$15B a year, Reality Labs losing $9.4B so far in 2022). Investors want milestones and see heavy investment with no clear payoff. The period's own news is mostly commentary on that earlier report, plus minor items such as Facebook News changes and an India head departure. [A0024-S01, A0002-S02, A0002-S03]
- **P23 November 4–8, 2022 (3 days) · within noise** · stock +8.4% (S&P +2.9%, RSPC +1.2%) · market +2.77pp, company-specific +6.68pp (the market explains 29%; 1.0x normal noise) · **high confidence** (78 statements, 6 articles) · Cause, suspect in a within noise period: A Wall Street Journal report over the weekend said Meta would begin large-scale layoffs of thousands of workers this week, the first major headcount reduction in its history. Investors read it as management finally acting on out-of-control costs after weak Q3 results and Q4 guidance, with spending on the metaverse a key worry. The report pointed to lower expenses (Bloomberg Intelligence estimated $3-4B of opex cuts toward the low end of the $96-101B guidance) and a more disciplined investment stance. The stock jumped 6.5% on Monday, and the other days' moves were small. [A0003-S01, A0005-S01, A0007-S01, A0031-S02, A0006, A0007-S02]
- **P24 November 9, 2022 · divergent** · stock +5.2% (S&P -2.1%, RSPC -2.5%) · market -4.65pp, company-specific +10.25pp (the market explains 31%; 2.7x normal noise) · **high confidence** (63 statements, 4 articles) · Cause: Meta announced layoffs of about 13% of its workforce (11,000+), a hiring freeze through Q1, and lowered 2023 expense guidance by about $2B and the top end of 2023 capex by $2B. Analysts (UBS, JPMorgan, Jefferies) read this as a pivot toward cost discipline and capital efficiency. JPMorgan estimated ~$8B in annual savings and Jefferies a minimum 8% boost to FY23 EPS. Reality Labs losses were still expected to grow significantly in 2023, which limited the upside. [A0010-S01, A0010-S02, A0010-S03, A0049-S01, A0049-S02, A0053-S02, A0054-S01, A0019-S02, A0044-S02]
- **P25 November 10–15, 2022 (4 days) · market-driven** · stock +14.8% (S&P +6.4%, RSPC +8.6%) · market +13.90pp, company-specific +0.63pp (the market explains 96%; 0.1x normal noise) · big market day: S&P +5.5%, 3.5x normal on November 10, 2022 · **medium confidence** (60 statements, 4 articles) · Cause, suspect in a market-driven period: Meta announced layoffs of about 13% of staff (11,000+ employees) on Nov 9, plus an extended hiring freeze, lower 2023 expense guidance (about $1-2B off), capex range cut by $2B at the top end, and a reduced real estate footprint. Investors read this as a pivot toward cost discipline and capital efficiency. Analysts (Jefferies: at least 8% boost to FY23 EPS; JPMorgan: about $8B annual cost savings; UBS: the company 'gets it') endorsed it, and the rally continued into the following days (+10.2% on Nov 10). [A0010-S01, A0010-S02, A0010-S03, A0019-S02, A0040-S03, A0049-S01, A0049-S02, A0053-S02, A0054-S01, A0013]
- **P26 November 16–21, 2022 (4 days) · within noise** · stock -6.3% (S&P -1.0%, RSPC -2.6%) · market -3.90pp, company-specific -2.35pp (the market explains 62%; 0.3x normal noise) · **no cause found** (25 statements)
- **P27 November 22–23, 2022 (2 days) · within noise** · stock +2.2% (S&P +1.9%, RSPC +2.9%) · market +4.70pp, company-specific -2.53pp (the market explains 65%; 0.5x normal noise) · **no cause found** (8 statements)
- **P28 November 25–28, 2022 (2 days) · market-driven** · stock -3.1% (S&P -1.6%, RSPC -1.8%) · market -3.11pp, company-specific -0.09pp (the market explains 97%; 0.0x normal noise) · **no news collected**
- **P29 November 29–30, 2022 (2 days) · within noise** · stock +8.5% (S&P +2.9%, RSPC +3.5%) · market +5.51pp, company-specific +2.67pp (the market explains 67%; 0.5x normal noise) · **low confidence** (9 statements) · Cause, suspect in a within noise period: Investors appear to have been reassured by signs of cost discipline and spending focus: Meta is subleasing and exiting New York office space as part of its cost-cutting, and Zuckerberg said 80% of investment still goes to the core social media business, not the metaverse. The day's +7.9% jump is larger than this news alone would justify (the lease cuts and layoffs were already known), so part of the move likely reflects broader market strength not described in these statements. [A0022-S01, A0073-S01, 2022-12/A0008-S01, 2022-12/A0008-S02]

## December 2022: growth share 4.6% -> 8.8% (+4.24pp)

| Part | pp |
|---|---|
| Price: market (S&P 500 and sector) | -10.89 |
| Price: company-specific | +12.60 |
| Rates: 10-year Treasury | +3.20 |
| Rates: beta re-estimate | -0.66 |
| **Total** | **+4.24** |

- **P30 December 1–2, 2022 (2 days) · within noise** · stock +4.5% (S&P -0.2%, RSPC +0.6%) · market +0.69pp, company-specific +3.48pp (the market explains 16%; 0.7x normal noise) · **low confidence** (9 statements) · Cause, suspect in a within noise period: Continued cost-cutting: Meta is not renewing leases at 30 and 55 Hudson Yards and is subleasing part of 50 Hudson Yards, on top of the 13% layoffs, reinforcing a leaner cost base. Zuckerberg's comment that 80% of investment goes to the core business, not the metaverse, also eased worries about spending. Most of this repeats earlier announced restructuring, so it only partly explains the move and the market was likely also rising. [2022-11/A0022-S01, 2022-11/A0022-S02, 2022-11/A0073-S01, A0008-S01, A0008-S02]
- **P31 December 5–7, 2022 (3 days) · market-driven** · stock -7.8% (S&P -3.4%, RSPC -5.0%) · market -7.63pp, company-specific +0.01pp (the market explains 100%; 0.0x normal noise) · **low confidence** (26 statements) · Cause, suspect in a market-driven period: The -6.8% drop on Dec 6 coincides with Meta's public warning that it could pull all news from Facebook in the US if Congress passes a bill forcing it to pay publishers, plus an Oversight Board critique of the cross-check program (32 recommendations). These are regulatory/legal pressures, mainly the news-bill threat, though their financial impact is small and the size of the drop is not clearly explained. Severance disputes and H-1B layoff stories are minor reputational noise. The FTC trial coverage on Dec 8 came after the move. [A0013-S01, A0013-S02, A0036-S01, A0036-S02, A0036-S03]
- **P32 December 8–9, 2022 (2 days) · within noise** · stock +1.7% (S&P +0.0%, RSPC +0.7%) · market +0.93pp, company-specific +0.74pp (the market explains 56%; 0.1x normal noise) · **no cause found** (14 statements)
- **P33 December 12, 2022 · within noise** · stock -1.0% (S&P +1.4%, RSPC +1.3%) · market +2.20pp, company-specific -3.20pp (the market explains 41%; 0.9x normal noise) · **no cause found** (6 statements)
- **P34 December 13–14, 2022 (2 days) · within noise** · stock +5.9% (S&P +0.1%, RSPC +0.0%) · market +0.06pp, company-specific +5.47pp (the market explains 1%; 1.1x normal noise) · **no cause found** (13 statements) · The statements contain no plausible cause for the +5.9% rise. The items cover VA recruiting of laid-off tech workers, a Kenyan hate-speech lawsuit (a negative), and a halted Danish data center build (dated after the period). None is a positive change in expectations, so the move looks like market or sector strength or noise.
- **P35 December 15, 2022 · market-driven** · stock -4.5% (S&P -2.5%, RSPC -4.1%) · market -6.28pp, company-specific +1.94pp (the market explains 76%; 0.5x normal noise) · **low confidence** (11 statements, 2 articles) · Cause, suspect in a market-driven period: The -4.5% drop on Dec 15 most plausibly reflects the broad market selloff after the Fed's hawkish Wednesday outlook (raising the equity discount rate and lowering earnings expectations), compounded by Meta-specific negatives: the Kenya lawsuit seeking ~$2B and more content moderation spending, and the halt of Danish data center construction, which signals demand/growth caution. The data center cut is partly a cost-discipline positive, so the company-specific news is mixed and not clearly decisive. [A0022-S01, A0022-S03, A0038-S03, A0024-S01, A0024-S02, A0003]
- **P36 December 16, 2022 · within noise** · stock +2.8% (S&P -1.1%, RSPC -0.3%) · market -0.68pp, company-specific +3.35pp (the market explains 17%; 0.9x normal noise) · **high confidence** (10 statements, 2 articles) · Cause, suspect in a within noise period: JPMorgan upgraded Meta to buy and raised its price target, arguing that headwinds ease next year and citing better cost controls on total expenses and capex. The halted Denmark data center build also points to tighter spending. This lifted expectations for margins and investment discipline on a day when the broader market was weak. [A0004, A0023-S02, A0024-S01, A0024-S02]
- **P37 December 19, 2022 · market-driven** · stock -4.1% (S&P -0.9%, RSPC -2.5%) · market -3.67pp, company-specific -0.42pp (the market explains 90%; 0.1x normal noise) · **medium confidence** (5 statements) · Cause, suspect in a market-driven period: The European Commission charged Meta with breaching EU antitrust rules by distorting competition in online classified ads (Facebook Marketplace), with a potential fine of up to $11.8 billion (10% of global revenue), adding regulatory risk and possible forced changes to the business. The ongoing FTC challenge to the Within VR acquisition adds to the antitrust overhang, though it was mostly reported after the move. [A0005-S01, A0005-S03, A0026-S02]
- **P38 December 20–21, 2022 (2 days) · within noise** · stock +4.6% (S&P +1.6%, RSPC +1.7%) · market +2.57pp, company-specific +1.72pp (the market explains 60%; 0.3x normal noise) · **no cause found** (5 statements)
- **P39 December 22–28, 2022 (4 days) · market-driven** · stock -3.5% (S&P -2.5%, RSPC -1.8%) · market -3.09pp, company-specific -0.20pp (the market explains 94%; 0.0x normal noise) · **low confidence** (11 statements, 1 article) · Cause, suspect in a market-driven period: Meta's ad-market share was reported to be eroding as Insider Intelligence projected Meta and Alphabet's combined share would fall below 50% for the first time since 2014, with Apple privacy changes and TikTok competition cited. This adds modest pressure to growth expectations. The $725M Cambridge Analytica settlement is small relative to Meta's size and was largely anticipated, so it is a minor factor. The period's -3.5% drift is modest and likely also reflects broader market weakness. [A0031-S01, A0031-S02, A0031-S03, A0006-S03, A0006-S01]
- **P40 December 29–30, 2022 (2 days) · market-driven** · stock +4.1% (S&P +1.5%, RSPC +2.9%) · market +4.01pp, company-specific -0.29pp (the market explains 93%; 0.1x normal noise) · **no cause found** (1 statement)

## January 2023: growth share 8.8% -> 23.8% (+14.99pp)

| Part | pp |
|---|---|
| Price: market (S&P 500 and sector) | +16.95 |
| Price: company-specific | +1.10 |
| Rates: 10-year Treasury | -4.10 |
| Rates: beta re-estimate | +1.03 |
| **Total** | **+14.99** |

- **P41 January 3–13, 2023 (9 days) · market-driven** · stock +13.1% (S&P +4.1%, RSPC +9.2%) · market +12.11pp, company-specific -0.77pp (the market explains 94%; 0.1x normal noise) · **no cause found** (20 statements)
- **P42 January 17–18, 2023 (2 days) · market-driven** · stock -2.9% (S&P -1.8%, RSPC -2.1%) · market -2.76pp, company-specific +0.28pp (the market explains 91%; 0.1x normal noise) · **no cause found** (9 statements)
- **P43 January 19–23, 2023 (3 days) · market-driven** · stock +7.5% (S&P +2.3%, RSPC +4.0%) · market +4.80pp, company-specific +1.35pp (the market explains 78%; 0.2x normal noise) · **low confidence** (9 statements, 1 article) · Cause, suspect in a market-driven period: Optimism about a Meta rebound in 2023 (ad mogul Martin Sorrell expecting a strong comeback on Reels and business messaging against TikTok, plus a boost from China's reopening for outbound Chinese advertisers), alongside a broad big-tech rally on China reopening hopes and cost-cutting sentiment, lifted the stock. No company-specific earnings or guidance change is in the statements. [A0005-S01, A0005-S02, A0007]
- **P44 January 24–25, 2023 (2 days) · within noise** · stock -1.2% (S&P -0.1%, RSPC +1.5%) · market +1.73pp, company-specific -2.73pp (the market explains 39%; 0.7x normal noise) · **no cause found** (5 statements, 2 articles)
- **P45 January 26–27, 2023 (2 days) · outlier** · stock +7.1% (S&P +1.4%, RSPC +1.2%) · market +1.40pp, company-specific +4.04pp (the market explains 26%; 1.6x normal noise) · **no cause found** (5 statements, 1 article) · No company-specific catalyst in the statements explains the +7.1% move. The items are recaps of the November layoffs, a general analyst bullish take on ad targeting and measurement, a jobs-market piece, and a Cramer meeting recap noting Meta needs more cost cuts. The market rose modestly on strong GDP data, which is too small to account for the move. The news also doesn't mention the Q4 earnings reaction or any new information.
- **P46 January 30, 2023 · within noise** · stock -3.1% (S&P -1.3%, RSPC -1.4%) · market -1.63pp, company-specific -0.76pp (the market explains 68%; 0.4x normal noise) · **no cause found** (6 statements)
- **P47 January 31, 2023 · market-driven** · stock +1.3% (S&P +1.5%, RSPC +1.1%) · market +1.30pp, company-specific -0.31pp (the market explains 81%; 0.2x normal noise) · **no cause found** (22 statements, 2 articles) · The period's +1.3% move on January 31, 2023 came before Meta's earnings were released (after the close on Feb 1). The only same-day items are pre-earnings commentary: Bosworth's blog post on lost focus, expectations of a third straight quarterly sales decline, and old layoff news. None of these is new information that changes expectations. The big earnings beat, $40B buyback and lowered expense guidance came after this day's trading, so they don't explain this move. The move is consistent with general market drift or pre-earnings positioning.

## February 2023: growth share 23.8% -> 49.5% (+25.67pp)

| Part | pp |
|---|---|
| Price: market (S&P 500 and sector) | -4.73 |
| Price: company-specific | +16.98 |
| EPS update: release February 1, 2023 | +10.72 |
| Rates: 10-year Treasury | +2.66 |
| Rates: beta re-estimate | +0.04 |
| **Total** | **+25.67** |

- **P48 February 1, 2023 · market-driven** · stock +2.8% (S&P +1.0%, RSPC +1.3%) · market +1.47pp, company-specific +0.60pp (the market explains 71%; 0.4x normal noise) · **low confidence** (37 statements, 6 articles) · Cause, suspect in a market-driven period: The +2.8% move was in regular trading on Feb 1, before Meta's results came out after the bell. The earnings beat, $40B buyback and lower expense and capex guidance explain the after-hours jump, not this day's gain. The only same-day news that could plausibly explain a modest rise is the report that a court approved Meta's acquisition of Within, a defeat for the FTC. That eases regulatory limits on Meta's VR expansion. Broad market moves and pre-earnings positioning may also have contributed. [A0003-S01, A0003-S02]
- **P49 February 2, 2023 · outlier** · stock +23.3% (S&P +1.5%, RSPC +3.4%) · market +3.01pp, company-specific +10.97pp (the market explains 22%; 8.2x normal noise) · **high confidence** (31 statements, 6 articles) · Cause: Q4 2022 results beat revenue expectations ($32.17B vs about $31.5-31.65B) and daily active users topped estimates. Management also cut 2023 expense guidance to $89-95B from $94-100B and capex to $30-33B from $34-37B, declared a 'Year of Efficiency', and announced a $40B buyback. Together these signaled a leaner cost base, more disciplined investment in the metaverse, and stronger capital returns. Bank of America and Goldman Sachs backed the stock. [A0001-S01, A0021-S01, A0021-S03, A0024-S03, A0028-S02, A0029-S02, A0007-S02, A0007-S03, A0050-S03, A0006, A0009]

<div class="release">

**Release February 1, 2023** · quarter ended December 31, 2022 · in P48, P49 [R2023-02-01, R2022-02-02]

*TTM EPS change*

- -$1.87 (10.46 -> 8.59): the quarter ended December 31, 2022 ($1.77) replaces the one ended December 31, 2021 ($3.64); growth-share effect +10.72pp (price held still)

*One-time items identified*

- Entering: Restructuring charges, charge $4,200M pre-tax, about $1.17 per share (-1.17 to the step; estimated: less 25% tax, over the quarter's 2.70B diluted shares)
- TTM EPS change less one-time items: -$0.70 (estimated: some items are stated in dollars only)

*Market reaction*

- Results surprise: company-specific stock return +19.1% over 2 trading days (February 1, 2023 +0.8%, February 2, 2023 +18.3%), against the market model, 6.1x normal noise

</div>

- **P50 February 3–6, 2023 (2 days) · within noise** · stock -1.4% (S&P -1.6%, RSPC -3.7%) · market -3.03pp, company-specific +2.32pp (the market explains 57%; 1.1x normal noise) · **no cause found** (22 statements, 4 articles)
- **P51 February 7, 2023 · within noise** · stock +3.0% (S&P +1.3%, RSPC +1.2%) · market +0.95pp, company-specific +0.47pp (the market explains 67%; 0.3x normal noise) · **medium confidence** (4 statements) · Cause, suspect in a within noise period: Bloomberg reported that Meta is pushing many managers and directors to move into individual contributor roles or leave, flattening the organization as part of Zuckerberg's 'Year of Efficiency'. This points to lower overhead and a leaner cost base beyond the earlier layoffs, which investors would read as supporting margins. [A0031-S01, A0031-S02, A0052-S01, A0052-S02]
- **P52 February 8–10, 2023 (3 days) · market-driven** · stock -9.4% (S&P -1.8%, RSPC -5.2%) · market -4.40pp, company-specific -0.32pp (the market explains 93%; 0.1x normal noise) · **no cause found** (10 statements)
- **P53 February 13–14, 2023 (2 days) · market-driven** · stock +3.1% (S&P +1.1%, RSPC +1.7%) · market +1.41pp, company-specific +0.12pp (the market explains 92%; 0.1x normal noise) · **no cause found** (3 statements, 1 article) · Meta rose about 3% on Feb 13 alongside a broader tech rally (Microsoft also up ~3%). The only company-specific news is the Financial Times report on a pending layoff round and the 'year of efficiency' theme, which repeats earlier-announced plans rather than changing expectations. No clear new Meta-specific catalyst explains the move. [A0034-S01, A0034-S03, A0014]
- **P54 February 15–27, 2023 (8 days) · market-driven** · stock -5.6% (S&P -3.8%, RSPC -4.4%) · market -3.68pp, company-specific +0.78pp (the market explains 82%; 0.2x normal noise) · **no cause found** (52 statements, 1 article) · No clear company-specific negative catalyst explains the -5.6% decline. The news is mostly neutral-to-positive: the Meta Verified subscription launch (est. $1.7-3B annual revenue), the FTC dropping its Within challenge, more layoffs under the 'Year of Efficiency', and a new generative AI group. The drift lower looks like market or sector weakness (S&P 500 down about 2% in February) after the strong post-earnings run, rather than a change in expectations from these statements.
- **P55 February 28, 2023 · within noise** · stock +3.2% (S&P -0.3%, RSPC -0.6%) · market -0.44pp, company-specific +2.05pp (the market explains 18%; 1.4x normal noise) · **medium confidence** (14 statements, 1 article) · Cause, suspect in a within noise period: On Feb 27 Zuckerberg announced a new top-level generative AI product group, signaling Meta will not fall behind in the AI race and may use AI to boost efficiency, ad content and monetization of WhatsApp and Messenger. Investors read this as improving future growth and efficiency prospects, though the commentary notes that real revenue from it will take time. [A0018-S01, A0018-S03, A0048-S01, A0020-S02, 2023-03/A0002-S01]

## March 2023: growth share 49.5% -> 56.1% (+6.56pp)

| Part | pp |
|---|---|
| Price: market (S&P 500 and sector) | +1.08 |
| Price: company-specific | +8.11 |
| Rates: 10-year Treasury | -2.53 |
| Rates: beta re-estimate | -0.09 |
| **Total** | **+6.56** |

- **P56 March 1, 2023 · within noise** · stock -0.9% (S&P -0.5%, RSPC -1.1%) · market -0.86pp, company-specific +0.42pp (the market explains 67%; 0.3x normal noise) · **no cause found** (6 statements, 1 article)
- **P57 March 2–3, 2023 (2 days) · within noise** · stock +6.8% (S&P +2.4%, RSPC +2.1%) · market +1.63pp, company-specific +1.63pp (the market explains 50%; 0.8x normal noise) · **medium confidence** (10 statements, 1 article) · Cause, suspect in a within noise period: Wall Street analysts turned bullish on Meta's AI potential on March 3: Morgan Stanley named it a top pick and a largest beneficiary of a roughly $780 billion AI-driven online advertising opportunity, and Barclays named it an AI beneficiary. Meta also cut Quest VR headset prices, which was read as a sign of demand push and cost focus. The earlier TikTok ban speculation was a minor tailwind. [A0004-S01, A0005, A0003-S01, A0001-S01]
- **P58 March 6–10, 2023 (5 days) · within noise** · stock -3.1% (S&P -4.6%, RSPC -6.4%) · market -5.01pp, company-specific +3.45pp (the market explains 59%; 1.1x normal noise) · **no cause found** (27 statements, 1 article)
- **P59 March 13–16, 2023 (4 days) · divergent** · stock +13.6% (S&P +2.6%, RSPC +2.8%) · market +2.02pp, company-specific +4.40pp (the market explains 32%; 1.6x normal noise) · **high confidence** (35 statements, 2 articles) · Cause: Meta announced a second round of layoffs (10,000 jobs plus 5,000 open roles closed) as part of its 'year of efficiency', cutting its 2023 expense outlook to $86-92 billion, and signaled that it would cancel lower-priority projects, including metaverse wearables and NFTs. Investors read this as a stronger commitment to cost discipline and less spending on money-losing metaverse bets, which lifts margin and spending-efficiency expectations. Continued positive sentiment followed in the days after. [A0025-S01, A0025-S02, A0050-S01, A0010-S01, A0010-S02, A0011-S01, A0011-S02, A0027-S01, A0027-S02, A0015-S02, A0013]
- **P60 March 17, 2023 · within noise** · stock -4.5% (S&P -1.1%, RSPC -1.0%) · market -0.73pp, company-specific -1.45pp (the market explains 34%; 1.0x normal noise) · **no cause found** (16 statements)
- **P61 March 20–24, 2023 (5 days) · within noise** · stock +5.2% (S&P +1.4%, RSPC +1.9%) · market +1.35pp, company-specific +1.09pp (the market explains 56%; 0.3x normal noise) · **no cause found** (15 statements, 2 articles)
- **P62 March 27–28, 2023 (2 days) · within noise** · stock -2.6% (S&P +0.0%, RSPC +0.4%) · market +0.29pp, company-specific -1.51pp (the market explains 16%; 0.8x normal noise) · **no cause found** (11 statements)
- **P63 March 29–31, 2023 (3 days) · market-driven** · stock +5.5% (S&P +3.4%, RSPC +3.4%) · market +2.39pp, company-specific +0.09pp (the market explains 96%; 0.0x normal noise) · **low confidence** (21 statements) · Cause, suspect in a market-driven period: Continued cost-discipline news under Meta's 'Year of Efficiency' (lower bonus multiplier, twice-yearly reviews, 10,000 more job cuts, 5,000 unfilled openings, remote-job posting pause) reinforced expectations of a leaner cost base and better margins. This is mostly a continuation of the March 14 layoff announcement rather than a new surprise, so it explains the steady gains only partly; the broad market and tech rally likely contributed. [A0041-S01, A0041-S02, A0041-S03, A0053-S01, A0053-S02, A0053-S03, A0044-S02, A0056-S01, A0056-S02]

## April 2023: growth share 56.1% -> 63.5% (+7.46pp)

| Part | pp |
|---|---|
| Price: market (S&P 500 and sector) | -0.51 |
| Price: company-specific | +5.67 |
| EPS update: release April 26, 2023 | +2.35 |
| Rates: 10-year Treasury | -0.13 |
| Rates: beta re-estimate | +0.09 |
| **Total** | **+7.46** |

- **P64 April 3–5, 2023 (3 days) · within noise** · stock -0.2% (S&P -0.5%, RSPC -0.5%) · market -0.38pp, company-specific +0.28pp (the market explains 58%; 0.1x normal noise) · **no cause found** (15 statements, 1 article)
- **P65 April 6–14, 2023 (6 days) · within noise** · stock +4.7% (S&P +1.2%, RSPC -0.0%) · market +0.06pp, company-specific +1.95pp (the market explains 3%; 0.6x normal noise) · **low confidence** (28 statements, 1 article) · Cause, suspect in a within noise period: Investors appeared to reward Meta's AI push (executives focused on AI, generative-AI ad tools due by year-end) and its ongoing cost-cutting and efficiency drive, which analysts said should lift the bottom line. The news is mostly reiteration of known themes rather than a clear new surprise, so the link to the +4.7% move is only partial and may also reflect general market and tech strength. [A0002-S01, A0002-S02, A0023-S01, A0029-S01, A0005-S01, A0005-S02]
- **P66 April 17–26, 2023 (8 days) · market-driven** · stock -5.6% (S&P -2.0%, RSPC -4.7%) · market -2.88pp, company-specific +0.47pp (the market explains 86%; 0.1x normal noise) · **low confidence** (75 statements, 5 articles) · Cause, suspect in a market-driven period: Pre-earnings de-risking after a 77% rally. Articles on April 25, the day of the -2.5% drop, said Meta needed a new catalyst. They flagged expected Q1 revenue and profit declines (profit down about 30%) and a Reuters-reported memo in which an infrastructure head said Meta was an AI laggard and needed to invest heavily. The Q1 beat and guidance came after the close on April 26, so they are not in this period's price moves. [A0046-S01, A0046-S02, A0048-S01, A0073-S01, A0073-S02, A0073-S03]
- **P67 April 27, 2023 · divergent** · stock +13.9% (S&P +2.0%, RSPC +3.7%) · market +2.02pp, company-specific +3.39pp (the market explains 37%; 3.0x normal noise) · **high confidence** (41 statements, 5 articles) · Cause: Meta reported Q1 2023 results after the close on April 26 that beat expectations: revenue of $28.65B versus about $27.7B expected, the first year-over-year growth after three quarters of decline, and EPS of $2.20 versus $2.03. It guided Q2 revenue to $29.5-32B, above estimates, and cut its 2023 expense forecast to $86-90B. Management said AI was lifting engagement and ad sales, and the 'year of efficiency' cost cuts continued with slower hiring. Investors reset expectations toward a return to revenue growth, better margins and more disciplined spending. [A0010-S01, A0050-S01, A0050-S02, A0055-S01, A0057-S02, A0011-S01, A0011-S02, A0062-S01, A0064-S01, A0067-S02]

<div class="release">

**Release April 26, 2023** · quarter ended March 31, 2023 · in P66, P67 [R2023-04-26]

*TTM EPS change*

- -$0.52 (8.59 -> 8.07): the quarter ended March 31, 2023 ($2.20) replaces the one ended March 31, 2022 ($2.72); growth-share effect +2.35pp (price held still)

*One-time items identified*

- Entering: Restructuring charges, charge $1,140M pre-tax, about $0.33 per share (-0.33 to the step; estimated: less 25% tax, over the quarter's 2.60B diluted shares)
- TTM EPS change less one-time items: -$0.19 (estimated: some items are stated in dollars only)

*Market reaction*

- Results surprise: company-specific stock return +12.3% over 2 trading days (April 26, 2023 +3.6%, April 27, 2023 +8.7%), against the market model, 3.0x normal noise

</div>

- **P68 April 28, 2023 · within noise** · stock +0.7% (S&P +0.8%, RSPC +1.2%) · market +0.67pp, company-specific -0.41pp (the market explains 62%; 0.4x normal noise) · **no cause found** (23 statements, 3 articles)

## May 2023: growth share 63.5% -> 67.8% (+4.26pp)

| Part | pp |
|---|---|
| Price: market (S&P 500 and sector) | -0.99 |
| Price: company-specific | +4.25 |
| Rates: 10-year Treasury | +1.09 |
| Rates: beta re-estimate | -0.08 |
| **Total** | **+4.26** |

- **P69 May 1, 2023 · within noise** · stock +1.2% (S&P -0.0%, RSPC -0.0%) · market -0.02pp, company-specific +0.45pp (the market explains 4%; 0.4x normal noise) · **no cause found** (5 statements)
- **P70 May 2–5, 2023 (4 days) · market-driven** · stock -4.3% (S&P -0.7%, RSPC -3.0%) · market -1.56pp, company-specific -0.05pp (the market explains 97%; 0.0x normal noise) · **medium confidence** (15 statements) · Cause, suspect in a market-driven period: The FTC proposed barring Meta from monetizing data of users under 18, slowing its ability to launch new products until privacy compliance is confirmed, and limiting future facial recognition use. This raised regulatory risk and potential constraints on revenue and product development, outweighing the minor AI chip team hiring and the routine bond issue. [A0001-S01, A0001-S02, A0017-S01, A0018-S01, A0018-S02]
- **P71 May 8–19, 2023 (10 days) · within noise** · stock +5.4% (S&P +1.4%, RSPC +1.5%) · market +0.82pp, company-specific +1.14pp (the market explains 42%; 0.5x normal noise) · **medium confidence** (41 statements) · Cause, suspect in a within noise period: Meta's generative AI ad tools (AI Sandbox, Meta Advantage updates, ad performance prediction model) and disclosure of custom AI chips and data-center redesign raised expectations that AI will improve ad performance and monetization. Continued 'year of efficiency' cost discipline (Kustomer divestiture, layoffs) supported margin expectations, and the broader tech/AI enthusiasm and a rate-peak belief likely helped. No single large surprise; the EU fine risk was a modest offset. [A0002-S01, A0002-S03, A0022-S01, A0023-S02, A0004-S01, A0030-S01, A0030-S03, A0003-S02, A0028-S01, A0031-S01, A0032-S02]
- **P72 May 22–31, 2023 (7 days) · outlier** · stock +7.6% (S&P -0.3%, RSPC -0.3%) · market -0.22pp, company-specific +2.71pp (the market explains 8%; 1.6x normal noise) · **no cause found** (65 statements, 1 article) · The statements contain no clear company-specific catalyst for the +7.6% rise. The record EU fine of about $1.3B and the data-transfer suspension order were negative news, and the stock still rose through the period. The final round of layoffs and Zuckerberg's 'scrappier', efficiency-focused messaging (May 24-26) mildly support the cost-efficiency story. The sale of Giphy at a loss, the Magic Leap talks, and AI chip and AI-hype commentary are minor. The move more plausibly reflects the broad tech and AI rally than any news in these statements.

## June 2023: growth share 67.8% -> 70.5% (+2.76pp)

| Part | pp |
|---|---|
| Price: market (S&P 500 and sector) | +2.63 |
| Price: company-specific | -0.15 |
| Rates: 10-year Treasury | +0.29 |
| Rates: beta re-estimate | -0.01 |
| **Total** | **+2.76** |

- **P73 June 1, 2023 · within noise** · stock +3.0% (S&P +1.0%, RSPC +1.2%) · market +0.56pp, company-specific +0.38pp (the market explains 60%; 0.7x normal noise) · **low confidence** (34 statements) · Cause, suspect in a within noise period: Meta announced the Quest 3 headset at $500 shipping in the fall, plus a Quest 2 price cut to $299 and a gaming showcase, just ahead of Apple's expected headset reveal. It also set a three-day return-to-office mandate after its layoffs, which is read as an efficiency and productivity signal. These are modest, incremental items, and a +3.0% day likely also reflects the broader market and tech sector, so the attribution is only partial. [A0001-S01, A0001-S02, A0055-S01, A0055-S02, A0018-S03, A0002-S01, A0015-S01]
- **P74 June 2–7, 2023 (4 days) · outlier** · stock -3.3% (S&P +1.1%, RSPC +2.5%) · market +0.67pp, company-specific -1.74pp (the market explains 28%; 1.8x normal noise) · **no cause found** (54 statements, 1 article)
- **P75 June 8–22, 2023 (10 days) · within noise** · stock +7.9% (S&P +2.7%, RSPC -0.3%) · market +0.12pp, company-specific +2.29pp (the market explains 5%; 1.3x normal noise) · **low confidence** (58 statements, 1 article) · Cause, suspect in a within noise period: Investors appear to have been encouraged by Meta's generative AI push: the all-hands showcase of AI chatbots for WhatsApp and Messenger and photo-editing tools for Instagram, the open-sourced image model, and plans to make its open-source LLM available for commercial use. These suggest AI-driven engagement, ad-tool improvements and monetization, such as WhatsApp Channels payments. The move was probably also helped by a strong broader tech and AI rally. Negative regulatory items (EU child-content demands, Canada news ban) came late and were small. [A0005-S01, A0005-S02, A0006-S01, A0006-S02, A0029-S01, A0057-S03, A0040-S01, A0040-S03, A0042-S01, A0042-S02]
- **P76 June 23, 2023 · within noise** · stock +1.4% (S&P -0.8%, RSPC -0.4%) · market -0.23pp, company-specific +0.63pp (the market explains 27%; 1.2x normal noise) · **no cause found** (12 statements)
- **P77 June 26, 2023 · outlier** · stock -3.6% (S&P -0.4%, RSPC +0.8%) · market +0.26pp, company-specific -1.35pp (the market explains 16%; 2.5x normal noise) · **no cause found** (4 statements, 1 article)
- **P78 June 27–30, 2023 (4 days) · market-driven** · stock +3.1% (S&P +2.8%, RSPC +2.5%) · market +1.25pp, company-specific -0.35pp (the market explains 78%; 0.3x normal noise) · **no cause found** (9 statements, 2 articles)

## July 2023: growth share 70.5% -> 72.4% (+1.89pp)

| Part | pp |
|---|---|
| Price: market (S&P 500 and sector) | +1.01 |
| Price: company-specific | +1.88 |
| EPS update: release July 26, 2023 | -1.71 |
| Rates: 10-year Treasury | +0.58 |
| Rates: beta re-estimate | +0.13 |
| **Total** | **+1.89** |

- **P79 July 3, 2023 · within noise** · stock -0.3% (S&P +0.1%, RSPC +0.6%) · market +0.24pp, company-specific -0.34pp (the market explains 42%; 0.6x normal noise) · **no cause found** (12 statements, 1 article)
- **P80 July 5–18, 2023 (10 days) · within noise** · stock +8.9% (S&P +2.2%, RSPC +2.2%) · market +1.01pp, company-specific +1.42pp (the market explains 42%; 0.8x normal noise) · **medium confidence** (80 statements, 6 articles) · Cause, suspect in a within noise period: Meta's Threads launch on July 5 drew millions of sign-ups within hours (100 million within days), positioning it to take share from a weakened Twitter and open a new ad channel; Evercore ISI estimated about $8B in annual revenue within two years. Later in the period, the Llama 2 commercial release and the Qualcomm and Microsoft partnerships strengthened Meta's AI position. The EU court loss, Norway fine and tax-prep data issues were regulatory headwinds, but the stock still rose. [A0002-S01, A0003-S02, A0031-S01, A0031-S02, A0041-S01, A0041-S02, A0012-S01, A0050-S01, A0051-S01, A0001, A0004]
- **P81 July 19, 2023 · within noise** · stock +1.3% (S&P +0.2%, RSPC -0.3%) · market -0.07pp, company-specific +0.41pp (the market explains 15%; 0.8x normal noise) · **low confidence** (23 statements) · Cause, suspect in a within noise period: Meta released Llama 2 for free commercial use, distributed through Microsoft Azure and set to run on Qualcomm chips from 2024, and rolled out its first Threads update. These strengthen Meta's AI positioning and ecosystem reach. The move is modest (+1.3%), and the free model carries no direct revenue, so the link is plausible but weak. [A0011-S01, A0050-S01, A0050-S02, A0051-S01, A0052-S01, A0053-S01, A0053-S02]
- **P82 July 20–26, 2023 (5 days) · within noise** · stock -5.5% (S&P +0.0%, RSPC -2.6%) · market -0.64pp, company-specific -0.92pp (the market explains 41%; 0.9x normal noise) · **no cause found** (66 statements, 4 articles) · The period's net move was a 5.5% decline, driven by the early-period selloff (-4.3% and -2.7% on July 20-21). The statements give no clear company-specific cause for that drop. The July 26 Q2 earnings beat (revenue $32B vs ~$31.1B expected, Q3 guidance above expectations, capex cut, cost discipline) is the major news, but it came after the close on July 26. The stock's after-hours jump (~6-7%) falls outside the period, so it does not explain the net decline. The small gains on July 25-26 were modest pre-earnings moves, possibly helped by an analyst upgrade on AI feedback. The July 21 AI safeguards pledge and the EU antitrust probe are minor and do not plausibly explain a ~7% two-day drop. Overall, the net decline lacks a plausible stated cause.
- **P83 July 27, 2023 · outlier** · stock +4.4% (S&P -0.6%, RSPC +0.1%) · market -0.11pp, company-specific +1.28pp (the market explains 8%; 3.0x normal noise) · **high confidence** (48 statements, 4 articles) · Cause: Meta reported Q2 results after the close on July 26 that beat expectations: revenue of $32B (+11%) against $31.12B expected, and Q3 revenue guidance of $32B-$34.5B that investors took as optimistic. The ad rebound and the 'year of efficiency' cost cuts were credited, and full-year capex guidance was lowered to $27-30B from $30-33B. An analyst upgrade cited accelerating tailwinds and 'de-risked' 2024 guidance. Larger Reality Labs losses expected in 2024 were a partial offset. [A0014-S01, A0014-S02, A0014-S03, A0071-S01, A0018-S01, A0018-S02, A0079-S02, A0081-S03, A0084-S03, A0019]

<div class="release">

**Release July 26, 2023** · quarter ended June 30, 2023 · in P82, P83 [R2023-07-26]

*TTM EPS change*

- +$0.52 (8.07 -> 8.59): the quarter ended June 30, 2023 ($2.98) replaces the one ended June 30, 2022 ($2.46); growth-share effect -1.71pp (price held still)

*One-time items identified*

- Entering: Accrued legal expenses, charge $1,870M pre-tax, about $0.54 per share (-0.54 to the step; estimated: less 25% tax, over the quarter's 2.61B diluted shares)
- Entering: Restructuring charges, charge $780M pre-tax, about $0.22 per share (-0.22 to the step; estimated: less 25% tax, over the quarter's 2.61B diluted shares)
- TTM EPS change less one-time items: +$1.28 (estimated: some items are stated in dollars only)

*Market reaction*

- Results surprise: company-specific stock return +6.0% over 2 trading days (July 26, 2023 +1.1%, July 27, 2023 +4.8%), against the market model, 2.6x normal noise

</div>

- **P84 July 28–31, 2023 (2 days) · market-driven** · stock +2.3% (S&P +1.1%, RSPC +1.4%) · market +0.57pp, company-specific +0.04pp (the market explains 94%; 0.1x normal noise) · **medium confidence** (51 statements, 3 articles) · Cause, suspect in a market-driven period: Meta's Q2 2023 results (reported July 26 after the close) beat expectations: revenue rose 11% to $32B against a $31.12B estimate and EPS was $2.98 against $2.91. Q3 revenue guidance was above expectations, advertising rebounded, and the 'year of efficiency' cost cuts were working. Full-year capex guidance was lowered to $27-30B from $30-33B, and an analyst upgrade followed. Investors kept repricing these positives on July 28, giving a +4.4% day, followed by a partial giveback (-2.1%) on July 31 amid concerns about Threads retention, rising Reality Labs losses in 2024, and an analyst saying to invest elsewhere until the new investments become accretive. [A0018-S01, A0018-S02, A0076-S01, A0079-S02, A0081-S01, A0081-S03, A0084-S03, A0086-S02, A0020-S01, A0018-S03]

## August 2023: growth share 72.4% -> 71.2% (-1.26pp)

| Part | pp |
|---|---|
| Price: market (S&P 500 and sector) | -0.82 |
| Price: company-specific | -1.26 |
| Rates: 10-year Treasury | +0.54 |
| Rates: beta re-estimate | +0.28 |
| **Total** | **-1.26** |

- **P85 August 1, 2023 · within noise** · stock +1.3% (S&P -0.3%, RSPC -0.3%) · market -0.14pp, company-specific +0.49pp (the market explains 22%; 1.0x normal noise) · **low confidence** (18 statements) · Cause, suspect in a within noise period: Report (FT) that Meta will launch AI-powered chatbots with different personalities as soon as September to boost user retention, alongside continued AI enthusiasm and Threads optimism, modestly raised expectations for engagement and future revenue. The Canada news block and the Threads user losses were minor offsets. [A0006-S01, A0006-S02, A0009-S01, A0009-S02, A0011-S01]
- **P86 August 2–15, 2023 (10 days) · within noise** · stock -6.5% (S&P -3.1%, RSPC -1.9%) · market -1.15pp, company-specific -0.70pp (the market explains 62%; 0.5x normal noise) · **no cause found** (41 statements, 1 article)
- **P87 August 16–18, 2023 (3 days) · within noise** · stock -6.3% (S&P -1.5%, RSPC -2.3%) · market -1.01pp, company-specific -0.86pp (the market explains 54%; 1.0x normal noise) · **no cause found** (13 statements)
- **P88 August 21–23, 2023 (3 days) · within noise** · stock +3.9% (S&P +1.5%, RSPC +1.1%) · market +0.62pp, company-specific +0.50pp (the market explains 56%; 0.6x normal noise) · **no cause found** (11 statements)
- **P89 August 24–25, 2023 (2 days) · within noise** · stock -3.0% (S&P -0.7%, RSPC -1.3%) · market -0.51pp, company-specific -0.38pp (the market explains 57%; 0.5x normal noise) · **no cause found** (7 statements)
- **P90 August 28–31, 2023 (4 days) · market-driven** · stock +3.6% (S&P +2.3%, RSPC +3.1%) · market +1.36pp, company-specific -0.31pp (the market explains 81%; 0.3x normal noise) · **no cause found** (15 statements)

Batch cost: $0.455.
