"""PVGO history, the series: the EPS bases charted, the no-growth line, the daily
series and assembling a ticker's history (collect_history).
METHODOLOGY section 7.
"""

from __future__ import annotations

import bisect
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Callable, Optional

import requests

from pvgo_cost_of_equity import (
    BetaChoice,
    choose_beta,
    erp_on,
    load_company_index,
    load_erp_by_year,
    load_industry_betas,
    load_overrides,
    load_sic_map,
    _months_before,
    own_beta_on,
    own_beta_schedule,
    own_beta_source,
    resolve_industry,
)
from pvgo_eps import (
    _eps_rows,
    fiscal_quarters,
    investment_gain_adjustment,
    InvestmentAdjustment,
    is_periodic_report,
    quarter_diluted_shares,
    rd_adjustment,
    rd_tax_wording,
    RdAdjustment,
)
from pvgo_growth_share import compute, PvgoResult
from pvgo_history_releases import (
    find_releases,
    load_filings,
    _measurement_day,
    _pre_xbrl,
    Release,
    release_reconciliation,
    _ttm_for,
)
from pvgo_inputs import (
    DEFAULT_BASIS,
    DEFAULT_WINDOW_DAYS,
    EARNINGS_ITEM,
    EQUITY_RISK_PREMIUM,
    fetch_benchmark_history,
    fetch_company_facts,
    fetch_price_history,
    fetch_sec_profile,
    fetch_ten_year_yields,
    FILINGS_LOOKBACK_DAYS,
    get_user_agent,
    INVESTMENT_GAIN_TAX_RATE,
    LAG_WARNING,
    load_ticker_map,
    NOTE_SEPARATOR,
    OWN_BETA_MIN_MONTHS,
    OWN_BETA_MONTHS,
    RD_AMORTIZATION_YEARS,
    _sec_ticker,
    YIELD_LOOKBACK_DAYS,
    _yield_on,
)


@dataclass(frozen=True)
class EpsBasis:
    """An EPS the no-growth value can be based on (--eps-basis)."""
    label: str  # e.g. "TTM EPS"
    result_field: str  # the PvgoResult field holding it
    column: str  # short header in the points table
    color: str  # its lines in a chart of several bases (no-growth solid, growth share dashed)
    footnote: str  # the chart footnote's EPS description when it's charted alone
    short: str  # its part of that description in a chart of several bases


EPS_BASES = {  # in charting order
    "ttm_adjusted": EpsBasis(
        "Adjusted TTM EPS", "eps_ttm_adjusted", "Adj TTM", "#1565c0",
        "EPS: the adjusted TTM, trailing GAAP diluted EPS without the gains and losses on investments (less a flat "
        f"{INVESTMENT_GAIN_TAX_RATE:.0%} tax; financial companies unadjusted), from the filings available at each "
        "release, on today's share basis.",
        f"adjusted TTM = TTM without gains and losses on investments (less {INVESTMENT_GAIN_TAX_RATE:.0%} tax)"),
    "ttm": EpsBasis(
        "TTM EPS", "eps_ttm", "TTM EPS", "#eda100",
        "EPS: trailing GAAP diluted EPS (TTM), from the filings available at each release, on today's share basis.",
        "TTM = trailing GAAP diluted EPS"),
    "two_year": EpsBasis(
        "2-year EPS", "eps_two_year", "2y EPS", "#c55a11",
        "EPS: the 2-year EPS, 4 x the mean of the last 8 quarters of GAAP diluted EPS without the single highest and "
        "lowest, from the filings available at each release, on today's share basis. It damps one-time items but lags "
        "a real change in earnings. Kept for comparisons with Counterpoint's charts.",
        "2-year = 4 x the mean of the last 8 quarters without the highest and lowest"),
    "six_month": EpsBasis(
        "6-month EPS", "eps_six_month", "6m EPS", "#9467bd",
        "EPS: the 6-month EPS, 2 x the last 2 quarters of GAAP diluted EPS (annualized), from the filings available "
        "at each release, on today's share basis. It shows a real change in earnings soonest, but a one-time item "
        "weighs double and seasonal quarters make it swing within the year.",
        "6-month = 2 x the sum of the last 2 quarters"),
    "rd_adjusted": EpsBasis(
        "R&D-adjusted EPS", "eps_rd_adjusted", "R&D EPS", "#00897b",
        "EPS: R&D-adjusted, the adjusted TTM EPS + (current R&D - straight-line amortization of the prior "
        f"{RD_AMORTIZATION_YEARS} years' R&D) / diluted shares, {rd_tax_wording()}, from the filings available at "
        "each release, on today's share basis.",
        f"R&D-adjusted = adjusted TTM + (current R&D - straight-line amortization of the prior {RD_AMORTIZATION_YEARS} "
        f"years' R&D) / diluted shares, {rd_tax_wording()}"),
}


