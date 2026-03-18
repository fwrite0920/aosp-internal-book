# AOSP Internals Book

64 chapters + 2 appendices, ~227,000 lines, ~1,500 Mermaid diagrams.

## Quick Start

```bash
docker compose build
docker compose up -d serve         # http://localhost:8000
```

## Writing Rules

1. Chapters: `NN-slug.md`, titles: `# Chapter N: Title` (colon)
2. Section numbers: manual `## N.1`, `### N.1.2` matching filename
3. No duplicate section numbers within a chapter
4. Mermaid: quote labels with `()`, `<br/>`, `|`; no `<br/>` in `participant` lines
5. Descriptive heading before each mermaid block
6. Source refs: real AOSP paths with line numbers
7. End each chapter with "Try It" + "Summary"

## CI

GitHub Actions runs `mkdocs build` on push/PR (~2 min).

## Skills

- `.claude/skills/book-writer/SKILL.md` — chapter structure, content guidelines, Mermaid syntax
  - `references/mermaid-syntax.md` — detailed quoting rules and common parse errors
