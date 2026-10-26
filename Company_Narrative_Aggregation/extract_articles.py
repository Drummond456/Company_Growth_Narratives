"""Extraction, from the pull to the articles that get a request: the run folder, the
article files and their provenance, the free pre-submit screen and the text
normalisation they share. METHODOLOGY section 2.
"""

import base64
import csv
import glob
import re
import unicodedata
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import extract_fetch
from narrative_common import (
    BATCH_STATE_JSON,
    HEADLINE,
    HERE,
    load_state,
    MAX_PDF_BYTES,
    PDF_SUFFIX,
    read_text_file,
    RUNS_DIR,
    STATEMENTS,
    TEXT_SUFFIXES,
)


def load_articles(input_dir: str) -> list[dict]:
    """One article per supported file, in sorted filename order.

    Sorting makes article ids deterministic for a given folder: the same files always
    get the same A0001, A0002, ... - but adding a file can shift the ids of the ones
    after it, so ids are only stable WITHIN a run. Joining across runs should go on
    article_file or article_url.
    """
    folder = Path(input_dir)
    if not folder.is_dir():
        raise SystemExit(f"Input folder not found: {folder.resolve()}")

    articles = []
    for path in sorted(p for p in folder.iterdir() if p.is_file()):
        suffix = path.suffix.lower()
        title, headline = path.stem, ""
        if path.name.lower().endswith(extract_fetch.HEADLINE_SUFFIX):
            # Checked before the .md rule it would otherwise match: a headline file is
            # the headline (+ byline) of an article whose text isn't used.
            text = read_text_file(path)
            if not text:
                print(f"  ! skipping {path.name}: empty")
                continue
            kind, content = "headline", text
            title = path.name[: -len(extract_fetch.HEADLINE_SUFFIX)]
            headline = headline_of(text)
        elif suffix in TEXT_SUFFIXES:
            text = read_text_file(path)
            if not text:
                print(f"  ! skipping {path.name}: empty")
                continue
            kind, content = "text", text
        elif suffix == PDF_SUFFIX:
            data = path.read_bytes()
            if not data:
                print(f"  ! skipping {path.name}: empty")
                continue
            if len(data) > MAX_PDF_BYTES:
                print(f"  ! skipping {path.name}: {len(data) / 1e6:.1f} MB is over the per-request limit")
                continue
            kind, content = "pdf", base64.standard_b64encode(data).decode("ascii")
        else:
            print(f"  ! skipping {path.name}: unsupported file type")
            continue

        articles.append({
            # custom_id must match ^[a-zA-Z0-9_-]{1,64}$, which this always does
            "article_id": f"A{len(articles) + 1:04d}",
            "filename": path.name,
            "title": title,
            "kind": kind,
            "content": content,
            "headline": headline,  # headline articles only - becomes their unit verbatim
        })
    return articles


def headline_of(text: str) -> str:
    """The headline in a .headline.md file: its '# ' heading, else its first line."""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for line in lines:
        if line.startswith("# "):
            return line[2:].strip()
    return lines[0] if lines else ""


def request_kind(article: dict) -> str:
    """A headline file gets the headline request; any text or PDF gets statements."""
    return HEADLINE if article["kind"] == "headline" else STATEMENTS


# --- Runs, lists, provenance ---------------------------------------------------


def run_name(article_lists: list[str]) -> str:
    """Run folders are named after the list(s): "a" or "a+b". Capped at 40 characters -
    with the period label after it, the folder name's prefix stays within the 60 that
    Windows' 260-character path limit leaves room for, since article filenames go inside."""
    return "+".join(Path(p).stem for p in article_lists)[:40]


def period_label(article_lists: list[str]) -> str:
    """The period(s) the lists cover, for the run folder's name: "2026-09", or
    "2026-08_to_2026-10" for several. With generic list names this is what tells one
    run's folder from another's. Empty if the lists have no dates."""
    periods = set()
    for path in article_lists:
        with open(path, newline="", encoding="utf-8-sig") as f:
            periods.update(extract_fetch.list_row(row)["period"] for row in csv.DictReader(f))
    periods = sorted(p for p in periods if p)
    if not periods:
        return ""
    return periods[0] if len(periods) == 1 else f"{periods[0]}_to_{periods[-1]}"


def subject_slug(subject: str) -> str:
    """A short folder-name tag for the subject: the ticker in parentheses if there is one
    ("Microsoft (MSFT)" -> "msft"), else the name, lowercased and cut to 12 characters."""
    ticker = re.search(r"\(([^)]+)\)", subject)
    return re.sub(r"[^a-z0-9]+", "", (ticker.group(1) if ticker else subject).lower())[:12]


