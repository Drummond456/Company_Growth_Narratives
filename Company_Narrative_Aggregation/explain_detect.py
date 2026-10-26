"""Explanation, step 1: its settings and helpers, the state file, its inputs (the runs,
the PVGO series, market prices) and the daily bridge, the periods, months and release
bridge. METHODOLOGY section 7.
"""

from __future__ import annotations

import bisect
import csv
import email.utils
import hashlib
import itertools
import json
import math
import os
import re
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

import narrative_common as N


# --- Config ------------------------------------------------------------------------------

MODEL = "claude-sonnet-5-5"  # not Haiku: in testing it called 22 of 24 quiet days a move
PVGO_DIR = N.HERE.parent / "PVGO_Collection" / "Outputs_CSV_data"
SUBJECTS_JSON = N.HERE / "explain_subjects.json"
PROMPTS_DIR = N.HERE / "prompts"
PROMPTS = {k: PROMPTS_DIR / f"explain_{k}.txt" for k in ("told", "release", "ask")}
# --basis: the EPS behind the no-growth value -> PVGO_Collection's file suffix, and how that EPS is built.
# The adjusted TTM is the default: TTM without the gains and losses on investments, so a
# mark-to-market swing isn't capitalized as permanent earnings; other one-time items still enter at their
# release and leave four quarters later, so each step can be explained. Raw TTM keeps the unsuffixed files.
BASES = {"ttm_adjusted": ("_ttm_adjusted", "Adjusted TTM EPS: the sum of the last 4 quarters without the gains and "
                                            "losses on investments, less 25% tax"),
         "ttm": ("", "TTM EPS: the sum of the last 4 quarters"),
         "two_year": ("_two_year", "2-year EPS: the last 8 quarters without the single highest and lowest, x 4/6"),
         "six_month": ("_six_month", "6-month EPS: the last 2 quarters x 2")}
TTM_BASES = ("ttm", "ttm_adjusted")  # a release's quarter replaces the same quarter a year earlier
# The point columns a release call reads to see how each release's EPS was built
COMPOSITION_KEYS = ("eps_ttm", "eps_ttm_adjusted", "investment_adjustment_per_share", "investment_gains_ttm",
                    "investment_gain_tags", "eps_two_year", "eps_six_month", "eps_period", "two_year_period",
                    "two_year_dropped", "ttm_quarters", "ttm_quarter_leaving")
LEAVING_TABLE_CHARS = 1500  # TTM: the year-ago quarter's reconciliation shown to the release call
STATE_JSON = "explain_state.json"

FIT_DAYS, FIT_MIN_DAYS = 180, 120  # market model: rolling OLS on the prior trading days only
VOL_DAYS, VOL_MIN_DAYS = 60, 40  # the volatility a move is measured against: prior days only
# The periods: each month cut into consecutive periods that cover every trading day, each
# labelled by how much of its price move the market explains, and each explained by a told call.
# COST 2024: 44 periods, 7 market-driven, 27 within noise, 2 divergent, 8 outlier.
SHOCK_Z = 2.5  # a single day this many times its trailing sd is a period of its own (2024-03-08, 2024-07-11)
# The rest of a month is cut into swings of its price-driven path: a period ends at its high (or low) once
# the path has come back this far from it. 0.75pp gave COST 2024 about 3.5 periods a month.
SWING_PP = 0.75
PERIOD_MAX_DAYS = 10  # a swing longer than this is cut, so a slow drift doesn't make one long period
# The labels, in this order: market-driven when the market's part is this share of the period's move or more
# (|market| / (|market| + |company-specific|)); within noise when the company-specific move is under NOISE_Z
# times its normal size (sd x sqrt(days)); outlier when the market's share is at most OUTLIER_SHARE; else
# divergent. The noise floor matters for a low-beta stock: the market rarely explains 70% of COST's moves,
# but most of what's left is ordinary noise (1-10-day windows of pure noise pass 2.0 about 16 times a year).
MARKET_DRIVEN_SHARE = 0.70
NOISE_Z = 1.5
OUTLIER_SHARE = 0.30
LABELS = ["market-driven", "within noise", "divergent", "outlier"]
# A "big market day": the S&P 500's move at least this many times its own trailing-VOL_DAYS sd (14
# days in 2023-2025). The market model is fitted on mostly normal days, so on such a day it can
# leave part of the market's move as company-specific: on 2025-04-09 (S&P +9.5%, 6.8x) WMT rose
# 9.55%, the model credited ~6.9% to the market and the month call then tied the rest to the
# investor day. Flagged to the reader; segmentation, the labels and the bridge don't change.
MARKET_DAY_Z = 2.5
NEWS_DAYS = 1  # a period's news: from this many days before its start to as many after its end
MAX_PERIOD_STATEMENTS = 80
MAX_PERIOD_ARTICLES = 20  # stock/analyst articles (headline and opening) in a period's told call
LEAD_CHARS = 500  # of each stock/analyst article in the told call
MAX_TOKENS = {"told": 1000, "release": 1500, "ask": 3000}
OUTPUT_TOKENS = {"told": 350, "release": 250, "ask": 1500}  # estimates only
SCHEMA_OVERHEAD_TOKENS = 300  # structured outputs add instructions to each request - estimate only
ANALYST_STATUS = "skipped: stock content"  # the screened articles the told call also reads

