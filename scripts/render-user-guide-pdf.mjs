import { readFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright";

const rootDir = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const sourcePath = resolve(rootDir, "docs/user-guide.md");
const outputPath = resolve(rootDir, process.argv[2] ?? "docs/user-guide.pdf");

const markdown = await readFile(sourcePath, "utf8");

function escapeHtml(value) {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

function renderInline(value) {
  return escapeHtml(value)
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
}

function closeList(state, html) {
  if (!state.listType) return;
  html.push(`</${state.listType}>`);
  state.listType = null;
}

function closeParagraph(state, html) {
  if (state.paragraph.length === 0) return;
  html.push(`<p>${renderInline(state.paragraph.join(" "))}</p>`);
  state.paragraph = [];
}

function renderMarkdown(value) {
  const html = [];
  const state = {
    paragraph: [],
    listType: null,
    codeBlock: null,
    codeLines: [],
  };

  for (const line of value.split(/\r?\n/)) {
    const codeFence = line.match(/^```(\w*)\s*$/);
    if (codeFence) {
      if (state.codeBlock !== null) {
        html.push(
          `<pre><code>${escapeHtml(state.codeLines.join("\n"))}</code></pre>`,
        );
        state.codeBlock = null;
        state.codeLines = [];
      } else {
        closeParagraph(state, html);
        closeList(state, html);
        state.codeBlock = codeFence[1] || "";
      }
      continue;
    }

    if (state.codeBlock !== null) {
      state.codeLines.push(line);
      continue;
    }

    if (!line.trim()) {
      closeParagraph(state, html);
      closeList(state, html);
      continue;
    }

    const heading = line.match(/^(#{1,3})\s+(.+)$/);
    if (heading) {
      closeParagraph(state, html);
      closeList(state, html);
      const level = heading[1].length;
      html.push(`<h${level}>${renderInline(heading[2])}</h${level}>`);
      continue;
    }

    const unordered = line.match(/^-\s+(.+)$/);
    if (unordered) {
      closeParagraph(state, html);
      if (state.listType !== "ul") {
        closeList(state, html);
        html.push("<ul>");
        state.listType = "ul";
      }
      html.push(`<li>${renderInline(unordered[1])}</li>`);
      continue;
    }

    const ordered = line.match(/^\d+\.\s+(.+)$/);
    if (ordered) {
      closeParagraph(state, html);
      if (state.listType !== "ol") {
        closeList(state, html);
        html.push("<ol>");
        state.listType = "ol";
      }
      html.push(`<li>${renderInline(ordered[1])}</li>`);
      continue;
    }

    state.paragraph.push(line.trim());
  }

  closeParagraph(state, html);
  closeList(state, html);

  return html.join("\n");
}

const html = `<!doctype html>
<html lang="ja">
  <head>
    <meta charset="utf-8" />
    <title>麻雀思考ラボ 使い方ガイド</title>
    <style>
      :root {
        color-scheme: light;
        --ink: #1c1917;
        --muted: #57534e;
        --line: #d6d3d1;
        --soft: #f5f5f4;
        --accent: #0e7490;
      }

      * {
        box-sizing: border-box;
      }

      body {
        margin: 0;
        background: white;
        color: var(--ink);
        font-family:
          "Yu Gothic", "Meiryo", "Noto Sans JP", "Hiragino Kaku Gothic ProN",
          system-ui, sans-serif;
        font-size: 12.5px;
        line-height: 1.72;
      }

      main {
        max-width: 900px;
        margin: 0 auto;
      }

      h1,
      h2,
      h3 {
        line-height: 1.35;
        page-break-after: avoid;
      }

      h1 {
        margin: 0 0 16px;
        padding-bottom: 14px;
        border-bottom: 2px solid var(--accent);
        color: #0f172a;
        font-size: 25px;
        letter-spacing: 0;
      }

      h2 {
        margin: 24px 0 9px;
        padding-left: 10px;
        border-left: 4px solid var(--accent);
        color: #0f172a;
        font-size: 16px;
      }

      h3 {
        margin: 17px 0 8px;
        font-size: 13.5px;
      }

      p {
        margin: 7px 0;
      }

      ul,
      ol {
        margin: 7px 0 10px 1.4em;
        padding: 0;
      }

      li {
        margin: 2px 0;
        padding-left: 0.15em;
      }

      code {
        border: 1px solid var(--line);
        border-radius: 4px;
        background: var(--soft);
        padding: 0.05em 0.35em;
        font-family: "Cascadia Mono", Consolas, monospace;
        font-size: 0.92em;
      }

      pre {
        margin: 9px 0 12px;
        padding: 10px 12px;
        overflow: hidden;
        border: 1px solid var(--line);
        border-radius: 6px;
        background: #fafaf9;
        page-break-inside: avoid;
      }

      pre code {
        border: 0;
        background: transparent;
        padding: 0;
        font-size: 11.5px;
      }

      h1 + p {
        color: var(--muted);
      }

      p,
      li {
        orphans: 2;
        widows: 2;
      }
    </style>
  </head>
  <body>
    <main>${renderMarkdown(markdown)}</main>
  </body>
</html>`;

const browser = await chromium.launch();
try {
  const page = await browser.newPage({
    viewport: { width: 1240, height: 1754 },
  });
  await page.setContent(html, { waitUntil: "networkidle" });
  await page.pdf({
    path: outputPath,
    format: "A4",
    printBackground: true,
    displayHeaderFooter: true,
    headerTemplate: "<span></span>",
    footerTemplate:
      '<div style="width:100%;font-size:8px;color:#78716c;padding:0 16mm;text-align:right;"><span class="pageNumber"></span> / <span class="totalPages"></span></div>',
    margin: {
      top: "16mm",
      right: "16mm",
      bottom: "18mm",
      left: "16mm",
    },
  });
  console.log(`Wrote ${outputPath}`);
} finally {
  await browser.close();
}
