# PVGO_Collection — methodology

How the growth share is calculated, today by [pvgo_growth_share.py](pvgo_growth_share.py)
and as a daily history by [pvgo_history.py](pvgo_history.py) (section 7). The pipeline
runs the history through [pvgo_history_run.py](pvgo_history_run.py), "the runner" below:
its settings at the top of the file mirror `pvgo_history.py`'s flags.

## Where each step lives

The modules are named by the step they cover (flat, no package). Run the command files
from any folder.

| Module | Step |
|---|---|
| `pvgo_inputs` | Both commands' settings, and the raw inputs: SEC EDGAR (ticker map, company facts, submissions profile), the price (latest and daily history), the S&P 500 history, and the 10-year Treasury (latest and daily). (§2) |
| `pvgo_eps` | Every EPS basis: XBRL quarters to TTM, adjusted TTM (the default), 2-year and 6-month EPS; the R&D-adjusted EPS; the earnings-quality notes. (§2, §5, §6) |
| `pvgo_cost_of_equity` | Beta and ERP: Damodaran's files, industry resolution, the industry beta, the company's own beta, and the year-by-year ERP. (§3, §7) |
| `pvgo_growth_share` | The formula (`growth_share`, `compute`, `PvgoResult`) and today's reading as a command: `python pvgo_growth_share.py COST`. (§1) |
| `pvgo_history_releases` | For each quarter: the earnings release date, the measurement day, the TTM as known at the release, and the press-release EPS reconciliation (`--release-items`). (§7) |
| `pvgo_history_series` | The EPS bases charted, the no-growth line, the daily series, and assembling a ticker's history (`collect_history`). (§7) |
| `pvgo_history` | The history command and its outputs: the points table, the CSVs and the charts. (§7) |
| `pvgo_history_run` | The runner: the history with its settings at the top of the file. |

## 1. What this produces

For each ticker, the **share of the stock price that comes from expected growth**: the
present value of growth opportunities (PVGO) divided by the price.

```
growth share = 1 − EPS ÷ (price × cost of equity)
             = (price − EPS ÷ cost of equity) ÷ price
             = PVGO ÷ price
```

`EPS ÷ cost of equity` is what the stock would be worth if today's earnings continued
forever with no growth (the "no-growth value"). PVGO is whatever the price carries above
that.

**The EPS is the adjusted TTM EPS:** the last four fiscal quarters of GAAP diluted EPS,
without the realized and unrealized gains and losses on investments, less a flat 25% tax
(section 2).
- **It's a fixed rule,** the same for every company, with no management judgment. Banks,
  insurers and brokers are left unadjusted, since their investment gains are operating
  income.
- **Why the investment marks come out:** equity marks run through net income (ASU
  2016-01). Capitalized at the cost of equity, a one-quarter mark would become "permanent"
  no-growth value, though the holdings themselves are an asset.
- **Every other charge stays in:** restructuring, legal and the rest. "One-time" is
  management's label, and such charges often recur. So a charge enters the TTM at its
  release and leaves four quarters later, and Company_Narrative_Aggregation names each such
  step from the press release.
- **Trailing, not forward:** a full year covers seasonality and is observable,
  point-in-time and free. A forward (consensus) basis would put expected growth into the
  no-growth value, so changes in expectations would move it instead of PVGO.
- **Other bases, for comparison:** raw TTM, the trimmed 2-year EPS, the 6-month EPS
  (section 2) and the R&D-adjusted EPS (section 6).
- **Not yet separated: the investment holdings.** Price = value in place + investment
  holdings + PVGO, but the holdings stay inside PVGO, which overstates the growth share of
  a company with large holdings. The data (`EquitySecuritiesFvNi`) is often year-end only,
  so a separate asset would step once a year.

**Relation to Counterpoint.** This follows the steady-state approach in Mauboussin &
Callahan, *"Opportunities and Expectations"* (Morgan Stanley Counterpoint Global, June
2026): earnings capitalized at the cost of equity. The paper uses two methods (its p. 4):
- **Its company charts** (Exhibit 6 and the sector appendix, sourced from FactSet): "the
  consensus estimate for earnings over the next four quarters" capitalized at the cost of
  equity, at year-end, per share. These are what this tool's growth share compares with.
- **Its return study by PVGO quintile** (Exhibit 4, Compustat): trailing 12-month NOPAT
  capitalized at the WACC, less net debt, with "an adjustment for intangible investment"
  (its endnote 8). The company charts make no such adjustment.

It doesn't say which beta or ERP the company charts use. The differences from its company
charts:
- **Earnings:** trailing GAAP diluted EPS without investment gains, not forward consensus.
  - Trailing EPS lags the earnings' direction by up to a year. For a growing company it
    reads below consensus, which overstates the growth share; while earnings are falling it
    reads above, which understates it and can turn it negative (META, October-November 2022).
  - It keeps one-time charges and gains that consensus looks past. The trimmed 2-year EPS
    (section 2) is the closer stand-in for consensus in steady years, but it averages
    backward, so it reads further from consensus while earnings are falling.
- **Intangibles:** neither the main reading nor the paper's company charts adjust for
  expensed intangible investment, so R&D and brand spending lower EPS and raise the growth
  share in both. The R&D-adjusted reading (section 6) capitalizes R&D; it is a step away
  from the company charts, not toward them, though for a company whose earnings and R&D are
  both growing it can land near them (both raise the EPS).

**The terminal report shows every input:**
- price, TTM EPS, and P/E on TTM EPS;
- the adjusted TTM EPS, with the investment gains excluded and their XBRL tags;
- the 6-month EPS and the 2-year EPS (its eight quarters and the two it dropped);
- the cost of equity: the industry (and where it came from), raw and scaled beta, and the
  ERP;
- the no-growth value, PVGO and the growth share;
- the 2-year and 6-month growth shares, for comparison;
- the R&D-adjusted line, with the R&D, amortization and share count behind it.

