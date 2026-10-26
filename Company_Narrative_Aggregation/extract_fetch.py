"""
Turn a News_Collection results CSV (one row per article URL) into the folder of
article files that extract_run.py reads. A module only - extract_run.py calls
build_article_folder for each run; it has no command line of its own.
(Reads news_pull.py's Media Cloud lists, and an older list format - see list_row.)

For each row the page at `resolved_url` is downloaded and its main text extracted
with trafilatura, which strips navigation, adverts, cookie banners, related-article
rails and comment threads - the boilerplate that would otherwise surface as "themes".
The body is written as Markdown, so headings, lists and tables survive. A URL that
serves a PDF is saved as the .pdf itself; extract_run.py sends those to the model as a
native document.

Outputs:
  - articles/NNN_<period>_<slug>.md   one file per article that yielded usable text.
                                      NNN is the CSV row, so extract_run.py's sorted-
                                      filename ids (A0001, ...) follow CSV order.
  - articles/NNN_<period>_<slug>.headline.md
                                      the headline alone, for an article whose text
                                      couldn't be had (HEADLINE_FALLBACK).
  - articles_manifest.csv             one row per CSV row INCLUDING failures: which
                                      file it became, or why it didn't. Kept outside
                                      the articles folder so extract_run.py doesn't try to
                                      read it as an article. Join to narrative_units.csv
                                      or article_scope.csv on file = article_file.
Manifest status: ok (fetched now), reused (an earlier run's full text for the same URL,
copied, not fetched - reuse_index), headline (text unavailable - headline file written,
reason says why), kept (fetch failed but a full-text NNN_ file for that row was
already there and was left in place), failed (no file - no text and no title).

Files named NNN_* are owned by CSV row NNN, so use one articles folder per source CSV.

What "reliably" can and can't mean here:
  - Paywalled and bot-blocking sites (WSJ, The Economist, AP...) answer 401/403 or
    serve a teaser. Their block pages are never written as articles; the row falls
    back to its headline. To include the full text, save it by hand as
    articles/NNN_<anything>.md using the row's number; reruns keep it (status "kept")
    and it replaces the headline.
  - A 200 response can still be a stub - a teaser above a paywall, a consent wall.
    Anything under MIN_WORDS is treated as unavailable text (so: headline) for that
    reason. Check the word_count column in the manifest for borderline cases.
  - A landing page that only links to a report (e.g. a PDF behind a "Download"
    button) yields the landing page's summary, not the report.
  - Extraction is trafilatura's default balance. favor_precision was tried on a
    74-URL test list and is worse: it emptied two pages and cut another from 1449 words
    to 298. The cost of the default is that some end matter survives - a blog's "Further
    reading" list, a podcast plug - which the theme prompt already tells the model
    to ignore.

Uses the network but no paid API.
"""

import csv
import re
import time
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import requests
import trafilatura
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# --- Input -----------------------------------------------------------------

MANIFEST_CSV = "articles_manifest.csv"

MIN_WORDS = 150  # below this the "article" is almost always a paywall teaser or consent wall

# When an article's text can't be had - blocked (401/403), paywall stub, timeout - keep
# its headline instead of dropping the row: the core financial press (FT, NYT,
# Bloomberg, WSJ, Reuters, AP, Economist) returned NO full text in a 200-article test
# (2026-10-08), so without this they would contribute nothing at all. Saved as
# NNN_<period>_<slug>.headline.md, which extract_run.py reads as a headline-only article.
HEADLINE_FALLBACK = True
HEADLINE_SUFFIX = ".headline.md"
DELAY = 1.0  # seconds between requests - politeness, and fewer bot-detection trips
REQUEST_TIMEOUT = 20

