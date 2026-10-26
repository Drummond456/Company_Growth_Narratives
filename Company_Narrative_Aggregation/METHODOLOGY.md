# Company_Narrative_Aggregation — methodology

The narrative pipeline for **one company or stock** over a period, in two stages:
- **`extract_run.py`**, one run per month: a month's article list goes in, and short
  verbatim statements about the company, tagged with value-driver codes, come out (§1–§2).
- **`explain_run.py`**: it reads a series of monthly runs and PVGO_Collection's daily
  series, and explains why the growth share moved (§7). This is the main output.

The root `main.py` runs both stages for a company and period (steps 3 and 4), after the
news pull and the PVGO history. The commands for each stage on its own are in
[commands.txt](commands.txt).

## Where each step lives

The modules are named by the step they cover (flat, no package). Run the command files
from this folder.

| Module | Step |
|---|---|
| `narrative_common` | What both stages share: the settings, file helpers, the model calls and their cost (Claude batches, DeepInfra real time), the codebook. |
| `extract_fetch` | Fetch each article's full text, or reuse a copy an earlier run fetched. |
| `extract_articles` | From the pull to the articles that get a request: the run folder, the article files and their provenance, the pre-submit screen, and the text normalisation they share. |
| `extract_requests` | What the model is asked: the answer formats, the prompts and their fingerprint, the sentence ids, the request bodies and the cost estimate. |
| `extract_collect` | Answers to units: the verbatim check, the scope and code checks, and the unit rows. |
| `extract_reports` | Units to output files: the rejected split, `code_matrix.csv` and `run_funnel.csv`, plus the command that rebuilds them (`python extract_reports.py runs/<run>`). |
| `extract_run` | The command for a series of monthly runs (`--pull-dir`) or one run: prepare, submit, finish and `main`. |
| `explain_detect` | The explanation's settings, its state file, its inputs (the runs, the PVGO series, market prices), and step 1: the daily bridge, the periods and their labels, the months and the release bridge. |
| `explain_requests` | Step 2, building the batch: the answer formats, which news each call sees, the requests and the cost estimate; and step 3's request. |
| `explain_results` | Step 2, collecting: the answers, the text checks, merging into an existing run, and the readable outputs. |
| `explain_run` | The command for the explanation: prepare, submit, update, `--ask` and `main`. |
| `prompts/` | The explanation's system prompts, one per call: `explain_told.txt`, `explain_release.txt` and `explain_ask.txt` (`--ask`). The extraction prompts are built in `extract_requests`, since they're rendered from the codebook and the subject. |
| `company_codebook.csv` | The value-driver codebook (§2). |
| `explain_subjects.json` | Per ticker: the sector ETF of the market model (§7). |

## 1. What this produces

**`extract_run.py --pull-dir` → `runs/<ticker>_<first month>_<last month>/`,** a series
folder with one run per monthly list, each named after its list:
`runs/cost_2024-01_2024-12/news_pull_2024-01-01_2024-01-31/`. That's the folder
`explain_run.py --runs` reads. (A single list, `--article-list`, gets its own
`runs/<list>_<period>_<subject>_<time>/` instead.)

Each run's output, `narrative_units.csv`, has one row per unit:
- a **statement** (`A0001-S01`): one sentence, or two consecutive ones, copied verbatim
  from an article's full text. They're the sentences the model would use to summarize the
  article's news about the subject in at most 3 bullet points (§2);
- a **headline** (`A0002-H`): where the text couldn't be fetched.

Of note in the columns:
- `subject`, e.g. `Costco (COST)`;
- `topic_codes` and `topic_names`: the codebook codes the unit fits;
- `verbatim`: the verbatim check (§4);
- `model` and `prompt_version`: which model and which exact prompts made the unit.

The rest of the run folder:
- `articles_manifest.csv`: per URL, the file it became, or why the fetch failed;
- `article_scope.csv`: per article, its status (fit, no fit, skipped and why, or failed),
  its units, and on DeepInfra runs the `developments` the model listed;
- `narrative_units_rejected.csv`: the units the codebook's `exclude` column keeps out of
  the output (§2), with the code(s) that excluded them;
- `code_matrix.csv`: the same units read by code, a column pair (unit id, text) per code;
- `run_funnel.csv`: one `count` per stage, from the articles in the pull (full text,
  headline only, no file) through skipped, sent, fit and rejected, to the statements and
  headlines kept;
