"""Extraction, what the model is asked: the answer formats, the prompts and their
fingerprint, the sentence ids, the request bodies and the cost estimate.
METHODOLOGY section 2.
"""

import base64
import copy
import hashlib
import html
import json
import re
from pathlib import Path

from anthropic.types.message_create_params import MessageCreateParamsNonStreaming
from anthropic.types.messages.batch_create_params import Request
from pydantic import BaseModel

import narrative_common as N
from extract_articles import request_kind, unescape_markdown
from narrative_common import (
    BATCH_PRICING,
    CACHE_TTL,
    CACHE_WRITE_MULT,
    DEEPINFRA_MAX_TOKENS,
    DEEPINFRA_TEMPERATURE,
    HEADLINE,
    HEADLINE_OUTPUT_TOKENS,
    is_deepinfra,
    MAX_TOKENS,
    qualifier_codes,
    QUALIFIER_FAMILY,
    scope_codebook,
    scope_codes,
    STATEMENTS,
    STATEMENTS_OUTPUT_TOKENS,
)


# --- Output schemas ------------------------------------------------------------


class Statement(BaseModel):
    quote: str  # one or two consecutive sentences, verbatim from the article
    topics: list[str]


class StatementSet(BaseModel):
    # "bullets", matching the summary prompt's wording (2026-10-12); each is a statement.
    developments: list[str] = []  # only with the developments variant (prompt_options)
    bullets: list[Statement]  # empty = nothing in the article fits


class NumberedBullet(BaseModel):
    """A bullet given by sentence numbers (the sentence_ids variant); collection turns it
    into a Statement with the sentences' text."""
    sentences: list[int]  # one number, or two consecutive ones
    topics: list[str]


class NumberedStatementSet(BaseModel):
    developments: list[str] = []
    bullets: list[NumberedBullet]


class HeadlineTags(BaseModel):
    topics: list[str]  # empty = the headline doesn't fit


def topics_property(codes: list[str]) -> dict:
    return {"type": "array", "items": {"type": "string", "enum": codes}}


def statements_schema(codes: list[str], sentence_ids: bool = False, developments: bool = False) -> dict:
    """Written out by hand: structured outputs need additionalProperties: false on every
    object, and messages.parse() isn't available inside a batch. The enum means a code
    can't be invented; what the schema can't express (count, word length, MEAS not
    alone, verbatim) is checked after collection. The variants (prompt_options): sentence
    numbers in place of the quote, and the developments listed before the bullets."""
    item = ({"sentences": {"type": "array", "items": {"type": "integer"}}} if sentence_ids
            else {"quote": {"type": "string"}})
    item["topics"] = topics_property(codes)
    properties = {"developments": {"type": "array", "items": {"type": "string"}}} if developments else {}
    properties["bullets"] = {
        "type": "array",
        "items": {
            "type": "object",
            "properties": item,
            "required": list(item),
            "additionalProperties": False,
        },
    }
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties),
        "additionalProperties": False,
    }


def headline_schema(codes: list[str]) -> dict:
    props = {"topics": topics_property(codes)}
    return {
        "type": "object",
        "properties": props,
        "required": list(props),
        "additionalProperties": False,
    }


# Prompt variants for DeepInfra models, each a switch; Claude's prompts are
# unchanged. Each changes the prompt, so each combination has its own prompt_version.
# - The codebook as a numbered list: the same fields, wording and order as the grouped layout
#   Claude gets, one line per field ("1. TAM (Total accessible market)", then "- Family:",
#   "- Definition:", "- Includes:", "- Route elsewhere:"). On Qwen3 (test months 2024-01, 2024-10) it
#   picked slightly better than the grouped layout; tagging was about the same.
NUMBERED_CODEBOOK_FOR_DEEPINFRA = True
# - Sentence ids: the article's sentences are numbered [S1], [S2], ... (split_sentences) and each
#   bullet gives its sentence number(s) instead of copying the text; the quote is rebuilt from
#   the article at collection, so it is verbatim by construction. Qwen3 edited about 2 quotes a
#   month when copying (the subject swapped in for "the company", sentences spliced).
SENTENCE_IDS_FOR_DEEPINFRA = True
# - Developments first: the answer lists the article's distinct developments about the subject
#   before the bullets, one bullet per development. Qwen doesn't think, so this gives it a place
#   to decide what the news is before it picks sentences (it put two bullets on one story, and
#   picked backlog or cash flow over margin news). Kept in article_scope.csv, for auditing.
DEVELOPMENTS_FOR_DEEPINFRA = True
# - No qualifiers (PROMO): the codebook's qualifier family is left out of the prompt and the
#   schema, so these models can't tag it, and a PROMO they give anyway is dropped as unknown.
#   With sentence ids Qwen3 put PROMO on ordinary news - the job cuts, a guidance raise, a
#   launch, often "(Reuters) -" leads - sending it to the rejected file (7 statements in the
#   test months 2024-01 and 2024-10, against Sonnet's 0). The pre-submit screen already skips stock-pick
#   pages, and STOCK-only statements are still rejected. True offers PROMO again.
QUALIFIERS_FOR_DEEPINFRA = False


