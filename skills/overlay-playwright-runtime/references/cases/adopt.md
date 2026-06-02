# Case: Adopt Runtime Into Another Repo

Use this case when:

- the target repo does not already contain `a11y-overlay.js`
- the target repo does not already contain `playwright/overlay-client.mjs`
- the user wants the runtime committed into another repo
- the user wants repo-local or CI usage rather than a persistent Codex session

Implementation mode:

- `adopt`

Next read:

- [../adoption.md](../adoption.md)

## User-facing phrasing

Prefer:

- `Adopt runtime into another repo`

Do not open with:

- `Run adopt`
- `Run vendor_overlay_runtime.py`

## Default flow

1. Check whether the repo already has the runtime files.
2. Dry run the vendor script if the repo is unfamiliar.
3. Vendor the runtime.
4. Use `--temporary` only for audit-only integration.
5. Use `--cleanup` only after a prior temporary run.

## Notes

- Keep vendoring deterministic from the bundled local assets.
- Do not mutate `package.json` or lockfiles unless the user explicitly asks.
- If the user really wants live iterative QA instead of repo ownership, route
  them back to an `operate` case.
