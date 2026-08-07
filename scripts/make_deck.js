// Build the capstone presentation deck.
//   node scripts/make_deck.js
// Palette is ams OSRAM: #FD5000 sampled from logo.png.
const P = require("pptxgenjs");
const fs = require("fs");
const path = require("path");

const ROOT = path.join(__dirname, "..");
const OUT = path.join(ROOT, "Database_Knowledge_Assistant.pptx");

// Official ams OSRAM palette, from amsOSRAM_Brand-Guideline.pdf p26-28.
// These are the fixed core elements and may not be altered.
const ORANGE = "FD5000";    // ams OSRAM Orange, Pantone 21C
const INK    = "1D252D";    // Dark Blue, Pantone 433C
const SLATE  = "46555F";    // Grey
const MIST   = "FDF6F1";    // Cream
const WHITE  = "FFFFFF";
const SKY    = "00ADFD";    // Light Blue, Pantone 306C (secondary accent)

// Guideline p32: Lexend is primary, but Arial is the sanctioned secondary
// typeface for office applications - PowerPoint is named explicitly. Lexend
// is not installed on this machine, so Arial is both compliant and safe.
const H = "Arial";
const B = "Arial";

const pres = new P();
pres.layout = "LAYOUT_16x9";          // 10 x 5.625 in
pres.author = "Capstone Team";
pres.title = "Database Knowledge Assistant";

const W = 10, HT = 5.625, M = 0.55;

// ---------- helpers ----------------------------------------------------
function titleBar(s, text, kicker) {
  if (kicker) {
    s.addText(kicker.toUpperCase(), {
      x: M, y: 0.34, w: W - M * 2, h: 0.24,
      fontFace: B, fontSize: 11, bold: true, color: ORANGE, charSpacing: 2, margin: 0,
    });
  }
  s.addText(text, {
    x: M, y: kicker ? 0.60 : 0.42, w: W - M * 2, h: 0.62,
    fontFace: H, fontSize: 30, bold: true, color: INK, margin: 0,
  });
}

// Icon-free "chip" used as the repeating motif: a filled circle with a number.
function chip(s, n, x, y, fill) {
  s.addShape(pres.ShapeType.ellipse, {
    x, y, w: 0.34, h: 0.34, fill: { color: fill || ORANGE },
  });
  s.addText(String(n), {
    x, y, w: 0.34, h: 0.34,
    fontFace: B, fontSize: 13, bold: true, color: WHITE,
    align: "center", valign: "middle", margin: 0,
  });
}

function card(s, x, y, w, h, fill) {
  s.addShape(pres.ShapeType.roundRect, {
    x, y, w, h, rectRadius: 0.06,
    fill: { color: fill || MIST },
    line: { color: fill || MIST, width: 0 },
  });
}

// ---------- 1. title ---------------------------------------------------
{
  const s = pres.addSlide();
  s.background = { color: INK };

  if (fs.existsSync(path.join(ROOT, "logo_sidebar.png"))) {
    s.addImage({ path: path.join(ROOT, "logo_sidebar.png"), x: M, y: 0.5, w: 2.2, h: 0.24 });
  }

  s.addText("Database Knowledge\nAssistant", {
    x: M, y: 1.5, w: 6.6, h: 1.7,
    fontFace: H, fontSize: 42, bold: true, color: WHITE, lineSpacing: 46, margin: 0,
  });
  s.addText("Database telemetry and operational docs — with citations,\nverifiable SQL, and the honesty to refuse", {
    x: M, y: 3.15, w: 6.4, h: 0.75,
    fontFace: B, fontSize: 15, color: "B9C0CA", margin: 0,
  });

  s.addText("Capstone Level 2  \u00b7  AIMP  \u00b7  ams OSRAM Backend Penang", {
    x: M, y: 4.15, w: 6.5, h: 0.3,
    fontFace: B, fontSize: 11, color: "8A97A3", margin: 0,
  });

  // Stat block, right side
  const stats = [["9", "categories met"], ["0.93", "retrieval MRR"], ["44/44", "tests passing"]];
  stats.forEach(([big, lab], i) => {
    const y = 1.25 + i * 1.05;
    s.addText(big, {
      x: 7.35, y, w: 2.1, h: 0.55,
      fontFace: H, fontSize: 34, bold: true, color: ORANGE, align: "right", margin: 0,
    });
    s.addText(lab, {
      x: 7.35, y: y + 0.52, w: 2.1, h: 0.26,
      fontFace: B, fontSize: 11, color: "8C95A1", align: "right", margin: 0,
    });
  });

  s.addNotes("Database Knowledge Assistant — a grounded QA system for factory operations. Built on the Capstone Level 2 Factory Knowledge kit and extended with a text-to-SQL agent, six LLM providers, and a measured evaluation harness. Headline: 9 of 15 categories against a minimum of 5.");
}

