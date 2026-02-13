---
name: pdf-to-markdown
description: Converts PDF files to Markdown using Microsoft's markitdown package. Use this skill when the user asks to convert a PDF to Markdown, extract text from a PDF, or read/parse PDF content.
argument-hint: "[path to file]"
---

# PDF to Markdown Conversion

This skill converts PDF files to Markdown format using [Microsoft's markitdown](https://github.com/microsoft/markitdown) package.

## When to use

- User asks to convert a PDF to Markdown
- User wants to extract text content from a PDF
- User needs to read or parse a PDF document
- User asks to summarize or analyze a PDF file

## How to use

Use `uvx` to run markitdown directly. Pick the dependency group matching the file type:

| File type | Dependency group |
|-----------|-----------------|
| PDF       | `pdf`           |
| PowerPoint | `pptx`         |
| Word      | `docx`          |
| Excel (.xlsx) | `xlsx`      |
| Excel (.xls)  | `xls`       |

```bash
uvx 'markitdown[pdf]' <path-to-file> -o output.md
```

Or install all optional dependencies at once:

```bash
uvx 'markitdown[all]' <path-to-file> -o output.md
```

## Examples

```bash
uvx 'markitdown[pdf]' report.pdf -o report.md
uvx 'markitdown[pptx]' slides.pptx -o slides.md
uvx 'markitdown[docx]' document.docx -o document.md
```

## Output

- If you were asked to save the output to a specific file, save it to the requested file using `-o`.
- If no output file was specified, use the source filename with a `.md` suffix.
