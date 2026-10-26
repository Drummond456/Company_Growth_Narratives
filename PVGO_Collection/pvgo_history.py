"""
One-year PVGO history per ticker: the daily share price against the
no-growth (steady-state) value per share,

    no-growth value = adjusted TTM EPS / cost of equity

charted over the last 365 days. The gap between the two lines is PVGO (see
pvgo_growth_share.py for the method). The no-growth line steps to a new level at
each earnings release and moves weekly with the 10-year Treasury in between.
The growth share, PVGO / price = 1 - no-growth value / close, is plotted
daily on a right-hand axis. The adjusted TTM EPS (the default)
is the sum of the last 4 fiscal quarters of GAAP diluted EPS without the gains
and losses on investments, less 25% tax; raw TTM EPS (--eps-basis ttm) and the
trimmed 2-year EPS (--eps-basis two_year, for comparisons with Counterpoint's
charts) are kept.

How the line is built:
  - Earnings release, per fiscal quarter (SEC submissions API): the first
    8-K with item 2.02 ("Results of Operations") filed after the quarter end
    and on or before the quarter's 10-Q/10-K; without one, the 10-Q/10-K
    filing date. The 10-Q/10-K is the original filing (not a /A) whose
    reportDate is within 7 days of the quarter end (52/53-week years). The
    form that set each date, and the time SEC accepted it (New York time),
    are recorded. Earnings 8-Ks on more than one day for a quarter are noted.
  - Measurement date: the first trading day whose close comes after the
    release was public (from the price history, not a calendar): the
    release day itself when SEC accepted the filing before the 4:00 pm
    close, otherwise the next trading day.
    Today counts only after the close.
  - EPS as known at each release (point-in-time): built only from XBRL
    facts filed on or before that quarter's 10-Q/10-K, the TTM's four
    quarters and the four before them. Yahoo's closes are adjusted for
    stock splits, so each EPS fact is divided by the splits dated after its
    filing date (Yahoo's split history), with a note.
    Two exceptions, marked ~ in the table and noted: when SEC's data credits
    the quarter to an amendment (10-Q/A, 10-K/A) filed within 45 days of the
    original, the amendment's date is used; and when the TTM reaches back
    before the company's first XBRL filing (2009-2011 for most companies),
    its EPS comes from the earliest later filing that has those quarters
    (pre-XBRL backfill). Either way the step stays at the release date.
  - Cost of equity: 10-year Treasury (FRED DGS10, last value on or before
    the day) + beta x ERP, with beta and ERP held at today's values:
    choose_beta() with the current Damodaran file (or --market-beta), and
    EQUITY_RISK_PREMIUM (or --erp). With --erp-by-year the ERP instead
    follows Damodaran's implied ERP at each date: his estimate each January
    (damodaran_implied_erp.csv, kept by hand), interpolated in between.
    With --own-beta the beta is the company's own at each date: the slope
    of its last 60 monthly total returns on the S&P 500's (Yahoo Finance,
    prices known then), Blume-adjusted (0.67 x slope + 0.33; --raw-beta
    uses the slope as is), re-estimated each month; the industry beta before
    36 monthly returns exist.
  - Line points: a vertical step at each measurement date (old EPS, then new
    EPS, at that day's yield), each week's last trading day in between (EPS
    in effect / that week's yield), each completed year's last trading day,
    the window's first trading day, and the latest close.
  - A newer quarter with an 8-K (or 10-Q) whose 10-Q/10-K isn't in SEC's XBRL
    company facts yet gets no step: the previous EPS is kept, with a note.

Releases shown: every release whose measurement date falls in the window
(--days, default 365), plus the latest one before it so the line starts at
the left edge. At each measurement date, pvgo_growth_share.compute() gives the
full result at that day's close and Treasury yield (the R&D-adjusted reading
only with --eps-basis rd_adjusted).

EPS basis (--eps-basis): the EPS behind the no-growth value, PVGO and growth
share, at each point as known then:
  - ttm_adjusted (default): TTM diluted EPS without the gains and losses on
    investments, less 25% tax. Other one-time items enter at their release and
    leave four quarters later, so each step can be explained (Company_Narrative_
    Aggregation labels them); it reacts to a real change in earnings within a year.
  - ttm: TTM diluted EPS as reported, investment marks included.
  - two_year: the trimmed 2-year EPS, for comparisons with Counterpoint: it
    damps one-time items by one fixed rule, and lags a real change in earnings.
  - six_month: the TTM's last 2 quarters x 2 (annualized), for comparison:
    it reacts soonest, but a one-time item weighs twice what it does in the
    TTM, and seasonal quarters make it swing within the year.
  - rd_adjusted: the TTM EPS + the R&D adjustment of pvgo_growth_share.py,
    computed from R&D and share counts filed by each quarter's 10-Q/10-K
    (share counts on today's share basis).
  Where the chosen basis isn't available at a point (the 2-year EPS needs 8
  consecutive quarters; R&D needs 3+ prior years of R&D
  and a share count), the table shows TTM EPS for that point (marked +,
  with a note), and the chart leaves that basis's lines out for the period
  the point covers, so they never sit on top of the TTM line.
  Lag warning: points where TTM EPS is more than LAG_WARNING above or below
  the 2-year EPS are marked ! and listed in a note: there the 2-year EPS may
  lag a real change in earnings.
  Choose several (--eps-basis two_year ttm six_month rd_adjusted) to chart
  them together from one download: each gets its own no-growth line (solid)
  and growth-share line (dashed) in one color, without the PVGO shading.

Smoothing (--smooth weekly, monthly or yearly), for the chart only: every
line is drawn as a centered moving average of 5, 21 or 252 trading days.
Weekly and monthly: the no-growth average doesn't reach across a measurement
date, so its steps stay sharp. Yearly: it does, so the lines show the trend
(a change shows up to six months early and late). The growth share is
computed from the smoothed price and no-growth value. The measurement dots
stay at the actual close, and the tables and CSVs are unchanged.

Outputs for each ticker: the charts in PVGO_Collection/, the CSVs in
PVGO_Collection/Outputs_CSV_data/ (a basis other than ttm adds its
name, e.g. <TICKER>_pvgo_history_two_year.png; a chart of several bases names
them all, e.g. <TICKER>_pvgo_history_ttm_two_year.png, and each basis
still gets its own CSVs):
  <TICKER>_pvgo_history.png          the chart
  <TICKER>_pvgo_history_points.csv   the result at each measurement date, with
                                     quarter_end, release_date, release_form,
                                     cutoff_date and measurement_date columns
  <TICKER>_pvgo_history_series.csv   daily close, no-growth line (as drawn) and
                                     growth share, plus the line's points
  <TICKER>_pvgo_history_year_end.csv the reading at each completed year's last
                                     trading day (Counterpoint's unit)
  <TICKER>_pvgo_history_year_end.png those year-end growth shares as a line, the
                                     format of Counterpoint's company charts

Needs SEC_EDGAR_USER_AGENT in .env, like pvgo_growth_share.py. SEC responses
are kept in cache/sec/ (a day; older filing-list pages 30 days), so a
rerun with different chart settings makes no SEC requests.

Usage:
    python pvgo_history.py <ticker>
    python pvgo_history.py <ticker 1> <ticker 2>      # one chart per ticker
    python pvgo_history.py <ticker> --erp 4.3        # ERP in percent
    python pvgo_history.py <ticker> --erp-by-year    # Damodaran's ERP at each date
    python pvgo_history.py <ticker> --market-beta    # beta 1.0
    python pvgo_history.py <ticker> --own-beta       # the company's own beta at each date
    python pvgo_history.py <ticker> --own-beta --raw-beta   # ... without the Blume adjustment
    python pvgo_history.py <ticker> --days 730       # window length in days
    python pvgo_history.py <ticker> --eps-basis ttm   # or six_month, rd_adjusted
    python pvgo_history.py <ticker> --eps-basis two_year ttm six_month rd_adjusted   # together
    python pvgo_history.py <ticker> --smooth monthly   # or weekly, yearly: smoother chart lines
Or set TICKER, YEARS, the PLOT_* switches, SMOOTHING and ERP_BY_YEAR at the
top of pvgo_history_run.py and run that file.
"""

