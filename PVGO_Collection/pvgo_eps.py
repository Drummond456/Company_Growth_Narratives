"""PVGO earnings: every EPS basis - XBRL quarters to TTM, 2-year and 6-month EPS, the
adjusted TTM (the default), R&D-adjusted EPS and the earnings-quality notes.
METHODOLOGY sections 2, 5 and 6.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Optional

from pvgo_inputs import (
    DILUTED_SHARE_TAGS,
    ERRATIC_MIN_FLAGS,
    FINANCIAL_SIC,
    INVESTMENT_GAIN_FALLBACK_TAGS,
    INVESTMENT_GAIN_TAGS,
    INVESTMENT_GAIN_TAX_RATE,
    ONE_TIME_DEVIATION,
    RD_AMORTIZATION_YEARS,
    RD_MIN_PRIOR_YEARS,
    RD_TAGS,
    RD_TAX_RATE,
    SecProfile,
    STALE_EPS_DAYS,
)


@dataclass
class Quarter:
    start: date
    end: date
    eps: float  # the quarter's value: diluted EPS, or R&D dollars in the R&D series
    source: str  # "10-Q", "10-K", or "derived: FY - Q1-Q3"
    filed: Optional[date] = None  # filing date of the fact (derived Q4: the earliest of the 10-K's and Q1-Q3's)

    @property
    def derived(self) -> bool:
        return self.source.startswith("derived")


@dataclass
class TtmEps:
    value: float
    quarters: list[Quarter]
    concept: str  # XBRL tag used
    notes: list[str] = field(default_factory=list)
    prior_quarters: list[Quarter] = field(default_factory=list)  # the four quarters before `quarters`
    prior_value: Optional[float] = None
    prior_reason: str = ""  # why there's no prior TTM, when there isn't one


@dataclass
class RdAdjustment:
    per_share: Optional[float]  # added to the EPS used; 0.0 when no R&D is reported, None when not computable
    rd_current: Optional[float] = None  # current-year R&D expense (USD)
    amortization: Optional[float] = None  # prior years' R&D / life (USD)
    shares: Optional[float] = None  # weighted-average diluted shares used
    life: Optional[int] = RD_AMORTIZATION_YEARS  # amortization life in years
    effective_life: Optional[int] = None  # prior years actually averaged (< life when gaps were filled)
    basis: str = ""  # the window rd_current covers, e.g. "TTM ending 2026-06-30"
    notes: list[str] = field(default_factory=list)


@dataclass
class InvestmentAdjustment:
    per_share: Optional[float]  # added to TTM EPS: -gains x (1 - tax) / shares; 0.0 when none or exempt, None if n/a
    gains_ttm: Optional[float] = None  # pre-tax gains (+) / losses (-) on investments in the TTM quarters (USD)
    tax_rate: float = INVESTMENT_GAIN_TAX_RATE
    shares: Optional[float] = None  # weighted-average diluted shares used
    tags: str = ""  # the XBRL tag(s) the TTM quarters came from
    basis: str = ""  # e.g. "TTM ending 2024-07-31", "no investment gains in SEC's data", "exempt: financial company"
    notes: list[str] = field(default_factory=list)


# --------------------------------------------------------------------------
# Trailing 12-month diluted EPS from XBRL facts
# --------------------------------------------------------------------------
def _eps_rows(facts: dict) -> tuple[str, list[dict]]:
    gaap = facts.get("facts", {}).get("us-gaap", {})
    for concept in ("EarningsPerShareDiluted", "EarningsPerShareBasicAndDiluted"):
        rows = gaap.get(concept, {}).get("units", {}).get("USD/shares")
        if rows:
            return concept, rows
    raise RuntimeError(
        "No US-GAAP diluted EPS in SEC's XBRL data (foreign filers reporting under IFRS "
        "aren't supported)."
    )


def is_periodic_report(fact: dict) -> bool:
    """True for a fact from a 10-Q or 10-K, including amendments (10-Q/A,
    10-K/A): the only filings EPS, R&D and share counts are taken from."""
    return str(fact.get("form", "")).startswith(("10-Q", "10-K"))


def _duration_facts(rows: list[dict], as_of: Optional[date] = None) -> dict[tuple[date, date], dict]:
    """The most recently filed 10-Q/10-K value for each (start, end) period,
    which picks up restatements. Instant (point-in-time) facts are skipped.
    With `as_of`, facts filed after that date are ignored first, giving the
    values as they were known on that date."""
    latest: dict[tuple[date, date], dict] = {}
    for r in rows:
        if "start" not in r or not is_periodic_report(r):
            continue
        if as_of is not None and date.fromisoformat(r["filed"]) > as_of:
            continue
        key = (date.fromisoformat(r["start"]), date.fromisoformat(r["end"]))
        if key not in latest or r["filed"] > latest[key]["filed"]:
            latest[key] = r
    return latest


def _split_factor(filed: date, splits: Optional[list[tuple[date, float]]]) -> float:
    """Product of the split ratios dated after `filed`: what a per-share value
    filed on that date must be divided by to be on today's share basis."""
    factor = 1.0
    for split_date, ratio in splits or []:
        if split_date > filed:
            factor *= ratio
    return factor