# Tried in order; the next profile is used only when a site refuses (401/403) or stalls.
# The honest tool User-Agent - the one News_Collection sends - goes FIRST: measured on
# a 74-URL test list, two sites answered it in ~1s but silently tarpitted a request
# claiming to be Chrome (a browser User-Agent without a
# browser's TLS fingerprint is a classic bot signal). That cost 22 of 74 articles.
# The browser profile stays as the fallback for sites that reject unknown tools.
HEADER_PROFILES = [
    ("tool", {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) NewsCollector/1.0"}),
    ("browser", {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,application/pdf;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }),
]
RETRY_WITH_NEXT_PROFILE = {401, 403}

MANIFEST_COLUMNS = [
    "file", "row", "period", "title", "source", "published",
    "url", "final_url", "http_status", "kind", "word_count", "status", "reason",
]

# --- Helpers -----------------------------------------------------------------


@dataclass
class FetchResult:
    url: str
    final_url: str = ""
    http_status: int | None = None
    kind: str = ""  # "html" or "pdf"
    title: str = ""  # from the page's own metadata - cleaner than the RSS headline
    text: str = ""  # Markdown body (html only)
    pdf_bytes: bytes = field(default=b"", repr=False)
    word_count: int = 0
    error: str = ""  # empty means usable

    @property
    def ok(self) -> bool:
        return not self.error


def make_session() -> requests.Session:
    """Retries transient failures (429, 5xx, a failed connect) with backoff, honouring
    Retry-After. 401/403/404 are NOT retried - asking again doesn't change the answer.

    Read timeouts are NOT retried either. Some bot-blocking sites accept the
    connection and then never answer; retrying
    those with backoff cost ~94s per URL instead of one REQUEST_TIMEOUT, and a server
    that stonewalled once stonewalls again.
    """
    session = requests.Session()
    retry = Retry(
        total=3,
        read=0,
        backoff_factor=2,  # 0s, 2s, 4s
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET",),
        respect_retry_after_header=True,
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session  # headers are per request - see HEADER_PROFILES


def fetch_article(url: str, session: requests.Session | None = None, min_words: int = MIN_WORDS) -> FetchResult:
    """Download one URL and extract its main text.

    Never raises for a bad page - every failure comes back as FetchResult.error, so one
    blocked site can't stop a batch.
    """
    session = session or make_session()
    result = FetchResult(url=url)

    resp, attempts = None, []
    for name, headers in HEADER_PROFILES:
        try:
            resp = session.get(url, headers=headers, timeout=REQUEST_TIMEOUT, allow_redirects=True)
        except requests.RequestException as exc:
            resp = None
            attempts.append(f"{name}: {exc.__class__.__name__}")
            continue
        if resp.status_code not in RETRY_WITH_NEXT_PROFILE:
            break
        attempts.append(f"{name}: HTTP {resp.status_code}")

    if resp is None:
        result.error = "request failed (" + "; ".join(attempts) + ")"
        return result

    result.final_url, result.http_status = resp.url, resp.status_code
    if resp.status_code != 200:
        # 401/403 are almost always a paywall or bot block; the body is the block page,
        # so extracting from it would produce an "article" about cookies or subscribing.
        result.error = f"HTTP {resp.status_code}"
        return result

    content_type = resp.headers.get("Content-Type", "").lower()
    if "application/pdf" in content_type or resp.content[:5] == b"%PDF-":
        result.kind, result.pdf_bytes = "pdf", resp.content
        return result  # word count unknown without parsing; extract_run.py reads PDFs natively

    result.kind = "html"
    # Bytes, not resp.text: trafilatura detects the encoding from the document itself,
    # where requests falls back to ISO-8859-1 for text/html without a charset and turns
    # curly quotes and dashes into mojibake.
    html_bytes = resp.content
    common = dict(
        url=resp.url,
        output_format="markdown",
        include_comments=False,  # reader comments are not the article
        include_tables=True,
        include_links=False,
    )
    text = trafilatura.extract(html_bytes, **common) or ""
    if count_words(text) < min_words:
        # Default settings lean towards precision; on pages with unusual markup that can
        # discard real paragraphs. One retry leaning towards recall before giving up.
        text = trafilatura.extract(html_bytes, favor_recall=True, **common) or text

    metadata = trafilatura.extract_metadata(html_bytes, default_url=resp.url)
    if metadata and metadata.title:
        result.title = strip_site_suffix(metadata.title.strip(), metadata.sitename)
    result.text = text.strip()
    result.word_count = count_words(result.text)
    if result.word_count < min_words:
        result.error = (
            f"only {result.word_count} words extracted (short page - abstract, event listing, "
            "interactive tool, paywall teaser or consent wall)"
        )
    return result


def count_words(text: str) -> int:
    return len(re.findall(r"\w+", text))


# 40: this folder's name and its run folders (which add the subject) are long, and
# Windows caps a path at 260 characters.
def slugify(text: str, max_len: int = 40) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug[:max_len].rstrip("-") or "article"


def strip_site_suffix(title: str, *site_names: str | None) -> str:
    """Drop trailing ' | Site' / ' - Site' segments - page titles carry one (' | Governor
    of California'), and so does every Google News headline (' - Reuters').

    Repeated, and a segment that only BEGINS with the site name goes too: Google's
    "... | CNN Politics - CNN" loses " - CNN" and then the outlet's own section tag
    " | CNN Politics". A segment that doesn't start with the name stays ("Borrowing for
    a mortgage — or a car", from NPR)."""
    title = title.strip()
    names = [name.strip() for name in site_names if name and name.strip()]
    changed = True
    while changed:
        changed = False
        for sep in (" | ", " - ", " — ", " – "):
            head, found, tail = title.rpartition(sep)
            if found and head and any(tail == name or tail.startswith(name + " ") for name in names):
                title, changed = head.strip(), True
                break
    return title


def render_markdown(title: str, source: str, published: str, body: str) -> str:
    """The title goes in as a heading because extract_run.py passes the whole file to the
    model - it is real context about what the article is. The URL deliberately does
    not: it's in the manifest, and it would only be noise in the prompt."""
    byline = f"*{', '.join(part for part in (source, published) if part)}*\n\n" if (source or published) else ""
    first_line, _, rest = body.partition("\n")
    if first_line.startswith("# "):
        # The extractor kept the page's own headline; use it rather than stack ours on top.
        return f"{first_line}\n\n{byline}{rest.lstrip()}\n"
    return f"# {title}\n\n{byline}{body}\n"


# --- Build the folder ---------------------------------------------------------


def list_row(row: dict) -> dict:
    """An article-list row in the fields this pipeline uses, from either list format: the
    Google-era News_Collection CSVs (resolved_url, source, published, period) or
    news_pull.py's Media Cloud CSVs (url, domain, publish_date - no period, which is
    taken from the publish date's month)."""
    published = row.get("published") or row.get("publish_date") or ""
    period = row.get("period") or (published[:7] if re.fullmatch(r"\d{4}-\d{2}-\d{2}.*", published) else "")
    return {
        **row,
        "resolved_url": row.get("resolved_url") or row.get("url") or "",
        "source": row.get("source") or row.get("domain") or "",
        "title": row.get("title") or "",
        "published": published,
        "period": period,
    }


def reuse_index(runs_dir: str | Path, exclude: str | Path | None = None) -> dict[str, dict]:
    """{url: its manifest row, plus 'path' to the article file} for every full-text article an
    earlier run under runs_dir fetched (status ok, kept or reused, file still there). Where a
    URL was fetched more than once, the newest manifest wins. Headline-only rows aren't
    indexed, so a page that was blocked before is tried again. exclude: a run folder to
    leave out (the one being built)."""
    index = {}
    skip = Path(exclude).resolve() if exclude else None
    for manifest in sorted(Path(runs_dir).rglob(MANIFEST_CSV), key=lambda m: m.stat().st_mtime):
        if skip and manifest.parent.resolve() == skip:
            continue
        with open(manifest, newline="", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                name, url = row.get("file") or "", row.get("url") or ""
                if row.get("status") not in ("ok", "kept", "reused") or not name or not url or name.endswith(HEADLINE_SUFFIX):
                    continue
                path = manifest.parent / "articles" / name
                if path.is_file():
                    index[url] = {**row, "path": path}
    return index


def build_article_folder(
    source_csv: str,
    out_dir: str,
    manifest_path: str = MANIFEST_CSV,
    min_words: int = MIN_WORDS,
    delay: float = DELAY,
    fetch_row: Callable[[dict], bool] | None = None,
    reuse: dict[str, dict] | None = None,
) -> list[dict]:
    """Fetch every row of a News_Collection CSV into out_dir; return the manifest rows.

    reuse: reuse_index's {url: earlier copy}. A row whose URL is in it is copied, not fetched
    (status "reused"), so a re-run of a list costs no fetching and reads the same text.

    fetch_row: a row it returns False for is not fetched at all - it gets its headline
    file straight away. Kept domain-agnostic: the caller decides which rows those are
    (this folder's extract_run.py passes none, so every row is fetched).
    """
    with open(source_csv, newline="", encoding="utf-8-sig") as f:
        rows = [list_row(row) for row in csv.DictReader(f)]
    Path(out_dir).mkdir(parents=True, exist_ok=True)

    session = make_session()
    manifest = []
    for i, row in enumerate(rows, start=1):
        # resolved_url is the publisher's page (list_row fills it from a Media Cloud list's
        # url; in a Google-era list, url is a Google News redirect).
        url = row.get("resolved_url") or ""
        source = row.get("source", "")
        rss_title = strip_site_suffix(row.get("title", ""), source)
        entry = {
            "file": "", "row": i, "period": row.get("period", ""), "title": rss_title,
            "source": source, "published": row.get("published", ""), "url": url,
            "final_url": "", "http_status": "", "kind": "", "word_count": "",
            "status": "failed", "reason": "",
        }

        # Files named NNN_* belong to CSV row NNN.
        existing = sorted(Path(out_dir).glob(f"{i:03d}_*"))
        stem = f"{i:03d}_{entry['period'] or 'undated'}"
        error, headline_only = None, fetch_row is not None and not fetch_row(row)
        reused = False
        if headline_only:
            error = "headline only by design (not fetched)"
        elif not url.startswith("http"):
            error = "no resolved_url in source CSV"
        elif reuse and url in reuse and reuse[url]["path"].is_file():
            old = reuse[url]
            # Read before this row's old files are cleared: the copy may come from this same
            # folder (a series month prepared before), even from the very file being replaced.
            data = old["path"].read_bytes()
            for p in existing:
                p.unlink()
            # The earlier file's name minus its NNN_<period>_ prefix, under this row's number.
            path = Path(out_dir) / f"{stem}_{re.sub(r'^[0-9]{3}_[^_]+_', '', old['path'].name)}"
            path.write_bytes(data)
            entry.update(
                file=path.name, status="reused", title=old.get("title") or rss_title,
                final_url=old.get("final_url", ""), http_status=old.get("http_status", ""),
                kind=old.get("kind", ""), word_count=old.get("word_count", ""),
                reason=f"text from {old['path'].parent.parent.name}",
            )
            reused = True
        else:
            result = fetch_article(url, session=session, min_words=min_words)
            # The page's own title, where there is one: the RSS headline is truncated
            # and, in News_Collection's CSVs, sometimes has mangled punctuation.
            title = strip_site_suffix(result.title, source) or rss_title
            entry.update(
                title=title, final_url=result.final_url, http_status=result.http_status or "",
                kind=result.kind, word_count=result.word_count if result.kind == "html" else "",
            )
            if result.ok:
                # A re-fetch can change the title, and with it the slug - clear the row's
                # old file (a headline included) so the folder never holds the same
                # article twice.
                for old in existing:
                    old.unlink()
                if result.kind == "pdf":
                    path = Path(out_dir) / f"{stem}_{slugify(title)}.pdf"
                    path.write_bytes(result.pdf_bytes)
                else:
                    path = Path(out_dir) / f"{stem}_{slugify(title)}.md"
                    path.write_text(render_markdown(title, source, entry["published"], result.text), encoding="utf-8")
                entry.update(file=path.name, status="ok")
            else:
                error = result.error

        if error:
            full_text = [p for p in existing if not p.name.endswith(HEADLINE_SUFFIX)]
            if full_text and headline_only:
                # By design these rows are headlines only, so an old full-text file for
                # the row doesn't apply - clear it rather than keep it.
                for old in full_text:
                    old.unlink()
                full_text = []
            if full_text:
                # Left alone on failure: either a good copy from an earlier run (a
                # transient block shouldn't destroy it) or text saved by hand for a
                # paywalled article - which is exactly how those get in.
                entry.update(file=full_text[0].name, status="kept", reason=f"{error}; kept existing file")
            elif HEADLINE_FALLBACK and rss_title:
                # The RSS headline, never the fetched page's title: on a blocked fetch
                # that is the block page's ("Access Denied", "Subscribe to read").
                for old in existing:  # an older headline file (or a full text cleared above)
                    old.unlink(missing_ok=True)
                path = Path(out_dir) / f"{stem}_{slugify(rss_title)}{HEADLINE_SUFFIX}"
                path.write_text(render_markdown(rss_title, source, entry["published"], ""), encoding="utf-8")
                entry.update(file=path.name, title=rss_title, kind="headline", status="headline", reason=error)
            else:
                entry["reason"] = error

        mark = {"ok": "ok  ", "reused": "reus", "kept": "kept", "headline": "head"}.get(entry["status"], "FAIL")
        detail = entry["file"] or entry["reason"]
        print(f"  [{mark}] {i:>3}/{len(rows)} {source[:28]:<28} {detail}")
        manifest.append(entry)
        if i < len(rows) and not headline_only and not reused:  # nothing was requested - no need to pause
            time.sleep(delay)

    with open(manifest_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=MANIFEST_COLUMNS, quoting=csv.QUOTE_ALL)
        writer.writeheader()
        writer.writerows(manifest)

    counts = {s: sum(1 for m in manifest if m["status"] == s) for s in ("ok", "reused", "kept", "headline", "failed")}
    print(
        f"\n{len(manifest)} row(s): {counts['ok']} full text fetched, {counts['reused']} reused from earlier runs, "
        f"{counts['kept']} kept from before, "
        f"{counts['headline']} headline-only, {counts['failed']} failed; "
        f"written to {out_dir}/, manifest in {manifest_path}"
    )
    return manifest