from __future__ import annotations

import argparse
import csv
import os
import textwrap
from dataclasses import asdict
from datetime import date
from itertools import groupby
from typing import Optional

import requests

from pvgo_growth_share import PvgoResult
from pvgo_history_series import (
    _beta_on,
    _beta_range,
    collect_history,
    daily_values,
    EPS_BASES,
    _erp_at,
    _erp_range,
    LinePoint,
    _money,
    TickerHistory,
    year_end_rows,
)
from pvgo_inputs import (
    BASE_DIR,
    BLUME_WEIGHT,
    CSV_DIR,
    DEFAULT_BASIS,
    DEFAULT_WINDOW_DAYS,
    EQUITY_RISK_PREMIUM,
    LAG_WARNING,
    OWN_BETA_MONTHS,
    POINT_COLUMNS,
    RELEASE_ITEMS_COLUMNS,
    SERIES_COLUMNS,
    SMOOTHING,
)


def _runs(items: list, keep) -> list[list]:
    """The consecutive stretches of `items` for which keep(item) is true."""
    runs, current = [], []
    for item in items:
        if keep(item):
            current.append(item)
        elif current:
            runs.append(current)
            current = []
    if current:
        runs.append(current)
    return runs


def _check_smoothing(smoothing: Optional[str]) -> None:
    if smoothing is not None and smoothing not in SMOOTHING:
        raise ValueError(f"smoothing must be None, {' or '.join(map(repr, SMOOTHING))}; got {smoothing!r}")


def _moving_average(values: list[float], window: int) -> list[float]:
    """Centered moving average over `window` values; near either end, the
    average of the values the window still covers."""
    half = window // 2
    out = []
    for i in range(len(values)):
        lo, hi = max(0, i - half), min(len(values), i + half + 1)
        out.append(sum(values[lo:hi]) / (hi - lo))
    return out


def _smoothed(run: list[tuple], step_days: set[date], smooth_close: dict[date, float], window: int) -> list[tuple]:
    """A drawn stretch of daily_values() rows as charted with smoothing: the
    close from the smoothed price line; the no-growth value averaged only
    within each stretch between the dates in `step_days` (the measurement
    dates, so a step isn't blurred into the days before the release; none
    for yearly smoothing); and the growth share from those two, so it
    matches the gap between the lines as drawn."""
    pieces = []
    for row in run:
        if not pieces or row[0] in step_days:
            pieces.append([])
        pieces[-1].append(row)
    out = []
    for piece in pieces:
        for (d, *_), value in zip(piece, _moving_average([r[2] for r in piece], window)):
            close = smooth_close[d]
            out.append((d, close, value, (1 - value / close) * 100))
    return out


def _stepped(rows: list[tuple], step_days: set[date]) -> list[tuple[date, float]]:
    """(day, no-growth value) to draw from smoothed rows: the old level is
    held up to each measurement date for a vertical step, like the unsmoothed
    line."""
    out = []
    for d, _, value, _ in rows:
        if out and d in step_days:
            out.append((d, out[-1][1]))
        out.append((d, value))
    return out