CONFIDENCE = ["high", "medium", "low", "none"]
# A period's status: answered (its told answer is in), no news collected (no call), or failed
STATUSES = ["answered", "no news collected", "failed"]
# A release's market reaction, by code: a results
# surprise when the company-specific move from the release to the measurement day is at least this many times
# its normal size over that many days (the periods' noise floor), else results expected
RELEASE_SURPRISE_Z = NOISE_Z
# The one-time items the release call extracts: which quarter of the TTM step each is in, and its kind
ITEM_QUARTERS = ["new quarter (entering)", "quarter leaving the TTM"]
ITEM_KINDS = ["benefit or gain", "charge or loss"]
# How an item's amount is stated. One stated in dollars only (Meta) is put per share by code: over its quarter's
# diluted shares (PVGO_Collection), less ITEM_TAX_RATE when pre-tax - PVGO_Collection's flat rate on investment
# gains. It is an estimate, not the company's figure, and is shown as one.
ITEM_UNITS = ["per diluted share", "$ millions"]
ITEM_TAX = ["pre-tax", "after tax or a tax item"]
ITEM_TAX_RATE = 0.25
# The points CSV notes a release call reads. "split" explains why older press-release per-share amounts are
# larger than PVGO_Collection's split-adjusted EPS (e.g. WMT's 3-for-1 on 2024-02-26).
PVGO_NOTE_RE = re.compile(r"one-time|erratic|TTM EPS|sign depends|split", re.I)

# The bridge: total growth-share change = price-driven (market + company-specific) + EPS update + rates/other
BRIDGE = ["total_change_pp", "price_driven_pp", "market_pp", "eps_update_pp", "rate_other_pp"]
# rates/other by the part of the cost of equity that moved: k = Treasury + beta x ERP
RATE_PARTS = ["rate_treasury_pp", "rate_erp_pp", "rate_beta_pp"]
DAILY_COLUMNS = ["date", "close", "growth_share_pct", "ret_pct", "spx_ret_pct", "spx_z", "sector_ret_pct", "beta_spx",
                 "beta_sector", "company_ret_pct", "z", "total_change_pp", "price_driven_pp", "market_pp", "company_pp",
                 "eps_update_pp", "rate_other_pp"] + RATE_PARTS + ["point", "period_id"]
MONTH_SPLIT = ["share_start", "share_end", "total_change_pp", "price_driven_pp", "market_pp", "company_pp",
               "eps_update_pp", "rate_other_pp"] + RATE_PARTS
MONTH_COLUMNS = ["month"] + MONTH_SPLIT + ["n_periods", "n_days"]
PERIOD_COLUMNS = ["period_id", "month", "start", "end", "days", "label", "market_share", "z", "ret_pct", "spx_ret_pct",
                  "sector_ret_pct", "company_ret_pct", "price_driven_pp", "market_pp", "company_pp", "release",
                  "n_statements", "n_articles", "cause", "expected_before_vs_after", "drivers", "evidence",
                  "confidence", "status", "failure"]
RELEASE_COLUMNS = ["release_date", "release_time", "measurement_date", "quarter_end", "eps_before", "eps_after",
                   "eps_update_pp", "share_before_step", "share_after_step", "reaction_company_pct", "reaction_days",
                   "reaction_pp", "reaction_z", "market_reaction", "period_ids", "reconciliation", "item_sentences",
                   "item_dollar_sentences", "one_time_items", "items_effect", "eps_change_ex_items", "items_check", "failure"]
# Results kept by --update (everything else is recomputed by step 1)
PERIOD_RESULTS = ("cause", "expected_before_vs_after", "drivers", "evidence", "confidence", "status", "failure")
RELEASE_RESULTS = ("items", "one_time_items", "items_effect", "eps_change_ex_items", "items_check", "failure")
# An older format of a release's answer, a category and prose instead of extracted items; still read
OLD_RELEASE_KEYS = ("category", "step_cause", "headline", "explanation", "confidence", "one_time_items", "n_statements")
SPLIT_RE = re.compile(r"(\d+)-for-(\d+) split on (\d{4}-\d{2}-\d{2})")  # PVGO_Collection's split note
# Text checks on the answers (check_text): statement numbers left in the prose ("(18)", "(3, 15)") become
# refs; a date outside the run's years +-1 ("2015-08-15" for 2024-08-15) is marked [date?] and listed.
PROSE_REF_RE = re.compile(r"[(\[]\s*(?:statements?\s+)?(\d{1,3}(?:\s*(?:,|;|and|&)\s*\d{1,3})*)\s*[)\]]", re.I)
DATE_RE = re.compile(r"\b(\d{4})-\d{2}-\d{2}\b( \[date\?\])?")


