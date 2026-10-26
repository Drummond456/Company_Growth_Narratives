"""Explanation, step 2 (collect): the answers, the text checks, merging into an
existing run, and the readable outputs (explanations.md and the CSVs).
METHODOLOGY section 7.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from pathlib import Path

import narrative_common as N
from explain_detect import (
    BASES,
    CONFIDENCE,
    DAILY_COLUMNS,
    DATE_RE,
    LABELS,
    market_day_note,
    market_reaction,
    MARKET_DRIVEN_SHARE,
    MODEL,
    NOISE_Z,
    OUTLIER_SHARE,
    PERIOD_COLUMNS,
    PERIOD_RESULTS,
    PROSE_REF_RE,
    RATE_PARTS,
    read_csv,
    RELEASE_COLUMNS,
    RELEASE_RESULTS,
    RELEASE_SURPRISE_Z,
    save,
    SHOCK_Z,
    STATUSES,
    TTM_BASES,
    write_csv,
)
from explain_requests import (
    in_dollars,
    item_text,
    MODELS,
    quarter_step,
    reaction_text,
    release_items,
    with_per_share,
)


# --- Step 2: collect ---------------------------------------------------------------------


def evidence_refs(numbers: list[int], refs: list[str]) -> str:
    return "; ".join(refs[n - 1] if 0 < n <= len(refs) else f"#{n}?" for n in numbers)


def cite(text: str, refs: list[str]) -> str:
    """Statement numbers left in the prose, "(18)" or "[3, 15]", as their refs; a group
    with any number out of range is left alone."""
    def sub(m: re.Match) -> str:
        nums = [int(x) for x in re.findall(r"\d+", m.group(1))]
        return "(" + evidence_refs(nums, refs) + ")" if refs and all(0 < n <= len(refs) for n in nums) else m.group(0)
    return PROSE_REF_RE.sub(sub, text)


def check_text(state: dict) -> None:
    """The text checks, in place, on every answer (repeatable): statement numbers in the
    prose become refs; a YYYY-MM-DD outside the run's years +-1 is marked [date?], and
    each is listed in state['text_checks']. Entity claims (who joined the Dow) aren't
    checked: the cited statements are the check."""
    lo, hi = int(state["first"][:4]) - 1, int(state["last"][:4]) + 1
    refs, notes = state.get("refs", {}), []

    def fix(text: str, cid: str, where: str) -> str:
        def mark(m: re.Match) -> str:
            if lo <= int(m.group(1)) <= hi:
                return m.group(0)
            notes.append(f"{where}: {m.group(0).split(' ')[0]} is outside the run's years")
            return m.group(0) if m.group(2) else m.group(0) + " [date?]"
        return DATE_RE.sub(mark, cite(text, refs.get(cid, [])))

    for p in state["periods"]:
        for k in ("cause", "expected_before_vs_after"):
            if p.get(k):
                p[k] = fix(p[k], f"told_{p['period_id']}", f"{p['period_id']} {k}")
    state["text_checks"] = notes


def collect(state: dict, out_dir: Path) -> None:
    """Parse the batch in state['batch_id'] into the periods and releases whose requests it
    carried (state['pending']; all of them for a run from before --update). Everything else
    in the state is left as it is."""
    client = N.get_client()
    usage = N.new_usage()
    results = {}
    for r in client.messages.batches.results(state["batch_id"]):
        N.add_usage(usage, r)
        results[r.custom_id] = r
    parsed = {cid: N.read_result(r, MODELS[cid.split("_")[0]]) for cid, r in results.items()}
    pending = set(state["pending"]) if state.get("pending") is not None else None
    sent = lambda cid: cid in parsed or (pending is not None and cid in pending)  # noqa: E731
    refs = state["refs"]
    for p in state["periods"]:
        cid = f"told_{p['period_id']}"
        if not sent(cid):
            continue
        told, fail = parsed.get(cid, (None, "no result"))
        if fail:
            p["status"], p["failure"] = "failed", fail
        else:
            p["status"], p["failure"] = "answered", ""
            p.update(cause=told.cause, expected_before_vs_after=told.expected_before_vs_after,
                     drivers="; ".join(told.drivers), confidence=told.confidence,
                     evidence=evidence_refs(told.evidence, refs.get(cid, [])))
    for r in state.get("releases", []):
        cid = f"release_{r['release_date']}"
        if not sent(cid):
            continue
        res, fail = parsed.get(cid, (None, "no result"))
        if fail:
            r["failure"] = fail
        else:
            items = [with_per_share(i.model_dump(), r) for i in res.items]
            r.update(items=items, failure="", **release_items(r, items, state.get("basis", "two_year")))
    check_text(state)
    N.report_usage(usage, MODEL, "explain")
    p = N.BATCH_PRICING[MODEL]
    batch_cost = (usage["input"] * p.input + usage["output"] * p.output) / 1e6
    state.update(collected=True, collected_at=N.now_iso(), usage=usage,
                 cost_usd=round((state.get("cost_usd") or 0) + batch_cost, 4))
    state.setdefault("batches", [])
    if state["batch_id"] not in state["batches"]:
        state["batches"].append(state["batch_id"])
    save(state, out_dir)
    write_outputs(state, out_dir)


def write_outputs(state: dict, out_dir: Path) -> None:
    for r in state.get("releases", []):
        r["market_reaction"] = market_reaction(r)
    write_csv(state["periods"], PERIOD_COLUMNS, out_dir / "periods.csv")
    write_csv(state.get("releases", []), RELEASE_COLUMNS, out_dir / "releases.csv")
    (out_dir / "explanations.md").write_text(render_md(state), encoding="utf-8")
    print(f"Wrote periods.csv, releases.csv and explanations.md to {out_dir}")


# --- explanations.md ---------------------------------------------------------------------------
# Each month is its bridge as a table, then its timeline: every period in date order, one
# list item each, with its label, its numbers, the told cause and its confidence, and the release blocks after
# the periods they overlap. Every answer is shown with the labels the calls gave it; the code's labels say
# how much the market explains, and a cause found where the market explains the move (or where the
# company-specific move is within noise) is marked suspect: the news is company-specific. Each told cause
# ends with the refs it cites.

SUSPECT = ("market-driven", "within noise")  # where a company-news cause is suspect


def ref_list(evidence: str, month: str) -> str:
    """' [A0065, A0064-H, A0061-H]': an answer's refs, without the 'YYYY-MM/' of the section's
    month (a ref from another month keeps it); '' when it cites none. The website reads them."""
    refs = [r.strip() for r in (evidence or "").split(";") if r.strip()]
    return " [" + ", ".join(r.removeprefix(f"{month}/") for r in refs) + "]" if refs else ""


# Dates are written out in explanations.md: "March 8, 2024", a range "March 1–7, 2024", a
# month "March 2024". The model's own ISO dates in its answers are written out too (written_dates), after the
# text checks. Refs keep their form ("2024-03/A0012-S01", "R2024-03-07").
MONTHS = ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
          "November", "December")
ISO_DATE_RE = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")


def long_date(iso: str, year: bool = True) -> str:
    y, m, d = iso[:10].split("-")
    return f"{MONTHS[int(m) - 1]} {int(d)}" + (f", {y}" if year else "")


def long_month(key: str) -> str:
    """'2024-03' -> 'March 2024'; app.js and update_data.py read the month headings in this form."""
    return f"{MONTHS[int(key[5:7]) - 1]} {key[:4]}"


def date_range(start: str, end: str) -> str:
    if start == end:
        return long_date(start)
    if start[:7] == end[:7]:
        return f"{long_date(start, False)}–{int(end[8:10])}, {end[:4]}"
    if start[:4] == end[:4]:
        return f"{long_date(start, False)} – {long_date(end)}"
    return f"{long_date(start)} – {long_date(end)}"


def written_dates(text: str) -> str:
    return ISO_DATE_RE.sub(lambda m: long_date(m.group(0)), text)


def period_when(p: dict) -> str:
    return date_range(p["start"], p["end"]) + (f" ({p['days']} days)" if p["days"] > 1 else "")


def bridge_table(m: dict, releases: list[dict]) -> list[str]:
    """The month's change as a table that adds up: the price's market and company-specific
    parts, each release's EPS update and the rates. A month whose releases don't add up to
    its EPS update gets one EPS row."""
    rows = [("Price: market (S&P 500 and sector)", m["market_pp"]), ("Price: company-specific", m["company_pp"])]
    if releases and abs(sum(r["eps_update_pp"] for r in releases) - m["eps_update_pp"]) < 0.01:
        rows += [(f"EPS update: release {r['release_date']}", r["eps_update_pp"]) for r in releases]
    elif round(m["eps_update_pp"], 2):
        rows.append(("EPS update", m["eps_update_pp"]))
    if all(k in m for k in RATE_PARTS):
        rows.append(("Rates: 10-year Treasury", m["rate_treasury_pp"]))
        if round(m["rate_erp_pp"], 2):  # zero throughout with a fixed ERP
            rows.append(("Rates: equity risk premium", m["rate_erp_pp"]))
        rows.append(("Rates: beta re-estimate", m["rate_beta_pp"]))
    else:
        rows.append(("Rates/other", m["rate_other_pp"]))
    return (["| Part | pp |", "|---|---|"] + [f"| {part} | {pp:+.2f} |" for part, pp in rows]
            + [f"| **Total** | **{m['total_change_pp']:+.2f}** |"])


def period_item(p: dict, sector: str) -> str:
    """'- **P07 March 8, 2024 · outlier** · stock ... · market ..., company-specific ... ·
    **medium confidence** (25 statements) · Cause: ... [refs]'. The website finds a period by
    its '**P07 ' opening, its refs by the closing bracket, and its cause after '· Cause'."""
    market = "".join(f" · {market_day_note(d)}" + (f" on {d['date']}" if p["days"] > 1 else "")
                     for d in p.get("market_days") or [])
    head = (f"- **{p['period_id']} {period_when(p)} · {p['label']}** · stock {p['ret_pct']:+.1f}% "
            f"(S&P {p['spx_ret_pct']:+.1f}%, {sector} {p['sector_ret_pct']:+.1f}%) · market {p['market_pp']:+.2f}pp, "
            f"company-specific {p['company_pp']:+.2f}pp (the market explains {p['market_share']:.0%}; "
            f"{abs(p['z']):.1f}x normal noise){market}")
    if p.get("failure"):
        return f"{head} · *explanation failed: {p['failure']}*"
    if p.get("status") != "answered":
        return f"{head} · **{p.get('status') or 'not explained'}**"
    n, a = p["n_statements"], p.get("n_articles") or 0
    news = f"{n} statement{'s' * (n != 1)}" + (f", {a} article{'s' * (a != 1)}" if a else "")
    head += f" · **{outcome(p)}** ({news})"
    refs = ref_list(p.get("evidence"), p["month"])
    # Confidence none is the call's own "no cause" (the prompt asks for an empty cause, but it sometimes
    # writes why nothing explains the move): shown as its reason, not as a cause, and not marked suspect
    if outcome(p) == NO_CAUSE:
        return f"{head}" + (f" · {p['cause']}" if p.get("cause") else "") + refs
    # The cause is the best news found, untested; in a market-driven or within-noise period the
    # company-specific move it explains is small or ordinary
    cause = f"Cause, suspect in a {p['label']} period" if p["label"] in SUSPECT else "Cause"
    return f"{head} · {cause}: {p['cause']}{refs}"


def dollars(x: float) -> str:
    return f"{'+' if x >= 0 else '-'}${abs(x):.2f}"


def release_refs(r: dict) -> list[str]:
    """The press releases a release block cites, as 'R<release date>': its own (when PVGO_Collection
    read its filing) and, when it names items, the one of the quarter leaving the TTM. The website
    resolves them from PVGO_Collection's release items (update_data.py)."""
    refs = [f"R{r['release_date']}"] if r.get("reconciliation_note") or r.get("item_sentences") else []
    gone = r.get("leaving") or {}
    if gone.get("item_sentences") or gone.get("item_dollar_sentences") or gone.get("reconciliation"):
        refs.append(f"R{gone['release_date']}")
    return refs


