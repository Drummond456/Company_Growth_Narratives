"""PVGO inputs: both files' settings blocks and the raw data - SEC EDGAR (ticker map,
company facts, submissions profile), the price (latest and daily), the S&P 500 and
the 10-year Treasury. METHODOLOGY section 2.
"""

from __future__ import annotations

import bisect
import csv
import io
import json
import math
import os
import re
import time
from dataclasses import dataclass
from datetime import date, time as clock_time, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
import requests


EQUITY_RISK_PREMIUM = 0.0414  # default ERP; --erp overrides it
MARKET_BETA = 1.0  # used with --market-beta and as the fallback beta
ONE_TIME_DEVIATION = 0.50  # flag a TTM quarter this far from the median (x |median|)
ERRATIC_MIN_FLAGS = 3  # this many flagged quarters -> one "erratic earnings" note
LAG_WARNING = 0.25  # note when TTM EPS is this far above or below the 2-year EPS (x |2-year EPS|)
DAMODARAN_CACHE_MAX_AGE_DAYS = 30
DAMODARAN_RETRY_AFTER_DAYS = 1  # after a failed refresh (with a cache to fall back on), wait this long to retry
SEC_CACHE_MAX_AGE_DAYS = 1  # SEC ticker list, company facts and submissions record: reused for a day
SEC_FILING_PAGES_MAX_AGE_DAYS = 30  # SEC's older filing-list pages (pvgo_history_releases.py), which rarely change
RD_AMORTIZATION_YEARS = 5  # straight-line life for capitalized R&D; --rd-life overrides it
RD_TAX_RATE = 0.0  # 0 = add R&D back untaxed (Damodaran); e.g. 0.21 to tax-effect the adjustment
RD_MIN_PRIOR_YEARS = 3  # fewer prior years of R&D than this (or than the life, if shorter) -> n/a
# Adjusted TTM EPS (the EPS behind the growth share): TTM GAAP EPS without the
# gains and losses on investments (realized and unrealized; ASU 2016-01 runs equity marks through
# net income), less this flat tax, per diluted share. A mark-to-market gain isn't earnings that recur:
# divided by the cost of equity it became "permanent" no-growth value (Walmart's +$3.8B in Q2 FY24).
# 25%: the US federal 21% plus a typical state rate, Damodaran's US marginal rate. Mechanical and the
# same for every company; Walmart's own reconciliations imply about 24%.
INVESTMENT_GAIN_TAX_RATE = 0.25
# SIC codes whose investment gains are operating income (banks, insurers, brokers): left unadjusted.
FINANCIAL_SIC = range(6000, 6800)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_DIR = os.path.join(BASE_DIR, "cache")
BETA_CACHE_PATH = os.path.join(CACHE_DIR, "damodaran_betas_us.xls")
COMPANY_CACHE_PATH = os.path.join(CACHE_DIR, "damodaran_companies_us.csv")  # US-exchange rows only
SEC_CACHE_DIR = os.path.join(CACHE_DIR, "sec")
SIC_MAP_PATH = os.path.join(BASE_DIR, "sic_to_damodaran_industry.csv")
OVERRIDES_PATH = os.path.join(BASE_DIR, "company_industry_overrides.csv")

SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SEC_FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"
SEC_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik:010d}.json"
FRED_DGS10_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv"
DAMODARAN_BETAS_URL = "https://pages.stern.nyu.edu/~adamodar/pc/datasets/betas.xls"
DAMODARAN_COMPANIES_URL = "https://pages.stern.nyu.edu/~adamodar/pc/datasets/indname.xls"

# Exchange prefixes in Damodaran's "Exchange:Ticker" column that are US venues.
# Ticker matching is limited to these: the same ticker exists on foreign
# exchanges for unrelated companies (e.g. ASE:MSFT, SET:BA). OTCNO is Norway's
# OTC list, not a US venue, so it's left out. OTCQX, OTCQB and ARCA have no
# rows in the January 2026 file; they're listed in case a later file uses them.
US_EXCHANGES = {"NYSE", "NasdaqGS", "NasdaqGM", "NasdaqCM", "NYSEAM", "OTCPK",
                "OTCQX", "OTCQB", "BATS", "ARCA"}