def prompt_options(model: str) -> dict:
    """The prompt variants this model gets - all off for Claude."""
    deepinfra = is_deepinfra(model)
    return {
        "numbered": NUMBERED_CODEBOOK_FOR_DEEPINFRA and deepinfra,
        "sentence_ids": SENTENCE_IDS_FOR_DEEPINFRA and deepinfra,
        "developments": DEVELOPMENTS_FOR_DEEPINFRA and deepinfra,
    }


def model_codebook(codebook: list[dict], model: str) -> list[dict]:
    """The codebook this model's prompts and schema are built from: without the qualifier
    family for a DeepInfra model unless QUALIFIERS_FOR_DEEPINFRA. Everything downstream of
    the answer (the exclusion sets, topic names) still reads the full codebook."""
    if is_deepinfra(model) and not QUALIFIERS_FOR_DEEPINFRA:
        return [row for row in codebook if row.get("family") != QUALIFIER_FAMILY]
    return codebook


def render_codebook(codebook: list[dict], numbered: bool = False) -> str:
    """The scope codebook as the model sees it: grouped by family, one block per code,
    empty fields omitted so they don't read as instructions. A route note pointing at
    an exclude=scope code is rendered as out of scope. numbered: the same fields as a
    numbered list, one line each (NUMBERED_CODEBOOK_FOR_DEEPINFRA)."""
    excluded = re.compile(r"->\s*(" + "|".join(map(re.escape, sorted(N.SCOPE_EXCLUDED))) + r")\b") if N.SCOPE_EXCLUDED else None
    if numbered:
        blocks = []
        for i, row in enumerate(scope_codebook(codebook), start=1):
            lines = [f"{i}. {row['code']} ({row.get('topic', '')})"]
            fields = [("Family", row.get("family")), ("Definition", row.get("definition")),
                      ("Includes", row.get("includes"))]
            if row.get("route_elsewhere"):
                route = row["route_elsewhere"]
                fields.append(("Route elsewhere",
                               excluded.sub("-> out of scope (fits no topic)", route) if excluded else route))
            lines += [f"   - {name}: {value}" for name, value in fields if value]
            blocks.append("\n".join(lines))
        return "\n\n".join(blocks)
    lines, family = [], None
    for row in scope_codebook(codebook):
        if row.get("family") != family:
            family = row.get("family")
            lines.append(f"\n## {family}")
        lines.append(f"{row['code']} - {row.get('topic', '')}: {row.get('definition', '')}")
        if row.get("includes"):
            lines.append(f"  Includes: {row['includes']}")
        if row.get("route_elsewhere"):
            route = excluded.sub("-> out of scope (fits no topic)", row["route_elsewhere"]) if excluded else row["route_elsewhere"]
            lines.append(f"  Route elsewhere: {route}")
    return "\n".join(lines).strip()