# A release block is three parts: the EPS change (facts), the one-time items the press
# releases name with the change less them (extracted by the release call, the arithmetic by code), and the
# market reaction (by code). It's a <div class="release"> (outlined on the website), so its lists stay apart
# from the period list around it; the head line ends with the press releases it cites.
def release_block(r: dict, basis: str) -> list[str]:
    """'**Release March 7, 2024** ... [R2024-03-07]', then *EPS change*, *One-time items
    identified* (when the press releases name any) and *Market reaction*, each with its bullets."""
    ttm = basis in TTM_BASES
    ids = [i for i in (r.get("period_ids") or "").split("; ") if i]
    refs = release_refs(r)
    out = ['<div class="release">', "",
           f"**Release {long_date(r['release_date'])}** · quarter ended {long_date(r['quarter_end'])}"
           + (f" · in {', '.join(ids)}" if ids else "") + (f" [{', '.join(refs)}]" if refs else ""), ""]
    q = quarter_step(r, basis)
    effect = f"; growth-share effect {r['eps_update_pp']:+.2f}pp (price held still)"
    if q:
        line = (f"{dollars(q['step'])} ({r['eps_before']} -> {r['eps_after']}): the quarter ended "
                f"{long_date(q['new']['end'])} (${q['new']['eps']:.2f}) replaces the one ended "
                f"{long_date(q['gone']['end'])} (${q['gone']['eps']:.2f})"
                + (f", investment adjustment {q['adjustment']:+.2f}" if round(q["adjustment"], 2) else "")
                + (f", restated earlier quarters {q['rest']:+.2f}" if round(q["rest"], 2) else ""))
    elif r["eps_before"]:
        line = f"{dollars(float(r['eps_after']) - float(r['eps_before']))} ({r['eps_before']} -> {r['eps_after']})"
    else:
        line = f"EPS {r['eps_after']}"
    out += [f"*{'TTM EPS' if ttm else 'EPS'} change*", "", f"- {line}{effect}", ""]
    if r.get("failure"):
        out += [f"*One-time items: extraction failed: {r['failure']}*", ""]
    elif r.get("items"):
        out += ["*One-time items identified*", ""]
        out += [f"- {'Entering' if i['quarter'].startswith('new quarter') else 'Leaving'}: {item_text(i)}"
                for i in r["items"]]
        if r.get("eps_change_ex_items") not in ("", None):
            estimated = any(in_dollars(i) for i in r["items"])
            out.append(f"- TTM EPS change less one-time items: {dollars(r['eps_change_ex_items'])}"
                       + (" (estimated: some items are stated in dollars only)" if estimated else ""))
        if r.get("items_check"):
            out.append(f"- [amount not found in the press release: {r['items_check']}]")
        out.append("")
    z = f", {abs(float(r['reaction_z'])):.1f}x normal noise" if r.get("reaction_z") not in ("", None) else ""
    out += ["*Market reaction*", "",
            f"- {market_reaction(r).capitalize()}: company-specific stock return {reaction_text(r)}, against the "
            f"market model{z}", "", "</div>"]
    return out