# --- Small helpers -----------------------------------------------------------------------


def read_csv(path: Path) -> list[dict]:
    with open(path, newline="", encoding="utf-8-sig") as f:
        return [{k: v or "" for k, v in row.items()} for row in csv.DictReader(f)]


def write_csv(rows: list[dict], columns: list[str], path: Path) -> None:
    """Narrative's CSV format (utf-8-sig, all quoted), keeping only `columns`."""
    N.write_csv([{k: r.get(k, "") for k in columns} for r in rows], columns, path)


def write_preview(reqs: list[dict], path: Path) -> None:
    with open(path, "w", encoding="utf-8") as f:
        for r in reqs:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def iso_day(text: str) -> str:
    """YYYY-MM-DD from an ISO date or an RSS date ("Thu, 15 May 2025 07:00:00 GMT")."""
    text = (text or "").strip()
    try:
        return date.fromisoformat(text[:10]).isoformat()
    except ValueError:
        pass
    try:
        return email.utils.parsedate_to_datetime(text).date().isoformat()
    except (TypeError, ValueError, IndexError):
        return ""


def days_between(first: str, last: str) -> list[str]:
    d, end, out = date.fromisoformat(first), date.fromisoformat(last), []
    while d <= end:
        out.append(d.isoformat())
        d += timedelta(days=1)
    return out


def month_days(month: str) -> list[str]:
    y, m = map(int, month.split("-"))
    nxt = date(y + (m == 12), m % 12 + 1, 1)
    return days_between(f"{month}-01", (nxt - timedelta(days=1)).isoformat())


def shift(day: str, n: int) -> str:
    return (date.fromisoformat(day) + timedelta(days=n)).isoformat()


def name_of(subject: str) -> str:
    """'Walmart (WMT)' -> 'Walmart'."""
    return re.sub(r"\s*\([^)]*\)\s*", " ", subject).strip()


def ticker_of(subject: str) -> str:
    m = re.search(r"\(([^)]+)\)", subject)
    return m.group(1).strip().upper() if m else ""


def headline(text: str) -> str:
    return next((line[2:].strip() for line in text.splitlines() if line.startswith("# ")), "")


def lead(text: str, n: int = LEAD_CHARS) -> str:
    body = [l for l in text.splitlines() if l.strip() and not l.startswith("# ") and not l.startswith("*")]
    return " ".join(" ".join(body).split())[:n]


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# --- Inputs: the runs ---------------------------------------------------------------------


def find_runs(paths: list[str]) -> list[Path]:
    runs = []
    for raw in paths:
        p = Path(raw)
        if (p / N.OUTPUT_CSV).is_file():
            runs.append(p.resolve())
        elif p.is_dir():
            runs += sorted(q.resolve() for q in p.iterdir() if (q / N.OUTPUT_CSV).is_file())
        else:
            raise SystemExit(f"Not a run folder or a folder of runs: {raw}")
    if not runs:
        raise SystemExit(f"No run with a {N.OUTPUT_CSV} under {', '.join(paths)}")
    return runs


def load_news(runs: list[Path]) -> tuple[str, dict[str, list[dict]], dict[str, list[dict]]]:
    """(subject, {day: statements}, {day: screened stock/analyst articles}). Each
    statement carries its headline (from the fetched article, else the list title) and
    a ref '<period>/<unit_id>'. One run per month: two runs for a month would count its
    news twice."""
    subjects, by_period = set(), {}
    statements, analyst = defaultdict(list), defaultdict(list)
    for run in runs:
        units = read_csv(run / N.OUTPUT_CSV)
        subjects |= {u["subject"] for u in units if u.get("subject")}
        periods = {u.get("period") or iso_day(u["published"])[:7] for u in units} - {""}
        for period in periods:
            if period in by_period:
                raise SystemExit(f"Two runs cover {period}: {by_period[period].name} and {run.name} - pass only one")
            by_period[period] = run
        heads = {}
        for u in units:
            day = iso_day(u["published"])
            if not day:
                continue
            f = u["article_file"]
            if f not in heads:
                path = run / N.INPUT_DIR / f
                heads[f] = (headline(path.read_text(encoding="utf-8")) if path.is_file() else "") or u["article_title"]
            statements[day].append({"text": " ".join(u["text"].split()), "headline": heads[f],
                                    "ref": f"{u.get('period') or day[:7]}/{u['unit_id']}",
                                    "codes": u.get("topic_codes", "")})
        scope = run / N.SCOPE_CSV
        for s in read_csv(scope) if scope.is_file() else []:
            day = iso_day(s["published"])
            if not day or not s["status"].startswith(ANALYST_STATUS):
                continue
            path = run / N.INPUT_DIR / s["article_file"]
            text = path.read_text(encoding="utf-8") if path.is_file() else ""
            analyst[day].append({"headline": headline(text) or s["article_title"], "lead": lead(text),
                                 "ref": f"{s.get('period') or day[:7]}/{s['article_id']}"})
    if len(subjects) != 1:
        raise SystemExit(f"The runs must be about one subject; found: {', '.join(sorted(subjects)) or 'none'}")
    return subjects.pop(), statements, analyst


