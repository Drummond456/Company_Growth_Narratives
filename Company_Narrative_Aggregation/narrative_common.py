"""What both stages share: the settings block, file and state helpers, the model calls
and their cost (Claude batches, DeepInfra real time) and the codebook.
METHODOLOGY section 2 (settings and cost).
"""

import csv
import json
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import NamedTuple

import anthropic
import requests as http  # "requests" is the name of the batch request lists below
from dotenv import load_dotenv
from pydantic import ValidationError


HERE = Path(__file__).resolve().parent
# Anchored to this file, not the working directory: VS Code's Run button may start the
# script from the workspace root, where a bare load_dotenv() / "runs" would miss.
load_dotenv(HERE / ".env")

# --- Input -----------------------------------------------------------------

# No default article list: a company run always names its pull with --article-list (one
# path or several, concatenated into one list for the run). --input-dir uses a folder of
# articles you built yourself.
ARTICLE_LIST_CSV = []
MERGED_LIST_CSV = "article_list.csv"  # the concatenated list, written into the run folder

RUNS_DIR = HERE / "runs"  # one runs/<list-name>_<timestamp>/ folder per run

# Every request - full-text statements and headlines - runs on this model, so both
# kinds are scoped and tagged the same way. A "claude-" id runs on Claude's Message Batches
# API, any other id on DeepInfra's (is_deepinfra). Qwen3-235B keeps the extraction's cost to
# about a tenth of Sonnet's (claude-sonnet-5-5, which --model selects), and picks close to
# Sonnet (test months 2024-01 and 2024-10). explain_run.py has its own MODEL and stays on Claude.
MODEL = "Qwen/Qwen3-235B-A22B-Instruct-2507"
# Ceiling on statements per full-text article: stated in the prompt ("at most three bullet
# points"), warned about at collection, never enforced. It is also a weighting choice - a
# full-text article counts up to this many units, a headline one. A higher ceiling gets
# filled with restatements of the same point; a hard 3 gives 3 when an article has three
# developments and fewer when it has less, while a soft "usually two or three" is ignored
# (METHODOLOGY.md s.2).
MAX_STATEMENTS = 3

# Topic codes. Read at run time and placed in the system prompts, so editing the CSV
# changes the next run. Columns: code, family, topic, definition, includes,
# route_elsewhere, exclude.
CODEBOOK_CSV = HERE / "company_codebook.csv"
# Both exclusion sets come from the codebook's `exclude` column, filled by load_codebook
# (in place, so every reference sees them):
#   scope  - left out of the prompts and the schema (OTHER: an "other" bucket would let
#            anything in);
#   output - units tagged with it go to narrative_units_rejected.csv instead of
#            narrative_units.csv and code_matrix.csv (PROMO). Tagging is unaffected.
#   alone  - a unit goes to the rejected file only when this is its ONLY topic code
#            (STOCK: a bare share-price move or analyst rating). Tagged alongside a value
#            driver, it is kept - a statement that explains the business stays in.
SCOPE_EXCLUDED: set[str] = set()
OUTPUT_EXCLUDED_CODES: set[str] = set()
ALONE_EXCLUDED: set[str] = set()
QUALIFIER_CODES: set[str] = set()  # the codebook's qualifier family, filled by load_codebook
# Codebook rows in this family are qualifiers - allowed only alongside a topic code: a
# unit tagged with qualifiers alone is out of scope, and dropped at collection.
QUALIFIER_FAMILY = "Qualifier"

# The company or stock every unit must be about, e.g. "Microsoft (MSFT)" - set from
# --subject. It is written into both prompts, so it is part of prompt_version.
SUBJECT = ""

INPUT_DIR = "articles"
OUTPUT_CSV = "narrative_units.csv"
REJECTED_CSV = "narrative_units_rejected.csv"  # units carrying an OUTPUT_EXCLUDED_CODES code
SCOPE_CSV = "article_scope.csv"  # per article: fit / no_fit / failure, n_units, kept
CODE_MATRIX_CSV = "code_matrix.csv"  # per code: the unit ids and texts tagged with it, side by side
RUN_FUNNEL_CSV = "run_funnel.csv"  # articles in the pull -> sent -> fit -> units out
BATCH_STATE_JSON = "batch_state.json"  # so --resume works
PREVIEW_JSONL = "batch_requests_preview.jsonl"  # --dry-run: the exact requests

