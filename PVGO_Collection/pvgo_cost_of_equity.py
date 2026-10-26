"""PVGO cost of equity: beta and ERP - Damodaran's files, industry resolution, the
industry beta, the company's own beta and the year-by-year ERP.
METHODOLOGY sections 3 and 7.
"""

from __future__ import annotations

import bisect
import csv
import io
import math
import os
import re
import statistics
import time
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from typing import Callable, Optional

import requests

from pvgo_inputs import (
    BETA_CACHE_PATH,
    BLUME_WEIGHT,
    CACHE_DIR,
    COMPANY_CACHE_PATH,
    DAMODARAN_BETAS_URL,
    DAMODARAN_CACHE_MAX_AGE_DAYS,
    DAMODARAN_COMPANIES_URL,
    DAMODARAN_RETRY_AFTER_DAYS,
    ERP_BY_YEAR_PATH,
    MARKET_BETA,
    NAME_FILLER,
    OVERRIDES_PATH,
    OWN_BETA_MIN_MONTHS,
    OWN_BETA_MONTHS,
    SecProfile,
    SIC_MAP_PATH,
    US_EXCHANGES,
)


@dataclass
class DamodaranCompany:
    exchange: str
    ticker: str
    name: str  # without the "(Exchange:Ticker)" suffix Damodaran appends
    industry: str


@dataclass
class CompanyIndex:
    by_ticker: dict[str, DamodaranCompany]
    by_name: dict[str, list[DamodaranCompany]]
    notes: list[str] = field(default_factory=list)  # run-level notes (e.g. stale cache)


@dataclass
class IndustryBetas:
    betas: dict[str, float]  # Damodaran industry name -> average levered beta (raw)
    market: Optional[float]  # the file's "Total Market" beta, used for scaling
    label: str  # e.g. "Damodaran US industry beta (Jan 2026)"
    notes: list[str] = field(default_factory=list)  # run-level notes (e.g. stale cache)


@dataclass
class IndustryChoice:
    industry: str  # Damodaran industry name ("" if none)
    source: str  # "damodaran_company", "sic_mapping", "override", or "" if none
    notes: list[str] = field(default_factory=list)


@dataclass
class BetaChoice:
    beta: float  # used in the cost of equity (scaled industry beta, or 1.0)
    raw: Optional[float]  # Damodaran's industry beta as published, when one was used
    source: str  # becomes beta_source
    notes: list[str] = field(default_factory=list)


# --------------------------------------------------------------------------
# Damodaran files: download + local cache
# --------------------------------------------------------------------------
def _cached_download(
    url: str, cache_path: str, to_cache_bytes: Callable[[bytes], bytes], session: requests.Session,
) -> tuple[Optional[str], list[str], str]:
    """Keep `cache_path` fresh: re-download `url` when the cache is missing or
    older than DAMODARAN_CACHE_MAX_AGE_DAYS. `to_cache_bytes` turns the
    download into what's cached and raises if it doesn't look right, so a bad
    download never replaces a good cache. After a failed refresh, the cached
    copy is used without retrying for DAMODARAN_RETRY_AFTER_DAYS (the
    attempt is recorded in a ".failed" file next to it). Returns (path or
    None, notes, reason when None)."""
    os.makedirs(CACHE_DIR, exist_ok=True)
    cached = os.path.exists(cache_path)
    stale = not cached or (time.time() - os.path.getmtime(cache_path)) / 86400 > DAMODARAN_CACHE_MAX_AGE_DAYS
    notes: list[str] = []
    if stale:
        name = url.rsplit("/", 1)[-1]
        failed_marker = cache_path + ".failed"
        if cached and os.path.exists(failed_marker) and \
                (time.time() - os.path.getmtime(failed_marker)) / 86400 < DAMODARAN_RETRY_AFTER_DAYS:
            cache_date = datetime.fromtimestamp(os.path.getmtime(cache_path)).date()
            notes.append(f"Damodaran's {name} couldn't be refreshed in the last day; used the cached copy from "
                         f"{cache_date} (the next attempt is a day after the last one)")
            return cache_path, notes, ""
        try:
            r = session.get(url, timeout=120)
            r.raise_for_status()
            data = to_cache_bytes(r.content)
            tmp = cache_path + ".tmp"
            with open(tmp, "wb") as f:
                f.write(data)
            os.replace(tmp, cache_path)
            if os.path.exists(failed_marker):
                os.remove(failed_marker)
        except Exception as exc:
            if not cached:
                return None, [], f"couldn't download Damodaran's {name} ({exc}) and there's no cached copy"
            with open(failed_marker, "w") as f:  # its modified time is the attempt's time
                f.write(f"{exc}\n")
            cache_date = datetime.fromtimestamp(os.path.getmtime(cache_path)).date()
            notes.append(f"couldn't refresh Damodaran's {name} ({exc}); used the cached copy from {cache_date}")
    return cache_path, notes, ""


