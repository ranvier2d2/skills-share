# Shadcn Intent Rendering

Use this when a repo contains `components.json`, `components/ui`, or an installed Shadcn skill. The job is not just to import Shadcn components; it is to infer the best Shadcn-backed product surface from the user's intent.

## Context First

1. Read local instructions and route examples.
2. Run the Shadcn CLI with the project's package runner:

```bash
pnpm dlx shadcn@latest info --json
pnpm dlx shadcn@latest preset resolve --json
```

Use `npx shadcn@latest` or `bunx --bun shadcn@latest` instead when the project package manager requires it.

3. If the CLI fails because of DNS, registry access, package download, or sandbox restrictions, run:

```bash
python3 $SKILL_ROOT/scripts/extract_shadcn_context.py --cwd <workspace> --json
```

Then fall back to local evidence instead of blocking:
   - Read root and app-level `components.json`.
   - List `components/ui/*.tsx` to infer installed components.
   - Read `package.json` for `packageManager`, framework, icon packages, and Shadcn dependencies.
   - Read `tsconfig.json` for import aliases when present.
   - Read nearby routes for actual import paths and component style.
   - Record that Shadcn CLI context was unavailable and continue with the local evidence.
4. Use the returned or locally inferred context instead of guessing:
   - `aliases` and `resolvedPaths` for imports.
   - `base` for Radix vs Base UI API differences.
   - `iconLibrary` for icon imports.
   - `tailwindVersion` and `tailwindCssFile` for theme work.
   - `components` for the installed primitive surface.
   - `preset` and `style` for visual baseline.
5. If `.agents/skills/shadcn/SKILL.md` exists, use it as a companion reference. Load only the rule file needed for the current task: `rules/styling.md`, `rules/composition.md`, `rules/forms.md`, `rules/icons.md`, or `rules/base-vs-radix.md`.
6. Before using a complex or unfamiliar primitive, run:

```bash
pnpm dlx shadcn@latest docs <component>
```

Fetch the docs/examples URLs when the component API or composition is not obvious.

If docs fetching is unavailable, inspect the local component source and existing route examples.

## Intent To Component Strategy

Choose components from the user's job, not from what is easiest to hand-code.

| Intent | Prefer |
| --- | --- |
| Executive decision or prioritization | `Card`, `Badge`, `Table`, `Tabs`, `Progress`, `Alert`, `Separator` |
| Dense operations dashboard | `Sidebar`, `Card`, `Table`, `Chart`, `Tabs`, `ScrollArea`, `Tooltip` |
| Form, intake, settings, configuration | `FieldGroup`, `Field`, `FieldSet`, `InputGroup`, `Select`, `Switch`, `Checkbox`, `ToggleGroup` |
| Search, command, filtering, action-command UI | `Command`, `InputGroup`, `Dialog`, `Sheet`, `ButtonGroup`, `Badge`, `Table` |
| Empty, loading, error, not-ready states | `Empty`, `Skeleton`, `Spinner`, `Alert`, `Progress`, `sonner` |
| Comparison or launch-readiness review | `Tabs`, `Table`, `Item`, `Badge`, `Progress`, `Sheet` |

Use existing installed components first. If a needed component is not installed, use `shadcn search` or `shadcn add --dry-run` to inspect options. Do not install or overwrite components unless the user asked for implementation and the component is clearly needed.

## Styling From Intent

Infer a style direction, then express it using installed components, semantic tokens, layout density, and content hierarchy. The default is a considered interface, not an unstyled Shadcn demo. Only produce a stark black-and-white or bare-neutral UI when the user explicitly asks for a plain wireframe, no styling, or a deliberately austere system screen.

| User intent signal | Style direction |
| --- | --- |
| Internal operator, audit, workflow, triage | Compact, dense, restrained, high information contrast |
| Executive review, sales demo, launch decision | Polished, spacious enough for scanability, clear recommendations |
| Technical configuration or developer tool | Sharp, grid-based, keyboard-friendly, compact |
| Editorial strategy, memo, narrative report | Typographic, sectioned, calmer rhythm |
| Product demo or customer-facing prototype | More deliberate spacing, richer state examples, stronger first viewport |
| Generic UI request with no style direction | Choose a tasteful, domain-appropriate treatment using semantic tokens and one or two chart-token/status accents |

Use route-local composition first:

- Use semantic tokens such as `bg-background`, `text-foreground`, `text-muted-foreground`, `bg-muted`, `bg-primary`, `text-primary-foreground`, `border-border`, and `bg-card`.
- Use built-in component variants before custom classes.
- Use chart tokens such as `var(--chart-1)` through `var(--chart-5)` for status accents, progress tracks, metric strips, soft washes, and data visualization accents when available.
- Use route-local `color-mix()` with semantic or chart tokens to create subtle backgrounds, borders, shadows, and status treatments without changing the global theme.
- Use layout classes for spacing, grid, width, and responsive behavior.

