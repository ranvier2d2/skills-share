# Semantic Lock

## Purpose

A semantic lock prevents the renderer from treating a word as an object merely because the word is visually common.

## Term Classifications

| Class | Meaning | Example |
|---|---|---|
| Literal | The object itself should appear | "clouds over a mountain" |
| Technical | The term names a system concept | "cloud infrastructure" |
| Metaphorical | The term guides structure or mood | "message in a bottle" for cross-domain analogy |
| Text-only | The word may appear as text but not as an object | "agent skill" |
| Forbidden visual | The word must not be depicted | "cloud" in a SaaS architecture page |

## Ambiguity Pass

Before visual generation, scan the request for:

- technical nouns with everyday meanings;
- metaphors from the conversation;
- domain terms from medicine, programming, product, law, finance, or design;
- words that have iconic stock imagery;
- exact copy that should not be paraphrased.

For each risky term, write:

```text
<term>: means <intended meaning>; show as <visual treatment>; do not show <forbidden literalizations>.
```

## High-Risk Terms

Always inspect these terms before image generation:

`cloud`, `agent`, `model`, `state`, `pipeline`, `memory`, `container`, `runtime`, `token`, `branch`, `tree`, `architecture`, `stack`, `framework`, `skill`, `object`, `function`, `tool`, `pattern`, `flow`, `episode`, `journey`, `lightcone`, `flush`.

Example:

```text
The word "cloud" means cloud computing infrastructure. Do not depict weather clouds, skies, rain, cloud taxonomy, fluffy cloud icons, or meteorological diagrams.
```

## Negative Semantics

Negative prompts should be semantic, not just object lists.

Weak:

```text
No clouds.
```

Stronger:

```text
Do not interpret "cloud" as weather, sky, fluffy icons, meteorology, rain, or cloud taxonomy. It means distributed computing infrastructure and may appear only as abstract server/network structure or text.
```

## When To Ask

Ask the user only when ambiguity changes the artifact category.

Do not ask if context strongly implies the meaning. Lock the meaning and proceed.
