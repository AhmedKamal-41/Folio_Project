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

// Quill attaches block attributes (header, list) to the newline that ends a line,
// so a line's formatting is only known once that trailing newline is reached.
function deltaToParagraphs(ops) {
  const headingLevels = {
    1: docx.HeadingLevel.HEADING_1,
    2: docx.HeadingLevel.HEADING_2,
    3: docx.HeadingLevel.HEADING_3
  };
  const paragraphs = [];
  let runs = [];

  const endLine = (attributes = {}) => {
    const options = { children: runs.length ? runs : [new docx.TextRun("")] };
    if (attributes.header) options.heading = headingLevels[attributes.header];
    if (attributes.list === "bullet") options.bullet = { level: 0 };
    if (attributes.list === "ordered") options.numbering = { reference: "ordered-list", level: 0 };
    paragraphs.push(new docx.Paragraph(options));
    runs = [];
  };

  for (const op of ops) {
    if (typeof op.insert !== "string") continue;
    const attributes = op.attributes || {};
    const lines = op.insert.split("\n");
    lines.forEach((text, index) => {
      if (text) runs.push(new docx.TextRun({
        text,
        bold: attributes.bold,
        italics: attributes.italic,
        underline: attributes.underline ? {} : undefined
      }));
      if (index < lines.length - 1) endLine(attributes);
    });
  }
  if (runs.length) endLine();
  return paragraphs;
}

export async function downloadDraft(editor) {
  const title = $("document-title").value.trim() || "Untitled document";
  const file = new docx.Document({
    numbering: {
      config: [{
        reference: "ordered-list",
        levels: [{ level: 0, format: "decimal", text: "%1.", alignment: docx.AlignmentType.START }]
      }]
    },
    sections: [{
      children: [
        new docx.Paragraph({ text: title, heading: docx.HeadingLevel.TITLE }),
        ...deltaToParagraphs(editor.getContents().ops)
      ]
    }]
  });
  const blob = await docx.Packer.toBlob(file);
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = title.replace(/[<>:"/\\|?*\u0000-\u001f]/g, "_").slice(0, 90) + ".docx";
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
