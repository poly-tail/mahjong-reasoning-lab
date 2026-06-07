import { renderMarkdownPdf } from "./render-markdown-pdf.mjs";

await renderMarkdownPdf({
  source: "docs/user-guide.md",
  output: process.argv[2] ?? "docs/user-guide.pdf",
  title: "麻雀思考ラボ 使い方ガイド",
});
