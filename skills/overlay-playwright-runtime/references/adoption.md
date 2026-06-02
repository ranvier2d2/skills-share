# Vendoring Details

Read this file only when the selected case is
[cases/adopt.md](cases/adopt.md).

This file is intentionally implementation-focused. It covers the vendoring
behavior after the case has already been classified as `adopt`.

## Canonical repo files

The reusable files are:

- `a11y-overlay.js`
- `playwright/overlay-client.mjs`

In this skill, those files are bundled locally under `assets/runtime/` so
vendoring does not need to fetch from GitHub during each run.

## Detect whether a repo already has the runtime

From the target repo root:

```bash
rg --files | rg '(^a11y-overlay\\.js$|^playwright/overlay-client\\.mjs$)'
```

If both files exist:

- prefer the in-repo versions
- do not vendor fresh copies unless the user explicitly asks to overwrite

## Vendor the runtime

Dry run first when the target repo is unfamiliar:

```bash
python3 scripts/vendor_overlay_runtime.py \
  --target-root /absolute/path/to/repo \
  --dry-run
```

Actual vendoring:

```bash
python3 scripts/vendor_overlay_runtime.py \
  --target-root /absolute/path/to/repo
```

Use `--force` only when the user explicitly wants to overwrite divergent files.

## Compatibility-aware behavior

Identical existing files are treated as compatible:

- identical `a11y-overlay.js` is reused
- identical `playwright/overlay-client.mjs` is reused
- only divergent files require `--force`

## Temporary audit-only mode

For an audit run that should not leave vendored files behind:

```bash
python3 scripts/vendor_overlay_runtime.py \
  --target-root /absolute/path/to/repo \
  --temporary
```

After the audit:

```bash
python3 scripts/vendor_overlay_runtime.py \
  --target-root /absolute/path/to/repo \
  --cleanup
```

Cleanup is conservative:

- files copied by the temporary run are removed
- files changed after vendoring are preserved
- the manifest is removed only when cleanup completes fully

## Keep the boundary clear

Use vendoring when:

- another repo should own the runtime files
- CI or repo-local Playwright code should call the overlay directly
- the browser session does not need to stay alive between Codex turns

Do not use this file as the main guide for persistent local iteration in Codex.
For that, read [interactive.md](interactive.md) and the chosen `operate` case.
