"""
Present value of growth opportunities (PVGO) as a share of price, per ticker.

    growth share = 1 - EPS / (price x cost of equity)  =  PVGO / price

where EPS is the adjusted TTM EPS (below) and PVGO = price - EPS / cost of
equity: the part of today's price that steady earnings, held flat forever,
don't explain.

Methodology note: this follows the steady-state approach in Mauboussin &
Callahan, "Opportunities and Expectations" (Morgan Stanley Counterpoint
Global, June 2026) -- earnings capitalized at the cost of equity. Known
differences from the paper:
  - Earnings basis: the adjusted TTM EPS -- trailing GAAP diluted EPS
    without the gains and losses on investments, less a flat tax -- not
    operating or forward consensus earnings. Other one-time items (legal
    charges, restructuring) stay in: each enters at its release and leaves
    four quarters later. (Since 2026-10-19; raw TTM EPS from 2026-10-16, the
    trimmed 2-year EPS before.)
  - Intangibles: the main reading makes no adjustment for expensed
    intangible investment, so R&D and brand spending lower EPS and raise
    the growth share. The R&D-adjusted reading (below) capitalizes R&D;
    brand/SG&A spending isn't adjusted (how much of it is investment is a
    judgment call, and SG&A tagging is inconsistent).

Inputs (all free, no API keys):
  - Share price: latest price from Yahoo Finance via the yfinance library
    (delayed intraday during market hours, otherwise the last close), or
    --price.
  - Trailing 12-month diluted EPS: SEC EDGAR XBRL company facts
    (data.sec.gov), the sum of the last four fiscal quarters. Q4 is rarely
    reported on its own, so it's derived as annual EPS minus Q1-Q3. Each
    EPS fact filed before a stock split (Yahoo's split history, from the
    same request as the price) is divided by the split ratio, so EPS is on
    the price's share basis. SEC responses are kept in cache/sec/ for
    SEC_CACHE_MAX_AGE_DAYS, so a rerun the same day makes no SEC requests.
  - Adjusted TTM EPS, the EPS behind the growth share: TTM EPS minus the
    realized and unrealized gains (plus the losses) on investments in the
    TTM's quarters (INVESTMENT_GAIN_TAGS, from the same company facts), less
    INVESTMENT_GAIN_TAX_RATE (25%), per diluted share. A mark-to-market gain
    isn't earnings that recur, so it isn't capitalized as no-growth value.
    Financial companies (FINANCIAL_SIC) are left unadjusted: their investment
    gains are operating income. No investment tag -> zero adjustment (same as
    TTM); where the adjustment can't be computed, the raw TTM EPS is used
    (noted).
  - Cost of equity: r = 10-year Treasury yield (FRED series DGS10) +
    beta x equity risk premium (ERP).
      * Industry, chosen in this order (industry_source):
          1. damodaran_company -- the company's own industry in Damodaran's
             company list (indname.xls), matched by ticker on a US exchange,
             or by company name when the ticker isn't listed.
          2. sic_mapping -- otherwise the company's SIC code (SEC submissions
             API) mapped through sic_to_damodaran_industry.csv.
          3. override -- company_industry_overrides.csv, applied last.
      * beta: that industry's average levered beta from Damodaran's US
        industry betas file, divided by the file's "Total Market" beta so the
        market averages 1.0 (both raw and scaled are reported; scaled is
        used). Not relevered for company debt. No industry, or an
        unavailable file, falls back to beta 1.0 with a note. --market-beta
        forces beta 1.0 for every ticker.
      * ERP: EQUITY_RISK_PREMIUM by default -- set by hand to Damodaran's
        current implied ERP (he updates it monthly); --erp overrides it for
        a single run.
    Both Damodaran files are cached in cache/ and refreshed when older than
    DAMODARAN_CACHE_MAX_AGE_DAYS (after a failed refresh, retried a day
    later).

2-year reading -- growth share (2-year): the same formula on the trimmed
2-year EPS: the last 8 fiscal quarters (the TTM's four and the four before
them, consecutive) without the single highest and single lowest quarter,
x 4 -- i.e. 4 x the mean of the other six. Trimming drops most one-time
charges and gains by one fixed rule, but the 2-year EPS lags a real change
in earnings by up to two years. Kept for comparisons with Counterpoint's
charts; n/a without 8 consecutive quarters.

6-month reading -- growth share (6-month): the same formula on the 6-month
EPS, the TTM's last two quarters x 2 (annualized). It shows a real change in
earnings soonest, but a one-time item weighs twice what it does in the TTM,
and seasonal quarters make it swing within the year.

R&D-adjusted reading -- growth share (R&D-adjusted): expensed R&D treated as
an investment (Damodaran-style capitalization), so the steady-state earnings
aren't depressed by spending on future growth:
    R&D-adjusted EPS = adjusted TTM EPS
                       + (current R&D - amortization) x (1 - RD_TAX_RATE) / diluted shares
  - current R&D: the same window as TTM EPS (Q4 derived as FY - Q1-Q3).
    Without quarterly R&D, the latest fiscal year is used instead (noted).
  - amortization: R&D of the prior RD_AMORTIZATION_YEARS twelve-month periods
    divided by that many years (straight-line); --rd-life changes the life.
    A period missing from SEC's quarterly data is estimated by splitting the
    fiscal-year totals it overlaps by days; periods still missing are filled
    with the average of the others, which amounts to a shorter effective life
    (noted). Fewer than RD_MIN_PRIOR_YEARS prior years -> n/a.
  - diluted shares: the average weighted-average diluted share count of the
    TTM quarters (the fiscal year's figure stands in for a derived Q4),
    split-adjusted like EPS; noted when some quarters have no count.
  - R&D and share counts come from the same SEC company facts as EPS (no
    extra request). R&D tags are tried in RD_TAGS order and merged period
    by period, so a company that switched tags keeps its history.
  - RD_TAX_RATE is 0: the add-back isn't tax-effected, as in Damodaran's method.
  - No R&D tag at all -> the adjustment is zero (same as unadjusted).

Warning notes about the trailing EPS:
  - a TTM quarter that looks like a one-time item: negative while the other
    three are positive, or more than ONE_TIME_DEVIATION away from the median
    of the four (relative to the median's size). When ERRATIC_MIN_FLAGS or
    more of the four trip these checks, one "erratic earnings" note replaces
    the per-quarter notes.
  - TTM EPS whose sign flips when its largest-magnitude quarter is removed.
  - TTM EPS more than LAG_WARNING above or below the 2-year EPS: a one-off
    may sit in the TTM, or earnings really changed. Compare the 2-year
    reading.
  - SEC's XBRL data lagging the company's latest 10-Q/10-K (a known SEC-side
    gap), and the latest quarter being older than STALE_EPS_DAYS.

EPS of zero or less still gets a number: the growth share is then 100% or
more, which is how Mauboussin & Callahan report loss-making companies.

SEC requires every request to identify the requester via User-Agent (name +
contact email): set SEC_EDGAR_USER_AGENT in .env (see .env.example).
Only company tickers are supported; foreign filers reporting under IFRS
(20-F) aren't.

Usage:
    python pvgo_growth_share.py <ticker>
    python pvgo_growth_share.py <ticker 1> <ticker 2> <ticker 3>
    python pvgo_growth_share.py <ticker> --price 123.45   # skip the quote lookup
    python pvgo_growth_share.py <ticker> --erp 4.3        # ERP in percent
    python pvgo_growth_share.py <ticker> --market-beta    # beta 1.0 for every ticker
    python pvgo_growth_share.py <ticker> --rd-life 10     # amortize R&D over 10 years
"""