# --- Inputs: prices -----------------------------------------------------------------------


def load_pvgo(ticker: str, pvgo_dir: Path, basis: str = "ttm") -> tuple[list[dict], list[dict], dict]:
    """(daily rows, release points, press-release reconciliations by release date) for
    one EPS basis. Each daily row: close, no-growth value, and on a release's
    measurement day the no-growth value just before the EPS step. The price-driven part
    doesn't depend on the basis or the ERP/beta choices behind the series; the EPS
    update and its size do."""
    suffix = BASES[basis][0]
    series = pvgo_dir / f"{ticker}_pvgo_history{suffix}_series.csv"
    if not series.is_file():
        raise SystemExit(f"No PVGO series for {ticker} ({basis}): {series} (run PVGO_Collection's history first)")
    num = lambda r, k: float(r[k]) if r.get(k) else None  # noqa: E731
    rows = [{"date": r["date"], "close": float(r["close"]), "ngv": float(r["no_growth_value"]),
             "ngv_before": num(r, "no_growth_value_before_step"), "point": r.get("point", ""),
             # the cost of equity's parts, in percent (k = treasury + beta x erp), for rate_parts()
             "treasury": num(r, "treasury_10y_pct"), "erp": num(r, "erp_pct"), "beta": num(r, "beta")}
            for r in read_csv(series) if r.get("close") and r.get("no_growth_value")]
    points_csv = pvgo_dir / f"{ticker}_pvgo_history{suffix}_points.csv"
    points = sorted(read_csv(points_csv), key=lambda r: r["release_date"]) if points_csv.is_file() else []
    items_csv = pvgo_dir / f"{ticker}_pvgo_history_release_items.csv"
    items = {r["release_date"]: r for r in read_csv(items_csv)} if items_csv.is_file() else {}
    return sorted(rows, key=lambda r: r["date"]), points, items


def fetch_closes(symbol: str, first: str, last: str) -> dict[str, float]:
    """Daily closes from Yahoo Finance (yfinance; split-adjusted, not dividend-adjusted,
    like the PVGO series' close)."""
    import yfinance as yf
    hist = yf.Ticker(symbol).history(start=first, end=shift(last, 1), interval="1d", auto_adjust=False)
    if hist is None or hist.empty:
        raise SystemExit(f"Yahoo Finance returned no prices for {symbol}")
    return {ts.date().isoformat(): float(c) for ts, c in hist["Close"].items() if c == c}


def market_prices(out_dir: Path, sector: str, first: str, last: str) -> dict[str, tuple[float, float]]:
    """{day: (S&P 500, sector ETF)}, cached in market_prices.csv so a --resume or an
    --ask uses the same numbers."""
    path = out_dir / "market_prices.csv"
    if path.is_file():
        return {r["date"]: (float(r["spx"]), float(r["sector"])) for r in read_csv(path)}
    spx, sec = fetch_closes("^GSPC", first, last), fetch_closes(sector, first, last)
    prices = {d: (spx[d], sec[d]) for d in sorted(spx) if d in sec}
    write_csv([{"date": d, "spx": a, "sector": b} for d, (a, b) in prices.items()], ["date", "spx", "sector"], path)
    return prices


# --- Step 1: detect ----------------------------------------------------------------------