# R&D expense XBRL tags; for each period the first tag that has a value wins.
# Usage in SEC filings (CY2024 annual): 2,543 / 137 / 36 companies. The
# "excluding acquired in-process" variants rank first so one-time acquired
# IPR&D charges stay out; some companies switch tags over time (Eli Lilly,
# 2023), so periods are merged across tags.
RD_TAGS = ["ResearchAndDevelopmentExpenseExcludingAcquiredInProcessCost",
           "ResearchAndDevelopmentExpense",
           "ResearchAndDevelopmentExpenseSoftwareExcludingAcquiredInProcessCost"]
# Weighted-average diluted share count, for putting the R&D adjustment per share.
DILUTED_SHARE_TAGS = ["WeightedAverageNumberOfDilutedSharesOutstanding",
                      "WeightedAverageNumberOfShareOutstandingBasicAndDiluted"]
# Gains (+) and losses (-) on investments, for the adjusted TTM EPS; for each quarter the first tag
# with a value wins. Only investment-specific tags: the broad "other (gains) and losses" line
# (NonoperatingIncomeExpense) also holds recurring items, e.g. pension income. Seen in
# 2026-10: Amazon (Rivian) the first; Microsoft and Walmart (from FY24) the second; Walmart up to FY23
# the third (both from the cash-flow statement, year-to-date in 10-Qs); the last is a fallback
# (unrealized only, and Walmart's are rounded to $0.1B).
INVESTMENT_GAIN_TAGS = ["EquitySecuritiesFvNiGainLoss",
                        "GainLossOnInvestments",
                        "UnrealizedGainLossOnInvestments",
                        "EquitySecuritiesFvNiUnrealizedGainLoss"]
# Used for a quarter only after a fiscal year less 9 months across tags has been tried: rounded and
# unrealized-only at Walmart, whose 10-K kept the old cash-flow tag for FY24-FY25 while its 10-Qs used the new.
INVESTMENT_GAIN_FALLBACK_TAGS = {"EquitySecuritiesFvNiUnrealizedGainLoss"}
# Words ignored when comparing company names across SEC and Damodaran.
NAME_FILLER = {"the", "and", "inc", "incorporated", "corp", "corporation", "co", "company",
               "ltd", "limited", "plc", "llc", "lp", "sa", "nv", "ag", "se", "holdings"}

SEC_REQUEST_DELAY_SECONDS = 0.2  # SEC fair-access limit is 10 requests/second
NOTE_SEPARATOR = " | "  # between notes in the CSV's notes column
STALE_EPS_DAYS = 140  # warn if the latest reported quarter ended longer ago
STALE_PRICE_DAYS = 7

CAVEAT = (
    "Main way it misleads: the 2-year EPS lags a real, lasting change in earnings. After a sharp drop it overstates "
    "earnings power and understates the growth share, and the reverse after a jump. The TTM reading reacts sooner, "
    f"and a note flags TTM EPS more than {LAG_WARNING:.0%} away from the 2-year EPS."
)


@dataclass
class SecProfile:
    """What the SEC submissions API says about a company."""
    sic: Optional[int]
    sic_description: str
    latest_periodic: Optional[tuple[str, date, date]]  # (form, period end, filing date) of the latest 10-Q/10-K


# --------------------------------------------------------------------------
# Data sources
# --------------------------------------------------------------------------
def get_user_agent() -> str:
    """SEC fair-access policy: identify yourself (name + contact email)."""
    load_dotenv(os.path.join(BASE_DIR, ".env"))
    ua = (os.environ.get("SEC_EDGAR_USER_AGENT") or "").strip().strip('"')
    if not ua:
        raise RuntimeError(
            "Missing SEC_EDGAR_USER_AGENT. Copy PVGO_Collection/.env.example to .env and set "
            "it to your name and contact email -- SEC requires this on every request."
        )
    return ua


