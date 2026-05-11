# Overleaf Package — IEEE Access Submission

## Paper Title
LLM-Augmented Azure VM Incident Triage with RAG Memory and Deterministic Safety Enforcement

## Files in this package

| File | Description |
|---|---|
| `main.tex` | Complete LaTeX source (IEEE Access format) |
| `references.bib` | BibTeX bibliography (19 entries) |
| `fig1_accuracy_comparison.png` | Safety-guard ablation bar chart |
| `fig2_learning_curve.png` | Feedback-driven memory improvement |
| `fig3_safety_guard.png` | Safety guard prevention rate per rule |
| `fig4_architecture.png` | 6-layer architecture diagram |
| `fig4_architecture.tex` | TikZ source for architecture diagram |
| `fig5_rag_pipeline.png` | RAG memory pipeline diagram |
| `fig5_rag_pipeline.tex` | TikZ source for RAG pipeline |
| `photo1.jpg` | Author 1 photo (TODO: replace) |
| `photo2.jpg` | Author 2 photo (TODO: replace) |
| `cover_letter.md` | Cover letter draft |

## How to use in Overleaf

1. Create a new Overleaf project
2. Upload all files from this directory
3. Set `main.tex` as the main document
4. Compile with pdfLaTeX
5. Replace TODO placeholders with actual author details before submission

## TODO before submission

- [ ] Replace `[TODO: Author 1 Name]` etc. with real names
- [ ] Replace `[TODO: Department]`, `[TODO: Institution]` etc.
- [ ] Replace `[TODO: email@domain.com]` with real emails
- [ ] Replace `photo1.jpg` and `photo2.jpg` with actual author photos
- [ ] Replace GitHub URL placeholder with actual repository URL
- [ ] Verify IEEE Access template compliance
- [ ] Run final grammar/spell check

## Key Results (from evaluation)

| Config | Overall | Known | Novel | McNemar vs A |
|---|---|---|---|---|
| A (Rule Engine + Safety) | 88/100 (88.0%) | 87/95 (91.6%) | 1/5 (20.0%) | — |
| A-noSafety (ablation) | 82/100 (82.0%) | 81/95 (85.3%) | 1/5 (20.0%) | +6pp |
| B (LLM Only) | 73/100 (73.0%) | 70/95 (73.7%) | 3/5 (60.0%) | p=0.0026 |
| C (LLM + SOP RAG) | 86/100 (86.0%) | 85/95 (89.5%) | 1/5 (20.0%) | p=0.79 |
| D (Full System) | 84/95 (88.4%) | 83/90 (92.2%) | 1/5 (20.0%) | p=1.0 |

## Version
Last updated: 2026-05-05
