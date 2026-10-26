# Deconstructing PVGO moves

How much of a stock's price is the market paying for growth, and why does that share
change?

This project builds a daily, point-in-time series of a company's **growth share**:
PVGO / price, the part of the price that today's earnings, held flat forever, don't
explain. It splits each day's change into its mechanical parts (new earnings, interest
rates) and the part driven by the share price. Then it uses LLMs to read the news behind
the price-driven moves. Everything runs on free data; only the model calls are paid, at
cents per company-year.

**Example outputs:** [the project site](https://drummond456.github.io/Company_Growth_Narratives/) shows the
pipeline's output for two companies, Costco (COST) in 2024 and Meta Platforms (META) from
September 2022 to August 2023: an interactive PVGO chart with a month slider, beside each
month's explanation. The source is in [`website/`](website/).

## How it works

Three folders, one per stage. Each has its own `METHODOLOGY.md` with the full method and
the data's limits. The root `main.py` runs them in order.

1. **`News_Collection`** pulls the company's articles from Media Cloud, one list per
   month: CNBC, Yahoo Finance and Fortune, chosen because their full text can be fetched.
   The headline must contain one of the company's search terms.
2. **`PVGO_Collection`** computes the growth share from free sources. EPS comes from SEC
   XBRL filings, point in time and split-adjusted. It also uses the FRED 10-year Treasury
   and Yahoo prices. Release timing comes from 8-K acceptance times, and the one-time
   items each press release names, in its adjusted-EPS table or its text, are read from it.
3. **`Company_Narrative_Aggregation`** has two stages.
   - `extract_run.py` turns each month's articles into short verbatim statements tagged
     with value-driver codes.
   - `explain_run.py` builds the daily bridge, cuts each month into periods labelled by
     how much the market explains, and explains every period. This is the main output:
     an `explanations.md` per run, with the same content as tables.

### The math

```
growth share     = 1 − no-growth value / price
no-growth value  = EPS / cost of equity
cost of equity   = 10-year Treasury + beta × equity risk premium

daily change     = price-driven   100 × V₀ × (1/P₀ − 1/P₁), split into market and company-specific
                 + EPS update     the step at an earnings release
                 + rates/other    Treasury and beta
```

The market part comes from a rolling regression of the stock's return on the S&P 500
and a sector ETF, fitted on the prior 180 trading days only. Each month is cut into
periods that cover every trading day: a day whose company-specific return is at least 2.5×
its trailing 60-day volatility stands alone, and the rest is cut into swings of the
price-driven path. Each period is labelled by the market's share of its move,
|market| ÷ (|market| + |company-specific|): **market-driven** at 70% or more; **within
noise** when the company-specific move is under 1.5× its normal size; otherwise
**outlier** at 30% or less, and **divergent** in between.

Each month's bridge adds up exactly: the growth share's change = market +
company-specific + each release's EPS update + Treasury + beta.

### What the LLMs do

- **Extraction** (Qwen3-235B on DeepInfra, real time; about a cent per month of news for a
  large company).
  - For each article, the model picks up to three sentences that summarize its news about
    the company. It answers with sentence numbers, so every quote is verbatim by
    construction.
  - It tags each sentence against a value-driver codebook, enforced by a JSON schema.
  - Free Python screens first drop duplicate stories, stock-pick and price-target pages,
    and shopping listicles.
- **Explanation** (Claude Sonnet, Message Batches; about $0.005 per period and $0.003 per
  earnings release).
  - **Each period** gets one call, the *period* call: it reads the period's news and the
    stock's own moves, but not the market's, and says what changed in expectations
    (confidence: high/medium/low/none).
  - **A built-in placebo check.** The news is company-specific, so a cause found in a
    market-driven or within-noise period is suspect. The output marks those, and counts how
    often the period call finds them against divergent and outlier periods.
  - **Each earnings release** gets one call, which only extracts the one-time items the
    press releases name in the step's two quarters: amount per share (or in dollars, where
    the release gives no per-share figure), entering or leaving the TTM, benefit or charge.
    Code checks each amount against the press-release text, puts a dollar amount per share
    (an estimate: less 25% tax, over the quarter's diluted shares), and computes the TTM EPS
    change less them. Whether the release was a "results surprise" or
    "results expected" is code too: the company-specific move against 1.5× its normal
    noise.
- **Guardrails.**
  - Structured outputs, validated with Pydantic.
  - Every cited cause traces to a statement ID, an article and its outlet. The IDs
    (`<month>/<article>-<statement>`, e.g. `2024-03/A0106-S02`) are in the `evidence` column
    of `periods.csv`, and in brackets after each cause in `explanations.md`. The
    month's `narrative_units.csv` (by `unit_id`) holds each statement's text, headline, URL
    and outlet. Release blocks cite their press releases (`R2024-03-07`), which the project
    site shows with their one-time item lines and a link to the filing on EDGAR.
  - A cost estimate and a confirmation come before any paid call; `--dry-run` calls
    nothing.
  - Runs are resumable, so an interrupted run never pays twice.

## Design choices

- **Trailing GAAP EPS, with one-time items kept in.** Only gains and losses on
  investments are removed, less a flat 25% tax, since a mark-to-market swing isn't
  earnings that recur.
  - Legal charges and restructuring stay in. Whether the market "looks through" a
    one-time charge is itself an expression of expectations, and a run of "one-offs" is a
    pattern. So each charge is kept, and each release block names it, with the TTM EPS
    change less it and the price reaction beside it.
  - The cost: levels are distorted while a charge sits in the TTM. Each release block
    names the items entering and leaving it.
- **Point in time.** At each release, EPS is built only from the filings available then.
  The step is dated by the 8-K's acceptance time. Beta uses only prices known at each
  month end.
- **Cost of equity.** The 10-year Treasury, daily, plus the company's own beta times a
  fixed equity risk premium.
  - The beta uses 60 monthly returns against the S&P 500, Blume-adjusted toward 1.0.
  - The ERP is the average of Damodaran's January implied estimates for the period's
    years. A year-by-year ERP interpolated between his January estimates would use the
    next year's figure mid-year, so the explanation runs hold it fixed.
- **The sector ETF follows a fixed rule:** the equal-weight S&P 500 fund of the company's
  GICS sector (RSPS consumer staples, RSPT technology, RSPC communication services, and so
  on), not the fund that fits best, which would be chosen with hindsight.

## Limitations

- **The level depends on the inputs.** A 1pp change in the cost of equity moves the growth
  share by (1 − growth share) / cost of equity: about 3pp for a stock with a 75% growth
  share and an 8% cost of equity. "No growth" means zero *nominal* growth, so part of the
  growth share is just keeping pace with inflation.
- **The market/company split depends on the factors chosen.** The sector ETF keeps
  market-wide days out of the company-specific part, but it also counts sector-wide news
  as market. Two funds that fit about equally well can split a year quite differently.
- **The causes are the model's reading of the news, not tested one by one.** The period call
  sees the move, so it can fit a story to it:
  - a fall after good news reads as "priced in" or "sell the news", which fits any such
    fall; nothing in the inputs says what was expected beyond what the articles quote;
  - an article recapping older results can be credited to a later day. The dates of the
    cited statements show it.

  The placebo check measures how often this happens. The model may also remember the
  period from its training; it's told to use only the statements.
- **The news is selected by headline.** Articles come from three outlets (Yahoo Finance
  carries wire copy), and the headline must contain a search term. Sector news is missed,
  and there are no earnings-call transcripts.
- **Returns have fat tails.** Moves beyond 3σ happen several times as often as a normal
  distribution predicts, so a move off an earnings day without a cause in the news may be
  noise.
- **There are no automated tests yet.**

## Run it

Python 3.12, one virtual environment for the whole project. Each folder has a
`.env.example` for its keys. Media Cloud and SEC EDGAR are free; DeepInfra and Anthropic
are pay-per-use.

```bash
# Setup, once, at the project root
python -m venv .venv
.venv\Scripts\activate          # Windows; on macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
# Then copy each folder's .env.example to .env and fill it in:
#   News_Collection: MEDIACLOUD_API_KEY    PVGO_Collection: SEC_EDGAR_USER_AGENT
#   Company_Narrative_Aggregation: DEEPINFRA_API_KEY and ANTHROPIC_API_KEY

# One company, end to end: the news, the growth share, the statements and the explanation
python main.py --ticker <TICKER> --search-terms <Name> "<Other name>" --sector-etf <ETF> --start <YYYY-MM> --end <YYYY-MM>
```

`main.py` runs the four steps below in turn. Each paid step shows its estimated cost and
asks before spending. Pulling the news takes a while, mostly waiting out Media Cloud's
rate limit, and so does fetching the articles' text (in step 3, before its cost is
shown).
- **Search terms are separated by spaces;** put a term with a space in quotes.
- **The ticker is searched for only if you list it.** List it only when it's distinctive
  in a headline: `MSFT` is, but `COST` would match every headline about costs. For
  Microsoft: `--ticker MSFT --search-terms MSFT Microsoft --sector-etf RSPT`.
