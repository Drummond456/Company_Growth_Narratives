// Interactive PVGO history + month-synced explanations.
// Everything is read from static copies in data/ (see README.md); nothing here touches the pipeline.

// The method note under the title; beta: its range over the chart's window, from series.csv's beta column
const footnote = (beta, erp) =>
  "Growth share = 1 − no-growth value / close, each trading day; PVGO = close − no-growth value. " +
  "No-growth value = adjusted TTM EPS / cost of equity: the trailing GAAP diluted EPS without the gains and " +
  "losses on investments (less a flat 25% tax), from the filings available at each release, on today's share " +
  "basis. It steps at each measurement date (the first close after the release). Cost of equity = 10-year " +
  "Treasury (FRED DGS10, weekly between releases) + beta × ERP. Beta: the company's own, re-estimated each " +
  "month from the prior 60 monthly total returns against the S&P 500, Blume-adjusted (0.67 × slope + 0.33): " +
  `${beta} here. ERP: ${erp}, held constant.`;

// One page per company: its <body data-company="cost"> picks the entry here, and its data is in data/cost/
const COMPANIES = {
  cost: {
    chartTitle: "COST: share price vs. no-growth value, and the growth share (own beta)",
    footnote: footnote("0.84 to 1.00", "4.60%"),
  },
  "meta_2022-09_2023-08": {
    chartTitle: "META: share price vs. no-growth value, and the growth share (own beta)",
    footnote: footnote("1.09 to 1.27", "5.09%"),
  },
};

// The market model's sector ETF is read from the run's settings line ("market model: S&P 500 + RSPS");
// its full name goes in the method note for the equal-weight GICS sector funds the rule picks
// (Company_Narrative_Aggregation METHODOLOGY §7)
const ETF_NAMES = {
  RSPS: "Invesco S&P 500 Equal Weight Consumer Staples ETF",
  RSPC: "Invesco S&P 500 Equal Weight Communication Services ETF",
  RSPT: "Invesco S&P 500 Equal Weight Technology ETF",
};

const COMPANY = document.body.dataset.company || "cost";
const CONFIG = {
  ...COMPANIES[COMPANY],
  repoUrl: "https://github.com/Drummond456/Company_Growth_Narratives",  // hidden while empty
  files: {
    series: `data/${COMPANY}/series.csv`,
    points: `data/${COMPANY}/points.csv`,
    yearEnd: `data/${COMPANY}/year_end.csv`,
    explanations: `data/${COMPANY}/explanations.md`,
    evidence: `data/${COMPANY}/evidence.json`,  // optional: built by update_data.py
    dailySplit: `data/${COMPANY}/daily_split.csv`,  // optional: the explain run's daily market / company-specific split
    periods: `data/${COMPANY}/periods.csv`,  // optional: the explain run's periods, shaded in the bottom panel
  },
};

// The same palette as style.css's :root
const COLORS = {
  price: "#f2f5f3",  // sail white
  nogrowth: "#2ec4d6",  // sea cyan
  share: "#3ddc84",  // terminal green
  pvgo: "rgba(64, 156, 255, 0.2)",
  release: "#4a5a58",
  grid: "#1a2426",
  axis: "#73827e",
  ink: "#edf1ee",
  background: "rgba(0, 0, 0, 0)",  // the chart sits on its panel (or, stacked, on the page)
  card: "#162023",  // gunmetal-green: marker rings and hover labels
  window: "rgba(143, 166, 160, 0.04)",
  month: "rgba(255, 159, 28, 0.16)",  // terminal amber (style.css --accent)
  monthEdge: "#ff9f1c",
  market: "#8fa6a0",  // the hull's silver-green
  company: "#e055e0",
  standsOut: "rgba(224, 85, 224, 0.14)",  // divergent and outlier periods
  frame: "#223031",  // each panel's border
  font: "IBM Plex Mono, ui-monospace, SFMono-Regular, Menlo, Consolas, monospace",
};

const MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const FULL_MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September",
  "October", "November", "December"];