def _split_label(ratio: float) -> str:
    return f"{ratio:g}-for-1 split" if ratio >= 1 else f"1-for-{1 / ratio:g} reverse split"


def _quarter_series(
    latest: dict[tuple[date, date], dict], splits: Optional[list[tuple[date, float]]] = None,
) -> tuple[list[Quarter], dict[date, tuple[date, float]]]:
    """Fiscal quarters (oldest first) and fiscal-year values keyed by year end
    -> (start, value).

    10-Qs report Q1-Q3 as 3-month periods; Q4 is usually only inside the
    10-K's 12-month figure, so it's derived as FY - (Q1 + Q2 + Q3). That's
    only meaningful for amounts that add up across quarters (EPS
    approximately, R&D exactly) -- not for share counts.

    `splits` ([(split date, ratio)], e.g. 4.0 for 4-for-1) puts per-share
    values on today's share basis: each fact is divided by the splits dated
    after its filing date, before quarters are summed or Q4 is derived."""
    quarters: dict[date, Quarter] = {}
    annuals: dict[date, tuple[date, float]] = {}
    annual_filed: dict[date, date] = {}
    for (start, end), r in latest.items():
        filed = date.fromisoformat(r["filed"])
        value = float(r["val"]) / _split_factor(filed, splits)
        days = (end - start).days + 1
        if 80 <= days <= 100:
            quarters[end] = Quarter(start, end, value, r["form"], filed)
        elif 350 <= days <= 380:
            annuals[end] = (start, value)
            annual_filed[end] = filed

    for end, (start, fy_value) in annuals.items():
        if end in quarters:
            continue
        inside = sorted((q for q in quarters.values() if q.start >= start - timedelta(days=7) and q.end < end),
                        key=lambda q: q.end)
        if len(inside) == 3 and _contiguous(inside):
            q4_start = inside[-1].end + timedelta(days=1)
            # filed: the earliest of the facts it's built from, so a split after any of them gets noted
            quarters[end] = Quarter(q4_start, end, fy_value - sum(q.eps for q in inside), "derived: FY - Q1-Q3",
                                    min([annual_filed[end]] + [q.filed for q in inside if q.filed is not None]))

    return sorted(quarters.values(), key=lambda q: q.end), annuals


def fiscal_quarters(
    facts: dict, as_of: Optional[date] = None, splits: Optional[list[tuple[date, float]]] = None,
    through: Optional[date] = None,
) -> tuple[str, list[Quarter]]:
    """Every fiscal quarter of diluted EPS SEC has, oldest first (Q4 derived
    as FY - Q1-Q3 where needed; most recently filed value per period).
    `as_of` and `splits`: see _duration_facts and _quarter_series. `through`
    drops quarters ending after that date (within a week, for 52/53-week
    years)."""
    concept, rows = _eps_rows(facts)
    quarters, _ = _quarter_series(_duration_facts(rows, as_of), splits)
    if through is not None:
        quarters = [q for q in quarters if q.end <= through + timedelta(days=7)]
    return concept, quarters


