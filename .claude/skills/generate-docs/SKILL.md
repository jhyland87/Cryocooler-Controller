---
name: generate-docs
description: Regenerate the firmware API documentation with Doxygen (and render the mermaid diagram PDFs). Use when the user wants to build, refresh, or view the C++ API docs after changing code comments.
---

# Generate API docs

The firmware is Doxygen-documented. Config is in the root `Doxyfile`.

## Prerequisites

```bash
brew install doxygen graphviz        # macOS
```

Both are recommended. The committed `Doxyfile` has `HAVE_DOT = YES`, so Doxygen
uses Graphviz to render class/call/caller/collaboration graphs. If `dot` is not
installed, Doxygen still builds the docs and just skips the graphs with a
warning — so a Graphviz-less machine keeps working, only with plainer output.

## Build the docs

```bash
doxygen Doxyfile
```

Output is written to `docs/doxygen/html/` (gitignored). Open the result:

```bash
open docs/doxygen/html/index.html
```

## Published docs (GitHub Pages)

Merges to `main` trigger `.github/workflows/docs.yml`, which builds these docs
(with Graphviz graphs) and deploys them to GitHub Pages. You normally don't need
to run Doxygen by hand — do it only to preview changes locally before merging.
One-time repo setup: **Settings → Pages → Build and deployment → Source =
GitHub Actions.**

The landing page is the project `README.md`; `docs/*.md` appear as related
pages, and the module/class APIs come from the `/** */` comments in
`src/` + `include/`.

## What's excluded

Generated and non-firmware code is excluded from the docs and must never be
hand-documented: `include/web_content.h`, `*/generated/*`, `*.pb.*`,
`include/config/arduino_secrets.h` (secrets), `dashboard/`, `lib/`, `.pio/`.

## Diagrams (optional)

Mermaid diagrams in `docs/*.md` can be rendered to PDF:

```bash
scripts/generate-mermaid-pdfs.sh
```

## After building

- Review Doxygen warnings — `WARN_IF_UNDOCUMENTED` flags any undocumented
  public symbol. New warnings usually mean a missing `@file`, `@param`, or
  `@return`; fix per `STYLEGUIDE.md`.
- Do not commit `docs/doxygen/` (it is gitignored regenerated output).