- `realtime_results.jsonl`: the model's answers, on DeepInfra runs;
- **gitignored:** `articles/` (the fetched texts: publishers' text), `batch_state.json`
  (for `--resume`) and `realtime_requests.jsonl` (the DeepInfra requests, which carry each
  article's full text).

`extract_reports.py` rebuilds `code_matrix.csv` and `run_funnel.csv` for free, e.g. after
one was locked by Excel.

**`explain_run.py` → `<runs>/explain_<time>/`:**
- **`explanations.md`:**
  - an opening in six `###` sections:
    - *How each month is split:* the bridge and the period labels;
    - *How each period is explained:* the period call;
    - *Citations:* how to read the refs;
    - *Findings and the placebo check:* the number of periods, months and releases; a table
      per label (market-driven, within noise, divergent, outlier) with the periods, how many
      got a cause with medium or high confidence, and every answer (by confidence, "no cause
      found", "no news collected" or "failed"); and **the placebo check,** how often the
      period call found a cause (medium or high confidence) in market-driven or within-noise
      periods, against divergent or outlier ones (§7);
    - *Earnings releases:* the release blocks, a note on levels, and a table of the releases,
      each one's growth-share effect of the EPS update (pp, with the price held still) and
      its company-specific stock return from the release to the measurement day (%);
    - *Settings:* the EPS basis, the beta and ERP behind the cost of equity, the market
      model's sector ETF, and the extraction and explanation models;
  - per month (headed "March 2024"), the growth share's start → end, then **the bridge as a
    table** (Part | pp)
    that adds up (to ±0.01pp of rounding): the market, the company-specific part, each
    release's EPS update, the 10-year Treasury, the beta re-estimate, and the ERP when it
    moves;
  - then **the month's timeline,** one list item per period in date order:
    - its dates and label;
    - the stock, S&P and sector returns;
    - the market and company-specific parts in pp, the market's share and the
      company-specific move against normal noise;
    - its big market days;
    - the period call's confidence (high, medium, low), or "no cause found", "no news
      collected" or "failed", with how many statements and articles it read;
    - the cause. It's marked "suspect" in a market-driven or within-noise period.
      Confidence "none" is the call's own "no cause", shown as "no cause found" with any
      reason it gave.
  - each release's block, an outlined box (`<div class="release">`) after the period
    holding its measurement day, headed by its date, its quarter, the periods it falls in
    and the press releases it cites, then in three parts:
    - *TTM EPS change:* the step with EPS before → after and, on TTM, the two quarters
      behind it ("+$0.42 (16.14 -> 16.56): the quarter ended September 1, 2024 ($5.28)
      replaces the one ended September 3, 2023 ($4.86)", with any adjustment or
      restatement), and its growth-share effect in pp with the price held still;
    - *One-time items identified* (only when the press releases name any): each item,
      entering or leaving the TTM, with its amount per share and its effect on the step,
      then the TTM EPS change less them, and any amount not found in the press-release
      text. An item stated in dollars only shows its amount as stated and the per-share
      figure code made of it, marked "estimated" (§7), and so is the change less them;
    - *Market reaction:* "results surprise" or "results expected" (§7), with the
      company-specific stock return from the release to the measurement day, by day, and
      its size against normal noise;
  - the text checks: generated dates outside the run's years (§7).

  Dates are written out ("March 8, 2024", a range "March 1–7, 2024"), the model's own dates
  in its answers too; refs keep their form.

  Confidence levels are the model's own and untested. The labels and the placebo check are
  computed. **Each cause ends with the refs it cites,** in brackets
  (`[A0065, A0064-H, A0061-H]`: `-S01` a statement, `-H` a headline, a bare id an analyst
  article read as headline plus opening). The `YYYY-MM/` is dropped when the ref is from the
  section's month. A period with no cause still shows what its period call cited. **A release
  block's head line ends with the press releases it cites,** `[R2024-05-30, R2023-05-25]`
  (R and the release date): its own, when PVGO_Collection read its filing, and the quarter
  leaving the TTM's, when that press release names items. The website reads the refs from
  these brackets, and resolves the press releases from PVGO_Collection's release items.
- **`periods.csv`, `releases.csv`, `pvgo_daily.csv` (with each day's `period_id`),
  `pvgo_months.csv`:** the same as tables. `market_prices.csv` caches the S&P 500 and
  sector-ETF closes. `explain_state.json` holds the settings, the requests' references, the
  answers and the cost.
- **`ask_<from>_<to>.md`:** the answer for any period, on demand (`--ask`).
- **Timestamps:** the `explain_<time>` folder name is local time. The state's times and the
  header's "collected" are UTC, so they can fall on the day after the folder name's date.

**Comparability:**
- **Compare runs with the same `prompt_version`.** It fingerprints the prompts, which
  include the subject and the codebook, and differ by model family (§2). So runs of
  different companies, or by Qwen and by Claude, aren't comparable.
- **Full-text articles carry more weight:** one gives up to 3 statements
  (`MAX_STATEMENTS`), a headline gives 1.

## 2. Collection mechanics

**Running a series** (`--pull-dir ../News_Collection/pulls/cost --subject "Costco (COST)"`,
with optional `--from`/`--to` months):
- **One run per monthly list** (`news_pull_<start>_<end>.csv`), into the series folder
  (§1). A month with more than one list stops the run.
- **Everything is prepared first:** each month's articles are fetched and screened and its
  requests built. Then one table shows the estimated cost per month and in total, and the
  whole series is confirmed **once**. `--dry-run` stops at the table; `--yes` skips the
  question.
- **Then each month is submitted and collected** in turn.
- **Rerunning the same command continues the series:**
  - a month with a collected run is skipped;
  - a month submitted but not collected is finished, without asking again;
  - the rest are prepared, reusing the text already in their folders (e.g. after a dry
    run).
- **A collected month made with another `prompt_version`** is flagged, since the series
  would mix prompts. Delete the month's folder to redo it.

**Article lists.** `news_pull.py`'s Media Cloud CSVs (`url`, `domain`, `publish_date`).
`extract_fetch.list_row` maps them to the run's fields, and `period` is the publish date's
month. `--input-dir` runs on a folder of hand-built article files instead.

**Full text for every article** (`extract_fetch.py`).
- **The requests:** one per URL, 1 s apart (politeness), with a 20 s timeout. An honest tool
  User-Agent (`NewsCollector/1.0`) goes first. A browser profile is tried only when a site
  refuses (401/403) or the request fails, since some sites tarpit requests that claim to be
  a browser.
- **The extraction:** trafilatura, to markdown, without reader comments or links. When it
  gives under 150 words, one retry favours recall. A PDF is kept as a PDF.
- **A page that's blocked** (401/403), times out, or yields under 150 words falls back to
  its headline. Every failure is recorded in `articles_manifest.csv`.
- **Text already fetched is reused.** Before fetching, `extract_run.py` indexes every
  earlier run's `articles_manifest.csv` under `runs/` by URL (`extract_fetch.reuse_index`).
  - A URL an earlier run fetched in full is copied, and shows as `reused`. Where it was
    fetched more than once, the newest copy is used.
  - Headline-only rows are fetched again, since a page blocked before may load now.
  - `--refetch` fetches every row afresh, e.g. to pick up a page that has changed.
- **Article filenames use a 40-character slug,** since Windows caps a path at 260
  characters.

**The pre-submit screen** (`screen_articles`, free) skips articles before any request is
paid for. Each skip shows in `article_scope.csv` with its reason.
- **Duplicates:** an article that lands on the same final page as an earlier one, has the
  same text (`SAME_TEXT_JACCARD` = 0.8 of 8-word sequences shared), or, for headline-only
  articles, the same headline from the same outlet. A PDF with the same host and title as a
  text article is skipped too, since the text copy's quotes can be checked verbatim. The
  first copy is kept; the rest show as "same page as …", "same text as …", "duplicate
  headline of …" or "PDF copy of …". Yahoo republishes a developing story under new URLs,
  all redirecting to its latest version.
  - **What still counts:** a sentence two different articles share, such as a CEO quote,
    counts in each, since each is an editorial choice to amplify it. The same news told by
    another outlet in its own words counts too.
- **Stock content** (`SCREEN_STOCK_CONTENT`): pages about the stock rather than the
  business, shown as "skipped: stock content: <category>".
  - **By headline (`STOCK_TITLE_RULES`):** market wraps and movers, stock picks ("Is … a
    buy", "best stocks to buy"), price targets and ratings, TV stock pickers (Cramer), and
    performance and personal-finance pieces ("If you invested $1,000", "Why … stock jumped
    11%").
  - **By provider template in the text (`STOCK_PROVIDER_RULES`):** Insider Monkey, Motley
    Fool, Zacks.
  - The period calls of `explain_run.py` still read these articles' openings, as analyst
    evidence (§7).
- **Shopping content** (`SCREEN_SHOPPING_CONTENT`, headline only): deal and sale roundups
  ("…shop 90+ deals", "50% off"), numbered shopping listicles ("8 Pantry Items To Buy at
  Costco", "5 Costco Clothing Items That Are a Waste of Money"), and holiday store hours ("What's
  open on Easter?"). Shown as "skipped: shopping content: <category>".
- **The rules** are case-insensitive regular expressions with no company names. Patterns
  that also match business news ("sticks with its forecast", "a buy now, pay later
  service", "rollback", "markdowns") are left out.

**The model and provider.** The provider follows the model id.
- **Default: `Qwen/Qwen3-235B-A22B-Instruct-2507` on DeepInfra** (`MODEL` in
  `narrative_common.py`), real time, `DEEPINFRA_WORKERS` (8) requests at a time. A month
  takes minutes.
  - **Retries:** 429s, 5xx errors and connection errors are retried up to 4 times. A
    request that still fails shows as errored in `article_scope.csv`, and a rejected key
    stops the run.
  - **The timeout:** `DEEPINFRA_TIMEOUT` = 90 s per call.
  - **Resuming:** the requests are saved in `realtime_requests.jsonl`, and each answer is
    appended to `realtime_results.jsonl` as it arrives. `--resume` sends only the requests
    without an answer, so nothing is paid twice.
  - **The context:** 262,144 tokens, with `DEEPINFRA_MAX_TOKENS` = 2,048 for the answer.
    A request estimated not to fit is warned about before submitting.
- **A `claude-` id** (e.g. `--model claude-sonnet-5-5`) runs on Claude's Message Batches
  API, with the system prompt cached.

**The prompt: a summary of at most 3 statements.** The statements prompt
(`build_statements_prompt`) asks for the sentences the model "would choose if you had to
summarize its news about <subject> in at most three bullet points, each bullet a sentence
copied from the article".
- **Each bullet covers a different development,** stated by "the sentence that states it
  most plainly, usually the reporter's own words rather than a quote".
- **Two sentences are allowed** when the first doesn't say on its own who or what it's
  about.
- **Each bullet must fit a topic** in the codebook, and is tagged with its codes. If
  nothing fits, the answer is an empty list.
- **The ceiling** is `MAX_STATEMENTS` = 3 (`--max-statements`). Articles with less news give
  fewer.
- **`--subject` (required)** names the company every unit must be about, and is written into
  the prompt. The scope rules say:
  - a unit fits a topic when it makes a claim, reports news or data, gives a forecast, or
    describes an action "about that part of <subject>'s business, stock or situation";
  - nothing fits when a unit only announces an event, a publication or an appointment, or
    only names the subject among other companies or stocks.
- **Prompt changes need testing.** A single sentence measurably changes which statements
  are picked. Change one thing at a time, and compare a test month against the run before.

**What DeepInfra models get differently** (switches in `extract_requests.py`, each part of
`prompt_version`):
- **The codebook as a numbered list** (`NUMBERED_CODEBOOK_FOR_DEEPINFRA`): each code is an
  entry ("1. TAM (Total accessible market)") with one line per field. Both layouts are
  rendered from `company_codebook.csv`.
- **Sentence ids instead of copied quotes** (`SENTENCE_IDS_FOR_DEEPINFRA`).
  - **How it works:** the article's sentences are numbered `[S1]`, `[S2]`, … in the request,
    and each bullet gives one number, or two consecutive ones. The quote is rebuilt from the
    article at collection, so it's verbatim by construction.
  - **The split** (`split_sentences`) is rule-based and deterministic, and runs on the same
    article file at both ends. Each line is a paragraph. Headings, the italic source line,
    all-bold subheads, tables, images and lines without letters are shown but not numbered.
    Common abbreviations (U.S., Inc., Corp., …) and single initials don't end a sentence.
  - **Bad numbers:** a bullet with more than two numbers, or two that aren't consecutive,
    keeps its first sentence, with a warning. A first number out of range drops the bullet
    (counted in `n_dropped`).
  - **The unit's text** has the article's Markdown emphasis, links and escapes removed.
- **Developments first** (`DEVELOPMENTS_FOR_DEEPINFRA`): the answer first lists the
  article's distinct developments about the subject (at most 3, most important first), then
  one bullet per development. The list is kept in `article_scope.csv`'s `developments`
  column for auditing, and doesn't affect the units.
- **No PROMO** (`QUALIFIERS_FOR_DEEPINFRA = False`): the qualifier family is left out of the
  prompt and schema; a PROMO given anyway is dropped as an unknown code. The pre-submit
  screen still skips stock-pick pages, and STOCK-only statements are still rejected.
- **The schema is sent as `response_format` `json_schema`, strict.** Codes outside the
  codebook are still dropped, with a warning (`codebook_codes`), since DeepInfra may not
  enforce the enum.
- **Also:** no thinking, no prompt caching, and PDFs are skipped ("PDF (the model reads text
  only)"). `as_batch_result` turns each answer into the shape a Claude result has, so every
  check after collection is the same.

**The codebook: `company_codebook.csv` (v4),** built on Damodaran's "Value Drivers for a
Company": the families are his drivers and the topics his sub-categories.

| Family (value driver) | Topics |
|---|---|
| Revenue growth | TAM total accessible market; SHARE market share; REV revenue & volume (not attributed), the residual when an article doesn't say whether the change comes from the market or from share |
| Operating margins | PRICE pricing power; COST cost efficiencies |
| Investment efficiency | INVEST investment needed to deliver growth |
| Cost of equity | EQUITY return equity investors demand |
| Cost of debt | DEBT borrowing cost, net of taxes |
| Failure risk | FAIL catastrophic event threatening the business model |
| Market reaction (not a value driver) | STOCK share price & analyst views |
| Qualifier | PROMO promotional or stock-pick content |
| Meta | OTHER |

- **Columns:** `code`, `family`, `topic`, `definition`, `includes`, `route_elsewhere`,
  `exclude` and `search_terms`. Each topic's example terms are both its `includes` cues and
  its `search_terms`; the model never sees `search_terms`.
- **The `exclude` column:**
  - **`scope`:** left out of the prompts and the schema (OTHER);
  - **`output`:** units go to `narrative_units_rejected.csv` (PROMO);
  - **`alone`:** a unit goes to the rejected file only when this is its only code. STOCK
    alone (a bare share-price move or analyst rating) is rejected; STOCK plus a value driver
    (a sales beat and the share drop it caused) is kept;
  - **blank:** a normal code.
- **PROMO is a qualifier:** it only goes alongside a topic, so a rejected unit still shows
  what it was about.
- **What fits nothing:** leadership news, and legal news short of a failure risk, unless
  they state an effect on a driver.
- **Editing the codebook changes the prompts,** and so `prompt_version`.

**After collection:** each unit's codes are checked against the codebook, statements under
5 words are dropped as filler, units with an `output` or `alone` exclusion go to the
rejected file, and the verbatim check runs (§4).

`SCREEN_STOCK_CONTENT` and `SCREEN_SHOPPING_CONTENT` (in `extract_articles.py`) can be set
to `False` to see what the screens remove.

**Known limits of the selection:**
- **The ceiling can cost a fourth point** in in-depth articles.
- **About 1 pick in 10 doesn't name its subject** ("The company stuck by its full-year
  forecast…"). In an article that also covers a rival, "the company" could be the rival.
- **The two-sentence clause reads backwards:** the context a sentence lacks is usually in
  the sentence before, but the clause allows the sentence after.
- **A sentence the source page breaks across paragraphs** (seen in an earnings-call
  transcript) stays two sentences.
- **Recaps leak into later months.** Analysis pieces repeat older news ("the company warned
  in May…" in a July piece), and those statements count in the month they were published.

## 3. Source-specific limits

- **Syndicated and promotional content:** Yahoo Finance carries stock-promotion pieces (e.g.
  Insider Monkey, Motley Fool). Most are skipped by the stock-content screen. Their endings
  ("READ NEXT: 10 Best…", "Disclosure: None") stay in the extracted text of what gets
  through.
- **Promotional providers also repackage real news,** such as a product recall. A story only
  such a provider covers is lost to the provider rule.
- **Extraction can pick up the next article on the page** (seen once on Yahoo). The verbatim
  check confirms a quote is in the extracted text, not that it belongs to this article.
- **Yahoo `/research/` links** are paywalled Argus teasers. They pass the 150-word minimum
  but hold no report.
- **Many outlets refuse or serve teasers:** Forbes, Bloomberg, Reuters, AP, Seeking Alpha,
  MarketWatch, Barron's and Investor's Business Daily. Yahoo republishes many Reuters and AP
  stories, so wire coverage arrives that way.

## 4. Reliability

- **Interrupted runs:** `--resume` finishes a run, and nothing is paid twice. A Claude
  batch's id is saved on submission (`batch_state.json`); on DeepInfra each answer is saved
  as it arrives (`realtime_results.jsonl`), and only the missing requests are sent.
- **A bad page never stops a run:** its failure is recorded in `articles_manifest.csv`, and
  the row falls back to its headline.
- **The verbatim check:** after collection, each statement is looked up in the article's
  text, with whitespace, quote marks, dashes, markdown and case normalised. The `verbatim`
  column records TRUE, FALSE (kept, but warned about and counted) or `unchecked` (a PDF,
  whose text Python doesn't have).
- **`run_funnel.csv`** shows where every article of the pull went.

**The reference series** is `runs/cost_2024-01_2024-12/`: Costco's 12 monthly runs of
2024 and their explanation in `explain_20261025-2151/` (sector ETF RSPS). The repo also
holds `runs/meta_2022-09_2023-08/` and its explanation `explain_20261026-1208/` (sector
ETF RSPC). These are the project site's two examples.

**What this repo holds, and what it doesn't:**
- **Re-running from a clone sees less than the original run did.** The fetched texts
  (`articles/`) aren't in the repo. Without them, `explain_run.py` takes each statement's
  headline from the article list's title, and the period calls get no openings of the
  screened analyst articles (`explain_detect.load_news`). So a `--dry-run` or `--update` on
  the shipped runs doesn't reproduce the shipped explanation's inputs exactly. `extract_run.py`
  refetches what it can't reuse.
- **PVGO_Collection's series aren't in the repo either:** run its history first (`main.py`'s
  step 2, or the command in README "Run it"). The explanation folder's `pvgo_daily.csv` and
  `pvgo_months.csv` hold the series as the reference run read it.

## 5. Credentials and cost

- **The keys:** `.env` holds `DEEPINFRA_API_KEY` (the extraction on Qwen) and
  `ANTHROPIC_API_KEY` (`explain_run.py`, and the extraction on a `claude-` model).
- **Every paid run shows its estimate and asks before submitting.** `--dry-run` is free:
  it fetches the pages, writes the requests to `batch_requests_preview.jsonl` and prints
  the estimate. `--yes` skips the question.
- **The extraction on Qwen3:** $0.09 input / $0.55 output per million tokens, real time,
  with no caching discount (`BATCH_PRICING` holds this real-time price). Costco's 12 months
  cost $0.10. The estimate's tokens per character (0.28) is approximate; the measured cost
  is printed after collection.
- **The extraction on Sonnet** (batch price, cached system prompt) costs about 10 times as
  much.
- **A full-text article costs more** than a headline: the request reads the whole article
  (often 1–3k tokens) and writes up to 3 statements.
- **The explanation (§7): one batch, then about $0.02 per question.**
  - Per period, one call, about $0.005; per earnings release, about $0.003. Costco's 2024
    (44 periods, 4 releases; 47 requests) estimates ~$0.21 and cost $0.16.
  - `--ask`: one call at the standard price, about $0.02.
  - The periods, the monthly split and `--dry-run` are free. The S&P 500 and sector prices
    come from Yahoo Finance (yfinance).

## 6. Interpreting the output

- **Explanations (§7): read a period's label and confidence before its cause.** A period
  explanation sees the move, so it can rationalize: no single cause is tested.
  - A cause in a market-driven or within-noise period is marked suspect. The news is
    company-specific, and there the company-specific move is small or ordinary.
  - The header's placebo check counts how often that happens, against divergent and outlier
    periods: the closer the two rates, the less a cause says on its own.
  - Check a cause's refs: their dates show whether the news is the period's own or a recap
    of older results (§7 limits).
- **The statements are for material developments:** material, fairly significant changes to
  the business as they happen, such as a price-hike warning, pulled guidance, a
  restructuring or a share shift. They're not meant to measure the daily tone of coverage.
  - **Most drivers are roughly the same from month to month.** What matters is that a
    material development shows up when it happens, not how many articles a month there are.
  - **A thin month usually means nothing material happened,** not that coverage failed.
- **What gets in follows the pull** (News_Collection): CNBC, Yahoo Finance and Fortune, in
  articles whose headline names the company or its ticker. Coverage that never names it in
  the headline, such as sector stories, is missed. If a material development is ever missed,
  Fox Business is the remaining full-text outlet to add.
- **Units are about the subject by construction,** and only as far as they bear on a driver
  of its value. A unit mainly about a rival fits nothing unless it states an effect on the
  subject.
- **Stock content is common for big tickers:** 112 of Costco's 864 articles in 2024, and
  shopping content another 105. To see how much of a pull it was, look at `article_scope.csv`'s "skipped:
  stock content: …" rows and `narrative_units_rejected.csv`'s PROMO and STOCK-only rows.

## 7. Explaining PVGO moves (`explain_run.py`)

**The question:** "why did the subject's growth share rise or fall over this period?"

**Usage:** `--runs` (the monthly runs), with optional `--from`/`--to` (months), `--sector`
(overrides `explain_subjects.json`), `--basis`, `--pvgo-dir` and `--out`. Then `--resume`,
`--update` and `--ask` act on an existing explanation folder (below).

**Inputs:**
- **One run per month** from `extract_run.py`: `narrative_units.csv`, `article_scope.csv`
  and, where present, the fetched `articles/` (for headlines and the analyst articles'
  openings).
- **PVGO_Collection's series for one EPS basis** (`--basis`):
  `<TICKER>_pvgo_history{_ttm_adjusted,,_two_year,_six_month}_series.csv` and its
  `_points.csv`, from `PVGO_Collection/Outputs_CSV_data/`.
  - **The default, `ttm_adjusted`:** TTM GAAP EPS without the gains and losses on
    investments (PVGO METHODOLOGY §1–2). Other one-time items enter the TTM at their release
    and leave four quarters later, and each such step is explained.
  - **From the series:** `close`, `no_growth_value`, the cost of equity's parts on the line
    points, and on a release's measurement day `no_growth_value_before_step`.
  - **From the points file:** each release's EPS, how it's built, and the one-time flags.
  - **A run keeps the basis it was made on** for `--update` and `--ask`. Another basis is a
    new run, because the bridge and the periods' pp figures change with it.
- **`<TICKER>_pvgo_history_release_items.csv`** (PVGO_Collection, `RELEASE_ITEMS = True`):
  each press release's GAAP-to-adjusted EPS reconciliation tables, the sentences in its text
  that name an item per share, those that name one in dollars only, and the quarter's
  diluted share count, naming the one-time items. Without it, a release block has no
  one-time items.
- **Daily S&P 500 and sector-ETF closes** (Yahoo Finance), cached in `market_prices.csv`.
- **`explain_subjects.json`, per ticker:** the sector ETF, chosen by the rule below (COST:
  RSPS, META: RSPC).

**Step 1, detect (free):**
- **The daily bridge.** Each day's change in the growth share (100 × (1 − V/P)) splits
  exactly into three parts:
  - **price-driven** = 100 × V0 × (1/P0 − 1/P1), with V0 the previous day's no-growth value:
    the move from the price alone. Within a day it's the stock's return scaled by the
    no-growth share, so it hardly depends on PVGO_Collection's input choices.
  - **EPS update** = 100 × (V_before − V1)/P1, on a release's measurement day: the new EPS
    replacing the old. It's often the biggest single move in a month.
  - **rates/other:** the rest, the cost of equity's drift, split into Treasury, ERP and beta
    (`rate_treasury_pp`, `rate_erp_pp`, `rate_beta_pp`). Between two line points, k =
    Treasury + β × ERP changes by exactly ΔTreasury + mean β × ΔERP + mean ERP × Δβ, and each
    day's rates/other is shared in that proportion. With PVGO_Collection's fixed ERP,
    `rate_erp_pp` is zero, and the bucket measures the Treasury and the monthly re-estimate
    of the beta.
- **The monthly bridge:** the growth share at the start → at the end = market +
  company-specific (the price-driven part) + EPS update + rates/other. It matches
  PVGO_Collection's chart line.
- **The market part:** a rolling OLS of the stock's daily return on the S&P 500 and the
  sector ETF, fitted on the previous 180 trading days only (at least 120).
  - The intercept is fitted but not removed: the stock's own trailing drift counts as
    company-specific.
  - The sector factor keeps market-wide days (a tariff pause) out of the company-specific
    part, but it also counts sector-wide news (a rotation into staples) as market.
  - **The rule for the sector ETF:** the equal-weight S&P 500 fund (Invesco's RSPx) of the
    company's GICS sector, the same for every company and fixed before any run.
    - **GICS, not our own reading of the business:** the classification is external and
      applies to every company alike. Meta is in Communication Services (with Alphabet and
      Netflix), as in the Counterpoint charts PVGO_Collection compares with, though it trades
      with megacap tech. How a stock trades (growth, rates, a theme) is a style, not a
      sector; it would come in as a style factor for every company, not as a swapped sector.
    - **Equal weight, not cap weight:** a cap-weighted fund can hold much of the company
      itself (Meta was about 22% of XLC, Costco about 10% of XLP), so part of the company's
      own move would be credited to "market". In an equal-weight fund the company is about
      1/N of it at each rebalance (a few percent for a sector of a few dozen members), and
      the effect is small.
    - **Not chosen by fit:** a fund that fits better in the explained year would be picked
      with hindsight.
    - **Limits:** the funds' sectors are broad (RSPC also holds telecoms and media), and
      RSPC's prices start in November 2018, so a META period before 2019 needs the GICS
      sector of the time (Meta was in Information Technology until September 2018: RSPT).
- **Big market days are flagged:** a day where the S&P 500 moved at least `MARKET_DAY_Z` =
  2.5 × its own 60-day volatility (`spx_z` in `pvgo_daily.csv`). The market model is fitted
  on mostly normal days, so on an extreme one it can leave part of the market's move as
  company-specific. The day is marked on its period's line in `explanations.md`. The period
  call isn't told: it sees no market figures (below). The periods, their labels and the
  bridge don't change.
- **The periods** (`periods()`): each month is cut into consecutive periods covering every
  trading day, by code alone.
  1. **Shocks stand alone:** a day whose company-specific return is at least `SHOCK_Z` =
     2.5 × its trailing 60-day volatility is a period of its own (Costco: 2024-03-08,
     2024-07-11).
  2. **The rest is cut into swings** of the price-driven path. A period ends at its high (or
     low) once the path has come back `SWING_PP` = 0.75pp from it, and lasts at most
     `PERIOD_MAX_DAYS` = 10 trading days.
  3. **Periods stop at month ends,** so each month's periods add up to its bridge.
- **Each period's label,** from how much of its price move the market explains. The
  market's share is |market| ÷ (|market| + |company-specific|) over the period. Its z is
  the summed company-specific return ÷ (the trailing sd on its last day × √days). In this
  order:
  - **market-driven:** the market's share ≥ `MARKET_DRIVEN_SHARE` = 70%;
  - **within noise:** |z| < `NOISE_Z` = 1.5, so the company-specific move is ordinary for
    that many days;
  - **outlier:** the market's share ≤ `OUTLIER_SHARE` = 30%;
  - **divergent:** in between.

  **Why a noise floor as well as the share:** a ratio says what kind of move it was, not
  whether there was one. Costco's beta is low, so the market rarely explains 70% of its
  moves, but most of what's left is ordinary noise. Without the floor, about half of its
  periods would be divergent or outlier.

  Costco's 2024: 44 periods (3.7 a month, about 6 days each). 7 are market-driven, 27
  within noise, 2 divergent and 8 outlier.
- **Levels versus changes:** the growth share's level depends on the EPS basis. One-time
  charges kept in the TTM lower the EPS and raise the growth share for the four quarters
  they're in. Changes are explained release by release; read levels across years or
  companies with the named one-time items in mind (the output says so).

**Step 2, explain (one batch, `claude-sonnet-5-5`):**
- **Per period, one call, the period call,** every period alike, on the statements from the
  day before it starts to the day after it ends (at most 80, dated, with their headlines),
  the stock's own daily moves and their total, plus the stock and analyst articles of those
  days (headline and opening, at most 20). "Which change in expectations caused this move?"
  It returns a cause (or none), a confidence level (high, medium, low, none), the drivers it
  touches and the statements cited. (In the code and the state its requests are named
  `told_<period>`, from `prompts/explain_told.txt`.)
- **The period call doesn't see the market:** no S&P or sector return, no market share, no
  label, no PVGO figure. It's told only that a stock also moves with the market and often
  with no news of its own. **That makes the placebo check:**
  - In a market-driven or within-noise period, the company-specific move is small or
    ordinary, and the news is company-specific. So a cause found there is suspect, and is
    marked so in the output.
  - The header counts how often the period call found a cause with medium or high confidence
    in those periods, against divergent and outlier ones.
  - A suspect cause isn't necessarily wrong: company news can coincide with a market move,
    or be offset by it, and sector news counts as market (below). The count is a rate, not
    a verdict on each period.
- **A period's status** (`status` in `periods.csv`): **answered**; **no news collected**
  (nothing dated in the window, so no call is made); or **failed** (the reason is in
  `failure`, and `--update` sends it again).
- **Per earnings release, one call, which only extracts the one-time items** (every release
  whose measurement day falls in the run). The EPS change, the arithmetic and the market
  reaction are done by code.
  - **What it reads,** from the filings and the press releases only (no news, no price):
    - the EPS on the basis, before → after, and how it's built at this release and the one
      before (the TTM's window, the adjustment);
    - on TTM, the quarters behind the step, from PVGO_Collection's `ttm_quarters` and
      `ttm_quarter_leaving`: the new quarter and the one it replaces, each with its EPS and
      source (a derived Q4 is labelled as the annual EPS minus Q1–Q3), and their
      difference. On the adjusted TTM, the change in the investment adjustment too. Code
      checks that these add up to the EPS step; any remainder is stated as earlier quarters
      restated since the previous release;
    - PVGO_Collection's flags on unusual quarters;
    - the press release's reconciliation table and the items named in its text, per share
      and in dollars only, and, on TTM, the same for the quarter leaving the TTM (the same
      quarter a year earlier; its table up to 1,500 characters);
    - when a press release has none of these, a line saying its one-time items are unknown,
      not zero;
    - a line when a reconciliation predates a split: the call is told to divide older
      per-share amounts by the ratio.
  - **What it returns:** every one-time item the press releases name in the step's two
    quarters, once each, with its name, its amount, its kind (benefit or gain; charge or loss)
    and its quarter (the new quarter, entering; or the quarter leaving the TTM). A "last
    year's results included…" sentence in this release counts as the leaving quarter. On a
    basis other than TTM, only the new quarter's items.
    - **The amount** is per diluted share (after tax) wherever the press release gives one.
      Only an item with no such figure is given in dollars (`$ millions`), with whether it is
      pre-tax (a charge or gain in costs and expenses, operating or other income) or after tax
      (a tax item, or stated net of tax).
    - **Each item once:** a total given with its parts (by segment, the severance within the
      restructuring) is listed as the total; a quarter's item given only by segment, as their
      sum. Outlooks, year-to-date and full-year figures are left out.
  - **The arithmetic (code):** a dollar item is put per share over its quarter's diluted
    shares from PVGO_Collection (the new quarter's or the leaving quarter's), less
    `ITEM_TAX_RATE` = 25% when pre-tax (PVGO_Collection's flat rate on investment gains). That
    is an estimate, not the company's figure, and the block says so. A benefit entering or a
    charge leaving raises the step by its per-share amount, a charge entering or a benefit
    leaving lowers it. The TTM EPS change less the items is the step minus their sum (TTM
    bases only). A leaving quarter whose press release names nothing contributes nothing:
    unknown, not zero.
  - **The check (code):** each amount must appear in one of the two press releases' text: a
    per-share amount as written ("0.21", or × the split ratio for one from before a split); a
    dollar amount in one of the item sentences, or as the sum of two amounts in one sentence
    (Meta's Q3 2023 restructuring, given as $305 million and $75 million by segment), within
    0.5%. An amount not found is kept and shown as "[amount not found in the press release]",
    and a dollar item without a share count is listed there and left out of the step
    (`items_check` in `releases.csv`).
  - **Its limits with dollar items:** the per-share figure carries the flat tax rate and,
    for a Q4, the fiscal year's average share count. The check confirms an amount is in the
    text, not that it is the quarter's own: a full-year figure or one segment of a total
    would pass it.
  - **The market reaction (code, `market_reaction`):** **results surprise** when the
    company-specific stock return from the release date to the measurement day is at least
    `RELEASE_SURPRISE_Z` = 1.5 × its normal size over those days (the periods' noise floor),
    else **results expected**. The label says the price moved more than noise, not why;
    the periods holding those days carry the cause.
- **Evidence numbers are mapped back** to `<period>/<unit_id>` (statements) or
  `<period>/<article_id>` (analyst articles). Every cited cause traces to a statement, its
  article and its outlet.
- **Text checks** (`check_text`, at collection):
  - statement numbers left in the prose ("(18)", "(3, 15)") become their refs;
  - a date outside the run's years ±1 is marked "[date?]" and listed at the end of
    `explanations.md`.

**Step 3, ask (on demand):** `--ask FROM TO --explain-dir <explain folder>` makes one call
with the period's full bridge by month, the weekly company-specific path, the releases
(the EPS step, its growth-share effect, the market reaction and the one-time items), and
every period with its label, the period call's confidence and its cause. It returns a ranked
answer, with approximate pp per cause and evidence strength, and also sees EPS updates with
flat prices across releases ("growth delivered but not re-extended").
It's built from the step-2 explanations, not from all the statements.

**`--resume EXPLAIN_DIR`** collects a batch that was interrupted.

**`--update EXPLAIN_DIR`** re-runs step 1 for a collected run with the current code and the
run's own settings (runs, months, sector, basis). It keeps every answer the run has
(periods by id, start and end; releases by date), and submits a batch, after showing the
cost and asking, only for the requests the run doesn't have. Each batch is added to the
run's `cost_usd` and listed in the state.

**The reference run** (`runs/cost_2024-01_2024-12/explain_20261025-2151/`, on RSPS):
- **Periods:** 44 (7 market-driven, 27 within noise, 2 divergent, 8 outlier) and 4 releases.
- **Placebo check:** a medium- or high-confidence cause in 1 of the 34 market-driven or
  within-noise periods, against 2 of the 9 that stand out and have news. The one is
  December 2–13, which holds the Q1 release: real company news, in a period whose
  company-specific move was within noise.
- **Answers:** medium confidence 3, low 4, no cause found 36, no news collected 1; none
  high.
- **Releases:** Costco has no reconciliation table, so the items come from the press
  releases' text. Every TTM step equals its two quarters exactly, and every item's amount
  was found in the text. Less the items, the TTM EPS changes are +0.41 (March), +0.35 (May),
  +0.28 (September) and +0.34 (December). March and September are results surprises; May
  and December results expected.
- **Cost:** $0.16, one batch.

**Limits:**
- **The causes are the model's reading of the news, not proven.** Nothing tests a single
  cause; the placebo check measures how often the period call finds causes where there's
  little to explain. Earnings days are the easiest moves to explain.
- **A cause can credit older news recapped in the window.** Articles recap results for
  days after a release. Given a fake +4% on a quiet 2024-03-14, the period call credited
  Costco's Q2 results, which it said were reported the day before (they were reported on
  March 7). The dates of the cited refs show it.
- **A cause follows the move it's given.** Good news followed by a fall reads as
  "priced in" or "sell the news", a story that fits any fall after good news. Nothing in the
  inputs says what was expected, beyond what the statements quote.
- **The model may know the period's events from its training.** The prompt tells it to use
  only the statements; the cited refs are the check.
- **Coverage gaps:** a period with no news in its window, or none that fits, stays
  unexplained. Many within-noise periods are just that.
- **A period's news is its own days ±1.** News from well before it (an announcement the
  stock re-prices slowly) is out of reach, and an article on a boundary day reaches both
  neighbouring periods.
- **Entity claims aren't checked.** A period call can misstate who did what (which company
  replaced which in an index) even when its statements have it right. The cited statements
  are the check.
- **The periods depend on their settings.** `SWING_PP` and `PERIOD_MAX_DAYS` set where
  periods start and end. A smaller swing gives more, shorter periods. A move just under
  `SHOCK_Z` is folded into a swing (Costco's +3.2% on 2024-03-12 sits in a 10-day period).
  The labels' cutoffs (`MARKET_DRIVEN_SHARE`, `NOISE_Z`, `OUTLIER_SHARE`) are judgment
  calls, set on Costco's 2024 alone.
- **The market/company split depends on the factors chosen** (above). For a low-beta stock
  the market rarely explains 70% of a period, so few periods are market-driven: most of the
  placebo check's controls are within-noise periods.
- **The EPS step can land a day after the price reaction:** a press release out during the
  session with its 8-K accepted after the close is measured the next day (PVGO METHODOLOGY
  §7). In a month the bridge still adds up. A release entry looks from the release date to
  the measurement date, and names the periods that span it.
