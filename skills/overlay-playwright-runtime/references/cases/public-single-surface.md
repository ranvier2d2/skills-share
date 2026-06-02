# Case: Audit Current Public Page Only

Use this case when:

- the target is public
- one page or one current surface matters
- there is no sign-in barrier
- route-by-route coverage is not the main goal

Implementation mode:

- `operate`

Primary helper:

- `auditLocalWeb(...)`

Also read:

- [../interactive.md](../interactive.md)
- [../reporting.md](../reporting.md) when the user wants a durable report

## User-facing phrasing

Prefer:

- `Audit current public page only`

## Default flow

1. Bootstrap or reuse the persistent sandbox session.
2. Open the target URL on desktop.
3. Add mobile only if the page is responsive or the user asked for it.
4. Choose a real readiness signal.
5. Run `auditLocalWeb(...)`.

## Readiness

Prefer:

- `selector-visible` on a real hydrated marker
- `custom-wait` when the page settles after delayed client render

Avoid:

- treating `body` as enough for hydrated dashboards

## Defaults

- desktop plus mobile when responsive behavior matters
- `scroll-slices` when the page is taller than one viewport
- standard report bundle

## Annotation policy

Use notes or arrows when:

- the primary issue is visual and obvious
- one compact control or CTA is clearly below the common 44px guidance
- the user wants review-ready evidence