Every non-minimal Shadcn route should show evidence of deliberate visual treatment. Good evidence includes:

- Status accent systems mapped to user intent, for example ready, gated, blocked, risky, complete, or internal.
- Card or panel treatments using semantic tokens, chart tokens, subtle shadows, or token-based border accents.
- Meaningful hierarchy through spacing, density, content grouping, and component variants.
- Route-local CSS variables or inline style objects using `var(--chart-*)`, `var(--primary)`, `var(--muted)`, `var(--border)`, or `color-mix()`.
- Polished loading, empty, warning, and success states where the workflow implies them.

Bad evidence:

- A page that merely imports Shadcn `Card`, `Button`, `Badge`, `Table`, or `Tabs` and leaves them at their default neutral appearance.
- A page that uses only black text, gray borders, white cards, and default progress bars for a product surface that should help a user make a decision.
- A page that adds arbitrary Tailwind color families to compensate for default styling instead of using the project tokens.

Avoid:

- Raw Tailwind color families such as `text-emerald-600`, `bg-blue-500`, or `border-violet-300`.
- Manual `dark:` color overrides.
- `space-x-*` or `space-y-*`; use flex/grid with `gap-*`.
- Ad hoc buttons, badges, alerts, skeletons, empty states, or tables when Shadcn primitives exist.
- Icon sizing or margin classes inside component slots; Shadcn button icons use `data-icon`.

When an exception is intentional, add an explicit waiver comment near the code:

```tsx
// shadcn-waive raw-color: route-local prototype uses a one-off status accent
```

Supported waiver codes include `raw-color`, `spacing`, `dark-color`, `raw-table`, `separator`, `skeleton`, `empty-state`, `button-icon`, `button-loading`, `card-composition`, `tabs-list`, `overlay-title`, `grouped-items`, `field-group`, `input-group`, and `visual-treatment`.

## Composition Rules

- Use full Card composition: `Card`, `CardHeader`, `CardTitle`, `CardDescription`, `CardAction` when useful, `CardContent`, and `CardFooter` when applicable.
- Use Shadcn `Table` primitives instead of raw `<table>` markup.
- Use `Empty` for empty states, `Alert` for callouts, `Skeleton` for loading, `Spinner` for pending actions, and `Separator` for dividers.
- Put `TabsTrigger` only inside `TabsList`.
- Give `Dialog`, `Sheet`, and `Drawer` a title for accessibility. Use visually hidden text only when necessary.
- Use `FieldGroup` and `Field` for forms. Use `InputGroupInput` or `InputGroupTextarea` inside `InputGroup`.
- Use `ToggleGroup` for 2 to 7 mutually exclusive or grouped choices instead of manually looping buttons.
- For Radix custom triggers, use `asChild`. For Base UI custom triggers, use `render`; check the `base` field.

## Proactive Preset And Theme Behavior

Do not ask the user to choose layout or components. Do ask before repo-wide design-system mutations.

Safe without asking:

- Creating or updating a route/component using installed Shadcn primitives.
- Choosing a local density/style direction from user intent.
- Using semantic tokens and existing variants.
- Reading Shadcn docs, examples, and project context.
- Running `shadcn info`, `preset resolve`, `docs`, `search`, `view`, `add --dry-run`, or `add --diff`.

Requires user approval:

- `shadcn apply`.
- `shadcn init --preset`.
- `shadcn add` that writes files.
- `--overwrite`.
- Editing global theme tokens, fonts, or component source for broad design-system changes.

When the user's intent implies a repo-wide visual upgrade, present concrete choices:

- Route-local only: no global changes, fastest, safest.
- Partial preset: `apply <preset> --only theme` or `--only font`.
- Full preset apply: updates theme, fonts, icons, CSS variables, and detected UI components.
- Merge path: update config first, then inspect component diffs one by one.

## Validation

Before final response for Shadcn route work:

```bash
python3 $SKILL_ROOT/scripts/validate_shadcn_route.py --cwd <repo> --route-file <route>
pnpm type-check
```

In forked or dependency-stripped workspaces:

- Prefer validators that do not require installing dependencies.
- Do not run package-manager commands that would install dependencies unless the user asked for that.
- If `node_modules` is symlinked outside the fork and Turbopack fails, try a production build or a non-Turbopack dev server only when dependencies are already available.
- If browser tooling or local port binding is unavailable, record the blocker and use route validation plus type/build evidence.

Also browser-check desktop and mobile when possible. Fix warnings that indicate weak use of Shadcn unless there is a clear reason to keep the code as-is.