// ---------- 2. the problem --------------------------------------------
{
  const s = pres.addSlide();
  titleBar(s, "We added a second engine", "What we built");

  s.addText("The starter kit does RAG over documents. Our DBA teammate brought real session telemetry \u2014 and questions RAG physically cannot answer.", {
    x: M, y: 1.30, w: W - M * 2, h: 0.4,
    fontFace: B, fontSize: 13, color: SLATE, margin: 0,
  });

  const cols = [
    { t: "\u201cWhich database used the most CPU?\u201d",
      e: "Text-to-SQL over telemetry  \u2014  our extension",
      w: "No document contains this. It must be computed across 2,372 rows.",
      c: INK, tc: WHITE },
    { t: "\u201cWhat does alarm code E-204 mean?\u201d",
      e: "RAG over documents  \u2014  the kit baseline",
      w: "The answer is written down. Find it, quote it, cite the source.",
      c: MIST, tc: INK },
  ];

  cols.forEach((c, i) => {
    const x = M + i * 4.6;
    card(s, x, 1.85, 4.3, 2.75, c.c);
    s.addText(c.t, {
      x: x + 0.3, y: 2.10, w: 3.7, h: 0.7,
      fontFace: H, fontSize: 16, bold: true, color: c.tc, margin: 0,
    });
    s.addText(c.e, {
      x: x + 0.3, y: 2.95, w: 3.7, h: 0.3,
      fontFace: B, fontSize: 12, bold: true, color: ORANGE, margin: 0,
    });
    s.addText(c.w, {
      x: x + 0.3, y: 3.32, w: 3.7, h: 0.9,
      fontFace: B, fontSize: 12, color: c.tc === WHITE ? "B9C0CA" : SLATE, margin: 0,
    });
  });

  s.addText("Retrieval cannot SUM. Sending a spreadsheet question to RAG is how you get a confident wrong number.", {
    x: M, y: 4.80, w: W - M * 2, h: 0.35,
    fontFace: B, fontSize: 12, italic: true, color: INK, margin: 0,
  });

  s.addNotes("Lead with this: the trainer asked us not to simply follow the provided example. The kit gives you RAG over documents. Our DBA-team member brought real SQL Server session telemetry and the questions that go with it - and those questions cannot be answered by retrieval at all. 'Which database used the most CPU' requires aggregating 2,372 rows — retrieval physically cannot do that. So we route: documents to RAG, telemetry to text-to-SQL. Each answer type gets the tool that can actually produce it.");
}