// "2024-03-07" -> "March 7, 2024", as the explanations write their dates
const longDate = iso => (iso ? `${FULL_MONTHS[Number(iso.slice(5, 7)) - 1]} ${Number(iso.slice(8, 10))}, ${iso.slice(0, 4)}` : "");
// Panel heights in paper units: price, growth share, and (with the explain run's daily split) the
// cumulative market and company-specific parts of the growth share's change
const TWO_PANELS = { price: [0.36, 1], share: [0, 0.27] };
const THREE_PANELS = { price: [0.551, 1], share: [0.278, 0.530], split: [0, 0.257] };
// The chart shows the explained window and this many months on each side; the history runs longer
const CONTEXT_MONTHS = 6;
// The chart beside the text, not above it: the same media query as style.css
const SIDE_BY_SIDE = "(min-width: 1100px) and (min-height: 650px)";

// ---------- data loading ----------

function parseCSV(text) {
  // RFC 4180-ish: quoted fields, doubled quotes, CRLF. Returns an array of objects keyed by the header.
  text = text.replace(/^﻿/, "");
  const rows = [];
  let row = [], field = "", quoted = false;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (quoted) {
      if (c === '"' && text[i + 1] === '"') { field += '"'; i++; }
      else if (c === '"') quoted = false;
      else field += c;
    } else if (c === '"') quoted = true;
    else if (c === ",") { row.push(field); field = ""; }
    else if (c === "\n" || c === "\r") {
      if (c === "\r" && text[i + 1] === "\n") i++;
      row.push(field); rows.push(row); row = []; field = "";
    } else field += c;
  }
  if (field !== "" || row.length) { row.push(field); rows.push(row); }
  const header = rows.shift();
  return rows
    .filter(r => r.length > 1 || r[0] !== "")
    .map(r => Object.fromEntries(header.map((h, j) => [h, r[j] ?? ""])));
}

async function fetchText(path) {
  const res = await fetch(path);
  if (!res.ok) throw new Error(`${path}: HTTP ${res.status}`);
  return res.text();
}

const num = s => (s === "" || s == null ? null : Number(s));

// ---------- explanations ----------

// Render the markdown and wrap each "## March 2024: ..." heading (or the older "## 2024-03: ...") and what
// follows it (up to the next h2) in a <section class="month">; what comes before the first month (the
// run's settings, label table and notes) moves into intro, the collapsed reading guide in the page's
// top panel; the run's title gives the page's. Returns [{key: "2024-03", label, section}] in document order.
function renderExplanations(md, container, intro) {
  const html = DOMPurify.sanitize(marked.parse(md));
  container.innerHTML = html;

  container.querySelectorAll("table").forEach(t => {
    const wrap = document.createElement("div");
    wrap.className = "table-wrap";
    t.replaceWith(wrap);
    wrap.appendChild(t);
  });
  // Figures in mono; a signed one colored up or down ("+0.40", "-1.50")
  container.querySelectorAll("td").forEach(td => {
    const text = td.textContent.trim();
    if (/^[+-]\d/.test(text)) td.classList.add(text.startsWith("+") ? "pos" : "neg");
    else if (/^\d[\d.,]*%?$/.test(text)) td.classList.add("num");
  });

  const months = [];
  for (const h2 of [...container.querySelectorAll("h2")]) {
    const iso = h2.textContent.match(/^(\d{4}-\d{2}):\s*(.*)$/);
    const named = h2.textContent.match(/^([A-Z][a-z]+) (\d{4}):\s*(.*)$/);
    const m = iso || (named && FULL_MONTHS.includes(named[1])
      ? [null, `${named[2]}-${String(FULL_MONTHS.indexOf(named[1]) + 1).padStart(2, "0")}`, named[3]] : null);
    if (!m) continue;
    const section = document.createElement("section");
    section.className = "month";
    section.id = `m-${m[1]}`;
    h2.before(section);
    let node = h2;
    while (node && !(node !== h2 && node.tagName === "H2")) {
      const next = node.nextSibling;
      section.appendChild(node);
      node = next;
    }
    const label = m[2].replace(/->/g, "→");
    // The month's name and its move, set apart: "March 2024" | "growth share 75.7% → 74.2% (-1.50pp)"
    const name = document.createElement("span");
    name.className = "month-name";
    name.textContent = h2.textContent.slice(0, h2.textContent.indexOf(":"));
    const sub = document.createElement("span");
    sub.className = "month-sub";
    const move = label.match(/^(.*)\(([+-][\d.]+pp)\)$/);
    if (move) {
      const pp = document.createElement("span");
      pp.className = move[2].startsWith("+") ? "pos" : "neg";
      pp.textContent = move[2];
      sub.append(`${move[1]}(`, pp, ")");
    } else sub.textContent = label;
    h2.replaceChildren(name, sub);
    months.push({ key: m[1], label, section });
  }
  const body = intro.querySelector(".intro-body");
  if (months.length) {
    while (container.firstChild && container.firstChild !== months[0].section) body.appendChild(container.firstChild);
  }
  const title = body.querySelector(":scope > h1");
  if (title) {
    // The page's title gets the run's company and months, on a line of their own: "Why Costco (COST)'s
    // PVGO share moved: January 2024 to December 2024" -> ": / Costco (COST), January 2024 – December 2024",
    // each date kept whole
    const run = title.textContent.match(/^Why (.+?)'s PVGO share moved: (.+?) to (.+)$/);
    const keep = s => s.replace(/ /g, " ");
    if (run) document.getElementById("page-title").append(":", h("span", "title-run", `${run[1]}, ${keep(run[2])} – ${keep(run[3])}`));
    title.remove();
  }
  // Each "### Settings" heading and what follows it (up to the next) is one part, kept whole in its column
  for (const h3 of [...body.querySelectorAll(":scope > h3")]) {
    const part = document.createElement("section");
    part.className = "intro-part";
    h3.before(part);
    let node = h3;
    while (node && !(node !== h3 && node.tagName === "H3")) {
      const next = node.nextSibling;
      part.appendChild(node);
      node = next;
    }
  }
  intro.hidden = !body.children.length;
  return months;
}

// ---------- evidence ----------

const SOURCE_NAMES = { "finance.yahoo.com": "Yahoo Finance", "cnbc.com": "CNBC", "www.cnbc.com": "CNBC",
  "fortune.com": "Fortune" };
const KIND_LABELS = { statement: "Statement", headline: "Headline", article: "Article · headline/intro only",
  filing: "Press release" };
const CHIPS_SHOWN = 4;  // more than this + 1 collapse behind a "+N" chip

function h(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text != null) node.textContent = text;
  return node;
}