from __future__ import annotations

import argparse
import csv
import os
from dataclasses import asdict, dataclass
from datetime import date
from typing import Optional

import requests

from pvgo_cost_of_equity import (
    BetaChoice,
    choose_beta,
    IndustryChoice,
    load_company_index,
    load_industry_betas,
    load_overrides,
    load_sic_map,
    resolve_industry,
)
from pvgo_eps import (
    earnings_quality_notes,
    filing_gap_note,
    investment_gain_adjustment,
    InvestmentAdjustment,
    rd_adjustment,
    rd_tax_wording,
    RdAdjustment,
    six_month_eps,
    ttm_diluted_eps,
    TtmEps,
    two_year_eps,
)
from pvgo_inputs import (
    BASE_DIR,
    CAVEAT,
    EQUITY_RISK_PREMIUM,
    fetch_company_facts,
    fetch_price,
    fetch_sec_profile,
    fetch_ten_year_yield,
    get_user_agent,
    INVESTMENT_GAIN_TAX_RATE,
    LAG_WARNING,
    load_ticker_map,
    NOTE_SEPARATOR,
    RD_AMORTIZATION_YEARS,
    RD_MIN_PRIOR_YEARS,
    _sec_ticker,
    STALE_PRICE_DAYS,
)


@dataclass
class PvgoResult:
    ticker: str
    company: str
    sic: str
    damodaran_industry: str
    industry_source: str
    price: float
    price_date: str
    price_source: str
    eps_ttm: float
    eps_period: str  # "first quarter start .. last quarter end"
    pe: Optional[float]  # price / TTM EPS
    eps_six_month: float  # the TTM's last 2 quarters x 2 (six_month_eps)
    eps_prior_ttm: Optional[float]  # the four quarters before the TTM; None without them
    eps_two_year: Optional[float]  # trimmed 2-year EPS (two_year_eps); None without 8 consecutive quarters
    two_year_period: str  # the 8 quarters it spans, "" without them
    two_year_dropped: str  # the lowest and highest quarter trimmed out, e.g. "2013-09-30 -0.17; 2013-06-30 1.60"
    # The TTM's four quarters, oldest first, each "end EPS source" ("2024-09-01 5.2800 derived: FY - Q1-Q3"), and
    # the quarter before them, which the TTM dropped when it took the newest ("" without the prior four): a
    # release's TTM step is the newest minus that one, given outright to Company_Narrative_Aggregation's release call
    ttm_quarters: str
    ttm_quarter_leaving: str
    # behind no_growth_value, pvgo and growth_share_pct: the adjusted TTM EPS (eps_ttm_adjusted) since
    # 2026-10-19, raw TTM where it can't be computed; TTM EPS from 2026-10-16, the 2-year EPS before
    eps_used: float
    ttm_vs_two_year_pct: Optional[float]  # (TTM - 2-year) / |2-year| x 100; a note fires beyond LAG_WARNING
    treasury_10y_pct: float
    treasury_date: str
    beta_raw: Optional[float]  # Damodaran's industry beta as published
    beta_scaled: float  # raw / Total Market (or 1.0); used in the cost of equity
    beta_source: str
    equity_risk_premium_pct: float
    cost_of_equity_pct: float
    no_growth_value: float  # eps_used / cost of equity
    pvgo: float  # price - no-growth value
    growth_share_pct: float
    growth_share_two_year_pct: Optional[float]  # the same formula on the trimmed 2-year EPS; None without it
    growth_share_six_month_pct: float  # the same formula on 6-month EPS
    investment_gains_ttm: Optional[float]  # pre-tax gains (+) / losses (-) on investments in the TTM (USD)
    investment_gain_tags: str  # the XBRL tag(s) they came from, or why there's no adjustment
    investment_adjustment_per_share: Optional[float]  # -gains x (1 - tax) / diluted shares; 0 when none or exempt
    eps_ttm_adjusted: Optional[float]  # eps_ttm + investment_adjustment_per_share
    growth_share_ttm_adjusted_pct: Optional[float]
    rd_current: Optional[float]  # current-year R&D expense (USD) used in the adjustment
    rd_basis: str  # the window rd_current covers
    rd_amortization: Optional[float]  # prior years' R&D / life (USD)
    rd_life_years: Optional[int]
    rd_effective_life_years: Optional[int]  # prior years of R&D actually averaged (< rd_life_years when gaps were filled)
    rd_diluted_shares: Optional[float]  # weighted-average diluted shares the adjustment is spread over
    rd_adjustment_per_share: Optional[float]  # 0 when no R&D is reported
    eps_rd_adjusted: Optional[float]
    growth_share_rd_adjusted_pct: Optional[float]
    notes: str