- **The terms are saved** in `News_Collection/pulls/<ticker>/search_terms.csv`, so later
  runs can leave `--search-terms` out.
- **A new company also needs its sector ETF** (`--sector-etf`) for the market model, by the
  rule above. It's saved in `Company_Narrative_Aggregation/explain_subjects.json`.
- **Rerunning the same command continues where it stopped.** The months already pulled or
  extracted are skipped.
- **`--dry-run`** runs the free steps, and prices the paid ones without calling the models.
- **`--steps`** runs only some of the steps, e.g. `--steps news pvgo`.

The steps it runs, each usable on its own (`<ticker>` in lower case):

```bash
# 1. News (free): one CSV per month in News_Collection/pulls/<ticker>/, with its search_terms.csv
cd News_Collection
python news_pull.py --ticker <TICKER> --search-terms <Name> "<Other name>" --start <YYYY-MM> --end <YYYY-MM>

# 2. The growth share's daily history (free): adjusted TTM EPS, the company's own beta, the
#    ERP averaged over the period's Januaries, and the press-release tables. --days counts
#    back from today and should reach about 13 months before the period, for the market
#    model (main.py computes it).
cd ../PVGO_Collection
python pvgo_history.py <TICKER> --days <N> --own-beta --erp <ERP %> --release-items

# 3. Statements (paid): one run per month, in runs/<ticker>_<first>_<last>/
cd ../Company_Narrative_Aggregation
python extract_run.py --pull-dir ../News_Collection/pulls/<ticker> --subject "<Name> (<TICKER>)" --from <YYYY-MM> --to <YYYY-MM>

# 4. The explanation (paid): --dry-run first for the free part, the bridge and the periods
python explain_run.py --runs runs/<ticker>_<first>_<last>
```

