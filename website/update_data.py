"""Refresh the site's static data from the project's outputs. Run by hand; nothing in the
pipeline calls it, so the site only changes when you do.

    python website/update_data.py --explain Company_Narrative_Aggregation/runs/cost_2024-01_2024-12/explain_20261025-2151 \
        --pvgo PVGO_Collection/Outputs_CSV_data --ticker COST --basis ttm_adjusted

Copies the PVGO history CSVs and the run's explanations.md, pvgo_daily.csv (as daily_split.csv)
and periods.csv into website/data/<ticker>/ (e.g. data/cost/; --folder names another, e.g.
data/meta_2022-09_2023-08/ after the explain run's series) under stable names, and writes its
evidence.json: the statements, headlines and articles the explanations
cite, resolved from the monthly runs' narrative_units.csv, article_scope.csv and
articles_manifest.csv, and the press releases the release blocks cite, from PVGO_Collection's
<TICKER>_pvgo_history_release_items.csv (the filing, its link and the one-time item lines).
Only cited items are written, and an article read as headline plus opening gets its headline
and link only (its text isn't redistributed).
"""
import argparse
import csv
import json
import re
import shutil
from datetime import date
from pathlib import Path

SITE = Path(__file__).resolve().parent
ROOT = SITE.parent
DATA = SITE / "data"  # one folder per page, data/<ticker>/ by default: the page's <body data-company> names it
NARRATIVE = ROOT / "Company_Narrative_Aggregation"  # explain_state.json's run paths are relative to it


def resolve(path: str, base: Path = ROOT) -> Path:
    """A path as given (absolute or from the working directory), else relative to base."""
    p = Path(path)
    return p if p.is_absolute() or p.exists() else base / p


def read_csv(path: Path) -> list[dict]:
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


# The refs an explanation cites end its text in explanations.md: "[A0065, A0064-H, A0061-H]", a short id
# being from its section's month; a release block's head line ends with the press releases it cites,
# "[R2024-05-30, R2023-05-25]" (R and the release date). app.js reads them the same way.
REF = r"(?:(?:\d{4}-\d{2}/)?A\d+(?:-[A-Z]+\d*)?|R\d{4}-\d{2}-\d{2})"
REFS_AT_END = re.compile(rf"\[({REF}(?:, {REF})*)\]\s*$")
MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
          "November", "December"]


def heading_month(line: str) -> str:
    """'## March 2024: ...' (or the older '## 2024-03: ...') -> '2024-03'; '' for any other line."""
    if m := re.match(r"## (\d{4}-\d{2}):", line):
        return m.group(1)
    if (m := re.match(r"## ([A-Z][a-z]+) (\d{4}):", line)) and m.group(1) in MONTHS:
        return f"{m.group(2)}-{MONTHS.index(m.group(1)) + 1:02d}"
    return ""


def md_refs(md: str) -> set[str]:
    """Every ref explanations.md cites: 'YYYY-MM/<id>' for the news, 'R<date>' for a press release."""
    cited, month = set(), ""
    for line in md.splitlines():
        month = heading_month(line) or month
        if month and (found := REFS_AT_END.search(line)):
            cited |= {r if "/" in r or r.startswith("R") else f"{month}/{r}" for r in found.group(1).split(", ")}
    return cited


def filing_item(row: dict, ticker: str) -> dict:
    """A press release as the site shows it: the filing, links to it (its EDGAR index page and its
    first exhibit, the press release, when PVGO_Collection wrote the index URL; else EDGAR's list
    of the company's filings of that form up to a week after it), and the one-time item lines."""
    exhibits = [e.split(" ", 1) for e in (row.get("exhibits") or "").split("; ") if " " in e]
    index = row.get("filing_url") or ""
    folder = index.rsplit("/", 1)[0] + "/" if index else ""
    after = date.fromisoformat(row["release_date"]).toordinal() + 7
    return {"kind": "filing", "form": row.get("release_form") or "", "accession": row.get("accession") or "",
            "release_date": row["release_date"], "quarter_end": row["quarter_end"],
            "index_url": index,
            "doc_url": folder + exhibits[0][1] if folder and exhibits else "",
            "doc_name": exhibits[0][0] if exhibits else "",
            "search_url": "" if index else
            ("https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&owner=include&count=40"
             f"&CIK={ticker}&type={row.get('release_form') or '8-K'}"
             f"&dateb={date.fromordinal(after).strftime('%Y%m%d')}"),
            "lines": [x for k in ("item_sentences", "item_dollar_sentences")
                      for x in (row.get(k) or "").splitlines() if x.strip()],
            "reconciliation": row.get("reconciliation_text") or "", "note": row.get("note") or ""}


