# Expectation_Narratives — PVGO and economic narratives

The workspace explores the historical PVGO of a company and attempts to explain why a company's PVGO share moves, from the news.

- **`main.py` (root):** one company end to end,
  `python main.py --ticker COST --search-terms Costco "Costco Wholesale" --start 2024-01 --end 2024-12`. It runs
  each folder's own command in turn (news, PVGO history, extract, explain) by subprocess,
  so the folders stay independent and each step also runs on its own.
- **`News_Collection`:** `news_pull.py --ticker <TICKER> [--search-terms ...] --start --end`
  pulls a company's article lists from Media Cloud (CNBC, Yahoo Finance, Fortune; the shared
  `outlets.csv`), one CSV per month, into `pulls/<ticker>/` (e.g. `pulls/cost/`), with its
  `search_terms.csv`.
- **`Company_Narrative_Aggregation`:**
  - `extract_run.py` fetches each month's articles, screens them, and turns them into
    statements tagged with value-driver codes (paid: Qwen3-235B on DeepInfra, real time;
    Sonnet with `--model claude-sonnet-5-5`). One run per month: `--pull-dir pulls/<ticker>`
    makes the series folder `runs/<ticker>_<first>_<last>/` and asks once for the whole
    series.
  - `explain_run.py` is **the main output**. It reads a set of monthly runs and
    PVGO_Collection's daily series, and explains why the growth share moved: each month
    cut into periods labelled by how much the market explains, every period explained,
    and each earnings release (paid batch; METHODOLOGY §7).
  - `extract_reports.py` rebuilds a run's reports for free (e.g. one locked by Excel).
- **`PVGO_Collection`:** growth-share calculations, on the adjusted TTM EPS by default
  (TTM GAAP EPS without the gains and losses on investments, less 25% tax). Raw TTM is kept for comparison, and the trimmed 2-year EPS for Counterpoint
  comparisons.
  `pvgo_history.py` (or the runner `pvgo_history_run.py`) writes the daily series, the
  release points and the press-release reconciliations that `explain_run.py` reads (by the
  sibling path).
- **`website`:** a static GitHub Pages showcase. One page per example company (Costco,
  Meta) shows an interactive PVGO chart with a month slider over one explain run's
  `explanations.md`. It is **not part of the pipeline**:
  it reads only the files in `website/data/<page>/`, refreshed by hand with
  `website/update_data.py` (which also builds the cited-evidence file), and the pipeline never
  writes to it. Its
  `README.md` (not a METHODOLOGY) lists each copy's source and the update steps.
  `.github/workflows/pages.yml` deploys it.

**Each folder documents its own quirks** in its own `METHODOLOGY.md`. Don't force a
common interface across folders.

## Git
**One repo at the project root.** **Folders keep their own `.gitignore`** (caches,
fetched article text); the root `.gitignore` adds global safety rules (`.env`, `.venv/`)
and keeps `CHANGELOG.md` out of the repo.

**The published history is separate.** GitHub's `main` started from a single clean commit;
the local `dev-history` branch keeps the full earlier history and is never pushed.

## Folder conventions
| File/dir | Purpose |
|---|---|
| `*.py` | Modules named by pipeline step (`narrative_common`/`extract_*`/`explain_*`, `pvgo_*`); importable, nothing runs on import. The command files (`main.py` at the root; `news_pull.py`, `extract_run.py`, `extract_reports.py`, `explain_run.py`, `pvgo_growth_share.py`, `pvgo_history.py`, `pvgo_history_run.py`) are listed in each METHODOLOGY. |
| `METHODOLOGY.md` | The most important file per folder (see below). |
| `CHANGELOG.md` (root only) | The project's history: what changed, what was tried, and the tests behind each design choice, newest first, by date and folder. Kept locally and gitignored, so no published file may link to it or cite it. |
| `.gitignore` | Always `__pycache__/`, `*.pyc`; plus `.env` and anything bulky or regenerated. |
| `.env` / `.env.example` | Only where credentials are needed (`Company_Narrative_Aggregation`'s Anthropic and DeepInfra keys, `News_Collection`'s Media Cloud key, `PVGO_Collection`'s SEC user agent). `.env` is never committed; `.env.example` is its committed template, with placeholder values. |

**One environment for the whole project:** `.venv/` at the root
(gitignored), from the root `requirements.txt`, which groups the dependencies by folder.
A new dependency goes in that file under its folder. Scripts find their own files from
their own location, so they run from any working directory.

## What goes in each `METHODOLOGY.md`
It is written for a reader who needs to trust and interpret the output, not just run
the code. Cover:

1. **What this produces:** the exact unit and shape of the output, and whether it's
   comparable across queries and time or only within a batch.
2. **Collection mechanics:** how the source is actually queried (API or library, query
   construction, batching).
3. **Source-specific limits:** whatever is unique to this source.
4. **Reliability:** official API or scraper; known failure modes and how the code
   handles them.
5. **Credentials and cost:** the auth needed, and how it's billed.
6. **Anything else load-bearing** for interpreting the output correctly.

**Current version only.** A METHODOLOGY describes how things work now, their known limits
and how to use them. It holds no history: no "since <date>", no earlier versions, no
alternatives tried, and no test results behind a choice. Those go in the root
`CHANGELOG.md`, under the date and folder. A short reason a choice holds today may stay.
When a change lands, update the METHODOLOGY to the new state, and add the change and its
evidence to the CHANGELOG.

## Changing the pipeline
- **`Company_Narrative_Aggregation` makes paid API calls** (`extract_run.py`,
  `explain_run.py`). Never run a live batch without the
  user's explicit permission. Use `--dry-run` instead (there are no automated tests yet).
- **The pulls feed Narrative directly.** A change to News_Collection's pull settings
  (outlets, query) changes what the runs measure.
- **PVGO_Collection's outputs feed explain_run.** Re-running its history
  regenerates them; a change to its EPS or cost-of-equity method changes the bridge.