def parse_damodaran_betas(content: bytes) -> tuple[dict[str, float], Optional[date]]:
    """Industry name -> average levered beta, plus the file's "Date updated".

    The header row is located by its "Industry Name" cell and the beta column
    by its "Beta" header (it has a trailing space in the file), rather than by
    fixed offsets, since the layout can shift between yearly updates."""
    import xlrd

    wb = xlrd.open_workbook(file_contents=content)
    sheets = sorted(wb.sheets(), key=lambda s: s.name != "Industry Averages")  # usual sheet first
    for sh in sheets:
        for r in range(min(sh.nrows, 60)):
            header = [str(v).strip().lower() for v in sh.row_values(r)]
            if not header or header[0] != "industry name" or "beta" not in header:
                continue
            beta_col = header.index("beta")
            betas: dict[str, float] = {}
            for rr in range(r + 1, sh.nrows):
                name = str(sh.cell_value(rr, 0)).strip()
                if not name:
                    break
                try:
                    betas[name] = float(sh.cell_value(rr, beta_col))
                except (TypeError, ValueError):
                    continue
            updated = None
            for rr in range(r):
                row = sh.row_values(rr)
                if str(row[0]).strip().lower().startswith("date updated") and isinstance(row[1], float):
                    updated = xlrd.xldate_as_datetime(row[1], wb.datemode).date()
            if betas:
                return betas, updated
    raise ValueError("couldn't find the 'Industry Name' / 'Beta' header row in Damodaran's beta file")


def load_industry_betas(session: requests.Session) -> tuple[Optional[IndustryBetas], str]:
    """Damodaran's US industry betas (cached). Returns (betas, "") or, when
    neither a download nor a cache is usable, (None, reason)."""
    def validate(content: bytes) -> bytes:
        parse_damodaran_betas(content)
        return content

    path, notes, reason = _cached_download(DAMODARAN_BETAS_URL, BETA_CACHE_PATH, validate, session)
    if path is None:
        return None, reason
    try:
        with open(path, "rb") as f:
            betas, updated = parse_damodaran_betas(f.read())
    except Exception as exc:
        return None, f"couldn't read the cached Damodaran beta file ({exc})"
    label = "Damodaran US industry beta" + (f" ({updated:%b %Y})" if updated else "")
    return IndustryBetas(betas, betas.get("Total Market"), label, notes), ""


def parse_damodaran_companies(content: bytes) -> list[DamodaranCompany]:
    """Companies listed on US exchanges from Damodaran's indname.xls. Columns
    are found by their header names (Company Name, Exchange:Ticker, Industry
    Group), not by position."""
    import xlrd

    wanted = {"company name", "exchange:ticker", "industry group"}
    wb = xlrd.open_workbook(file_contents=content)
    for sh in wb.sheets():
        for r in range(min(sh.nrows, 20)):
            header = [str(v).strip().lower() for v in sh.row_values(r)]
            if not wanted <= set(header):
                continue
            col = {h: i for i, h in enumerate(header)}
            out = []
            for rr in range(r + 1, sh.nrows):
                row = sh.row_values(rr)
                exchange, _, ticker = str(row[col["exchange:ticker"]]).strip().partition(":")
                industry = str(row[col["industry group"]]).strip()
                if exchange not in US_EXCHANGES or not ticker or not industry:
                    continue
                name = re.sub(r"\s*\([^()]*:[^()]*\)\s*$", "", str(row[col["company name"]])).strip()
                out.append(DamodaranCompany(exchange, ticker.strip(), name, industry))
            if len(out) < 1000:  # the real file has ~7,000 US-exchange rows
                raise ValueError(f"only {len(out)} US-exchange companies found in Damodaran's company list")
            return out
    raise ValueError("couldn't find the 'Company Name' / 'Exchange:Ticker' / 'Industry Group' header")


def _companies_to_csv(content: bytes) -> bytes:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=list(DamodaranCompany.__dataclass_fields__))
    w.writeheader()
    for c in parse_damodaran_companies(content):
        w.writerow(asdict(c))
    return buf.getvalue().encode("utf-8")