def copy_inputs(explain: Path, pvgo: Path, ticker: str, basis: str, out: Path) -> None:
    pairs = [(pvgo / f"{ticker}_pvgo_history_{basis}_{part}.csv", out / f"{name}.csv")
             for part, name in (("series", "series"), ("points", "points"), ("year_end", "year_end"))]
    pairs += [(explain / "explanations.md", out / "explanations.md"),
              (explain / "pvgo_daily.csv", out / "daily_split.csv"),  # the bottom panel's market / company split
              (explain / "periods.csv", out / "periods.csv")]  # its shaded divergent and outlier periods
    for src, dst in pairs:
        if not src.is_file():
            raise SystemExit(f"Missing: {src}")
        shutil.copyfile(src, dst)
        print(f"copied {src.relative_to(ROOT) if src.is_relative_to(ROOT) else src} -> {dst.relative_to(ROOT)}")


def load_news(runs: list[Path]) -> tuple[dict, dict, dict]:
    """({period/unit_id: unit row}, {period/article_id: scope row}, {article_file: manifest row})."""
    units, scope, manifest = {}, {}, {}
    for run in runs:
        for u in read_csv(run / "narrative_units.csv"):
            units[f"{u.get('period') or u['published'][:7]}/{u['unit_id']}"] = u
        for s in read_csv(run / "article_scope.csv"):
            scope[f"{s.get('period') or s['published'][:7]}/{s['article_id']}"] = s
        for m in read_csv(run / "articles_manifest.csv"):
            manifest[m["file"]] = m
    return units, scope, manifest


def build_evidence(explain: Path, pvgo: Path, ticker: str) -> dict:
    state = json.loads((explain / "explain_state.json").read_text(encoding="utf-8"))
    runs = [resolve(r, NARRATIVE) for r in state["runs"]]
    units, scope, manifest = load_news(runs)

    cited = sorted(md_refs((explain / "explanations.md").read_text(encoding="utf-8")))
    releases_csv = pvgo / f"{ticker}_pvgo_history_release_items.csv"
    releases = {r["release_date"]: r for r in read_csv(releases_csv)} if releases_csv.is_file() else {}

    items, articles, missing = {}, {}, []

    def article(key: str, row: dict) -> str:
        m = manifest.get(row["article_file"], {})
        articles[key] = {"title": m.get("title") or row["article_title"], "url": row["article_url"] or m.get("url", ""),
                         "source": row["source"], "published": row["published"][:10]}
        return key

    for ref in cited:
        period = ref.split("/")[0]
        if ref.startswith("R") and ref[1:] in releases:
            items[ref] = filing_item(releases[ref[1:]], ticker)
        elif ref in units:
            u = units[ref]
            items[ref] = {"kind": "headline" if u["unit_id"].endswith("-H") else "statement",
                          "text": " ".join(u["text"].split()), "verbatim": u["verbatim"].strip().upper() == "TRUE",
                          "topics": u.get("topic_names", ""), "article": article(f"{period}/{u['article_id']}", u)}
        elif ref in scope:
            items[ref] = {"kind": "article", "article": article(ref, scope[ref])}
        else:
            missing.append(ref)

    kinds = {k: sum(i["kind"] == k for i in items.values()) for k in ("statement", "headline", "article", "filing")}
    print(f"evidence: {len(cited)} cited refs ({', '.join(f'{n} {k}s' for k, n in kinds.items())}), "
          f"{len(articles)} articles, {len(missing)} unresolved" + (f": {', '.join(missing)}" if missing else ""))
    return {"source": {"explain_run": explain.relative_to(ROOT).as_posix() if explain.is_relative_to(ROOT) else str(explain),
                       "built": date.today().isoformat()},
            "items": items, "articles": articles}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--explain", required=True, help="the explain run folder (explain_<time>)")
    ap.add_argument("--pvgo", required=True, help="PVGO_Collection's Outputs_CSV_data folder")
    ap.add_argument("--ticker", required=True)
    ap.add_argument("--basis", default="ttm_adjusted", help="the EPS basis in the history file names")
    ap.add_argument("--folder", help="the page's folder under data/ (default: the ticker in lower case)")
    a = ap.parse_args()
    explain, pvgo = resolve(a.explain), resolve(a.pvgo)
    folder = DATA / (a.folder or a.ticker.lower())
    folder.mkdir(parents=True, exist_ok=True)
    copy_inputs(explain, pvgo, a.ticker.upper(), a.basis, folder)
    out = folder / "evidence.json"
    out.write_text(json.dumps(build_evidence(explain, pvgo, a.ticker.upper()), ensure_ascii=False, indent=1) + "\n",
                   encoding="utf-8")
    print(f"wrote {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