# --------------------------------------------------------------------------
# Calculation
# --------------------------------------------------------------------------
def growth_share(price: float, eps: float, cost_of_equity: float) -> float:
    """1 - EPS/(price x r). For EPS <= 0 this is 100% or more by construction."""
    if price <= 0 or cost_of_equity <= 0:
        raise ValueError(f"price ({price}) and cost of equity ({cost_of_equity}) must be positive")
    return 1 - eps / (price * cost_of_equity)


def compute(
    ticker: str, company: str, sic: Optional[int], price: float, price_date: str, price_source: str,
    eps: TtmEps, treasury_date: date, treasury_pct: float, industry: IndustryChoice, beta: BetaChoice,
    erp: float = EQUITY_RISK_PREMIUM, extra_notes: Optional[list[str]] = None, rd: Optional[RdAdjustment] = None,
    inv: Optional[InvestmentAdjustment] = None,
) -> PvgoResult:
    r = treasury_pct / 100 + beta.beta * erp
    two, dropped, _ = two_year_eps(eps)
    six = six_month_eps(eps)
    # The adjusted TTM: TTM without the gains and losses on investments (METHODOLOGY 2). A one-time
    # item enters at its release and leaves four quarters later; raw TTM where the adjustment is n/a.
    inv = inv or InvestmentAdjustment(None, basis="not computed")
    adjusted = eps.value + inv.per_share if inv.per_share is not None else None
    used = adjusted if adjusted is not None else eps.value
    share = growth_share(price, used, r)
    no_growth = used / r
    notes = list(eps.notes) + list(extra_notes or []) + industry.notes + beta.notes + inv.notes
    if adjusted is None and inv.basis != "not computed":
        notes.append("adjusted TTM EPS not computed, so the growth share uses the raw TTM EPS")
    notes += earnings_quality_notes(eps)
    lag = None
    if two is not None and two != 0:
        lag = (eps.value - two) / abs(two)
        if abs(lag) > LAG_WARNING:
            notes.append(f"TTM EPS {eps.value:.2f} is {lag:+.0%} vs the 2-year EPS {two:.2f}: a one-off may sit in the "
                         "TTM, or earnings really changed; compare the 2-year reading")

    rd = rd or RdAdjustment(None, life=None, basis="not computed")
    rd_eps = rd_share = None
    if rd.per_share is not None:
        rd_eps = used + rd.per_share
        rd_share = growth_share(price, rd_eps, r)
    notes += rd.notes

    return PvgoResult(
        ticker=ticker.upper(),
        company=company,
        sic="" if sic is None else str(sic),
        damodaran_industry=industry.industry,
        industry_source=industry.source,
        price=round(price, 4),
        price_date=price_date,
        price_source=price_source,
        eps_ttm=eps.value,
        eps_period=f"{eps.quarters[0].start} .. {eps.quarters[-1].end}",
        pe=round(price / eps.value, 2) if eps.value > 0 else None,
        eps_six_month=six,
        eps_prior_ttm=eps.prior_value,
        eps_two_year=two,
        two_year_period=f"{eps.prior_quarters[0].start} .. {eps.quarters[-1].end}" if two is not None else "",
        two_year_dropped="; ".join(f"{q.end} {q.eps:.2f}" for q in dropped),
        ttm_quarters="; ".join(f"{q.end} {q.eps:.4f} {q.source}" for q in eps.quarters),
        ttm_quarter_leaving=(f"{eps.prior_quarters[-1].end} {eps.prior_quarters[-1].eps:.4f} "
                             f"{eps.prior_quarters[-1].source}" if eps.prior_quarters else ""),
        eps_used=used,
        ttm_vs_two_year_pct=round(lag * 100, 1) if lag is not None else None,
        treasury_10y_pct=treasury_pct,
        treasury_date=treasury_date.isoformat(),
        beta_raw=round(beta.raw, 4) if beta.raw is not None else None,
        beta_scaled=round(beta.beta, 4),
        beta_source=beta.source,
        equity_risk_premium_pct=round(erp * 100, 4),
        cost_of_equity_pct=round(r * 100, 4),
        no_growth_value=round(no_growth, 2),
        pvgo=round(price - no_growth, 2),
        growth_share_pct=round(share * 100, 1),
        growth_share_two_year_pct=round(growth_share(price, two, r) * 100, 1) if two is not None else None,
        growth_share_six_month_pct=round(growth_share(price, six, r) * 100, 1),
        investment_gains_ttm=round(inv.gains_ttm) if inv.gains_ttm is not None else None,
        investment_gain_tags=inv.tags or inv.basis,
        investment_adjustment_per_share=round(inv.per_share, 4) if inv.per_share is not None else None,
        eps_ttm_adjusted=round(adjusted, 4) if adjusted is not None else None,
        growth_share_ttm_adjusted_pct=round(share * 100, 1) if adjusted is not None else None,
        rd_current=round(rd.rd_current) if rd.rd_current is not None else None,
        rd_basis=rd.basis,
        rd_amortization=round(rd.amortization) if rd.amortization is not None else None,
        rd_life_years=rd.life,
        rd_effective_life_years=rd.effective_life,
        rd_diluted_shares=round(rd.shares) if rd.shares is not None else None,
        rd_adjustment_per_share=round(rd.per_share, 4) if rd.per_share is not None else None,
        eps_rd_adjusted=round(rd_eps, 4) if rd_eps is not None else None,
        growth_share_rd_adjusted_pct=round(rd_share * 100, 1) if rd_share is not None else None,
        notes=NOTE_SEPARATOR.join(notes),
    )


