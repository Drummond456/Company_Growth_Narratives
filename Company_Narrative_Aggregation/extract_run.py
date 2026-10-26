"""
Narrative units about ONE company or stock (--subject), tagged with the company codebook
(company_codebook.csv). Every article's full text is fetched where the site allows it;
blocked or short pages fall back to their headline.

Turn article lists (News_Collection CSVs) into narrative units tagged with topic codes.
The topic codebook IS the scope: a unit exists only where something fits a topic.

  - full text:    the model picks the sentences it would use to summarize the article's
                  news about the subject in at most MAX_STATEMENTS (3) bullet points - each
                  a statement copied VERBATIM from the article (one or two sentences),
                  fitting a topic and tagged with its codes. Nothing fits: the article is
                  dropped.
  - headline     (articles whose text couldn't be fetched): the model gives the codes of
                  the topics the headline fits. None: the article is dropped. The unit is
                  the headline itself.

One pass, one batch, one model: no separate filter stage.

Scope = the codebook's substantive codes. Codes marked exclude=scope in the codebook
(OTHER) are left out of the prompt and the schema - an "other" bucket would make
everything in scope. Qualifiers (codebook family "Qualifier": PROMO) may only accompany
a topic code, so they never bring a unit into scope. Units carrying a code marked
exclude=output go to narrative_units_rejected.csv, and so do units whose only topic is
an exclude=alone code (STOCK).

Verbatim check: after collection, each quote is looked up in the article's text
(normalised for whitespace, quote marks, dashes, markdown and case) and the result is
recorded in the `verbatim` column - TRUE, FALSE (kept, warned, counted) or unchecked
(PDFs: Python doesn't have their text).

Usual use, a company's whole pull folder, one run per month:
    python extract_run.py --pull-dir ../News_Collection/pulls/cost --subject "Costco (COST)"
It fetches every month's articles, shows the estimated cost per month and in total, and
asks once before submitting. The runs go into one series folder,
runs/<ticker>_<first month>_<last month>/<list name>/, which explain_run.py reads as is.
Rerunning the same command skips the months already extracted and finishes any that
were interrupted. --from/--to (YYYY-MM) limit the months.

One list:
    python extract_run.py --article-list <pull.csv> --subject "Microsoft (MSFT)"
writes everything for the run into runs/<list-name>_<period>_<subject>_<timestamp>/.
Each run folder holds:
  - article_list.csv       the merged list, when several were given
  - articles/              fetched texts and headline files (gitignored - publishers' text)
  - articles_manifest.csv  per URL: which file it became, or why it failed
  - article_scope.csv      per article: fit / no_fit / failure, units, kept
  - narrative_units.csv    THE OUTPUT - one row per unit (a statement or a headline),
                           minus units tagged PROMO (exclude=output) or tagged only STOCK
                           (exclude=alone).
  - narrative_units_rejected.csv   those excluded units, with the code(s) that excluded them
  - code_matrix.csv        the same units read by code: a column pair (unit id, text) per
                           codebook code
  - run_funnel.csv         articles in the pull -> skipped -> sent -> fit -> units in
                           narrative_units.csv
  (extract_reports.py rebuilds the last two for an existing run)
  - batch_state.json       for --resume
--input-dir instead points it at a folder of articles you assembled yourself.
Article lists are news_pull.py's Media Cloud CSVs (read by extract_fetch.list_row).

API: an open model (the default, Qwen/Qwen3-235B-A22B-Instruct-2507) runs on
DeepInfra's real-time API, several requests at a time; each answer is saved as it arrives
(realtime_results.jsonl). A "claude-" model (--model) runs on Claude's Message Batches API
at 50% off, whose cost is waiting - the limit is 24h - so the batch id is saved on
submission. Either way an interrupted run continues with --resume, and nothing is paid
twice.

Before anything is submitted, a free Python screen (screen_articles) skips a PDF copy
of a page already fetched as text, and a headline the same outlet published twice. Skipped articles get no request and are listed in
article_scope.csv with their reason.

Reads DEEPINFRA_API_KEY (open models) or ANTHROPIC_API_KEY (Claude) from a .env file in
this directory.
Importing this module makes no API call - everything that spends money is reached only
through main().
"""

import argparse
import csv
import re
from pathlib import Path

from anthropic.types.messages.batch_create_params import Request

