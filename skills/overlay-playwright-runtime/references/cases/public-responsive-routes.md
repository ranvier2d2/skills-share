# Case: Audit All Public Routes Across Desktop And Mobile

Use this case when:

- the target is public
- desktop and mobile expose different route controls
- the route changes are client-side rather than URL-based
- you want one artifact bundle per route

Implementation mode:

- `operate`

Primary helper:

- `auditResponsiveRouteSet(...)`

Also read:

- [../interactive.md](../interactive.md)
- [../reporting.md](../reporting.md) when the user wants a durable report

## User-facing phrasing

Prefer:

- `Audit all public routes across desktop and mobile`

## Default mapping

For the first version, the helper is best when:

- desktop uses `tabs`
- mobile uses `combobox-options`

That matches the Ranvier public dashboard shape.

## Default flow

1. Bootstrap or reuse the persistent sandbox session.
2. Choose one canonical public URL.
3. Detect or provide the desktop route control.
4. Detect or provide the mobile route control.
5. Choose separate readiness for desktop and mobile.
6. Run `auditResponsiveRouteSet(...)`.
7. Review the route summary and backlog output after the route bundles are written.

## Navigator guidance

Desktop:

- use `kind: "tabs"` when routes are real tab buttons
- use `scopeSelectors` to keep route discovery narrow

Mobile:

- use `kind: "combobox-options"` when a responsive picker drives the same routes

## Readiness

Prefer separate readiness per surface:

- `desktopReadiness` for the desktop route control
- `mobileReadiness` for the mobile route control
- `routeReadiness` only when each route needs an additional wait after selection

## Annotation policy

Default notes/arrows should call out:

- the active route control when it is visibly compact
- the first compact visible control on the route

Use a custom `annotateRoute` only when the route family has a known issue pattern
that is stronger than the defaults.

## Expected outputs

- one route folder per route
- `report.md` and `report.html` per route
- desktop and mobile HTML bundles per route
- route summary
- route backlog or follow-up summary when the user wants prioritization
