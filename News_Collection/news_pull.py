import argparse
import calendar
import csv
import os
import time
from datetime import date
from pathlib import Path

import mediacloud.api
import mediacloud.error
import requests
from dotenv import load_dotenv

HERE = Path(__file__).resolve().parent
# One folder per company, named by its ticker: pulls/<ticker>/search_terms.csv (the headline terms)
# and its monthly pulls. outlets.csv stays shared, so every company is pulled from the same outlets.
PULLS_DIR = HERE / "pulls"
SEARCH_TERMS_CSV = "search_terms.csv"
MAX_QUERY_CHARS = 2000
COLUMNS = ["domain", "mc_story_id", "title", "url", "publish_date", "language", "title_search"]
# Media Cloud rate-limits often (HTTP 429): a failed month is retried after a wait, then reported.
TRIES = 5
RETRY_SECONDS = 60


def read_csv(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def title_queries(terms):
    queries, chunk = [], []
    for term in terms:
        clause = f'article_title:"{term}"'
        if chunk and len("(" + " OR ".join(chunk + [clause]) + ")") > MAX_QUERY_CHARS:
            queries.append("(" + " OR ".join(chunk) + ")")
            chunk = []
        chunk.append(clause)
    queries.append("(" + " OR ".join(chunk) + ")")
    return queries


def fetch(search, query, start, end, source_id):
    stories, token = [], None
    while True:
        page, token = search.story_list(query, start, end, source_ids=[source_id], page_size=1000,
                                        pagination_token=token)
        stories.extend(page)
        if token is None:
            return stories


def parse_day(text, end=False):
    """YYYY-MM-DD, or YYYY-MM for a month's first day (its last day with end=True)."""
    if len(text) == 7:
        year, month = map(int, text.split("-"))
        return date(year, month, calendar.monthrange(year, month)[1] if end else 1)
    return date.fromisoformat(text)


def months(start, end):
    """[(first day, last day)] per calendar month from start to end; the first and last may be partial."""
    out, day = [], start
    while day <= end:
        last = date(day.year, day.month, calendar.monthrange(day.year, day.month)[1])
        out.append((day, min(last, end)))
        day = date(day.year + day.month // 12, day.month % 12 + 1, 1)
    return out


def search_terms(company_dir, given, replace):
    """The headline terms for this company: its search_terms.csv, written on first use from `given`.
    The ticker is searched for only if it's among them: a ticker that's also a common word (COST)
    would match unrelated headlines. Terms that differ from an existing file stop the pull (they would
    change what the earlier months measure) unless `replace`."""
    path = company_dir / SEARCH_TERMS_CSV
    wanted = list(dict.fromkeys(t.strip() for t in given if t.strip()))
    if not path.is_file() and not wanted:
        raise SystemExit(f"No {path}: give the headline terms with --search-terms, e.g. --search-terms Costco 'Costco Wholesale'")
    if path.is_file():
        current = [row["term"].strip() for row in read_csv(path) if row["term"].strip()]
        if not wanted or sorted(current) == sorted(wanted):
            return current
        if not replace:
            raise SystemExit(f"{path} has the terms {current}, not {wanted}. Changing the terms changes what the "
                             "earlier pulls measure: rerun without --search-terms to keep them, or with "
                             "--replace-search-terms to replace them (and re-pull the earlier months with --overwrite).")
    company_dir.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["term"])
        writer.writerows([t] for t in wanted)
    print(f"Search terms {wanted} saved to {path}")
    return wanted


def pull_month(search, outlets, terms, start, end):
    """One period's stories from every outlet: (rows, {domain: count})."""
    rows, counts = [], {}
    for outlet in outlets:
        title_search = outlet["title_search"].strip().lower() == "on"
        queries = title_queries(terms) if title_search else ["*"]
        stories = {}
        for query in queries:
            for story in fetch(search, query, start, end, int(outlet["source_id"])):
                stories.setdefault(story["id"], story)
        counts[outlet["domain"]] = len(stories)
        for story in stories.values():
            rows.append({
                "domain": outlet["domain"],
                "mc_story_id": story["id"],
                "title": story.get("title") or "",
                "url": story.get("url") or "",
                "publish_date": story["publish_date"].isoformat() if story.get("publish_date") else "",
                "language": story.get("language") or "",
                "title_search": "on" if title_search else "off",
            })
    return rows, counts


def pull_with_retries(search, outlets, terms, start, end):
    """pull_month, retried after RETRY_SECONDS on a Media Cloud error (429, empty or 5xx) or a
    connection error; None once TRIES attempts have failed."""
    for attempt in range(1, TRIES + 1):
        try:
            return pull_month(search, outlets, terms, start, end)
        except (mediacloud.error.APIResponseError, requests.RequestException) as exc:
            if attempt == TRIES:
                print(f"  ! failed after {TRIES} tries: {exc}")
                return None
            print(f"  ! {type(exc).__name__} (try {attempt} of {TRIES}); waiting {RETRY_SECONDS} s")
            time.sleep(RETRY_SECONDS)


def main():
    parser = argparse.ArgumentParser(description="Pull the list of articles about one company from Media Cloud, "
                                                 "one CSV per calendar month, into pulls/<ticker>/.")
    parser.add_argument("--ticker", required=True, help="the company's ticker, e.g. COST: names its folder (pulls/cost/)")
    parser.add_argument("--search-terms", nargs="*", default=[],
                        help="the headline terms, separated by spaces, with a term that has a space in quotes: e.g. "
                             "MSFT Microsoft, or Costco \"Costco Wholesale\" (include the ticker only if it's distinctive). "
                             f"Saved in the folder's {SEARCH_TERMS_CSV} on first use; later runs can leave them out")
    parser.add_argument("--start", required=True, help="first day, YYYY-MM-DD (or YYYY-MM for the month's first day)")
    parser.add_argument("--end", required=True, help="last day, YYYY-MM-DD (or YYYY-MM for the month's last day)")
    parser.add_argument("--overwrite", action="store_true", help="re-pull months that already have a file")
    parser.add_argument("--replace-search-terms", action="store_true",
                        help=f"replace an existing {SEARCH_TERMS_CSV} whose terms differ from --search-terms")
    args = parser.parse_args()

    ticker = args.ticker.strip().upper()
    start, end = parse_day(args.start), parse_day(args.end, end=True)
    if end < start:
        parser.error("--end is before --start")
    company_dir = PULLS_DIR / ticker.lower()
    terms = search_terms(company_dir, args.search_terms, args.replace_search_terms)
    load_dotenv(HERE / ".env")
    if not os.environ.get("MEDIACLOUD_API_KEY"):
        raise SystemExit(f"No MEDIACLOUD_API_KEY: copy {HERE / '.env.example'} to .env and fill it in")
    search = mediacloud.api.SearchApi(os.environ["MEDIACLOUD_API_KEY"])
    outlets = read_csv(HERE / "outlets.csv")

    failed = []
    for first, last in months(start, end):
        path = company_dir / f"news_pull_{first}_{last}.csv"
        if path.is_file() and not args.overwrite:
            print(f"{first:%Y-%m}: already pulled ({path.name})")
            continue
        print(f"Collecting articles from {first:%Y-%m}...")
        pulled = pull_with_retries(search, outlets, terms, first, last)
        if pulled is None:
            failed.append(f"{first:%Y-%m}")
            continue
        rows, counts = pulled
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=COLUMNS)
            writer.writeheader()
            writer.writerows(rows)
        print(f"  {len(rows)} stories ({', '.join(f'{d}: {n}' for d, n in counts.items())}) -> {path.name}")
        # One list per month: an earlier pull of the same month over other days is replaced.
        for other in company_dir.glob(f"news_pull_{first:%Y-%m}-*_*.csv"):
            if other != path:
                other.unlink()
                print(f"  replaced {other.name} (the same month, other days)")
    if failed:
        raise SystemExit(f"Not pulled: {', '.join(failed)}. Rerun the same command to pull them; the months "
                         "already pulled are skipped.")
    print(f"Done: {company_dir}")


if __name__ == "__main__":
    main()