def ols2(y: list[float], x1: list[float], x2: list[float]) -> tuple[float, float, float]:
    """(intercept, b1, b2) of y on x1 and x2."""
    n = len(y)
    my, m1, m2 = sum(y) / n, sum(x1) / n, sum(x2) / n
    s11 = sum((a - m1) ** 2 for a in x1)
    s22 = sum((b - m2) ** 2 for b in x2)
    s12 = sum((a - m1) * (b - m2) for a, b in zip(x1, x2))
    s1y = sum((a - m1) * (c - my) for a, c in zip(x1, y))
    s2y = sum((b - m2) * (c - my) for b, c in zip(x2, y))
    det = s11 * s22 - s12 * s12
    if not det:
        return my, 0.0, 0.0
    b1, b2 = (s1y * s22 - s2y * s12) / det, (s11 * s2y - s12 * s1y) / det
    return my - b1 * m1 - b2 * m2, b1, b2


def sd(xs: list[float]) -> float:
    m = sum(xs) / len(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1))


def daily_split(pvgo: list[dict], prices: dict) -> list[dict]:
    """Per trading day, the bridge of the growth share (100 x (1 - V/P), pp):
      total        = share today - share yesterday
      price-driven = 100 x (V0/P0 - V0/P1), V0 = yesterday's no-growth value: the move
                     from the price alone, split into market + company-specific below
      EPS update   = 100 x (V_before - V1)/P1 on a release's measurement day (the new EPS
                     replacing the old), else 0
      rates/other  = the rest: the cost of equity's drift (Treasury, ERP, beta)
    The intercept of the market model is fitted (for unbiased betas) but not removed:
    the stock's own trailing drift is company-specific, not market - removing it moved
    0.5-1.4pp a month into "market" in testing."""
    rows = [r for r in pvgo if r["date"] in prices]
    # The series has the cost of equity's parts on its line points only (the no-growth line is linear
    # between them): each day's rates/other is split by the change between the points around it.
    pts = [i for i, r in enumerate(rows) if all(r.get(k) is not None for k in ("treasury", "erp", "beta"))]
    days = []
    for j, (p, r) in enumerate(zip(rows, rows[1:]), 1):
        a, b = bisect.bisect_right(pts, j - 1) - 1, bisect.bisect_left(pts, j)
        seg = (rows[pts[a]], rows[pts[b]]) if a >= 0 and b < len(pts) else ({}, {})
        ret = 100 * (r["close"] / p["close"] - 1)
        spx = 100 * (prices[r["date"]][0] / prices[p["date"]][0] - 1)
        sec = 100 * (prices[r["date"]][1] / prices[p["date"]][1] - 1)
        share0, share1 = 100 * (1 - p["ngv"] / p["close"]), 100 * (1 - r["ngv"] / r["close"])
        price = 100 * (p["ngv"] / p["close"] - p["ngv"] / r["close"])
        step = (100 * (r["ngv_before"] - r["ngv"]) / r["close"]
                if r.get("point") == "measurement" and r.get("ngv_before") is not None else 0.0)
        rate = share1 - share0 - price - step
        days.append({"date": r["date"], "close": r["close"], "ret_pct": ret, "spx_ret_pct": spx, "sector_ret_pct": sec,
                     "growth_share_pct": share1, "total_change_pp": share1 - share0, "price_driven_pp": price,
                     "eps_update_pp": step, "rate_other_pp": rate, **rate_parts(*seg, rate),
                     "point": r.get("point", ""), "ngv": r["ngv"], "ngv_before": r.get("ngv_before")})
    for i, d in enumerate(days):
        fit = days[max(0, i - FIT_DAYS):i]
        if len(fit) < FIT_MIN_DAYS:
            continue
        _, b1, b2 = ols2([x["ret_pct"] for x in fit], [x["spx_ret_pct"] for x in fit], [x["sector_ret_pct"] for x in fit])
        d.update(beta_spx=b1, beta_sector=b2, company_ret_pct=d["ret_pct"] - b1 * d["spx_ret_pct"] - b2 * d["sector_ret_pct"])
        k = d["price_driven_pp"] / d["ret_pct"] if d["ret_pct"] else 0.0  # pp per % of return, that day
        d["company_pp"] = k * d["company_ret_pct"]
        d["market_pp"] = d["price_driven_pp"] - d["company_pp"]
    for i, d in enumerate(days):
        hist = [x["company_ret_pct"] for x in days[max(0, i - VOL_DAYS):i] if "company_ret_pct" in x]
        if "company_ret_pct" in d and len(hist) >= VOL_MIN_DAYS:
            d["sd"] = sd(hist)
            d["z"] = d["company_ret_pct"] / d["sd"]
        market = [x["spx_ret_pct"] for x in days[max(0, i - VOL_DAYS):i]]
        market_sd = sd(market) if len(market) >= VOL_MIN_DAYS else 0.0
        if market_sd:
            d["spx_z"] = d["spx_ret_pct"] / market_sd  # big market day: |spx_z| >= MARKET_DAY_Z
    return days


