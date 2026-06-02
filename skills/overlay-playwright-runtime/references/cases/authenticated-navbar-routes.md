# Case: Audit Authenticated Navbar Routes In The Same Live Session

Use this case when:

- the app is already authenticated or can be authenticated once
- the app is a SPA with a stable top navbar
- hard reloads create auth churn or instability
- you want a route-by-route desktop audit in the same browser session

Implementation mode:

- `operate`

Primary helpers:

- `beginManualAuthSession(...)`
- `resumeAuthenticatedAudit(...)`
- `auditDesktopTopNavRoutes(...)`

Also read:

- [../interactive.md](../interactive.md)
- [../reporting.md](../reporting.md) when the user wants a durable report

## User-facing phrasing

Prefer:

- `Audit authenticated navbar routes in the same live session`

## Default flow

1. Keep the desktop browser session alive.
2. Authenticate once.
3. Stay on the same live page.
4. Run `auditDesktopTopNavRoutes(...)`.
5. Avoid hard `goto(...)` loops when the SPA can navigate in-app.

## Route-walk guidance

Prefer:

- a narrow navbar scope via `navScopeSelectors`
- in-app DOM clicks
- per-route settle time when the app animates or hydrates
- higher screenshot timeouts for heavy routes

Use this case only when the route family is really exposed by a stable app navbar.
If desktop and mobile use different route controls, route back to
[public-responsive-routes.md](public-responsive-routes.md) or a future
authenticated responsive variant.