The same fields go to `pvgo_results.csv` (`--output` to change it):

`ticker, company, sic, damodaran_industry, industry_source, price, price_date,
price_source, eps_ttm, eps_period, pe, eps_six_month, eps_prior_ttm, eps_two_year,
two_year_period, two_year_dropped, ttm_quarters, ttm_quarter_leaving, eps_used,
ttm_vs_two_year_pct, treasury_10y_pct,
treasury_date, beta_raw, beta_scaled, beta_source, equity_risk_premium_pct,
cost_of_equity_pct, no_growth_value, pvgo, growth_share_pct, growth_share_two_year_pct,
growth_share_six_month_pct, investment_gains_ttm, investment_gain_tags,
investment_adjustment_per_share, eps_ttm_adjusted, growth_share_ttm_adjusted_pct,
rd_current, rd_basis, rd_amortization, rd_life_years, rd_effective_life_years,
rd_diluted_shares, rd_adjustment_per_share, eps_rd_adjusted, growth_share_rd_adjusted_pct,
notes`

- `eps_used` is the EPS behind `no_growth_value`, `pvgo` and `growth_share_pct`: the
  adjusted TTM, or raw TTM, with a note, where the adjustment can't be computed.
- `growth_share_two_year_pct` is the same formula on the 2-year EPS. It's blank without
  eight consecutive quarters.
- The investment columns (section 2):
  - `investment_gains_ttm`: the TTM's pre-tax gains (+) or losses (−) on investments, USD;
  - `investment_gain_tags`: the XBRL tags they came from, or why there's no adjustment;
  - `investment_adjustment_per_share`: −gains × 0.75 ÷ diluted shares;
  - `eps_ttm_adjusted` = `eps_ttm` + that adjustment.
- `two_year_dropped` names the lowest and highest quarter, e.g.
  `2024-09-30 4.37; 2026-06-30 7.70`.
- `ttm_quarters` lists the TTM's four quarters, oldest first, each as its end date, its EPS
  and its source: `10-Q`, `10-K`, or `derived: FY - Q1-Q3` for a Q4 worked out from the
  annual figure. For example, Costco's newest quarter at its September 2024 release:
  `…; 2024-09-01 5.2800 derived: FY - Q1-Q3`.
  - `ttm_quarter_leaving` is the quarter just before them, in the same form. It's the one the
    TTM dropped when it took its newest quarter, so at a release the TTM's change is the
    newest quarter minus this one (blank without the four prior quarters).
  - `Company_Narrative_Aggregation`'s release call reads both.
- `ttm_vs_two_year_pct` is (TTM − 2-year) ÷ |2-year| × 100, behind the lag warning
  (section 5).
- `notes` holds several notes separated by ` | `. If the CSV is open in Excel (which locks
  it), the run still prints everything and says the file couldn't be written.

**The growth share is a number only.** There are no interpretive bands or cutoffs: compare
companies and track changes over time directly.

**EPS of zero or less still gets a number.** The no-growth value is then zero or negative,
so the growth share is 100% or more, as Mauboussin & Callahan report loss-making
companies. The report marks it "(EPS <= 0, so 100% or more by construction)", and P/E
shows as n/a.

**The main ways it misleads:**
- **A real, lasting change in earnings.** TTM EPS takes up to a year to reflect one fully
  (the 2-year EPS up to two). After a sharp, lasting drop it overstates earnings power, so
  the growth share falls with the price and **understates** expectations; after a jump,
  the reverse. The 6-month growth share reacts sooner.
- **One-time items.** A one-time charge lowers the TTM EPS for four quarters, and raises the
  growth share by the same mechanics, without any change in expectations. The lag warning
  (section 5) flags raw TTM EPS more than 25% away from the 2-year EPS.
- **The level depends on the inputs.** A 1pp change in the cost of equity moves the growth
  share by several points. "No growth" means zero nominal growth, so part of the growth
  share is just keeping pace with inflation.

## 2. Inputs and how they're fetched

| Input | Source | Notes |
|---|---|---|
| Share price and stock splits | Yahoo Finance via `yfinance`: the latest daily bar, not dividend-adjusted, plus the last five years of splits from the same request | During market hours, a **delayed** intraday price; otherwise the last close. `--price` overrides the price for a single ticker; the splits are still looked up |
| Quarterly diluted EPS | SEC EDGAR XBRL company facts (`data.sec.gov/api/xbrl/companyfacts/`) | Ticker → company ID via SEC's `company_tickers.json` |
| Investment gains, R&D expense and diluted share count | The same SEC company facts | No extra request (sections 2 and 6) |
| SIC code and latest 10-Q/10-K | SEC submissions API (`data.sec.gov/submissions/CIK##########.json`) | One request per ticker |
| Company → industry | Damodaran's company list (`pc/datasets/indname.xls`) | About a 22 MB download, cached as a ~0.5 MB CSV of the ~6,900 companies on US exchanges (section 3) |
| Industry beta | Damodaran, "Levered and Unlevered Betas by Industry", U.S. (`pc/datasets/betas.xls`) | Cached in `cache/` |
| 10-year Treasury yield | FRED series DGS10, no-key CSV download | Latest available daily value; holidays (`.`) skipped |

**TTM diluted EPS = the sum of the last four fiscal quarters.**
- **The tag:** `EarningsPerShareDiluted`, falling back to `EarningsPerShareBasicAndDiluted`
  with a note.
- **Which filings:** only 10-Q and 10-K figures count, including amendments (10-Q/A,
  10-K/A). Where a period was reported more than once, the **most recently filed** value is
  used, which picks up restatements.
- **Q4** is usually only inside the 10-K's 12-month figure, so it's derived as annual EPS −
  (Q1 + Q2 + Q3), and flagged in the notes. The 10-Qs' year-to-date figures are ignored.