# Ceiling, not a reservation - unused headroom costs nothing. Sonnet 5.5 thinks by
# default and thinking tokens share this budget; a low ceiling cuts the JSON off.
MAX_TOKENS = 16000
POLL_SECONDS = 60

# Both system prompts are identical on every request of their kind, so they are marked
# for caching. 1h rather than the default 5m because a batch's requests run concurrently
# and in any order over minutes - the documented recommendation for batches. A 1h write
# costs 2x the input price (5m: 1.25x) against 0.1x for a read, so caching only beats
# not caching above a ~53% hit rate (5m: ~22%); usage is reported after every batch.
CACHE_TTL = "1h"
CACHE_WRITE_MULT = {"5m": 1.25, "1h": 2.0}


class Pricing(NamedTuple):
    input: float  # batch $ per MTok
    output: float  # batch $ per MTok
    cache_read_mult: float  # cache read price as a fraction of input
    cache_min_tokens: int  # shortest prefix the model will cache
    tokens_per_char: float  # for estimates only


# For the estimate shown before submitting and the measured cost shown after.
# tokens_per_char measured 2026-10-09 on the cached news prompt: Sonnet 0.38, Haiku 0.26.
BATCH_PRICING = {
    "claude-haiku-4-5": Pricing(0.50, 2.50, 0.10, 4096, 0.26),
    "claude-sonnet-5-5": Pricing(1.00, 5.00, 0.10, 512, 0.38),
    "claude-opus-5-5": Pricing(2.00, 10.00, 0.05, 512, 0.38),
    # DeepInfra, real time - not a batch price: $0.36 / $0.40 on the model page (2026-10-17).
    # No prompt caching is documented, so the system prompt is paid on every request (a
    # cache minimum no prompt reaches makes the estimate flat). tokens_per_char not yet
    # measured - a guess for Qwen's tokenizer on English text.
    "Qwen/Qwen2.5-72B-Instruct": Pricing(0.36, 0.40, 1.0, 10**9, 0.28),
    "Qwen/Qwen3-235B-A22B-Instruct-2507": Pricing(0.09, 0.55, 1.0, 10**9, 0.28),  # model page, 2026-10-17
}
# Output tokens per request, thinking included - for the estimate only. Measured
# 2026-10-09 on headlines (~16), and 2026-10-12 on full-text articles with the summary
# prompt and 3 statements (~230-270 each; it was ~312 with 6).
STATEMENTS_OUTPUT_TOKENS = 260  # up to MAX_STATEMENTS quotes with codes
HEADLINE_OUTPUT_TOKENS = 20  # a few codes

MIN_STATEMENT_WORDS = 5  # a quote shorter than this is filler, not a statement - dropped
# Soft cap: warned about at collection, never enforced. Set from the run of 2026-10-07:
# units with 6-9 tags were nearly all lists of subjects. No longer stated in the
# statements prompt (2026-10-12): the summary prompt was tested without it.
MAX_TOPICS_PER_UNIT = 4

TEXT_SUFFIXES = {".txt", ".md"}
PDF_SUFFIX = ".pdf"
# A batch request may be at most 32 MB, and base64 inflates a file by 4/3 - so anything
# much over 24 MB would be rejected per-request after the whole batch was submitted.
MAX_PDF_BYTES = 24 * 1024 * 1024

STATEMENTS, HEADLINE = "statements", "headline"  # the two kinds of request

CSV_COLUMNS = [
    "run_id", "subject",
    "article_id", "article_file", "article_title", "article_url",
    "published", "period", "source", "content_type",
    "unit_id", "unit_index", "text", "verbatim", "topic_codes", "topic_names", "n_units",
    "model", "prompt_version", "created_at",
]
REJECTED_CSV_COLUMNS = CSV_COLUMNS + ["rejected_for"]  # the excluded code(s) the unit carries
SCOPE_CSV_COLUMNS = [
    "article_id", "article_file", "article_title", "article_url",
    "published", "period", "source", "content_type",
    "request_kind", "status", "n_units", "n_dropped", "n_rejected", "kept", "model", "prompt_version",
    "developments",  # the developments variant only (prompt_options): what the model listed as the news
]
TOPIC_SEPARATOR = ";"  # within topic_codes, e.g. "INF;MP"