def settings_line(state: dict) -> str:
    """How the run was made: the EPS basis, the cost of equity's parts, the market model and
    the models. Times are UTC (the explain_<time> folder name is local time)."""
    pv = state.get("pvgo_settings") or {}
    parts = [f"EPS basis: {BASES[state.get('basis', 'two_year')][1].split(':')[0]}"]
    if pv:
        parts.append(f"cost of equity: 10-year Treasury + {pv['beta']} x {pv['erp']}")
    parts.append(f"market model: S&P 500 + {state.get('sector') or '?'}")
    if state.get("extraction_models"):
        parts.append("statements: " + ", ".join(state["extraction_models"]))
    when = (state.get("collected_at") or "")[:16].replace("T", " ")
    parts.append(f"explanations: {state.get('model', MODEL)}" + (f", collected {when} UTC" if when else ""))
    return "; ".join(parts) + "."


def pvgo_settings(pvgo: list[dict], points: list[dict], first_day: str, last_day: str) -> dict:
    """The beta and ERP behind PVGO_Collection's series, read from its files."""
    src = next((p["beta_source"] for p in reversed(points) if p.get("beta_source")), "")
    m = re.match(r"own beta: (\d+ monthly returns vs the S&P 500)", src)
    beta = (f"own beta ({m.group(1)}, {'Blume-adjusted' if 'Blume' in src else 'raw'})" if m
            else src.split(":")[0].strip() or "beta ?")
    erps = {r["erp"] for r in pvgo if first_day <= r["date"] <= last_day and r.get("erp") is not None}
    erp = ("Damodaran's implied ERP by year" if len(erps) > 1 else
           f"a fixed ERP of {next(iter(erps)):.2f}%" if erps else "ERP ?")
    return {"beta": beta, "erp": erp}


