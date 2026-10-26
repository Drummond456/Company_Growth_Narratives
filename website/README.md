# website

A static GitHub Pages showcase of the project's main output, one example page per company:
Costco (COST) in 2024 and Meta Platforms (META) from September 2022 to August 2023. Each is
an interactive version of the
company's PVGO history chart, with a month slider, beside the full text of one explain run's
`explanations.md`. Moving the slider highlights a month on the chart and scrolls to that
month's explanation. Scrolling the text moves the slider.

The layout is built for desktop. The tabs, title, intro and the chart's method note span the
top of the page, with the explain run's own opening below them: everything in
`explanations.md` before the first month, in a collapsed box labelled "How to read this:
method, findings and settings". The run's title (`# Why Costco (COST)'s PVGO share moved: ...`)
gives the page's title its company and months instead. Open, its `###` sections (how each month is split, how each period is explained,
citations, findings and the placebo check, earnings releases, settings) flow into up to three
columns, each section kept whole. From 1100px wide (and 650px tall) the chart and slider are below them on the
left, beside the text; once the top has scrolled away, the chart column sticks at the full
screen height. Below that width, the chart sits above the text, as a sticky block when there's
room.

Each period's cause in the text carries the IDs of the statements it cites (`A0077-S01`), and
each earnings release the press releases behind it (`R2024-03-07`). Clicking an ID opens its
card under the cause: the quote, the article headline and link, outlet, date and topics; for a
press release, its one-time item lines and the filing. The same ID again closes it.

**It is not part of the pipeline.** The site reads only the copies in `data/<page>/`
(`data/cost/`, `data/meta_2022-09_2023-08/`). Re-running any folder, or `main.py`, leaves the
site unchanged until you copy new outputs in by hand.