# --------------------------------------------------------------------------
# Public entry points
# --------------------------------------------------------------------------
def collect(
    tickers: list[str],
    price: Optional[float] = None,
    market_beta: bool = False,
    erp_pct: Optional[float] = None,
    rd_life: Optional[int] = None,
) -> list[PvgoResult]:
    """Growth share for each ticker. `price` overrides the quote lookup
    (only allowed for a single ticker); `market_beta` forces beta 1.0;
    `erp_pct` overrides the equity risk premium (in percent, e.g. 4.3);
    `rd_life` overrides the R&D amortization life (years).
    Tickers that fail are reported and skipped."""
    if price is not None and len(tickers) != 1:
        raise ValueError("--price can only be used with a single ticker.")
    if erp_pct is not None and erp_pct <= 0:
        raise ValueError("--erp must be a positive percentage, e.g. 4.3")
    if rd_life is not None and rd_life < 1:
        raise ValueError("--rd-life must be at least 1 year")
    erp = EQUITY_RISK_PREMIUM if erp_pct is None else erp_pct / 100
    life = RD_AMORTIZATION_YEARS if rd_life is None else rd_life

    user_agent = get_user_agent()
    with requests.Session() as session:
        treasury_date, treasury_pct = fetch_ten_year_yield(session)
        ticker_map = load_ticker_map(session, user_agent)
        sic_map, overrides = load_sic_map(), load_overrides()
        companies, companies_reason = load_company_index(session)
        industry_betas, betas_reason = (None, "") if market_beta else load_industry_betas(session)

        results = []
        for ticker in tickers:
            try:
                key = _sec_ticker(ticker)
                if key not in ticker_map:
                    raise RuntimeError("not found in SEC's ticker list")
                cik, company = ticker_map[key]

                # Price first, so a ticker without one is skipped before any SEC request. Yahoo's
                # split history comes with it: EPS goes on the price's (today's) share basis.
                price_notes = []
                if price is not None:
                    p, p_date, p_source = price, date.today().isoformat(), "entered manually"
                    try:
                        splits = fetch_price(ticker)[2]
                    except Exception:
                        splits = []
                        price_notes.append("couldn't get Yahoo's split history, so EPS isn't adjusted for a "
                                           "recent stock split, if there was one")
                else:
                    d, p, splits = fetch_price(ticker)
                    p_date, p_source = d.isoformat(), "Yahoo Finance latest"
                    if (date.today() - d).days > STALE_PRICE_DAYS:
                        price_notes.append(f"price is from {d}")

                facts = fetch_company_facts(cik, session, user_agent)
                eps = ttm_diluted_eps(facts, splits=splits)
                try:
                    rd = rd_adjustment(facts, eps, life, splits=splits)
                except Exception as exc:  # the R&D reading is secondary; don't lose the ticker over it
                    rd = RdAdjustment(None, life=life, notes=[f"R&D adjustment failed ({exc})"])

                extra_notes = []
                try:
                    profile = fetch_sec_profile(cik, session, user_agent)
                except Exception as exc:
                    profile = None
                    extra_notes.append(f"couldn't get the SIC code and filing list from SEC ({exc})")
                gap = filing_gap_note(eps, profile)
                if gap:
                    extra_notes.append(gap)
                extra_notes += price_notes
                industry = resolve_industry(ticker, company, profile, companies, companies_reason, sic_map, overrides)
                beta = choose_beta(industry, industry_betas, betas_reason, market_beta)
                try:
                    inv = investment_gain_adjustment(facts, eps, profile.sic if profile else None, splits=splits)
                except Exception as exc:  # fall back to the raw TTM rather than lose the ticker
                    inv = InvestmentAdjustment(None, basis="failed", notes=[f"investment-gain adjustment failed ({exc})"])

                results.append(compute(ticker, company, profile.sic if profile else None, p, p_date, p_source,
                                       eps, treasury_date, treasury_pct, industry, beta, erp, extra_notes, rd, inv))
            except Exception as exc:  # one bad ticker shouldn't stop the rest
                print(f"{ticker.upper()}: skipped -- {exc}")
    return results


