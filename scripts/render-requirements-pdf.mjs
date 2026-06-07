import { renderMarkdownPdf } from "./render-markdown-pdf.mjs";

await renderMarkdownPdf({
  source: "docs/requirements-definition.md",
  output: process.argv[2] ?? "docs/requirements-definition.pdf",
  title: "Mahjong Reasoning Lab 要件定義書",
});