def _sec_get_json(
    url: str, session: requests.Session, user_agent: str, max_age_days: float = SEC_CACHE_MAX_AGE_DAYS,
) -> dict:
    """A JSON document from SEC, reusing the copy in cache/sec/ while it's
    younger than `max_age_days` (0 = always download). A download replaces
    the copy, so reruns the same day make no SEC requests."""
    path = os.path.join(SEC_CACHE_DIR, "_".join(url.rsplit("/", 2)[-2:]))  # e.g. companyfacts_CIK0000789019.json
    if max_age_days > 0 and os.path.exists(path) and time.time() - os.path.getmtime(path) < max_age_days * 86400:
        try:
            with open(path, "rb") as f:
                return json.loads(f.read())
        except ValueError:
            pass  # a damaged copy: download it again
    time.sleep(SEC_REQUEST_DELAY_SECONDS)
    r = session.get(url, headers={"User-Agent": user_agent, "Accept-Encoding": "gzip, deflate"}, timeout=30)
    if r.status_code == 403:
        raise RuntimeError("SEC returned 403 -- check SEC_EDGAR_USER_AGENT is a real name and email.")
    r.raise_for_status()
    data = r.json()
    try:
        os.makedirs(SEC_CACHE_DIR, exist_ok=True)
        with open(path + ".tmp", "wb") as f:
            f.write(r.content)
        os.replace(path + ".tmp", path)
    except OSError:
        pass  # the cache is only a convenience; the run goes on without it
    return data


def load_ticker_map(session: requests.Session, user_agent: str) -> dict[str, tuple[int, str]]:
    """{TICKER: (CIK, company name)} from SEC's ticker list."""
    data = _sec_get_json(SEC_TICKERS_URL, session, user_agent)
    return {row["ticker"].upper(): (int(row["cik_str"]), row["title"]) for row in data.values()}


def _sec_ticker(ticker: str) -> str:
    return ticker.strip().upper().replace(".", "-")  # SEC lists BRK.B as BRK-B


def fetch_company_facts(cik: int, session: requests.Session, user_agent: str) -> dict:
    return _sec_get_json(SEC_FACTS_URL.format(cik=cik), session, user_agent)


def fetch_sec_profile(cik: int, session: requests.Session, user_agent: str, data: Optional[dict] = None) -> SecProfile:
    """SIC code and the latest 10-Q/10-K (period end + filing date) from SEC's
    submissions API. The latter catches XBRL company-facts lagging a filing.
    Pass `data` (an already-fetched submissions JSON) to skip the request."""
    if data is None:
        data = _sec_get_json(SEC_SUBMISSIONS_URL.format(cik=cik), session, user_agent)
    sic = str(data.get("sic") or "").strip()
    recent = data.get("filings", {}).get("recent", {})
    latest = None
    for form, period, filed in zip(recent.get("form", []), recent.get("reportDate", []), recent.get("filingDate", [])):
        if form in ("10-Q", "10-K") and period and filed:
            latest = (form, date.fromisoformat(period), date.fromisoformat(filed))
            break  # most recent first
    return SecProfile(int(sic) if sic.isdigit() else None, str(data.get("sicDescription") or ""), latest)


def fetch_ten_year_yield(session: requests.Session) -> tuple[date, float]:
    """Latest 10-year Treasury yield (percent) from FRED's no-key CSV download."""
    since = (date.today() - timedelta(days=30)).isoformat()
    r = session.get(FRED_DGS10_URL, params={"id": "DGS10", "cosd": since}, timeout=30)
    r.raise_for_status()
    rows = list(csv.reader(io.StringIO(r.text)))[1:]  # header is DATE/observation_date,DGS10
    for row in reversed(rows):
        if len(row) >= 2 and row[1].strip() not in ("", "."):  # "." = no data (holiday)
            return date.fromisoformat(row[0].strip()), float(row[1])
    raise RuntimeError("FRED returned no 10-year Treasury yield for the last 30 days.")