def format_points_table(h: TickerHistory) -> str:
    label, column = EPS_BASES[h.eps_basis].label, EPS_BASES[h.eps_basis].column
    standard = h.eps_basis == DEFAULT_BASIS
    by_year = h.erp_schedule is not None  # --erp-by-year: an ERP column, and the header says so
    own = h.beta_schedule is not None  # --own-beta: a beta column, and the header says so
    beta_text = (f"own beta by month ({_beta_range(h)}{'' if h.blume else ', unadjusted'})" if own
                 else f"beta {h.beta.beta:.2f} held constant")
    if by_year:
        held = f"{beta_text}; ERP by year (Damodaran's implied ERP, {_erp_range(h)})"
    elif own:
        held = f"{beta_text}; ERP {h.erp:.2%} held constant"
    else:
        held = f"beta {h.beta.beta:.2f} and ERP {h.erp:.2%} held constant"
    lines = [
        f"{h.ticker}  {h.company}   window {h.window_start} .. {h.window_end}; {held}; no-growth value from "
        f"{label}",
        f"  {'quarter end':<12} {'release (New York time)':<21} {'measured':<11} {column:>8} {'10Y':>6}"
        + (f" {'ERP':>6}" if by_year else "") + (f" {'beta':>5}" if own else "") + f" {'r':>7} "
        f"{'no-growth':>10} {'price':>10} {'PVGO':>10} {'growth share':>13}",
    ]
    eps_used = h.eps_used
    lag_limit = LAG_WARNING * 100
    for (rel, res), (eps, basis) in zip(h.points, eps_used):
        mark = "*" if rel.measurement_date < h.window_start else " "
        if standard:  # compute()'s own result: TTM EPS
            no_growth, pvgo, share = res.no_growth_value, res.pvgo, res.growth_share_pct
        else:  # compute()'s formula on the charted EPS
            r = res.treasury_10y_pct / 100 + _beta_on(h, rel.measurement_date) * _erp_at(h, rel.measurement_date)
            no_growth = eps / r
            pvgo, share = res.price - no_growth, (1 - eps / (res.price * r)) * 100
        lagging = res.ttm_vs_two_year_pct is not None and abs(res.ttm_vs_two_year_pct) > lag_limit
        flags = ("+" if basis != h.eps_basis else "") + ("~" if rel.eps_from else "") + ("!" if lagging else "")
        erp_cell = (f" {res.equity_risk_premium_pct:>5.2f}%" if by_year else "") + (
            f" {res.beta_scaled:>5.2f}" if own else "")
        released_at = rel.accepted.strftime("%H:%M") if rel.accepted else ""
        lines.append(
            f" {mark}{rel.quarter_end}   {rel.release_date} {released_at:<5} {rel.form:<4} {rel.measurement_date}  "
            f"{_money(eps):>8} {res.treasury_10y_pct:>5.2f}%{erp_cell} {res.cost_of_equity_pct:>6.2f}% "
            f"{_money(no_growth):>10} {_money(res.price):>10} {_money(pvgo):>10} "
            f"{share:>12.1f}%" + (f"  {flags}" if flags else ""))
    if any(rel.measurement_date < h.window_start for rel, _ in h.points):
        lines.append("  * measured before the window; sets the no-growth line's level at the left edge")
    if any(basis != h.eps_basis for _, basis in eps_used):
        lines.append(f"  + {label} not available at this point: TTM EPS shown here, not charted")
    if any(rel.eps_from for rel, _ in h.points):
        lines.append("  ~ EPS from a later SEC filing than the release's own 10-Q/10-K (see the notes)")
    if any(res.ttm_vs_two_year_pct is not None and abs(res.ttm_vs_two_year_pct) > lag_limit for _, res in h.points):
        lines.append(f"  ! TTM EPS more than {LAG_WARNING:.0%} above or below the 2-year EPS: the 2-year EPS may lag "
                     "a real change in earnings here")
    year_ends = [(p.day.year, share) for p, _, share in year_end_rows(h) if share is not None]
    if year_ends:
        cells = [f"{y} {share:+.0f}%" for y, share in year_ends]
        lines.append("  Year-end growth share: " + "\n                         ".join(
            ", ".join(cells[i:i + 8]) for i in range(0, len(cells), 8)))
    lines += [f"  Note: {n}" for n in h.notes]
    return "\n".join(lines)


def output_paths(ticker: str, eps_basis: str = DEFAULT_BASIS) -> dict[str, str]:
    """Output files; a basis other than raw "ttm" adds its name (pinned to "ttm", not DEFAULT_BASIS, so a
    change of default never renames files an explanation run reads), so runs
    on different bases don't overwrite each other."""
    name = f"{ticker.upper()}_pvgo_history" + ("" if eps_basis == "ttm" else f"_{eps_basis}")
    chart, csv_stem = os.path.join(BASE_DIR, name), os.path.join(CSV_DIR, name)
    return {"chart": chart + ".png", "points": csv_stem + "_points.csv", "series": csv_stem + "_series.csv",
            "year_end": csv_stem + "_year_end.csv"}


def release_items_path(ticker: str) -> str:
    """--release-items: one file per ticker, whatever the bases (the press releases don't depend on them)."""
    return os.path.join(CSV_DIR, f"{ticker.upper()}_pvgo_history_release_items.csv")


def chart_path(ticker: str, eps_bases: list[str]) -> str:
    """The chart for one EPS basis is output_paths()'s; a chart of several
    names them all, e.g. MSFT_pvgo_history_two_year_ttm.png."""
    if len(eps_bases) == 1:
        return output_paths(ticker, eps_bases[0])["chart"]
    return os.path.join(BASE_DIR, f"{ticker.upper()}_pvgo_history_{'_'.join(eps_bases)}.png")


