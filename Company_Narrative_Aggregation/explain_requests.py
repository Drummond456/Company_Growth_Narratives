"""Explanation, step 2 (build the batch) and step 3's request: the answer formats, which
news each call sees, the wording of moves, the requests and the cost estimate.
METHODOLOGY section 7.
"""

from __future__ import annotations

import re
from collections import defaultdict
from datetime import date
from typing import Literal

from pydantic import BaseModel

import narrative_common as N
from explain_detect import (
    BASES,
    BRIDGE,
    CONFIDENCE,
    days_between,
    ITEM_KINDS,
    ITEM_QUARTERS,
    ITEM_TAX,
    ITEM_TAX_RATE,
    ITEM_UNITS,
    market_reaction,
    MAX_PERIOD_ARTICLES,
    MAX_PERIOD_STATEMENTS,
    MAX_TOKENS,
    MODEL,
    name_of,
    NEWS_DAYS,
    OUTPUT_TOKENS,
    PROMPTS,
    SCHEMA_OVERHEAD_TOKENS,
    shift,
    TTM_BASES,
)


# --- Answer formats ----------------------------------------------------------------------


class ToldCause(BaseModel):
    cause: str
    expected_before_vs_after: str
    drivers: list[str]
    evidence: list[int]
    confidence: Literal["high", "medium", "low", "none"]


class OneTimeItem(BaseModel):
    name: str
    amount: float  # positive: net per diluted share on today's share basis, or $ millions (unit)
    unit: Literal["per diluted share", "$ millions"]
    tax: Literal["pre-tax", "after tax or a tax item"]  # for a $ amount; code taxes a pre-tax one
    kind: Literal["benefit or gain", "charge or loss"]
    quarter: Literal["new quarter (entering)", "quarter leaving the TTM"]


class ReleaseItems(BaseModel):
    items: list[OneTimeItem]


class AskDriver(BaseModel):
    expectation_change: str
    when: str
    direction: Literal["up", "down"]
    approx_pp: float
    evidence_strength: Literal["strong", "moderate", "weak"]


class AskAnswer(BaseModel):
    answer: str
    drivers_of_move: list[AskDriver]
    unexplained: str
    confidence: Literal["high", "medium", "low"]


def _obj(required: dict) -> dict:
    return {"type": "object", "additionalProperties": False, "required": list(required), "properties": required}


def schemas(families: list[str]) -> dict[str, dict]:
    text, ints = {"type": "string"}, {"type": "array", "items": {"type": "integer"}}
    enum = lambda values: {"type": "string", "enum": values}  # noqa: E731
    return {
        "told": _obj({"cause": text, "expected_before_vs_after": text,
                      "drivers": {"type": "array", "items": enum(families)}, "evidence": ints,
                      "confidence": enum(CONFIDENCE)}),
        "release": _obj({"items": {"type": "array", "items": _obj({
            "name": text, "amount": {"type": "number"}, "unit": enum(ITEM_UNITS), "tax": enum(ITEM_TAX),
            "kind": enum(ITEM_KINDS), "quarter": enum(ITEM_QUARTERS)})}}),
        "ask": _obj({"answer": text,
                     "drivers_of_move": {"type": "array", "items": _obj({
                         "expectation_change": text, "when": text, "direction": enum(["up", "down"]),
                         "approx_pp": {"type": "number"},
                         "evidence_strength": enum(["strong", "moderate", "weak"])})},
                     "unexplained": text, "confidence": enum(CONFIDENCE[:3])}),
    }


def prompt(kind: str, subject: str, families_text: str) -> str:
    text = PROMPTS[kind].read_text(encoding="utf-8").strip()
    return text.replace("{subject}", subject).replace("{name}", name_of(subject)).replace("{drivers}", families_text)


def driver_families(codebook: list[dict]) -> tuple[list[str], str]:
    """The value-driver families (codebook order) and the list the prompts show:
    '- Revenue growth: Total accessible market; Market share; ...'."""
    drivers = N.driver_codes(codebook)
    topics = {row["code"]: row.get("topic", "") for row in codebook}
    fams: dict[str, list[str]] = {}
    for code, fam in drivers.items():
        fams.setdefault(fam, []).append(topics.get(code, code))
    return list(fams), "\n".join(f"- {fam}: {'; '.join(t)}" for fam, t in fams.items())