def new_run_dir(name: str, label: str = "") -> Path:
    """runs/<name>_<period label>_<timestamp>. --resume finds it by <name>_*."""
    stamp = datetime.now().strftime("%Y%m%d-%H%M")
    name = f"{name}_{label}" if label else name
    run_dir = RUNS_DIR / f"{name}_{stamp}"
    n = 2
    while run_dir.exists():  # two runs inside the same minute
        run_dir = RUNS_DIR / f"{name}_{stamp}-{n}"
        n += 1
    return run_dir


def merge_article_lists(article_lists: list[str], out_csv: Path) -> None:
    """Concatenate several News_Collection CSVs into one, period by period (each list's
    own order kept within a period)."""
    lists = []
    for path in article_lists:
        with open(path, newline="", encoding="utf-8-sig") as f:
            lists.append((Path(path).stem, [extract_fetch.list_row(row) for row in csv.DictReader(f)]))
    periods = sorted({row.get("period", "") for _, rows in lists for row in rows})
    merged, report = [], []
    for period in periods:
        counts = []
        for name, rows in lists:
            in_period = [r for r in rows if r.get("period", "") == period]
            merged.extend(in_period)
            counts.append(f"{name} {len(in_period)}")
        report.append(f"  {period or '(no period)'}: " + ", ".join(counts))
    fieldnames = list(dict.fromkeys(k for _, rows in lists for row in rows for k in row))
    with open(out_csv, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, quoting=csv.QUOTE_ALL)
        writer.writeheader()
        writer.writerows(merged)
    print(f"Merged {len(lists)} article lists:")
    print("\n".join(report))
    print(f"  -> {len(merged)} article(s) in {out_csv}")


def load_manifest(input_dir: str) -> dict[str, dict]:
    """{article filename: provenance} from the fetch manifest beside the articles folder
    - runs/<run>/articles_manifest.csv for runs/<run>/articles/. Empty for a hand-built
    folder with no manifest. The final URL (after redirects) is preferred, as the one
    that actually loads when reviewing."""
    manifest = Path(input_dir).resolve().parent / extract_fetch.MANIFEST_CSV
    if not manifest.is_file():
        return {}
    with open(manifest, newline="", encoding="utf-8-sig") as f:
        return {
            row["file"]: {
                "url": row.get("final_url") or row.get("url", ""),
                "published": row.get("published", ""),
                "period": row.get("period", ""),
                "source": row.get("source", ""),
            }
            for row in csv.DictReader(f)
            if row.get("file")
        }


def article_record(article: dict, manifest: dict[str, dict]) -> dict:
    """What the state keeps per article: identity, provenance and request kind, so the
    outputs can be written from the state alone - on --resume, too."""
    prov = manifest.get(article["filename"], {})
    url = prov.get("url", "")
    return {
        "filename": article["filename"],
        "title": article["title"],
        "url": url,
        "published": prov.get("published", ""),
        "period": prov.get("period", ""),
        "source": prov.get("source", ""),
        "content_type": "headline" if article["kind"] == "headline" else "full_text",
        "file_kind": article["kind"],  # text / pdf / headline - the verbatim check needs it
        "request_kind": request_kind(article),
        # The unit text of a headline article. Cleaned again here (extract_fetch does it
        # too) so folders fetched before the suffix rule widened get the same text.
        "headline": extract_fetch.strip_site_suffix(article.get("headline", ""), prov.get("source")),
    }


def attach_records(articles: list[dict], input_dir: str) -> dict[str, dict]:
    """{article id: record} for the state."""
    manifest = load_manifest(input_dir)
    return {a["article_id"]: article_record(a, manifest) for a in articles}


def title_slug(filename: str) -> str:
    """The title part of an article filename: '037_2026-10_in-a-tale-of.pdf' ->
    'in-a-tale-of' (extract_fetch names files NNN_<period>_<slug>)."""
    stem = filename[: -len(extract_fetch.HEADLINE_SUFFIX)] if filename.endswith(extract_fetch.HEADLINE_SUFFIX) else Path(filename).stem
    return re.sub(r"^\d+_[^_]*_", "", stem)


# Two article texts sharing at least this share of their 8-word sequences (Jaccard) are
# one piece of journalism carried twice - a wire story on two sites. Another outlet's
# own write-up of the same news shares far less, and is kept.
SAME_TEXT_JACCARD = 0.8
SHINGLE_WORDS = 8