# --- Helpers -----------------------------------------------------------------

_client = None


def get_client() -> anthropic.Anthropic:
    """Created on first use, not at import, so importing this module costs nothing."""
    global _client
    if _client is None:
        _client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from the environment
    return _client


# --- DeepInfra (open models) ---------------------------------------------------------
# Real-time chat completions, DEEPINFRA_WORKERS at a time, at the standard price. (The first
# version, the same day, used DeepInfra's Batch API: 20% off, but each month waited on a batch
# with a 24h window. Its Flex tier, also 20% off, can queue a request for 10 minutes or turn
# it away. Neither was worth it at ~$0.01 a month. Only collecting a batch submitted then is
# kept: deepinfra_wait / deepinfra_results, through --resume.)
# Each answer is appended to REALTIME_RESULTS_JSONL in the run folder as it arrives, so an
# interrupted run continues with --resume, sending only the requests without an answer -
# nothing is paid twice. The lines have the Batch API's output shape, and as_batch_result
# turns each into what collect() reads from a Claude batch, so the checks after it are shared.
# Plain HTTP (requests), no extra SDK. The requests carry the same prompts and JSON schemas
# as Claude's.

DEEPINFRA_BASE_URL = "https://api.deepinfra.com/v1/openai"
# Neither Qwen model thinks, so this is all answer: ~260 tokens for 3 statements. The context
# (input and this ceiling together) is per model on DeepInfra; 32,768 for one not listed.
DEEPINFRA_MAX_TOKENS = 2048
DEEPINFRA_CONTEXT = {"Qwen/Qwen2.5-72B-Instruct": 32768, "Qwen/Qwen3-235B-A22B-Instruct-2507": 262144}
# 0: the statements are copied, so the most likely next token is the right one. At
# DeepInfra's default temperature, quotes come back edited.
# Claude requests keep the API default.
DEEPINFRA_TEMPERATURE = 0.0
DEEPINFRA_TRIES = 4  # attempts per request: 429s, 5xx and connection errors are retried
DEEPINFRA_RETRY_SECONDS = [10, 30, 60]  # the wait before each retry
# Seconds per call. An answer is a few hundred tokens, normally back in seconds; at 300 one
# unanswered request held a WMT month for 8.5 minutes (2026-10-17) before its retry succeeded.
DEEPINFRA_TIMEOUT = 90
DEEPINFRA_WORKERS = 8
DEEPINFRA_DONE = {"completed", "failed", "expired", "cancelled"}  # Batch API end states
REALTIME_REQUESTS_JSONL = "realtime_requests.jsonl"  # the run's requests, for --resume
REALTIME_RESULTS_JSONL = "realtime_results.jsonl"  # one line per answer, as it arrives

_local = threading.local()  # one HTTP session per worker thread


def is_deepinfra(model: str) -> bool:
    return not model.startswith("claude-")


def deepinfra_session() -> http.Session:
    """Created on first use in each thread, like get_client."""
    session = getattr(_local, "session", None)
    if session is None:
        key = os.environ.get("DEEPINFRA_API_KEY")
        if not key:
            raise SystemExit(f"DEEPINFRA_API_KEY is not set (in {HERE / '.env'})")
        session = _local.session = http.Session()
        session.headers["Authorization"] = f"Bearer {key}"
    return session


def deepinfra_call(method: str, path: str, **kwargs) -> http.Response:
    resp = deepinfra_session().request(method, DEEPINFRA_BASE_URL + path, timeout=300, **kwargs)
    if not resp.ok:
        raise SystemExit(f"DeepInfra {method} {path}: HTTP {resp.status_code}: {resp.text[:500]}")
    return resp