def scope_rules(codebook: list[dict]) -> str:
    """What "fits" means - shared by both prompts, so a statement and a headline are
    judged in or out of scope the same way: about SUBJECT, not merely naming it. The
    "nothing fits" sentence keeps out event notices, bios and lists that only name it.
    """
    if not N.SUBJECT:
        raise SystemExit("No subject set - pass --subject, e.g. --subject \"Microsoft (MSFT)\"")
    qualifiers = qualifier_codes(codebook)
    text = (
        f"The subject of this analysis is {N.SUBJECT}. The topic codebook below defines what "
        f"is in scope. A unit fits a topic when it makes a claim, reports news or data, "
        f"gives a forecast or assessment, or describes an action about that part of "
        f"{N.SUBJECT}'s business, stock or situation. Tag a topic only when the unit itself "
        f"is about it, not when it is merely mentioned in passing. Follow each topic's "
        f"'Includes' and 'Route elsewhere' notes: when a note routes a subject to another "
        f"code, use that code instead.\n\n"
        f"Nothing fits when the unit only announces or describes an event, publication, "
        f"program or appointment (a conference agenda, a list of sessions or speakers, a "
        f"biography), or when it only names {N.SUBJECT} among other companies or stocks "
        f"without saying anything about it."
    )
    if qualifiers:
        listed = qualifiers[0] if len(qualifiers) == 1 else f"{', '.join(qualifiers[:-1])} and {qualifiers[-1]}"
        if len(qualifiers) == 1:
            text += (f"\n\n{listed} is a qualifier, never enough on its own: give it only alongside a "
                     "topic code, when it applies.")
        else:
            text += (f"\n\n{listed} are qualifiers, never enough on their own: give them only alongside "
                     "a topic code, when they apply.")
    return text


_NUMBER_WORDS = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six"}


def build_statements_prompt(max_n: int, codebook: list[dict], numbered: bool = False, sentence_ids: bool = False,
                            developments: bool = False) -> str:
    """The full-text instructions - identical for every request of this kind.

    Framed as a summary: the sentences you would pick to summarize the article's news in
    at most max_n bullet points, each a sentence copied from it. A list of extraction rules
    gave about 6 statements per article, mostly restatements (METHODOLOGY.md s.2). Two
    parts do the work: the hard ceiling (a soft "usually two or three" was
    ignored) and "states it most plainly, usually the reporter's own words" - without it
    the model preferred executives' quotes over the sentence reporting the news. Keep it
    short: change one thing at a time, and test it.

    "A bullet may be two consecutive sentences when the first does not say..." reads
    backwards, but it is kept as tested: a rewrite ("When a sentence does not say on its own
    who or what it is about, take it together with the sentence before it") was checked the
    same day and changed nothing it aimed at - picks beginning "The company..." stayed.

    The DeepInfra variants (prompt_options; all off, the text is exactly as tested):
    sentence_ids replaces the copying paragraph with sentence numbers, and developments adds
    a paragraph asking for the developments before the bullets.
    """
    n = _NUMBER_WORDS.get(max_n, str(max_n))
    if sentence_ids:
        source = "each bullet a sentence of the article"
        sentences = (
            "The article's sentences are numbered [S1], [S2], ... Give each bullet as the number of its "
            "sentence. A bullet may be two consecutive sentences, given as their two numbers, when the "
            "first does not say on its own who or what it is about.\n\n"
        )
    else:
        source = "each bullet a sentence copied from the article"
        sentences = (
            "Copy each sentence exactly as it appears in the article: the same words in the same "
            "order, with the original punctuation, and without markdown formatting. A bullet may be "
            "two consecutive sentences when the first does not say on its own who or what it is "
            "about.\n\n"
        )
    plan = (
        f"First list the article's distinct developments about {N.SUBJECT}, at most {n}, in a few words "
        f"each, most important first. Then give one bullet per development, in the same order.\n\n"
        if developments else ""
    )
    return (
        f"You pick the sentences of a news article that you would choose if you had to summarize "
        f"its news about {N.SUBJECT} in at most {n} bullet points, "
        f"{source}. Each bullet covers a different "
        f"development; for each, choose the sentence that states it most plainly, usually the "
        f"reporter's own words rather than a quote.\n\n"
        f"{plan}"
        f"{sentences}"
        "Every bullet must fit a topic in the codebook below; tag it with the codes of the topics "
        "it fits. If nothing in the article fits, return an empty list.\n\n"
        f"{scope_rules(codebook)}\n\n"
        f"<topic_codebook>\n{render_codebook(codebook, numbered)}\n</topic_codebook>"
    )


def build_headline_prompt(codebook: list[dict], numbered: bool = False) -> str:
    """The headline instructions - identical for every request of this kind.

    No "one or more" and no "one to three codes" here: on a one-line input both read as
    a quota (2026-10-09: near-identical headlines differed on a trailing code)."""
    return (
        "You decide whether a single headline fits the topic codebook below, and if it "
        "does, which topics. The article's text is not available.\n\n"
        "Judge the headline alone: tag only the topics the headline itself names or "
        "directly states - not ones you would expect the full article to cover. A vague "
        "headline gets fewer codes, not guessed ones. If the headline fits no topic, return "
        "an empty list. That is a correct answer, not a failure.\n\n"
        f"{scope_rules(codebook)}\n\n"
        f"<topic_codebook>\n{render_codebook(codebook, numbered)}\n</topic_codebook>"
    )