def ttm_diluted_eps(
    facts: dict, today: Optional[date] = None, as_of: Optional[date] = None,
    splits: Optional[list[tuple[date, float]]] = None, through: Optional[date] = None,
) -> TtmEps:
    """Sum of the last four fiscal quarters of diluted EPS, plus the prior
    four (when they're consecutive with them) for the 2-year EPS.
    `as_of` builds the TTM from facts filed on or before that date (as known
    then); `splits` puts EPS on today's share basis (see _quarter_series);
    `through` ends the TTM at that quarter instead of the latest one."""
    concept, ordered = fiscal_quarters(facts, as_of, splits, through)
    today = today or date.today()
    if len(ordered) < 4:
        raise RuntimeError(f"Only {len(ordered)} fiscal quarter(s) of diluted EPS found in SEC data.")
    last4 = ordered[-4:]
    if not _contiguous(last4):
        periods = ", ".join(f"{q.start}..{q.end}" for q in last4)
        raise RuntimeError(f"The latest four quarters of EPS aren't consecutive ({periods}); can't build TTM.")

    notes = []
    if concept != "EarningsPerShareDiluted":
        notes.append(f"EPS from XBRL tag {concept}: the company reports one figure for basic and diluted EPS")
    if any(q.derived for q in last4):
        notes.append("Q4 derived as annual EPS minus Q1-Q3")
    if (today - last4[-1].end).days > STALE_EPS_DAYS:
        notes.append(f"latest reported quarter ended {last4[-1].end}, more than {STALE_EPS_DAYS} days ago; "
                     "EPS may be stale")

    prior, prior_reason = [], ""
    if len(ordered) < 8:
        prior_reason = "fewer than 8 quarters of EPS at SEC"
    elif not _contiguous(ordered[-8:]):
        prior_reason = "the four quarters before the current TTM aren't consecutive with it"
    else:
        prior = ordered[-8:-4]
    for split_date, ratio in sorted({(d, x) for q in last4 + prior for d, x in splits or []
                                     if q.filed is not None and d > q.filed}):
        notes.append(f"EPS put on today's share basis: values filed before the {_split_label(ratio)} on "
                     f"{split_date} were divided by {ratio:g}")
    return TtmEps(
        value=round(sum(q.eps for q in last4), 4), quarters=last4, concept=concept, notes=notes,
        prior_quarters=prior,
        prior_value=round(sum(q.eps for q in prior), 4) if prior else None,
        prior_reason=prior_reason,
    )


def two_year_eps(eps: TtmEps) -> tuple[Optional[float], list[Quarter], str]:
    """The trimmed 2-year EPS: the last 8 fiscal quarters (eps.prior_quarters
    and eps.quarters) without the single highest and single lowest, x 4 --
    i.e. 4 x the mean of the other six. Returns (value, [lowest, highest],
    ""), or (None, [], why) without 8 consecutive quarters."""
    if eps.prior_value is None:
        return None, [], eps.prior_reason
    quarters = eps.prior_quarters + eps.quarters
    ranked = sorted(quarters, key=lambda q: q.eps)  # stable: one quarter each on ties
    lowest, highest = ranked[0], ranked[-1]
    kept = sum(q.eps for q in quarters) - lowest.eps - highest.eps
    return round(kept * 4 / 6, 4), [lowest, highest], ""


def six_month_eps(eps: TtmEps) -> float:
    """The 6-month EPS: the TTM's last two fiscal quarters x 2, annualized so
    it's on the same yearly basis as TTM and 2-year EPS. Always available
    with the TTM, whose four quarters are consecutive."""
    return round(sum(q.eps for q in eps.quarters[-2:]) * 2, 4)


def _contiguous(quarters: list[Quarter]) -> bool:
    """Each quarter starts within a week of the previous one ending
    (allows for 52/53-week fiscal calendars)."""
    return all(0 < (b.start - a.end).days <= 7 for a, b in zip(quarters, quarters[1:]))


def filing_gap_note(eps: TtmEps, profile: Optional[SecProfile]) -> Optional[str]:
    """Note when the company has filed a 10-Q/10-K for a later period than
    SEC's XBRL company facts contain -- SEC's API sometimes never picks a
    filing up (seen with Duke Energy's June 2026 10-Q)."""
    if profile is None or profile.latest_periodic is None:
        return None
    form, period_end, filed = profile.latest_periodic
    if period_end > eps.quarters[-1].end + timedelta(days=7):
        return (f"SEC's XBRL data doesn't include the {form} for the period ended {period_end} (filed {filed}); "
                f"TTM EPS ends {eps.quarters[-1].end} and is at least a quarter behind")
    return None


