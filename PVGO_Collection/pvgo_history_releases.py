"""PVGO history, per quarter: the earnings release date, the measurement day, the TTM
as known at the release and the press-release EPS reconciliation.
METHODOLOGY section 7.
"""

from __future__ import annotations

import bisect
import os
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from time import sleep
from typing import Optional

import requests

from pvgo_eps import Quarter, ttm_diluted_eps, TtmEps
from pvgo_inputs import (
    AMENDMENT_WINDOW_DAYS,
    EARNINGS_ITEM,
    ITEM_DOLLAR_RE,
    ITEM_OUTLOOK_RE,
    ITEM_PER_SHARE_RE,
    ITEM_SENTENCE_MAX_CHARS,
    ITEM_SENTENCE_SPLIT_RE,
    ITEM_SENTENCES_MAX_CHARS,
    ITEM_WORD_RE,
    MARKET_CLOSE,
    NEW_YORK,
    RECONCILIATION_MAX_CELL_CHARS,
    RECONCILIATION_MAX_CHARS,
    RECONCILIATION_RE,
    REPORT_DATE_TOLERANCE_DAYS,
    SEC_CACHE_DIR,
    SEC_FILING_INDEX_URL,
    SEC_FILING_PAGES_MAX_AGE_DAYS,
    SEC_FILING_TEXT_URL,
    _sec_get_json,
    SEC_REQUEST_DELAY_SECONDS,
    SEC_SUBMISSIONS_FILE_URL,
    SEC_SUBMISSIONS_URL,
)


@dataclass
class Release:
    quarter_end: date
    release_date: date
    form: str  # the filing that set release_date: "8-K", "10-Q" or "10-K"
    cutoff: date  # filing date of the quarter's 10-Q/10-K: EPS facts filed later are ignored
    accepted: Optional[datetime] = None  # when SEC accepted the filing that set release_date (New York time)
    measurement_date: Optional[date] = None  # first trading day whose close comes after the release (see _measurement_day)
    other_8k_days: list[date] = field(default_factory=list)  # later days with an earnings 8-K for the same quarter
    amendments: list[tuple[str, date]] = field(default_factory=list)  # (form, filed): 10-Q/A or 10-K/A soon after
    eps_from: str = ""  # "" = facts filed by the cutoff; else "pre-XBRL backfill" or the amendment's form
    eps_as_of: Optional[date] = None  # with eps_from: the later filing date the EPS facts come from
    accession: str = ""  # SEC accession number of the filing that set release_date (for its documents)


def _filing_rows(block: dict) -> list[dict]:
    """SEC's columnar filing arrays (filings.recent, or an older submissions
    file) as one dict per filing."""
    keys = ("form", "filingDate", "reportDate", "items", "acceptanceDateTime", "accessionNumber")
    n = len(block.get("form") or [])
    cols = {k: (block.get(k) or [""] * n) for k in keys}
    return [{k: str(cols[k][i] or "") for k in keys} for i in range(n)]


def load_filings(cik: int, session: requests.Session, user_agent: str, since: date) -> tuple[dict, list[dict]]:
    """The submissions JSON and its filings (form, filingDate, reportDate,
    items, acceptanceDateTime, accessionNumber). When filings.recent doesn't reach back to `since`, the older
    files listed under filings.files that cover it are loaded too."""
    data = _sec_get_json(SEC_SUBMISSIONS_URL.format(cik=cik), session, user_agent)
    filings = data.get("filings", {})
    rows = _filing_rows(filings.get("recent", {}))
    oldest = min((r["filingDate"] for r in rows if r["filingDate"]), default="")
    if not oldest or date.fromisoformat(oldest) > since:
        for f in filings.get("files", []):
            if f.get("filingTo") and date.fromisoformat(f["filingTo"]) >= since:
                # Older pages come from cache/sec/ for up to SEC_FILING_PAGES_MAX_AGE_DAYS; heavy filers have
                # dozens. A cached page whose filing count no longer matches SEC's list is downloaded again.
                url = SEC_SUBMISSIONS_FILE_URL.format(name=f["name"])
                page = _filing_rows(_sec_get_json(url, session, user_agent, SEC_FILING_PAGES_MAX_AGE_DAYS))
                if f.get("filingCount") and len(page) != f["filingCount"]:
                    page = _filing_rows(_sec_get_json(url, session, user_agent, 0))
                rows += page
    return data, rows