def write_outputs(versions: list[TickerHistory], smoothing: Optional[str] = None) -> list[str]:
    """For one ticker: each version's (EPS basis's) CSVs (points, series and,
    with a completed year in the window, year-end), plus one chart with all
    the versions and, with two or more year-ends, a year-end chart, in
    PVGO_Collection/ (the CSVs in its Outputs_CSV_data/). Returns the paths,
    chart first (then the year-end chart). `smoothing` ("weekly", "monthly" or "yearly") applies to the
    history chart only; it's checked here, before anything is written."""
    _check_smoothing(smoothing)
    os.makedirs(CSV_DIR, exist_ok=True)
    written = [chart_path(versions[0].ticker, [v.eps_basis for v in versions])]
    for v in versions:
        paths = output_paths(v.ticker, v.eps_basis)
        write_points_csv(v, paths["points"])
        write_series_csv(v, paths["series"])
        written += [paths["points"], paths["series"]]
        if year_end_rows(v):
            write_year_end_csv(v, paths["year_end"])
            written.append(paths["year_end"])
    if versions[0].release_items is not None:
        path = release_items_path(versions[0].ticker)
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=RELEASE_ITEMS_COLUMNS)
            writer.writeheader()
            writer.writerows(versions[0].release_items)
        written.append(path)
    plot_history(versions, written[0], smoothing)
    if len(year_end_rows(versions[0])) >= 2:  # the year-end chart needs two years to draw a line
        written.insert(1, year_end_chart_path(written[0]))
        plot_year_end(versions, written[1])
    return written


def write_points_csv(h: TickerHistory, path: str) -> None:
    """compute()'s result at each measurement date, after eps_basis (the
    basis used at that point: this version's, or ttm where it fell back) and
    eps_charted (blank where it fell back, since those periods aren't
    charted)."""
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=POINT_COLUMNS + ["eps_basis", "eps_charted"]
                                + list(PvgoResult.__dataclass_fields__))
        writer.writeheader()
        for (rel, res), (eps, basis) in zip(h.points, h.eps_used):
            row = {
                "quarter_end": rel.quarter_end.isoformat(),
                "release_date": rel.release_date.isoformat(),
                "release_time": rel.accepted.strftime("%H:%M") if rel.accepted else "",  # New York time
                "release_form": rel.form,
                "release_accession": rel.accession,
                "cutoff_date": rel.cutoff.isoformat(),
                "measurement_date": rel.measurement_date.isoformat(),
                "eps_basis": basis,
                "eps_charted": round(eps, 4) if basis == h.eps_basis else "",
                **asdict(res),
            }
            writer.writerow(row)


def write_year_end_csv(h: TickerHistory, path: str) -> None:
    """One row per completed year in the window: the reading at its last
    trading day (year_end_rows), with the EPS, Treasury, beta, ERP and cost
    of equity behind it. Growth share is blank where this version's EPS
    isn't available."""
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["year", "date", "close", "no_growth_value", "growth_share_pct", "eps", "eps_basis",
                         "eps_through", "treasury_10y_pct", "beta", "erp_pct", "cost_of_equity_pct"])
        for p, close, share in year_end_rows(h):
            writer.writerow([p.day.year, p.day.isoformat(), round(close, 4), round(p.value, 4),
                             "" if share is None else round(share, 2), p.eps, p.basis, p.eps_through.isoformat(),
                             p.treasury_pct, round(p.beta, 4), round(p.erp * 100, 4), round(p.cost_of_equity * 100, 4)])


def write_series_csv(h: TickerHistory, path: str) -> None:
    """One row per trading day in the window: the close, the no-growth line
    as drawn (linear between its points) and the growth share. The `point`,
    EPS and Treasury columns are filled on the days with a line point
    (start, weekly, year-end, measurement, final); on a measurement date,
    no_growth_value_before_step is the old level. eps_basis says which
    basis the EPS is at each line point (ttm where the chosen one isn't
    available). The erp_pct and beta columns give each line point's ERP and
    beta, constant or not (always written: explain_run.py splits rates/other by
    them)."""
    columns = SERIES_COLUMNS + ["erp_pct", "beta"]
    on_day: dict[date, list[LinePoint]] = {}
    for p in h.line:
        on_day.setdefault(p.day, []).append(p)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(columns)
        for d, close, value, share in daily_values(h):
            row = [d.isoformat(), round(close, 4), "" if value is None else round(value, 4),
                   "" if share is None else round(share, 2)]
            pts = on_day.get(d)
            if not pts:
                writer.writerow(row + [""] * (len(columns) - len(row)))
                continue
            p = pts[-1]  # after any step
            before = next((q.value for q in pts if q.kind == "step-before"), None)
            writer.writerow(row + [
                "" if before is None else round(before, 4), "measurement" if p.kind == "step-after" else p.kind,
                p.eps, p.basis, p.eps_through.isoformat(), p.treasury_pct, p.treasury_date.isoformat(),
                round(p.cost_of_equity * 100, 4),
                round(p.erp * 100, 4), round(p.beta, 4),
            ])


def _same_as(versions: list[TickerHistory]) -> dict[int, int]:
    """Version index -> index of an earlier version whose no-growth line is
    identical (e.g. R&D-adjusted for a company with no R&D in SEC's data)."""
    same: dict[int, int] = {}
    lines = [[(p.day, p.value) for p in v.line] for v in versions]
    for i in range(len(versions)):
        match = next((j for j in range(i) if j not in same and lines[j] == lines[i]), None)
        if match is not None:
            same[i] = match
    return same