def window_statements(statements: dict, days: list[str], cap: int) -> list[dict]:
    """The statements published on these days, identical texts once, at most `cap`."""
    out, seen = [], set()
    for d in days:
        for s in statements.get(d, []):
            if s["text"].lower() in seen:
                continue
            seen.add(s["text"].lower())
            out.append({**s, "day": d})
    return out[:cap]


def numbered(items: list[dict], dated: bool, start: int = 1) -> str:
    return "\n".join(f"[{i}] {s['day'] + ' ' if dated else ''}({s['headline']}) {s['text']}"
                     for i, s in enumerate(items, start))


def period_window(p: dict) -> list[str]:
    """A period's news days: from NEWS_DAYS before its start to as many after its end."""
    return days_between(shift(p["start"], -NEWS_DAYS), shift(p["end"], NEWS_DAYS))


# --- Step 2: requests ----------------------------------------------------------------------


def reaction_text(r: dict) -> str:
    """A release's company-specific reaction with its window: over how many trading days, and
    by day when more than one."""
    n, by_day = r.get("reaction_days") or 1, r.get("reaction_by_day") or []
    text = f"{r['reaction_company_pct']:+.1f}%"
    if n > 1:
        text += f" over {n} trading days"
        if by_day:
            text += " (" + ", ".join(f"{x['date']} {x['company_ret_pct']:+.1f}%" for x in by_day) + ")"
    return text


# The told call sees the stock's own moves only: no S&P, sector, market share, label or
# PVGO figure. Every period is explained, so a cause found where the market explains the move (or where
# the company-specific move is within noise) is a built-in placebo: the news is company-specific.
def move_text(p: dict) -> str:
    """The period as its told call reads it: the dates and the stock's daily and total moves."""
    when = p["start"] if p["days"] == 1 else f"{p['start']} to {p['end']} ({p['days']} trading days)"
    daily = "; ".join(f"{d['date']} {d['ret_pct']:+.1f}%" for d in p["daily"])
    return (f"Period: {when}.\nThe stock's daily moves: {daily}."
            + (f"\nOver the period (sum): {p['ret_pct']:+.1f}%." if p["days"] > 1 else ""))


def request(cid: str, kind: str, system: str, user: str, schema: dict) -> dict:
    return {"custom_id": cid, "params": {
        "model": MODEL, "max_tokens": MAX_TOKENS[kind], "system": [{"type": "text", "text": system}],
        "messages": [{"role": "user", "content": user}],
        "output_config": {"format": {"type": "json_schema", "schema": schema}}}}


def press_release_items(r: dict) -> list[str]:
    """The items a press release names in its text, per share and in dollars only
    (PVGO_Collection's item sentences), or, when neither they nor a reconciliation table
    exist, that its one-time items are unknown: the 2026-10-20 COST run read "no table" as
    "no items" and missed $0.21, $0.14 and $0.22 tax benefits stated in the text."""
    out = []
    if r.get("item_sentences"):
        out += ["Press release, per-share items named in its text:", r["item_sentences"]]
    if r.get("item_dollar_sentences"):  # a company that states its items in dollars only (Meta)
        out += ["Press release, items named in its text in dollars only (no per-share amount):",
                r["item_dollar_sentences"]]
    if not out and not r.get("reconciliation"):
        out = ["Press release text: no item named with an amount. With no reconciliation either, whether this "
               "quarter holds one-time items is unknown, not zero."]
    return out


# On TTM the step is the newest quarter minus the one it drops, and PVGO_Collection writes both, so the
# release call is given them rather than left to work them out.
def _quarter(text: str) -> dict:
    """'2024-09-01 5.2800 derived: FY - Q1-Q3' -> its end, EPS and how it was reported."""
    end, eps, source = text.split(" ", 2)
    return {"end": end, "eps": float(eps),
            "source": "derived: the 10-K's annual EPS minus Q1-Q3" if source.startswith("derived") else source}