# --------------------------------------------------------------------------
# Releases and the no-growth line
# --------------------------------------------------------------------------
def _new_york_time(accepted: str) -> Optional[datetime]:
    """SEC's acceptanceDateTime (UTC, e.g. "2024-10-30T20:04:07.000Z") in New York time; None if missing."""
    try:
        return datetime.fromisoformat(accepted).astimezone(NEW_YORK)
    except ValueError:
        return None


def find_releases(quarters: list[Quarter], filings: list[dict]) -> tuple[list[Release], list[str]]:
    """The earnings release of each XBRL quarter whose original 10-Q/10-K is
    in `filings` (oldest first), with the time SEC accepted the filing that
    set it, plus notes about a newer quarter that's been released or filed
    but isn't in SEC's XBRL data yet (it gets no step)."""
    periodic = [f for f in filings if f["form"] in ("10-Q", "10-K") and f["reportDate"] and f["filingDate"]]
    amended = [f for f in filings if f["form"] in ("10-Q/A", "10-K/A") and f["reportDate"] and f["filingDate"]]
    # (filing date, acceptance time, accession): sorted, so the earliest of a day's 8-Ks comes first
    earnings_8ks = sorted((date.fromisoformat(f["filingDate"]), f["acceptanceDateTime"], f["accessionNumber"])
                          for f in filings
                          if f["form"] == "8-K" and f["filingDate"]
                          and EARNINGS_ITEM in [item.strip() for item in f["items"].split(",")])

    def same_quarter(f: dict, end: date) -> bool:
        return abs((date.fromisoformat(f["reportDate"]) - end).days) <= REPORT_DATE_TOLERANCE_DAYS

    releases = []
    for q in quarters:
        matches = [f for f in periodic if same_quarter(f, q.end)]
        if not matches:
            continue  # filed before the filings loaded
        filing = min(matches, key=lambda f: f["filingDate"])
        cutoff = date.fromisoformat(filing["filingDate"])
        in_window = [(d, accepted, acc) for d, accepted, acc in earnings_8ks if q.end < d <= cutoff]
        if in_window:
            (release_date, accepted, accession), form = in_window[0], "8-K"
        else:
            release_date, accepted, form = cutoff, filing["acceptanceDateTime"], filing["form"]
            accession = filing["accessionNumber"]
        amendments = sorted(((f["form"], date.fromisoformat(f["filingDate"])) for f in amended
                             if same_quarter(f, q.end)
                             and cutoff < date.fromisoformat(f["filingDate"]) <= cutoff + timedelta(days=AMENDMENT_WINDOW_DAYS)),
                            key=lambda a: a[1])
        releases.append(Release(q.end, release_date, form, cutoff, accepted=_new_york_time(accepted),
                                other_8k_days=sorted({d for d, _, _ in in_window} - {release_date}),
                                amendments=amendments, accession=accession))

    notes = []
    if quarters:
        last = quarters[-1].end
        newer = sorted((f for f in periodic
                        if date.fromisoformat(f["reportDate"]) > last + timedelta(days=REPORT_DATE_TOLERANCE_DAYS)),
                       key=lambda f: f["filingDate"])
        last_cutoff = releases[-1].cutoff if releases and releases[-1].quarter_end == last else None
        newer_8ks = [d for d, _, _ in earnings_8ks if last_cutoff and d > last_cutoff]
        if newer:
            f = newer[0]
            notes.append(f"the {f['form']} for the quarter ended {f['reportDate']} (filed {f['filingDate']}) isn't "
                         f"in SEC's XBRL data yet, so it gets no step; the line keeps the TTM through {last}")
        elif newer_8ks:
            notes.append(f"earnings for the quarter after {last} were released on {newer_8ks[0]} (8-K), but its "
                         f"10-Q/10-K isn't in SEC's XBRL data yet, so it gets no step; the line keeps the TTM "
                         f"through {last}")
    return releases, notes