@dataclass
class LinePoint:
    day: date
    value: float  # no-growth value per share = eps / cost_of_equity
    eps: float  # EPS in effect
    eps_through: date  # quarter end of its latest quarter
    treasury_pct: float
    treasury_date: date
    cost_of_equity: float
    kind: str  # "start", "weekly", "year-end", "step-before", "step-after" or "final"
    basis: str  # EPS basis of `eps` (the chart's, or "ttm" where it fell back)
    erp: float  # the ERP in cost_of_equity
    beta: float  # the beta in cost_of_equity


@dataclass
class TickerHistory:
    ticker: str
    company: str
    window_start: date
    window_end: date
    beta: BetaChoice
    erp: float
    points: list[tuple[Release, PvgoResult]]  # one per release shown, oldest first
    line: list[LinePoint]  # the no-growth line in drawing order (two points per step)
    prices: list[tuple[date, float]]  # daily closes in the window, oldest first
    notes: list[str] = field(default_factory=list)  # ticker-level notes
    eps_basis: str = DEFAULT_BASIS  # see EPS_BASES
    eps_used: list[tuple[float, str]] = field(default_factory=list)  # per point: (EPS charted, its basis)
    # --erp-by-year: load_erp_by_year()'s rows (erp is then the one at window_end); None = erp throughout
    erp_schedule: Optional[list[tuple[date, float]]] = None
    # --own-beta: own_beta_schedule()'s rows, (month end, beta used, regression beta, monthly returns); `beta`
    # is then the fallback for dates before the first row. None = `beta` throughout
    beta_schedule: Optional[list[tuple[date, float, float, int]]] = None
    blume: bool = True  # --own-beta: the beta used is Blume-adjusted (False: --raw-beta, the regression slope)
    # --release-items: release_reconciliation()'s row per point (same for every basis); None = not fetched
    release_items: Optional[list[dict]] = None


def _basis_eps(basis: str, res: PvgoResult) -> Optional[float]:
    """A basis's EPS at a point, from compute()'s result, or None where it
    isn't available (the 2-year EPS needs 8 consecutive quarters; R&D-adjusted
    needs the R&D history)."""
    return getattr(res, EPS_BASES[basis].result_field)


