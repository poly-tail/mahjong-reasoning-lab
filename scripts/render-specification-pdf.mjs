import { renderMarkdownPdf } from "./render-markdown-pdf.mjs";

await renderMarkdownPdf({
  source: "docs/detailed-specification.md",
  output: process.argv[2] ?? "docs/detailed-specification.pdf",
  title: "Mahjong Reasoning Lab 詳細仕様書",
});