# --------------------------------------------------------------------------
# Earnings press releases (--release-items)
# --------------------------------------------------------------------------
def _sec_get_text(url: str, session: requests.Session, user_agent: str, cache_name: str) -> str:
    """A text document from SEC (sec.gov Archives), kept in cache/sec/ for good:
    a filing never changes once accepted. Same User-Agent, delay and 403
    handling as _sec_get_json."""
    path = os.path.join(SEC_CACHE_DIR, cache_name)
    if os.path.exists(path):
        with open(path, encoding="utf-8", errors="replace") as f:
            return f.read()
    sleep(SEC_REQUEST_DELAY_SECONDS)
    r = session.get(url, headers={"User-Agent": user_agent, "Accept-Encoding": "gzip, deflate"}, timeout=60)
    if r.status_code == 403:
        raise RuntimeError("SEC returned 403 -- check SEC_EDGAR_USER_AGENT is a real name and email.")
    r.raise_for_status()
    text = r.content.decode("utf-8", errors="replace")
    try:
        os.makedirs(SEC_CACHE_DIR, exist_ok=True)
        with open(path + ".tmp", "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(path + ".tmp", path)
    except OSError:
        pass  # the cache is only a convenience
    return text


def _submission_documents(text: str) -> list[tuple[str, str, str]]:
    """(type, filename, body) of each <DOCUMENT> in a complete submission text file."""
    docs = []
    for m in re.finditer(r"<DOCUMENT>(.*?)</DOCUMENT>", text, re.S | re.I):
        doc = m.group(1)
        kind = re.search(r"<TYPE>([^\s<]+)", doc, re.I)
        name = re.search(r"<FILENAME>([^\s<]+)", doc, re.I)
        body = re.search(r"<TEXT>(.*)</TEXT>", doc, re.S | re.I)
        docs.append(((kind.group(1) if kind else "").upper(), name.group(1) if name else "",
                     body.group(1) if body else ""))
    return docs


def _table_lines(table) -> list[str]:
    """A BeautifulSoup table as 'cell | cell' lines: whitespace collapsed, empty and
    lone '$' cells dropped, a lone ')' or '%' joined to the cell before it."""
    lines = []
    for tr in table.find_all("tr"):
        cells = []
        for td in tr.find_all(["td", "th"]):
            cell = " ".join(td.get_text(" ", strip=True).split())
            if cell in ("", "$"):
                continue
            if cell in (")", "%", ")%", "%)") and cells:
                cells[-1] += cell
                continue
            cells.append(cell)
        if cells:
            lines.append(" | ".join(cells))
    return lines


def _item_sentences(soup) -> tuple[list[str], list[str]]:
    """An exhibit's sentences with an item word (ITEM_WORD_RE): those that name a per-share
    amount (ITEM_PER_SHARE_RE), and those that name a dollar amount only (ITEM_DOLLAR_RE),
    outlooks and estimates left out (ITEM_OUTLOOK_RE). Number tables are dropped first;
    text laid out in tables (a cell over RECONCILIATION_MAX_CELL_CHARS) is kept as text.
    Mutates the soup."""
    for table in soup.find_all("table"):
        cells = [" ".join(td.get_text(" ", strip=True).split()) for td in table.find_all(["td", "th"])]
        if max((len(c) for c in cells), default=0) <= RECONCILIATION_MAX_CELL_CHARS:
            table.decompose()
    text = " ".join(soup.get_text(" ").split())
    found = [s for s in (s.strip(" -•") for s in ITEM_SENTENCE_SPLIT_RE.split(text))
             if len(s) <= ITEM_SENTENCE_MAX_CHARS and ITEM_WORD_RE.search(s)]
    per_share = [s for s in found if ITEM_PER_SHARE_RE.search(s)]
    dollars = [s for s in found if not ITEM_PER_SHARE_RE.search(s) and ITEM_DOLLAR_RE.search(s)
               and not ITEM_OUTLOOK_RE.search(s)]
    return per_share, dollars


def _joined(sentences: list[str]) -> str:
    joined = "\n".join(sentences)
    return joined[:ITEM_SENTENCES_MAX_CHARS] + " [... cut]" if len(joined) > ITEM_SENTENCES_MAX_CHARS else joined


def release_reconciliation(cik: int, rel: Release, session: requests.Session, user_agent: str,
                           diluted_shares: Optional[float] = None) -> dict:
    """The one-time items a release's press release names, as text:
      - reconciliation_text: every table matching RECONCILIATION_RE (the
        GAAP-to-adjusted EPS reconciliation) in the 8-K's EX-99 exhibits (EX-99.1
        first, in document order, so the quarter's own table leads), except text
        laid out in tables (a cell over RECONCILIATION_MAX_CELL_CHARS);
      - item_sentences: the sentences that name a per-share item, for companies
        that state their items in the text (Costco), one per line;
      - item_dollar_sentences: the sentences that name an item in dollars only, for
        companies that give no per-share amount (Meta), one per line; with
        diluted_shares, the quarter's diluted share count, to put them per share.
    Together they name the one-time items behind a jump in GAAP EPS (legal
    charges, tax benefits, gains or losses on investments, restructuring). One SEC
    request per release, cached; a miss is recorded in `note`, never raised."""
    folder = (rel.accession or "").replace("-", "")
    row = {"quarter_end": rel.quarter_end.isoformat(), "release_date": rel.release_date.isoformat(),
           "release_form": rel.form, "accession": rel.accession,
           "filing_url": SEC_FILING_INDEX_URL.format(cik=cik, folder=folder, accession=rel.accession)
           if rel.accession else "", "exhibits": "", "n_tables": 0,
           "reconciliation_text": "", "item_sentences": "", "item_dollar_sentences": "",
           "diluted_shares": round(diluted_shares) if diluted_shares else "", "note": ""}
    if rel.form != "8-K":
        row["note"] = f"released by its {rel.form}: no press release"
        return row
    if not rel.accession:
        row["note"] = "no accession number in SEC's filing list"
        return row
    from bs4 import BeautifulSoup  # only needed for --release-items

    url = SEC_FILING_TEXT_URL.format(cik=cik, folder=folder, accession=rel.accession)
    try:
        text = _sec_get_text(url, session, user_agent, f"{rel.accession}.txt")
    except (requests.RequestException, RuntimeError) as exc:
        row["note"] = f"couldn't fetch the filing ({exc})"
        return row
    exhibits = sorted((d for d in _submission_documents(text) if d[0].startswith("EX-99")),
                      key=lambda d: (d[0] != "EX-99.1", d[0]))
    row["exhibits"] = "; ".join(f"{kind} {name}" for kind, name, _ in exhibits)
    if not exhibits:
        row["note"] = "no EX-99 exhibit in the 8-K"
        return row
    blocks, sentences, dollar_sentences = [], [], []
    for kind, name, body in exhibits:
        soup = BeautifulSoup(body, "html.parser")
        for table in soup.find_all("table"):
            if not RECONCILIATION_RE.search(" ".join(table.get_text(" ").split())):
                continue
            lines = _table_lines(table)
            if lines and max(len(c) for line in lines for c in line.split(" | ")) <= RECONCILIATION_MAX_CELL_CHARS:
                blocks.append(f"[{kind} table]\n" + "\n".join(lines))
        per_share, dollars = _item_sentences(soup)
        sentences += [s for s in per_share if s not in sentences]
        dollar_sentences += [s for s in dollars if s not in dollar_sentences]
    row["n_tables"] = len(blocks)
    joined = "\n\n".join(blocks)
    if len(joined) > RECONCILIATION_MAX_CHARS:
        joined = joined[:RECONCILIATION_MAX_CHARS] + "\n[... cut]"
    row["reconciliation_text"] = joined
    row["item_sentences"] = _joined(sentences)
    row["item_dollar_sentences"] = _joined(dollar_sentences)
    if not blocks:
        named = [w for w, s in (("per share", sentences), ("in dollars only", dollar_sentences)) if s]
        row["note"] = (f"no adjusted-EPS reconciliation table in the EX-99 exhibits; items named in the text "
                       f"({' and '.join(named)})" if named
                       else "no adjusted-EPS reconciliation table or item named in the EX-99 exhibits")
    return row


def _ttm_for(
    rel: Release, facts: dict, splits: list[tuple[date, float]], first_xbrl: date, later_filings: list[date],
) -> tuple[Optional[TtmEps], str]:
    """The TTM EPS ending at the release's quarter, as known at the release
    (facts filed by its 10-Q/10-K). Failing that:
      - from an amendment (10-Q/A, 10-K/A) of that filing filed soon after,
        when SEC's data credits the quarter's figures to the amendment;
      - pre-XBRL backfill: when the TTM reaches back before the company's
        first XBRL filing (`first_xbrl`), from the earliest later filing that
        has its quarters.
    Sets rel.eps_from / rel.eps_as_of when a later filing is used. Returns
    (TTM or None, why the point-in-time TTM failed)."""
    def attempt(as_of: date) -> tuple[Optional[TtmEps], str]:
        try:
            eps = ttm_diluted_eps(facts, today=rel.measurement_date, as_of=as_of, splits=splits,
                                  through=rel.quarter_end)
        except RuntimeError as exc:
            return None, f"no TTM from the XBRL facts filed by {as_of} ({exc})"
        if abs((eps.quarters[-1].end - rel.quarter_end).days) > REPORT_DATE_TOLERANCE_DAYS:
            return None, f"the XBRL facts filed by {as_of} only reach {eps.quarters[-1].end}"
        return eps, ""

    eps, why = attempt(rel.cutoff)
    if eps is not None:
        return eps, ""
    for form, filed in rel.amendments:
        eps, _ = attempt(filed)
        if eps is not None:
            rel.eps_from, rel.eps_as_of = form, filed
            return eps, ""
    if _pre_xbrl(rel, first_xbrl):
        for filed in (d for d in later_filings if d > rel.cutoff):
            eps, _ = attempt(filed)
            if eps is not None:
                rel.eps_from, rel.eps_as_of = "pre-XBRL backfill", filed
                return eps, ""
    return None, why


def _pre_xbrl(rel: Release, first_xbrl: date) -> bool:
    """True when the release's four-quarter TTM includes quarters that ended
    before the company's first XBRL filing (never machine-readable then)."""
    return rel.quarter_end - timedelta(days=365) < first_xbrl


def _next_trading_day(days: list[date], d: date) -> Optional[date]:
    i = bisect.bisect_right(days, d)
    return days[i] if i < len(days) else None


def _measurement_day(days: list[date], rel: Release) -> Optional[date]:
    """The first trading day whose close comes after the release was public:
    the day SEC accepted the filing, if that was before the close on a trading
    day (e.g. a 6:45 am release, or an 11:00 am 8-K after a pre-market press
    release); otherwise the first trading day after it (e.g. a 4:05 pm
    release). Without an acceptance time, the first trading day after the
    release date. None while that day's close isn't in yet."""
    if rel.accepted is None:
        day = _next_trading_day(days, rel.release_date)
    else:
        accepted_day = rel.accepted.date()
        i = bisect.bisect_left(days, accepted_day)
        # Before the close, not the open: that day's close already has the news. Walmart's 8-Ks
        # are accepted about 11:00, after its 7:00 press release; an open rule would measure them
        # the next day, a day after the reaction.
        if i < len(days) and days[i] == accepted_day and rel.accepted.time() < MARKET_CLOSE:
            day = accepted_day
        else:
            day = _next_trading_day(days, accepted_day)
    now = datetime.now(NEW_YORK)
    if day is not None and day == now.date() and now.time() < MARKET_CLOSE:
        return None  # today's bar is still an intraday price
    return day