# --------------------------------------------------------------------------
# R&D capitalization (Damodaran-style)
# --------------------------------------------------------------------------
def _merged_duration_facts(
    gaap: dict, tags: list[str], unit: str, as_of: Optional[date] = None,
) -> dict[tuple[date, date], dict]:
    """Latest-filed value per (start, end) period across several tags; for a
    period reported under more than one tag, the earlier tag in `tags` wins.
    Each fact is tagged with the XBRL tag it came from ("tag"). `as_of`: see
    _duration_facts."""
    merged: dict[tuple[date, date], dict] = {}
    for tag in tags:
        for key, r in _duration_facts(gaap.get(tag, {}).get("units", {}).get(unit) or [], as_of).items():
            merged.setdefault(key, {**r, "tag": tag})
    return merged


def _years_before(d: date, years: int) -> date:
    try:
        return d.replace(year=d.year - years)
    except ValueError:  # Feb 29
        return d.replace(year=d.year - years, day=28)


def _near(values: dict[date, float], target: date, tolerance_days: int = 10) -> Optional[float]:
    """The value whose period end is closest to `target`, within the
    tolerance (52/53-week fiscal years drift by a few days a year)."""
    best = min(values, key=lambda e: abs((e - target).days), default=None)
    if best is None or abs((best - target).days) > tolerance_days:
        return None
    return values[best]


def _twelve_months_ending(quarters: list[Quarter], annuals: dict[date, tuple[date, float]], end: date) -> Optional[float]:
    """Twelve months of a flow (R&D) ending near `end`: four consecutive
    quarters when available, else a fiscal-year figure ending there."""
    for i in range(3, len(quarters)):
        if abs((quarters[i].end - end).days) <= 10 and _contiguous(quarters[i - 3:i + 1]):
            return sum(q.eps for q in quarters[i - 3:i + 1])
    return _near({e: v for e, (_, v) in annuals.items()}, end)


def _annual_split(annuals: dict[date, tuple[date, float]], start: date, end: date) -> Optional[float]:
    """R&D for start..end estimated from the fiscal-year totals it overlaps,
    each split in proportion to days (assumes even spending within a year).
    None unless those fiscal years cover the whole window (within 10 days)."""
    total, covered = 0.0, 0
    for fy_end, (fy_start, value) in annuals.items():
        overlap = (min(end, fy_end) - max(start, fy_start)).days + 1
        if overlap > 0:
            total += value * overlap / ((fy_end - fy_start).days + 1)
            covered += overlap
    return total if abs(covered - ((end - start).days + 1)) <= 10 else None


def _diluted_shares(
    gaap: dict, eps: TtmEps, basis_end: date, as_of: Optional[date] = None,
    splits: Optional[list[tuple[date, float]]] = None,
) -> tuple[Optional[float], Optional[int]]:
    """Weighted-average diluted shares for the R&D window, and for a TTM
    window how many of its quarters had a count (None otherwise). For a TTM
    window: the average of its quarters' 3-month figures (the 10-K's annual
    figure stands in for a derived Q4). Otherwise, or if those are all
    missing, the annual figure ending at basis_end, else the latest within a
    year. `as_of` ignores facts filed later; `splits` puts the counts on
    today's share basis (a count filed before a split is multiplied by its
    ratio)."""
    facts = _merged_duration_facts(gaap, DILUTED_SHARE_TAGS, "shares", as_of)
    quarterly, annual = {}, {}
    for (start, end), r in facts.items():
        days = (end - start).days + 1
        shares = float(r["val"]) * _split_factor(date.fromisoformat(r["filed"]), splits)
        if 80 <= days <= 100:
            quarterly[end] = shares
        elif 350 <= days <= 380:
            annual[end] = shares

    counted = None
    if basis_end == eps.quarters[-1].end:
        found = [_near(quarterly, q.end, 7) or _near(annual, q.end, 7) for q in eps.quarters]
        found = [v for v in found if v]
        if found:
            return sum(found) / len(found), len(found)
        counted = 0
    shares = _near(annual, basis_end)
    if shares is None:
        recent = [e for e in annual if e <= basis_end and (basis_end - e).days <= 400]
        shares = annual[max(recent)] if recent else None
    return shares, counted