// ---------- 3. architecture -------------------------------------------
{
  const s = pres.addSlide();
  titleBar(s, "How a question flows", "Architecture");

  const boxW = 1.75, boxH = 0.62, y1 = 1.75;

  // Question
  card(s, M, y1, boxW, boxH, MIST);
  s.addText("Question", { x: M, y: y1, w: boxW, h: boxH, fontFace: B, fontSize: 12, bold: true, color: INK, align: "center", valign: "middle", margin: 0 });

  // Router
  const rx = M + 2.15;
  card(s, rx, y1, boxW, boxH, INK);
  s.addText("Router", { x: rx, y: y1, w: boxW, h: boxH, fontFace: B, fontSize: 12, bold: true, color: WHITE, align: "center", valign: "middle", margin: 0 });

  s.addShape(pres.ShapeType.line, { x: M + boxW, y: y1 + boxH / 2, w: 0.40, h: 0, line: { color: SLATE, width: 1.5, endArrowType: "triangle" } });

  // Two branches
  const bx = rx + 2.15;
  const branches = [
    { y: 1.30, t: "RAG  ·  3 specialists", d: "Maintenance · Safety · Quality\nChroma vector search + citations" },
    { y: 2.55, t: "Text-to-SQL agent", d: "SQLite over 2,372 telemetry rows\nread-only, ships its query" },
  ];
  branches.forEach((b) => {
    card(s, bx, b.y, 3.35, 1.02, MIST);
    s.addText(b.t, { x: bx + 0.22, y: b.y + 0.12, w: 3.0, h: 0.28, fontFace: B, fontSize: 12, bold: true, color: ORANGE, margin: 0 });
    s.addText(b.d, { x: bx + 0.22, y: b.y + 0.42, w: 3.0, h: 0.52, fontFace: B, fontSize: 10.5, color: SLATE, margin: 0 });
  });

  // One elbow connector per branch, from the router's right edge to each card.
  branches.forEach((b) => {
    const sy = y1 + boxH / 2;
    const ty = b.y + 0.51;
    s.addShape(pres.ShapeType.line, { x: rx + boxW, y: sy, w: 0.20, h: 0, line: { color: SLATE, width: 1.5 } });
    s.addShape(pres.ShapeType.line, {
      x: rx + boxW + 0.20, y: Math.min(sy, ty), w: 0, h: Math.abs(ty - sy),
      line: { color: SLATE, width: 1.5 },
    });
    s.addShape(pres.ShapeType.line, { x: rx + boxW + 0.20, y: ty, w: 0.20, h: 0, line: { color: SLATE, width: 1.5, endArrowType: "triangle" } });
  });

  // Guardrail band
  card(s, M, 3.95, W - M * 2, 0.92, INK);
  s.addText("Guardrail runs BEFORE the model is called", {
    x: M + 0.3, y: 4.08, w: 4.6, h: 0.3,
    fontFace: B, fontSize: 12, bold: true, color: WHITE, margin: 0,
  });
  s.addText("trusted = [h for h in hits if h.score >= min_score]  \u2192  if empty, refuse", {
    x: M + 0.3, y: 4.40, w: 8.6, h: 0.3,
    fontFace: "Courier New", fontSize: 11, color: ORANGE, margin: 0,
  });

  s.addNotes("A question hits the router, which picks the engine. RAG path: one of three specialists, each with its own isolated vector collection. SQL path: the telemetry agent. The critical detail is the guardrail — it is deterministic Python that runs BEFORE the LLM is called. If no chunk clears the score floor, we refuse. The model never gets the chance to invent.");
}

// ---------- 4. evaluation ---------------------------------------------
{
  const s = pres.addSlide();
  titleBar(s, "We measured it, we didn't assume it", "Evaluation");

  s.addText("17-case golden set. Mean Reciprocal Rank across every chunking strategy and retriever.", {
    x: M, y: 1.32, w: W - M * 2, h: 0.32,
    fontFace: B, fontSize: 13, color: SLATE, margin: 0,
  });

  s.addChart(pres.ChartType.bar, [{
    name: "MRR",
    labels: ["metadata_aware", "fixed", "recursive", "hybrid RRF", "BM25"],
    values: [0.93, 0.92, 0.88, 0.88, 0.70],
  }], {
    x: M, y: 1.80, w: 5.5, h: 2.95,
    barDir: "bar",
    chartColors: [ORANGE, "C8CDD4", "C8CDD4", "C8CDD4", "C8CDD4"],
    varyColors: true,
    showValue: true, dataLabelPosition: "outEnd",
    dataLabelFontFace: B, dataLabelFontSize: 10, dataLabelColor: INK,
    dataLabelFormatCode: "0.00",
    catAxisLabelColor: INK, catAxisLabelFontFace: B, catAxisLabelFontSize: 10,
    valAxisLabelColor: SLATE, valAxisLabelFontSize: 9,
    valAxisMaxVal: 1.0,
    valGridLine: { color: "E6E8EB", size: 1 },
    catGridLine: { style: "none" },
    showLegend: false, showTitle: false,
  });

  const findings = [
    ["Best config", "metadata_aware chunking\n+ vector retrieval  \u2192  MRR 0.93"],
    ["Reported as found", "Hybrid RRF scored WORSE than\npure vector (0.88 vs 0.93)"],
    ["Hit@5", "1.00 across all strategies —\nthe right doc is always retrieved"],
  ];
  findings.forEach((f, i) => {
    const y = 1.80 + i * 1.02;
    chip(s, i + 1, 6.35, y + 0.02);
    s.addText(f[0], { x: 6.82, y, w: 2.7, h: 0.26, fontFace: B, fontSize: 12, bold: true, color: INK, margin: 0 });
    s.addText(f[1], { x: 6.82, y: y + 0.28, w: 2.75, h: 0.62, fontFace: B, fontSize: 10.5, color: SLATE, margin: 0 });
  });

  s.addText("Hybrid retrieval is widely recommended. On our corpus it lost. We report the measurement, not the expectation.", {
    x: M, y: 4.92, w: W - M * 2, h: 0.3,
    fontFace: B, fontSize: 11.5, italic: true, color: INK, margin: 0,
  });

  s.addNotes("Every design choice here is backed by a number. We built a 17-case golden set and benchmarked all four chunking strategies against all three retrievers. metadata_aware plus vector won at 0.93 MRR. Note the second finding: hybrid RRF is the textbook recommendation and it scored worse than plain vector on our corpus. We kept the result rather than hiding it.");
}