def quarter_step(r: dict, basis: str) -> dict | None:
    """On TTM, the release's EPS step from its quarters: the newest quarter, the one it drops,
    the change in the investment adjustment (adjusted TTM), and what's left of the step after
    them (a restated earlier quarter; about zero otherwise). None without the quarters."""
    c, prev = r["eps_composition"], r.get("prev_composition") or {}
    if basis not in TTM_BASES or not c.get("ttm_quarters") or not c.get("ttm_quarter_leaving") or not r["eps_before"]:
        return None
    new, gone = _quarter(c["ttm_quarters"].split("; ")[-1]), _quarter(c["ttm_quarter_leaving"])
    adjustment = (float(c.get("investment_adjustment_per_share") or 0)
                  - float(prev.get("investment_adjustment_per_share") or 0)) if basis == "ttm_adjusted" else 0.0
    step = float(r["eps_after"]) - float(r["eps_before"])
    return {"new": new, "gone": gone, "quarters": new["eps"] - gone["eps"], "adjustment": adjustment, "step": step,
            "rest": step - (new["eps"] - gone["eps"]) - adjustment}


def quarter_step_text(q: dict) -> str:
    """The step's quarters as the release call reads them."""
    text = (f"Quarters behind the step (PVGO_Collection): the new quarter, ended {q['new']['end']}, {q['new']['eps']:.2f} "
            f"({q['new']['source']}), replaces the quarter ended {q['gone']['end']}, {q['gone']['eps']:.2f} "
            f"({q['gone']['source']}): {q['quarters']:+.2f} per share")
    if round(q["adjustment"], 2):
        text += f", and the investment adjustment changed by {q['adjustment']:+.2f}"
    if round(q["rest"], 2):
        return text + (f". The EPS step is {q['step']:+.2f}: the other {q['rest']:+.2f} comes from earlier quarters "
                       "restated since the previous release.")
    return text + f". Together that is the whole EPS step, {q['step']:+.2f}."


def release_facts(r: dict, basis: str) -> str:
    """What a release call reads: the EPS update and how it's built, and the press releases'
    one-time items (this quarter's and, on TTM, the quarter leaving)."""
    def comp(c: dict) -> str:
        adjusted = ""
        if c.get("eps_ttm_adjusted"):  # the adjusted TTM and what was taken out
            per_share = float(c.get("investment_adjustment_per_share") or 0)
            gains = float(c.get("investment_gains_ttm") or 0)
            adjusted = (f"adjusted TTM {c['eps_ttm_adjusted']} (= TTM {c.get('eps_ttm') or '-'} "
                        f"{'+' if per_share >= 0 else '-'} {abs(per_share):.4f} per share: the TTM's "
                        f"{'gains' if gains >= 0 else 'losses'} on investments of ${abs(gains) / 1e6:,.0f}M excluded, "
                        f"less 25% tax; {c.get('investment_gain_tags') or '-'}); ")
        return (adjusted + f"TTM {c.get('eps_ttm') or '-'} ({c.get('eps_period') or '-'}); 2-year {c.get('eps_two_year') or '-'} "
                f"({c.get('two_year_period') or '-'}; trimmed quarters: {c.get('two_year_dropped') or '-'}); "
                f"6-month {c.get('eps_six_month') or '-'}")
    when = r["release_date"] + (f" {r['release_time']} New York time" if r["release_time"] else "")
    lines = [
        f"Release: quarter ended {r['quarter_end']}; earnings released {when} ({r['release_form']}); the EPS update "
        f"takes effect at the close of {r['measurement_date']}.",
        f"EPS basis: {BASES[basis][1]}. EPS used: {r['eps_before'] or '?'} -> {r['eps_after']}.",
        f"EPS figures at this release: {comp(r['eps_composition'])}.",
        f"At the previous release: {comp(r['prev_composition']) if r['prev_composition'] else 'not available'}.",
    ]
    q = quarter_step(r, basis)
    lines += [quarter_step_text(q)] if q else []
    lines += ["Data flags on the quarters (PVGO_Collection): " + ("; ".join(r["pvgo_flags"]) or "none")]
    lines += ["", "Press release, GAAP-to-adjusted EPS reconciliation:",
              r["reconciliation"] or f"(not available: {r['reconciliation_note'] or 'no table'})"]
    lines += press_release_items(r)
    gone = r.get("leaving") or {}
    if gone:
        lines += ["", f"Quarter leaving the TTM: the quarter ended {gone['quarter_end']} (released {gone['release_date']}), "
                      "replaced by this release's quarter. Its press-release reconciliation:",
                  gone["reconciliation"] or "(not available)"]
        lines += press_release_items(gone)
    for s in r.get("splits") or []:
        n = f"{s['ratio']:g}"
        before = ([] if r["release_date"] >= s["date"] else ["this release's"]) + (
            ["the year-ago quarter's"] if gone and gone["release_date"] < s["date"] else [])
        lines += ["", f"Share basis: the EPS figures above are on today's share basis, after the {n}-for-1 split on "
                      f"{s['date']}. Per-share amounts in press releases from before it ({' and '.join(before)} "
                      f"reconciliation) are on the old basis: divide them by {n} before comparing them with the EPS "
                      "above, and quote them divided."]
    return "\n".join(lines)


