# Anchor schema

Use this schema when the page is live and you have a detections JSON export.

The resolver matches each callout to a detection, then generates a pixel spec for the renderer.

Prefer a detections export shaped like:

```json
{
  "viewport": {
    "scrollX": 0,
    "scrollY": 4642.5,
    "width": 1200,
    "height": 789
  },
  "detections": [
    {
      "id": "heading-49",
      "kind": "heading",
      "label": "h2 · Current Initiatives",
      "rect": { "x": 116, "y": 5017, "w": 960, "h": 40 }
    }
  ]
}
```

That lets the resolver map document-space element coordinates back into the visible screenshot when the page is scrolled.

## Shape

```json
{
  "callouts": [
    {
      "anchor": {
        "kind": "interactive",
        "text_contains": "Get in Touch"
      },
      "text": "Top-right CTA competes with the hero CTA below.",
      "placement": "left",
      "width": 240,
      "gap": 56,
      "label": "Competing CTA"
    }
  ]
}
```

## Anchor fields

- `kind`: optional but strongly recommended; one of the detection kinds such as `heading`, `landmark`, `interactive`, `alt-missing`, `repeat`, `focus`
- `text_contains`: case-insensitive substring match against detection text and label
- `label_contains`: case-insensitive substring match against the exported detection label
- `tag`: optional exact tag match
- `role`: optional exact role match
- `id`: optional exact detection id match when you already know it

## Callout fields

- `anchor`: detection query object
- `text`: note content
- `placement`: `left`, `right`, `top`, or `bottom`
- `width`: optional note width in pixels; default `220`
- `gap`: optional distance between note and target; default `48`
- `dx`: optional horizontal nudge after placement
- `dy`: optional vertical nudge after placement
- `label`: optional short arrow label

## Guidance

- Use `kind` plus one text-based matcher whenever possible.
- Prefer `text_contains` for headings and buttons.
- Prefer `role` and `tag` when multiple items share similar text.
- Add `dx` and `dy` only for final polish after a first render.