// ---------- 5. abstention ---------------------------------------------
{
  const s = pres.addSlide();
  s.background = { color: INK };

  s.addText("GROUNDING", { x: M, y: 0.34, w: 6, h: 0.24, fontFace: B, fontSize: 11, bold: true, color: ORANGE, charSpacing: 2, margin: 0 });
  s.addText("Knowing when to say nothing", { x: M, y: 0.60, w: 8.9, h: 0.62, fontFace: H, fontSize: 30, bold: true, color: WHITE, margin: 0 });

  s.addText("Score distributions, measured on our corpus:", {
    x: M, y: 1.38, w: 8.9, h: 0.3, fontFace: B, fontSize: 13, color: "B9C0CA", margin: 0,
  });

  const rows = [
    ["Grounded questions", "0.643  \u2014  0.847", ORANGE],
    ["Adversarial questions", "0.500  \u2014  0.673", "9BA6B2"],
  ];
  rows.forEach((r, i) => {
    const y = 1.82 + i * 0.72;
    s.addText(r[0], { x: M, y, w: 3.0, h: 0.4, fontFace: B, fontSize: 13, color: WHITE, valign: "middle", margin: 0 });
    s.addText(r[1], { x: 3.6, y, w: 2.6, h: 0.4, fontFace: "Courier New", fontSize: 15, bold: true, color: r[2], valign: "middle", margin: 0 });
  });

  card(s, 6.55, 1.75, 2.9, 1.45, "262A30");
  s.addText("0.68", { x: 6.55, y: 1.88, w: 2.9, h: 0.6, fontFace: H, fontSize: 36, bold: true, color: ORANGE, align: "center", margin: 0 });
  s.addText("abstain floor\nset just above the adversarial ceiling", {
    x: 6.75, y: 2.50, w: 2.5, h: 0.55, fontFace: B, fontSize: 10.5, color: "B9C0CA", align: "center", margin: 0,
  });

  s.addText("The honest part: these ranges overlap.", {
    x: M, y: 3.45, w: 8.9, h: 0.32, fontFace: B, fontSize: 14, bold: true, color: WHITE, margin: 0,
  });
  s.addText("An adversarial question can score 0.673 while a real one scores 0.643. No threshold separates them cleanly — every floor trades false refusals against false answers. We chose the value, and we can defend why.",
    { x: M, y: 3.80, w: 8.9, h: 0.75, fontFace: B, fontSize: 12, color: "B9C0CA", margin: 0 });

  s.addText("Live demo:  ask for alarm code Z-999  \u2014  it does not exist  \u2014  the system refuses instead of improvising.", {
    x: M, y: 4.72, w: 8.9, h: 0.32, fontFace: B, fontSize: 11.5, italic: true, color: ORANGE, margin: 0,
  });

  s.addNotes("This is the slide to linger on. We measured what grounded and adversarial questions actually score. The floor at 0.68 sits just above where fake questions top out. But be honest: the ranges overlap, so no threshold is perfect. Any floor trades false refusals against false answers. Demo: ask about alarm code Z-999, which does not exist, and watch it refuse.");
}

