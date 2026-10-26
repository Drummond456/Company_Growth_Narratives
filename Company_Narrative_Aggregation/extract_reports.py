"""Extraction, units to output files: the rejected split, code_matrix.csv and
run_funnel.csv, plus the command that rebuilds them for a run folder.
METHODOLOGY section 1.
"""

import argparse
import csv
import json
from pathlib import Path

import extract_fetch
import narrative_common as N
from narrative_common import (
    CODE_MATRIX_CSV,
    load_codebook,
    REJECTED_CSV,
    RUN_FUNNEL_CSV,
    scope_codebook,
    TOPIC_SEPARATOR,
)


def exclusion_label(sep: str) -> str:
    """What sends a unit to the rejected file, for reports: "tagged OTHER, PROMO, or
    only STOCK"."""
    label = "tagged " + sep.join(sorted(N.OUTPUT_EXCLUDED_CODES))
    return label + (f", or only {sep.join(sorted(N.ALONE_EXCLUDED))}" if N.ALONE_EXCLUDED else "")


def split_units(units: list[dict]) -> tuple[list[dict], list[dict]]:
    """(units for narrative_units.csv, units for narrative_units_rejected.csv), order kept.
    Units must come sorted by article and unit index (finish does this).
      - a unit carrying any OUTPUT_EXCLUDED_CODES code is rejected, with those codes in
        its `rejected_for` column;
      - a unit whose only topic codes (qualifiers aside) are ALONE_EXCLUDED codes - STOCK
        and nothing else - is rejected the same way."""
    kept, rejected = [], []
    for u in units:
        codes = [c for c in u["topic_codes"].split(TOPIC_SEPARATOR) if c]
        hits = [c for c in codes if c in N.OUTPUT_EXCLUDED_CODES]
        topics = [c for c in codes if c not in N.QUALIFIER_CODES]
        if hits:
            rejected.append({**u, "rejected_for": TOPIC_SEPARATOR.join(hits)})
        elif topics and set(topics) <= N.ALONE_EXCLUDED:
            rejected.append({**u, "rejected_for": TOPIC_SEPARATOR.join(topics)})
        else:
            kept.append(u)
    return kept, rejected


def write_code_matrix(units: list[dict], codebook: list[dict], path: str | Path,
                      hide_codes: set[str] | frozenset[str] = frozenset()) -> None:
    """The units read by code: one column pair per scope code ("<CODE> - Unit ID", then
    the unit's text), with the family, topic and code above it. A unit tagged with
    several codes appears under each. Codebook order across, unit order (by article)
    down. A view of narrative_units.csv for reading, not a
    second dataset. utf-8-sig, like every CSV here (see write_csv).

    hide_codes: codes that get no column - OUTPUT_EXCLUDED_CODES for a run that splits
    off rejected units, whose remaining units never carry them."""
    columns = [(row["code"], row.get("family", ""), row.get("topic", ""))
               for row in scope_codebook(codebook) if row["code"] not in hide_codes]
    known = {code for code, _, _ in columns} | set(hide_codes)
    tagged = [(u, u["topic_codes"].split(TOPIC_SEPARATOR)) for u in units]
    # A code the codebook no longer has (edited since the run) still gets a column.
    columns += [(code, "", "") for code in sorted({c for _, codes in tagged for c in codes if c and c not in known})]
    lists = {code: [(u["unit_id"], u["text"]) for u, codes in tagged if code in codes] for code, _, _ in columns}
    depth = max((len(v) for v in lists.values()), default=0)
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["family"] + [cell for _, family, _ in columns for cell in ("", family)])
        writer.writerow(["topic"] + [cell for _, _, topic in columns for cell in ("", topic)])
        writer.writerow(["code"] + [cell for code, _, _ in columns for cell in (f"{code} - Unit ID", code)])
        for i in range(depth):
            writer.writerow([""] + [cell for code, _, _ in columns
                                    for cell in (lists[code][i] if i < len(lists[code]) else ("", ""))])