# The release call only extracts the one-time items; code does the rest (the EPS change, the arithmetic and
# the market reaction), since items listed as free text get missed.
def in_dollars(i: dict) -> bool:
    """An item the press release states in dollars only (an older answer without the field is per share)."""
    return i.get("unit") == ITEM_UNITS[1]


def with_per_share(i: dict, r: dict) -> dict:
    """The answer's item with its `per_share`: the amount as given, or for one stated in
    dollars only, over its quarter's diluted shares (this release's, or the leaving
    quarter's), less ITEM_TAX_RATE when pre-tax. None without a share count."""
    if not in_dollars(i):
        return {**i, "per_share": i["amount"]}
    entering = i["quarter"].startswith("new quarter")
    shares = float((r if entering else r.get("leaving") or {}).get("diluted_shares") or 0)
    after_tax = i["amount"] * 1e6 * ((1 - ITEM_TAX_RATE) if i["tax"] == ITEM_TAX[0] else 1)
    return {**i, "per_share": round(after_tax / shares, 4) if shares else None, "diluted_shares": shares or None}


def item_effect(i: dict) -> float:
    """An item's effect on the TTM step: a benefit entering or a charge leaving raises it.
    Zero for a dollar item without a share count."""
    entering, benefit = i["quarter"].startswith("new quarter"), i["kind"].startswith("benefit")
    per_share = i["per_share"] or 0.0
    return per_share if entering == benefit else -per_share


def item_text(i: dict) -> str:
    """'Q4 restructuring, charge $0.21 (+0.21 to the step)', or for a dollar item the amount as
    stated and the per-share estimate code made of it."""
    kind = i["kind"].split(" ")[0]
    if not in_dollars(i):
        return f"{i['name']}, {kind} ${i['per_share']:.2f} ({item_effect(i):+.2f} to the step)"
    pre_tax = i["tax"] == ITEM_TAX[0]
    stated = f"{i['name']}, {kind} ${i['amount']:,.0f}M {'pre-tax' if pre_tax else 'after tax'}"
    if i.get("per_share") is None:
        return stated + " (no diluted share count: not put per share, not in the step)"
    return (f"{stated}, about ${i['per_share']:.2f} per share ({item_effect(i):+.2f} to the step; estimated: "
            + (f"less {ITEM_TAX_RATE:.0%} tax, " if pre_tax else "")
            + f"over the quarter's {i['diluted_shares'] / 1e9:.2f}B diluted shares)")


def _amount_found(amount: float, text: str, ratios: list[float]) -> bool:
    """The amount as a press release writes it ("0.21", "$.21"), or before a later split (x its ratio)."""
    for x in [amount] + [amount * k for k in ratios]:
        s = f"{x:.2f}"
        if s in text or "$" + s.removeprefix("0") in text:
            return True
    return False


DOLLAR_AMOUNT_RE = re.compile(r"\$\s?(\d[\d,]*(?:\.\d+)?)\s*(million|billion)\b", re.I)


def _dollars_found(millions: float, text: str) -> bool:
    """A dollar amount ($ millions) as a sentence of the text states it, or as the sum of two
    amounts in one sentence: a quarter's restructuring given only by segment ("$305 million
    ... FoA ... and $75 million ... RL"). Within 0.5%, for "$4.2 billion" against 4,200."""
    for line in text.splitlines():
        found = [float(m.group(1).replace(",", "")) * (1000 if m.group(2).lower() == "billion" else 1)
                 for m in DOLLAR_AMOUNT_RE.finditer(line)]
        sums = found + [a + b for n, a in enumerate(found) for b in found[n + 1:]]
        if any(abs(x - millions) <= 0.005 * millions for x in sums):
            return True
    return False