// ---------- 6. text-to-SQL --------------------------------------------
{
  const s = pres.addSlide();
  titleBar(s, "Numbers you can re-run", "Tool use");

  s.addText("2,372 rows of SQL Server session telemetry, loaded into an in-memory SQLite snapshot. Read-only whitelist.", {
    x: M, y: 1.30, w: W - M * 2, h: 0.32, fontFace: B, fontSize: 13, color: SLATE, margin: 0,
  });

  card(s, M, 1.78, 5.35, 2.15, INK);
  s.addText("\u201cWhich database used the most CPU in total?\u201d", {
    x: M + 0.28, y: 1.94, w: 4.8, h: 0.3, fontFace: B, fontSize: 12, bold: true, color: WHITE, margin: 0,
  });
  s.addText("SELECT DB_NAME, SUM(CPU_TIME) AS total_cpu\nFROM sessions\nGROUP BY DB_NAME\nORDER BY total_cpu DESC\nLIMIT 1;", {
    x: M + 0.28, y: 2.30, w: 4.9, h: 1.0, fontFace: "Courier New", fontSize: 10.5, color: ORANGE, margin: 0,
  });
  s.addText("db06  \u2014  60,214,551 ms  across 1,242 sessions", {
    x: M + 0.28, y: 3.44, w: 4.9, h: 0.3, fontFace: B, fontSize: 11.5, bold: true, color: WHITE, margin: 0,
  });

  const pts = [
    ["Every answer ships its SQL", "The number is auditable — re-run the query and check it yourself."],
    ["Read-only by construction", "A whitelist rejects anything that is not a SELECT."],
    ["Two-layer test suite", "44 deterministic tests with no LLM; 46 end-to-end with one."],
  ];
  pts.forEach((p, i) => {
    const y = 1.82 + i * 0.75;
    chip(s, i + 1, 6.25, y);
    s.addText(p[0], { x: 6.72, y: y - 0.02, w: 2.85, h: 0.26, fontFace: B, fontSize: 12, bold: true, color: INK, margin: 0 });
    s.addText(p[1], { x: 6.72, y: y + 0.24, w: 2.85, h: 0.5, fontFace: B, fontSize: 10.5, color: SLATE, margin: 0 });
  });

  s.addText("Finding: qwen2.5:3b scored 45/46 — it invented a WHERE clause and returned 28.6M instead of 60.2M. Small local models are weak at SQL; we route this path to a stronger model.", {
    x: M, y: 4.20, w: W - M * 2, h: 0.55, fontFace: B, fontSize: 11, italic: true, color: INK, margin: 0,
  });

  s.addNotes("The telemetry agent. Natural language in, SQL out, and crucially the SQL is shown with every answer so any number can be verified. Read-only whitelist. And a real finding from testing: the small local model qwen2.5:3b fails one case by hallucinating a WHERE status='running' filter — right database, wrong number. That is why we route SQL to a stronger model and keep local models for RAG.");
}