def write_run_funnel(scope_rows: list[dict], units: list[dict], manifest_path: str | Path, path: str | Path,
                     rejected: list[dict] | None = None) -> None:
    """How many articles made it through each stage, from the pull to
    narrative_units.csv: one row per stage. "Articles in pull" counts the fetch
    manifest's rows (one per list row), so an article the fetch produced no file for
    still shows up; without a manifest (a hand-built folder) it counts the articles
    loaded. utf-8-sig, like every CSV here (see write_csv).

    units: those in narrative_units.csv. rejected: those moved to
    narrative_units_rejected.csv - None for a run from before that split, which then
    shows no rejected rows."""
    if Path(manifest_path).is_file():
        with open(manifest_path, newline="", encoding="utf-8-sig") as f:
            pulled_sources = [row.get("source", "") for row in csv.DictReader(f)]  # one per list row
    else:
        pulled_sources = [r["source"] for r in scope_rows]

    def count(rows, test) -> int:
        return sum(1 for r in rows if test(r))

    def status(r) -> str:
        return "skipped" if r["status"].startswith("skipped") else r["status"] if r["status"] in ("fit", "no_fit") else "failed"

    n_pulled = len(pulled_sources)
    n_loaded = len(scope_rows)
    n_skipped = count(scope_rows, lambda r: status(r) == "skipped")
    n_units = len(units)
    rows = [
        ("articles in pull", n_pulled),
        ("- full text fetched", count(scope_rows, lambda r: r["content_type"] == "full_text")),
        ("- headline only", count(scope_rows, lambda r: r["content_type"] == "headline")),
        ("- no file (fetch produced nothing)", n_pulled - n_loaded),
        ("skipped before submitting", n_skipped),
        ("sent to model", n_loaded - n_skipped),
        ("- failed (no usable result)", count(scope_rows, lambda r: status(r) == "failed")),
        ("- no fit (nothing matched the codebook)", count(scope_rows, lambda r: status(r) == "no_fit")),
        ("- fit (1+ units)", count(scope_rows, lambda r: status(r) == "fit")),
    ]
    if rejected is not None:
        rows += [
            ("units extracted", n_units + len(rejected)),
            (f"- moved to {REJECTED_CSV}: {exclusion_label(', ')}", len(rejected)),
        ]
    rows += [
        ("units in narrative_units.csv", n_units),
        ("- statements", count(units, lambda u: "-S" in u["unit_id"])),
        ("- headlines", count(units, lambda u: u["unit_id"].endswith("-H"))),
        ("articles with units in narrative_units.csv", len({u["article_id"] for u in units})),
        ("sources in pull", len({s for s in pulled_sources if s})),
        ("sources in output", len({u["source"] for u in units if u["source"]})),
    ]
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["stage", "count"])
        for label, value in rows:
            writer.writerow([label, value])


def write_reports(units: list[dict], scope_rows: list[dict], input_dir: Path, out_dir: Path,
                  rejected: list[dict] | None = None) -> None:
    """The views written beside the outputs - code_matrix.csv and run_funnel.csv.
    Written after the run is marked collected, each on its own: they
    are derived from narrative_units.csv and article_scope.csv, so a file locked by Excel
    only costs that view (extract_reports.py rebuilds it), never the run.

    units: those in narrative_units.csv. rejected: those in narrative_units_rejected.csv,
    or None for a run from before that split - its matrix then keeps every code column."""
    load_codebook()  # fills OUTPUT_EXCLUDED_CODES (extract_reports.py calls this directly)
    hide = N.OUTPUT_EXCLUDED_CODES if rejected is not None else frozenset()
    for name, write in (
        (CODE_MATRIX_CSV, lambda path: write_code_matrix(units, load_codebook(), path, hide_codes=hide)),
        (RUN_FUNNEL_CSV, lambda path: write_run_funnel(scope_rows, units, input_dir.parent / extract_fetch.MANIFEST_CSV,
                                                       path, rejected=rejected)),
    ):
        path = out_dir / name
        try:
            write(path)
            print(f"Wrote {path}")
        except PermissionError:
            print(f"  ! {path} is open in another program (Excel?) - close it and run: python extract_reports.py {out_dir}")


# Rebuild the per-run reports for an existing run folder - extract_run.py writes them at
# the end of every run; this is for a run collected before that, after a codebook change,
# or when a file was locked by Excel. Read-only apart from those two files - no API call.
# Each is overwritten, hand edits included.
#
#   - code_matrix.csv    the units read by codebook code: a column pair (unit id, text) per code
#   - run_funnel.csv     articles in the pull -> skipped -> sent ->
#                        fit -> units in narrative_units.csv
#
#     python extract_reports.py                  # the most recently collected run under runs/
#     python extract_reports.py runs/<run>

def latest_run() -> Path:
    runs = [p.parent for p in N.RUNS_DIR.glob(f"*/{N.OUTPUT_CSV}")]
    if not runs:
        raise SystemExit(f"No collected run under {N.RUNS_DIR}")
    return max(runs, key=lambda p: (p / N.OUTPUT_CSV).stat().st_mtime)


def read_csv(path: Path) -> list[dict]:
    if not path.is_file():
        raise SystemExit(f"{path} not found")
    with open(path, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def main() -> None:
    parser = argparse.ArgumentParser(description="Rebuild code_matrix.csv and run_funnel.csv for a run folder (no API call).")
    parser.add_argument("run_dir", nargs="?", help="a collected run folder (default: the most recent)")
    args = parser.parse_args()

    run_dir = Path(args.run_dir) if args.run_dir else latest_run()
    units = read_csv(run_dir / N.OUTPUT_CSV)
    if units and "text" not in units[0]:
        raise SystemExit(f"{run_dir / N.OUTPUT_CSV} is from an older Narrative.py (no 'text' column)")
    scope_rows = read_csv(run_dir / N.SCOPE_CSV)
    # A run from before narrative_units_rejected.csv existed has none: its reports are
    # rebuilt as they were (every code column, no rejected rows in the funnel).
    rejected = read_csv(run_dir / N.REJECTED_CSV) if (run_dir / N.REJECTED_CSV).is_file() else None

    # The manifest sits beside the articles folder the batch ran on (the run folder,
    # unless the run used --input-dir).
    state_path = run_dir / N.BATCH_STATE_JSON
    input_dir = Path(json.loads(state_path.read_text(encoding="utf-8"))["input_dir"]) if state_path.is_file() else run_dir / N.INPUT_DIR
    write_reports(units, scope_rows, input_dir, run_dir, rejected)


if __name__ == "__main__":
    main()