**The Design Overview tab** (`index.html`, the site's landing page) is the content of
`docs/pitch_flowchart.html` (the flowchart, the two models, the Costco proof of concept, the
trust notes and the data upgrade path), restyled in the site's look, without the pitch's per-model costs (the Costco section
gives the year's total); its styles are the "design overview" section of
`style.css`, and the flowchart's SVG classes carry an `fc-` prefix. A change to the pitch is
copied over by hand: the text as is, and the SVG with `fc-` added to each class.

## Data

Each page's folder holds the same seven files. It's the ticker in lower case (`data/cost/`),
or another name given with `update_data.py --folder` (`data/meta_2022-09_2023-08/`, the
explain run's series name):

| File | Copied from | What the site uses |
|---|---|---|
| `series.csv` | `PVGO_Collection/Outputs_CSV_data/<TICKER>_pvgo_history_ttm_adjusted_series.csv` | the daily close, no-growth value (with its step at each measurement date) and growth share |
| `points.csv` | `PVGO_Collection/Outputs_CSV_data/<TICKER>_pvgo_history_ttm_adjusted_points.csv` | the release dates (dotted lines) and measurement dates (dots) |
| `year_end.csv` | `PVGO_Collection/Outputs_CSV_data/<TICKER>_pvgo_history_ttm_adjusted_year_end.csv` | the year-end growth share (diamonds) |
| `explanations.md` | the explain run's `explanations.md` | the text beside the chart |
| `daily_split.csv` | the explain run's `pvgo_daily.csv` | each day's market and company-specific part of the growth share's change (pp), summed into the bottom panel's lines |
| `periods.csv` | the explain run's `periods.csv` | the divergent and outlier periods, shaded in the bottom panel |
| `evidence.json` | built by `update_data.py` from the refs in the explain run's `explanations.md`, the monthly runs' `narrative_units.csv`, `article_scope.csv` and `articles_manifest.csv`, and PVGO_Collection's `<TICKER>_pvgo_history_release_items.csv` | each cited item's text, article, outlet and date; each cited press release's filing and one-time item lines |

Current copies:
- **`data/cost/`:** the PVGO history on the adjusted TTM EPS (own beta, ERP 4.60%), and
  explain run `cost_2024-01_2024-12/explain_20261025-2151` (44 periods; sector ETF RSPS).
  The evidence has 50 cited refs (32 statements, 1 headline, 11 articles, 6 press
  releases), and all of them resolve. Most periods have no cause, so they carry no refs.
- **`data/meta_2022-09_2023-08/`:** the PVGO history on the adjusted TTM EPS (own beta,
  ERP 5.09%: the January 2022 and 2023 estimates averaged), and explain run
  `meta_2022-09_2023-08/explain_20261026-1208` (90 periods; sector ETF RSPC). The evidence
  has 257 cited refs (231 statements, 2 headlines, 18 articles, 6 press releases), and all
  of them resolve.

The slider's months come from the markdown: each `## March 2024: ...` heading becomes one stop,
and the explained window is shaded on the chart. Any explain run works as is.

**Evidence.** Each period in the markdown is a list item (`- **P07 March 8, 2024 · outlier** ·
…`), and its cause ends with the refs it cites, in brackets (`[A0065, A0064-H]`; a
short id is from the section's month). Each release is a `<div class="release">`, drawn as an
outlined box, whose first line ends with its press releases (`[R2024-05-30, R2023-05-25]`: R
and the release date; the second is the quarter leaving the TTM, when its press release names
items). The site reads each bracket, removes it from the text and shows its refs as chips
under the period or at the foot of the release box. `update_data.py` reads the same brackets to
choose which items to publish, so the page and `evidence.json` can't disagree. Only the
cited items are published.

There are four kinds:
- A **statement** is at most a few verbatim sentences, or a paraphrase, which is marked as
  one.
- A **headline** is the article's headline.
- An **article, headline/intro only**, is a stock or analyst article that the model read as
  headline plus opening. Its text isn't republished; the site shows only its headline and link.
- A **press release** is an earnings release's 8-K: the one-time item lines PVGO_Collection read
  from it, its accession number, and links to the press release and the filing on EDGAR. They
  come from the release items' `filing_url`; a release without it gets a link to EDGAR's
  list of the company's filings instead, where the accession number finds it.

If `evidence.json` is missing, the site works without evidence.

## Updating

1. Refresh the page's folder with the script. It copies the six files above into
   `data/<ticker>/` (or `data/<--folder>/`) and rebuilds its `evidence.json`:

   ```
   python website/update_data.py --explain Company_Narrative_Aggregation/runs/cost_2024-01_2024-12/explain_20261025-2151 \
       --pvgo PVGO_Collection/Outputs_CSV_data --ticker COST --basis ttm_adjusted
   python website/update_data.py --explain Company_Narrative_Aggregation/runs/meta_2022-09_2023-08/explain_20261026-1208 \
       --pvgo PVGO_Collection/Outputs_CSV_data --ticker META --folder meta_2022-09_2023-08 --basis ttm_adjusted
   ```

   It prints the count of each kind of cited item, and any ref it couldn't resolve; the site
   shows an unresolved ref as "not found". Copying the six files by hand still works, but
   `evidence.json` then stays as it was.
2. In `app.js`, update the company's entry in `COMPANIES`: `chartTitle`, and `footnote` if the
   EPS basis, beta or ERP changed. The footnote names the beta range over the chart's window
   (`footnote("0.84 to 1.00", "4.60%")`), so check it against the `beta` column of the
   company's `series.csv` over that window (the explained months and 6 on each side).
   The sector ETF needs no setting: it's read from the run (below). A fund not yet in
   `ETF_NAMES` shows as its ticker alone; add its full name there.
3. Update the "Current copies" lines above.
4. Push to `main`. The workflow (`.github/workflows/pages.yml`) publishes the folder.

**A new company** needs, besides step 1 to make its folder: an entry in `app.js`'s
`COMPANIES`, keyed by the folder's name; a page, a copy of `meta.html` with its own
`<body data-company="...">`, meta description and current tab; and its tab in every page's tab
bar. **Another period for a page** needs only a new folder (`--folder`), its `COMPANIES` entry,
and the page's `data-company` pointed at it.

**The PVGO history files carry no period,** and the ERP is the period's (PVGO_Collection
METHODOLOGY §7). Copy a page's history right after the history run for its own period.

## Preview locally

The page fetches its data, so it needs a server; opening a page as a file won't work.

```
python -m http.server 8000 -d website
```

Then open http://localhost:8000. A month can be linked directly, e.g.
http://localhost:8000/costco.html#2024-07 or http://localhost:8000/meta.html#2022-11.

## How it's built

There is no build step: the pages, `style.css` and `app.js`; `update_data.py` (standard
library only) prepares the data. The site has three pages, and a tab bar at the top of each
links them, in this order: **Design Overview** (`index.html`, the site's landing page),
**Example Output – Meta Platforms (META)** (`meta.html`) and **Example Output – Costco (COST)**
(`costco.html`). The two example pages are the same HTML and share `app.js`; each one's `<body data-company="cost">` picks its
`COMPANIES` entry and its data folder. **The market model's sector ETF** is read from the
run's settings line in `explanations.md` ("market model: S&P 500 + RSPS"), so it always
matches the data: the legend shows it ("Market's part (S&P 500 + RSPS), cumulative"), and the
method note under the title names the fund in full, from `ETF_NAMES` in `app.js`, with the rule
that picks it (Company_Narrative_Aggregation METHODOLOGY §7). The tab bar is repeated in each page's
HTML, so a new page means adding its tab to every page. Three libraries come from
jsDelivr at pinned versions: Plotly (`plotly.js-basic-dist-min` 2.35.2) draws the chart,
`marked` 12.0.2 renders the markdown, and DOMPurify 3.1.6 sanitizes it. The chart is drawn as
panels sharing one date axis:
- the share price and no-growth value in dollars, with PVGO as the band between them;
- the growth share;
- with `daily_split.csv`, the cumulative market and company-specific parts of the growth
  share's change over the explained window (pp), with the divergent and outlier periods
  shaded.

That keeps one scale per panel, where the PNG puts both on twin axes. The chart shows the
explained window and 6 months on each side of it (`CONTEXT_MONTHS` in `app.js`);
`series.csv` holds the whole history and is left as copied. Without
`daily_split.csv` the chart keeps its first two panels.

## Deploying

`.github/workflows/pages.yml` runs on each push to `main` that changes `website/`, and on
demand from the Actions tab. One-time setup: in the repo, go to **Settings → Pages** and set
**Source** to **GitHub Actions**. The site is then served at
`https://drummond456.github.io/Company_Growth_Narratives/`.