- **Consecutive quarters:** each must start within 7 days of the previous end, which allows
  for 52/53-week years. Otherwise the ticker is skipped.
- **Summing quarters** is the standard approximation; EPS isn't strictly additive, because
  share counts change.
- **Stock splits:** each EPS fact filed before a split in Yahoo's split history is divided
  by the split ratio, before quarters are summed or Q4 is derived. EPS is then on the same
  share basis as the price, and a note names the split. This matters because after a
  split, later 10-Qs restate the prior-year quarters but not the current year's earlier
  quarters, so the latest values mix pre- and post-split figures.

**The adjusted TTM EPS** (`investment_gain_adjustment`) = TTM EPS − TTM gains on
investments × (1 − 25%) ÷ diluted shares.
- **The gains:** realized and unrealized gains (+) and losses (−) on investments, from the
  first of these XBRL tags that has a value for each quarter:
  - `EquitySecuritiesFvNiGainLoss` (Amazon: Rivian);
  - `GainLossOnInvestments` (Microsoft);
  - `UnrealizedGainLossOnInvestments`;
  - `EquitySecuritiesFvNiUnrealizedGainLoss`: a fallback, sometimes rounded and
    unrealized-only.
- **Not used:** the broad "other (gains) and losses" line (`NonoperatingIncomeExpense`). It
  also holds recurring items, such as pension income, and business disposals, such as the
  loss on selling a subsidiary.
- **Quarters from year-to-date figures.** Cash-flow-statement tags are reported
  year-to-date in 10-Qs. Within a tag, a quarter is the difference of two year-to-date
  figures with the same fiscal-year start (6-month − Q1, 9-month − 6-month, FY − 9-month).
  A Q4 is otherwise FY − Q1−Q3, as for EPS.
  - Differences never mix tags, except as a last resort, with a note: a fiscal year under
    one tag less 9 months under another.
  - That covers a company whose 10-Ks keep an old tag while its 10-Qs use a new one. It's
    tried before the fallback tag.
- **Point-in-time and splits:** only facts filed by each release's cutoff, like the EPS. The
  diluted share count is the TTM's average, on today's share basis (`_diluted_shares`, as
  for R&D).
- **Tax:** a flat 25% (`INVESTMENT_GAIN_TAX_RATE`): the US federal 21% plus a typical state
  rate, Damodaran's US marginal rate.