def _norm_ticker(ticker: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", ticker.upper())  # BRK.B, BRK-B, BRKB all compare equal


def _name_tokens(name: str) -> list[str]:
    tokens = re.sub(r"[^a-z0-9]+", " ", name.lower().replace("&", " and ")).split()
    while tokens and tokens[0] == "the":
        tokens.pop(0)
    while tokens and tokens[-1] in NAME_FILLER:
        tokens.pop()
    return tokens


def _norm_name(name: str) -> str:
    return " ".join(_name_tokens(name))


def _names_overlap(a: str, b: str) -> bool:
    """True when two company names share a meaningful word."""
    sig = lambda n: {t for t in _name_tokens(n) if len(t) >= 3 and t not in NAME_FILLER}
    return bool(sig(a) & sig(b))


def load_company_index(session: requests.Session) -> tuple[Optional[CompanyIndex], str]:
    """Damodaran's US-exchange companies (cached as a small CSV). Returns
    (index, "") or (None, reason)."""
    path, notes, reason = _cached_download(DAMODARAN_COMPANIES_URL, COMPANY_CACHE_PATH, _companies_to_csv, session)
    if path is None:
        return None, reason
    by_ticker: dict[str, DamodaranCompany] = {}
    by_name: dict[str, list[DamodaranCompany]] = {}
    try:
        with open(path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                # Filtered again here, so a change to US_EXCHANGES applies before the next refresh;
                # named columns, so a cache written with extra columns still loads.
                if row["exchange"] not in US_EXCHANGES:
                    continue
                c = DamodaranCompany(row["exchange"], row["ticker"], row["name"], row["industry"])
                by_ticker.setdefault(_norm_ticker(c.ticker), c)
                by_name.setdefault(_norm_name(c.name), []).append(c)
    except Exception as exc:
        return None, f"couldn't read the cached Damodaran company list ({exc})"
    return CompanyIndex(by_ticker, by_name, notes), ""


def find_company(index: CompanyIndex, ticker: str, sec_name: str) -> tuple[Optional[DamodaranCompany], str, list[str]]:
    """(company, "ticker" or "name", notes). A ticker match only counts when
    the company names share a word, which guards against a ticker reused by a
    different company since Damodaran's snapshot."""
    notes = []
    c = index.by_ticker.get(_norm_ticker(ticker))
    if c is not None and not _names_overlap(c.name, sec_name):
        notes.append(f"ticker {ticker.upper()} is '{c.name}' in Damodaran's list, which doesn't look like "
                     f"'{sec_name}'; ignored that match")
        c = None
    if c is not None:
        return c, "ticker", notes
    candidates = index.by_name.get(_norm_name(sec_name), [])
    if len(candidates) == 1:
        return candidates[0], "name", notes
    if len(candidates) > 1:
        notes.append(f"{len(candidates)} companies in Damodaran's list share the name '{sec_name}'; not matched")
    return None, "", notes


# --------------------------------------------------------------------------
# Industry + beta
# --------------------------------------------------------------------------
def load_sic_map(path: str = SIC_MAP_PATH) -> dict[int, tuple[str, str, str]]:
    """SIC code -> (SIC description, Damodaran industry, review note) from the
    hand-editable CSV. A blank industry means "not mapped"."""
    if not os.path.exists(path):
        return {}
    out = {}
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            sic = (row.get("sic") or "").strip()
            if sic.isdigit():
                out[int(sic)] = (
                    (row.get("sic_description") or "").strip(),
                    (row.get("damodaran_industry") or "").strip(),
                    (row.get("review_note") or "").strip(),
                )
    return out


def load_overrides(path: str = OVERRIDES_PATH) -> dict[str, tuple[str, str]]:
    """Normalized ticker -> (Damodaran industry, note) from the per-company
    override CSV (columns: ticker, damodaran_industry, note)."""
    if not os.path.exists(path):
        return {}
    out = {}
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            ticker = (row.get("ticker") or "").strip()
            industry = (row.get("damodaran_industry") or "").strip()
            if ticker and industry and not ticker.startswith("#"):
                out[_norm_ticker(ticker)] = (industry, (row.get("note") or "").strip())
    return out


def resolve_industry(
    ticker: str, company: str, profile: Optional[SecProfile],
    companies: Optional[CompanyIndex], companies_reason: str,
    sic_map: dict[int, tuple[str, str, str]], overrides: dict[str, tuple[str, str]],
) -> IndustryChoice:
    """Damodaran industry from his company list, else the SIC mapping, then
    the per-company override CSV (applied last)."""
    notes: list[str] = []
    industry, source = "", ""

    if companies is not None:
        match, how, match_notes = find_company(companies, ticker, company)
        notes += companies.notes + match_notes
        if match is not None:
            industry, source = match.industry, "damodaran_company"
            if how == "name":
                notes.append(f"matched Damodaran's company list by name: {match.name} ({match.exchange}:{match.ticker})")
    elif companies_reason:
        notes.append(f"{companies_reason}; used the SIC mapping")

    if not industry:
        sic = profile.sic if profile else None
        if sic is None:
            notes.append("no SIC code from SEC, so no SIC mapping")
        else:
            _, mapped, review = sic_map.get(sic, ("", "", ""))
            if mapped:
                industry, source = mapped, "sic_mapping"
                if review:
                    notes.append(f"SIC {sic} -> {mapped} is flagged for review in sic_to_damodaran_industry.csv")
            else:
                notes.append(f"SIC {sic} ({profile.sic_description or 'no description'}) isn't mapped to a "
                             "Damodaran industry in sic_to_damodaran_industry.csv -- add it to the CSV")

    override = overrides.get(_norm_ticker(ticker))
    if override:
        new, why = override
        was = f" (was {industry}, from {source})" if industry and industry != new else ""
        notes.append(f"industry overridden to {new}{was}" + (f": {why}" if why else ""))
        industry, source = new, "override"
    return IndustryChoice(industry, source, notes)


def _lookup_beta(industry: str, betas: dict[str, float]) -> Optional[float]:
    if industry in betas:
        return betas[industry]
    folded = {" ".join(k.lower().split()): v for k, v in betas.items()}
    return folded.get(" ".join(industry.lower().split()))


def choose_beta(
    choice: IndustryChoice, industry_betas: Optional[IndustryBetas], unavailable_reason: str, market_beta: bool,
) -> BetaChoice:
    """Scaled industry beta (raw / Total Market), or beta 1.0 with a note saying why not."""
    if market_beta:
        return BetaChoice(MARKET_BETA, None, "market beta 1.0 (--market-beta)")
    if not choice.industry:
        return BetaChoice(MARKET_BETA, None, "default 1.0 (no industry)",
                          ["no Damodaran industry for this company; used beta 1.0"])
    if industry_betas is None:
        return BetaChoice(MARKET_BETA, None, "default 1.0 (beta file unavailable)",
                          [f"{unavailable_reason}; used beta 1.0"])
    raw = _lookup_beta(choice.industry, industry_betas.betas)
    if raw is None:
        return BetaChoice(MARKET_BETA, None, "default 1.0 (industry not in beta file)", [
            f"industry '{choice.industry}' ({choice.source}) isn't in Damodaran's beta file; used beta 1.0"]
            + industry_betas.notes)
    notes = list(industry_betas.notes)
    if industry_betas.market:
        return BetaChoice(raw / industry_betas.market, raw,
                          f"{industry_betas.label}, scaled by Total Market {industry_betas.market:.3f}", notes)
    notes.append("Damodaran's beta file has no Total Market row; industry beta used unscaled")
    return BetaChoice(raw, raw, f"{industry_betas.label}, unscaled", notes)


# --------------------------------------------------------------------------
# Own beta (--own-beta)
# --------------------------------------------------------------------------
def _months_before(d: date, months: int) -> date:
    """The first day of the month `months` calendar months before d's."""
    index = d.year * 12 + d.month - 1 - months
    return date(index // 12, index % 12 + 1, 1)


def own_beta_schedule(
    stock: list[tuple[date, float]], benchmark: list[tuple[date, float]], today: date, blume: bool = True,
) -> list[tuple[date, float, float, int]]:
    """The company's own beta at the end of each completed month, oldest
    first: (the month's last trading day, beta used, regression beta,
    monthly returns used).

    The regression beta is the slope of the stock's monthly total returns
    (dividend-adjusted closes) on the S&P 500's monthly returns, over the
    OWN_BETA_MONTHS months ending that month, using only prices known then.
    Months are calendar months, measured between each month's last trading
    day common to both series; the current month counts once it's over. A
    month needs OWN_BETA_MIN_MONTHS returns. The beta used is
    BLUME_WEIGHT x regression + (1 - BLUME_WEIGHT) x 1.0, which pulls it
    toward the market's 1.0 as commercial services' "adjusted beta" does;
    with `blume` off (--raw-beta), the regression beta itself."""
    bench_on = dict(benchmark)
    month_last: dict[tuple[int, int], tuple[date, float, float]] = {}
    for d, close in stock:
        if d in bench_on:
            month_last[(d.year, d.month)] = (d, close, bench_on[d])
    month_last.pop((today.year, today.month), None)  # still in progress
    months = sorted(month_last.items())
    returns = []  # (month end, stock return, market return), consecutive months only
    for ((y0, m0), (_, s0, b0)), ((y1, m1), (d1, s1, b1)) in zip(months, months[1:]):
        if (y1 * 12 + m1) - (y0 * 12 + m0) == 1 and s0 > 0 and b0 > 0:
            returns.append((d1, s1 / s0 - 1, b1 / b0 - 1))
    schedule = []
    for i, (month_end, _, _) in enumerate(returns):
        start = _months_before(month_end, OWN_BETA_MONTHS - 1)
        window = [r for r in returns[max(0, i + 1 - OWN_BETA_MONTHS):i + 1] if r[0] >= start]
        if len(window) < OWN_BETA_MIN_MONTHS:
            continue
        xs, ys = [m for _, _, m in window], [s for _, s, _ in window]
        mx, my = statistics.fmean(xs), statistics.fmean(ys)
        variance = sum((x - mx) ** 2 for x in xs)
        if variance == 0:
            continue
        raw = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / variance
        schedule.append((month_end, BLUME_WEIGHT * raw + (1 - BLUME_WEIGHT) if blume else raw, raw, len(window)))
    return schedule


def own_beta_on(schedule: list[tuple[date, float, float, int]], d: date) -> Optional[tuple[date, float, float, int]]:
    """The latest own_beta_schedule() row on or before d, or None before the first."""
    i = bisect.bisect_right(schedule, (d, math.inf))
    return schedule[i - 1] if i else None


def own_beta_source(row: tuple[date, float, float, int], blume: bool = True) -> str:
    month_end, _, raw, months = row
    return (f"own beta: {months} monthly returns vs the S&P 500 to {month_end}, regression {raw:.2f}, "
            + ("Blume-adjusted" if blume else "unadjusted"))


def load_erp_by_year(path: str = ERP_BY_YEAR_PATH) -> list[tuple[date, float]]:
    """(date, ERP as a fraction) from the hand-maintained CSV of Damodaran's
    implied ERP (columns as_of, erp_pct), oldest first. Rows whose as_of
    starts with # are notes."""
    name = os.path.basename(path)
    if not os.path.exists(path):
        raise ValueError(f"--erp-by-year needs {name} in PVGO_Collection/ (see METHODOLOGY.md)")
    rows = []
    with open(path, newline="", encoding="utf-8") as f:
        for line, row in enumerate(csv.DictReader(f), start=2):
            as_of = (row.get("as_of") or "").strip()
            if not as_of or as_of.startswith("#"):
                continue
            try:
                d, pct = date.fromisoformat(as_of), float((row.get("erp_pct") or "").strip())
            except ValueError:
                raise ValueError(f"{name} line {line}: expected a date (YYYY-MM-DD) and an ERP in percent, got "
                                 f"{as_of!r} and {row.get('erp_pct')!r}") from None
            if not 0 < pct < 20:
                raise ValueError(f"{name} line {line}: an ERP of {pct}% is outside 0-20%")
            rows.append((d, pct / 100))
    if not rows:
        raise ValueError(f"{name} has no ERP rows")
    rows.sort()
    repeated = sorted({a for (a, _), (b, _) in zip(rows, rows[1:]) if a == b})
    if repeated:
        raise ValueError(f"{name} has more than one row for {', '.join(map(str, repeated))}")
    return rows


def erp_on(schedule: list[tuple[date, float]], d: date) -> float:
    """The ERP on d from load_erp_by_year()'s rows: linear between the rows
    around d; before the first row or after the last, that row's value."""
    i = bisect.bisect_right(schedule, (d, math.inf))
    if i == 0:
        return schedule[0][1]
    if i == len(schedule):
        return schedule[-1][1]
    (d0, e0), (d1, e1) = schedule[i - 1], schedule[i]
    return e0 + (e1 - e0) * (d - d0).days / (d1 - d0).days