const shortRef = (ref, monthKey) => (ref.startsWith(`${monthKey}/`) ? ref.slice(monthKey.length + 1) : ref);

// One cited item: what it says, where it's from, and its ref. Data text goes in as text, never HTML.
function evidenceCard(ev, ref) {
  const item = ev.items[ref];
  const card = h("div", "ev-card");
  card.dataset.ref = ref;
  const meta = h("div", "ev-meta");
  meta.append(h("span", "ev-badge", item ? KIND_LABELS[item.kind] || item.kind : "Not found"), h("span", "ev-id", ref));
  card.appendChild(meta);
  if (!item) {
    card.appendChild(h("p", "ev-source", "This ref isn't in the run's statements."));
    return card;
  }
  if (item.kind === "filing") return filingCard(card, item);
  if (item.text) {
    const quote = h("p", "ev-quote", item.verbatim ? `“${item.text}”` : item.text);
    if (!item.verbatim) quote.appendChild(h("span", "ev-tag", " (paraphrase)"));
    card.appendChild(quote);
  }
  const art = ev.articles[item.article];
  if (art) {
    const link = h("a", "ev-title", art.title);
    link.href = art.url;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    card.append(link, h("p", "ev-source", `${SOURCE_NAMES[art.source] || art.source} · ${longDate(art.published)}`));
  }
  if (item.topics) card.appendChild(h("p", "ev-topics", item.topics));
  return card;
}

// A press release a release block cites: the one-time item lines PVGO_Collection read from it, then the
// filing (form, accession, dates) and links: the press release itself and the filing's EDGAR index, or
// without them EDGAR's list of the company's filings, where the accession number finds it.
function filingCard(card, item) {
  item.lines.forEach(line => card.appendChild(h("p", "ev-quote", `“${line}”`)));
  if (!item.lines.length && !item.reconciliation) {
    card.appendChild(h("p", "ev-source", "This press release names no per-share one-time item."));
  }
  if (item.reconciliation) {
    const details = h("details", "ev-recon");
    details.append(h("summary", null, "Reconciliation table"), h("pre", null, item.reconciliation));
    card.appendChild(details);
  }
  const link = (href, text) => {
    const a = h("a", "ev-title", text);
    a.href = href;
    a.target = "_blank";
    a.rel = "noopener noreferrer";
    return a;
  };
  if (item.doc_url) card.appendChild(link(item.doc_url, `Press release (${item.doc_name || "exhibit"})`));
  if (item.index_url) card.appendChild(link(item.index_url, "Filing on SEC EDGAR"));
  else if (item.search_url) card.appendChild(link(item.search_url, `Find it on SEC EDGAR (${item.form} filings)`));
  card.appendChild(h("p", "ev-source", `${item.form} · accession ${item.accession || "?"} · released ` +
    `${longDate(item.release_date)} · quarter ended ${longDate(item.quarter_end)}`));
  return card;
}