def _abbrev(v: float) -> str:
    """1234567890 -> '1.23B', 45600000 -> '45.6M'."""
    for size, suffix, digits in ((1e9, "B", 2), (1e6, "M", 1)):
        if abs(v) >= size:
            return f"{v / size:,.{digits}f}{suffix}"
    return f"{v:,.0f}"


def format_report(res: PvgoResult) -> str:
    def money(v):
        return "n/a" if v is None else f"{'-' if v < 0 else ''}${abs(v):,.2f}"

    def big_money(v):
        return f"{'-' if v < 0 else ''}${_abbrev(abs(v))}"

    industry = f"{res.damodaran_industry} [{res.industry_source}]" if res.damodaran_industry else "no industry"
    if res.beta_raw is not None:
        beta_detail = f"{industry}: raw {res.beta_raw:.2f}, scaled {res.beta_scaled:.2f} ({res.beta_source})"
    else:
        beta_detail = f"{res.beta_source}; {industry}"
    share = f"{res.growth_share_pct:.1f}%" + (" (EPS <= 0, so 100% or more by construction)" if res.eps_used <= 0 else "")
    two_share = ("n/a (needs 8 consecutive quarters)" if res.growth_share_two_year_pct is None else
                 f"{res.growth_share_two_year_pct:.1f}%"
                 + (" (2-year EPS <= 0, so 100% or more by construction)" if res.eps_two_year <= 0 else ""))
    six_share = (f"{res.growth_share_six_month_pct:.1f}%"
                 + (" (6-month EPS <= 0, so 100% or more by construction)" if res.eps_six_month <= 0 else ""))
    if res.eps_two_year is None:
        two_year = "n/a (needs 8 consecutive quarters)"
    else:
        two_year = (f"{money(res.eps_two_year):<12} (8 quarters, {res.two_year_period}; without the lowest and "
                    f"highest: {res.two_year_dropped.replace('; ', ' and ')})")

    rd_detail = None
    if res.growth_share_rd_adjusted_pct is None:
        rd = "n/a (see notes)"
    elif res.rd_current is None:  # no R&D reported: adjustment is zero
        rd = f"{res.growth_share_rd_adjusted_pct:.1f}%  (same as unadjusted: {res.rd_basis})"
    else:
        adj = res.rd_adjustment_per_share
        rd = (f"{res.growth_share_rd_adjusted_pct:.1f}%  (adjusted EPS {money(res.eps_rd_adjusted)} = "
              f"{money(res.eps_used)} {'-' if adj < 0 else '+'} {money(abs(adj))} R&D adjustment)")
        if res.eps_rd_adjusted <= 0:
            rd += " (adjusted EPS <= 0, so 100% or more by construction)"
        life, eff = res.rd_life_years, res.rd_effective_life_years
        amortized = f"prior {eff} years' R&D / {eff}"
        if eff != life:
            amortized += f"; effective life, {life - eff} of {life} years missing"
        rd_detail = (f"R&D: {big_money(res.rd_current)} ({res.rd_basis}) - amortization "
                     f"{big_money(res.rd_amortization)} ({amortized}), "
                     f"over {_abbrev(res.rd_diluted_shares)} diluted shares")
    if res.eps_ttm_adjusted is None:
        adjusted = "n/a (see notes); the raw TTM EPS is used"
    elif res.investment_gains_ttm:
        adj = res.investment_adjustment_per_share
        adjusted = (f"{money(res.eps_ttm_adjusted):<12} (TTM {'-' if adj < 0 else '+'} {money(abs(adj))}: "
                    f"{'gains' if res.investment_gains_ttm > 0 else 'losses'} on investments of "
                    f"{big_money(abs(res.investment_gains_ttm))} excluded, less {INVESTMENT_GAIN_TAX_RATE:.0%} tax; "
                    f"{res.investment_gain_tags})")
    else:
        adjusted = f"{money(res.eps_ttm_adjusted):<12} (same as TTM: {res.investment_gain_tags})"
    lines = [
        f"{res.ticker}  {res.company}",
        f"  Price            {money(res.price):<12} ({res.price_source}, {res.price_date})",
        f"  TTM diluted EPS  {money(res.eps_ttm):<12} (4 quarters, {res.eps_period})",
        f"  Adjusted TTM EPS {adjusted}",
        f"  6-month EPS      {money(res.eps_six_month):<12} (the last 2 of those quarters, x 2)",
        f"  2-year EPS       {two_year}",
        f"  P/E              {'n/a' if res.pe is None else f'{res.pe:.1f}':<12} (price / TTM EPS)",
        f"  Cost of equity   {f'{res.cost_of_equity_pct:.2f}%':<12} (10Y Treasury {res.treasury_10y_pct:.2f}% on "
        f"{res.treasury_date} + beta {res.beta_scaled:.2f} x ERP {res.equity_risk_premium_pct:.2f}%)",
        f"                   beta: {beta_detail}",
        f"  No-growth value  {money(res.no_growth_value):<12} "
        + ("(adjusted TTM EPS / cost of equity)" if res.eps_ttm_adjusted is not None else "(TTM EPS / cost of equity)"),
        f"  PVGO             {money(res.pvgo)}",
        f"  Growth share     {share}",
        f"  Growth share (2-year)        {two_share}",
        f"  Growth share (6-month)       {six_share}",
        f"  Growth share (R&D-adjusted)  {rd}",
    ]
    if rd_detail:
        lines.append(f"                   {rd_detail}")
    if res.notes:
        lines.append("  Notes:")
        lines += [f"    - {n}" for n in res.notes.split(NOTE_SEPARATOR)]
    return "\n".join(lines)


