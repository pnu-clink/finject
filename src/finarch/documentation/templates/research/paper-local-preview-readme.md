# FInject · Local LaTeX Preview

This README is generated from a document template, which is a local copy of the current project for review and not reflected in the Overleaf.

## Reading order

1. [main.pdf](main.pdf): Preview of the English subtitles compiled from local.
2. [main.tex](main.tex): Entry files and Abstract.
3. [sections/01-introduction.tex](sections/01-introduction.tex)Introduction and Figure 1.
4. [revision-20261002-body.tex](revision-20261002-body.tex): Related Works to Appendices.
5. [current figure: step](../instructdion/MANUSCRIPT-STATE.json): human annotation pre quantity and approval order.
6. [Automation records](../../reports/run/20261003-paper-local-sync/README.md)Back up, check log.

## The order of work.

First, we review changes in Hungarian and English from the existing FInject Revision Draft, and then we send them to Overleaf only after the user decides to reflect.

The current review data is `reports/run/20261003-paper-revision-draft/paper-review.json`And then we'll see how we can do that. `paper/local-preview-content/counts-en.md`and `counts-ko.md`It preserves the original of the previous distribution run, and in this project, it doesn't run the existing date-by-date source generator again.

It's a project root that adapts the Han-ing review copy and the local PDF:

```sh
python3 src/finarch/documentation/sync_paper_revision.py --build
```

When you re-create the LaTeX text and then re-created the PDF, you run it in this folder:

```sh
latexmk -pdf -interaction=nonstopmode -halt-on-error main.tex
```

Now I'm using latexmk and pdflatex on my PC. It's a project with multiple source, graphic, and ACL-style files, so I compile it with a local LaTeX tool. PDFs can be opened in the Codex. If you're editing LaTeX directly, you'll have to update the corresponding text of the Revision Draft together, and you'll only change one and report that the sync is complete.

The manuscript still has the existing default entry and the Appendix # tag. This PDF is not a completed copy.
