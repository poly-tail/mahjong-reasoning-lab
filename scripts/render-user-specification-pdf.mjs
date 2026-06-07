import { renderMarkdownPdf } from "./render-markdown-pdf.mjs";

await renderMarkdownPdf({
  source: "docs/specification.md",
  output: process.argv[2] ?? "docs/specification.pdf",
  title: "麻雀思考ラボ ユーザー向け仕様書",
});
