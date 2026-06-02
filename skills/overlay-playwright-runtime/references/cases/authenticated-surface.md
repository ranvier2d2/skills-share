# Case: Audit Authenticated App After Sign-In

Use this case when:

- the app requires authentication before the real surface is visible
- you need one authenticated surface more than a full route walk
- the user can provide credentials or manually sign in

Implementation mode:

- `operate`

Primary helpers:

- `auditAuthenticatedWeb(...)`
- `beginManualAuthSession(...)`
- `resumeAuthenticatedAudit(...)`

Also read:

- [../interactive.md](../interactive.md)
- [../reporting.md](../reporting.md) when the user wants a durable report

## User-facing phrasing

Prefer:

- `Audit authenticated app after sign-in`

## Choose the auth path

Use:

- `reuse-existing-session` when the user already signed in or can sign in once
- `form-fill` when the user provides test credentials
- `url-token` when a tokenized entry URL exists
- `custom` when the sign-in flow is bespoke

## Default flow

1. Keep the same desktop session alive.
2. Authenticate.
3. Validate the post-auth state explicitly.
4. Run the authenticated audit.
5. Add mobile only if it is important for this task.

## Validation

Prefer:

- `postAuthUrl`
- `readySelector`
- `forbiddenSelector`
- optional `postAuthCheck`

Do not rely on vague page load events as proof of authentication.

## Manual-auth posture

When the user signs in manually:

1. open the visible browser with `beginManualAuthSession(...)`
2. let the user sign in in that same window
3. continue with `resumeAuthenticatedAudit(...)`

That is the preferred pattern for SSO or human-in-the-loop login.
