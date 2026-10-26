"""Extraction, answers to units: the verbatim check, the scope and code checks, and the
unit rows. METHODOLOGY section 2.
"""

from pathlib import Path

from extract_articles import normalise, provenance_columns, unescape_markdown
from extract_requests import (
    bullets_from_ids,
    HeadlineTags,
    NumberedStatementSet,
    split_sentences,
    Statement,
    StatementSet,
)
from narrative_common import (
    add_usage,
    HEADLINE,
    MAX_TOPICS_PER_UNIT,
    MIN_STATEMENT_WORDS,
    new_usage,
    now_iso,
    read_result,
    read_text_file,
    report_usage,
    STATEMENTS,
    TOPIC_SEPARATOR,
)


def verbatim_status(quote: str, article_text: str | None) -> str:
    """TRUE / FALSE / unchecked (no text to check against: a PDF)."""
    if article_text is None:
        return "unchecked"
    needle = normalise(quote).strip(" \"'")
    return "TRUE" if needle and needle in normalise(article_text) else "FALSE"


def source_text(state: dict, record: dict) -> str | None:
    """The article text the model was given, re-read from the run's articles folder;
    None for a PDF (or a file that has since gone missing)."""
    if record.get("file_kind") != "text":
        return None
    path = Path(state["input_dir"]) / record["filename"]
    return read_text_file(path) if path.is_file() else None


def in_scope(codes: list[str], qualifiers: set[str]) -> bool:
    """At least one topic code - a code that isn't a qualifier."""
    return any(code not in qualifiers for code in codes)


def codebook_codes(article_id: str, codes: list[str], known: set[str]) -> list[str]:
    """The model's codes without repeats, in its order, and without any code not in the
    codebook the run was submitted with (`known`; empty for runs from before it was
    recorded). Claude's structured outputs enforce the schema's enum; DeepInfra's may not,
    so an invented code is dropped here, with a warning, rather than counting as in scope."""
    codes = list(dict.fromkeys(codes))
    unknown = [c for c in codes if known and c not in known]
    if unknown:
        print(f"  ! {article_id}: dropped code(s) not in the codebook: {', '.join(unknown)}")
    return [c for c in codes if c not in unknown]


def check_statements(article_id: str, statements: list[Statement], article_text: str | None,
                     max_n: int, qualifiers: set[str],
                     known: set[str] = frozenset()) -> tuple[list[tuple[str, list[str], str]], int]:
    """The rules the schema can't express. Returns ([(quote, codes, verbatim)],
    n dropped).

    Dropped, with a warning: filler (under MIN_STATEMENT_WORDS - on main, the model once
    padded speeches with "x" and "placeholder"), no in-scope code, and repeats.
    Warned only: over max_n statements, over MAX_TOPICS_PER_UNIT codes, not verbatim."""
    kept, seen, dropped = [], set(), 0
    for s in statements:
        quote = s.quote.strip()
        codes = codebook_codes(article_id, s.topics, known)
        if len(quote.split()) < MIN_STATEMENT_WORDS:
            print(f"  ! {article_id}: dropped filler statement {quote!r}")
        elif not in_scope(codes, qualifiers):
            print(f"  ! {article_id}: dropped out-of-scope statement (codes {codes or 'none'}): {quote[:70]!r}")
        elif normalise(quote) in seen:
            print(f"  ! {article_id}: dropped repeated statement {quote[:70]!r}")
        else:
            seen.add(normalise(quote))
            if len(codes) > MAX_TOPICS_PER_UNIT:
                print(f"  ! {article_id}: {len(codes)} topic codes, over the soft cap of {MAX_TOPICS_PER_UNIT}; "
                      f"kept all ({TOPIC_SEPARATOR.join(codes)})")
            kept.append((unescape_markdown(quote), codes, verbatim_status(quote, article_text)))
            continue
        dropped += 1
    if len(kept) > max_n:
        print(f"  ! {article_id}: {len(kept)} statements, over the ceiling of {max_n}; kept all")
    for quote, _, verbatim in kept:
        if verbatim == "FALSE":
            print(f"  ! {article_id}: statement not found verbatim in the article: {quote[:90]!r}")
    return kept, dropped


def unit_row(state: dict, article_id: str, record: dict, index: int, n_units: int, unit_id: str,
             text: str, verbatim: str, codes: list[str], created_at: str) -> dict:
    names = state["topic_names"]
    return {
        "run_id": state["run_id"],
        "subject": state.get("subject", ""),
        "article_id": article_id,
        **provenance_columns(record),
        "unit_id": unit_id,
        "unit_index": index,
        "text": text,
        "verbatim": verbatim,
        "topic_codes": TOPIC_SEPARATOR.join(codes),
        # Same order as topic_codes, position for position. Names come from the
        # codebook, never the model; an unknown code shows as itself, not a gap.
        "topic_names": TOPIC_SEPARATOR.join(names.get(code) or code for code in codes),
        "n_units": n_units,
        "model": state["model"],
        "prompt_version": state.get("prompt_version", ""),
        "created_at": created_at,
    }


