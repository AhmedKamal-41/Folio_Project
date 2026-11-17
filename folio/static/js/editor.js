import { $ } from "./dom.js";

export function createEditor(onChange) {
  const editor = new Quill("#editor", {
    theme: "snow",
    placeholder: "Start with a thought…",
    formats: ["bold", "italic", "underline", "header", "list"],
    modules: { toolbar: "#toolbar" }
  });
  editor.root.setAttribute("aria-label", "Document content");
  editor.root.setAttribute("role", "textbox");
  editor.root.setAttribute("aria-multiline", "true");
  editor.on("text-change", (delta, previous, source) => {
    if (source === "user") onChange();
  });
  return editor;
}

export function updateWordCount(editor) {
  const text = editor.getText().trim();
  const words = text ? text.split(/\s+/).length : 0;
  $("word-count").textContent = `${words} ${words === 1 ? "word" : "words"}`;
}

export function downloadDraft(editor) {
  const title = $("document-title").value.trim() || "Untitled document";
  const content = `${title}\n\n${editor.getText()}`;
  const blob = new Blob([content], { type: "text/plain;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = title.replace(/[<>:"/\\|?*\u0000-\u001f]/g, "_").slice(0, 90) + ".txt";
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