More commands (resume, update, `--ask`) are in
[`Company_Narrative_Aggregation/commands.txt`](Company_Narrative_Aggregation/commands.txt).

**What's in the repo:** the article lists, monthly runs and explanation behind each of the
project site's examples (`News_Collection/pulls/`, `Company_Narrative_Aggregation/runs/`).
The fetched article text isn't included, so re-running an explanation on them reads
slightly less than the original run did (Company_Narrative_Aggregation METHODOLOGY §4).
PVGO_Collection's series are regenerated by step 2.

## Data and terms

- **Article text isn't redistributed.** The repo keeps the article lists (headline, URL,
  outlet) and the statements: at most three verbatim sentences per article, each traced to
  its URL. The fetched pages and the requests that carried them are gitignored. The project
  site shows only the statements the explanations cite, each with its article's headline
  and link.
- **Prices come from Yahoo Finance via `yfinance`,** an unofficial interface. Yahoo's
  terms limit the data to personal use; the run outputs include daily closes
  (`market_prices.csv`, `pvgo_daily.csv`), and the project site charts them
  (`website/data/<page>/series.csv`).
- **SEC EDGAR, FRED and Damodaran's datasets** are free public sources.

## How it was built

Built with Claude Code as a coding assistant. [`CLAUDE.md`](CLAUDE.md) holds the project
instructions it works from. Each folder's `METHODOLOGY.md` describes the current method and
its limits.

## Next steps

- An EPS basis without one-time items, built from the press-release reconciliations
  already collected.
- Explaining the drift: consensus estimate revisions, style factors (momentum, low
  volatility) and themes tracked across months.
- Consensus estimates at each release, so a "priced in" cause can be checked against what
  was expected.
- An out-of-sample test of the period call, on a period after the model's training cutoff.
- More companies and longer periods, and automated tests.
