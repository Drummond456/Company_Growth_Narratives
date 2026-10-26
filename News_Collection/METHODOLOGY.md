# News_Collection — methodology

The first stage of the pipeline: a company's list of articles, one CSV per month, which
`Company_Narrative_Aggregation/extract_run.py` then fetches, screens and extracts from. The
root `main.py` runs it as step 1.

## 1. What this produces
`pulls/<ticker>/news_pull_<start>_<end>.csv`, one per calendar month (e.g.
`pulls/cost/news_pull_2024-01-01_2024-01-31.csv`).
- **Rows:** one per story, with `domain`, `mc_story_id`, `title`, `url`, `publish_date`,
  `language` and `title_search`.
- **What's in it:** only the article list, no text. `extract_run.py` fetches the text.
- **One list per month.** A partial month (a period starting or ending mid-month) covers
  only those days. Pulling the same month again over other days replaces its file.
- **Comparability:** pulls are comparable across months for one company, as long as its
  `search_terms.csv` and `outlets.csv` stay the same. Changing either changes what the
  runs measure.

## 2. Collection mechanics
- **The command:**
  `news_pull.py --ticker COST --search-terms Costco "Costco Wholesale" --start 2024-01 --end 2024-12`. Dates are
  `YYYY-MM` (a whole month) or `YYYY-MM-DD`.
- **The source:** Media Cloud's search API (`mediacloud` 5.2.0).
- **One folder per company,** named by its ticker in lower case: `pulls/cost/`. It's created
  on first use.
- **The search terms,** in the folder's `search_terms.csv` (one `term` column):
  - **On first use,** the file is written from `--search-terms`: the company's name and any
    variants, as headlines write them, separated by spaces (a term with a space in quotes).
    `pulls/cost/` searches for `Costco` and `Costco Wholesale`.
  - **The ticker is a search term only when it's listed.** Include it only if it's
    distinctive in a headline: `MSFT` is, but `COST` (Costco) would match every headline about
    costs.
  - **Later runs** can leave `--search-terms` out, and the file is used as is.
  - **Terms that differ from the file stop the pull,** since they would change what the
    earlier months measure. `--replace-search-terms` replaces the file; then re-pull the
    earlier months with `--overwrite`.
- **Shared outlets:** `outlets.csv` (`domain`, `source_id`, `title_search`), so every
  company is pulled from the same outlets: CNBC, Yahoo Finance and Fortune. They were chosen
  because their full text can be extracted. `outlets_full.csv` is a wider candidate list.
- **The query:** per month and outlet, a headline search,
  `(article_title:"t1" OR article_title:"t2" …)`, split into several queries if it would
  exceed 2,000 characters. An outlet with `title_search` off is pulled whole. Results are
  paged by 1,000 and deduped by story id.
- **Progress:** each month prints `Collecting articles from <YYYY-MM>...`, then its story
  count per outlet.

## 3. Source-specific limits
- **A headline search** misses coverage that doesn't name the company in the headline,
  such as sector stories.
- **Media Cloud's collection per outlet is incomplete:** early 2023 is thin for every
  company.

## 4. Reliability
- **Official API, with frequent rate limiting** (HTTP 429). A month that fails on a Media
  Cloud error or a connection error is retried after 60 s, up to 5 tries (`TRIES`,
  `RETRY_SECONDS`).
- **A month that still fails** is reported, the remaining months are pulled, and the
  command ends with the list of months not pulled (and a non-zero exit).
- **Rerunning the same command** skips the months that already have a file, so it pulls
  only what's missing. `--overwrite` re-pulls them.
- **Time:** a 36-month pull takes about an hour, mostly waiting.

## 5. Credentials and cost
Free. `MEDIACLOUD_API_KEY` goes in `.env` here (copy `.env.example`), and is never
committed.