- **Exempt:** SIC 6000–6799 (banks, insurers, brokers), with a note.
- **Partial data:** a tag reporting only some of the TTM's quarters counts the rest as
  zero, with a note. No tag at all means a zero adjustment ("no investment gains in SEC's
  data").
- **Accuracy:** checked against a company's press-release reconciliations, the
  per-quarter after-tax amounts match within a few cents (the flat tax against the
  company's actual tax).
- **A company without investment gains** (Costco) has a zero adjustment: its adjusted TTM
  equals its TTM.

**The trimmed 2-year EPS** (`eps_two_year`, the chart's `two_year` basis):
```
2-year EPS = 4 × mean of the last 8 fiscal quarters, without the single highest and lowest
           = (sum of the 8 − highest − lowest) × 4 ÷ 6
```
- **The eight quarters** are the TTM's four and the four before them, consecutive with
  them, built exactly like the TTM.
- **Trimming** drops one quarter at each end, one each on ties. A loss quarter is the
  lowest, so a write-down is dropped; a one-time gain is the highest.
- **Without eight consecutive quarters** (e.g. within two years of an IPO), it's blank.
- **What it's for:** comparisons with Counterpoint (section 7). It's the closest free
  stand-in found for consensus EPS, which looks past one-time items. Trimming removes a big
  one-off by one fixed rule; in ordinary periods the highest and lowest quarters roughly
  cancel.
- **Its costs:**
  - **Seasonal companies:** dropping the highest quarter removes one of two holiday peaks,
    understating EPS by about 4% for Apple-like seasonality.
  - **A real change shows late.** Suppose quarterly EPS falls from 1.00 to 0.50 and stays
    there. How much of that 50% drop each measure shows:

    | Bad quarters so far | 6-month | TTM | Plain 2-year average | Trimmed 2-year |
    |---|---|---|---|---|
    | 1 | −25% | −12.5% | −6% | 0% |
    | 2 | −50% | −25% | −12.5% | −8% |
    | 4 | −50% | −50% | −25% | −25% |
    | 7 | −50% | −50% | −44% | −50% |

    Trimming ignores the first bad quarter and part of the second, then catches up. Both
    2-year versions show only half the drop after a full year.

**The 6-month EPS** (`eps_six_month`) = 2 × the TTM's latest two quarters, so it's on the
same yearly basis as the TTM. It exists wherever the TTM does, and reacts soonest, at
three costs:
- **One-time items count double:** a quarter is half the window.
- **Seasonal quarters make it swing within the year,** since the window holds two of the
  four seasons. Stylized: a holiday quarter of 1.50 and three of 1.00 (TTM 4.50) give 5.00
  (+11%) after the holiday quarter and the one after it, and 4.00 (−11%) after the other
  two.
- **Growth puts it above the TTM,** by about a quarter of a year's growth, since its
  quarters are on average three months more recent.

## 3. Cost of equity

```
cost of equity = 10-year Treasury yield + beta × ERP
beta           = industry beta ÷ Total Market beta     (Damodaran's US file)
```

The history chart can instead use the company's own beta and the ERP at each date
(section 7).

**Industry: chosen in this order.** The CSV's `industry_source` records which step
applied:
1. **`damodaran_company`:** the company's own industry in Damodaran's company list.
   - **Ticker match:** the list's `Exchange:Ticker` column (e.g. `NYSE:JPM`), on US
     exchanges only: NYSE, NasdaqGS, NasdaqGM, NasdaqCM, NYSEAM, OTCPK, OTCQX, OTCQB, BATS
     and ARCA. (OTCNO is Norway's OTC list.) Tickers are compared without punctuation, so
     `BRK.B` = `BRK-B`. The restriction matters because the same ticker exists abroad for
     unrelated companies (`ASE:MSFT` is a Jordanian trucking firm).
   - **Guard against reused tickers:** a ticker match only counts if the company names
     share a meaningful word. Otherwise it's ignored, with a note.
   - **Name fallback:** if the ticker isn't listed, or fails the name check, the SEC company
     name is matched to Damodaran's after dropping words like Inc/Corp/Co/The. This needs a
     unique match. Berkshire Hathaway's `BRK.B` is found this way, since only `BRK.A` is
     listed.
2. **`sic_mapping`:** otherwise the company's SIC code is mapped through
   `sic_to_damodaran_industry.csv` (below).
3. **`override`:** `company_industry_overrides.csv` (columns `ticker`,
   `damodaran_industry`, `note`) is applied last and wins over both. It ships empty; add a
   row for any edge case.

**Beta: the industry's average levered beta,** not relevered for the company's own debt.
- **Raw:** the "Beta" column of Damodaran's US file, the simple average across the
  industry's firms. The parser finds the "Industry Name" header row and the "Beta" column
  itself, rather than assuming positions.
- **Scaled:** raw ÷ the file's own **Total Market** beta (0.912 in January 2026), so the
  market averages 1.0. **The scaled beta is used.** The CSV shows both, as `beta_raw` and
  `beta_scaled`.
- **Fallback to beta 1.0, with a note,** when no industry is found (the note names the SIC
  code, so you can add it to the mapping), when the industry isn't in the beta file, or
  when the beta file can't be downloaded and there's no cache.
- **`--market-beta`** forces beta 1.0 for every ticker. `beta_raw` is then blank, and the
  industry is still recorded.

**ERP:** `EQUITY_RISK_PREMIUM` in `pvgo_inputs.py` (4.14%) sets the default. It's set by
hand to Damodaran's current implied ERP, the headline figure on his home page, which he
updates at the start of each month. `--erp 4.3` (in percent) overrides it for a run.
Compare only runs made with the same ERP.

**Caching:** both Damodaran files are stored in `cache/` (gitignored):
`damodaran_betas_us.xls` and `damodaran_companies_us.csv` (the US-exchange extract).
- **Refresh:** each is re-downloaded when it's more than 30 days old
  (`DAMODARAN_CACHE_MAX_AGE_DAYS`).
- **A download only replaces the cache if it parses and looks complete:** for the company
  list, at least 1,000 US companies.
- **A failed refresh** uses the old cache, with a note, and isn't retried for a day
  (`DAMODARAN_RETRY_AFTER_DAYS`).
- **With no cache at all,** a missing company list falls back to the SIC mapping, and a
  missing beta file to beta 1.0, each with a note.

**How `sic_to_damodaran_industry.csv` was built.** It's the fallback for companies not in
Damodaran's list. His list records a SIC code and an industry for about 48,000 companies,
about 6,000 of them US.
- **The starting point:** for each of SEC's 444 SIC codes, the industry most of his US
  companies with that code are in. Global companies were used where there were fewer than
  3 US ones.
- **Matched by description:** where his companies were split or thin, the industry was
  chosen by matching the SIC description to Damodaran's industry names.
- **Not mapped:** 6 non-operating codes (blank checks, ADRs and the like). They fall back
  to beta 1.0.
- **Flagged:** 192 rows carry a `review_note`. A company that falls back to a flagged row
  gets a note saying so.

## 4. Reliability and limits

- **yfinance is unofficial.** It reads Yahoo Finance's website endpoints, can break when
  Yahoo changes them, and can be rate-limited ("Too Many Requests"). On a price failure the
  ticker is skipped with a message; use `--price`. Prices more than 7 days old are flagged.
  Yahoo's terms limit the data to personal use.
- **SEC requires a real name and contact email** in the User-Agent of every request, and
  allows up to 10 requests a second. Requests here are spaced 0.2 s apart. A run makes 1
  request for the ticker list, plus 2 per ticker (the company facts and the submissions
  record).
- **The SEC cache:** responses are kept in `cache/sec/` for a day (`SEC_CACHE_MAX_AGE_DAYS`),
  so a filing made today shows up tomorrow. `cache/` can be deleted at any time to force
  fresh downloads.
- **SEC's XBRL data can miss a filing.** SEC's company facts have been seen to miss a
  filing whose own XBRL had the data (Duke Energy's 10-Q for the quarter ended 2026-06-30).
  The script compares the latest 10-Q/10-K in the submissions record with the end of the
  TTM. If the filing is later, a note says the TTM is at least a quarter behind. The
  missing quarter isn't filled in from the filing.
- **Stale EPS:** a latest reported quarter that ended more than 140 days ago
  (`STALE_EPS_DAYS`) is flagged. Before a 10-K arrives (60–90 days after year-end), the
  latest quarter can be 150–180 days old, so the note can fire for normal filers then. The
  filing-gap check above is the precise signal.
- **Damodaran's files** are free spreadsheets updated each January, with no API contract.
  If a layout change breaks parsing, the download is rejected and the fallbacks in section
  3 apply. The company list is a January snapshot, so newer listings fall back to the SIC
  mapping.
- **FRED's** CSV download needs no key. The yield is usually the previous business day's.
- **Company tickers only.** Foreign filers reporting under IFRS (20-F/40-F) have no US-GAAP
  EPS in SEC's data and are skipped, as are companies with fewer than four reported
  quarters.

## 5. Earnings-quality notes

**Possible one-time item.** A TTM quarter is flagged if it either:
- is negative while the other three are positive; or
- differs from the median of the four by more than 50% of the median's absolute value
  (`ONE_TIME_DEVIATION`). This test is skipped if the median is exactly 0.

One or two flagged quarters each get a note, naming the quarter end and whether it was a
derived Q4. Three or more (`ERRATIC_MIN_FLAGS`) get one note instead: "erratic earnings;
trailing EPS unreliable".

**The flag is a warning, not a filter,** and never changes the numbers. EPS alone can't
tell a one-off from a real change. It flags seasonal holiday quarters, real growth
spurts, and quarters next to a real one-off (which distorts the median), and it misses
one-offs that are under 50% of normal. Near-zero EPS makes it fire often. The company's
earnings release says which it was.

**TTM sign depends on one quarter.** If removing the largest-magnitude quarter flips the
sign of TTM EPS, a note names that quarter and says the growth share is unreliable.

**Lag warning.** When raw TTM EPS is more than 25% above or below the 2-year EPS
(`LAG_WARNING`), a note says a one-off may sit in the TTM, or the 2-year EPS may lag a
real change in earnings.
- The size is in `ttm_vs_two_year_pct`.
- Ordinary growth stays well under 25%: 30% a year gives about +13%.
- The history chart marks those points `!` and lists them in one note (section 7).
- It's a pointer, not a judgment: the earnings release says which it was.

## 6. R&D-adjusted reading

**The R&D-adjusted growth share** is a secondary line, printed under the main one. It
treats R&D as an investment rather than an expense, the capitalization approach best known
from Damodaran, so steady-state earnings aren't depressed by spending on future products.

```
R&D-adjusted EPS = EPS used + (current R&D − amortization) ÷ diluted shares
amortization     = R&D of the prior N twelve-month periods ÷ N        (N = 5 by default)
```

1. **Current R&D** covers the same TTM window as the EPS. Q4 is derived as annual − (Q1 +
   Q2 + Q3).
2. **Amortization** is straight-line over N years.
   - N is `RD_AMORTIZATION_YEARS` (5, in `pvgo_inputs.py`); `--rd-life` changes it for a
     run.
   - The prior periods are the twelve-month windows ending 1, 2, … N years before the TTM
     end, built from quarters or taken from the 10-K's annual figure. A window may end
     within 10 days of the target date.
   - The current year's R&D isn't amortized in the year it's spent.
3. **Per share:** the difference is divided by the weighted-average diluted share count.
   - Tag: `WeightedAverageNumberOfDilutedSharesOutstanding`, falling back to
     `WeightedAverageNumberOfShareOutstandingBasicAndDiluted`.
   - The count is the average of the TTM quarters' 3-month figures; the fiscal year's
     figure stands in for a derived Q4. Counts filed before a split are multiplied by its
     ratio.
   - If some quarters have no count, the others are averaged; if none has one, the fiscal
     year's count is used. Each with a note.
4. **No tax adjustment by default.** The difference is added back pre-tax, as Damodaran
   does: the full tax deduction for R&D was a real benefit. To tax-effect it, set
   `RD_TAX_RATE` in `pvgo_inputs.py` (e.g. 0.21).
5. **Same inputs otherwise:** the price and cost of equity are the main reading's.

**Five years is a simplification.** Damodaran uses industry-specific lives, longer for
pharma than for software. For a company whose R&D keeps growing, a longer life lowers
amortization and raises the adjustment.

**Columns:**
- `rd_current`: R&D (USD) in the window named by `rd_basis`, normally "TTM ending <date>".
- `rd_amortization`: the prior N periods' R&D ÷ N (USD), or the average of the available
  ones.
- `rd_life_years`: N.
- `rd_effective_life_years`: how many prior years were actually averaged; blank when not
  computed or there's no R&D.
- `rd_diluted_shares`, `rd_adjustment_per_share`, `eps_rd_adjusted` (`eps_used` + the
  adjustment), `growth_share_rd_adjusted_pct`.

**R&D tags,** tried in this order and merged period by period (some companies switch; the
first tag wins where a period has both):

| Tag | Companies using it (calendar 2024 annual figures, SEC frames API) |
|---|---|
| `ResearchAndDevelopmentExpenseExcludingAcquiredInProcessCost` | 137 |
| `ResearchAndDevelopmentExpense` | 2,543 |
| `ResearchAndDevelopmentExpenseSoftwareExcludingAcquiredInProcessCost` | 36 |

The "excluding acquired in-process" variant comes first, so one-time charges for R&D bought
in acquisitions stay out. A note names the tag whenever it isn't
`ResearchAndDevelopmentExpense`, or two tags were combined.

**Edge cases:**
- **No R&D tag** (banks, retailers, utilities): the adjustment is zero, and `rd_basis` says
  "no R&D expense in SEC's data". A company reporting R&D only under a custom tag, or inside
  another line, shows up the same way.
- **No quarterly R&D:** the latest fiscal year, ending within about 13 months of the TTM
  end, becomes the current figure, with a note.
- **R&D stopped appearing** (none in the last ~13 months): not computed, with a note.
- **No diluted share count:** not computed, with a note.

**Missing prior years** are handled in three steps:
1. **Annual split.** A window is estimated from the fiscal-year totals it overlaps, split in
   proportion to days, when those years cover it. A note names such windows. (E.g. Reddit,
   public since March 2024: the twelve months ending June 2023 are about half of fiscal
   2022 plus half of fiscal 2023.)
2. **Average fill.** Windows still missing are filled with the average of the available
   ones: in effect a K-year life, which the note and `rd_effective_life_years` report. For
   a company whose R&D was growing, this slightly overstates amortization.
3. **Minimum.** With fewer than 3 available prior years (`RD_MIN_PRIOR_YEARS`, or the whole
   life if it's shorter), the reading shows n/a, with a note.

**When it matters:** with steady R&D, current R&D roughly equals amortization and little
changes. Growing R&D raises adjusted EPS and lowers the growth share, most where R&D grows
fast.

**Not included:**
- **SG&A, brand or organization capital.** How much of SG&A is investment is a judgment
  call: Peters & Taylor capitalize 30%, Eisfeldt & Papanikolaou all of it, and other work
  estimates it by industry. SG&A tagging is also inconsistent.
- **A NOPAT/WACC rewrite.** The adjustment stays inside the equity framework.

## 7. PVGO history chart (`pvgo_history.py`)

`python pvgo_history.py <ticker> [<ticker> ...] [--days N] [--eps-basis B ...]
[--erp X | --erp-by-year] [--market-beta | --own-beta] [--raw-beta] [--release-items]
[--smooth weekly|monthly|yearly]` charts the last 365 days, or N. Or set `TICKER` and
`YEARS` at the top of the runner and run it.

It plots the daily close against the no-growth value per share (EPS ÷ cost of equity), on
the adjusted TTM EPS by default. The gap between the two lines is PVGO.
- **Each earnings release** is a dotted line, labelled "8-K <release date> / EPS through
  <quarter end>". When labels would overlap (multi-year windows), each is the release date
  alone, written vertically.
- **A right-hand axis** shows the daily growth share: 1 − no-growth value ÷ close, from the
  line as drawn. At each measurement date it equals the growth share in the points table.
- **The calculation** reuses `pvgo_growth_share.py` for the EPS, industry, beta and result at
  each point, with an `as_of` option that builds each TTM only from facts filed by a given
  date.

**The series for an explanation run.** The root `main.py` (step 2) runs:
```
python pvgo_history.py <TICKER> --days <N> --own-beta --erp <X> --release-items
```
- the adjusted TTM (the default basis), the company's own beta, and the press-release
  tables that `explain_run.py` reads;
- a fixed ERP, X = the average of Damodaran's January estimates for the period's years
  (below). For a 2024 run, the January 2024 estimate alone: 4.60%; for 2023–2025,
  (5.94 + 4.60 + 4.33) / 3 = 4.96%;
- a window starting about 13 months before the period (N = the days back to the period's
  start + 400), since `explain_run.py`'s market model is fitted on the 180 trading days
  before each day, from prices that start where the series does.

**The runner** (`pvgo_history_run.py`) holds the same settings for COST, over 5 years, with
monthly smoothing on the chart. Set `RELEASE_ITEMS = True` there for the press-release
tables.

**Earnings release dates** come from the SEC submissions API.
- **Cutoff:** for each fiscal quarter in SEC's XBRL data, the filing date of the original
  10-Q/10-K (not a /A) whose reportDate is within 7 days of the quarter end.
- **Release date:** the first 8-K with item 2.02 ("Results of Operations") filed after the
  quarter end and on or before the cutoff. Without one, it's the cutoff itself.
  `release_form` records which filing set it (8-K, 10-Q or 10-K), and `release_time` when
  SEC accepted it, in New York time.
- **More than one earnings 8-K:** the point's notes name them. The step uses the first,
  which would be early if it were a pre-announcement of partial results.
- **The EPS figures** come from the 10-Q/10-K as of the cutoff, since the 8-K's press
  release isn't machine-readable. They're assumed to match what the release announced.
- **Older filings:** when SEC's recent filing list doesn't reach back far enough, the older
  filing files are loaded too, and cached in `cache/sec/` for 30 days
  (`SEC_FILING_PAGES_MAX_AGE_DAYS`). JPM's 15-year chart needs 65 pages, about 23 MB.
- **Not in XBRL yet:** a newer quarter with an 8-K or 10-Q but no XBRL facts gets no step.
  The previous TTM is kept, with a note.

**Measurement date:** the first trading day whose close comes after the release was
public, from Yahoo's daily history and SEC's acceptance time.
- **Accepted before the 4:00 pm close on a trading day:** that day. JPM files around 6:45
  am, so it's measured on the release day.
- **Otherwise:** the next trading day. Microsoft files around 4:05 pm, and Costco in the
  evening (about 8–9:40 pm), so both are measured the next day.
- **Without an acceptance time:** the first trading day after the release date.
- **Today counts only after the close.** Before that, the release gets no step yet.
- **A limit:** a press release out during the session, with its 8-K accepted after the
  close, is measured the next day, after the price has reacted. explain_run's release
  entries look from the release date to the measurement date to cover both days.

**Point-in-time TTM EPS.** Each point's TTM uses only XBRL facts filed on or before its
cutoff, keeping the latest remaining value per period, so later restatements don't leak
back. Staleness is judged against the measurement date. Two exceptions keep the step at the
original release date, marked `~` in the table and noted on the point and in the chart
footnote:
- **Amendment:** when SEC's data credits a quarter's figures to an amendment (10-Q/A,
  10-K/A) filed within 45 days of the original, the amendment is used.
- **Pre-XBRL backfill:** SEC's XBRL data began in 2009–2011, depending on company size. A
  release whose TTM reaches back before the company's first XBRL EPS takes its numbers from
  the earliest later filing that reports those quarters. The release dates are real; the
  numbers match what was announced unless the company later restated those periods.
- Releases whose TTM can't be built even from later filings are skipped, and summarized in
  one note.

**Stock splits.** Yahoo's close (`auto_adjust=False`) is split-adjusted, so each XBRL fact
is divided by the product of the split ratios dated after its filing date, before quarters
are summed or Q4 is derived. A note says so whenever it applies.

**Cost of equity:** the 10-year Treasury plus beta × ERP.
- **Treasury:** FRED DGS10, fetched for the whole range in one request. Each date uses the
  last value on or before it.
- **By default, beta and ERP are held at today's values,** as in `pvgo_growth_share.py`
  (with `--market-beta` and `--erp`). The line then moves only with the Treasury between
  releases.

**Fixed or year-by-year ERP.**
- **The explanation runs use a fixed ERP:** the average of Damodaran's January estimates
  for the period's years, from `damodaran_implied_erp.csv` (4.60% for 2024; `ERP_PCT`
  in the runner, `--erp` on the command line).
- **`--erp-by-year`** (`ERP_BY_YEAR = True`, with `ERP_PCT = None`) follows Damodaran's
  implied ERP at each date instead.
  - **Source:** `damodaran_implied_erp.csv`, kept by hand: one row per January from 1962,
    from the "Implied ERP (FCFE)" column of his `histimpl.xls`. His table labels each row by
    the year that just ended, so his row 2011 (6.01%) is entered as `2012-01-01`. Add a row
    each January.
  - **Between rows:** straight-line interpolation; after the last row, that row's value.
    His table gives 4.23% for the start of 2026, against the hand-set default of 4.14%.
  - **Use it for long windows,** such as year-end comparisons with Counterpoint: holding
    today's ERP over a long window understates past costs of equity.
  - **Don't use it for daily explanations:** mid-year values move toward the next January's
    estimate, which is computed from that December's prices. That is a smooth drift nobody
    could have known at the time.

**Own beta (`--own-beta`, `OWN_BETA = True`).** The company's own beta, re-estimated each
month from prices known then, instead of today's industry beta.
- **Regression:** the slope of the stock's monthly total returns (Yahoo's dividend-adjusted
  close) on the S&P 500's (`^GSPC`), over the 60 calendar months ending at each month's last
  trading day (`OWN_BETA_MONTHS`). A month counts once it's over.
- **Blume adjustment:** 0.67 × slope + 0.33 (`BLUME_WEIGHT`), as Bloomberg's "Adjusted
  Beta". It moves every beta a third of the way to 1.0, for estimation error and for betas
  drifting toward 1.0 over time. `--raw-beta` (`BLUME_ADJUST = False`) uses the slope as is.
- **Too little history:** under 36 monthly returns (`OWN_BETA_MIN_MONTHS`), the industry
  beta is used, with a note.
- **Where it shows:** a beta column in the terminal table; `beta_raw` (the slope),
  `beta_scaled` (the beta used) and `beta_source` in the points CSV; "own beta" in the chart
  title.
- **Scope:** only the history chart. `pvgo_growth_share.py` keeps the industry beta.

**Line points:**
- at each measurement date, a vertical step from the old EPS to the new one, at that day's
  yield;
- in between, a point on each week's last trading day;
- a point on the window's first trading day, one at the latest close, and one on each
  completed year's last trading day (labelled `year-end`).

All releases measured inside the window are shown, and so is the last one before it, which
sets the line's level at the left edge (marked `*` in the table).

**EPS basis** (`--eps-basis`, one or more, or the runner's `PLOT_*` switches):
- **`ttm_adjusted`** (the default): the adjusted TTM EPS of section 2.
- **`ttm`**: raw TTM diluted EPS, for comparison.
- **`two_year`**: the trimmed 2-year EPS, for comparisons with Counterpoint.
- **`six_month`**: the 6-month EPS. Its line swings within each year.
- **`rd_adjusted`**: the adjusted TTM plus the R&D adjustment of section 6, from R&D and
  share-count facts filed by each quarter's 10-Q/10-K.

Where a basis can't be computed at a point, the table shows TTM EPS for that point, marked
`+` with a note. The chart and the series CSV leave that basis out for the period the point
covers, so a fallback never sits on top of the TTM line.

**File names:** a basis other than raw `ttm` adds its name, e.g.
`WMT_pvgo_history_ttm_adjusted_series.csv`. The rule is pinned to `ttm`, not to the default,
so the unsuffixed files always hold raw TTM.

**Several bases in one chart:** each gets its own no-growth line (solid) and growth-share
line (dashed), in one color, without the PVGO shading. Each still gets its own CSVs. A line
identical to an earlier one's is drawn dotted on top of it, with "same as ..." in the
legend.

**Lag marks:** points where TTM EPS is more than 25% from the 2-year EPS are marked `!` in
every version's table, and listed in one note (section 5).

**Press-release items (`--release-items`, `RELEASE_ITEMS`).** These write
`<TICKER>_pvgo_history_release_items.csv`, one row per release shown: `quarter_end,
release_date, release_form, accession, filing_url, exhibits, n_tables, reconciliation_text,
item_sentences, item_dollar_sentences, diluted_shares, note`. `explain_run.py` reads it to name the one-time items behind each EPS
step, and the website links each release's evidence to its filing (`filing_url`: the
filing's EDGAR index page; the exhibits are files in the same folder). A company names its items in a reconciliation table, in its text, or both, so both are
kept.
- **How it's fetched:** one SEC request per release, for the filing's complete submission
  text. It's cached in `cache/sec/` for good, since a filing never changes.
- **What's kept:** the `EX-99` exhibits, `EX-99.1` (the press release) first. Every HTML
  table matching "adjusted EPS", "adjusted earnings per share" or "non-GAAP EPS" is kept, in
  document order, as `cell | cell` lines (at most 6,000 characters per release). Tables with
  any cell over 200 characters (text laid out as a table) are skipped.
- **Item sentences (`item_sentences`):** from the same exhibits, with their number tables
  dropped (text laid out as a table is kept), every sentence that has both a per-share amount
  ("$0.22 per diluted share", "$0.14/diluted share", "5 cents a share") and an item word
  (non-recurring, one-time, discrete, charge, benefit, gain, loss, impairment,
  restructuring, settlement, write-down or write-off, severance, litigation, unusual, special
  item). One per line, EX-99.1 first, no exact repeats, at most 1,500 characters per release.
  Fragments over 500 characters are skipped: they're slide text run together, not sentences.
  - **Why:** companies that report only GAAP EPS have no table but often state their items
    in a sentence. Costco does: "a tax benefit of $100 million, $0.22 per diluted share,
    related to stock-based compensation."
  - **Prior-year items come too** ("Last year's results included…"). They name an item that
    is leaving the TTM.
- **Dollar-only sentences (`item_dollar_sentences`):** the same exhibits' sentences with an
  item word and a dollar amount ("$780 million", "$4.20 billion") but no per-share amount, in
  the same form and limits.
  - **Why:** some companies that report only GAAP EPS state their items in dollars alone.
    Meta: "This includes accrued legal expenses of $1.87 billion and restructuring charges of
    $780 million in the second quarter of 2023."
  - **Outlooks and estimates are left out:** a sentence with "expect", "outlook",
    "estimate(d)", "forecast" or "guidance" ("This outlook includes approximately $4 billion
    of restructuring costs").
  - **Still in:** a total and its parts (the same charge by segment, or the severance within
    the restructuring), full-year figures beside the quarter's, and older items cited in a
    footnote (a 2020 settlement in a free-cash-flow note). The release call keeps each item
    once and only the step's two quarters (Company_Narrative_Aggregation METHODOLOGY §7).
- **`diluted_shares`:** the quarter's weighted-average diluted share count, as filed by its
  cutoff and on today's share basis (`quarter_diluted_shares`): its 3-month figure, or the
  fiscal year's for a quarter without one (a Q4, reported only in the 10-K).
  Company_Narrative_Aggregation divides a dollar-only item by it.
- **Limits:**
  - It's a text match, not a parse: whole tables are kept for a model or person to read,
    including prior-year, year-to-date and guidance tables. The sentences can include a
    headline EPS sentence with "loss" or "benefit" in it, and a near-repeat from the slides
    (Costco's EX-99.2 repeats EX-99.1's items).
  - An item under a table label the pattern misses ("core EPS", "comparable EPS"), stated in
    neither per-share nor "$ million/billion" terms, or stated only inside a number table (Meta's
    restructuring table by activity) isn't found. Neither is an item the release doesn't
    mention at all: a 10-Q may name items the release left out.
  - The outlook filter is a word match: a sentence about the quarter's own item that also says
    "expected" is dropped with the outlooks.
  - A Q4's share count is the fiscal year's average, not the quarter's (Meta's Q4 2022: 2.70B,
    the year's), which is off by however much the count moved during the year.
  - Gaps are recorded in `note`, never raised: a release made by a 10-Q, no `EX-99`, no
    matching table or item sentence, or a failed fetch.

**Smoothing (chart only).** `--smooth weekly`, `monthly` or `yearly` (the runner's
`SMOOTHING`) draws each line as a centered moving average of 5, 21 or 252 trading days. The
tables and CSVs keep the daily values, and the measurement dots stay at the actual close.
- **Weekly and monthly:** the no-growth average doesn't reach across a measurement date, so
  the steps stay sharp.
- **Yearly:** the no-growth average does run across releases, to show the long-run trend.
  A change then shows up to six months before and after it happened.
- **The price average always runs across releases,** so a large earnings-day jump shows as
  a ramp, and the dots can sit off the smoothed line.
- **The growth share** is computed from the smoothed lines, so it matches the gap as drawn.
- Near the window's edges, and next to a step (weekly and monthly), the average covers only
  one side.

**Outputs** (charts in `PVGO_Collection/`, CSVs in `Outputs_CSV_data/`; gitignored, since
every run regenerates them). Each name below carries the basis after `_pvgo_history`, except
for raw `ttm` (see "File names" above): the default run writes
`<TICKER>_pvgo_history_ttm_adjusted.png`, `<TICKER>_pvgo_history_ttm_adjusted_series.csv`
and so on. The release items file (above) has no basis in its name.
- `<TICKER>_pvgo_history.png`: the chart.
- `<TICKER>_pvgo_history_points.csv`: `pvgo_growth_share.py`'s full result at each
  measurement date, with `pvgo_results.csv`'s columns plus `quarter_end`, `release_date`,
  `release_time` (New York), `release_form`, `release_accession`, `cutoff_date`,
  `measurement_date`, `eps_basis` (the version's, or `ttm` where it fell back) and
  `eps_charted` (blank where the basis wasn't charted). The R&D columns are filled only
  with the `rd_adjusted` basis.
- `<TICKER>_pvgo_history_series.csv`: one row per trading day, with the close,
  `no_growth_value` and `growth_share_pct`.
  - `no_growth_value` is the line as drawn: linear between its points, after any step that
    day. On measurement dates, `no_growth_value_before_step` holds the old level.
  - `point` marks the line's own points (start, weekly, year-end, measurement or final). The
    `eps`, `eps_basis`, `eps_through`, Treasury, `erp_pct`, `beta` and cost-of-equity
    columns are filled only on those days. `explain_run.py` splits rates/other by them.
- `<TICKER>_pvgo_history_year_end.csv`: the reading at each completed year's last trading
  day (`year`, `date`, `close`, `no_growth_value`, `growth_share_pct`, `eps`, `eps_basis`,
  `eps_through`, `treasury_10y_pct`, `beta`, `erp_pct`, `cost_of_equity_pct`).
- `<TICKER>_pvgo_history_year_end.png`: those year-end growth shares as a line, one per
  version, when the window holds two or more year-ends. That's the format of Counterpoint's
  company charts.

**Comparing with Counterpoint's company charts.** Use `--own-beta --erp-by-year
--eps-basis two_year`, and compare the year-end chart or CSV. These settings fit their JPM
and MSFT charts best, and the own beta does most of the work.
What's left: consensus forward EPS runs ahead of trailing EPS for a growing company, so a
grower such as MSFT reads several points high in most years.

## 8. Credentials and cost

All free, with no API keys. The only setting is `SEC_EDGAR_USER_AGENT` in `.env` (copy
`.env.example`): your name and contact email, which SEC requires. It isn't a secret.