def quarter_diluted_shares(
    facts: dict, quarter_end: date, as_of: Optional[date] = None,
    splits: Optional[list[tuple[date, float]]] = None,
) -> Optional[float]:
    """One quarter's weighted-average diluted shares, on today's share basis: its 3-month
    figure, or the fiscal year's for a quarter without one (a Q4, reported only in the
    10-K). Facts filed after `as_of` are ignored. It puts a one-time item a press release
    states in dollars only per share (release_reconciliation)."""
    gaap = facts.get("facts", {}).get("us-gaap", {})
    quarterly, annual = {}, {}
    for (start, end), r in _merged_duration_facts(gaap, DILUTED_SHARE_TAGS, "shares", as_of).items():
        days = (end - start).days + 1
        shares = float(r["val"]) * _split_factor(date.fromisoformat(r["filed"]), splits)
        if 80 <= days <= 100:
            quarterly[end] = shares
        elif 350 <= days <= 380:
            annual[end] = shares
    return _near(quarterly, quarter_end, 7) or _near(annual, quarter_end, 7)


def rd_adjustment(
    facts: dict, eps: TtmEps, life: int = RD_AMORTIZATION_YEARS, as_of: Optional[date] = None,
    splits: Optional[list[tuple[date, float]]] = None,
) -> RdAdjustment:
    """Capitalize R&D (straight-line over `life` years) and express
    (current R&D - amortization) per diluted share, to add to TTM EPS.

    Current R&D covers the same TTM window as EPS. If quarterly R&D isn't
    available, the latest fiscal year (within about a year of the TTM end)
    is used instead and the prior years shift with it. Amortization = the R&D
    of the prior `life` twelve-month periods / life. A period that can't be
    built from quarters or a fiscal year is estimated by splitting the
    fiscal-year totals it overlaps; any still missing are filled with the
    average of the others, so amortization = their average (effective life =
    the years available). Fewer than RD_MIN_PRIOR_YEARS (or `life`, if
    shorter) -> not computed. No R&D tag at all -> zero adjustment.

    Point-in-time (pvgo_history.py): `as_of` uses only facts filed on or before
    that date, and `splits` puts the share count on today's share basis."""
    def listed(dates: list[date]) -> str:
        return ", ".join(str(d) for d in sorted(dates))

    gaap = facts.get("facts", {}).get("us-gaap", {})
    rd_facts = _merged_duration_facts(gaap, RD_TAGS, "USD", as_of)
    if not rd_facts:
        return RdAdjustment(0.0, life=life, basis="no R&D expense in SEC's data")
    quarters, annuals = _quarter_series(rd_facts)
    notes = []

    basis_end = eps.quarters[-1].end
    current = _twelve_months_ending(quarters, annuals, basis_end)
    basis = f"TTM ending {basis_end}"
    if current is None:
        fy_ends = [e for e in annuals if e <= basis_end and (basis_end - e).days <= 400]
        if not fy_ends:
            latest = max(end for _, end in rd_facts)
            return RdAdjustment(None, life=life, notes=[
                f"R&D for the TTM ending {basis_end} isn't in SEC's data (latest R&D figure: period ending "
                f"{latest}); R&D adjustment not computed"])
        basis_end = max(fy_ends)
        current = annuals[basis_end][1]
        basis = f"fiscal year ending {basis_end}"
        notes.append(f"quarterly R&D isn't available for the TTM, so the R&D adjustment uses the {basis} "
                     "and the fiscal years before it")

    prior, split, missing = [], [], []
    for j in range(1, life + 1):
        end = _years_before(basis_end, j)
        value = _twelve_months_ending(quarters, annuals, end)
        if value is None:
            value = _annual_split(annuals, _years_before(basis_end, j + 1) + timedelta(days=1), end)
            if value is not None:
                split.append(end)
        if value is None:
            missing.append(end)
        else:
            prior.append(value)
    if split:
        notes.append(f"R&D for the twelve months ending {listed(split)} estimated by splitting fiscal-year "
                     "totals by days (assumes even spending within each year)")
    required = min(RD_MIN_PRIOR_YEARS, life)
    if len(prior) < required:
        return RdAdjustment(None, rd_current=current, life=life, basis=basis, notes=notes + [
            f"R&D available for only {len(prior)} of the {life} prior years (missing the twelve months ending "
            f"{listed(missing)}); at least {required} are needed, so the R&D adjustment isn't computed"])
    amortization = sum(prior) / len(prior)  # same as filling the missing years with the average of the rest
    if missing:
        notes.append(f"R&D available for {len(prior)} of the {life} prior years (missing the twelve months ending "
                     f"{listed(missing)}); the gaps are filled with the average of the available years, so "
                     f"amortization = their sum / {len(prior)} (effective life {len(prior)} years)")

    # Which tags the windows above drew on: only worth a note when it's not the standard one.
    window_start = _years_before(basis_end, life + 1)
    tags = sorted({r["tag"] for (_, end), r in rd_facts.items() if window_start < end <= basis_end + timedelta(days=10)},
                  key=RD_TAGS.index)
    if len(tags) > 1:
        notes.append(f"R&D combines XBRL tags {' and '.join(tags)} (the company switched tags; for a period "
                     "reported under both, the first is used)")
    elif tags and tags[0] != "ResearchAndDevelopmentExpense":
        notes.append(f"R&D from XBRL tag {tags[0]}")

    shares, counted = _diluted_shares(gaap, eps, basis_end, as_of, splits)
    if not shares:
        return RdAdjustment(None, rd_current=current, amortization=amortization, life=life, basis=basis,
                            notes=notes + ["no diluted share count in SEC's data; R&D adjustment not computed"])
    if counted == 0:
        notes.append("no diluted share count for the TTM quarters in SEC's data; the R&D adjustment uses the "
                     "fiscal-year count")
    elif counted is not None and counted < len(eps.quarters):
        notes.append(f"diluted share count averaged over {counted} of the {len(eps.quarters)} TTM quarters (the "
                     "others have no count in SEC's data)")
    per_share = (current - amortization) * (1 - RD_TAX_RATE) / shares
    return RdAdjustment(per_share, rd_current=current, amortization=amortization, shares=shares, life=life,
                        effective_life=len(prior), basis=basis, notes=notes)