def no_growth_line(
    points: list[tuple[Release, PvgoResult]], prices: list[tuple[date, float]],
    yields: list[tuple[date, float]], beta_at: Callable[[date], float], erp_at: Callable[[date], float],
    window_start: date, eps_used: list[tuple[float, str]],
) -> list[LinePoint]:
    """The no-growth line over the window, in drawing order: the window's
    first trading day, each week's last trading day, each completed year's
    last trading day, two points at each measurement date (old EPS, then new
    EPS, at the same yield: a vertical step) and the latest close. Each value
    is the EPS in effect / r, with r from the last Treasury yield on or
    before that day and the beta and ERP on that day (`beta_at`, `erp_at`).
    `eps_used` gives each point's (EPS, basis)."""
    steps = [(rel.measurement_date, eps, rel.quarter_end, basis)
             for (rel, _), (eps, basis) in zip(points, eps_used)]

    def in_effect(d: date, before_step: bool = False) -> Optional[tuple[float, date, str]]:
        """(EPS, quarter end, basis) in effect at d's close, or just before d's step."""
        current = None
        for m, eps, quarter_end, basis in steps:
            if m < d or (m == d and not before_step):
                current = (eps, quarter_end, basis)
        return current

    def point(d: date, kind: str, ttm: tuple[float, date, str]) -> LinePoint:
        t_date, t_pct = _yield_on(yields, d)
        e, b = erp_at(d), beta_at(d)
        r = t_pct / 100 + b * e
        return LinePoint(d, ttm[0] / r, ttm[0], ttm[1], t_pct, t_date, r, kind, ttm[2], e, b)

    days = [d for d, _ in prices if d >= window_start]
    if not days:
        return []
    week_last = {}
    for d in days:
        week_last[d.isocalendar()[:2]] = d  # ISO (year, week) -> its last trading day
    week_last_days = set(week_last.values())
    year_last = {}
    for d in days:
        year_last[d.year] = d
    year_last_days = {d for y, d in year_last.items() if y < days[-1].year}  # completed years only
    step_days = {m for m, _, _, _ in steps}

    line = []
    for d in days:
        if d in step_days:
            before = in_effect(d, before_step=True)
            if before:
                line.append(point(d, "step-before", before))
            line.append(point(d, "step-after", in_effect(d)))
        elif d == days[0] or d == days[-1] or d in week_last_days or d in year_last_days:
            ttm = in_effect(d)
            if ttm:
                kind = ("start" if d == days[0] else "final" if d == days[-1] else "weekly" if d in week_last_days
                        else "year-end")
                line.append(point(d, kind, ttm))
    return line


def _line_value_on(
    line: list[LinePoint], line_days: list[date], d: date, basis: Optional[str] = None,
) -> Optional[float]:
    """The no-growth line at d's close: linear between line points, after any
    step on d. With `basis`, None while the EPS in effect is of another basis
    (a point that fell back to TTM)."""
    i = bisect.bisect_right(line_days, d)
    if i == 0:
        return None  # before the line starts
    a = line[i - 1]
    if basis is not None and a.basis != basis:
        return None
    if a.day == d or i == len(line):
        return a.value
    b = line[i]
    return a.value + (b.value - a.value) * (d - a.day).days / (b.day - a.day).days


def daily_values(h: TickerHistory) -> list[tuple[date, float, Optional[float], Optional[float]]]:
    """(day, close, no-growth value, growth share %) for each trading day in
    the window. The no-growth value is the line as drawn (linear between its
    points); growth share = 1 - no-growth value / close. Both are None before
    the line starts, and while this version's EPS isn't available (the
    periods where it fell back to TTM aren't drawn)."""
    line_days = [p.day for p in h.line]
    out = []
    for d, close in h.prices:
        value = _line_value_on(h.line, line_days, d, h.eps_basis)
        out.append((d, close, value, None if value is None else (1 - value / close) * 100))
    return out


