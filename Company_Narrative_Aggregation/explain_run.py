"""
Explain PVGO moves: why did the subject's PVGO share (growth share = PVGO / price) rise
or fall over a period? (METHODOLOGY.md s.7.)

Reads the monthly runs extract_run.py made for one company, and that company's daily PVGO
series from PVGO_Collection (on one EPS basis, --basis: the adjusted TTM by default), cuts
each month into periods and explains each from the collected news:

  1 detect   code, free. Each day's growth-share change = price-driven (no-growth value
             held at the day before) + EPS update (the step at a release's measurement
             day) + rates/other. The price-driven part is split into the market's part -
             a rolling regression of the stock's return on the S&P 500 and a sector ETF -
             and the company-specific rest. Each month is cut into periods covering
             every trading day (a day >= SHOCK_Z x its noise alone, the rest in swings of
             the price-driven path), each labelled by how much the market explains:
             market-driven, within noise, divergent or outlier.
  2 explain  one batch (Sonnet). Per period, the told call: given the stock's own moves
             (not the market's) and the period's news, which change in expectations
             caused them, with what confidence? A cause found in a market-driven or
             within-noise period is suspect: the news is company-specific, so those
             periods are the placebo check. Per earnings release, one call extracts
             the one-time items the press releases name (PVGO_Collection's release
             items); code checks them, computes the EPS change less them, and labels
             the price reaction "results surprise" or "results expected".
  3 ask      on demand, one standard API call: "why did PVGO move from <month> to
             <month>?", rolled up from step 2's period and release explanations.

    python explain_run.py --runs runs/cost_2024-01_2024-12 --dry-run   # free: step 1, preview
    python explain_run.py --runs runs/cost_2024-01_2024-12             # asks before submitting
    python explain_run.py --resume runs/cost_2024-01_2024-12/explain_<time>
    python explain_run.py --update runs/cost_2024-01_2024-12/explain_<time>   # only what's missing
    python explain_run.py --ask 2024-06 2024-08 --explain-dir runs/cost_2024-01_2024-12/explain_<time>

--runs takes run folders, or folders of them; one run per month. The ticker comes from
the units' subject ("Costco (COST)"); its sector ETF comes from explain_subjects.json
(--sector overrides it). --update re-runs
step 1 for a collected run with the current code and its own settings, keeps every
answer it has, and submits only the requests it lacks (e.g. the release items, for a
run made before them). A different --basis needs a new run.

Output: <runs folder>/explain_<YYYYMMDD-HHMM>/
  - pvgo_daily.csv          per trading day: growth share, the bridge, returns, z, period id
  - pvgo_months.csv         per month: share start/end and the bridge (step 1)
  - periods.csv             per period: the move, its label, the cause and its confidence
  - releases.csv            per release: the EPS update, the reaction, the label
  - explanations.md         THE READABLE OUTPUT: releases, and each month's bridge and periods
  - market_prices.csv       the S&P 500 and sector closes used (Yahoo Finance)
  - explain_state.json      the batch id, settings and answers, for --resume, --update, --ask
  - batch_requests_preview.jsonl   the exact requests (also on --dry-run)
  - ask_<from>_<to>.md / .json     each --ask answer

PAID: step 2 is one batch at batch prices; step 3 is one standard-price call per question. Each shows its estimate and asks first (--yes skips the question). Step 1 and
the preview are free. Reads ANTHROPIC_API_KEY from .env, as extract_run.py does.
"""

from __future__ import annotations

import argparse
import json
import os
from collections import defaultdict
from pathlib import Path

import narrative_common as N
from explain_detect import (
    BASES,
    build_releases,
    DAILY_COLUMNS,
    daily_split,
    find_runs,
    FIT_DAYS,
    from_state_path,
    LABELS,
    load_news,
    load_pvgo,
    market_prices,
    MARKET_DRIVEN_SHARE,
    migrate,
    MODEL,
    MONTH_COLUMNS,
    month_days,
    month_split,
    new_out_dir,
    NEWS_DAYS,
    NOISE_Z,
    OUTLIER_SHARE,
    PERIOD_COLUMNS,
    PERIOD_MAX_DAYS,
    periods,
    PROMPTS,
    PVGO_DIR,
    read_csv,
    save,
    sha256_of,
    SHOCK_Z,
    STATE_JSON,
    SUBJECTS_JSON,
    SWING_PP,
    ticker_of,
    to_state_path,
    VOL_DAYS,
    write_csv,
    write_preview,
)
from explain_requests import (
    ask_request,
    AskAnswer,
    build_requests,
    estimate,
)
from explain_results import (
    collect,
    daily_rows,
    extraction_models,
    merge_results,
    pvgo_settings,
    write_outputs,
)