def compute_prompt_version(max_n: int, codebook: list[dict], numbered: bool = False, sentence_ids: bool = False,
                           developments: bool = False) -> str:
    """A short fingerprint of everything that defines the measurement - both prompts,
    which embed the scope codebook and MAX_STATEMENTS - stamped on every output row. Any wording change gives a new value, so a
    break in a time series shows up as a change in this column rather than going
    unnoticed. The keyword arguments are prompt_options(model)."""
    parts = [build_statements_prompt(max_n, codebook, numbered, sentence_ids, developments),
             build_headline_prompt(codebook, numbered)]
    if sentence_ids:  # the split decides what [Sn] the model sees, so its rules are part of the measurement
        parts.append("\n".join([_SENTENCE_END.pattern, _UNNUMBERED_LINE.pattern, _LIST_MARKER.pattern,
                                " ".join(sorted(_ABBREVIATIONS))]))
    text = "\n\x00\n".join(parts)
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:8]


# --- Sentence ids (the sentence_ids variant) -------------------------------------
# The article file is split into sentences the same way when the request is built and when
# its answer is collected (both read it with read_text_file), so [S12] means the same sentence
# both times. Deterministic and rule-based: a line is a paragraph (trafilatura Markdown puts
# each paragraph and list item on its own line); headings, the italic source line, all-bold
# subheads, tables, images and lines without letters are shown but not numbered; within a
# line, a sentence ends at . ? or ! (plus
# closing quotes or brackets) before whitespace and a capital, a digit or an opening quote,
# except after a known abbreviation or a single capital initial.

_SENTENCE_END = re.compile(r"([.?!])([\"”’')\]]*)\s+(?=[\"“‘'(\[*_]*[A-Z0-9$])")
_ABBREVIATIONS = {
    "u.s", "u.k", "u.n", "inc", "corp", "co", "ltd", "llc", "plc", "mr", "mrs", "ms", "dr", "st", "no", "vs",
    "e.g", "i.e", "jan", "feb", "mar", "apr", "jun", "jul", "aug", "sep", "sept", "oct", "nov", "dec",
    "jr", "sr", "gov", "sen", "rep", "gen", "lt", "col", "sgt", "capt", "adm", "fig", "approx", "est", "dept",
}
# heading, italic line, all-bold line (a subhead or speaker), table, image, a line with no letters
_UNNUMBERED_LINE = re.compile(r"^(#|\*[^*].*\*$|_[^_].*_$|\*\*[^*]+\*\*:?$|\||!\[|[^A-Za-z]*$)")
_LIST_MARKER = re.compile(r"^(?:[-*+]|\d+[.)])\s+")


def _split_line(line: str) -> list[str]:
    out, start = [], 0
    for m in _SENTENCE_END.finditer(line):
        if m.group(1) == ".":
            word = re.search(r"([A-Za-z][A-Za-z.]*)$", line[:m.start()])
            w = word.group(1) if word else ""
            if w.lower() in _ABBREVIATIONS or (len(w) == 1 and w.isupper()) or re.fullmatch(r"(?:[A-Za-z]\.)+[A-Za-z]", w):
                continue
        piece = line[start:m.end(2)].strip()
        if piece:
            out.append(piece)
        start = m.end()
    if line[start:].strip():
        out.append(line[start:].strip())
    return out


def article_paragraphs(text: str) -> list[tuple[bool, list[str]]]:
    """The article as (numbered, pieces) per line: numbered lines are split into sentences;
    the others are one piece, shown as they are."""
    paragraphs = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if _UNNUMBERED_LINE.match(line):
            paragraphs.append((False, [line]))
        else:
            paragraphs.append((True, _split_line(_LIST_MARKER.sub("", line))))
    return paragraphs


def split_sentences(text: str) -> list[str]:
    """The numbered sentences, in order: sentence n is split_sentences(text)[n - 1]."""
    return [s for numbered, pieces in article_paragraphs(text) if numbered for s in pieces]


def numbered_article(text: str) -> str:
    """The article as the model sees it with sentence ids: each sentence prefixed [Sn]."""
    n, lines = 0, []
    for numbered, pieces in article_paragraphs(text):
        if not numbered:
            lines.append(pieces[0])
            continue
        tagged = []
        for piece in pieces:
            n += 1
            tagged.append(f"[S{n}] {piece}")
        lines.append(" ".join(tagged))
    return "\n\n".join(lines)