def deepinfra_complete(request: dict) -> dict:
    """One request, retried; returns its result line - an API error is recorded in the line,
    not raised, so one failed article doesn't stop the run. A rejected key (401/403) does."""
    error = None
    for attempt in range(DEEPINFRA_TRIES):
        if attempt:
            time.sleep(DEEPINFRA_RETRY_SECONDS[min(attempt - 1, len(DEEPINFRA_RETRY_SECONDS) - 1)])
        try:
            resp = deepinfra_session().post(f"{DEEPINFRA_BASE_URL}/chat/completions", json=request["body"],
                                            timeout=DEEPINFRA_TIMEOUT)
        except http.RequestException as exc:
            error = {"code": "connection", "message": str(exc)[:300]}
            continue
        if resp.status_code == 200:
            try:
                body = resp.json()
            except ValueError:
                error = {"code": "bad_response", "message": resp.text[:300]}
                continue
            return {"custom_id": request["custom_id"], "response": {"status_code": 200, "body": body}, "error": None}
        if resp.status_code in (401, 403):
            raise SystemExit(f"DeepInfra rejected the API key (HTTP {resp.status_code}): {resp.text[:300]}")
        error = {"code": str(resp.status_code), "message": resp.text[:300]}
        if resp.status_code != 429 and resp.status_code < 500:
            break  # a bad request won't get better
    return {"custom_id": request["custom_id"], "response": None, "error": error}


