---
name: word-file-to-handwritten
description: Convert a Word file (.docx), typed PDF, text file, notes or pasted text into a realistic handwritten-looking PDF on plain or ruled paper. Use whenever the user asks to make something "handwritten", "look hand written", "in handwriting", "like notebook pages", wants a Word document, typed notes or an assignment turned into handwritten pages, or supplies a handwriting font (.ttf) and wants a document written in it — even if they do not say "PDF".
---

# Word File to Handwritten

Turns text into A4 pages that look written with a pen. The bundled script draws every letter
separately with small random changes in size, tilt, spacing and baseline, then bends the whole
page slightly, so repeated letters are never identical. This is what makes the result read as
handwriting; a handwriting font laid out by HTML/CSS or a word processor repeats each letter
exactly and looks typed, so do not use that route.

No browser is needed. Dependencies: `pillow numpy scipy fonttools img2pdf`, plus `python-docx`
for Word input and `pdfplumber` or `pypdf` for PDF input. Install any that are missing with pip (in Claude's sandbox add
`--break-system-packages`).

## Choose the route

**Plain prose (notes, letters, essays): use the command line.**

```bash
python scripts/handwrite.py input.docx -o output.pdf
```

Input can be `.docx`, `.pdf`, `.txt` or `.md`. From a Word file the script keeps headings, list items
and paragraphs, and writes each table row as one line; old `.doc` files must be saved as `.docx` first. Without `-o` the result is saved next to the input as
`<name>_handwritten.pdf`. Options:

| Option | Meaning |
|---|---|
| `--paper plain\|ruled` | blank paper, or blue rules with a red margin line |
| `--ink black\|blue\|R,G,B` | pen colour |
| `--font path.ttf` | a different handwriting font, such as one made from the user's own writing |
| `--size N` / `--pitch N` | letter size and line spacing in pixels at 200 dpi (defaults 41 / 70) |
| `--messiness F` | 0 very neat, 1 natural (default), 1.5 hurried |
| `--frame` | pencil border round each page |
| `--keep-pages` | start a new page wherever the source PDF does |

Text files may use light markup: `# ` title, `## ` underlined sub-heading, `- ` or `1)` list
items, a blank line between paragraphs, `---` for a new page, and `_{..}` / `^{..}` for
subscripts and superscripts (`x_{1}`, `e^{−0.1}`).

**Maths, tables, worked answers, or a layout that must match an original: write a short Python
script with the `Doc` class.** Text extracted from a PDF loses fractions, alignment and columns,
so for this kind of content read the source yourself and lay it out explicitly:

```python
import sys; sys.path.insert(0, "<skill dir>/scripts")
from handwrite import Doc

d = Doc(paper="plain", ink="black")          # same options as the command line
d.heading("Assignment 2")                     # centred, underlined title
d.para("Calculate the weighted sum for x_{1} = 2 and x_{2} = 3.", x=0.02, hang=0.08, label="Q1)")
d.line("= 2 × 0.4 + 3 × 0.2 + 0.5", x=0.45)   # one unwrapped line at 45% across
d.cols([(0.0, "Rank"), (0.3, "Individual"), (0.7, "Fitness")])   # table row / side-by-side maths
d.frac("P_{i} =", "25", "100", "= 0.25", x=0.1)                  # stacked fraction
d.line("Δw_{1} = 0.2", x=0.2, box=True)       # boxed result
d.gap(0.5)                                    # half a line of space
d.new_page()
d.save("output.pdf")
```

Positions (`x`, `hang`, column positions) are fractions of the text width: 0.0 is the left
margin and 1.0 the right. Pages break automatically; call `d.new_page()` to force one. On ruled
paper the script keeps every line on a rule by itself.

## Workflow

1. Get the text. For a Word file or typed PDF the command line extracts it. For a scan or a photo there is no
   text layer, so read the pages yourself and transcribe them first.
2. Keep the content word for word unless the user asks for a summary or study notes.
3. Render, then look at the result before delivering it: `d.preview("page.png")` saves one page
   as an image (or open the PDF's first page). Check that nothing runs past the right margin
   and that symbols appear. If a character is missing from the font it is dropped silently, so
   compare against the source for unusual symbols.
4. Deliver the PDF.

## Fonts and "my own handwriting"

The bundled font (Mali, with Playpen Sans supplying Greek and maths symbols; both under the SIL
Open Font License, texts in `assets/fonts/`) is a neat, round, upright print. It is a generic
hand, not the user's.

To write in the user's real handwriting they need a font built from it: they fill in a
character template on a service such as Calligraphr, download the `.ttf`, and give it to you;
pass it with `--font` or `Doc(font=...)`. A photo of a few handwritten sentences is not enough
to do this, because most letters, digits and symbols will be missing. Say so plainly instead of
implying the output matches their writing, and tell the user when a generic font was used.