def sentence_text(sentence: str) -> str:
    """A sentence as a unit's text: Markdown emphasis, links and escapes removed."""
    sentence = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", sentence)
    sentence = re.sub(r"\*\*|__", "", sentence)
    return unescape_markdown(sentence).strip()


def bullets_from_ids(article_id: str, bullets: list["NumberedBullet"], sentences: list[str]) -> tuple[list["Statement"], int]:
    """The answer's bullets as Statements with their sentences' text, and how many were
    dropped. A bullet with more than two numbers, or two that aren't consecutive, keeps its
    first sentence (with a warning): on the 2024-10 test month that lost 3 bullets whose first sentence
    was the pick. Only a bullet whose first number is out of range, or that has none, is
    dropped."""
    statements, dropped = [], 0
    for b in bullets:
        ids = b.sentences
        if not ids or not 1 <= ids[0] <= len(sentences):
            print(f"  ! {article_id}: dropped a bullet with sentence numbers {ids} "
                  f"(the article has {len(sentences)})")
            dropped += 1
            continue
        if not (len(ids) == 1 or (len(ids) == 2 and ids[1] == ids[0] + 1 and ids[1] <= len(sentences))):
            print(f"  ! {article_id}: sentence numbers {ids} are not one or two consecutive - kept the first")
            ids = ids[:1]
        quote = " ".join(sentence_text(sentences[i - 1]) for i in ids)
        statements.append(Statement(quote=quote, topics=b.topics))
    return statements, dropped


# --- Requests ----------------------------------------------------------------


def article_content(article: dict, task: str, sentence_ids: bool = False) -> list[dict]:
    """The user turn for one article. task: e.g. "Summarize {} in bullets." - its {} is
    filled with "this article" or "the article in this document". sentence_ids: a text
    article's sentences are numbered (numbered_article)."""
    if article["kind"] == "pdf":
        # Document before the instruction text, the order the API docs recommend.
        return [
            {
                "type": "document",
                "source": {"type": "base64", "media_type": "application/pdf", "data": article["content"]},
                "title": article["title"],
            },
            {"type": "text", "text": task.format("the article in this document")},
        ]
    title = html.escape(article["title"], quote=True)
    if article["kind"] == "headline":
        return [{"type": "text", "text": f'<headline title="{title}">\n{article["content"]}\n</headline>'}]
    body = numbered_article(article["content"]) if sentence_ids else article["content"]
    return [{
        "type": "text",
        "text": f'<article title="{title}">\n{body}\n</article>\n\n{task.format("this article")}',
    }]


def cached_system(text: str) -> list[dict]:
    """A block rather than a plain string so it can carry the cache marker. The
    breakpoint sits at the end of the shared part; the article comes after it."""
    return [{"type": "text", "text": text, "cache_control": {"type": "ephemeral", "ttl": CACHE_TTL}}]


def build_request(article: dict, codebook: list[dict], model: str, max_n: int) -> Request | dict:
    """A Claude batch Request, or for a DeepInfra model a real-time request ({custom_id,
    body}) - the same system prompt, user turn and schema either way."""
    codebook = model_codebook(codebook, model)
    codes, opts = scope_codes(codebook), prompt_options(model)
    if request_kind(article) == HEADLINE:
        system, schema = build_headline_prompt(codebook, opts["numbered"]), headline_schema(codes)
        content = article_content(article, "")
    else:
        system = build_statements_prompt(max_n, codebook, **opts)
        schema = statements_schema(codes, opts["sentence_ids"], opts["developments"])
        content = article_content(article, "Summarize {} in bullets.", opts["sentence_ids"])
    if is_deepinfra(model):
        return {
            "custom_id": article["article_id"],
            "body": {
                "model": model,
                "max_tokens": DEEPINFRA_MAX_TOKENS,
                "temperature": DEEPINFRA_TEMPERATURE,
                "messages": [
                    {"role": "system", "content": system},
                    # text only: PDFs are skipped before this for these models (main)
                    {"role": "user", "content": "\n\n".join(block["text"] for block in content)},
                ],
                "response_format": {"type": "json_schema",
                                    "json_schema": {"name": "answer", "strict": True, "schema": schema}},
            },
        }
    return Request(
        custom_id=article["article_id"],
        params=MessageCreateParamsNonStreaming(
            model=model,
            max_tokens=MAX_TOKENS,
            system=cached_system(system),
            messages=[{"role": "user", "content": content}],
            output_config={"format": {"type": "json_schema", "schema": schema}},
        ),
    )


