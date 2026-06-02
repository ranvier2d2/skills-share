# Annotation schema

Use a JSON file with `notes` and `arrows`.

Coordinates are image pixels relative to the top-left corner of the source image.

## Shape

```json
{
  "notes": [
    {
      "x": 760,
      "y": 120,
      "text": "Spacing feels tight here",
      "width": 220
    }
  ],
  "arrows": [
    {
      "x1": 740,
      "y1": 156,
      "x2": 620,
      "y2": 300,
      "label": "Target"
    }
  ]
}
```

## Fields

### notes[]

- `x`: note left position
- `y`: note top position
- `text`: note content
- `width`: optional note width in pixels; default is `220`

### arrows[]

- `x1`, `y1`: arrow start point
- `x2`, `y2`: arrow end point
- `label`: optional short label drawn near the midpoint

## Example

```json
{
  "notes": [
    {
      "x": 830,
      "y": 110,
      "text": "Primary CTA is visually buried"
    },
    {
      "x": 60,
      "y": 420,
      "text": "Padding collapses at this breakpoint",
      "width": 240
    }
  ],
  "arrows": [
    {
      "x1": 820,
      "y1": 150,
      "x2": 640,
      "y2": 190
    },
    {
      "x1": 250,
      "y1": 460,
      "x2": 360,
      "y2": 510,
      "label": "Compressed content"
    }
  ]
}
```