def rate_parts(p: dict, r: dict, rate: float) -> dict:
    """A day's rates/other split by what moved the cost of equity, k = Treasury + beta x ERP
    (percent), between the series points p and r around the day. The change in k is
    exactly dTreasury + mean beta x dERP + mean ERP x dbeta, and rates/other (the no-growth
    value moving with 1/k) is shared in that proportion. {} without the parts."""
    if any(x.get(k) is None for x in (p, r) for k in ("treasury", "erp", "beta")):
        return {}
    parts = (r["treasury"] - p["treasury"], (p["beta"] + r["beta"]) / 2 * (r["erp"] - p["erp"]),
             (p["erp"] + r["erp"]) / 2 * (r["beta"] - p["beta"]))
    dk = sum(parts)
    return {k: (rate * x / dk if abs(dk) > 1e-12 else 0.0) for k, x in zip(RATE_PARTS, parts)}


def big_market_day(d: dict) -> bool:
    return abs(d.get("spx_z") or 0.0) >= MARKET_DAY_Z


def market_reaction(r: dict) -> str:
    """'results surprise' or 'results expected', from the release's company-specific reaction z."""
    z = r.get("reaction_z")
    return "results surprise" if z not in ("", None) and abs(float(z)) >= RELEASE_SURPRISE_Z else "results expected"


def market_day_note(d: dict) -> str:
    return f"big market day: S&P {d['spx_ret_pct']:+.1f}%, {abs(d['spx_z']):.1f}x normal"


def _swings(days: list[dict]) -> list[list[dict]]:
    """A stretch of days cut into swings of its price-driven path: a period ends at its high
    (or low) once the path has come back SWING_PP from it, or after PERIOD_MAX_DAYS days."""
    out, cur = [], []
    for d in days:
        if cur:
            path = list(itertools.accumulate((x["price_driven_pp"] for x in cur), initial=0.0))
            hi, lo, nxt = max(path), min(path), path[-1] + d["price_driven_pp"]
            if len(cur) >= PERIOD_MAX_DAYS:
                out.append(cur)
                cur = []
            elif hi > 0 and hi - nxt >= SWING_PP:
                k = path.index(hi)
                out.append(cur[:k])
                cur = cur[k:]
            elif lo < 0 and nxt - lo >= SWING_PP:
                k = path.index(lo)
                out.append(cur[:k])
                cur = cur[k:]
        cur.append(d)
    return [p for p in out + [cur] if p]


def label_of(market_pp: float, company_pp: float, z: float) -> tuple[str, float]:
    """(the period's label, the market's share of its move): market-driven, within noise,
    outlier or divergent, in that order (MARKET_DRIVEN_SHARE, NOISE_Z, OUTLIER_SHARE)."""
    total = abs(market_pp) + abs(company_pp)
    share = abs(market_pp) / total if total else 1.0
    if share >= MARKET_DRIVEN_SHARE:
        return "market-driven", share
    if abs(z) < NOISE_Z:
        return "within noise", share
    return ("outlier" if share <= OUTLIER_SHARE else "divergent"), share


def periods(days: list[dict], first: str, last: str) -> list[dict]:
    """The periods between first and last (days), month by month, covering every bridge day:
    a day with |z| >= SHOCK_Z alone, the rest cut into swings (_swings). Each gets its sums,
    its z (the summed company-specific return / (its last day's sd x sqrt(days))), its label,
    its big market days and its daily returns; its days get its period_id."""
    span = [d for d in days if first <= d["date"] <= last and "company_pp" in d]
    cut = []
    for month in sorted({d["date"][:7] for d in span}):
        chunk = []
        for d in (x for x in span if x["date"][:7] == month):
            if abs(d.get("z") or 0.0) >= SHOCK_Z:
                cut += _swings(chunk) + [[d]]
                chunk = []
            else:
                chunk.append(d)
        cut += _swings(chunk)
    out = []
    for n, w in enumerate(cut, 1):
        sd_last = next((x["sd"] for x in reversed(w) if x.get("sd")), None)
        z = sum(x["company_ret_pct"] for x in w) / (sd_last * math.sqrt(len(w))) if sd_last else 0.0
        p = {"period_id": f"P{n:02d}", "month": w[0]["date"][:7], "start": w[0]["date"], "end": w[-1]["date"],
             "days": len(w), "z": round(z, 2)}
        for k in ("ret_pct", "spx_ret_pct", "sector_ret_pct", "company_ret_pct", "price_driven_pp", "market_pp",
                  "company_pp"):
            p[k] = round(sum(x[k] for x in w), 3)
        p["label"], share = label_of(p["market_pp"], p["company_pp"], z)
        p["market_share"] = round(share, 3)
        p["market_days"] = [{"date": x["date"], "spx_ret_pct": round(x["spx_ret_pct"], 2),
                             "spx_z": round(x["spx_z"], 1)} for x in w if big_market_day(x)]
        p["daily"] = [{"date": x["date"], "ret_pct": round(x["ret_pct"], 2)} for x in w]
        for x in w:
            x["period_id"] = p["period_id"]
        out.append(p)
    return out