def _title_suffix(versions: list[TickerHistory]) -> str:
    """The chart title's tags, e.g. " (2-year EPS, TTM EPS; own beta)", or "own beta, unadjusted"."""
    h = versions[0]
    tags = (", ".join(EPS_BASES[v.eps_basis].label for v in versions)
            if len(versions) > 1 or h.eps_basis != DEFAULT_BASIS else "")
    if h.beta_schedule is not None:
        tags += ("; " if tags else "") + "own beta" + ("" if h.blume else ", unadjusted")
    return f" ({tags})" if tags else ""


def _eps_text(versions: list[TickerHistory]) -> str:
    """The chart footnote's description of the EPS behind each version."""
    h = versions[0]
    if len(versions) > 1:
        text = ("EPS, from the filings available at each release and on today's share basis: "
                + "; ".join(EPS_BASES[v.eps_basis].short for v in versions) + ".")
    else:
        text = EPS_BASES[h.eps_basis].footnote
    return text


def _cost_of_equity_text(h: TickerHistory, treasury: str) -> str:
    """The chart footnote's cost-of-equity sentences. treasury: when the yield is read, e.g.
    "weekly between releases"."""
    text = f"Cost of equity = 10-year Treasury (FRED DGS10, {treasury}) + beta x ERP. "
    if h.beta_schedule is not None:
        text += (f"Beta: the company's own, re-estimated each month from the prior {OWN_BETA_MONTHS} monthly total "
                 "returns against the S&P 500, "
                 + (f"Blume-adjusted ({BLUME_WEIGHT:g} x slope + {1 - BLUME_WEIGHT:.2f})" if h.blume
                    else "unadjusted (the slope itself)")
                 + f": {_beta_range(h)} here. ")
    else:
        text += f"Beta: {h.beta.beta:.2f} ({h.beta.source}), held constant. "
    if h.erp_schedule:
        text += (f"ERP: Damodaran's implied ERP at each date, interpolated between his January estimates "
                 f"({_erp_range(h)} here). ")
    else:
        text += f"ERP: {h.erp:.2%}, held constant. "
    return text


def year_end_chart_path(chart: str) -> str:
    """The year-end chart's path, next to the history chart: <chart name>_year_end.png."""
    return chart[:-len(".png")] + "_year_end.png"


