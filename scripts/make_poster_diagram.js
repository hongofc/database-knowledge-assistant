// Architecture diagram for the AIMP capstone poster.
// One slide, rendered to PNG for the "WHAT WE BUILT" panel.
// Palette is the official ams OSRAM spec (brand guideline p26-28).

const PptxGenJS = require("pptxgenjs");

const ORANGE = "FD5000";
const DARK   = "1D252D";
const GREY   = "46555F";
const CREAM  = "FDF6F1";
const WHITE  = "FFFFFF";

const pptx = new PptxGenJS();
pptx.defineLayout({ name: "DIAG", width: 13.33, height: 7.0 });
pptx.layout = "DIAG";

const s = pptx.addSlide();
s.background = { color: WHITE };

// ---- helpers --------------------------------------------------------------
function box(x, y, w, h, opts = {}) {
  s.addShape(pptx.ShapeType.roundRect, {
    x, y, w, h,
    rectRadius: 0.06,
    fill: { color: opts.fill || WHITE },
    line: { color: opts.line || GREY, width: opts.lw || 1.25 },
    shadow: { type: "none" },
  });
}

function label(x, y, w, h, text, opts = {}) {
  s.addText(text, {
    x, y, w, h,
    fontFace: "Arial",
    fontSize: opts.size || 12,
    bold: opts.bold || false,
    color: opts.color || DARK,
    align: opts.align || "center",
    valign: opts.valign || "middle",
    lineSpacingMultiple: 0.95,
  });
}

function node(x, y, w, h, title, sub, opts = {}) {
  box(x, y, w, h, opts);
  if (sub) {
    label(x, y + 0.08, w, h * 0.52, title, {
      size: opts.size || 12.5, bold: true, color: opts.color || DARK,
    });
    label(x, y + h * 0.52, w, h * 0.42, sub, {
      size: opts.subSize || 9.5, color: opts.subColor || GREY,
    });
  } else {
    label(x, y, w, h, title, { size: opts.size || 12.5, bold: true, color: opts.color || DARK });
  }
}

// straight arrow
function arrow(x1, y1, x2, y2, color = GREY) {
  s.addShape(pptx.ShapeType.line, {
    x: x1, y: y1, w: x2 - x1, h: y2 - y1,
    line: { color, width: 1.75, endArrowType: "triangle" },
  });
}

// elbow: horizontal then vertical then horizontal
function elbow(x1, y1, x2, y2, color = GREY) {
  const midX = x1 + (x2 - x1) / 2;
  s.addShape(pptx.ShapeType.line, { x: x1, y: y1, w: midX - x1, h: 0, line: { color, width: 1.75 } });
  s.addShape(pptx.ShapeType.line, { x: midX, y: Math.min(y1, y2), w: 0, h: Math.abs(y2 - y1), line: { color, width: 1.75 } });
  s.addShape(pptx.ShapeType.line, { x: midX, y: y2, w: x2 - midX, h: 0, line: { color, width: 1.75, endArrowType: "triangle" } });
}

// ---- row 1: question ------------------------------------------------------
node(0.35, 3.05, 1.75, 0.95, "Question", "plain English", {
  fill: DARK, color: WHITE, subColor: "C9D1D6", line: DARK,
});

// ---- row 2: router --------------------------------------------------------
node(2.45, 3.05, 1.6, 0.95, "Router", "keyword / LLM", { fill: CREAM, line: ORANGE, lw: 1.75 });
arrow(2.10, 3.52, 2.42, 3.52, DARK);

// ---- branch A: three document specialists ---------------------------------
const AX = 4.45, AW = 2.15;
label(AX, 0.52, AW, 0.3, "RETRIEVAL  (the kit baseline)", { size: 9, bold: true, color: GREY, align: "left" });
node(AX, 0.90, AW, 0.78, "Maintenance", "55 chunks");
node(AX, 1.78, AW, 0.78, "Safety", "51 chunks");
node(AX, 2.66, AW, 0.78, "Quality", "47 chunks");

elbow(4.05, 3.35, 4.42, 1.29);
elbow(4.05, 3.45, 4.42, 2.17);
elbow(4.05, 3.52, 4.42, 3.05);

// vector store
node(7.00, 1.78, 2.05, 0.95, "ChromaDB", "text-embedding-3-small", { subSize: 8.5 });
arrow(6.62, 1.29, 6.97, 2.05, GREY);
arrow(6.62, 2.17, 6.97, 2.22, GREY);
arrow(6.62, 3.05, 6.97, 2.45, GREY);

// the guardrail - emphasised
node(9.45, 1.78, 2.15, 0.95, "Score floor  0.60", "drop chunks below it", {
  fill: ORANGE, color: WHITE, subColor: "FFE2D4", line: ORANGE, size: 12,
});
arrow(9.07, 2.25, 9.42, 2.25, DARK);

// ---- branch B: text-to-SQL ------------------------------------------------
label(AX, 4.30, 3.2, 0.3, "TEXT-TO-SQL  (our extension)", { size: 9, bold: true, color: ORANGE, align: "left" });
node(AX, 4.66, AW, 0.95, "DBA agent", "schema-aware", { fill: DARK, color: WHITE, subColor: "C9D1D6", line: DARK });
elbow(4.05, 3.75, 4.42, 5.13);

node(7.00, 4.66, 2.05, 0.95, "Generated SQL", "shown to the user", { line: ORANGE, lw: 1.75 });
arrow(6.62, 5.13, 6.97, 5.13, GREY);

node(9.45, 4.66, 2.15, 0.95, "SQLite", "2,372 telemetry rows", { subSize: 9 });
arrow(9.07, 5.13, 9.42, 5.13, GREY);

// ---- answer ---------------------------------------------------------------
node(11.95, 3.05, 1.05, 0.95, "Answer", "", { fill: DARK, color: WHITE, line: DARK, size: 11.5 });
elbow(11.62, 2.25, 11.92, 3.35);
elbow(11.62, 5.13, 11.92, 3.75);

// refusal path
s.addShape(pptx.ShapeType.line, {
  x: 10.52, y: 2.75, w: 0, h: 0.62,
  line: { color: ORANGE, width: 1.75, dashType: "dash", endArrowType: "triangle" },
});
label(9.30, 3.38, 2.45, 0.34, "nothing clears the floor", { size: 9, color: ORANGE, bold: true });
label(9.30, 3.68, 2.45, 0.34, '→ "I could not find this"', { size: 9.5, color: DARK, bold: true });

// ---- footer facts ---------------------------------------------------------
s.addShape(pptx.ShapeType.line, { x: 0.35, y: 6.28, w: 12.63, h: 0, line: { color: "D8DCDE", width: 1 } });
label(0.35, 6.36, 12.63, 0.4,
  "16 documents  ·  153 chunks  ·  2,372 telemetry rows  ·  answered 7/8 in-corpus questions, refused 4/4 out-of-corpus  ·  median 3.7 s",
  { size: 10, color: GREY });

pptx.writeFile({ fileName: "poster_architecture.pptx" }).then(() => console.log("built poster_architecture.pptx"));