def fetch_price(ticker: str) -> tuple[date, float, list[tuple[date, float]]]:
    """Latest price from Yahoo Finance via yfinance: the most recent daily
    bar's close, which during market hours is the current (delayed) price.
    Not dividend-adjusted (auto_adjust=False), so it's the traded price.

    Also returns the stock splits of the last five years [(date, ratio)],
    e.g. 4.0 for a 4-for-1 split, from the same request, to put EPS on the
    price's share basis. Older splits predate every SEC fact the TTM and
    prior TTM are built from."""
    import yfinance as yf

    symbol = ticker.strip().upper().replace(".", "-")  # Yahoo lists BRK.B as BRK-B
    try:
        yf.config.debug.hide_exceptions = False  # raise on errors (replaces the deprecated raise_errors=True)
    except AttributeError:
        pass  # older yfinance; the empty-result check below still catches failures
    try:
        hist = yf.Ticker(symbol).history(period="5y", interval="1d", auto_adjust=False, actions=True)
    except Exception as exc:
        raise RuntimeError(f"no Yahoo Finance price for {symbol} ({exc}). Pass --price instead.") from exc
    splits = []
    if "Stock Splits" in hist:
        splits = sorted((ts.date(), float(x)) for ts, x in hist["Stock Splits"].items() if x and float(x) > 0)
    hist = hist.dropna(subset=["Close"])
    if hist.empty:
        raise RuntimeError(f"no Yahoo Finance price for {symbol}. Pass --price instead.")
    return hist.index[-1].date(), float(hist["Close"].iloc[-1]), splits

DEFAULT_WINDOW_DAYS = 365
EARNINGS_ITEM = "2.02"  # 8-K item "Results of Operations and Financial Condition"
NEW_YORK = ZoneInfo("America/New_York")  # SEC's acceptance times are UTC; the market's clock is New York's
MARKET_CLOSE = clock_time(16, 0)
REPORT_DATE_TOLERANCE_DAYS = 7  # 10-Q/10-K reportDate vs quarter end (52/53-week fiscal years)
AMENDMENT_WINDOW_DAYS = 45  # a 10-Q/A or 10-K/A filed this soon after the original can stand in for it
FILINGS_LOOKBACK_DAYS = 300  # SEC filings needed this far before the window (the two releases before it)
YIELD_LOOKBACK_DAYS = 400  # Treasury yields fetched this far before the window (the release before it)
SEC_SUBMISSIONS_FILE_URL = "https://data.sec.gov/submissions/{name}"  # older filings, listed in filings.files
# --release-items: a filing's complete submission text (all its documents, the press release among them)
SEC_FILING_TEXT_URL = "https://www.sec.gov/Archives/edgar/data/{cik}/{folder}/{accession}.txt"
SEC_FILING_INDEX_URL = "https://www.sec.gov/Archives/edgar/data/{cik}/{folder}/{accession}-index.htm"  # for readers
# A press-release table is kept when its text matches this: the GAAP-to-adjusted (non-GAAP) EPS reconciliation
RECONCILIATION_RE = re.compile(r"(adjusted|non-gaap)\s+(diluted\s+)?(eps|earnings\s+per\s+(diluted\s+)?share)", re.I)
RECONCILIATION_MAX_CHARS = 6000  # per release, all matching tables together
# A table with a longer cell is text laid out in a table (e.g. Walmart's highlights), not a reconciliation
RECONCILIATION_MAX_CELL_CHARS = 200
# A press-release sentence is kept when it has a per-share amount and an item word: the one-time items a company
# names in its text rather than in a table (Costco: "a tax benefit of $100 million, $0.22 per diluted share")
ITEM_PER_SHARE_RE = re.compile(r"(?:\$\s?\(?\d*\.\d+\)?|\d+\s*cents?)\s*(?:per|/|a)\s*(?:diluted\s+)?share", re.I)
ITEM_WORD_RE = re.compile(r"non-?\s?recurring|one-?time|discrete|charges?\b|benefits?\b|gains?\b|loss(?:es)?\b|"
                          r"impairment|restructuring|settlement|write-?(?:down|off)|severance|litigation|unusual|"
                          r"special items?", re.I)