# Stock content: pages about the stock rather than the business - market wraps, stock
# picks, price targets, TV stock pickers, performance and personal-finance pieces, and
# the templates of promotional providers syndicated on Yahoo. Skipped before submitting:
# on the May and June 2025 Walmart pulls they were about half the articles, held no story
# that other articles didn't carry, and leaned optimistic.
# Case-insensitive regular expressions, kept generic (no company names); a pattern that
# could match a news headline ("Walmart sticks with its forecast", "a buy now, pay later
# service") is left out. False keeps every article.
SCREEN_STOCK_CONTENT = True
STOCK_TITLE_RULES = [  # (category, pattern) - matched against the headline
    ("market wrap", r"stocks making the biggest|biggest analyst calls|stock market today|trending tickers|"
                    r"stocks to watch|premarket moves|\bdow (jumps|drops|falls|rises|slides)\b"),
    ("stock pick", r"\bstocks? to (buy|sell)\b|\bbest stocks?\b|\b(stock|shares)( is)? a buy\b|\bis .{0,40}\ba buy\b|"
                   r"\bbetter buy\b|\bshould you buy\b|\bstand pat\b|\bwhere will .{0,60}\bstock be\b|"
                   r"\bthe best (dow |retail )?stock\b"),
    ("price target / rating", r"price target|\boutperform rating|\b(buy|hold|sell) rating\b|\boverweight\b|\bunderweight\b|"
                              r"\b(remains|is) bullish\b|\bbullish or bearish\b|"
                              r"\bstock forecasts?\b|\bprice levels\b|\banalysts? (affirm|think|reboot)\b|"
                              r"\bwhat analysts\b|wall street experts are saying"),
    ("TV stock picker", r"\bcramer\b|\bo.leary\b|\btengler\b"),
    ("performance / personal finance", r"\bif you (had )?invested\b|\binvested \$|\bcrush(es|ing)? the s&p\b|"
                                       r"\btopped the market\b|\bstock (jumped|soared|plunged|sank) \d+%|"
                                       r"\bdividend aristocrats\b|\b(put|call) spread\b"),
]
STOCK_PROVIDER_RULES = [  # (provider, pattern) - matched against the start and end of the text
    ("Insider Monkey", r"we recently published a list of|insider monkey"),
    ("Motley Fool", r"motley fool"),
    ("Zacks", r"\bzacks\b"),
]


def article_headline(article: dict) -> str:
    """The headline: a fetched text's '# ' heading, a headline file's headline, else the
    title slug of the file name (a PDF)."""
    if article["kind"] == "text":
        return headline_of(article["content"])
    if article["kind"] == "headline":
        return article.get("headline", "")
    return title_slug(article["filename"]).replace("-", " ")


def stock_content(article: dict) -> str:
    """The stock-content category an article falls in, or "". Headlines for every kind;
    the provider templates only where the text was fetched."""
    title = article_headline(article).lower()
    for category, pattern in STOCK_TITLE_RULES:
        if re.search(pattern, title):
            return category
    if article["kind"] == "text":
        text = article["content"].lower()
        ends = text[:4000] + " " + text[-2500:]
        for name, pattern in STOCK_PROVIDER_RULES:
            if re.search(pattern, ends):
                return f"{name} template"
    return ""


# Shopping content: pages for shoppers rather than about the business - deal roundups,
# "N items to buy / avoid" listicles, holiday store hours. Skipped before submitting
# (2026-10-14). The 2023-2025 Walmart pulls had 128 such headlines of 1,548, nearly all
# from Yahoo in 2023-24, and they surfaced as a false signal: July 2023's Prime Day and
# July 4 deal roundups rated as pricing news (PRICE -0.43). Patterns were checked against
# all 1,548 headlines; ones that also matched business news were left out ("rollback"
# of a policy, "markdowns", a singular "deal on", "cheaper than" outside a numbered list,
# "Insider Sale:"). False keeps every article.
SCREEN_SHOPPING_CONTENT = True
SHOPPING_TITLE_RULES = [  # (category, pattern) - matched against the headline
    ("deals / sales", r"\bshop the\b|\b(best|top|early|biggest|hottest|killer|last-minute)\b[^.?!]{0,40}\bdeals\b|"
                      r"\bdeals (on|of the day|this week|to shop)\b|\b\d+% off\b|\bon sale\b|"
                      r"\bshop [^.?!]{0,60}\b(deals|savings|sales|discounts)\b|"
                      r"\b(find|score|snag|grab)\b[^.?!]{0,40}\b(deals|discounts|savings)\b"),
    ("shopping list", r"^\d+\+? [^.?!]{0,70}\b(items?|things|buys|products|gifts|meals|deals|brands?)\b|"
                      r"\bwastes? of money\b|\bworth (buying|the money)\b|\bstock up on\b"),
    ("store hours", r"\bwhat'?s open\b|\bwhat stores are open\b|\bopen on (easter|thanksgiving|christmas|new year|"
                    r"labor day|memorial day|july 4|the fourth)|\b(store|holiday) hours\b|\bopen today\b"),
]