// The refs an explanation cites end its text in the markdown: "[A0065, A0064-H, A0061-H]", a short id
// being from the month's run; a release block's head line ends with its press releases, "[R2024-05-30]"
// (update_data.py reads them the same way). Removes the bracket from the page and returns the refs as
// "YYYY-MM/<id>", or "R<date>" as they are.
const REF = String.raw`(?:(?:\d{4}-\d{2}\/)?A\d+(?:-[A-Z]+\d*)?|R\d{4}-\d{2}-\d{2})`;
const REFS_AT_END = new RegExp(String.raw`\s*\[(${REF}(?:, ${REF})*)\]\s*$`);

function takeRefs(node, monthKey) {
  const last = [...node.childNodes].reverse().find(n => n.nodeType === Node.TEXT_NODE && n.textContent.trim());
  const found = last?.textContent.match(REFS_AT_END);
  if (!found) return [];
  last.textContent = last.textContent.slice(0, found.index);
  return found[1].split(", ").map(r => (r.includes("/") || r.startsWith("R") ? r : `${monthKey}/${r}`));
}

// Chips under each cause and release box; a chip opens its card under them, and the same chip
// again closes it.
function setupEvidence(ev, months) {
  for (const m of months) {
    // Each period is a list item ("**P07 March 8, 2024 · outlier** · ... · Cause: ... [refs]"); each
    // release is a <div class="release"> between them, its head line ending with its press releases
    for (const node of m.section.querySelectorAll(":scope > ul > li, :scope > div.release")) {
      let refs;
      if (node.tagName === "DIV") {
        const first = node.querySelector("p");
        refs = first ? takeRefs(first, m.key) : [];
      } else if (/^P\d+\s/.test(node.querySelector("strong")?.textContent || "")) {
        refs = takeRefs(node, m.key);
      } else continue;
      if (refs.length) node.appendChild(chipRow(m.key, refs));
    }
  }

  function chipRow(monthKey, refs) {
    const row = h("div", "cites");
    row.appendChild(h("span", "cites-label", "Evidence"));
    const collapse = refs.length > CHIPS_SHOWN + 1;
    const chips = refs.map((ref, i) => {
      const chip = h("button", "chip", shortRef(ref, monthKey));
      chip.type = "button";
      chip.title = `${ref}: ${KIND_LABELS[ev.items[ref]?.kind] || "not found"}`;
      chip.hidden = collapse && i >= CHIPS_SHOWN;
      chip.addEventListener("click", () => open(row, ref, chip));
      row.appendChild(chip);
      return chip;
    });
    if (collapse) {
      const more = h("button", "chip chip-more", `+${refs.length - CHIPS_SHOWN}`);
      more.type = "button";
      more.title = "Show all";
      more.addEventListener("click", () => { chips.forEach(c => { c.hidden = false; }); more.remove(); });
      row.appendChild(more);
    }
    return row;
  }

  // One card open per row: the card goes right after the chips
  function open(row, ref, chip) {
    const wasOpen = chip.getAttribute("aria-expanded") === "true";
    row.querySelectorAll(".chip").forEach(c => c.setAttribute("aria-expanded", "false"));
    if (row.nextElementSibling?.classList.contains("ev-inline")) row.nextElementSibling.remove();
    if (wasOpen) return;
    chip.setAttribute("aria-expanded", "true");
    const inline = h("div", "ev-inline");
    inline.appendChild(evidenceCard(ev, ref));
    row.after(inline);
  }
}

// ---------- chart ----------

function monthRange(key) {
  const [y, m] = key.split("-").map(Number);
  const start = `${key}-01`;
  const end = m === 12 ? `${y + 1}-01-01` : `${y}-${String(m + 1).padStart(2, "0")}-01`;
  return [start, end];
}