def format_footer(rd_life: Optional[int] = None) -> str:
    """Printed once after the per-ticker reports. Pass the --rd-life used, if any."""
    life = RD_AMORTIZATION_YEARS if rd_life is None else rd_life
    two_year_explainer = (
        "2-year EPS: the last 8 fiscal quarters without the single highest and lowest, x 4. It damps one-time items "
        "by one fixed rule but lags a real change in earnings, which the TTM reading shows sooner."
    )
    six_month_explainer = (
        "6-month EPS: the last 2 fiscal quarters x 2. It shows a real change in earnings soonest, but a one-time item "
        "weighs twice what it does in the TTM, and seasonal quarters make it swing within the year."
    )
    rd_explainer = (
        f"R&D-adjusted reading: R&D treated as an investment and amortized straight-line over {life} years; "
        "adjusted EPS = adjusted TTM EPS + (current R&D - amortization) / diluted shares, "
        f"{rd_tax_wording()}. Prior years missing from SEC's data are estimated from fiscal-year totals where possible, "
        f"otherwise filled with the average of the others (n/a with fewer than {min(RD_MIN_PRIOR_YEARS, life)}). "
        "No R&D reported -> same as unadjusted."
    )
    return "\n".join([CAVEAT, two_year_explainer, six_month_explainer, rd_explainer])


