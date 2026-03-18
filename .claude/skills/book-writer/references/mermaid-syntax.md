# Mermaid Syntax Reference

Mermaid's parser is stricter than most Markdown authors expect. These rules prevent silent rendering failures — diagrams that just show up blank with no error message.

## Quoting Rules

Any node label containing special characters must be wrapped in double quotes. Mermaid interprets unquoted `()` as round-node syntax, `|` as edge-label delimiters, and `<br/>` as raw HTML in non-HTML contexts.

### Diamond nodes
```
Bad:  {text with parens()}
Good: {"text with parens()"}

Bad:  {text<br/>more text}
Good: {"text<br/>more text"}
```

### Square bracket nodes
```
Bad:  NODE[text(stuff)]
Good: NODE["text(stuff)"]

Bad:  NODE[text<br/>more]
Good: NODE["text<br/>more"]
```

### Edge labels
```
Bad:  -->|func()|
Good: -->|"func()"|
```

## Diagram-Specific Rules

### sequenceDiagram
`<br/>` in `participant` declarations breaks rendering entirely. Use spaces instead:

```
Bad:  participant App as Application<br/>(App Process)
Good: participant App as Application (App Process)
```

`<br/>` in message labels and `Note` blocks is fine.

### stateDiagram-v2
Parentheses in transition labels cause parse errors. Rewrite without them:

```
Bad:  State1 --> State2 : CanvasContext::create()
Good: State1 --> State2 : CanvasContext create
```

### flowchart / graph
`<br/>` in node labels is valid when the label is quoted:
```
Good: A["First line<br/>Second line"]
```

Subgraph names with spaces need explicit IDs:
```
Bad:  subgraph Home Screen
Good: subgraph HS["Home Screen"]
```

## Common Parse Errors

| Error message | Cause | Fix |
|--------------|-------|-----|
| `Expecting 'SQE', 'PE'...` | Unquoted `()` in node label | Quote the label |
| `Parse error on line N` near `<br/>` | `<br/>` in participant or unquoted label | Quote or remove |
| `No diagram type detected` | Empty or malformed mermaid block | Check for unclosed fences |
| Diagram renders blank (no error) | Syntax valid but semantically wrong | Check node/edge references match |