def plot_year_end(versions: list[TickerHistory], path: str) -> None:
    """The growth share at each completed year's last trading day
    (year_end_rows), one line per version: the format of Counterpoint's
    company charts, which show year-end PVGO percentages."""
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure
    from matplotlib.ticker import PercentFormatter

    h, multi = versions[0], len(versions) > 1
    fig = Figure(figsize=(10, 5.5), dpi=150)
    FigureCanvasAgg(fig)
    ax = fig.add_subplot()
    years = sorted({p.day.year for v in versions for p, _, _ in year_end_rows(v)})
    labels = [EPS_BASES[v.eps_basis].label for v in versions]
    same = _same_as(versions) if multi else {}  # identical to an earlier version: dotted on top of it, so both show
    for i, v in enumerate(versions):
        rows = [(p.day.year, share) for p, _, share in year_end_rows(v) if share is not None]
        if not rows:
            continue
        style = {"color": EPS_BASES[v.eps_basis].color if multi else "#2e7d32", "lw": 2, "marker": "o", "ms": 6,
                 "label": f"Growth share, {labels[i]}"}
        if i in same:
            style.update(ls=":", marker="", label=f"Growth share, {labels[i]}: same as {labels[same[i]]} (dotted)")
        ax.plot([y for y, _ in rows], [x for _, x in rows], **style)
    ax.axhline(0, color="#404040", lw=1)
    ax.set_xticks(years)
    ax.set_xticklabels([str(y) for y in years], rotation=90)
    ax.yaxis.set_major_formatter(PercentFormatter(xmax=100, decimals=0))
    ax.set_ylabel("Growth share (PVGO / price)")
    ax.grid(axis="y", alpha=0.3)
    tags = _title_suffix(versions).strip()[1:-1]  # without the parentheses, on its own line
    ax.set_title(f"{h.ticker}: growth share at each year-end" + (f"\n{tags}" if tags else ""),
                 fontsize=11)
    footnote = ("Each point: growth share = PVGO / price = 1 - EPS / (close x cost of equity) at the year's last "
                "trading day, with the EPS in effect that day. " + _cost_of_equity_text(h, "on that day")
                + f"{_eps_text(versions)} Notes: see the history chart and table.")
    wrapped = textwrap.fill(footnote, 175)
    fig.text(0.01, 0.01, wrapped, ha="left", va="bottom", fontsize=7.5, color="#404040")
    footnote_top = 0.02 + 0.024 * (wrapped.count("\n") + 1)
    legend_rows = 0
    if multi:  # in its own strip between the year labels and the footnote, so it never covers a point
        ncol = min(2, len(versions))
        legend_rows = -(-len(versions) // ncol)
        fig.legend(*ax.get_legend_handles_labels(), loc="lower center", bbox_to_anchor=(0.5, footnote_top),
                   ncol=ncol, fontsize=8, frameon=False)
    fig.subplots_adjust(left=0.09, right=0.97, top=0.88 if tags else 0.92,
                        bottom=footnote_top + 0.035 * legend_rows + 0.09)
    fig.savefig(path, dpi=150)


def plot_history(versions: list[TickerHistory], path: str, smoothing: Optional[str] = None) -> None:
    """Daily close and the no-growth line with the PVGO area between them
    ($, left axis), the growth share (%, right axis), release markers, and a
    dot on the price line at each measurement date.

    `versions` are one ticker's versions (EPS bases). Several are charted
    together: each gets a no-growth line (solid) and a growth-share line
    (dashed) in its own color. The PVGO shading is left out then; the gap
    between the price and each no-growth line is that version's PVGO. A
    version identical to an earlier one is drawn dotted on top of it and
    labeled as the same, so neither line hides the other.

    `smoothing` ("weekly", "monthly" or "yearly", already checked by
    write_outputs) draws every line as a centered moving average instead
    (see _smoothed); the dots stay at the actual close."""
    import matplotlib.dates as mdates
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure
    from matplotlib.ticker import MultipleLocator, PercentFormatter

    multi = len(versions) > 1
    h = versions[0]  # prices, releases, window, beta and ERP are the same in every version
    basis_labels = [EPS_BASES[v.eps_basis].label for v in versions]
    days = [d for d, _ in h.prices]
    closes = [c for _, c in h.prices]
    # Each version is drawn only where its own EPS is available: a point that fell back to TTM
    # leaves a gap rather than repeating (and hiding) the TTM line.
    line_runs = [_runs(v.line, lambda p, basis=v.eps_basis: p.basis == basis) for v in versions]
    line_runs = [[[(p.day, p.value) for p in run] for run in runs] for runs in line_runs]  # (day, value) to draw
    values = [value for runs in line_runs for run in runs for _, value in run]  # the $ axis fits the actual values
    # Per version: stretches of (day, close, no-growth value, growth share) on the days it's drawn.
    day_runs = [_runs(daily_values(v), lambda r: r[2] is not None) for v in versions]
    price_line, price_label = closes, "Share price, daily close (left axis)"
    if smoothing:
        window, span, across = SMOOTHING[smoothing]
        price_line, price_label = _moving_average(closes, window), f"Share price, {span} moving average (left axis)"
        smooth_close = dict(zip(days, price_line))
        step_days = set() if across else {rel.measurement_date for rel, _ in h.points}  # where the average restarts
        day_runs = [[_smoothed(run, step_days, smooth_close, window) for run in runs] for runs in day_runs]
        line_runs = [[_stepped(run, step_days) for run in runs] for runs in day_runs]
    drawn = [[r for run in runs for r in run] for runs in day_runs]

    fig = Figure(figsize=(12, 7.5), dpi=150)  # the saving dpi, so text measured below is as it will be drawn
    FigureCanvasAgg(fig)  # a canvas, so text can be measured before saving
    ax = fig.add_subplot()
    ax.plot(days, price_line, color="#1f4e79", lw=1.6, label=price_label)
    same = _same_as(versions) if multi else {}
    for i, (v, label, runs) in enumerate(zip(versions, basis_labels, line_runs)):
        if i in same:  # identical to an earlier line: dotted on top of it, so both show
            style = {"color": EPS_BASES[v.eps_basis].color, "lw": 1.4, "ls": ":",
                     "label": f"No-growth value, {label}: same as {basis_labels[same[i]]} "
                              + ("(dotted)" if runs else "(not drawn)")}
        else:
            style = {"color": EPS_BASES[v.eps_basis].color if multi else "#c55a11", "lw": 1.8,
                     "label": f"No-growth value = {label} / cost of equity (left axis)"}
        for run in runs or [[]]:  # an empty plot still gives the legend entry
            ax.plot([d for d, _ in run], [value for _, value in run], **style)
            style["label"] = None

    if drawn[0] and not multi:
        pvgo_label, negative_label = "PVGO", "Negative PVGO (price below no-growth value)"
        for run in day_runs[0]:
            xs, cs, vs, _ = (list(t) for t in zip(*run))
            above = [c >= v for c, v in zip(cs, vs)]
            ax.fill_between(xs, cs, vs, where=above, interpolate=True, color="#9dc3e6", alpha=0.5, lw=0,
                            label=pvgo_label)
            pvgo_label = None
            if not all(above):
                ax.fill_between(xs, cs, vs, where=[not a for a in above], interpolate=True, color="#f4b183",
                                alpha=0.5, lw=0, label=negative_label)
                negative_label = None
        xs, cs, vs, _ = (list(t) for t in zip(*drawn[0]))
        middle = range(len(xs) // 6, max(len(xs) * 5 // 6, len(xs) // 6 + 1))  # keep the label off the edges
        widest = max(middle, key=lambda i: cs[i] - vs[i])
        if cs[widest] > vs[widest]:
            ax.text(xs[widest], (cs[widest] + vs[widest]) / 2, "PVGO", ha="center", va="center", fontsize=14,
                    fontweight="bold", color="#1f4e79", alpha=0.6)

    release_labels = []
    for i, (rel, _) in enumerate((rel, res) for rel, res in h.points if rel.release_date >= h.window_start):
        ax.axvline(rel.release_date, color="#7f7f7f", ls=":", lw=1.2, label="Earnings release" if i == 0 else None)
        release_labels.append((ax.annotate(
            f"{rel.form} {rel.release_date}\nEPS through {rel.quarter_end}",
            xy=(rel.release_date, 1), xycoords=("data", "axes fraction"), xytext=(3, -4),
            textcoords="offset points", ha="left", va="top", fontsize=7.5, color="#404040",
            bbox={"boxstyle": "round,pad=0.2", "fc": "white", "ec": "none", "alpha": 0.8}), rel))
    shown = [(rel, res) for rel, res in h.points if rel.measurement_date >= h.window_start]
    ax.scatter([rel.measurement_date for rel, _ in shown], [res.price for _, res in shown], s=28,
               color="#1f4e79", zorder=5,
               label="Measurement date (first close after the release)" + (", actual close" if smoothing else ""))

    lowest, highest = min(closes + values), max(closes + values)
    ax.set_ylim(0 if lowest > 0 else lowest * 1.1, highest * 1.12)  # headroom for the release labels
    ax.set_xlim(h.window_start, h.window_end)
    locator = mdates.AutoDateLocator()
    ax.xaxis.set_major_locator(locator)
    ax.xaxis.set_major_formatter(mdates.ConciseDateFormatter(locator))
    ax.set_ylabel("$ per share")
    ax.grid(alpha=0.3)
    ax.set_title(f"{h.ticker}: share price vs. no-growth value{_title_suffix(versions)}", fontsize=12)

    # Growth share on a right-hand axis; a twin axes is drawn on top, so the lines stay above the shading.
    ax_pct = ax.twinx()
    axis_color = "#404040" if multi else "#2e7d32"
    for i, (v, label, runs) in enumerate(zip(versions, basis_labels, day_runs)):
        if i in same:
            style = {"color": EPS_BASES[v.eps_basis].color, "lw": 1.1, "ls": ":",
                     "label": f"Growth share, {label}: same as {basis_labels[same[i]]} "
                              + ("(dotted)" if runs else "(not drawn)")}
        elif multi:
            style = {"color": EPS_BASES[v.eps_basis].color, "lw": 1.3, "ls": "--",
                     "label": f"Growth share, {label} (right axis)"}
        else:
            style = {"color": axis_color, "lw": 1.4, "label": "Growth share = PVGO / price (right axis)"}
        for run in runs or ([[]] if multi else []):  # in a combined chart, keep the legend entry
            ax_pct.plot([r[0] for r in run], [r[3] for r in run], **style)
            style["label"] = None
    for i, (v, label) in enumerate(zip(versions, basis_labels)):  # a marker at each year-end reading
        marks = [(p.day, share) for p, _, share in year_end_rows(v) if share is not None]
        if marks and i not in same:  # an identical version's markers would only hide the earlier one's
            ax_pct.scatter([d for d, _ in marks], [x for _, x in marks], marker="D", s=16, zorder=6,
                           color=EPS_BASES[v.eps_basis].color if multi else axis_color,
                           label=f"Year-end growth share{f', {label}' if multi else ''}"
                                 + (", actual" if smoothing else ""))
    shares = [r[3] for rows in drawn for r in rows]
    shares += [share for v in versions for _, _, share in year_end_rows(v) if share is not None]
    if shares:
        lo, hi = min(shares), max(shares)
        if lo >= 0 and hi <= 100:
            ax_pct.set_ylim(0, 112)  # same 12% headroom as the $ axis, for the release labels
            ax_pct.yaxis.set_major_locator(MultipleLocator(20))
        else:
            ax_pct.set_ylim(min(0, lo) - 5, max(100, hi) * 1.12)
    ax_pct.yaxis.set_major_formatter(PercentFormatter(xmax=100, decimals=0))
    ax_pct.set_ylabel("Growth share (PVGO / price)", color=axis_color)
    ax_pct.tick_params(axis="y", colors=axis_color)

    eps_text = _eps_text(versions)
    if multi:
        line_text = ("Each no-growth line steps at each measurement date. Growth share = 1 - no-growth value / "
                     "close, each trading day (dashed lines).")
    else:
        line_text = ("The no-growth line steps at each measurement date. Growth share = 1 - no-growth value / "
                     "close, each trading day.")
    if smoothing:
        line_text += (f" Lines drawn as a centered {span} ({window}-trading-day) moving average, for display only: "
                      + ("it runs across earnings releases too, averaging out the no-growth steps, so a change shows "
                         "up to six months before and after it happened, and the first and last six months are "
                         "averaged from one side; "
                         if across else
                         "the no-growth average doesn't reach across a measurement date, so its steps stay sharp, "
                         "and ")
                      + "the growth share comes from the smoothed price and no-growth value. Dots and CSVs: actual "
                      "values.")
    footnote = _cost_of_equity_text(h, "weekly between releases") + f"{eps_text} {line_text}"
    footnote += "".join(f" Note: {n}." for n in dict.fromkeys(n for v in versions for n in v.notes))  # each once
    wrapped = textwrap.fill(footnote, 190)
    fig.text(0.01, 0.01, wrapped, ha="left", va="bottom", fontsize=7.5, color="#404040")

    # Legend in its own strip between the date axis and the footnote, so it never covers the lines.
    legend_y = 0.02 + 0.019 * (wrapped.count("\n") + 1)
    handles, legend_labels = ax.get_legend_handles_labels()
    pct_handles, pct_labels = ax_pct.get_legend_handles_labels()
    if multi:  # one column each: price and markers | the no-growth lines | the growth-share lines
        from matplotlib.lines import Line2D

        n = len(versions)
        groups = [
            (handles[:1] + handles[n + 1:], legend_labels[:1] + legend_labels[n + 1:]),
            (handles[1:n + 1], legend_labels[1:n + 1]),
            (pct_handles, pct_labels),
        ]
        rows = max(len(g[0]) for g in groups)
        handles, legend_labels, pct_handles, pct_labels = [], [], [], []
        for group_handles, group_labels in groups:  # pad each column so the versions line up across them
            pad = rows - len(group_handles)
            handles += group_handles + [Line2D([], [], linestyle="none")] * pad
            legend_labels += group_labels + [""] * pad
    rows_needed = -(-(len(handles) + len(pct_handles)) // 3)  # 3 columns
    legend_args = (handles + pct_handles, legend_labels + pct_labels)
    legend_kwargs = {"loc": "lower center", "bbox_to_anchor": (0.5, legend_y), "ncol": 3, "frameon": False}
    legend = fig.legend(*legend_args, fontsize=8, **legend_kwargs)
    fig.subplots_adjust(left=0.07, right=0.93, top=0.94,
                        bottom=legend_y + 0.1 + 0.025 * max(0, rows_needed - 2))

    # A legend wider than the figure (long labels) gets a smaller font until it fits.
    renderer = fig.canvas.get_renderer()
    for size in (7.5, 7, 6.5, 6):
        if legend.get_window_extent(renderer).width <= fig.bbox.width * 0.98:
            break
        legend.remove()
        legend = fig.legend(*legend_args, fontsize=size, **legend_kwargs)

    # Releases closer together than a label is wide (a window of more than about a year): the
    # two-line labels would overlap and hide each other's dates. Each label then becomes its
    # release date alone (and the form, when it isn't an 8-K), written vertically beside its
    # line, with more headroom above the lines for it. The quarter each release reported is in
    # the points table and CSV.
    boxes = [label.get_window_extent(renderer) for label, _ in release_labels]
    if any(a.x1 > b.x0 for a, b in zip(boxes, boxes[1:])):
        for label, rel in release_labels:
            label.set_text(f"{rel.release_date}" + ("" if rel.form == "8-K" else f" {rel.form}"))
            label.set_rotation(90)
            label.set_fontsize(7)
            label.xyann = (2, -4)
        ax.set_ylim(ax.get_ylim()[0], highest * 1.25)
        low, high = ax_pct.get_ylim()  # the growth-share axis gets the same extra room
        ax_pct.set_ylim(low, low + (high - low) * 1.25 / 1.12)
        if (low, high) == (0, 112):  # the 0-100% axis: no tick above 100% in the extra room
            ax_pct.set_yticks(range(0, 101, 20))

    # A release label that would run past the plot's right edge is shifted left just enough to fit.
    right_edge = ax.get_window_extent(renderer).x1
    for label, _ in release_labels:
        overflow = label.get_window_extent(renderer).x1 - right_edge
        if overflow > 0:
            x, y = label.xyann
            label.xyann = (x - (overflow + 3) * 72 / fig.dpi, y)  # pixels -> offset points
    fig.savefig(path, dpi=150)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("tickers", nargs="+", help="Company stock ticker(s), US listings")
    erp_choice = parser.add_mutually_exclusive_group()
    erp_choice.add_argument("--erp", type=float, default=None,
                            help=f"Equity risk premium in percent, e.g. 4.3 (default {EQUITY_RISK_PREMIUM * 100:g})")
    erp_choice.add_argument("--erp-by-year", action="store_true",
                            help="Use Damodaran's implied ERP at each date (damodaran_implied_erp.csv, interpolated "
                                 "between its January rows) instead of one ERP for the whole window")
    beta_choice = parser.add_mutually_exclusive_group()
    beta_choice.add_argument("--market-beta", action="store_true",
                             help="Use beta 1.0 instead of the industry beta")
    beta_choice.add_argument("--own-beta", action="store_true",
                             help=f"Use the company's own beta at each date ({OWN_BETA_MONTHS} monthly returns vs the "
                                  "S&P 500, Blume-adjusted) instead of the industry beta")
    parser.add_argument("--raw-beta", action="store_true",
                        help="With --own-beta, use the regression slope as is, without the Blume adjustment "
                             f"({BLUME_WEIGHT:g} x slope + {1 - BLUME_WEIGHT:.2f})")
    parser.add_argument("--days", type=int, default=DEFAULT_WINDOW_DAYS,
                        help=f"Window length in days (default {DEFAULT_WINDOW_DAYS})")
    parser.add_argument("--eps-basis", nargs="+", choices=list(EPS_BASES), default=[DEFAULT_BASIS],
                        help="EPS behind the no-growth value and growth share: ttm_adjusted (TTM without gains and "
                             "losses on investments), ttm, two_year (trimmed 2-year EPS), "
                             "six_month (last 2 quarters x 2) and/or rd_adjusted; several are charted together "
                             f"(default {DEFAULT_BASIS})")
    parser.add_argument("--release-items", action="store_true",
                        help="Also save each release's press-release EPS reconciliation (the GAAP-to-adjusted table "
                             "that names one-time items) to <TICKER>_pvgo_history_release_items.csv: one SEC request "
                             "per release, cached")
    parser.add_argument("--smooth", choices=list(SMOOTHING), default=None,
                        help="Draw the chart's lines as a moving average of 5 (weekly), 21 (monthly) or 252 "
                             "(yearly, across earnings releases) trading days; the tables and CSVs stay daily")
    args = parser.parse_args()

    try:
        histories = collect_history(args.tickers, market_beta=args.market_beta, erp_pct=args.erp,
                                    window_days=args.days, eps_basis=args.eps_basis, erp_by_year=args.erp_by_year,
                                    own_beta=args.own_beta, blume=not args.raw_beta,
                                    release_items=args.release_items)
    except (ValueError, RuntimeError, requests.RequestException) as exc:
        raise SystemExit(f"PVGO history stopped: {exc}") from exc

    for _, group in groupby(histories, key=lambda h: h.ticker):  # one ticker's versions, one chart
        versions = list(group)
        print("\n\n".join(format_points_table(v) for v in versions))
        try:
            written = write_outputs(versions, args.smooth)
        except OSError as exc:  # Windows refuses to overwrite a file that's open in another program
            print(f"  Couldn't write {exc.filename} -- is it open in Excel or an image viewer? Close it and rerun.")
        else:
            print("  Wrote " + ", ".join(os.path.basename(p) for p in written))
        print()


if __name__ == "__main__":
    main()
