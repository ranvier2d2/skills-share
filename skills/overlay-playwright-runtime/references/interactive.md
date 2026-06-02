# Persistent Sandbox Bootstrap

Read this file only after choosing an `operate` case from
[SKILL.md](../SKILL.md).

This file is intentionally cross-cutting. It covers the shared browser-session
bootstrap and runtime-path rules that multiple cases reuse.

## Why this exists

`OverlayClient` is a semantic adapter, not a browser-session manager.

For local Codex iteration, the preferred model is:

1. bootstrap a dedicated sandbox under `~/.codex/overlay-playwright-runtime/sandbox`
2. keep a real Playwright browser session alive in `js_repl`
3. inject the overlay runtime into those persistent pages
4. use the runtime for reports, evidence, and annotations
5. use Playwright for navigation and interaction

## Bootstrap the sandbox once

```bash
python3 scripts/bootstrap_operate_sandbox.py
```

Default sandbox root:

```text
~/.codex/overlay-playwright-runtime/sandbox
```

## Bootstrap once inside `js_repl`

```javascript
var overlaySandboxFactory;
var overlaySession;

({ createOverlaySandboxSession: overlaySandboxFactory } = await import(`file://${process.env.HOME}/.codex/overlay-playwright-runtime/sandbox/launch-session.mjs`));

overlaySession ??= await overlaySandboxFactory({
  outputDir: `${process.env.HOME}/.codex/overlay-playwright-runtime/sandbox/output`
});
```

## Runtime path choices

Use these rules consistently:

- local development inside this repo:
  - `runtimeScriptPath = "/absolute/path/to/repo/a11y-overlay.js"`
- adopted repo that owns the vendored runtime:
  - `runtimeScriptPath = "/absolute/path/to/target-repo/a11y-overlay.js"`
- skill-owned bundled runtime:
  - use only when you explicitly want to test the installed skill bundle itself

Prefer the repo runtime during development so you are testing the code you are
actively editing.

## Minimal session variables

```javascript
var TARGET_URL = "http://127.0.0.1:3000";
var RUNTIME_SCRIPT = "/absolute/path/to/repo/a11y-overlay.js";
```

## Shared session rules

- Reuse the same browser when the task is still on the same app.
- Reuse the same desktop page for manual-auth flows.
- Create the mobile page only when the chosen case needs it.
- In agent-driven desktop sessions, the overlay now defaults to a collapsed
  bottom launcher instead of pinning the full toolbar at the top.

## Cross-reference

After bootstrapping, return to the selected case file:

- [cases/public-single-surface.md](cases/public-single-surface.md)
- [cases/public-responsive-routes.md](cases/public-responsive-routes.md)
- [cases/authenticated-surface.md](cases/authenticated-surface.md)
- [cases/authenticated-navbar-routes.md](cases/authenticated-navbar-routes.md)
- [cases/desktop-shell.md](cases/desktop-shell.md)
- [cases/visual-evidence-only.md](cases/visual-evidence-only.md)