def write_preview(requests: list[Request], path: str | Path) -> None:
    """--dry-run output: the exact requests that would be submitted, minus PDF bytes."""
    with open(path, "w", encoding="utf-8") as f:
        for request in requests:
            shown = copy.deepcopy(request)
            if "body" in shown:  # a DeepInfra request, exactly as it would be sent
                f.write(json.dumps(shown, ensure_ascii=False) + "\n")
                continue
            for block in shown["params"]["messages"][0]["content"]:
                if block["type"] == "document":
                    n_bytes = len(base64.standard_b64decode(block["source"]["data"]))
                    block["source"]["data"] = f"<base64 PDF, {n_bytes} bytes>"
            f.write(json.dumps(shown, ensure_ascii=False) + "\n")


def estimate_cost(
    articles: list[dict], model: str, system_prompt: str, output_tokens: int,
) -> tuple[float, float] | None:
    """Rough batch cost in dollars as (best, worst), or None for a model without
    calibration numbers.

    With caching in play the cost depends on the hit rate, which a batch doesn't
    promise: best = one cache write then every other request reads it; worst = no
    request hits, so every one pays the write premium. Below the model's caching
    minimum best == worst.

    PDFs are a guess (about one token per ten bytes): their real cost depends on page
    count, and each page is also billed as an image.
    """
    if model not in BATCH_PRICING or not articles:
        return (0.0, 0.0) if model in BATCH_PRICING else None
    p = BATCH_PRICING[model]
    n = len(articles)
    article_tokens = sum(
        len(a["content"]) * 3 / 40 if a["kind"] == "pdf" else len(a["content"]) * p.tokens_per_char
        for a in articles
    )
    prompt_tokens = len(system_prompt) * p.tokens_per_char  # rides on every request
    base = article_tokens * p.input + output_tokens * n * p.output
    if prompt_tokens < p.cache_min_tokens:
        flat = (base + prompt_tokens * n * p.input) / 1e6
        return flat, flat
    write = prompt_tokens * p.input * CACHE_WRITE_MULT[CACHE_TTL]
    read = prompt_tokens * p.input * p.cache_read_mult
    return (base + write + read * (n - 1)) / 1e6, (base + write * n) / 1e6


def fmt_estimate(est: tuple[float, float] | None) -> str:
    if est is None:
        return "no estimate"
    best, worst = est
    return f"~${best:.2f}" if abs(best - worst) < 0.005 else f"~${best:.2f} (cache hits) to ${worst:.2f} (no hits)"


def cost_by_kind(articles: list[dict], codebook: list[dict], model: str,
                 max_n: int) -> list[tuple[str, int, tuple[float, float] | None]]:
    """[(label, n requests, estimate)] per request kind that has requests. `articles`: only
    the ones that get a request (screen_articles has removed the skipped)."""
    codebook = model_codebook(codebook, model)
    out = []
    for kind, prompt, tokens in (
        (STATEMENTS, build_statements_prompt(max_n, codebook, **prompt_options(model)), STATEMENTS_OUTPUT_TOKENS),
        (HEADLINE, build_headline_prompt(codebook, prompt_options(model)["numbered"]), HEADLINE_OUTPUT_TOKENS),
    ):
        group = [a for a in articles if request_kind(a) == kind]
        if group:
            label = "statements (full text)" if kind == STATEMENTS else "headlines"
            out.append((label, len(group), estimate_cost(group, model, prompt, tokens)))
    return out


def describe_costs(articles: list[dict], codebook: list[dict], model: str, max_n: int) -> list[str]:
    """The lines printed before submitting: one per request kind."""
    return [f"{label}: {n} request(s), {model} - {fmt_estimate(est)}"
            for label, n, est in cost_by_kind(articles, codebook, model, max_n)]


def total_cost(articles: list[dict], codebook: list[dict], model: str, max_n: int) -> tuple[float, float] | None:
    """The (best, worst) estimate summed over the request kinds; None without calibration numbers."""
    estimates = [est for _, _, est in cost_by_kind(articles, codebook, model, max_n)]
    if any(est is None for est in estimates):
        return None
    return sum(e[0] for e in estimates), sum(e[1] for e in estimates)