def ask(explain_dir: Path, first: str, last: str, assume_yes: bool) -> None:
    state = N.load_state(explain_dir / STATE_JSON)
    if not state or not state.get("collected"):
        raise SystemExit(f"{explain_dir} has no collected explanation run - run (or --resume) step 2 first")
    migrate(state)
    days = read_csv(explain_dir / "pvgo_daily.csv")
    req = ask_request(state, days, first, last, N.load_codebook())
    cost = estimate([req], standard=True)
    print(f"One call to {MODEL} at standard price: ~${cost:.3f}")
    if not assume_yes and input("Make this call? [y/N] ").strip().lower() not in ("y", "yes"):
        print("Not run - nothing was called.")
        return
    msg = N.get_client().messages.create(**req["params"])
    if msg.stop_reason == "max_tokens":
        raise SystemExit("The answer was cut off at max_tokens - nothing written")
    text = next((b.text for b in msg.content if b.type == "text"), "")
    ans = AskAnswer.model_validate_json(text)
    p = N.BATCH_PRICING[MODEL]
    spent = 2 * (msg.usage.input_tokens * p.input + msg.usage.output_tokens * p.output) / 1e6
    stem = explain_dir / f"ask_{first}_{last}"
    stem.with_suffix(".json").write_text(json.dumps({**ans.model_dump(), "cost_usd": round(spent, 4),
                                                     "asked_at": N.now_iso()}, indent=1), encoding="utf-8")
    md = [f"# Why did {state['subject']}'s PVGO share move, {first} to {last}?", "", ans.answer, "",
          "| Expectation change | When | Direction | ~pp | Evidence |", "|---|---|---|---|---|"]
    md += [f"| {d.expectation_change} | {d.when} | {d.direction} | {d.approx_pp:+.1f} | {d.evidence_strength} |"
           for d in ans.drivers_of_move]
    md += ["", f"*Unexplained:* {ans.unexplained}", "", f"Confidence: {ans.confidence}. {MODEL}, ${spent:.3f}."]
    stem.with_suffix(".md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"${spent:.3f}; answer in {stem.with_suffix('.md')}\n\n{ans.answer}")


def prepare(args) -> tuple[dict, list[dict], Path]:
    """Step 1 and the request build. Writes the step-1 files and the preview; returns (state
    without a batch id, requests, out_dir)."""
    runs = find_runs(args.runs)
    subject, statements, analyst = load_news(runs)
    ticker = ticker_of(subject)
    if not ticker:
        raise SystemExit(f"No ticker in the subject '{subject}' - expected e.g. 'Costco (COST)'")
    config = json.loads(SUBJECTS_JSON.read_text(encoding="utf-8")) if SUBJECTS_JSON.is_file() else {}
    settings = config.get(ticker, {})
    sector = args.sector or settings.get("sector_etf")
    if not sector:
        raise SystemExit(f"No sector ETF for {ticker}: add it to {SUBJECTS_JSON.name} or pass --sector")
    news_days = sorted(statements)
    first = args.first or news_days[0][:7]
    last = args.last or news_days[-1][:7]
    pvgo, points, items = load_pvgo(ticker, Path(args.pvgo_dir), args.basis)
    # default: inside the one folder given (a folder of runs, or a single run), else
    # beside the runs given one by one
    parent = Path(args.runs[0]).resolve() if len(args.runs) == 1 else Path(os.path.commonpath([r.parent for r in runs]))
    out_dir = Path(args.out) if args.out else new_out_dir(parent)
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"Step 1: {subject}, {first} to {last}; {BASES[args.basis][1].split(':')[0]}; market model on the "
          f"S&P 500 and {sector}")
    prices = market_prices(out_dir, sector, pvgo[0]["date"], month_days(last)[-1])
    days = daily_split(pvgo, prices)
    first_day, last_day = f"{first}-01", month_days(last)[-1]
    if not any(d["date"] <= first_day and "z" in d for d in days):
        print(f"  ! not enough price history before {first} for the market model: periods start later")
    parts = periods(days, first_day, last_day)  # tags each day with its period_id, which month_split reads
    months_list = sorted({d["date"][:7] for d in days if first_day <= d["date"] <= last_day})
    months = [month_split(days, m) for m in months_list]
    releases = build_releases(points, items, days, parts, first_day, last_day, args.basis)
    write_csv(daily_rows([d for d in days if first_day <= d["date"] <= last_day]), DAILY_COLUMNS, out_dir / "pvgo_daily.csv")
    labels = ", ".join(f"{sum(p['label'] == x for p in parts)} {x}" for x in LABELS)
    print(f"  {len(parts)} periods ({labels}), {len(months)} months, {len(releases)} releases "
          f"({sum(bool(r['reconciliation']) for r in releases)} with a press-release reconciliation, "
          f"{sum(bool(r['item_sentences']) for r in releases)} with items named in its text per share, "
          f"{sum(bool(r['item_dollar_sentences']) for r in releases)} in dollars only)")
    if releases and not items:
        print("  ! no press-release reconciliations: run PVGO_Collection's history with RELEASE_ITEMS = True to "
              "name one-time items")
    codebook = N.load_codebook()
    reqs, refs = build_requests(subject, parts, statements, analyst, codebook, releases, args.basis)
    write_csv(months, MONTH_COLUMNS, out_dir / "pvgo_months.csv")
    write_csv(parts, PERIOD_COLUMNS, out_dir / "periods.csv")
    write_preview(reqs, out_dir / N.PREVIEW_JSONL)
    state = {"subject": subject, "ticker": ticker, "sector": sector, "basis": args.basis, "model": MODEL,
             "first": first, "last": last, "runs": [to_state_path(r) for r in runs],
             "pvgo_settings": pvgo_settings(pvgo, points, first_day, last_day),
             "extraction_models": extraction_models(runs),
             "pvgo_dir": to_state_path(args.pvgo_dir),
             "prompt_sha256": {k: sha256_of(p) for k, p in PROMPTS.items()},
             "config": {"FIT_DAYS": FIT_DAYS, "VOL_DAYS": VOL_DAYS, "SHOCK_Z": SHOCK_Z, "SWING_PP": SWING_PP,
                        "PERIOD_MAX_DAYS": PERIOD_MAX_DAYS, "MARKET_DRIVEN_SHARE": MARKET_DRIVEN_SHARE,
                        "NOISE_Z": NOISE_Z, "OUTLIER_SHARE": OUTLIER_SHARE, "NEWS_DAYS": NEWS_DAYS},
             "periods": parts, "months": months, "releases": releases, "refs": refs, "collected": False}
    return state, reqs, out_dir


