# Case: Audit Attached Desktop-Shell Surface

Use this case when:

- you already have a live desktop-shell or embedded-browser page handle
- the surface is not primarily a normal public URL flow
- you want to audit the attached shell surface without adopting the runtime into
  another repo first

Implementation mode:

- `operate`

Primary helper:

- `auditDesktopShell(...)`

Also read:

- [../interactive.md](../interactive.md)
- [../reporting.md](../reporting.md) when the user wants a durable report

## User-facing phrasing

Prefer:

- `Audit attached desktop-shell surface`

## Default flow

1. Reuse the existing desktop page handle.
2. Inject the overlay.
3. Run the shell audit.
4. Add mobile only if there is a second attached page that really represents a
   mobile or narrow-shell surface.

## Keep this case narrow

Use it for:

- attached native shells
- embedded browser surfaces
- already-launched desktop app pages

Do not overload this case with authenticated route walking or public route-set
logic.