# --------------------------------------------------------------------------
# Public entry points
# --------------------------------------------------------------------------
def _history_for(
    ticker: str, session: requests.Session, user_agent: str, setup: dict, yields: list[tuple[date, float]],
    erp: float, market_beta: bool, window_start: date, today: date,
    eps_bases: tuple[str, ...] = (DEFAULT_BASIS,),
    erp_schedule: Optional[list[tuple[date, float]]] = None,
    own_beta: bool = False,
    blume: bool = True,
    release_items: bool = False,
) -> list[TickerHistory]:
    """One TickerHistory per EPS basis in `eps_bases`, all from one download.
    With `erp_schedule` (--erp-by-year) the ERP follows it instead of `erp`;
    with `own_beta`, beta is the company's own at each date
    (own_beta_schedule; Blume-adjusted unless `blume` is off), the industry
    beta before enough price history exists. With `release_items`, each
    point's press-release EPS reconciliation (release_reconciliation)."""
    erp_at = (lambda d: erp_on(erp_schedule, d)) if erp_schedule else (lambda d: erp)
    key = _sec_ticker(ticker)
    if key not in setup["ticker_map"]:
        raise RuntimeError("not found in SEC's ticker list")
    cik, company = setup["ticker_map"][key]
    facts = fetch_company_facts(cik, session, user_agent)
    _, quarters = fiscal_quarters(facts)
    data, filings = load_filings(cik, session, user_agent, window_start - timedelta(days=FILINGS_LOOKBACK_DAYS))
    profile = fetch_sec_profile(cik, session, user_agent, data=data)
    industry = resolve_industry(ticker, company, profile, setup["companies"], setup["companies_reason"],
                                setup["sic_map"], setup["overrides"])
    beta = choose_beta(industry, setup["industry_betas"], setup["betas_reason"], market_beta)

    releases, notes = find_releases(quarters, filings)
    if not releases:
        raise RuntimeError("no earnings releases found in SEC's filing list")
    # Prices from the second-to-last release before the window: the last one's
    # measurement date can still fall inside the window.
    before = [r for r in releases if r.release_date < window_start]
    price_start = (before[-2] if len(before) >= 2 else before[-1] if before else releases[0]).release_date
    beta_schedule, beta_notes = None, []
    if own_beta:  # one request, reaching back far enough for the first regression
        beta_start = _months_before(min(price_start, window_start), OWN_BETA_MONTHS + 1)
        prices, splits, total = fetch_price_history(ticker, beta_start, today, adjusted=True)
        prices = [(d, c) for d, c in prices if d >= price_start]
        beta_schedule = own_beta_schedule(total, fetch_benchmark_history(beta_start, today), today, blume)
        first = beta_schedule[0][0] if beta_schedule else None
        if first is None or first > min(window_start, price_start):
            beta_notes.append(f"own beta needs {OWN_BETA_MIN_MONTHS} monthly returns; "
                              + (f"before {first}" if first else "throughout")
                              + f" the beta is {beta.beta:.2f} ({beta.source})")
    else:
        prices, splits = fetch_price_history(ticker, price_start, today)

    def beta_at(d: date) -> BetaChoice:
        """The beta in the cost of equity on d: own (--own-beta) where available, else `beta`."""
        row = own_beta_on(beta_schedule, d) if beta_schedule else None
        return BetaChoice(row[1], row[2], own_beta_source(row, blume)) if row else beta

    days = [d for d, _ in prices]
    close_on = dict(prices)

    measured = []
    for rel in releases:
        if rel.release_date < price_start:
            continue
        rel.measurement_date = _measurement_day(days, rel)
        if rel.measurement_date is None:
            notes.append(f"the quarter ended {rel.quarter_end} was released on {rel.release_date} ({rel.form}); "
                         "there's no closing price after it yet, so it gets no step")
        else:
            measured.append(rel)
    shown = ([r for r in measured if r.measurement_date < window_start][-1:]
             + [r for r in measured if r.measurement_date >= window_start])

    # 10-Q/10-K filings with EPS facts, the only ones a TTM is built from
    eps_filed = sorted({date.fromisoformat(r["filed"]) for r in _eps_rows(facts)[1] if is_periodic_report(r)})
    points, ttms, pre_xbrl_skipped = [], [], []  # ttms: each point's TtmEps (its quarters)
    for rel in shown:
        eps, why = _ttm_for(rel, facts, splits, eps_filed[0], eps_filed)
        if eps is None:
            if _pre_xbrl(rel, eps_filed[0]):
                pre_xbrl_skipped.append(rel)  # summarized in one note below
            else:
                notes.append(f"quarter ended {rel.quarter_end}: {why}; skipped")
            continue
        point_notes = []
        if rel.eps_from == "pre-XBRL backfill":
            point_notes.append(f"pre-XBRL backfill: SEC's machine-readable (XBRL) data didn't cover this TTM's "
                               f"quarters when it was released, so its EPS is as first reported in XBRL, filed "
                               f"{rel.eps_as_of} (the step stays at the release date)")
        elif rel.eps_from:
            point_notes.append(f"EPS from the {rel.eps_from} filed {rel.eps_as_of}: SEC's data credits this "
                               f"quarter's figures to that amendment, not the original filing of {rel.cutoff}")
        if rel.other_8k_days:
            point_notes.append(f"earnings 8-Ks (item {EARNINGS_ITEM}) for this quarter were also filed on "
                               f"{', '.join(map(str, rel.other_8k_days))}; the step uses the first, "
                               f"{rel.release_date}, which is early if that one was a pre-announcement")
        rd = None
        if "rd_adjusted" in eps_bases:  # R&D as known with the EPS, shares on today's basis
            try:
                rd = rd_adjustment(facts, eps, as_of=rel.eps_as_of or rel.cutoff, splits=splits)
            except Exception as exc:  # don't lose the point over it; it isn't charted there
                rd = RdAdjustment(None, notes=[f"R&D adjustment failed ({exc})"])
        try:  # gains on investments as known with the EPS: the adjusted TTM, the standard basis
            inv = investment_gain_adjustment(facts, eps, profile.sic, as_of=rel.eps_as_of or rel.cutoff, splits=splits)
        except Exception as exc:  # the point falls back to raw TTM, with a note
            inv = InvestmentAdjustment(None, basis="failed", notes=[f"investment-gain adjustment failed ({exc})"])
        t_date, t_pct = _yield_on(yields, rel.measurement_date)
        res = compute(ticker, company, profile.sic, close_on[rel.measurement_date],
                      rel.measurement_date.isoformat(), "Yahoo Finance daily close", eps, t_date, t_pct,
                      industry, beta_at(rel.measurement_date), erp_at(rel.measurement_date),
                      extra_notes=point_notes, rd=rd, inv=inv)
        points.append((rel, res))
        ttms.append(eps)

    backfilled = [rel for rel, _ in points if rel.eps_from == "pre-XBRL backfill"]
    if backfilled:
        sources = ", ".join(sorted({str(rel.eps_as_of) for rel in backfilled}))
        notes.append(f"{len(backfilled)} release(s) from {backfilled[0].release_date} to {backfilled[-1].release_date} "
                     f"came before SEC's XBRL data covered their quarters; their EPS is backfilled from the first "
                     f"XBRL filing(s) reporting those quarters ({sources}), with the steps at the original release "
                     "dates (marked ~)")
    for rel, _ in points:
        if rel.eps_from and rel.eps_from != "pre-XBRL backfill":
            notes.append(f"quarter ended {rel.quarter_end}: EPS from the {rel.eps_from} filed {rel.eps_as_of}, "
                         f"since SEC's data credits the quarter to it rather than the original of {rel.cutoff} "
                         "(marked ~)")
    if pre_xbrl_skipped:
        notes.append(f"{len(pre_xbrl_skipped)} release(s) for the quarters ended {pre_xbrl_skipped[0].quarter_end} "
                     f"to {pre_xbrl_skipped[-1].quarter_end} skipped: SEC's XBRL EPS history starts with the quarter "
                     f"ended {quarters[0].end}, too late for their four-quarter TTM even from later filings")
    if not points:
        raise RuntimeError("no measurement point could be computed" + "".join(f"\n    - {n}" for n in notes))
    if points[0][0].measurement_date >= window_start:
        notes.append("no release before the window start, so the no-growth line starts at the first release")
    lagging = [str(rel.quarter_end) for rel, res in points
               if res.ttm_vs_two_year_pct is not None and abs(res.ttm_vs_two_year_pct) > LAG_WARNING * 100]
    if lagging:
        notes.append(f"TTM EPS was more than {LAG_WARNING:.0%} above or below the 2-year EPS after the releases for "
                     f"the quarters ended {', '.join(lagging)} (marked !): a one-off may sit in the TTM, or the 2-year "
                     "EPS lags a real change in earnings; compare the 2-year line (--eps-basis two_year)")
    notes += beta_notes
    if notes:  # the latest point's notes carry the ticker-level ones too (e.g. a quarter without a step)
        last = points[-1][1]
        last.notes = NOTE_SEPARATOR.join([n for n in (last.notes, *notes) if n])

    window_prices = [(d, c) for d, c in prices if d >= window_start]
    # Each quarter's diluted shares as known with its EPS, on today's basis, for items stated in dollars only
    items = [release_reconciliation(cik, rel, session, user_agent,
                                    quarter_diluted_shares(facts, rel.quarter_end, rel.eps_as_of or rel.cutoff, splits))
             for rel, _ in points] if release_items else None
    versions = []
    for basis in eps_bases:
        # The EPS charted at each point: this basis, or TTM where it isn't available.
        label = EPS_BASES[basis].label
        eps_used = []
        for _, res in points:
            value = _basis_eps(basis, res)
            eps_used.append((value, basis) if value is not None else (res.eps_ttm, "ttm"))
        fell_back = [i for i, (_, b) in enumerate(eps_used) if b != basis]
        why = ("no TTM a year earlier: " + "; ".join(dict.fromkeys(ttms[i].prior_reason for i in fell_back))
               if basis == "two_year" else "see that point's notes")
        version_notes = notes + ([f"{label} isn't available for the quarter(s) ended "
                                               f"{', '.join(str(points[i][0].quarter_end) for i in fell_back)} "
                                               f"({why}), so its lines are left out of the chart for those periods "
                                               "(the table shows TTM EPS there, marked +)"] if fell_back else [])
        # No R&D tag at all: the adjustment is zero (rd_current None), so this version repeats TTM EPS.
        if basis == "rd_adjusted" and all(res.rd_current is None and res.rd_adjustment_per_share == 0
                                          for _, res in points):
            version_notes.append(f"{company} reports no R&D expense in SEC's data (no R&D-tagged line; it may sit "
                                 "under another expense line), so R&D-adjusted EPS equals the adjusted TTM EPS")
        line = no_growth_line(points, prices, yields, lambda d: beta_at(d).beta, erp_at, window_start, eps_used)
        versions.append(TickerHistory(ticker.upper(), company, window_start, today, beta, erp_at(today), points,
                                      line, window_prices, version_notes, basis, eps_used, erp_schedule,
                                      beta_schedule, blume, items))
    return versions