def _flow_quarters(rows: list[dict], as_of: Optional[date] = None) -> dict[date, Quarter]:
    """Quarterly values of a flow (USD) from one XBRL tag's 10-Q/10-K facts, keyed by quarter end.
    3-month facts are used as reported. The rest come from year-to-date facts that share a fiscal
    year's start (6-month - 3-month, 9-month - 6-month, 12-month - 9-month): a cash-flow-statement
    line is reported year-to-date only. A Q4 still missing is FY - (Q1 + Q2 + Q3), as in
    _quarter_series. Within one tag only, so differences never mix tags. `as_of`: see
    _duration_facts."""
    latest = _duration_facts(rows, as_of)
    quarters: dict[date, Quarter] = {}
    by_start: dict[date, list[tuple[date, dict]]] = {}
    annuals: dict[date, tuple[date, float, date]] = {}
    for (start, end), r in latest.items():
        days = (end - start).days + 1
        filed = date.fromisoformat(r["filed"])
        if 80 <= days <= 100:
            quarters[end] = Quarter(start, end, float(r["val"]), r["form"], filed)
        if 350 <= days <= 380:
            annuals[end] = (start, float(r["val"]), filed)
        if days >= 80:
            by_start.setdefault(start, []).append((end, r))
    for spans in by_start.values():
        spans.sort(key=lambda s: s[0])
        for (end0, r0), (end1, r1) in zip(spans, spans[1:]):
            if 80 <= (end1 - end0).days <= 100 and end1 not in quarters:
                filed = max(date.fromisoformat(r0["filed"]), date.fromisoformat(r1["filed"]))
                quarters[end1] = Quarter(end0 + timedelta(days=1), end1, float(r1["val"]) - float(r0["val"]),
                                         "derived: year-to-date difference", filed)
    for end, (start, fy_value, filed) in annuals.items():
        if end in quarters:
            continue
        inside = sorted((q for q in quarters.values() if q.start >= start - timedelta(days=7) and q.end < end),
                        key=lambda q: q.end)
        if len(inside) == 3 and _contiguous(inside):
            quarters[end] = Quarter(inside[-1].end + timedelta(days=1), end, fy_value - sum(q.eps for q in inside),
                                    "derived: FY - Q1-Q3", max([filed] + [q.filed for q in inside if q.filed]))
    return quarters