import extract_fetch
import narrative_common as N
from extract_articles import (
    attach_records,
    latest_uncollected_run,
    load_articles,
    merge_article_lists,
    new_run_dir,
    period_label,
    request_kind,
    resolve_article_lists,
    run_name,
    screen_articles,
    subject_slug,
)
from extract_collect import collect, print_summary
from extract_reports import exclusion_label, split_units, write_reports
from extract_requests import (
    build_request,
    compute_prompt_version,
    describe_costs,
    fmt_estimate,
    model_codebook,
    prompt_options,
    total_cost,
    write_preview,
)
from narrative_common import (
    ARTICLE_LIST_CSV,
    BATCH_PRICING,
    BATCH_STATE_JSON,
    confirm_submit,
    CSV_COLUMNS,
    DEEPINFRA_CONTEXT,
    DEEPINFRA_MAX_TOKENS,
    deepinfra_results,
    deepinfra_run,
    DEEPINFRA_TEMPERATURE,
    deepinfra_wait,
    get_client,
    HEADLINE,
    INPUT_DIR,
    is_deepinfra,
    load_codebook,
    load_state,
    MAX_STATEMENTS,
    MERGED_LIST_CSV,
    MODEL,
    new_run_id,
    now_iso,
    OUTPUT_CSV,
    PREVIEW_JSONL,
    qualifier_codes,
    read_jsonl,
    REALTIME_REQUESTS_JSONL,
    REALTIME_RESULTS_JSONL,
    REJECTED_CSV,
    REJECTED_CSV_COLUMNS,
    RUNS_DIR,
    save_state,
    scope_codes,
    SCOPE_CSV,
    SCOPE_CSV_COLUMNS,
    wait_for_batch,
    write_csv,
)


def submit(
    records: dict, requests: list[Request], model: str, max_n: int, input_dir: str,
    codebook: list[dict], state_path: Path, prompt_version: str,
) -> dict:
    """Submit the batch, and save the state that --resume reads back. Refuses to
    overwrite the state of a batch that hasn't been collected yet: that file is the only
    record of its id. For a DeepInfra model nothing is sent here: the requests are saved
    next to the state, and finish() sends them in real time."""
    previous = load_state(state_path)
    if previous and not previous.get("collected"):
        raise SystemExit(
            f"{state_path} holds {previous.get('batch_id') or 'a real-time run'}, which hasn't been collected yet. "
            "Run with --resume to collect it, or delete the file to discard it."
        )
    provider = "deepinfra" if is_deepinfra(model) else "anthropic"
    if provider == "deepinfra":
        batch_id = None
        write_preview(requests, state_path.parent / REALTIME_REQUESTS_JSONL)
    else:
        batch_id = get_client().messages.batches.create(requests=requests).id
    # Names and provenance are recorded here rather than looked up at collection, so a
    # --resume hours later reports what this batch was run against.
    state = {
        "run_id": new_run_id(),
        "subject": N.SUBJECT,
        "provider": provider,
        "batch_id": batch_id,
        "model": model,
        "temperature": DEEPINFRA_TEMPERATURE if provider == "deepinfra" else None,  # None: the API default
        # the prompt variants the requests were built with, so collection reads their answers alike
        "prompt_options": prompt_options(model),
        "prompt_version": prompt_version,
        "max_statements": max_n,
        "input_dir": str(Path(input_dir).resolve()),
        "submitted_at": now_iso(),
        "collected": False,
        "topic_names": {row["code"]: row.get("topic", "") for row in codebook},
        "qualifier_codes": qualifier_codes(codebook),
        "scope_codes": scope_codes(model_codebook(codebook, model)),  # the codes the model was offered
        "articles": records,
    }
    save_state(state, state_path)  # immediately - everything after this point is resumable
    if batch_id:
        print(f"Submitted batch {batch_id} ({len(requests)} request(s)); state in {state_path}")
    return state