def read_jsonl(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def deepinfra_run(requests: list[dict], results_path: Path) -> list[SimpleNamespace]:
    """Send every request that has no answer in results_path yet, appending each answer as
    it arrives; returns all of them as Claude-shaped results. A request that errored before
    is sent again (an error isn't billed); one that was answered never is."""
    answered = {}
    for line in read_jsonl(results_path):
        if line.get("response"):
            answered[line["custom_id"]] = line
    todo = [r for r in requests if r["custom_id"] not in answered]
    print(f"Sending {len(todo)} request(s) to DeepInfra in real time, {DEEPINFRA_WORKERS} at a time"
          + (f"; {len(answered)} already answered" if answered else ""))
    errors = {}
    pool = ThreadPoolExecutor(max_workers=DEEPINFRA_WORKERS)
    try:
        with open(results_path, "a", encoding="utf-8") as f:
            futures = [pool.submit(deepinfra_complete, r) for r in todo]
            for n, future in enumerate(as_completed(futures), start=1):
                line = future.result()
                f.write(json.dumps(line, ensure_ascii=False) + "\n")
                f.flush()
                if line.get("response"):
                    answered[line["custom_id"]] = line
                else:
                    errors[line["custom_id"]] = line
                if n % 10 == 0 or n == len(todo):
                    print(f"  {now_iso()}  {n}/{len(todo)} done, {len(errors)} failed")
    except KeyboardInterrupt:
        pool.shutdown(wait=False, cancel_futures=True)
        raise SystemExit(f"\nStopped. The answers so far are in {results_path} - rerun with --resume to send the rest.")
    except SystemExit:  # a rejected key: don't send the queued requests
        pool.shutdown(wait=False, cancel_futures=True)
        raise
    pool.shutdown()
    return [as_batch_result(line) for line in [*answered.values(), *errors.values()]]


def deepinfra_wait(batch_id: str, poll_seconds: int = POLL_SECONDS) -> dict:
    while True:
        batch = deepinfra_call("GET", f"/batches/{batch_id}").json()
        counts = batch.get("request_counts") or {}
        print(f"  {now_iso()}  {batch['status']}: {counts.get('completed', 0)} completed, "
              f"{counts.get('failed', 0)} failed, of {counts.get('total', '?')}")
        if batch["status"] in DEEPINFRA_DONE:
            return batch
        time.sleep(poll_seconds)


def deepinfra_results(batch: dict) -> list[SimpleNamespace]:
    """Every line of the batch's output and error files, as Claude-shaped results. A request
    with no line at all shows as "no result returned" at collection."""
    if not batch.get("output_file_id") and not batch.get("error_file_id"):
        raise SystemExit(f"DeepInfra batch {batch['id']} ended {batch['status']} with no results: "
                         f"{batch.get('errors')}")
    lines = []
    for key in ("output_file_id", "error_file_id"):
        if batch.get(key):
            text = deepinfra_call("GET", f"/files/{batch[key]}/content").text
            lines += [json.loads(line) for line in text.splitlines() if line.strip()]
    return [as_batch_result(line) for line in lines]


def as_batch_result(line: dict) -> SimpleNamespace:
    """One OpenAI-style result line -> the attributes collect(), add_usage() and read_result()
    read from a Claude batch result. A cut-off answer (finish_reason "length") becomes
    stop_reason "max_tokens", so it is reported as truncated rather than parsed."""
    response = line.get("response") or {}
    body = response.get("body") or {}
    if line.get("error") or response.get("status_code") != 200 or not body.get("choices"):
        error = line.get("error") or body.get("error") or {}
        if not isinstance(error, dict):
            error = {"message": str(error)}
        detail = SimpleNamespace(type=str(error.get("code") or response.get("status_code") or "error"),
                                 message=str(error.get("message") or "no answer"))
        return SimpleNamespace(custom_id=line.get("custom_id"),
                               result=SimpleNamespace(type="errored", error=SimpleNamespace(error=detail)))
    choice = body["choices"][0]
    usage = body.get("usage") or {}
    message = SimpleNamespace(
        stop_reason="max_tokens" if choice.get("finish_reason") == "length" else "end_turn",
        content=[SimpleNamespace(type="text", text=(choice.get("message") or {}).get("content") or "")],
        usage=SimpleNamespace(input_tokens=usage.get("prompt_tokens", 0), cache_creation_input_tokens=0,
                              cache_read_input_tokens=0, output_tokens=usage.get("completion_tokens", 0)),
    )
    return SimpleNamespace(custom_id=line.get("custom_id"), result=SimpleNamespace(type="succeeded", message=message))


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def new_run_id() -> str:
    return "r" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")


def read_text_file(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig", errors="replace").strip()


# --- Codebook and prompts ------------------------------------------------------


def load_codebook(path: str | Path = CODEBOOK_CSV) -> list[dict]:
    """One dict per topic code, in file order. utf-8-sig: Excel saves CSVs with a BOM,
    which would otherwise end up glued to the first column name."""
    path = Path(path)
    if not path.is_file():
        raise SystemExit(f"Topic codebook not found: {path}")
    with open(path, newline="", encoding="utf-8-sig") as f:
        rows = [{k: (v or "").strip() for k, v in row.items()} for row in csv.DictReader(f)]
    rows = [row for row in rows if row.get("code")]
    if not rows:
        raise SystemExit(f"Topic codebook has no codes: {path}")
    codes = [row["code"] for row in rows]
    if len(codes) != len(set(codes)):
        raise SystemExit(f"Topic codebook has duplicate codes: {path}")
    unknown = sorted({row.get("exclude", "") for row in rows} - {"", "scope", "output", "alone"})
    if unknown:
        raise SystemExit(f"Topic codebook: exclude must be blank, scope, output or alone, not {unknown}: {path}")
    SCOPE_EXCLUDED.clear()
    SCOPE_EXCLUDED.update(row["code"] for row in rows if row.get("exclude") == "scope")
    OUTPUT_EXCLUDED_CODES.clear()
    OUTPUT_EXCLUDED_CODES.update(row["code"] for row in rows if row.get("exclude") in ("scope", "output"))
    ALONE_EXCLUDED.clear()
    ALONE_EXCLUDED.update(row["code"] for row in rows if row.get("exclude") == "alone")
    QUALIFIER_CODES.clear()
    QUALIFIER_CODES.update(row["code"] for row in rows if row.get("family") == QUALIFIER_FAMILY)
    if not scope_codebook(rows):
        raise SystemExit(f"Topic codebook has no codes left once {sorted(SCOPE_EXCLUDED)} are excluded: {path}")
    return rows


def scope_codebook(codebook: list[dict]) -> list[dict]:
    """The codes that define the scope: the codebook minus SCOPE_EXCLUDED."""
    return [row for row in codebook if row["code"] not in SCOPE_EXCLUDED]


def scope_codes(codebook: list[dict]) -> list[str]:
    return [row["code"] for row in scope_codebook(codebook)]


def qualifier_codes(codebook: list[dict]) -> list[str]:
    """The scope codes in the QUALIFIER_FAMILY, in file order."""
    return [row["code"] for row in scope_codebook(codebook) if row.get("family") == QUALIFIER_FAMILY]


# --- State, cost ---------------------------------------------------------------


def load_state(state_path: str | Path) -> dict | None:
    if not os.path.exists(state_path):
        return None
    with open(state_path, encoding="utf-8") as f:
        return json.load(f)


def save_state(state: dict, state_path: str | Path) -> None:
    with open(state_path, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


def confirm_submit(cost_lines: list[str], assume_yes: bool, pricing: str = "batch pricing") -> bool:
    """The one gate in front of spending money: nothing is submitted without a 'y'."""
    print(f"\nReady to submit, {pricing}:")
    for line in cost_lines:
        print(f"  {line}")
    if assume_yes:
        return True
    try:
        return input("Submit? [y/N] ").strip().lower() in ("y", "yes")
    except EOFError:  # no terminal attached - never treat that as consent
        return False


# --- Batch -----------------------------------------------------------------------


def wait_for_batch(batch_id: str, poll_seconds: int = POLL_SECONDS) -> None:
    while True:
        batch = get_client().messages.batches.retrieve(batch_id)
        counts = batch.request_counts
        print(
            f"  {now_iso()}  {batch.processing_status}: {counts.processing} processing, "
            f"{counts.succeeded} succeeded, {counts.errored} errored, "
            f"{counts.expired} expired, {counts.canceled} canceled"
        )
        if batch.processing_status == "ended":
            return
        time.sleep(poll_seconds)


def new_usage() -> dict:
    return {"requests": 0, "cache_hits": 0, "input": 0, "cache_write": 0, "cache_read": 0, "output": 0}


def add_usage(usage: dict, result) -> None:
    """Counted for every succeeded result BEFORE parsing: an answer that fails
    validation was still billed. Errored/expired/canceled results aren't billed."""
    if result.result.type != "succeeded":
        return
    u = result.result.message.usage
    usage["requests"] += 1
    usage["input"] += u.input_tokens
    usage["cache_write"] += u.cache_creation_input_tokens or 0
    usage["cache_read"] += u.cache_read_input_tokens or 0
    usage["cache_hits"] += bool(u.cache_read_input_tokens)
    usage["output"] += u.output_tokens


def report_usage(usage: dict, model: str, stage: str = "") -> None:
    """Measured tokens, cost and cache hit rate - the numbers the pre-submit estimate
    was guessing at."""
    if not usage["requests"]:
        return
    line = (
        f"Usage{f' ({stage})' if stage else ''}: {usage['input']:,} input + {usage['cache_write']:,} cache-write + "
        f"{usage['cache_read']:,} cache-read + {usage['output']:,} output tokens; "
        f"cache hits on {usage['cache_hits']}/{usage['requests']} requests"
    )
    p = BATCH_PRICING.get(model)
    if p:
        cost = (
            usage["input"] * p.input
            + usage["cache_write"] * p.input * CACHE_WRITE_MULT[CACHE_TTL]
            + usage["cache_read"] * p.input * p.cache_read_mult
            + usage["output"] * p.output
        ) / 1e6
        line += f"; cost ${cost:.4f}"
    print(line)


def read_result(result, model_cls):
    """(parsed output, None) or (None, failure reason) for one batch result."""
    outcome = result.result
    if outcome.type == "errored":
        error = outcome.error.error
        return None, f"errored ({error.type}): {error.message}"
    if outcome.type in ("expired", "canceled"):
        return None, f"{outcome.type} - resubmit"
    message = outcome.message
    if message.stop_reason == "refusal":
        return None, "model declined"
    if message.stop_reason == "max_tokens":
        return None, "truncated by max_tokens"  # cut-off JSON would look complete
    text = next((b.text for b in message.content if b.type == "text"), None)
    if text is None:
        return None, "no text block in response"
    try:
        return model_cls.model_validate_json(text), None
    except ValidationError as exc:
        return None, f"output failed schema validation: {exc.errors()[0]['msg']}"


def write_csv(rows: list[dict], columns: list[str], path: str | Path) -> None:
    """Every CSV this pipeline writes is utf-8-sig (UTF-8 with a byte-order mark): Excel
    reads a UTF-8 file without the mark as Windows-1252 and garbles curly quotes and
    dashes ("There’s" -> "Thereâ€™s"). Every CSV it reads is opened as utf-8-sig too,
    which accepts files with or without the mark."""
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=columns, quoting=csv.QUOTE_ALL)
        writer.writeheader()
        writer.writerows(rows)


def driver_codes(codebook: list[dict]) -> dict[str, str]:
    """{code: family} for the codes that are value drivers: not excluded (scope, output or
    alone - so not OTHER, PROMO, STOCK) and not qualifiers."""
    return {row["code"]: row["family"] for row in codebook
            if not row.get("exclude") and row.get("family") != QUALIFIER_FAMILY}