def extraction_models(runs: list[Path]) -> list[str]:
    """The models that wrote the runs' statements (narrative_units' model column)."""
    return sorted({u["model"] for run in runs for u in read_csv(run / N.OUTPUT_CSV) if u.get("model")})


def found_cause(p: dict) -> bool:
    """A told cause given with medium or high confidence: what the placebo line counts."""
    return bool(p.get("cause")) and p.get("confidence") in ("high", "medium")


NO_CAUSE = "no cause found"
OUTCOMES = [f"{c} confidence" for c in CONFIDENCE[:3]] + [NO_CAUSE] + STATUSES[1:] + ["not explained"]


def outcome(p: dict) -> str:
    """A period's answer in a word or two: the told cause's confidence, no cause found, or
    why there's no answer (no news collected, failed, not explained)."""
    if p.get("status") != "answered":
        return p.get("status") or "not explained"
    conf = p.get("confidence") or "none"
    return NO_CAUSE if conf == "none" or not p.get("cause") else f"{conf} confidence"


def label_table(periods: list[dict]) -> list[str]:
    """Per label: the periods, how many got a cause with medium or high confidence (the
    placebo check: in market-driven and within-noise periods those are suspect), and every
    answer's confidence."""
    rows = ["| Label | Periods | Cause found, medium or high confidence | Answers |", "|---|---|---|---|"]
    for label in LABELS:
        ps = [p for p in periods if p["label"] == label]
        counts = Counter(outcome(p) for p in ps)
        rows.append(f"| {label}{' (suspect if explained)' if label in SUSPECT else ''} | {len(ps)} | "
                    f"{sum(found_cause(p) for p in ps)} | "
                    + ", ".join(f"{o} {counts[o]}" for o in OUTCOMES if counts[o]) + " |")
    return rows