def collect(results, state: dict) -> tuple[list[dict], list[dict]]:
    """Read the batch results into (unit rows, article scope rows). Results arrive in
    any order, so everything is keyed by custom_id (= article_id). `results` is taken
    as an argument so this can be exercised offline."""
    usage = {STATEMENTS: new_usage(), HEADLINE: new_usage()}
    returned = {}
    for result in results:
        kind = state["articles"].get(result.custom_id, {}).get("request_kind", STATEMENTS)
        add_usage(usage[kind], result)  # per kind: each prompt has its own cache hit rate
        returned[result.custom_id] = result

    # The qualifiers the batch ran with, recorded at submit - so a --resume after a
    # codebook edit still judges by the codebook the prompts embedded.
    qualifiers = set(state.get("qualifier_codes", ["MEAS"]))
    known = set(state.get("scope_codes", []))
    sentence_ids = state.get("prompt_options", {}).get("sentence_ids", False)
    created_at, units, scope_rows = now_iso(), [], []
    for article_id, record in state["articles"].items():
        kind = record["request_kind"]
        result = returned.get(article_id)
        found, dropped, failure, developments = [], 0, None, []
        if record.get("skip"):
            pass  # never requested - its status is the skip reason
        elif result is None:
            failure = "no result returned"
        elif kind == HEADLINE:
            parsed, failure = read_result(result, HeadlineTags)
            if parsed is not None:
                codes = codebook_codes(article_id, parsed.topics, known)
                if in_scope(codes, qualifiers):
                    # The headline verbatim, never the model's wording - paraphrases of
                    # vague headlines invented content.
                    found = [(record.get("headline") or record["title"], codes, "TRUE")]
        else:
            parsed, failure = read_result(result, NumberedStatementSet if sentence_ids else StatementSet)
            text = source_text(state, record)
            if parsed is not None and sentence_ids and text is None:
                parsed, failure = None, "article text missing: sentence numbers can't be read"
            if parsed is not None:
                developments, statements, bad_ids = parsed.developments, parsed.bullets, 0
                if sentence_ids:
                    statements, bad_ids = bullets_from_ids(article_id, parsed.bullets, split_sentences(text))
                found, dropped = check_statements(article_id, statements, text, state["max_statements"],
                                                  qualifiers, known)
                dropped += bad_ids

        for i, (text, codes, verbatim) in enumerate(found, start=1):
            unit_id = f"{article_id}-H" if kind == HEADLINE else f"{article_id}-S{i:02d}"
            units.append(unit_row(state, article_id, record, i, len(found), unit_id, text, verbatim, codes,
                                  created_at))
        if failure:
            print(f"  ! {article_id} ({record['filename']}) no usable result: {failure}")
        scope_rows.append({
            "article_id": article_id,
            **provenance_columns(record),
            "request_kind": kind,
            "status": (f"skipped: {record['skip']}" if record.get("skip")
                       else failure or ("fit" if found else "no_fit")),
            "n_units": len(found),
            "n_dropped": dropped,
            "kept": "TRUE" if found else "FALSE",
            "developments": " | ".join(developments),
            "model": state["model"],
            "prompt_version": state.get("prompt_version", ""),
        })

    state["usage"] = usage  # saved with the state, so a run's real cost stays on record
    print()
    for kind in (STATEMENTS, HEADLINE):
        report_usage(usage[kind], state["model"], kind)
    return units, scope_rows


def print_summary(units: list[dict], scope_rows: list[dict]) -> None:
    """Per request kind: how many articles fit; for statements, the verbatim tally."""
    print()
    for kind in sorted({r["request_kind"] for r in scope_rows}):
        rows = [r for r in scope_rows if r["request_kind"] == kind]
        n_fit = sum(r["status"] == "fit" for r in rows)
        n_skip = sum(r["status"].startswith("skipped") for r in rows)
        n_fail = sum(r["status"] not in ("fit", "no_fit") for r in rows) - n_skip
        n_units = sum(r["n_units"] for r in rows)
        line = f"{kind:<10}: {n_fit} of {len(rows) - n_skip} fit, {n_units} unit(s)"
        if kind == STATEMENTS:
            n_dropped = sum(r["n_dropped"] for r in rows)
            line += f", {n_dropped} statement(s) dropped"
        if n_fail:
            line += f", {n_fail} failed"
        if n_skip:
            line += f"; {n_skip} skipped before submitting"
        print(line)
    statements = [u for u in units if "-S" in u["unit_id"]]  # headlines are verbatim by construction
    if statements:
        tally = {}
        for u in statements:
            tally[u["verbatim"]] = tally.get(u["verbatim"], 0) + 1
        print("Verbatim check: " + ", ".join(f"{k} {v}" for k, v in sorted(tally.items())))