def investment_gain_adjustment(
    facts: dict, eps: TtmEps, sic: Optional[int] = None, as_of: Optional[date] = None,
    splits: Optional[list[tuple[date, float]]] = None,
) -> InvestmentAdjustment:
    """The adjustment that turns TTM EPS into the adjusted TTM EPS: minus the gains (plus the
    losses) on investments in the TTM's quarters, less INVESTMENT_GAIN_TAX_RATE, per diluted share.

    Each quarter's gain comes from the first INVESTMENT_GAIN_TAGS tag that has it (built per tag by
    _flow_quarters, so a year-to-date difference never mixes tags). A TTM quarter no tag covers
    counts as zero, with a note when other quarters are covered. No tag at all -> zero adjustment.
    Financial companies (FINANCIAL_SIC) are exempt: their investment gains are operating income.

    Point-in-time (pvgo_history.py): `as_of` uses only facts filed on or before that date, and
    `splits` puts the share count on today's share basis."""
    basis_end = eps.quarters[-1].end
    if sic is not None and sic in FINANCIAL_SIC:
        return InvestmentAdjustment(0.0, basis=f"exempt: financial company (SIC {sic})", notes=[
            f"investment gains not excluded from EPS: a financial company's (SIC {sic}) are operating income"])
    gaap = facts.get("facts", {}).get("us-gaap", {})
    per_tag, spans = [], {}
    for tag in INVESTMENT_GAIN_TAGS:
        rows = gaap.get(tag, {}).get("units", {}).get("USD") or []
        quarters = _flow_quarters(rows, as_of)
        if quarters:
            per_tag.append((tag, {end: q.eps for end, q in quarters.items()}))
        if rows:  # every tag's periods, for across_tags: some report only a fiscal year
            spans[tag] = _duration_facts(rows, as_of)
    if not per_tag and not spans:
        return InvestmentAdjustment(0.0, basis="no investment gains in SEC's data")

    def find(test) -> Optional[tuple[str, date, float]]:
        """The first (tag, start, value) in priority order whose (start, end) passes `test`."""
        return next(((tag, s, float(r["val"])) for tag in INVESTMENT_GAIN_TAGS
                     for (s, e), r in spans.get(tag, {}).items() if test(s, e)), None)

    def across_tags(q: Quarter) -> Optional[tuple[float, list[str]]]:
        """Last resort for a quarter no single tag gives: a fiscal-year total under one tag less the
        9 months before the quarter under another, both from the fiscal year's start (Amazon 2022:
        9 months under the total-gain tag, the full year only under the unrealized one)."""
        fy = find(lambda s, e: abs((e - q.end).days) <= 7 and 350 <= (e - s).days + 1 <= 380)
        if fy is None:
            return None
        nine = find(lambda s, e: abs((s - fy[1]).days) <= 7 and abs((e - q.start).days) <= 8
                    and 260 <= (e - s).days + 1 <= 290)
        return (fy[2] - nine[2], [fy[0], nine[0]]) if nine is not None else None

    def first_hit(tags: list) -> Optional[tuple[str, float]]:
        return next(((tag, value) for tag, values in tags for value in [_near(values, q.end, 7)] if value is not None),
                    None)

    gains, used_tags, missing, crossed = 0.0, [], [], []
    for q in eps.quarters:
        # A tag's own quarter first, then a fiscal year less 9 months across tags, then the fallback tags.
        hit = first_hit([(t, v) for t, v in per_tag if t not in INVESTMENT_GAIN_FALLBACK_TAGS])
        tags_for_q = [hit[0]] if hit else []
        if hit is None:
            derived = across_tags(q)
            if derived is not None:
                hit, tags_for_q = ("", derived[0]), derived[1]
                crossed.append(f"{q.end} ({derived[1][0]} for the fiscal year less {derived[1][1]} for 9 months)")
        if hit is None:
            hit = first_hit([(t, v) for t, v in per_tag if t in INVESTMENT_GAIN_FALLBACK_TAGS])
            tags_for_q = [hit[0]] if hit else []
        if hit is None:
            missing.append(q.end)
            continue
        gains += hit[1]
        used_tags += [t for t in tags_for_q if t not in used_tags]
    basis = f"TTM ending {basis_end}"
    if not used_tags:
        return InvestmentAdjustment(0.0, gains_ttm=0.0, basis=f"{basis}: no investment gains reported for its quarters")
    notes = []
    if crossed:
        notes.append("investment gains for the quarter(s) ending " + "; ".join(crossed) + ", since no single tag has it")
    if missing:
        notes.append(f"investment gains not in SEC's data for the quarter(s) ending {', '.join(map(str, missing))}; "
                     "counted as zero in the adjusted TTM EPS")
    shares, _ = _diluted_shares(gaap, eps, basis_end, as_of, splits)
    tags = ", ".join(sorted(used_tags, key=INVESTMENT_GAIN_TAGS.index))
    if not shares:
        return InvestmentAdjustment(None, gains_ttm=gains, tags=tags, basis=basis, notes=notes + [
            "no diluted share count in SEC's data; adjusted TTM EPS not computed"])
    per_share = -gains * (1 - INVESTMENT_GAIN_TAX_RATE) / shares
    return InvestmentAdjustment(per_share, gains_ttm=gains, shares=shares, tags=tags, basis=basis, notes=notes)