def finish(state: dict, state_path: Path, scope_path: Path, output: str | Path) -> None:
    """Wait for the batch (or, for DeepInfra, send the requests in real time), collect it,
    write both CSVs, mark the state collected."""
    deepinfra = state.get("provider") == "deepinfra"  # runs from before 2026-10-17 have no provider: Claude
    if deepinfra and not state.get("batch_id"):
        base = Path(state_path).parent
        results = deepinfra_run(read_jsonl(base / REALTIME_REQUESTS_JSONL), base / REALTIME_RESULTS_JSONL)
    else:
        try:
            batch = deepinfra_wait(state["batch_id"]) if deepinfra else wait_for_batch(state["batch_id"])
        except KeyboardInterrupt:
            raise SystemExit(f"\nStopped polling. Batch {state['batch_id']} is still running - rerun with --resume.")
        results = deepinfra_results(batch) if deepinfra else get_client().messages.batches.results(state["batch_id"])
    units, scope_rows = collect(results, state)
    units.sort(key=lambda r: (r["article_id"], r["unit_index"]))
    kept, rejected = split_units(units)
    # Per article: n_units stays what the model produced (after the checks); n_rejected
    # of them went to the rejected file; kept = it has a unit in narrative_units.csv.
    n_rejected = {}
    for u in rejected:
        n_rejected[u["article_id"]] = n_rejected.get(u["article_id"], 0) + 1
    for row in scope_rows:
        row["n_rejected"] = n_rejected.get(row["article_id"], 0)
        row["kept"] = "TRUE" if row["n_units"] > row["n_rejected"] else "FALSE"
    rejected_path = Path(scope_path).parent / REJECTED_CSV
    write_csv(scope_rows, SCOPE_CSV_COLUMNS, scope_path)
    write_csv(kept, CSV_COLUMNS, output)
    write_csv(rejected, REJECTED_CSV_COLUMNS, rejected_path)
    state["collected"] = True
    save_state(state, state_path)
    print_summary(units, scope_rows)
    print(f"\nSaved {len(kept)} unit(s) to {output}; to {rejected_path}: {len(rejected)} "
          f"{exclusion_label('/')}; per-article scope in {scope_path}")
    write_reports(kept, scope_rows, Path(state["input_dir"]), Path(scope_path).parent, rejected)


def prepare(article_list: str | None, run_dir: Path | None, input_dir: str, codebook: list[dict], model: str,
            max_n: int, refetch: bool, reuse_own: bool = False) -> tuple[dict, list[Request], list[dict]]:
    """Everything before a run is paid for: fetch the list into the run folder (when there is
    one), load and screen its articles, and build their requests. Returns (records, requests,
    the articles that get a request); the last two are empty when the screen skipped them all.
    reuse_own: the run folder's own earlier fetch counts as reusable text (a series month
    prepared before, e.g. by a dry run); a new run folder has none."""
    if article_list:
        # Every row is fetched for its full text; a blocked, failed or short page falls back
        # to its headline (extract_fetch.HEADLINE_FALLBACK).
        print(f"Fetching article texts from {article_list}\n  into {run_dir} (subject: {N.SUBJECT})")
        # An article an earlier run already fetched in full is copied from it rather than
        # fetched again: fetching is most of a run's time (about 2 s an article, mostly the
        # politeness delay), and a re-run then reads the same text. --refetch fetches afresh.
        reuse = None if refetch else extract_fetch.reuse_index(RUNS_DIR, exclude=None if reuse_own else run_dir)
        if reuse:
            print(f"  {len(reuse)} article(s) fetched by earlier runs under {RUNS_DIR.name}/ can be reused")
        extract_fetch.build_article_folder(
            article_list, out_dir=input_dir, manifest_path=str(run_dir / extract_fetch.MANIFEST_CSV), reuse=reuse,
        )
        print()

    articles = load_articles(input_dir)
    if not articles:
        raise SystemExit(f"No usable articles in {input_dir}")
    records = attach_records(articles, input_dir)
    n_head = sum(request_kind(a) == HEADLINE for a in articles)
    print(f"Loaded {len(articles)} article(s) from {input_dir}: {len(articles) - n_head} full text, "
          f"{n_head} headline")
    articles = screen_articles(articles, records)
    if is_deepinfra(model):  # text-only models: a PDF can't be sent (none in the 2023-2025 pulls)
        for a in articles:
            if a["kind"] == "pdf":
                records[a["article_id"]]["skip"] = "PDF (the model reads text only)"
                print(f"  ! {a['article_id']}: skipped, a PDF ({model} reads text only)")
        articles = [a for a in articles if a["kind"] != "pdf"]
    requests = [build_request(a, codebook, model, max_n) for a in articles]
    return records, requests, articles


def context_warnings(requests: list[Request], model: str) -> list[str]:
    """DeepInfra requests estimated not to fit the model's context. Estimated from characters,
    so a warning, not a cut: such a request may fail, and its article then shows as errored in
    article_scope.csv."""
    if not is_deepinfra(model):
        return []
    per_char = BATCH_PRICING[model].tokens_per_char if model in BATCH_PRICING else 0.3
    context = DEEPINFRA_CONTEXT.get(model, 32768)
    warnings = []
    for r in requests:
        n_chars = sum(len(m["content"]) for m in r["body"]["messages"])
        if n_chars * per_char + DEEPINFRA_MAX_TOKENS > context:
            warnings.append(f"! {r['custom_id']}: ~{n_chars * per_char:,.0f} input tokens, may not fit the "
                            f"{context:,}-token context")
    return warnings


