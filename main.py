"""
One company, end to end: why its growth share (PVGO / price) moved over a period.

    python main.py --ticker COST --search-terms Costco "Costco Wholesale" --sector-etf RSPS --start 2024-01 --end 2024-12

Runs each folder's own command in turn, so any step can also be run on its own:
  1. news     News_Collection/news_pull.py: the month-by-month article lists (free, Media Cloud)
  2. pvgo     PVGO_Collection/pvgo_history.py: the daily growth-share series (free: SEC, FRED, Yahoo)
  3. extract  Company_Narrative_Aggregation/extract_run.py --pull-dir: one run per month (paid)
  4. explain  Company_Narrative_Aggregation/explain_run.py: the explanation (paid)
Each paid step shows its estimated cost and asks first (--yes skips the question). Rerunning
the same command skips the months already pulled and extracted, so an interrupted run just
continues. The explanation is a new batch each time it runs (--steps leaves it out).
"""

import argparse
import calendar
import csv
import json
import os
import subprocess
import sys
from datetime import date
from pathlib import Path

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parent
NEWS = ROOT / "News_Collection"
PVGO = ROOT / "PVGO_Collection"
NARRATIVE = ROOT / "Company_Narrative_Aggregation"
SUBJECTS_JSON = NARRATIVE / "explain_subjects.json"
ERP_CSV = PVGO / "damodaran_implied_erp.csv"
STEPS = ["news", "pvgo", "extract", "explain"]
DEFAULT_MODEL = "Qwen/Qwen3-235B-A22B-Instruct-2507"  # extract_run.py's default (narrative_common.MODEL)
PRE_PERIOD_DAYS = 400  # the PVGO series' start before the period: room for the market model's 180-day fit


def parse_day(text: str, end: bool = False) -> date:
    """YYYY-MM-DD, or YYYY-MM for the month's first day (its last with end=True)."""
    if len(text) == 7:
        year, month = map(int, text.split("-"))
        return date(year, month, calendar.monthrange(year, month)[1] if end else 1)
    return date.fromisoformat(text)


def explanation_erp(first_year: int, last_year: int) -> float:
    """The ERP for an explanation run: the average of Damodaran's January estimates for the
    period's years (PVGO_Collection METHODOLOGY section 7). Years without a row yet are left
    out, with a note."""
    with open(ERP_CSV, newline="", encoding="utf-8") as f:
        rows = {r["as_of"]: float(r["erp_pct"]) for r in csv.DictReader(line for line in f if not line.startswith("#"))}
    years = range(first_year, last_year + 1)
    found = {y: rows[f"{y}-01-01"] for y in years if f"{y}-01-01" in rows}
    if not found:
        raise SystemExit(f"No January ERP in {ERP_CSV.name} for {first_year}-{last_year}: add the rows first")
    missing = [y for y in years if y not in found]
    if missing:
        print(f"  ! no January ERP for {', '.join(map(str, missing))} in {ERP_CSV.name}: averaging the other years")
    return round(sum(found.values()) / len(found), 2)


def subject_name(args: argparse.Namespace, ticker: str) -> str:
    """The company's name in the subject ("Costco" in "Costco (COST)"): --name, else the first
    search term that isn't the ticker, from the command or the folder's search_terms.csv."""
    if args.name:
        return args.name.strip()
    terms = [t.strip() for t in args.search_terms if t.strip()]
    saved = NEWS / "pulls" / ticker.lower() / "search_terms.csv"
    if not terms and saved.is_file():
        with open(saved, newline="", encoding="utf-8-sig") as f:
            terms = [r["term"].strip() for r in csv.DictReader(f)]
    names = [t for t in terms if t.upper() != ticker]
    if not names:
        raise SystemExit("Give the company's name: --search-terms <name> (also searched for) or --name <name>")
    return names[0]


def check_keys(steps: list[str], model: str) -> None:
    """Each step's credentials, checked before an hour of pulling rather than after."""
    needed = []
    if "news" in steps:
        needed.append((NEWS, "MEDIACLOUD_API_KEY"))
    if "pvgo" in steps:
        needed.append((PVGO, "SEC_EDGAR_USER_AGENT"))
    if "extract" in steps:
        needed.append((NARRATIVE, "ANTHROPIC_API_KEY" if model.startswith("claude-") else "DEEPINFRA_API_KEY"))
    if "explain" in steps:
        needed.append((NARRATIVE, "ANTHROPIC_API_KEY"))
    missing = [f"{key} in {folder.name}/.env" for folder, key in needed
               if not (dotenv_values(folder / ".env").get(key) or os.environ.get(key))]
    if missing:
        raise SystemExit("Missing: " + "; ".join(missing) + " (copy each folder's .env.example to .env and fill it in)")


