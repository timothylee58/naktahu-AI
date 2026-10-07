/**
 * List every user-visible English string in the walkthrough scripts, and
 * check the BM/ZH tables cover them.
 *
 *   node tools/walkthrough_strings.mjs            # print the strings as JSON
 *   node tools/walkthrough_strings.mjs --check    # exit 1 listing untranslated strings
 *
 * Uses the TypeScript AST rather than a regex: string literals and JSX text
 * are collected, then anything that is styling, an id, an import path or a
 * prop that never reaches the screen (tone, kind, side, …) is dropped.
 */
import fs from "node:fs";
import path from "node:path";
import ts from "typescript";

const DIR = path.resolve("src/Walkthrough");
const FILES = ["ask.tsx", "business.tsx", "life.tsx", "ui.tsx", "Walkthrough.tsx"];
// props/keys whose values are never shown as text
const SKIP_KEYS = new Set([
  "style", "key", "id", "d", "viewBox", "fill", "stroke", "strokeWidth", "strokeLinecap", "strokeLinejoin",
  "tone", "kind", "side", "color", "hue", "audio", "active", "l", "lang", "icon", "transformOrigin",
  "fontFamily", "background", "border", "boxShadow", "padding", "src", "href", "number",
]);
// a value is styling only if EVERY token is a CSS token ("0 0 60px rgba(…)"),
// so copy that merely starts with a number ("3 matching grants") is kept
const CSS_TOKEN = /^(-?[\d.]+(px|%|em|deg|s|ms|fr)?|#[0-9a-f]{3,8}|rgba?\(.*|hsla?\(.*|linear-.*|radial-.*|inset|solid|dashed|auto|none|[a-z-]+\(.*|.*\)|,),?$/i;
const isCss = (t) => t.split(/\s+/).every((tok) => CSS_TOKEN.test(tok));

const found = new Set();
const keep = (s) => {
  const t = s.trim();
  if (!t || !/[A-Za-zÀ-ɏ一-鿿]/.test(t)) return false;
  if (isCss(t)) return false;
  if (/^[a-z0-9_-]+$/.test(t)) return false; // css keywords, ids, file stems
  if (/\.(tsx?|wav|pdf|png|json)$/.test(t) && !/\s/.test(t)) return false;
  return true;
};

const skipByAncestor = (node) => {
  for (let p = node.parent; p; p = p.parent) {
    if (ts.isImportDeclaration(p) || ts.isExportDeclaration(p)) return true;
    if (ts.isJsxAttribute(p) && SKIP_KEYS.has(p.name.getText())) return true;
    if (ts.isPropertyAssignment(p) && SKIP_KEYS.has(p.name.getText())) return true;
    if (ts.isTypeNode(p)) return true;
    if (ts.isElementAccessExpression(p)) return true;
  }
  return false;
};

for (const f of FILES) {
  const src = ts.createSourceFile(f, fs.readFileSync(path.join(DIR, f), "utf8"), ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
  const visit = (n) => {
    if ((ts.isStringLiteral(n) || ts.isNoSubstitutionTemplateLiteral(n)) && !skipByAncestor(n) && keep(n.text)) {
      // property keys of object literals are not text
      if (!(ts.isPropertyAssignment(n.parent) && n.parent.name === n)) found.add(n.text);
    }
    if (ts.isJsxText(n) && !skipByAncestor(n)) {
      const t = n.text.replace(/\s+/g, " ").replace(/&amp;/g, "&").trim();
      if (keep(t)) found.add(t);
    }
    ts.forEachChild(n, visit);
  };
  visit(src);
}

const strings = [...found].sort();
if (!process.argv.includes("--check")) {
  console.log(JSON.stringify(strings, null, 1));
  process.exit(0);
}

// --check: compare against the tables (parsed as data, no TS import needed)
const table = (lang) => {
  const s = fs.readFileSync(path.join(DIR, `wt.${lang}.ts`), "utf8");
  const body = s.slice(s.indexOf("{"), s.lastIndexOf("}") + 1);
  return JSON.parse(body);
};
let missing = 0;
for (const lang of ["bm", "zh"]) {
  const t = table(lang);
  const gaps = strings.filter((s) => !(s in t));
  const stale = Object.keys(t).filter((k) => !found.has(k));
  missing += gaps.length;
  console.log(`${lang}: ${strings.length - gaps.length}/${strings.length} translated${stale.length ? `, ${stale.length} unused` : ""}`);
  for (const g of gaps) console.log(`  missing: ${JSON.stringify(g)}`);
}
process.exit(missing ? 1 : 0);