def month_split(days: list[dict], month: str) -> dict:
    """The month's bridge: total = market + company-specific (= price-driven) + EPS update
    + rates/other, with the growth share at the start and end."""
    m = [d for d in days if d["date"][:7] == month and "company_pp" in d]
    out = {"month": month, "n_periods": len({d["period_id"] for d in m if d.get("period_id")}), "n_days": len(m)}
    if not m:
        return out
    out.update({k: round(sum(d[k] for d in m), 3) for k in BRIDGE + ["company_pp"]})
    if all(k in d for d in m for k in RATE_PARTS):
        out.update({k: round(sum(d[k] for d in m), 3) for k in RATE_PARTS})
    out.update(share_start=round(m[0]["growth_share_pct"] - m[0]["total_change_pp"], 2),
               share_end=round(m[-1]["growth_share_pct"], 2))
    return out


def basis_eps(point: dict, basis: str) -> str:
    """The EPS a release point used on this basis (eps_charted; eps_used where it fell back)."""
    return point.get("eps_charted") or point.get("eps_used") or point.get(f"eps_{basis}", "")


def build_releases(points: list[dict], items: dict, days: list[dict], periods: list[dict], first_day: str,
                   last_day: str, basis: str) -> list[dict]:
    """One entry per release whose measurement day falls in the run: the EPS update on
    that day, the company-specific price reaction from the release date to the
    measurement date (the step can land a day after the reaction: PVGO_Collection
    measures from the 8-K's acceptance time), the periods that overlap it (each gets the
    release's date as its `release`), and the facts the release call reads."""
    by_day = {d["date"]: d for d in days}
    # Splits, from PVGO_Collection's notes: its EPS is on today's share basis, but a press release from
    # before a split quotes the old one (the 2024-05-16 call set post-split $0.60 against pre-split $1.47).
    splits = sorted({(m.group(3), int(m.group(1)) / int(m.group(2)))
                     for p in points for m in SPLIT_RE.finditer(p.get("notes", ""))})
    out, prev = [], None
    for i, p in enumerate(points):
        meas = p.get("measurement_date") or p["release_date"]
        d = by_day.get(meas)
        # On TTM, this release's quarter replaces the same quarter a year earlier (four releases back):
        # its press release (reconciliation table or text) names any one-time item now leaving the EPS.
        gone = points[i - 4] if basis in TTM_BASES and i >= 4 else None
        gone_item = items.get(gone["release_date"], {}) if gone else {}
        leaving = ({"quarter_end": gone["quarter_end"], "release_date": gone["release_date"],
                    "reconciliation": quarter_table(gone_item.get("reconciliation_text", "")),
                    "item_sentences": gone_item.get("item_sentences", ""),
                    "item_dollar_sentences": gone_item.get("item_dollar_sentences", ""),
                    "diluted_shares": gone_item.get("diluted_shares", "")}
                   if gone else {})
        if first_day <= meas <= last_day and d and "company_pp" in d:
            # The release date through the measurement date: two trading days when the 8-K came
            # after the close (Walmart's, accepted after the open, did until PVGO_Collection moved its
            # cutoff to the close on 2026-10-19), while the earnings-day event is the release
            # day alone - so the reaction is given by day too, and its z is the window's, the way
            # detect() scores a multi-day event (sum / (sd x sqrt n)), not its largest day's.
            window = [x for x in days if p["release_date"] <= x["date"] <= meas and "company_ret_pct" in x]
            scored = [x for x in window if x.get("sd")]
            window_z = (sum(x["company_ret_pct"] for x in window) / (scored[-1]["sd"] * math.sqrt(len(window)))
                        if scored else None)
            item = items.get(p["release_date"], {})
            overlapping = [x for x in periods if x["start"] <= meas and x["end"] >= p["release_date"]]
            for x in overlapping:
                x["release"] = p["release_date"]
            out.append({
                "release_date": p["release_date"], "release_time": p.get("release_time", ""),
                "release_form": p.get("release_form", ""), "measurement_date": meas, "quarter_end": p["quarter_end"],
                "eps_before": basis_eps(prev, basis) if prev else "", "eps_after": basis_eps(p, basis),
                "eps_update_pp": round(d["eps_update_pp"], 3),
                "share_before_step": round(100 * (1 - d["ngv_before"] / d["close"]), 2) if d.get("ngv_before") else "",
                "share_after_step": round(d["growth_share_pct"], 2),
                "ngv_before": d.get("ngv_before"), "ngv_after": d["ngv"], "cost_of_equity_pct": p.get("cost_of_equity_pct", ""),
                "reaction_ret_pct": round(sum(x["ret_pct"] for x in window), 2),
                "reaction_spx_pct": round(sum(x["spx_ret_pct"] for x in window), 2),
                "reaction_sector_pct": round(sum(x["sector_ret_pct"] for x in window), 2),
                "reaction_company_pct": round(sum(x["company_ret_pct"] for x in window), 2),
                "reaction_pp": round(sum(x["company_pp"] for x in window), 3),
                "reaction_z": round(window_z, 2) if window_z is not None else "",
                "reaction_days": len(window),
                "reaction_by_day": [{"date": x["date"], "company_ret_pct": round(x["company_ret_pct"], 2),
                                     "z": round(x["z"], 2) if x.get("z") is not None else ""} for x in window],
                "period_ids": "; ".join(x["period_id"] for x in overlapping),
                "eps_composition": {k: p.get(k, "") for k in COMPOSITION_KEYS},
                "prev_composition": {k: prev.get(k, "") for k in COMPOSITION_KEYS}
                if prev else {},
                "pvgo_flags": [n.strip() for n in p.get("notes", "").split("|") if PVGO_NOTE_RE.search(n)],
                "reconciliation": item.get("reconciliation_text", ""),
                "item_sentences": item.get("item_sentences", ""),
                "item_dollar_sentences": item.get("item_dollar_sentences", ""),
                "diluted_shares": item.get("diluted_shares", ""),
                "reconciliation_note": item.get("note", "") if item else "no press-release data from PVGO_Collection "
                                                                          "(run its history with release items)",
                "leaving": leaving,
                "splits": [{"date": s, "ratio": x} for s, x in splits
                           if min(p["release_date"], leaving.get("release_date") or p["release_date"]) < s],
            })
        prev = p
    return out