// "2024-01", -13 -> "2022-12"
function addMonths(key, n) {
  const [y, m] = key.split("-").map(Number);
  const t = y * 12 + (m - 1) + n;
  return `${Math.floor(t / 12)}-${String((t % 12) + 1).padStart(2, "0")}`;
}

// split: the explain run's days ({date, market_pp, company_pp}), [] without it; periods: its periods
// ({start, end, label}). With a split, a third panel shows the cumulative market and company-specific
// parts of the growth share's change over the explained window, with divergent and outlier periods shaded.
function buildChart(el, history, points, yearEnd, months, split = [], periods = []) {
  // The explained window and CONTEXT_MONTHS on each side of it; without months, the whole history
  const [lo, hi] = months.length ? [monthRange(addMonths(months[0].key, -CONTEXT_MONTHS))[0],
    monthRange(addMonths(months[months.length - 1].key, CONTEXT_MONTHS))[1]] : ["", "9999"];
  const series = history.filter(r => r.date >= lo && r.date < hi);
  const first = series[0].date, last = series[series.length - 1].date;
  yearEnd = yearEnd.filter(r => r.date >= first && r.date <= last);
  const panels = split.length ? THREE_PANELS : TWO_PANELS;

  // The no-growth line steps at each measurement date: draw the value before the step, then after, on that date.
  const ngX = [], ngY = [];
  for (const r of series) {
    if (r.no_growth_value_before_step != null) { ngX.push(r.date); ngY.push(r.no_growth_value_before_step); }
    ngX.push(r.date); ngY.push(r.no_growth_value);
  }

  const shown = points.filter(p => p.measurement_date >= first && p.measurement_date <= last);
  const releases = points.filter(p => p.release_date >= first && p.release_date <= last);

  const traces = [
    {
      name: "No-growth value", x: ngX, y: ngY, type: "scatter", mode: "lines",
      line: { color: COLORS.nogrowth, width: 1.5 },
      hovertemplate: "$%{y:,.2f}<extra>No-growth value</extra>",
    },
    {
      name: "Share price", x: series.map(r => r.date), y: series.map(r => r.close),
      type: "scatter", mode: "lines", fill: "tonexty", fillcolor: COLORS.pvgo,
      line: { color: COLORS.price, width: 1.5 },
      customdata: series.map(r => [r.close - r.no_growth_value, r.growth_share_pct]),
      hovertemplate: "$%{y:,.2f}  (PVGO $%{customdata[0]:,.0f}, growth share %{customdata[1]:.1f}%)<extra>Share price</extra>",
    },
    {
      name: "Measurement date", x: shown.map(p => p.measurement_date), y: shown.map(p => p.price),
      type: "scatter", mode: "markers",
      marker: { color: COLORS.price, size: 7, line: { color: COLORS.card, width: 2 } },
      customdata: shown.map(p => [p.release_date, p.quarter_end, p.eps_used]),
      hovertemplate: "%{x|%b %-d}: release %{customdata[0]}, EPS %{customdata[2]} through %{customdata[1]}" +
        "<extra>Measurement</extra>",
    },
    {
      name: "Growth share", x: series.map(r => r.date), y: series.map(r => r.growth_share_pct),
      xaxis: "x", yaxis: "y2", type: "scatter", mode: "lines",
      line: { color: COLORS.share, width: 1.5 },
      hovertemplate: "%{y:.1f}%<extra>Growth share</extra>",
    },
    {
      name: "Year-end growth share", x: yearEnd.map(r => r.date), y: yearEnd.map(r => r.growth_share_pct),
      xaxis: "x", yaxis: "y2", type: "scatter", mode: "markers",
      marker: { color: COLORS.share, size: 9, symbol: "diamond", line: { color: COLORS.card, width: 2 } },
      hovertemplate: "%{y:.1f}%<extra>Year-end</extra>",
    },
  ];

  // The cumulative market and company-specific parts (pp), from the explained window's first day
  let market = 0, company = 0;
  const round2 = x => Math.round(x * 100) / 100;  // running sums drift (3.0648999…): show 2 decimals
  const cum = split.map(d => ({ date: d.date, market: round2(market += d.market_pp),
    company: round2(company += d.company_pp) }));
  if (cum.length) {
    const common = { xaxis: "x", yaxis: "y3", type: "scatter", mode: "lines" };
    traces.push(
      { ...common, name: "Market, cumulative", x: cum.map(d => d.date), y: cum.map(d => d.market),
        line: { color: COLORS.market, width: 1.5 }, hovertemplate: "%{y:+.2f}pp<extra>Market, cumulative</extra>" },
      { ...common, name: "Company-specific, cumulative", x: cum.map(d => d.date), y: cum.map(d => d.company),
        line: { color: COLORS.company, width: 1.5 }, hovertemplate: "%{y:+.2f}pp<extra>Company-specific, cumulative</extra>" },
    );
  }

  const dollars = series.flatMap(r => [r.close, r.no_growth_value]);
  const shares = series.map(r => r.growth_share_pct);
  const shareLo = Math.floor((Math.min(...shares) - 3) / 10) * 10;
  const shareHi = Math.min(100, Math.ceil((Math.max(...shares) + 3) / 10) * 10);

  // A shape spanning the full height of each panel (but not the gaps between them).
  const yrefs = ["y domain", "y2 domain"].concat(cum.length ? ["y3 domain"] : []);
  const inBothPanels = shape => yrefs.map(yref => ({ ...shape, xref: "x", yref, y0: 0, y1: 1 }));

  // Divergent and outlier periods, shaded in the split panel; a one-day period spans to the next trading day
  const nextDay = Object.fromEntries(split.map((d, i) => [d.date, split[i + 1]?.date || d.date]));
  const periodShapes = cum.length ? periods.filter(p => p.label === "divergent" || p.label === "outlier").map(p => ({
    type: "rect", layer: "below", line: { width: 0 }, fillcolor: COLORS.standsOut,
    xref: "x", yref: "y3 domain", y0: 0, y1: 1, x0: p.start, x1: nextDay[p.end] || p.end,
  })) : [];

  const releaseShapes = releases.flatMap(p => inBothPanels({
    type: "line", x0: p.release_date, x1: p.release_date,
    line: { color: COLORS.release, width: 1, dash: "dot" }, layer: "below",
  }));
  const releaseLabels = releases.map(p => ({
    xref: "x", yref: "y domain", x: p.release_date, y: 1, xanchor: "left", yanchor: "top",
    text: p.release_date, showarrow: false, textangle: -90, xshift: 1,
    font: { size: 9, color: COLORS.axis },
  }));
  // A border around each panel, over everything drawn in it
  const frames = yrefs.map(yref => ({
    type: "rect", xref: "x domain", yref, x0: 0, x1: 1, y0: 0, y1: 1, layer: "above",
    line: { color: COLORS.frame, width: 1 },
  }));
  const windowShape = months.length ? inBothPanels({
    type: "rect", layer: "below", line: { width: 0 }, fillcolor: COLORS.window,
    x0: monthRange(months[0].key)[0], x1: monthRange(months[months.length - 1].key)[1],
  }) : [];

  const axisCommon = {
    gridcolor: COLORS.grid, zeroline: false, linecolor: COLORS.grid,
    tickfont: { size: 10, color: COLORS.axis }, fixedrange: true,
  };

  const layout = {
    margin: { l: 56, r: 12, t: 6, b: 22 },
    paper_bgcolor: COLORS.background, plot_bgcolor: COLORS.background,
    font: { family: COLORS.font, color: COLORS.ink },
    showlegend: false,
    hovermode: "x unified",
    hoverlabel: { bgcolor: COLORS.card, bordercolor: COLORS.monthEdge, font: { size: 11, family: COLORS.font, color: COLORS.ink } },
    xaxis: {
      ...axisCommon, type: "date", range: [first, last], anchor: cum.length ? "y3" : "y2",
      showspikes: true, spikemode: "across", spikethickness: 1, spikecolor: COLORS.axis, spikedash: "solid",
      hoverformat: "%a %b %-d, %Y",
    },
    yaxis: {
      ...axisCommon, domain: panels.price, range: [0, Math.max(...dollars) * 1.25],
      tickprefix: "$", title: { text: "$ per share", font: { size: 11, color: COLORS.axis }, standoff: 6 },
    },
    yaxis2: {
      // 1pp of padding keeps the end ticks' labels inside the panel, clear of the narrow gaps
      ...axisCommon, domain: panels.share, range: [shareLo - 1, shareHi + 1], ticksuffix: "%", nticks: 4,
      title: { text: "Growth share", font: { size: 11, color: COLORS.axis }, standoff: 6 },
    },
    ...(cum.length ? {
      yaxis3: {
        ...axisCommon, domain: panels.split, ticksuffix: "pp", nticks: 4, zeroline: true, zerolinecolor: COLORS.axis,
        hoverformat: "+.2f",
        title: { text: "Cumulative", font: { size: 11, color: COLORS.axis }, standoff: 6 },
      },
    } : {}),
    shapes: [...windowShape, ...periodShapes, ...releaseShapes, ...frames],
    annotations: releaseLabels,
  };

  const baseShapes = layout.shapes;
  Plotly.newPlot(el, traces, layout, { displayModeBar: false, responsive: true });
  // Side by side, the chart takes the column's height left by the slider, which changes without a
  // window resize (the slider's ticks and label are filled after this)
  new ResizeObserver(() => Plotly.Plots.resize(el)).observe(el);

  return {
    highlight(key) {
      const [x0, x1] = monthRange(key);
      Plotly.relayout(el, {
        shapes: [...baseShapes, ...inBothPanels({
          type: "rect", layer: "below", x0, x1,
          fillcolor: COLORS.month, line: { color: COLORS.monthEdge, width: 1 },
        })],
      });
    },
  };
}