def submit(state: dict, reqs: list[dict], out_dir: Path, dry_run: bool, assume_yes: bool) -> None:
    """Show the cost, ask, submit the batch, wait and collect. Only `reqs` are sent;
    collect() fills in just those (state['pending'])."""
    write_preview(reqs, out_dir / N.PREVIEW_JSONL)
    kinds = defaultdict(int)
    for r in reqs:
        kinds[r["custom_id"].split("_")[0]] += 1
    lines = [f"{n} {k} request(s)" for k, n in kinds.items()] + [f"{MODEL}, batch: ~${estimate(reqs):.2f}"]
    print(f"  preview: {out_dir / N.PREVIEW_JSONL}")
    if dry_run:
        print("Dry run - nothing submitted. Would send: " + "; ".join(lines))
        return
    if not N.confirm_submit(lines, assume_yes):
        print(f"Not submitted. The free step-1 files are in {out_dir}")
        return
    batch = N.get_client().messages.batches.create(requests=reqs)
    state.update(batch_id=batch.id, submitted_at=N.now_iso(), n_requests=len(reqs), collected=False,
                 pending=[r["custom_id"] for r in reqs])
    save(state, out_dir)
    print(f"Submitted batch {batch.id} ({len(reqs)} requests); state in {out_dir / STATE_JSON}. "
          f"If interrupted: python explain_run.py --resume {out_dir}")
    N.wait_for_batch(batch.id)
    collect(state, out_dir)


