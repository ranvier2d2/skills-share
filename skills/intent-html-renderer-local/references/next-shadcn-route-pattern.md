# Next Shadcn Route Pattern

Use this when `detect_ui_target.py` finds a Next/React app with Shadcn primitives.

## Implementation Pattern

1. Locate the app package and route root, commonly `app/`, `apps/web/app/`, or `src/app/`.
2. Read nearby routes and `components/ui` imports to match local style.
3. Read `references/shadcn-intent-rendering.md`.
4. Run Shadcn context detection when the CLI is available:

```bash
pnpm dlx shadcn@latest info --json
pnpm dlx shadcn@latest preset resolve --json
```

5. Create or update `app/<slug>/page.tsx` unless the user requested a different route.
6. Import primitives from the local UI layer using the alias returned by Shadcn context, for example:

```tsx
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
```

7. Use the project's configured icon library from `shadcn info`; do not assume `lucide-react` unless context says `lucide`.
8. Keep data fixtures domain-specific and close to the route unless the repo has a fixture convention.
9. Use Tailwind classes and existing semantic tokens. Do not add raw `<style>` blocks for normal layout.

## Layout Rules

- Build the first viewport as the usable artifact, not a landing explanation.
- Avoid cards inside cards. Use bands, grids, tables, lists, tabs, or panels for structure.
- Reserve large hero type for true landing pages. Dashboards and reports need compact headings.
- Put inherently wide content in bounded scroll regions, not page-level horizontal scroll.
- Use responsive grid constraints such as `grid-cols-1`, `md:grid-cols-2`, `xl:grid-cols-4`, and stable `min-h` values.
- Use Shadcn variants rather than custom button/card chrome when the local primitive supports it.
- Use `gap-*`, not `space-x-*` or `space-y-*`.
- Use Shadcn `Table`, `Alert`, `Empty`, `Skeleton`, `Progress`, `Separator`, and `Badge` instead of ad hoc markup when those primitives are installed.
- Use semantic tokens instead of raw color utilities for status and emphasis.
- Put icons inside buttons with `data-icon="inline-start"` or `data-icon="inline-end"` and no sizing/margin classes.

## Common Surfaces

- **Decision dashboard:** summary metrics, prioritized table/list, filters or tabs, recommendation panel, next actions.
- **Executive report:** compact header, evidence sections, comparison matrix, risks, decision log, export/share actions.
- **Action-command tool:** natural-language command input, detected assumptions, clarification controls, execution progress, logs, results.
- **Prompt-to-UI workbench:** prompt input, generated preview, code/tree toggle, validation status, debug drawer.
- **Launch readiness tool:** component/bundle matrix, exposure decision, missing docs/demos, owner/action table, risk callout.

## Validation

Run:

```bash
python3 $SKILL_ROOT/scripts/validate_shadcn_route.py --cwd <repo> --route-file <route>
pnpm type-check
```

Set `SKILL_ROOT` to this skill's installed directory before running the validation command.

When possible, open the route at desktop and mobile widths. Fix console errors, clipping, unreadable text, overlap, blank regions, Shadcn validation warnings, and page-level horizontal overflow before final response.