def quarter_table(text: str, cap: int = LEAVING_TABLE_CHARS) -> str:
    """The quarter's own EPS reconciliation from a release's press-release text: the first
    table that reconciles reported EPS (some releases lead with a guidance table)."""
    blocks = [b for b in text.split("\n\n") if b.strip()]
    pick = next((b for b in blocks if re.search(r"reported eps|diluted earnings per share", b, re.I)),
                blocks[0] if blocks else "")
    return pick[:cap]


# --- Outputs -------------------------------------------------------------------------------


def save(state: dict, out_dir: Path) -> None:
    (out_dir / STATE_JSON).write_text(json.dumps(state, indent=1, ensure_ascii=False), encoding="utf-8")


BLIND_KEYS = ("n_blind_statements", "n_blind_names_only", "blind_skipped", "blind_effect", "blind_reason", "verdict")


def migrate(state: dict) -> dict:
    """A state the current code can render and update. A run from before the periods
    (2026-10-22) has events and month explanations instead: it stops here, and its files
    stay as they were written. A run with a blind read (2026-10-22) keeps its told answers:
    its verdict becomes the status, and the blind read's fields are dropped. A release
    answered before the item extraction (2026-10-23) loses its category and prose, and
    counts as unanswered, so --update sends its call again."""
    if "periods" not in state:
        raise SystemExit("This run was made before the periods (2026-10-22): its events and month explanations "
                         "can't be re-rendered or updated by the current code, and its files stay as they are. "
                         "Make a new run instead.")
    for p in state["periods"]:
        if "verdict" in p:
            if p["verdict"] == "no news collected":
                p["status"] = p["verdict"]
            elif p.get("confidence"):  # the told answer is in, whatever the blind read did
                p["status"], p["failure"] = "answered", ""
            elif p["verdict"]:
                p["status"] = "failed"
        for k in BLIND_KEYS:
            p.pop(k, None)
    for r in state.setdefault("releases", []):
        if "items" not in r:
            for k in OLD_RELEASE_KEYS:
                r.pop(k, None)
    return state


def to_state_path(path: str | Path) -> str:
    """A path as the state stores it: relative to this folder, so a run moves with the
    repo (absolute only on another drive, where no relative path exists)."""
    try:
        return Path(os.path.relpath(Path(path).resolve(), N.HERE)).as_posix()
    except ValueError:
        return str(Path(path).resolve())


def from_state_path(stored: str) -> Path:
    """A stored path back on this machine; an absolute one is kept as it is."""
    return (N.HERE / stored).resolve()


# --- Main ------------------------------------------------------------------------------------


def new_out_dir(parent: Path) -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M")
    out, n = parent / f"explain_{stamp}", 2
    while out.exists():
        out, n = parent / f"explain_{stamp}-{n}", n + 1
    return out