def shopping_content(article: dict) -> str:
    """The shopping-content category an article's headline falls in, or ""."""
    title = article_headline(article).lower()
    for category, pattern in SHOPPING_TITLE_RULES:
        if re.search(pattern, title):
            return category
    return ""


def page_key(url: str) -> str:
    """A final URL reduced to the page it names: no scheme, query, fragment or trailing
    slash; host in lower case."""
    parts = urlparse(url)
    return f"{parts.netloc.lower()}{parts.path.rstrip('/')}"


def shingles(text: str) -> set[tuple[str, ...]]:
    words = normalise(text).split()
    return {tuple(words[i:i + SHINGLE_WORDS]) for i in range(max(0, len(words) - SHINGLE_WORDS + 1))}


def screen_articles(articles: list[dict], records: dict[str, dict]) -> list[dict]:
    """Free Python rules applied before anything is submitted. Returns the articles
    that get a request; each skipped one gets records[id]["skip"] = reason, which
    becomes its status in article_scope.csv. Deliberately narrow - each rule matches a
    page type, never a judgment about content:
      - a PDF with the same host and title slug as a text article: the same page twice.
        The text copy is kept, because its quotes can be checked verbatim. Title alone
        would be wrong: different pages of one site can share a generic title;
      - the same final page as an earlier article: different URLs that redirect to one
        page. Yahoo republishes a developing story under new URLs and headlines, all
        redirecting to the latest version (May 2025: the "Stock market today" blog
        under 4 URLs, the Walmart earnings story under 3) - each copy would be paid for again;
      - the same text as an earlier article (SAME_TEXT_JACCARD): one story carried on
        two sites;
      - the same headline from the same outlet: two pages of one story;
      - stock content (SCREEN_STOCK_CONTENT): a headline or provider template matching
        STOCK_TITLE_RULES / STOCK_PROVIDER_RULES - a page type (market wrap, stock pick,
        price target...), not a judgment on what the article says;
      - shopping content (SCREEN_SHOPPING_CONTENT): a headline matching
        SHOPPING_TITLE_RULES - deal roundups, shopping listicles, store hours;
    The same news from different outlets in their own words is kept - coverage is
    signal. So is a sentence two different articles share (a quote both use): only
    whole copies of an article are skipped. The first copy, by article id, is kept.
    """
    texts = {(urlparse(records[a["article_id"]]["url"]).netloc.lower(), title_slug(a["filename"])): a["article_id"]
             for a in articles if a["kind"] == "text" and records[a["article_id"]]["url"]}
    seen_headlines, seen_pages, seen_texts, kept = {}, {}, [], []
    for a in articles:
        record = records[a["article_id"]]
        host = urlparse(record["url"]).netloc.lower()
        page = page_key(record["url"]) if record["url"] else ""
        reason = None
        if a["kind"] == "pdf" and (host, title_slug(a["filename"])) in texts:
            reason = f"PDF copy of {texts[host, title_slug(a['filename'])]}"
        elif page and page in seen_pages:
            reason = f"same page as {seen_pages[page]}"
        elif a["kind"] == "text":
            mine = shingles(a["content"])
            same = next((aid for aid, other in seen_texts
                         if mine and other and len(mine & other) / len(mine | other) >= SAME_TEXT_JACCARD), None)
            if same:
                reason = f"same text as {same}"
            else:
                seen_texts.append((a["article_id"], mine))
        elif a["kind"] == "headline":
            key = (record["source"].strip().lower(), " ".join(record["headline"].lower().split()))
            if key in seen_headlines:
                reason = f"duplicate headline of {seen_headlines[key]}"
            else:
                seen_headlines[key] = a["article_id"]
        if not reason and SCREEN_STOCK_CONTENT:
            category = stock_content(a)
            if category:
                reason = f"stock content: {category}"
        if not reason and SCREEN_SHOPPING_CONTENT:
            category = shopping_content(a)
            if category:
                reason = f"shopping content: {category}"
        if reason:
            record["skip"] = reason
        else:
            kept.append(a)
            if page:
                seen_pages[page] = a["article_id"]
    skipped = [re.sub(r" (of|as) \S+$", "", r["skip"]) for r in records.values() if r.get("skip")]
    if skipped:
        counts = {}
        for reason in skipped:
            counts[reason] = counts.get(reason, 0) + 1
        print(f"Skipped before submitting: {len(skipped)} ({', '.join(f'{k} {v}' for k, v in sorted(counts.items()))})")
    return kept