def render_md(state: dict) -> str:
    periods, months, releases = state["periods"], state["months"], state.get("releases", [])
    basis, sector = state.get("basis", "two_year"), state.get("sector") or "sector"
    control = [p for p in periods if p["label"] in SUSPECT and p.get("status") == "answered"]
    tested = [p for p in periods if p["label"] not in SUSPECT and p.get("status") == "answered"]
    # The opening, in sections: how a month is split and its periods explained, the refs, what the
    # explanations found (the placebo check), the releases, and the run's settings
    lines = [f"# Why {state['subject']}'s PVGO share moved: {long_month(months[0]['month'])} to "
             f"{long_month(months[-1]['month'])}", "",
             "### How each month is split", "",
             "Each month opens with its bridge: the growth-share change (PVGO / price, in pp) split exactly into "
             "the price's **market** part (S&P 500 and sector) and its **company-specific** part, the **EPS update** "
             "at an earnings release, and the cost of equity's **rates**. Then its timeline: the month cut into "
             f"consecutive periods by code (a day at least {SHOCK_Z}x its normal company-specific move alone, the "
             "rest in swings of the price-driven path), each labelled by how much of its price move the market "
             "explains:", "",
             f"- **market-driven:** the market explains {MARKET_DRIVEN_SHARE:.0%} or more;",
             f"- **within noise:** less than that, but the company-specific move is under {NOISE_Z}x its normal size "
             "over that many days;",
             f"- **divergent:** the market explains {OUTLIER_SHARE:.0%}-{MARKET_DRIVEN_SHARE:.0%}, and the "
             "company-specific move stands out;",
             f"- **outlier:** the market explains {OUTLIER_SHARE:.0%} or less, and the company-specific move stands "
             "out.", "",
             "### How each period is explained", "",
             "Every period is explained the same way: one call reads the period's news (from the day before to "
             "the day after) and the stock's own daily moves, without the market's figures or the label, and names "
             "the change in expectations that most likely caused the move, with its confidence. A cause "
             "is the model's reading of the news, not a tested fact, and its confidence is the model's own: the "
             "placebo check below is the test of how often it finds causes that aren't there. The labels are "
             "computed.", "",
             "### Citations", "",
             "Each cause ends with the refs it cites, in brackets: `A0077-S01` is a statement, `A0077-H` a "
             "headline, and a bare `A0065` an analyst article read as headline plus opening, from the month's run (a "
             "ref from another month starts with its `YYYY-MM/`). Dates are written out; refs keep their own form.", "",
             "### Findings and the placebo check", "",
             f"{len(periods)} periods, {len(months)} months, {len(releases)} earnings releases, from "
             f"{len(state['runs'])} runs.", ""] + label_table(periods) + [
             "",
             f"**Placebo check:** in the {len(control)} market-driven or within-noise periods with news, the period "
             f"call found a cause with medium or high confidence in {sum(found_cause(p) for p in control)}; in the "
             f"{len(tested)} divergent or outlier periods, in {sum(found_cause(p) for p in tested)}. The news is "
             "company-specific, so a cause where the market explains the move, or where the company-specific move "
             "is ordinary noise, is suspect: the first count is how often the explanations find causes that aren't "
             "there.", "",
             "### Earnings releases", "",
             "Each earnings release has a block after the period holding its measurement day: the EPS change and "
             "the quarters behind it (filings); the one-time items the press releases name, entering or leaving "
             "the TTM, and the change less them (the release call extracts the items, code checks each amount "
             "against the press-release text and does the arithmetic; each block cites the press releases, `R` and "
             "the release date); and the market reaction, by code: a "
             f"**results surprise** when the company-specific stock return from the release to the measurement "
             f"day is at least {RELEASE_SURPRISE_Z}x its normal size over those days, else **results expected**.",
             "",
             "Levels: the growth share's level depends on the EPS basis. One-time charges kept in the TTM lower the "
             "EPS and raise the growth share for the four quarters they're in (the Release blocks name those the press "
             "releases name), so compare levels across years or companies with them in mind.", ""]
    if releases:
        lines += ["| Release | Growth-share effect of the EPS update (pp, price held still) | Company-specific stock "
                  "return, release to measurement day (%) |", "|---|---|---|"]
        lines += [f"| {r['release_date']} | {r['eps_update_pp']:+.2f} | {r['reaction_company_pct']:+.1f} |"
                  for r in releases]
        lines.append("")
    lines += ["### Settings", "", settings_line(state), ""]
    by_month, rel_month = defaultdict(list), defaultdict(list)
    for p in periods:
        by_month[p["month"]].append(p)
    for r in releases:
        rel_month[r["measurement_date"][:7]].append(r)
    for m in months:
        rels = rel_month.get(m["month"], [])
        lines += [f"## {long_month(m['month'])}: growth share {m['share_start']:.1f}% -> {m['share_end']:.1f}% "
                  f"({m['total_change_pp']:+.2f}pp)", ""] + bridge_table(m, rels) + [""]
        # The timeline: periods by start, each release after the period holding its measurement day
        items = [((p["start"], 0), [period_item(p, sector)]) for p in by_month.get(m["month"], [])]
        items += [((r["measurement_date"], 1), [""] + release_block(r, basis) + [""]) for r in rels]
        for _, block in sorted(items, key=lambda x: x[0]):
            lines += block
        lines.append("")
    if state.get("text_checks"):
        lines += ["**Text checks** (dates outside the run's years, marked [date?] in the text):", ""]
        lines += [f"- {n}" for n in state["text_checks"]] + [""]
    if state.get("cost_usd") is not None:
        lines.append(f"Batch cost: ${state['cost_usd']:.3f}" + (f" over {len(state['batches'])} batches"
                                                                 if len(state.get("batches", [])) > 1 else "") + ".")
    if state.get("anonymize_cost_usd"):  # a run made with a blind read (2026-10-22) also paid to anonymize its news
        lines.append(f"Anonymize calls for the blind read this run was made with: ${state['anonymize_cost_usd']:.3f} "
                     "(standard price).")
    return written_dates("\n".join(lines)) + "\n"