def write_csv(results: list[PvgoResult], path: str) -> None:
    """Relative paths resolve against PVGO_Collection/, not the cwd."""
    if not os.path.isabs(path):
        path = os.path.join(BASE_DIR, path)
    names = list(PvgoResult.__dataclass_fields__)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=names)
        writer.writeheader()
        for r in results:
            writer.writerow(asdict(r))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("tickers", nargs="+", help="Company stock ticker(s), US listings")
    parser.add_argument("--price", type=float, default=None,
                        help="Use this share price instead of looking one up (single ticker only)")
    parser.add_argument("--market-beta", action="store_true",
                        help="Use beta 1.0 for every ticker instead of its industry beta")
    parser.add_argument("--erp", type=float, default=None,
                        help=f"Equity risk premium in percent, e.g. 4.3 (default {EQUITY_RISK_PREMIUM * 100:g})")
    parser.add_argument("--rd-life", type=int, default=None,
                        help=f"R&D amortization life in years for the R&D-adjusted reading "
                             f"(default {RD_AMORTIZATION_YEARS})")
    parser.add_argument("--output", default="pvgo_results.csv", help="Output CSV path")
    args = parser.parse_args()

    try:
        results = collect(args.tickers, price=args.price, market_beta=args.market_beta, erp_pct=args.erp,
                          rd_life=args.rd_life)
    except (ValueError, RuntimeError, requests.RequestException) as exc:
        raise SystemExit(f"PVGO stopped: {exc}") from exc

    for res in results:
        print(format_report(res))
        print()
    if results:
        print(format_footer(args.rd_life))
        try:
            write_csv(results, args.output)
        except PermissionError:
            print(f"\nCouldn't write {args.output} -- is it open in Excel? Close it, or pass --output <other file>.")
        else:
            print(f"\nWrote {len(results)} row(s) to {args.output}")


if __name__ == "__main__":
    main()
