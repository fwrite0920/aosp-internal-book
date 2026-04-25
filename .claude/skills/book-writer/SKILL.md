---
name: book-writer
description: Patterns for writing technical book chapters in Markdown with Mermaid diagrams, served via MkDocs. Use this skill whenever writing, editing, reviewing, adding, removing, or renaming book chapters, organizing multi-chapter content, fixing Mermaid rendering issues, or changing the book's structure. Also triggers when updating mkdocs.yml, docs/ symlinks, or navigation — even if the user just says "add a chapter" or "reorganize sections" without mentioning MkDocs.
---

# Book Writer

Write source-code-referenced technical books in Markdown with Mermaid diagrams, served as a MkDocs website. Covers chapter structure, content flow, diagram syntax, and keeping the MkDocs site in sync with content changes.

## MkDocs Site Maintenance

The book is served via MkDocs Material. When chapter content changes, the site configuration must stay in sync. Forgetting this breaks navigation or hides new chapters from readers.

### When you add a new chapter

1. Create `NN-slug.md` with the chapter template below
2. Add a nav entry to `mkdocs.yml` in the correct Part section:
   ```yaml
   - "N. Chapter Title": NN-slug.md
   ```
3. Create a symlink in `docs/`:
   ```bash
   ln -sf "../NN-slug.md" "docs/NN-slug.md"
   ```
4. If the chapter number changes existing chapters, renumber the affected `mkdocs.yml` entries too

### When you remove a chapter

1. Delete the `.md` file
2. Remove its entry from `mkdocs.yml` nav
3. Remove the symlink from `docs/`
4. Renumber subsequent chapters if needed (in filenames, `mkdocs.yml`, and section headings inside the files)

### When you rename or reorder chapters

1. Rename the `.md` file
2. Update the `mkdocs.yml` nav entry (both the label and the filename)
3. Update the `docs/` symlink
4. Update all `## N.x` section headings inside the file to match the new chapter number

### mkdocs.yml nav structure

The nav groups chapters into Parts. Each Part is a collapsible section in the sidebar:

```yaml
nav:
  - Introduction: index.md
  - "Part I: Getting Started":
    - "Frontmatter": 00-frontmatter.md
    - "1. Introduction": 01-introduction.md
  - "Part II: Kernel & Boot":
    - "4. Boot and Init": 04-boot-and-init.md
```

The label format is `"N. Short Title": NN-slug.md`. Keep labels short — they appear in the sidebar.

### docs/ symlinks

MkDocs reads from `docs/` which contains symlinks to the actual chapter files in the repo root. This indirection exists because MkDocs requires `docs_dir` to be a child directory, but chapters live at the repo root for simplicity.

When creating symlinks, always use relative paths (`../filename.md`) so they work regardless of absolute path. Also symlink any static assets the chapters reference.

## Chapter Structure

Use this template for every chapter:

```markdown
# Chapter N: Title

> *Optional opening quote*

Introduction paragraph (no heading).

---

## N.1 First Major Section
### N.1.1 Subsection

## N.X Try It
Hands-on exercises with real commands.

## Summary
Key takeaways as bullets.

### Key Source Files
| File | Purpose |
```

**Example:**
```markdown
# Chapter 9: Binder IPC

> *"Binder is the heart of Android's inter-process communication."*

Android's IPC mechanism enables type-safe, identity-aware communication...

---

## 9.1 Why Binder?
### 9.1.1 One-Copy Semantics

## 9.7 Try It
- Run `adb shell service list` to see all registered Binder services

## Summary
- Binder provides one-copy IPC with caller identity
```

## Content Guidelines

**Reference real source code.** Every architectural claim should point to a specific file and line — this is what makes the book valuable beyond a generic overview.

```java
// Source: frameworks/base/services/core/.../PowerManagerService.java:202
private static final int DIRTY_WAKE_LOCKS = 1 << 0;
```

**Match code block language to source file extension.** AOSP has Go code (`.go` files in `build/soong/`) alongside Java. Use ` ```go ` for Go code, ` ```java ` for Java — never mark Go as Java. Key tells: Go uses `:=`, `func (c *config)`, `[]string{}`, no semicolons. Java uses `;` line endings, `public class`, `@Override`.

```go
// Source: build/soong/android/config.go:2402
func (c *config) UseHostMusl() bool {
    return Bool(c.productVariables.HostMusl)
}
```

**Use manual section numbers** matching the chapter (`## 5.1` for chapter 5). MkDocs doesn't auto-number, and if you ever generate PDF, Pandoc's auto-numbering doubles manual numbers.

**Title format:** `# Chapter N: Title` with colon separator consistently across all chapters.

**End every chapter** with "Try It" (hands-on exercises) and "Summary" (key takeaways).

## Content Organization

Bottom-to-top for system books — each layer builds on the one below:

Build system → Kernel/boot → Native foundation → HAL → Native services → Runtime → Framework core → Framework features → Connectivity → Security → UI → Apps → Infrastructure → Device support → Practical guide

## Mermaid Diagrams

Place a descriptive heading before every mermaid block — it helps readers navigate and becomes the figure caption if you ever generate PDF.

For syntax rules (quoting, special characters, parse errors), read `references/mermaid-syntax.md`. The short version: quote any node label containing `()`, `<br/>`, or `|`.

## Parallel Writing

For 20+ chapters, launch 5 agents per batch. Review after each batch — then update `mkdocs.yml` nav and `docs/` symlinks for all new chapters before starting the next batch.

## Lists

Markdown lists silently break when you forget the blank line before them — they render as inline text instead of a proper list. This is the single most common formatting issue in the book (we fixed 1,268 instances).

**Always leave a blank line before any numbered or bullet list:**

```markdown
BAD — renders on one line:
Services are started in four phases:
1. Bootstrap services
2. Core services

GOOD — renders as proper list:
Services are started in four phases:

1. Bootstrap services
2. Core services
```

**Match counts to list items.** If you write "three phases:" make sure exactly three items follow. Readers notice when the prose says "three" but the list has four items — it undermines trust in the technical accuracy of the entire chapter.

## Quick Reference

| Do | Don't | Why |
|----|-------|-----|
| Blank line before every list | List right after text | Renders inline instead of as a list |
| "four phases:" with 4 items | "three phases:" with 4 items | Count mismatch erodes reader trust |
| Update `mkdocs.yml` when adding/removing chapters | Add a chapter file without a nav entry | Readers won't find it in the sidebar |
| Create `docs/` symlink for every new chapter | Forget the symlink | MkDocs can't serve files outside `docs/` |
| `## 5.1 Title` in chapter 5 | `## 3.1 Title` (wrong chapter) | Readers use the number to locate content |
| `# Chapter 5: Title` | `# Chapter 5 -- Title` | Pick one separator, stick with it |
| Heading before each mermaid block | Two mermaid blocks in a row | Each diagram needs its own context |
| ` ```go ` for `.go` files | ` ```java ` for Go code | Wrong syntax highlighting, misleads readers |
| `NODE["text(stuff)"]` | `NODE[text(stuff)]` | Unquoted parens break Mermaid parser |
| Source path + line number | "The framework does X" | Unverifiable claims undermine the book |
