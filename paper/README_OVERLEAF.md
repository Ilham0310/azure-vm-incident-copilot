# Overleaf Upload Instructions

## 1. Download IEEEtran.cls

Download from IEEE Author Tools:
https://www.ieee.org/publications/authors/author-tools-resources.html
-> LaTeX template -> IEEEtran.cls

Place `IEEEtran.cls` in this folder (same directory as `main.tex`).

## 2. Fill in author details

In `main.tex`, replace every occurrence of:
- `[Author N Name]` with the real author name
- `[Department]` with the real department
- `[Institution]` with the real institution
- `[City, Country]` with the real location
- `[email@domain.com]` with the real email

Also fill in the `\IEEEbiography` blocks at the end of `main.tex`
with real biography text (3-5 sentences per author).

## 3. Replace placeholder photos

Replace `photo1.jpg` and `photo2.jpg` with real author headshots.
Required size: 1 inch wide x 1.25 inches tall (96x120 px at 96 DPI,
or 288x360 px at 288 DPI for print quality).

## 4. Add GitHub repository URL

In `main.tex`, in the Data and Code Availability section, replace
"the project repository" with the actual GitHub URL, e.g.:
  https://github.com/[username]/[repo-name]

## 5. Upload to Overleaf

1. Go to https://www.overleaf.com
2. New Project -> Upload Project
3. Zip this entire `overleaf_package/` folder and upload the zip
4. Set `main.tex` as the main document
5. Compile with pdfLaTeX (not XeLaTeX or LuaLaTeX)
6. If any package is missing, Overleaf will prompt to install it

## 6. Final checks before submission

- [ ] Abstract word count <= 250 words (check in compiled PDF)
- [ ] All `[Author N Name]` placeholders replaced
- [ ] All figures render correctly (not broken image icons)
- [ ] Both TikZ diagrams (fig4, fig5) compile without errors
- [ ] Reference list appears correctly formatted (9 entries)
- [ ] IEEEtran.cls is present in the project folder
- [ ] Author biographies are filled in with real text
- [ ] AI disclosure in Acknowledgments section is present

## 7. Package contents

| File | Description |
|------|-------------|
| main.tex | Main paper (IEEE Access two-column format) |
| references.bib | BibTeX references (9 entries, all verified) |
| fig4_architecture.tex | TikZ: 6-layer pipeline diagram |
| fig5_rag_pipeline.tex | TikZ: RAG dual-collection pipeline |
| fig1_accuracy_comparison.png | Experiment 1 bar chart (300 DPI) |
| fig2_learning_curve.png | Experiment 2 learning curve (300 DPI) |
| fig3_safety_guard.png | Experiment 3 safety guard chart (300 DPI) |
| photo1.jpg | Author 1 photo placeholder (replace with real) |
| photo2.jpg | Author 2 photo placeholder (replace with real) |
| IEEEtran.cls | IEEE template class (USER MUST ADD) |

## 8. Known issues / notes

- The `\xrightarrow` command in fig5_rag_pipeline.tex requires
  `amsmath` (already included in main.tex preamble).
- The `drop shadow` style in fig4_architecture.tex requires the
  `shadows` TikZ library (already loaded in main.tex preamble).
- If compiling locally (not Overleaf), run:
    pdflatex main.tex
    bibtex main
    pdflatex main.tex
    pdflatex main.tex