def release_items(r: dict, items: list[dict], basis: str) -> dict:
    """The release's derived item fields: the readable list, their summed effect on the EPS step,
    the step less them (TTM only), and the amounts not found in the press releases' text (or a
    dollar item that couldn't be put per share). `items` carry their per_share (with_per_share)."""
    sources = [(x, x.get("release_date") or "") for x in (r, r.get("leaving") or {}) if x]
    texts = [(f"{x.get('reconciliation') or ''}\n{x.get('item_sentences') or ''}",
              f"{x.get('item_sentences') or ''}\n{x.get('item_dollar_sentences') or ''}",
              [s["ratio"] for s in r.get("splits") or [] if day < s["date"]]) for x, day in sources]
    missing = [f"{i['name']} ${i['amount']:,.0f}M" if in_dollars(i) else f"{i['name']} ${i['per_share']:.2f}"
               for i in items
               if not any(_dollars_found(i["amount"], d) if in_dollars(i) else _amount_found(i["per_share"], t, ratios)
                          for t, d, ratios in texts)]
    missing += [f"{i['name']}: no diluted share count" for i in items if i.get("per_share") is None]
    effect = sum(item_effect(i) for i in items)
    q = quarter_step(r, basis)
    step = q["step"] if q else (float(r["eps_after"]) - float(r["eps_before"]) if r["eps_before"] else None)
    return {
        "one_time_items": "; ".join(
            f"{'entering' if i['quarter'].startswith('new quarter') else 'leaving'}: {item_text(i)}" for i in items),
        "items_effect": round(effect, 2) if items else "",
        "eps_change_ex_items": round(step - effect, 2) if items and step is not None and basis in TTM_BASES else "",
        "items_check": "; ".join(missing),
    }


# One call per period, the told call. The placebo check (periods where the market explains the move or the
# company-specific move is within noise) measures how often it finds a cause where there's little to explain.
def build_requests(subject: str, periods: list[dict], statements: dict, analyst: dict, codebook: list[dict],
                   releases: list[dict] = (), basis: str = "ttm") -> tuple[list[dict], dict]:
    """(requests, refs): refs maps each request to the statement/article refs its numbers
    stand for, so evidence [3] can be reported as '2025-03/A0012-S02'. Per period, a told
    call (the stock's own moves, the window's statements and stock/analyst articles); a
    period with no news gets its status here, without a call."""
    families, families_text = driver_families(codebook)
    sch = schemas(families)
    sys_told = prompt("told", subject, families_text)
    sys_release = prompt("release", subject, families_text)
    reqs, refs = [], {}
    for p in periods:
        window = period_window(p)
        told = window_statements(statements, window, MAX_PERIOD_STATEMENTS)
        arts = [{**a, "day": d, "text": a["lead"]} for d in window for a in analyst.get(d, [])][:MAX_PERIOD_ARTICLES]
        p["n_statements"], p["n_articles"] = len(told), len(arts)
        if not told and not arts:
            p["status"] = "no news collected"  # nothing to read: no call
            continue
        user = move_text(p) + "\n\nStatements:\n" + (numbered(told, True) or "(none collected)")
        if arts:
            user += ("\n\nAlso, stock-market and analyst articles from these days (headline and opening; ratings, "
                     "price targets and stock commentary):\n" + numbered(arts, True, start=len(told) + 1))
        reqs.append(request(f"told_{p['period_id']}", "told", sys_told, user, sch["told"]))
        refs[f"told_{p['period_id']}"] = [s["ref"] for s in told] + [a["ref"] for a in arts]
    for r in releases:  # the filings and press releases only: the release call reads no news
        reqs.append(request(f"release_{r['release_date']}", "release", sys_release, release_facts(r, basis),
                            sch["release"]))
    return reqs, refs


def estimate(reqs: list[dict], standard: bool = False) -> float:
    """Rough cost in dollars: characters x the model's tokens per character, plus
    the schema's overhead, plus the typical output per kind. Batch prices unless
    `standard` (twice)."""
    p = N.BATCH_PRICING[MODEL]
    cost = 0.0
    for r in reqs:
        kind = r["custom_id"].split("_")[0]
        chars = len(r["params"]["system"][0]["text"]) + len(r["params"]["messages"][0]["content"])
        cost += ((chars * p.tokens_per_char + SCHEMA_OVERHEAD_TOKENS) * p.input + OUTPUT_TOKENS[kind] * p.output) / 1e6
    return cost * (2 if standard else 1)