// ---------- 7. providers + UI -----------------------------------------
{
  const s = pres.addSlide();
  titleBar(s, "Runs offline. Or on any model you own.", "Deployment");

  const provs = ["Ollama", "LM Studio", "OpenAI", "Anthropic", "GitHub Copilot", "Retrieval-only"];
  provs.forEach((p, i) => {
    const x = M + (i % 3) * 3.08;
    const y = 1.40 + Math.floor(i / 3) * 0.62;
    card(s, x, y, 2.85, 0.48, i < 2 ? INK : MIST);
    s.addText(p, {
      x, y, w: 2.85, h: 0.48,
      fontFace: B, fontSize: 12, bold: true,
      color: i < 2 ? WHITE : INK, align: "center", valign: "middle", margin: 0,
    });
  });
  s.addText("Local-first (highlighted) — factory documents never have to leave the site.", {
    x: M, y: 2.68, w: W - M * 2, h: 0.3, fontFace: B, fontSize: 11.5, italic: true, color: SLATE, margin: 0,
  });

  const eng = [
    ["Live model discovery", "Model lists come from each provider's API — never hardcoded. Copilot exposed 38 models, OpenAI 73."],
    ["Attribution on every reply", "Each answer names the provider AND model that produced it, so a failure points at one model."],
    ["Credentials never touch disk", "Keys entered in the sidebar, held in process. Copilot uses browser device-flow sign-in."],
  ];
  eng.forEach((e, i) => {
    const y = 3.16 + i * 0.62;
    chip(s, i + 1, M, y);
    s.addText(e[0], { x: M + 0.47, y: y - 0.02, w: 2.6, h: 0.26, fontFace: B, fontSize: 11.5, bold: true, color: INK, margin: 0 });
    s.addText(e[1], { x: 3.15, y: y - 0.02, w: 6.3, h: 0.52, fontFace: B, fontSize: 10.5, color: SLATE, margin: 0 });
  });

  s.addNotes("Six providers behind one interface. The two highlighted are local — the system runs fully offline, which matters because factory documentation is confidential. Engineering detail worth mentioning: we fetch model lists live from each provider. A hardcoded list caused an HTTP 400 because it named models the account was not entitled to. Live discovery found 38 on Copilot and 73 on OpenAI.");
}

// ---------- 8. categories ---------------------------------------------
{
  const s = pres.addSlide();
  titleBar(s, "Nine categories, minimum was five", "Scope");

  const met = [
    ["1", "Working Prototype", "Streamlit app, live demo"],
    ["2", "RAG", "Chroma, citations, abstention"],
    ["3", "Advanced Chunking", "4 strategies, benchmarked"],
    ["5", "Memory", "6 turns fed back into the prompt"],
    ["6", "Tool Use", "Text-to-SQL over telemetry"],
    ["8", "Local LLM", "Ollama + LM Studio"],
    ["10", "Multiple Sources", "16 docs, 3 corpora, + XLSX"],
    ["12", "Evaluation", "17-case golden set, MRR"],
    ["13", "Deployment", "Docker, launchers, GitHub"],
  ];

  met.forEach((m, i) => {
    const x = M + (i % 3) * 3.08;
    const y = 1.38 + Math.floor(i / 3) * 0.92;
    card(s, x, y, 2.85, 0.78, MIST);
    s.addText(m[0], {
      x: x + 0.14, y: y + 0.13, w: 0.42, h: 0.52,
      fontFace: H, fontSize: 19, bold: true, color: ORANGE, align: "center", margin: 0,
    });
    s.addText(m[1], { x: x + 0.62, y: y + 0.11, w: 2.1, h: 0.26, fontFace: B, fontSize: 11, bold: true, color: INK, margin: 0 });
    s.addText(m[2], { x: x + 0.62, y: y + 0.37, w: 2.15, h: 0.34, fontFace: B, fontSize: 9.5, color: SLATE, margin: 0 });
  });

  card(s, M, 4.28, W - M * 2, 0.82, INK);
  s.addText("Not claimed:  Category 4, Agent / LangGraph", {
    x: M + 0.3, y: 4.40, w: 4.4, h: 0.28, fontFace: B, fontSize: 12, bold: true, color: ORANGE, margin: 0,
  });
  s.addText("This is a router + RAG + text-to-SQL system. The router picks a persona; it does not plan, loop, or act. We built the grounding properly rather than an agent layer on top of it.", {
    x: M + 0.3, y: 4.66, w: 8.6, h: 0.34, fontFace: B, fontSize: 10.5, color: "B9C0CA", margin: 0,
  });

  s.addNotes("Nine of fifteen categories against a minimum of five. And one deliberate omission, stated up front: we do not claim Category 4. There is no LangGraph, no planning loop, no agent that takes actions. The router selects a persona. We would rather build the grounding properly and say so than bolt on a state machine we cannot defend.");
}