# Sentences end at . ! ? before a space, or at a bullet; "$3.92" has no space after its point
ITEM_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+|:\s+[-•]\s+|\s+[•▪●]\s+")
ITEM_SENTENCE_MAX_CHARS = 500  # longer is slide text run together (Costco's EX-99.2 deck), not a sentence
ITEM_SENTENCES_MAX_CHARS = 1500  # per release, all sentences together
# A sentence with an item word and a dollar amount but no per-share amount is kept apart: companies that report
# only GAAP EPS may state their items in dollars alone (Meta: "restructuring charges of $780 million"). Outlooks
# and estimates of future charges are left out ("This outlook includes approximately $4 billion of
# restructuring costs"): in Meta's 2022-2023 releases they were 7 of the 20 dollar sentences with an item word.
# Not "anticipated": Meta's Q3 2022 lease impairment aligns its offices "with our anticipated operating needs".
ITEM_DOLLAR_RE = re.compile(r"\$\s?\d[\d,]*(?:\.\d+)?\s*(?:million|billion)\b", re.I)
ITEM_OUTLOOK_RE = re.compile(r"\b(?:expect\w*|outlook|estimat\w*|forecast\w*|guidance)\b", re.I)
RELEASE_ITEMS_COLUMNS = ["quarter_end", "release_date", "release_form", "accession", "filing_url", "exhibits",
                         "n_tables", "reconciliation_text", "item_sentences", "item_dollar_sentences",
                         "diluted_shares", "note"]
ERP_BY_YEAR_PATH = os.path.join(BASE_DIR, "damodaran_implied_erp.csv")  # --erp-by-year: hand-maintained, dated rows
CSV_DIR = os.path.join(BASE_DIR, "Outputs_CSV_data")  # the history CSVs; the charts stay in PVGO_Collection/
# The EPS basis charted by default. A trailing basis rather than the trimmed 2-year EPS: one-time items are
# explained at each release rather than hidden (METHODOLOGY 2). Only raw ttm's outputs get no suffix.
DEFAULT_BASIS = "ttm_adjusted"
OWN_BETA_MONTHS = 60  # --own-beta: monthly returns in each regression (5 years)
OWN_BETA_MIN_MONTHS = 36  # fewer than this -> the industry beta for that month, with a note
OWN_BETA_BENCHMARK = "^GSPC"  # --own-beta: the S&P 500 index on Yahoo Finance
BLUME_WEIGHT = 0.67  # --own-beta: adjusted beta = 0.67 x regression beta + 0.33 x 1.0 (Blume adjustment)
# Chart smoothing (--smooth): lines drawn as a centered moving average -> (trading days, label). Display only.
# The third value: whether the no-growth average runs across earnings releases. Weekly and monthly restart at
# each one, so its steps stay sharp; a year spans four releases, so restarting would leave quarterly blocks.
SMOOTHING = {"weekly": (5, "1-week", False), "monthly": (21, "1-month", False), "yearly": (252, "1-year", True)}
POINT_COLUMNS = ["quarter_end", "release_date", "release_time", "release_form", "release_accession", "cutoff_date",
                 "measurement_date"]
SERIES_COLUMNS = ["date", "close", "no_growth_value", "growth_share_pct", "no_growth_value_before_step", "point",
                  "eps", "eps_basis", "eps_through", "treasury_10y_pct", "treasury_date", "cost_of_equity_pct"]