def pricing_label(model: str) -> str:
    return "DeepInfra real-time pricing" if is_deepinfra(model) else "batch pricing"


# --- Series mode (--pull-dir): one run per monthly list ---------------------------------

PULL_LIST = re.compile(r"^news_pull_(\d{4}-\d{2})-\d{2}_\d{4}-\d{2}-\d{2}$")  # news_pull.py's monthly file names


def series_lists(pull_dir: Path, first: str | None, last: str | None) -> list[tuple[str, Path]]:
    """[(month, list)] for the pull folder's monthly lists, news_pull_<start>_<end>.csv, from
    month `first` to `last` (YYYY-MM; None = no bound)."""
    lists = []
    for path in sorted(pull_dir.glob("news_pull_*.csv")):
        match = PULL_LIST.match(path.stem)
        if match and (not first or match.group(1) >= first) and (not last or match.group(1) <= last):
            lists.append((match.group(1), path))
    return lists


def run_prompt_version(run_dir: Path) -> str:
    """The prompt_version of a collected run's units ("" if it has none)."""
    with open(run_dir / OUTPUT_CSV, newline="", encoding="utf-8-sig") as f:
        first = next(csv.DictReader(f), None)
    return (first or {}).get("prompt_version", "")


def run_series(pull_dir: Path, first: str | None, last: str | None, codebook: list[dict], prompt_version: str,
               args: argparse.Namespace) -> None:
    """One run per monthly list in the pull folder, all in one series folder,
    runs/<company>_<first month>_<last month>/, which explain_run.py reads as is. Each month's
    run folder is named after its list, so a rerun finds it: a collected month is skipped, an
    uncollected one is finished (--resume), and the rest are prepared. Every month is fetched
    and costed before anything is paid for, and the whole series is confirmed once."""
    lists = series_lists(pull_dir, first, last)
    if not lists:
        raise SystemExit(f"No monthly lists (news_pull_<start>_<end>.csv) in {pull_dir}"
                         + (f" from {first or 'the start'} to {last or 'the end'}" if first or last else ""))
    months = [m for m, _ in lists]
    repeated = sorted({m for m in months if months.count(m) > 1})
    if repeated:
        raise SystemExit(f"More than one list for {', '.join(repeated)} in {pull_dir}: keep one per month")
    series = RUNS_DIR / f"{pull_dir.name.lower()}_{first or months[0]}_{last or months[-1]}"
    print(f"Series: {len(lists)} month(s), {months[0]} to {months[-1]}, in {series}\n")

    done, to_finish, to_submit = [], [], []
    for month, path in lists:
        run_dir = series / path.stem
        state = load_state(run_dir / BATCH_STATE_JSON)
        if (run_dir / OUTPUT_CSV).is_file() and (state is None or state.get("collected")):
            done.append(month)
            if run_prompt_version(run_dir) not in ("", prompt_version):
                print(f"  ! {month}: extracted with prompt_version {run_prompt_version(run_dir)}, not "
                      f"{prompt_version}: the series mixes prompts (delete the month's folder to redo it)")
        elif state and not state.get("collected"):
            to_finish.append((month, run_dir, state))
        else:
            print(f"== {month}")
            run_dir.mkdir(parents=True, exist_ok=True)
            records, requests, articles = prepare(str(path), run_dir, str(run_dir / INPUT_DIR), codebook,
                                                  args.model, args.max_statements, args.refetch, reuse_own=True)
            if requests:
                to_submit.append((month, run_dir, records, requests, articles))
            else:
                print(f"  ! {month}: every article was skipped by the pre-submit screen - nothing to submit")

    print()
    if done:
        print(f"Already extracted: {len(done)} month(s), {done[0]} to {done[-1]}")
    if to_finish:
        print(f"Submitted before, to finish: {', '.join(m for m, _, _ in to_finish)}")
    if not to_submit and not to_finish:
        print(f"Nothing to do: every month is extracted. Explain it with: python explain_run.py --runs {series}")
        return

    lines, best, worst = [], 0.0, 0.0
    for month, run_dir, records, requests, articles in to_submit:
        est = total_cost(articles, codebook, args.model, args.max_statements)
        if est is not None:
            best, worst = best + est[0], worst + est[1]
        lines.append(f"{month}: {len(requests)} request(s) - {fmt_estimate(est)}")
        lines += [f"{month}: {w}" for w in context_warnings(requests, args.model)]
    if to_submit:
        lines.append(f"total: {sum(len(s[3]) for s in to_submit)} request(s) in {len(to_submit)} month(s), "
                     f"{args.model} - {fmt_estimate((best, worst))}")

    if args.dry_run:
        for month, run_dir, _, requests, _ in to_submit:
            write_preview(requests, run_dir / PREVIEW_JSONL)
        print(f"Dry run: requests written to each month's {PREVIEW_JSONL}; nothing submitted")
        for line in lines:
            print(f"  {line}")
        print(f"  prompt_version {prompt_version}")
        return
    if to_submit and not confirm_submit(lines, args.yes, pricing_label(args.model)):
        print(f"Not submitted - nothing was charged. Fetched articles are in {series}.")
        return

    # Every month is submitted first (a Claude batch each; nothing is sent for DeepInfra until
    # finish), then each is collected in turn. An interruption leaves each month's state, and a
    # rerun finishes what's left.
    for month, run_dir, records, requests, _ in to_submit:
        print(f"\n== {month}: submitting")
        state = submit(records, requests, args.model, args.max_statements, str(run_dir / INPUT_DIR), codebook,
                       run_dir / BATCH_STATE_JSON, prompt_version)
        to_finish.append((month, run_dir, state))
    for month, run_dir, state in sorted(to_finish, key=lambda t: t[0]):
        print(f"\n== {month}: collecting")
        finish(state, run_dir / BATCH_STATE_JSON, run_dir / SCOPE_CSV, run_dir / OUTPUT_CSV)
    print(f"\nSeries done: {series}\nExplain it with: python explain_run.py --runs {series}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Turn article lists about one company into topic-tagged narrative units - verbatim "
                    "statements (full text) and headlines that fit the company codebook - via DeepInfra's "
                    "real-time API (open models) or Claude's Message Batches (claude- models)."
    )
    parser.add_argument("--subject", help='the company or stock every unit must be about, e.g. "Microsoft (MSFT)" '
                                          "(required, except with --resume)")
    parser.add_argument("--pull-dir", help="a company's pull folder (News_Collection/pulls/<ticker>): one run per "
                                           f"monthly list, all in one series folder under {RUNS_DIR.name}/")
    parser.add_argument("--from", dest="first", help="with --pull-dir: the first month, YYYY-MM (default: the first list)")
    parser.add_argument("--to", dest="last", help="with --pull-dir: the last month, YYYY-MM (default: the last list)")
    parser.add_argument(
        "--article-list", nargs="+", default=ARTICLE_LIST_CSV,
        help="News_Collection CSV(s) of article URLs (news_pull.py's Media Cloud lists). "
             f"Several are concatenated into one run, in a new folder under {RUNS_DIR.name}/",
    )
    parser.add_argument("--input-dir", help="a folder of .txt/.md/.pdf/.headline.md articles you built yourself; "
                                            "overrides the article list, and outputs go to the working directory")
    parser.add_argument("--model", default=MODEL, help=f"model for every request (default: {MODEL}); a claude- id "
                                                       "runs on Claude's batch API, any other on DeepInfra's")
    parser.add_argument("--max-statements", type=int, default=MAX_STATEMENTS,
                        help=f"ceiling on statements per full-text article (default: {MAX_STATEMENTS})")
    parser.add_argument("--output", help=f"output CSV (default: the run folder's {OUTPUT_CSV})")
    parser.add_argument("--yes", action="store_true", help="submit without the cost confirmation prompt")
    parser.add_argument("--refetch", action="store_true",
                        help="fetch every article afresh instead of reusing text earlier runs fetched for the same URL")
    parser.add_argument("--dry-run", action="store_true",
                        help="fetch and build every request, write a preview, but don't call the API")
    parser.add_argument("--resume", action="store_true",
                        help="don't start a new run: collect the latest uncollected run of this list (or --run-dir)")
    parser.add_argument("--run-dir", help="with --resume: the run folder to resume")
    args = parser.parse_args()

    if args.max_statements < 1:
        parser.error("--max-statements must be at least 1")
    if not args.resume and not (args.subject or "").strip():
        parser.error('--subject is required, e.g. --subject "Microsoft (MSFT)"')
    if args.pull_dir and (args.article_list or args.input_dir or args.resume or args.output):
        parser.error("--pull-dir runs on its own: no --article-list, --input-dir, --resume or --output "
                     "(a rerun of the same command resumes the series)")
    if (args.first or args.last) and not args.pull_dir:
        parser.error("--from and --to go with --pull-dir")
    for month in (args.first, args.last):
        if month and not re.fullmatch(r"\d{4}-\d{2}", month):
            parser.error(f"months are YYYY-MM, not {month!r}")
    if not args.pull_dir and not args.input_dir and not args.article_list and not (args.resume and args.run_dir):
        parser.error("give the pull to run on with --pull-dir or --article-list (or a folder with --input-dir)")
    N.SUBJECT = (args.subject or "").strip()

    if args.pull_dir:
        pull_dir = Path(args.pull_dir)
        if not pull_dir.is_dir():
            raise SystemExit(f"Pull folder not found: {pull_dir.resolve()}")
        # Loaded before anything is fetched, so a missing or broken codebook fails fast.
        codebook = load_codebook()
        prompt_version = compute_prompt_version(args.max_statements, model_codebook(codebook, args.model),
                                                **prompt_options(args.model))
        run_series(pull_dir, args.first, args.last, codebook, prompt_version, args)
        return

    # Where this run reads and writes. An article list gets its own run folder, so two
    # lists - whose files are both named by row number - can never mix in one folder.
    article_lists = [] if args.input_dir else resolve_article_lists(args.article_list)
    if args.resume and args.run_dir:
        run_dir = Path(args.run_dir)
    elif args.resume and article_lists:
        run_dir = latest_uncollected_run(run_name(article_lists))
        if run_dir is None:
            raise SystemExit(f"--resume: no uncollected run of {run_name(article_lists)} under {RUNS_DIR}")
    elif article_lists:
        label = "_".join(p for p in (period_label(article_lists), subject_slug(N.SUBJECT)) if p)
        run_dir = new_run_dir(run_name(article_lists), label)
    else:
        run_dir = None  # folder mode - outputs in the working directory

    base = run_dir if run_dir else Path(".")
    input_dir = str(run_dir / INPUT_DIR) if run_dir else (args.input_dir or INPUT_DIR)
    state_path, scope_path = base / BATCH_STATE_JSON, base / SCOPE_CSV
    output = args.output or str(base / OUTPUT_CSV)

    if args.resume:
        state = load_state(state_path)
        if state is None:
            raise SystemExit(f"--resume: no {state_path} found")
        if state.get("collected"):
            raise SystemExit(f"--resume: the run in {state_path} is already collected")
        print(f"Resuming {('batch ' + state['batch_id']) if state.get('batch_id') else 'real-time requests'} "
              f"(run {state['run_id']})")
        load_codebook()  # fills the exclusion sets the collection uses
        finish(state, state_path, scope_path, output)
        return

    # Loaded before anything is fetched, so a missing or broken codebook fails fast.
    codebook = load_codebook()
    prompt_version = compute_prompt_version(args.max_statements, model_codebook(codebook, args.model),
                                            **prompt_options(args.model))

    article_list = None
    if article_lists:
        run_dir.mkdir(parents=True)
        if len(article_lists) == 1:
            article_list = article_lists[0]
        else:
            # One concatenated list in the run folder: row numbers (the NNN_ in article
            # filenames) are positions in it, and it records exactly what was run.
            article_list = str(run_dir / MERGED_LIST_CSV)
            merge_article_lists(article_lists, Path(article_list))
            print()
    records, requests, articles = prepare(article_list, run_dir, input_dir, codebook, args.model,
                                          args.max_statements, args.refetch)
    if not requests:
        raise SystemExit("Every article was skipped by the pre-submit screen - nothing to submit")
    cost_lines = describe_costs(articles, codebook, args.model, args.max_statements)
    cost_lines += context_warnings(requests, args.model)
    if args.dry_run:
        write_preview(requests, base / PREVIEW_JSONL)
        print(f"Dry run: {len(requests)} request(s) -> {base / PREVIEW_JSONL}; nothing submitted")
        for line in cost_lines:
            print(f"  {line}")
        print(f"  prompt_version {prompt_version}")
        return

    if not confirm_submit(cost_lines, args.yes, pricing_label(args.model)):
        print("Not submitted - nothing was charged." + (f" Fetched articles are in {run_dir}." if run_dir else ""))
        return

    state = submit(records, requests, args.model, args.max_statements, input_dir, codebook, state_path, prompt_version)
    finish(state, state_path, scope_path, output)


if __name__ == "__main__":
    main()