// ---------- slider <-> text sync ----------

function wireUp(months, chart, el) {
  const slider = document.getElementById("month-slider");
  const prev = document.getElementById("prev");
  const next = document.getElementById("next");
  const ticks = document.getElementById("ticks");
  const label = document.getElementById("month-label");
  const viz = document.getElementById("viz");

  slider.max = String(months.length - 1);
  ticks.style.setProperty("--n", months.length);
  const tickButtons = months.map((m, i) => {
    const [y, mm] = m.key.split("-");
    const b = document.createElement("button");
    b.type = "button";
    b.textContent = MONTH_NAMES[Number(mm) - 1] + (i === 0 || mm === "01" ? ` ’${y.slice(2)}` : "");
    b.addEventListener("click", () => select(i, "smooth"));
    ticks.appendChild(b);
    return b;
  });

  // Sticky height (the chart block, or on small screens just the slider bar), so a scrolled-to
  // section lands just below it. Side by side, the chart is beside the text and covers none of it.
  const controls = document.getElementById("controls");
  const sideBySide = matchMedia(SIDE_BY_SIDE);
  const stickyHeight = () => {
    if (sideBySide.matches) return 0;
    for (const el of [viz, controls]) if (getComputedStyle(el).position === "sticky") return el.offsetHeight;
    return 0;
  };
  const setStickyVar = () => document.documentElement.style.setProperty("--sticky-h", `${stickyHeight() + 8}px`);
  const resized = new ResizeObserver(setStickyVar);
  resized.observe(viz);
  resized.observe(controls);
  window.addEventListener("resize", setStickyVar);

  let current = -1;
  let programmaticUntil = 0;

  // scroll: false, or the scroll behavior ("smooth" for the controls, "instant" for a link on load).
  function select(i, scroll) {
    i = Math.max(0, Math.min(months.length - 1, i));
    if (i !== current) {
      if (current >= 0 || scroll) history.replaceState(null, "", `#${months[i].key}`);  // not on a plain first load
      current = i;
      const m = months[i];
      slider.value = String(i);
      prev.disabled = i === 0;
      next.disabled = i === months.length - 1;
      tickButtons.forEach((b, j) => b.setAttribute("aria-current", String(j === i)));
      months.forEach((mo, j) => mo.section.classList.toggle("active", j === i));
      label.replaceChildren();
      const strong = document.createElement("strong");
      const [y, mm] = m.key.split("-");
      strong.textContent = `${MONTH_NAMES[Number(mm) - 1]} ${y}`;
      label.append(strong, document.createTextNode(` · ${m.label}`));
      chart.highlight(m.key);
    }
    if (scroll) {
      programmaticUntil = performance.now() + 1200;
      months[i].section.scrollIntoView({ behavior: scroll, block: "start" });
    }
  }

  slider.addEventListener("input", () => select(Number(slider.value), "smooth"));
  prev.addEventListener("click", () => select(current - 1, "smooth"));
  next.addEventListener("click", () => select(current + 1, "smooth"));

  el.on("plotly_click", ev => {
    const x = ev.points && ev.points[0] && String(ev.points[0].x);
    const i = x ? months.findIndex(m => m.key === x.slice(0, 7)) : -1;
    if (i >= 0) select(i, "smooth");
  });

  // Reading the text moves the slider: the active month is the last section whose top has passed
  // the bottom of the sticky chart (or the last one, at the end of the page).
  let ticking = false;
  function onScroll() {
    ticking = false;
    if (performance.now() < programmaticUntil) return;
    const line = stickyHeight() + 60;
    let i = 0;
    months.forEach((m, j) => { if (m.section.getBoundingClientRect().top <= line) i = j; });
    const lastTop = months[months.length - 1].section.getBoundingClientRect().top;
    if (lastTop < window.innerHeight * 0.5) i = months.length - 1;
    select(i, false);
  }
  window.addEventListener("scroll", () => {
    if (!ticking) { ticking = true; requestAnimationFrame(onScroll); }
  }, { passive: true });
  window.addEventListener("scrollend", () => { programmaticUntil = 0; });

  const fromHash = months.findIndex(m => `#${m.key}` === location.hash);
  setStickyVar();
  if (fromHash >= 0) select(fromHash, "instant");
  else select(0, false);
}