// ---------- 9. team ----------------------------------------------------
{
  const s = pres.addSlide();
  titleBar(s, "Who built what", "Team");

  const team = [
    ["Sylvia Wong Shiau Ching", "(feature)"],
    ["Chin Ee Mei", "(feature)"],
    ["Khoo Yeong Kang", "(feature)"],
    ["Muhammad Muzzammil Bin Mohd Salahudin", "(feature)"],
    ["Phuah Hong", "(feature)"],
  ];

  team.forEach((t, i) => {
    const y = 1.42 + i * 0.66;
    card(s, M, y, W - M * 2, 0.54, i % 2 === 0 ? MIST : WHITE);
    chip(s, i + 1, M + 0.16, y + 0.10);
    s.addText(t[0], {
      x: M + 0.66, y, w: 4.4, h: 0.54,
      fontFace: B, fontSize: 13, bold: true, color: INK, valign: "middle", margin: 0,
    });
    s.addText(t[1], {
      x: 5.4, y, w: 4.05, h: 0.54,
      fontFace: B, fontSize: 12, color: SLATE, valign: "middle", margin: 0,
    });
  });

  s.addText("Each member owns their area end to end and can walk through the code on request.", {
    x: M, y: 4.85, w: W - M * 2, h: 0.3,
    fontFace: B, fontSize: 11.5, italic: true, color: SLATE, margin: 0,
  });

  s.addNotes("PLACEHOLDER — fill in each member's feature before presenting. Ten feature areas are listed in the README: RAG core, chunking, retrievers, evaluation harness, text-to-SQL agent, provider routing, UI and branding, session persistence, test suites, deployment. Whoever owns an area must be able to open those files and explain them.");
}

// ---------- 10. close --------------------------------------------------
{
  const s = pres.addSlide();
  s.background = { color: INK };

  s.addText("DEMO", { x: M, y: 0.9, w: 6, h: 0.24, fontFace: B, fontSize: 11, bold: true, color: ORANGE, charSpacing: 2, margin: 0 });
  s.addText("Three questions,\nthree behaviours", {
    x: M, y: 1.20, w: 5.6, h: 1.3, fontFace: H, fontSize: 34, bold: true, color: WHITE, lineSpacing: 38, margin: 0,
  });

  const demo = [
    ["Documented", "\u201cWhat does alarm code E-204 mean?\u201d", "answers with a citation"],
    ["Computed", "\u201cWhich database used the most CPU?\u201d", "answers with its SQL"],
    ["Unknowable", "\u201cWhat does alarm code Z-999 mean?\u201d", "refuses"],
  ];
  demo.forEach((d, i) => {
    const y = 2.70 + i * 0.72;
    chip(s, i + 1, M, y);
    s.addText(d[0], { x: M + 0.47, y: y - 0.03, w: 1.5, h: 0.26, fontFace: B, fontSize: 11, bold: true, color: ORANGE, margin: 0 });
    s.addText(d[1], { x: M + 0.47, y: y + 0.23, w: 4.3, h: 0.28, fontFace: B, fontSize: 12, color: WHITE, margin: 0 });
    s.addText(d[2], { x: 5.35, y: y + 0.05, w: 1.9, h: 0.28, fontFace: B, fontSize: 11, italic: true, color: "8C95A1", margin: 0 });
  });

  card(s, 7.45, 2.62, 2.0, 2.02, "262A30");
  s.addText("The point", { x: 7.45, y: 2.80, w: 2.0, h: 0.26, fontFace: B, fontSize: 11, bold: true, color: ORANGE, align: "center", margin: 0 });
  s.addText("A system that\nrefuses is more\nuseful than one\nthat guesses.", {
    x: 7.60, y: 3.15, w: 1.75, h: 1.1, fontFace: H, fontSize: 13, color: WHITE, align: "center", margin: 0,
  });

  s.addText("github.com/  \u2014  add repository URL before presenting", {
    x: M, y: 4.92, w: 8.9, h: 0.3, fontFace: B, fontSize: 10.5, color: SLATE, margin: 0,
  });

  s.addNotes("Close on the live demo. Three questions that show three different behaviours: one answered from documents with a citation, one computed with SQL shown, and one refused because the answer does not exist. That third one is the whole thesis — a system that refuses is more useful than one that guesses. Remember to put the GitHub URL on this slide.");
}

pres.writeFile({ fileName: OUT }).then(() => console.log("wrote", OUT));