def collect_history(
    tickers: list[str],
    market_beta: bool = False,
    erp_pct: Optional[float] = None,
    window_days: int = DEFAULT_WINDOW_DAYS,
    eps_basis: str | list[str] | tuple[str, ...] = DEFAULT_BASIS,
    erp_by_year: bool = False,
    own_beta: bool = False,
    blume: bool = True,
    release_items: bool = False,
) -> list[TickerHistory]:
    """PVGO history for each ticker over the last `window_days` days.
    `release_items` also fetches each release's press-release EPS
    reconciliation (one SEC request per release, cached; see
    release_reconciliation).
    `market_beta` forces beta 1.0; `own_beta` uses the company's own beta at
    each date instead (60 monthly returns vs the S&P 500, Blume-adjusted, or
    the regression slope as is with `blume` off); `erp_pct` overrides the equity risk
    premium (percent); `erp_by_year` uses Damodaran's implied ERP at each
    date instead (damodaran_implied_erp.csv); `eps_basis` picks the EPS
    behind the no-growth value and growth share: "ttm_adjusted" (the default),
    "ttm", "two_year" (trimmed 2-year EPS), "six_month" or "rd_adjusted" -- or a list
    of them, giving one TickerHistory per ticker and basis (in that order),
    all from one download per ticker. Tickers that fail are reported and
    skipped."""
    if erp_by_year and erp_pct is not None:
        raise ValueError("choose one ERP: --erp (one number) or --erp-by-year, not both")
    if own_beta and market_beta:
        raise ValueError("choose one beta: --market-beta (1.0) or --own-beta, not both")
    if not blume and not own_beta:
        raise ValueError("--raw-beta needs --own-beta: only the company's own beta is Blume-adjusted")
    if erp_pct is not None and erp_pct <= 0:
        raise ValueError("--erp must be a positive percentage, e.g. 4.3")
    if window_days < 30:
        raise ValueError("--days must be at least 30")
    chosen = [eps_basis] if isinstance(eps_basis, str) else list(eps_basis)
    if not chosen or any(b not in EPS_BASES for b in chosen):
        raise ValueError(f"--eps-basis must be one or more of: {', '.join(EPS_BASES)}")
    eps_bases = tuple(b for b in EPS_BASES if b in chosen)  # EPS_BASES order; no repeats
    erp = EQUITY_RISK_PREMIUM if erp_pct is None else erp_pct / 100
    erp_schedule = load_erp_by_year() if erp_by_year else None  # before any download, so a bad file stops early
    today = date.today()
    window_start = today - timedelta(days=window_days)

    user_agent = get_user_agent()
    with requests.Session() as session:
        yields = fetch_ten_year_yields(session, window_start - timedelta(days=YIELD_LOOKBACK_DAYS), today)
        companies, companies_reason = load_company_index(session)
        industry_betas, betas_reason = (None, "") if market_beta else load_industry_betas(session)
        setup = {
            "ticker_map": load_ticker_map(session, user_agent),
            "sic_map": load_sic_map(),
            "overrides": load_overrides(),
            "companies": companies,
            "companies_reason": companies_reason,
            "industry_betas": industry_betas,
            "betas_reason": betas_reason,
        }
        histories = []
        for ticker in tickers:
            try:
                histories.extend(_history_for(ticker, session, user_agent, setup, yields, erp, market_beta,
                                              window_start, today, eps_bases, erp_schedule, own_beta,
                                              blume, release_items))
            except Exception as exc:  # one bad ticker shouldn't stop the rest
                print(f"{ticker.upper()}: skipped -- {exc}")
    return histories