# --------------------------------------------------------------------------
# Warning flags
# --------------------------------------------------------------------------
def one_time_flags(quarters: list[Quarter]) -> list[tuple[Quarter, str]]:
    """Quarters that look like a one-time item: negative while the others
    are positive, or more than ONE_TIME_DEVIATION x |median| away from the
    median of the four. (The median test is skipped when the median is 0.)"""
    if not quarters:
        return []
    median = statistics.median(q.eps for q in quarters)
    flagged = []
    for q in quarters:
        reasons = []
        if q.eps < 0 and all(o.eps > 0 for o in quarters if o is not q):
            reasons.append("negative while the other three quarters are positive")
        if median != 0 and abs(q.eps - median) > ONE_TIME_DEVIATION * abs(median):
            reasons.append(f"more than {ONE_TIME_DEVIATION:.0%} away from the four-quarter median {median:.2f}")
        if reasons:
            flagged.append((q, " and ".join(reasons)))
    return flagged


def _describe_quarter(q: Quarter) -> str:
    return f"quarter ended {q.end}{' (Q4 derived = FY - Q1-Q3)' if q.derived else ''}"


def _sign(x: float) -> int:
    return (x > 0) - (x < 0)


def earnings_quality_notes(eps: TtmEps) -> list[str]:
    """One-time-item notes for the TTM quarters (or one "erratic earnings"
    note when ERRATIC_MIN_FLAGS or more are flagged), plus a note when the
    TTM sign hinges on its single largest-magnitude quarter."""
    notes = []
    flags = one_time_flags(eps.quarters)
    if len(flags) >= ERRATIC_MIN_FLAGS:
        notes.append(f"erratic earnings; trailing EPS unreliable ({len(flags)} of the 4 TTM quarters trip "
                     "the one-time-item checks)")
    else:
        notes += [f"possible one-time item: {_describe_quarter(q)}, EPS {q.eps:.2f} -- {why}" for q, why in flags]

    biggest = max(eps.quarters, key=lambda q: abs(q.eps))
    rest = sum(q.eps for q in eps.quarters if q is not biggest)
    total = sum(q.eps for q in eps.quarters)
    if _sign(total) != _sign(rest):
        notes.append(f"TTM EPS sign depends on a single quarter: {_describe_quarter(biggest)} has EPS "
                     f"{biggest.eps:+.2f}, and the other three sum to {rest:+.2f}; growth share is unreliable")
    return notes


def rd_tax_wording() -> str:
    """How the R&D add-back is taxed (RD_TAX_RATE), for report and chart text."""
    return "not tax-effected (Damodaran's method)" if RD_TAX_RATE == 0 else f"tax-effected at {RD_TAX_RATE:.0%}"