// ---------- main ----------

async function main() {
  document.getElementById("chart-title").textContent = CONFIG.chartTitle;
  document.getElementById("footnote").textContent = CONFIG.footnote;
  if (CONFIG.repoUrl) {
    const p = document.getElementById("repo-link");
    p.querySelector("a").href = CONFIG.repoUrl;
    p.hidden = false;
  }

  const container = document.getElementById("explanations");
  try {
    const [seriesText, pointsText, yearEndText, md] = await Promise.all(
      [CONFIG.files.series, CONFIG.files.points, CONFIG.files.yearEnd, CONFIG.files.explanations].map(fetchText));

    const series = parseCSV(seriesText).map(r => ({
      date: r.date, close: num(r.close), no_growth_value: num(r.no_growth_value),
      growth_share_pct: num(r.growth_share_pct), no_growth_value_before_step: num(r.no_growth_value_before_step),
    }));
    const points = parseCSV(pointsText).map(r => ({
      release_date: r.release_date, measurement_date: r.measurement_date, quarter_end: r.quarter_end,
      price: num(r.price), eps_used: r.eps_used,
    }));
    const yearEnd = parseCSV(yearEndText).map(r => ({ date: r.date, growth_share_pct: num(r.growth_share_pct) }));
    // Optional: without them the chart keeps its two panels
    const optional = path => fetch(path).then(r => (r.ok ? r.text() : "")).catch(() => "");
    const [splitText, periodsText] = await Promise.all([optional(CONFIG.files.dailySplit), optional(CONFIG.files.periods)]);
    const split = splitText ? parseCSV(splitText).filter(r => r.company_pp !== "")
      .map(r => ({ date: r.date, market_pp: num(r.market_pp), company_pp: num(r.company_pp) })) : [];
    const periods = periodsText ? parseCSV(periodsText).map(r => ({ start: r.start, end: r.end, label: r.label })) : [];

    const etf = md.match(/market model: S&P 500 \+ ([A-Z][A-Z0-9.]*)/)?.[1];
    if (etf) {
      document.querySelectorAll(".sector-etf").forEach(el => { el.textContent = ` (S&P 500 + ${etf})`; });
      const name = ETF_NAMES[etf] ? ` (${ETF_NAMES[etf]}: the equal-weight fund of the company's GICS sector)` : "";
      document.getElementById("footnote").append(" Market's part: each day's return explained by the S&P 500 " +
        `and the sector ETF, ${etf}${name}, in a regression fitted on the prior 180 trading days; the rest is ` +
        "company-specific.");
    }
    const months = renderExplanations(md, container, document.getElementById("intro"));
    const ev = await fetch(CONFIG.files.evidence).then(r => (r.ok ? r.json() : null)).catch(() => null);
    if (ev) setupEvidence(ev, months);
    const el = document.getElementById("chart");
    const chart = buildChart(el, series, points, yearEnd, months, split, periods);
    if (months.length) wireUp(months, chart, el);
  } catch (err) {
    container.innerHTML = "";
    const p = document.createElement("p");
    p.className = "error";
    p.textContent = `Could not load the data (${err.message}). If you opened the page directly, ` +
      "serve the folder instead: python -m http.server 8000 -d website";
    container.appendChild(p);
    console.error(err);
  }
}

main();