# --------------------------------------------------------------------------
# Data sources
# --------------------------------------------------------------------------
def fetch_ten_year_yields(session: requests.Session, start: date, end: date) -> list[tuple[date, float]]:
    """10-year Treasury yields (percent) from start to end, oldest first, from
    FRED's DGS10 CSV in one request. Days without a value ("." = holiday) are
    skipped."""
    r = session.get(FRED_DGS10_URL, params={"id": "DGS10", "cosd": start.isoformat(), "coed": end.isoformat()},
                    timeout=30)
    r.raise_for_status()
    yields = []
    for row in list(csv.reader(io.StringIO(r.text)))[1:]:  # header is DATE/observation_date,DGS10
        if len(row) >= 2 and row[1].strip() not in ("", "."):
            yields.append((date.fromisoformat(row[0].strip()), float(row[1])))
    if not yields:
        raise RuntimeError(f"FRED returned no 10-year Treasury yields between {start} and {end}.")
    return sorted(yields)


def fetch_price_history(ticker: str, start: date, end: date, adjusted: bool = False) -> tuple:
    """Daily closes from start through end, in one request (Yahoo Finance via
    yfinance, auto_adjust=False: split-adjusted, not dividend-adjusted), and
    the full split history [(date, ratio)], e.g. 4.0 for a 4-for-1 split.
    With `adjusted`, a third list: the dividend-adjusted closes from the same
    request (Yahoo's Adj Close), for total returns."""
    import yfinance as yf

    symbol = ticker.strip().upper().replace(".", "-")  # Yahoo lists BRK.B as BRK-B
    try:
        yf.config.debug.hide_exceptions = False  # raise on errors
    except AttributeError:
        pass
    t = yf.Ticker(symbol)
    try:
        hist = t.history(start=start.isoformat(), end=(end + timedelta(days=1)).isoformat(), interval="1d",
                         auto_adjust=False)
        splits = t.splits  # its own (full-history) request, so splits before `start` are included
    except Exception as exc:
        raise RuntimeError(f"no Yahoo Finance price history for {symbol} ({exc})") from exc
    hist = hist.dropna(subset=["Close"])
    if hist.empty:
        raise RuntimeError(f"no Yahoo Finance price history for {symbol} since {start}")
    prices = [(ts.date(), float(close)) for ts, close in hist["Close"].items()]
    split_list = sorted((ts.date(), float(x)) for ts, x in splits.items() if x and float(x) > 0)
    if not adjusted:
        return prices, split_list
    column = "Adj Close" if "Adj Close" in hist.columns else "Close"
    return prices, split_list, [(ts.date(), float(c)) for ts, c in hist[column].dropna().items()]


def fetch_benchmark_history(start: date, end: date) -> list[tuple[date, float]]:
    """Daily closes of the S&P 500 index (OWN_BETA_BENCHMARK) from start
    through end, in one request (Yahoo Finance via yfinance)."""
    import yfinance as yf

    try:
        hist = yf.Ticker(OWN_BETA_BENCHMARK).history(start=start.isoformat(), end=(end + timedelta(days=1)).isoformat(),
                                                     interval="1d", auto_adjust=False)
    except Exception as exc:
        raise RuntimeError(f"no Yahoo Finance history for the S&P 500 ({OWN_BETA_BENCHMARK}): {exc}") from exc
    hist = hist.dropna(subset=["Close"])
    if hist.empty:
        raise RuntimeError(f"no Yahoo Finance history for the S&P 500 ({OWN_BETA_BENCHMARK}) since {start}")
    return [(ts.date(), float(c)) for ts, c in hist["Close"].items()]


def _yield_on(yields: list[tuple[date, float]], d: date) -> tuple[date, float]:
    """The last Treasury yield on or before d: (its date, percent)."""
    i = bisect.bisect_right(yields, (d, math.inf))
    if i == 0:
        raise RuntimeError(f"no 10-year Treasury yield on or before {d} in the data fetched from FRED")
    return yields[i - 1]