def check_sector(ticker: str, sector_etf: str | None) -> None:
    """explain_run.py needs the ticker's sector ETF for its market model. A new ticker gets a
    minimal entry in explain_subjects.json."""
    config = json.loads(SUBJECTS_JSON.read_text(encoding="utf-8"))
    if ticker in config:
        return
    if not sector_etf:
        raise SystemExit(f"{ticker} isn't in {SUBJECTS_JSON.name}: give its sector ETF with --sector-etf "
                         "(the equal-weight fund of its GICS sector, e.g. RSPS consumer staples, RSPT technology, "
                         "RSPF financials, RSPH health care; Company_Narrative_Aggregation METHODOLOGY §7)")
    config[ticker] = {"sector_etf": sector_etf.upper()}
    SUBJECTS_JSON.write_text(json.dumps(config, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Added {ticker} to {SUBJECTS_JSON.name} (sector ETF {sector_etf.upper()}).")


def series_complete(series: Path, pull_dir: Path, first: str, last: str) -> tuple[int, int]:
    """(months extracted, months in the pull) for the period."""
    lists = [p for p in pull_dir.glob("news_pull_*.csv") if first <= p.stem[10:17] <= last]
    return sum((series / p.stem / "narrative_units.csv").is_file() for p in lists), len(lists)


def step(number: int, title: str, command: list[str], cwd: Path) -> None:
    print(f"\n{'=' * 78}\nStep {number}: {title}\n  {' '.join(command)}\n{'=' * 78}", flush=True)
    result = subprocess.run([sys.executable, *command], cwd=cwd)
    if result.returncode != 0:
        raise SystemExit(f"\nStep {number} ({title}) stopped (exit code {result.returncode}). Fix the cause and "
                         "rerun the same command: finished months are skipped.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0].strip(),
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--ticker", required=True, help="the company's ticker, e.g. COST")
    parser.add_argument("--search-terms", nargs="*", default=[],
                        help='the headline terms, separated by spaces (a term with a space in quotes), e.g. MSFT Microsoft '
                             'or Costco "Costco Wholesale"; the ticker only if it\'s distinctive. Needed the first '
                             "time; saved in News_Collection/pulls/<ticker>/search_terms.csv")
    parser.add_argument("--start", required=True, help="first month (YYYY-MM) or day (YYYY-MM-DD)")
    parser.add_argument("--end", required=True, help="last month (YYYY-MM) or day (YYYY-MM-DD)")
    parser.add_argument("--name", help='the company name in the subject, "<name> (<TICKER>)" (default: the first '
                                       "search term that isn't the ticker)")
    parser.add_argument("--sector-etf", help="the sector ETF for the market model; needed for a ticker not yet in "
                                             "Company_Narrative_Aggregation/explain_subjects.json")
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"the extraction model (default: {DEFAULT_MODEL})")
    parser.add_argument("--steps", nargs="+", choices=STEPS, default=STEPS, help="the steps to run (default: all)")
    parser.add_argument("--dry-run", action="store_true",
                        help="the free steps, and the paid ones without calling the models")
    parser.add_argument("--yes", action="store_true", help="don't ask before the paid steps")
    args = parser.parse_args()

    ticker = args.ticker.strip().upper()
    start, end = parse_day(args.start), parse_day(args.end, end=True)
    if end < start:
        parser.error("--end is before --start")
    if end > date.today():
        parser.error("--end is in the future")
    first, last = f"{start:%Y-%m}", f"{end:%Y-%m}"
    steps = [s for s in STEPS if s in args.steps]
    subject = f"{subject_name(args, ticker)} ({ticker})"
    pull_dir = NEWS / "pulls" / ticker.lower()
    series = NARRATIVE / "runs" / f"{ticker.lower()}_{first}_{last}"
    paid = {"extract", "explain"} & set(steps) if not args.dry_run else set()
    check_keys([s for s in steps if s in paid or s in ("news", "pvgo")], args.model)
    if "explain" in steps:
        check_sector(ticker, args.sector_etf)
    print(f"{subject}, {first} to {last}: {', '.join(steps)}{' (dry run)' if args.dry_run else ''}")

    if "news" in steps:
        command = ["news_pull.py", "--ticker", ticker, "--start", str(start), "--end", str(end)]
        if args.search_terms:
            command += ["--search-terms", *args.search_terms]
        step(1, "news (free)", command, NEWS)

    if "pvgo" in steps:
        # --days counts back from today. The series starts about 13 months before the period:
        # explain_run.py's market model is fitted on the 180 trading days (about 9 months)
        # before each day, from prices beginning at the series' first day.
        days = (date.today() - start).days + PRE_PERIOD_DAYS
        erp = explanation_erp(start.year, end.year)
        step(2, "PVGO history (free)",
             ["pvgo_history.py", ticker, "--days", str(days), "--own-beta", "--erp", f"{erp}", "--release-items"], PVGO)

    if "extract" in steps:
        command = ["extract_run.py", "--pull-dir", str(pull_dir), "--from", first, "--to", last, "--subject", subject,
                   "--model", args.model]
        command += ["--dry-run"] if args.dry_run else (["--yes"] if args.yes else [])
        step(3, "extract statements" + (" (dry run)" if args.dry_run else " (paid)"), command, NARRATIVE)

    if "explain" in steps:
        done, total = series_complete(series, pull_dir, first, last)
        if total == 0 or done < total:
            message = f"Step 4 (explain) needs every month extracted: {done} of {total} in {series.name}."
            if args.dry_run:  # expected: a dry run extracts nothing
                print(f"\n{message} Run without --dry-run to extract them, then explain.")
                return
            raise SystemExit(f"\n{message} Rerun the same command to extract the rest.")
        command = ["explain_run.py", "--runs", str(series), "--from", first, "--to", last]
        if args.sector_etf:
            command += ["--sector", args.sector_etf.upper()]
        command += ["--dry-run"] if args.dry_run else (["--yes"] if args.yes else [])
        step(4, "explain" + (" (dry run)" if args.dry_run else " (paid)"), command, NARRATIVE)
    print(f"\nDone. The runs are in {series}" if "extract" in steps or "explain" in steps else "\nDone.")


if __name__ == "__main__":
    main()