def provenance_columns(record: dict) -> dict:
    """The provenance columns shared by narrative_units.csv and article_scope.csv."""
    return {
        "article_file": record.get("filename", ""),
        "article_title": record.get("title", ""),
        "article_url": record.get("url", ""),
        "published": record.get("published", ""),
        "period": record.get("period", ""),
        "source": record.get("source", ""),
        "content_type": record.get("content_type", ""),
    }


# --- Verbatim check --------------------------------------------------------------

# Typographic variants mapped to plain ASCII, on both sides, so a quote that differs
# from the page only in quote marks or dashes still matches.
_PLAIN = str.maketrans({
    "\u2018": "'", "\u2019": "'", "\u201a": "'", "\u201b": "'", "\u2032": "'",
    "\u201c": '"', "\u201d": '"', "\u201e": '"', "\u2033": '"',
    "\u2010": "-", "\u2011": "-", "\u2012": "-", "\u2013": "-", "\u2014": "-", "\u2015": "-", "\u2212": "-",
    "\u00a0": " ",
})


def normalise(text: str) -> str:
    """Text reduced to what a verbatim quote must preserve: the words and their order.
    Markdown syntax (the article files are trafilatura Markdown, and the prompt tells
    the model to leave formatting out), whitespace, quote-mark and dash styles, and
    case are all flattened."""
    text = unicodedata.normalize("NFKC", text).translate(_PLAIN)
    # HTML left in the Markdown: footnote markers go with their content ("$630
    # million<sup>1</sup>" - run 1748 flagged a correct quote over one), other tags alone.
    text = re.sub(r"<(sup|sub)\b[^<>]*>.*?</\1>", "", text, flags=re.S | re.I)
    text = re.sub(r"</?[a-zA-Z][^<>]*>", "", text)
    text = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", text)  # [link text](url) -> link text
    text = re.sub(r"\\(.)", r"\1", text)  # markdown escapes: \$ -> $
    text = re.sub(r"[*_`#>|]", "", text)  # emphasis, code, heading, blockquote, table markers
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r" ?- ?", "-", text)  # "a - b" and "a-b" alike
    return text.strip().lower()


def unescape_markdown(text: str) -> str:
    """A quote as a reader should see it: without the Markdown backslash escapes the
    article file carries and the model sometimes copies along - "the \\[U.S.\\]
    government" becomes "the [U.S.] government" (run 1519). Only a backslash before
    Markdown punctuation is removed; the verbatim check ignores these escapes anyway."""
    return re.sub(r"\\([\\`*_{}\[\]()#+\-.!|<>~])", r"\1", text)


# --- CLI -----------------------------------------------------------------------


def resolve_article_list(raw: str) -> str:
    """Accepts a path pasted straight from Explorer's 'Copy as path' (which adds quotes);
    a relative path is tried against the working directory, then against this folder."""
    path = Path(raw.strip().strip('"'))
    if not path.is_absolute() and not path.exists():
        path = HERE / path
    if not path.is_file():
        raise SystemExit(f"Article list not found: {path}")
    return str(path)


def resolve_article_lists(value: str | list[str] | None) -> list[str]:
    """ARTICLE_LIST_CSV / --article-list as a list of resolved paths: one path, several,
    or none (empty string or list = folder mode)."""
    raw = [value] if isinstance(value, str) else list(value or [])
    return [resolve_article_list(r) for r in raw if r and r.strip()]


def latest_uncollected_run(name: str) -> Path | None:
    """Most recent run folder for this list (or combination) whose batch isn't collected."""
    for run_dir in sorted(RUNS_DIR.glob(f"{glob.escape(name)}_*"), reverse=True):
        state = load_state(run_dir / BATCH_STATE_JSON)
        if state and not state.get("collected"):
            return run_dir
    return None