# --------------------------------------------------------------------------
# Output: table, CSVs, chart
# --------------------------------------------------------------------------
def _money(v: float) -> str:
    return f"{'-' if v < 0 else ''}${abs(v):,.2f}"


def _erp_at(h: TickerHistory, d: date) -> float:
    """The ERP in h's cost of equity on d."""
    return erp_on(h.erp_schedule, d) if h.erp_schedule else h.erp


def _beta_on(h: TickerHistory, d: date) -> float:
    """The beta in h's cost of equity on d."""
    row = own_beta_on(h.beta_schedule, d) if h.beta_schedule else None
    return row[1] if row else h.beta.beta


def _beta_range(h: TickerHistory) -> str:
    """The beta's span over h's no-growth line, e.g. "1.05 to 1.46"."""
    values = [p.beta for p in h.line]
    low, high = f"{min(values):.2f}", f"{max(values):.2f}"
    return low if low == high else f"{low} to {high}"


def year_end_rows(h: TickerHistory) -> list[tuple[LinePoint, float, Optional[float]]]:
    """(line point, close, growth share %) at each completed year's last
    trading day in the window: the reading Counterpoint's year-end charts
    show. The growth share is None where this version's EPS isn't available."""
    if not h.prices:
        return []
    close_on = dict(h.prices)
    year_last = {}
    for d, _ in h.prices:
        year_last[d.year] = d
    wanted = {d for y, d in year_last.items() if y < h.prices[-1][0].year}
    at = {p.day: p for p in h.line if p.day in wanted}  # the last point that day: after any step
    return [(at[d], close_on[d], (1 - at[d].value / close_on[d]) * 100 if at[d].basis == h.eps_basis else None)
            for d in sorted(at)]


def _erp_range(h: TickerHistory) -> str:
    """The ERP's span over h's no-growth line, e.g. "4.23% to 6.01%"."""
    values = [p.erp for p in h.line]
    low, high = f"{min(values):.2%}", f"{max(values):.2%}"
    return low if low == high else f"{low} to {high}"