MODELS = {"told": ToldCause, "release": ReleaseItems}


# --- Step 3: ask -----------------------------------------------------------------------------


def ask_request(state: dict, days: list[dict], first: str, last: str, codebook: list[dict]) -> dict:
    months = [m for m in state["months"] if first <= m["month"] <= last]
    have = {m["month"] for m in months}
    want = {f"{y}-{mo:02d}" for y in range(int(first[:4]), int(last[:4]) + 1) for mo in range(1, 13)
            if first <= f"{y}-{mo:02d}" <= last}
    if want - have:
        raise SystemExit(f"Not in this explanation run: {', '.join(sorted(want - have))}")
    weeks = defaultdict(float)
    for d in days:
        if first <= d["date"][:7] <= last and d.get("company_pp") not in ("", None):
            y, w, _ = date.fromisoformat(d["date"]).isocalendar()
            weeks[f"{y}-W{w:02d}"] += float(d["company_pp"])
    tot = {k: sum(m[k] for m in months) for k in BRIDGE + ["company_pp"]}
    lines = [f"Period: {first} to {last}",
             f"Growth share (PVGO / price): {months[0]['share_start']:.1f}% -> {months[-1]['share_end']:.1f}%, "
             f"{tot['total_change_pp']:+.2f}pp = price-driven {tot['price_driven_pp']:+.2f}pp (market "
             f"{tot['market_pp']:+.2f}pp + company-specific {tot['company_pp']:+.2f}pp) + EPS updates at earnings "
             f"releases {tot['eps_update_pp']:+.2f}pp + rates/other {tot['rate_other_pp']:+.2f}pp", "",
             "By month (total = market / company-specific / EPS update / rates-other):"]
    lines += [f"  {m['month']}: {m['total_change_pp']:+.2f} = {m['market_pp']:+.2f} / {m['company_pp']:+.2f} / "
              f"{m['eps_update_pp']:+.2f} / {m['rate_other_pp']:+.2f}" for m in months]
    lines += ["", "Weekly company-specific PVGO change:"] + [f"  {w}: {v:+.2f}pp" for w, v in sorted(weeks.items())]
    rels = [r for r in state.get("releases", []) if first <= r["measurement_date"][:7] <= last]
    if rels:
        lines += ["", "Earnings releases (the EPS step, its growth-share effect with the price held still, the "
                      "market reaction by the size of the company-specific move, and the one-time items the press "
                      "releases name):"]
        lines += [f"- {r['release_date']}: EPS {r['eps_before'] or '?'} -> {r['eps_after']}, growth-share effect "
                  f"{r['eps_update_pp']:+.2f}pp; {market_reaction(r)}, company-specific stock return {reaction_text(r)}. "
                  + (f"One-time items: {r['one_time_items']}" + (f"; EPS change less them {r['eps_change_ex_items']:+.2f}"
                                                                 if r.get("eps_change_ex_items") not in ("", None) else "")
                     + "."
                     if r.get("one_time_items") else "One-time items: none named." if "items" in r
                     else "One-time items: not extracted.") for r in rels]
    lines += ["", "The periods (each month cut into consecutive periods; the label says how much of the move the "
                  "market explains; the cause was found in the period's news, without the market's figures):"]
    for p in (p for p in state["periods"] if first <= p["month"] <= last):
        when = p["start"] if p["days"] == 1 else f"{p['start']} to {p['end']}"
        conf = p.get("confidence") or "none"
        status = (p.get("status") or "not explained") if p.get("status") != "answered" else \
            "no cause found" if conf == "none" else f"{conf} confidence"
        lines.append(f"- {when} [{p['label']}; market {p['market_pp']:+.2f}pp, company-specific {p['company_pp']:+.2f}pp; "
                     f"{status}]: {p.get('cause') or 'no cause found in the news'}")
    families, families_text = driver_families(codebook)
    return request(f"ask_{first}_{last}", "ask", prompt("ask", state["subject"], families_text),
                   "\n".join(lines), schemas(families)["ask"])