def daily_rows(days: list[dict]) -> list[dict]:
    keys = DAILY_COLUMNS
    return [{k: (round(d[k], 4) if isinstance(d.get(k), float) else d.get(k, "")) for k in keys} for d in days]


def merge_results(new: dict, old: dict) -> set[str]:
    """--update: copy the old run's answers onto the recomputed periods (by id, start and
    end) and releases (by date); returns the custom ids already answered."""
    done = set()
    old_periods = {(p["period_id"], p["start"], p["end"]): p for p in old.get("periods", [])}
    for p in new["periods"]:
        o = old_periods.get((p["period_id"], p["start"], p["end"]))
        if o and o.get("status") == "answered":
            p.update({k: o[k] for k in PERIOD_RESULTS if k in o})
            done.add(f"told_{p['period_id']}")
    old_releases = {r["release_date"]: r for r in old.get("releases", [])}
    for r in new["releases"]:
        o = old_releases.get(r["release_date"], {})
        if o.get("items") is not None and not o.get("failure"):
            r.update({k: o[k] for k in RELEASE_RESULTS if k in o})
            done.add(f"release_{r['release_date']}")
    for k in ("cost_usd", "anonymize_cost_usd", "batches", "collected_at"):
        if k in old:
            new[k] = old[k]
    new.setdefault("batches", [old["batch_id"]] if old.get("batch_id") else [])
    return done