def update(out_dir: Path, dry_run: bool, assume_yes: bool) -> None:
    """Re-run step 1 for a collected run with its own settings and the current code,
    keep every answer it has, and submit only the requests it doesn't (e.g. the
    releases, for a run from before them)."""
    old = N.load_state(out_dir / STATE_JSON)
    if not old:
        raise SystemExit(f"No {STATE_JSON} in {out_dir}")
    if not old.get("collected"):
        raise SystemExit(f"{out_dir} has a batch that isn't collected yet - run --resume first")
    migrate(old)
    settings = argparse.Namespace(runs=[str(from_state_path(r)) for r in old["runs"]], first=old["first"],
                                  last=old["last"], sector=old["sector"], pvgo_dir=str(from_state_path(old["pvgo_dir"])),
                                  basis=old["basis"], out=str(out_dir), dry_run=dry_run, yes=assume_yes)
    state, reqs, _ = prepare(settings)
    done = merge_results(state, old)
    missing = [r for r in reqs if r["custom_id"] not in done]
    print(f"  kept {len(done)} answered request(s); {len(missing)} to send")
    # The run is consistent now: refreshed step-1 files, every kept answer in place. A
    # submitted batch flips `collected` back until it's collected.
    state["collected"] = True
    save(state, out_dir)
    write_outputs(state, out_dir)
    if missing:
        submit(state, missing, out_dir, dry_run, assume_yes)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--runs", nargs="+", help="run folders, or folders of runs (one run per month)")
    parser.add_argument("--from", dest="first", help="first month, YYYY-MM (default: the runs' first)")
    parser.add_argument("--to", dest="last", help="last month, YYYY-MM (default: the runs' last)")
    parser.add_argument("--sector", help="the sector ETF of the market model (default: explain_subjects.json)")
    parser.add_argument("--basis", choices=list(BASES), default="ttm_adjusted",
                        help="the EPS behind the no-growth value: ttm_adjusted (default), ttm, two_year or six_month - "
                             "PVGO_Collection's series for that basis")
    parser.add_argument("--pvgo-dir", default=str(PVGO_DIR), help="PVGO_Collection's Outputs_CSV_data folder")
    parser.add_argument("--out", help="output folder (default: explain_<time> beside the runs)")
    parser.add_argument("--dry-run", action="store_true", help="step 1 and the request preview only - free")
    parser.add_argument("--resume", metavar="EXPLAIN_DIR", help="collect a submitted batch")
    parser.add_argument("--update", metavar="EXPLAIN_DIR",
                        help="re-run step 1 for a collected run (same runs, basis, sector) and submit only the "
                             "requests it has no answer for (paid; asks first)")
    parser.add_argument("--ask", nargs=2, metavar=("FROM", "TO"), help="explain a period, YYYY-MM YYYY-MM (paid)")
    parser.add_argument("--explain-dir", help="with --ask: a collected explain_<time> folder")
    parser.add_argument("--yes", action="store_true", help="don't ask before the paid calls")
    args = parser.parse_args()

    if args.ask:
        if not args.explain_dir:
            parser.error("--ask needs --explain-dir")
        ask(Path(args.explain_dir), args.ask[0], args.ask[1], args.yes)
        return
    if args.resume:
        out_dir = Path(args.resume)
        state = N.load_state(out_dir / STATE_JSON)
        if not state:
            raise SystemExit(f"No {STATE_JSON} in {out_dir}")
        migrate(state)
        if not state.get("collected"):
            N.wait_for_batch(state["batch_id"])
            collect(state, out_dir)
        else:
            write_outputs(state, out_dir)
        return
    if args.update:
        update(Path(args.update), args.dry_run, args.yes)
        return
    if not args.runs:
        parser.error("--runs is required (or --resume / --update / --ask)")

    state, reqs, out_dir = prepare(args)
    if not reqs:
        print("No periods or releases with news - nothing to submit")
        return
    submit(state, reqs, out_dir, args.dry_run, args.yes)


if __name__ == "__main__":
    main()
