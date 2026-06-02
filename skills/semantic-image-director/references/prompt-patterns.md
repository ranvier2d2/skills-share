# Prompt Patterns

## Imagegen Brief With Semantic Lock

```text
Use case: <poster/mockup/infographic/concept image>
Primary artifact: <what the image should be>
Domain meaning: <business/technical/medical/philosophical meaning>
Must show: <visible elements>
Must preserve: <exact text, structure, brand, visual hierarchy>
Ambiguous terms:
- "<term>" means <meaning>. Show as <visual treatment>. Do not depict <literal trap>.
Negative semantics: Do not literalize technical or metaphorical terms as stock objects.
Style: <visual style>
Text: <exact short text, if any>
Composition: <layout/framing>
```

## ChatGPT Images / Image Gen 2 Stress Brief

Use this when the user wants `imagegen` pushed hard as a final communicational image.

```text
Create a <aspect ratio / format> visual artifact for <audience and use>.

Core idea:
<one-sentence semantic thesis>

Visual structure:
- <number> main sections/panels/objects.
- Clear hierarchy: <primary focal point>, <secondary supporting elements>.
- Use short, legible labels. Keep text exact where quoted.

Required text:
- "<short exact label 1>"
- "<short exact label 2>"
- "<short exact label 3>"

Semantic locks:
- "<term>" means <domain meaning>; show it as <visual treatment>; do not show <literal trap>.
- "<term>" means <domain meaning>; show it as <visual treatment>; do not show <literal trap>.

Composition:
<editorial poster / clean technical infographic / cinematic explainer / diagrammatic visual metaphor>

Style:
<typography, palette, density, lighting, realism/illustration, mood>

Negative semantics:
Do not use stock icons, literal metaphors, fake UI gibberish, invented labels, or decorative elements that change the meaning.
```

## Imagegen Compact Infographic Brief

```text
Create a compact infographic image, not an editable document.
Audience: <who needs to understand it quickly>.
Message: <the one thing the viewer should understand>.
Layout: <2-column / 3-step / before-after / layered flow / hub-and-spoke>.
Text budget: maximum <N> labels, each under <N> words.
Exact labels: "<label 1>", "<label 2>", "<label 3>".
Semantic guardrails: <locks and forbidden literalizations>.
Style: polished, legible, modern editorial, high contrast, no clutter.
```

## Deterministic Renderer Brief

```text
Artifact type: <page/slide/diagram/UI>
Renderer: HTML/CSS/SVG/Figma/intent-html-renderer
Exact text:
Layout:
Data/labels:
Visual layer:
Semantic locks:
Validation:
- text exact
- no semantic literalization
- mobile/desktop or export requirements
```

## Repair Prompt After Literalization

```text
The previous image failed semantically: it interpreted "<term>" as <wrong literal meaning>.
Regenerate with this lock:
"<term>" means <intended meaning>. Do not show <wrong literal family>.
Focus on <intended domain objects/relationships>.
Keep all other requirements the same.
```

## Example: Cloud

```text
Ambiguous term: "cloud"
Meaning: cloud computing infrastructure and operational platform.
Visual treatment: abstract server/network topology, deployment layers, or product UI infrastructure.
Forbidden interpretation: weather clouds, sky, rain, cloud taxonomy, fluffy cloud icons.
```

## Example: Agent Skill

```text
Ambiguous term: "skill"
Meaning: reusable agent practice that shapes action.
Visual treatment: modular instruction object, workflow kernel, or practice card.
Forbidden interpretation: school diploma, sports skill, martial arts, magic ability.
```
