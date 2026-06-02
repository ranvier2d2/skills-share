# Global Shadcn Render Host

Use this when the current workspace does not have a usable local Shadcn/json-render UI target and the user did not explicitly ask for a portable standalone HTML file.

## Purpose

The global host prevents the weak fallback pattern where "no UI dependencies in this repo" becomes "make a standalone HTML file." It gives the skill a reusable Next/Shadcn environment with installed dependencies, real `components/ui` primitives, semantic tokens, chart tokens, and browser-proof support.

Default host:

```text
~/.codex/render-hosts/intent-html-renderer-shadcn/
```

Generated route convention:

```text
~/.codex/render-hosts/intent-html-renderer-shadcn/app/artifacts/<slug>/page.tsx
```

Evidence convention:

```text
~/.codex/render-hosts/intent-html-renderer-shadcn/evidence/<slug>/
```

## Target Priority

Use this order:

1. Local repo route/component when the repo has usable React/Next/Shadcn/json-render.
2. Global Shadcn render host when the repo has no usable UI dependencies, no Shadcn target, or dependency install would pollute the repo.
3. Standalone HTML only when the user explicitly asks for a portable/single-file artifact, or the global host is unavailable and cannot be bootstrapped.
4. Plain/minimal output only when the user asks for plain, wireframe, no styling, or a deliberately austere screen.

Do not treat "this repo has no Shadcn" as permission to create low-quality standalone HTML.

## Bootstrap

Set `SKILL_ROOT` to this skill's installed directory before running script examples.

Run:

```bash
python3 $SKILL_ROOT/scripts/ensure_global_shadcn_host.py --install --json
```

For a quick check without installing:

```bash
python3 $SKILL_ROOT/scripts/ensure_global_shadcn_host.py --json
```

Use `--force` only when intentionally refreshing the managed host template files.

## Artifact Workflow

1. Pick a stable slug from the user's intent.
2. Create `app/artifacts/<slug>/page.tsx` in the host.
3. Use host imports:

```tsx
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
```

4. Use the same visual standard as local Shadcn output:
   - Semantic tokens.
   - `var(--chart-*)` accents.
   - Route-local `color-mix()` treatments.
   - Real Shadcn primitives instead of ad hoc controls.
   - No raw Tailwind color families unless explicitly waived.
5. Validate against the host:

```bash
python3 $SKILL_ROOT/scripts/validate_shadcn_route.py \
  --cwd ~/.codex/render-hosts/intent-html-renderer-shadcn \
  --route-file ~/.codex/render-hosts/intent-html-renderer-shadcn/app/artifacts/<slug>/page.tsx
```

6. Run:

```bash
pnpm type-check
pnpm build
```

from the host directory.

7. Browser proof:

```bash
pnpm exec next start -p <free-port>
python3 $SKILL_ROOT/scripts/browser_proof.py \
  --url http://localhost:<free-port>/artifacts/<slug> \
  --output-dir ~/.codex/render-hosts/intent-html-renderer-shadcn/evidence/<slug> \
  --json
```

Stop the server after capture.

## Maintenance

- Do not install dependencies in the user's unrelated repo just to render an artifact.
- Do not write generated artifacts into the skill source folder.
- The host is a cache/runtime, not the canonical skill source.
- If the host breaks, refresh it with `ensure_global_shadcn_host.py --install --force --json`.
- If a user explicitly needs a shareable single file, use standalone HTML instead of the host.
