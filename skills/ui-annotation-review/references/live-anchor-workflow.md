# Live anchor workflow

Use this workflow when Codex can inspect the page in a real browser.

## 1. Capture the screenshot

Capture the exact viewport you want to annotate.

## 2. Inject detector output if needed

If the page does not already expose structured detections, inject one first.

For `a11y-overlay`, use a browser evaluate step equivalent to:

```js
await page.addScriptTag({ path: "/absolute/path/to/a11y-overlay.js" });
```

## 3. Export detections

Use a browser evaluate step like:

```js
const detections = await page.evaluate(() => {
  return {
    viewport: {
      scrollX: window.scrollX,
      scrollY: window.scrollY,
      width: window.innerWidth,
      height: window.innerHeight
    },
    detections: window.__a11yOverlayInstalled.collectDetections()
  };
});
```

Write that object to `detections.json`.

The resolver accepts either:
- a plain detections array
- or a viewport-aware object with `viewport` plus `detections`

Use the viewport-aware form whenever the screenshot is taken from a scrolled page position.

## 4. Write the anchor spec

Author `anchor-spec.json` using [anchor-schema.md](anchor-schema.md).

## 5. Resolve and render

```bash
python3 scripts/resolve_anchor_spec.py screenshot.png detections.json anchor-spec.json pixel-spec.json
python3 scripts/annotate_png.py screenshot.png pixel-spec.json annotated.png
```

## 6. Review the artifact

If the callouts land poorly:
- tighten the anchor query
- change placement
- add `dx` / `dy`
- split the review into multiple screenshots
