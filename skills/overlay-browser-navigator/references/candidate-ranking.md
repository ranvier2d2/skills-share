# Candidate Ranking

Use this reference when an action target is ambiguous, dense, icon-only, or
visually risky.

## Candidate Sources

Collect candidates from the available layers:

- DOM/accessibility snapshot: role, accessible name, text, href, input type,
  selected/expanded/disabled state.
- Screenshot: visible layout, nearby labels, occlusion, modal/menu state, visual
  grouping.
- Overlay semantic map: landmarks, headings, interactive targets, hit boxes,
  focus order, accessible names, repeated components, tab order, and target
  warnings.

## Ranking Order

Prefer a candidate when it has:

1. exact match to the user intent by role and accessible name
2. visible position inside the current viewport
3. stable semantic locator: role/name, label, test id, href, or route intent
4. safe hit box and spacing for the action
5. context match from nearby heading, landmark, row, card, or form group
6. lower duplication risk than visually similar controls
7. direct verification signal after action

Use overlay hit boxes and focus order to downgrade candidates that are visible
but tiny, partially covered, or likely to be the wrong repeated instance.

## Locator Preference

Choose locators in this order when the backend supports them:

1. role plus accessible name
2. label or placeholder for form fields
3. link/button text with contextual parent
4. stable attribute such as `data-testid`
5. URL/href route when navigation is the goal
6. coordinate click only when semantic locators are unavailable and visual
   evidence confirms the target

Do not reuse a stale element reference after navigation, modal changes, route
changes, or significant DOM updates. Re-observe first.

## Ambiguous Interaction Patterns

- Duplicate labels: scope by landmark, heading, form group, row, card, or href
  before acting. If duplicates appear equivalent, verify they share the same
  action target before choosing one.
- Dropdowns and hidden links: do not click hidden descendants just because they
  have the right href. Open the owning menu or navigate by stable href when the
  destination is already known and no click-side effect matters.
- Current-route links: prefer direct URL verification over clicking the selected
  nav item again.
- Repeated cards or rows: bind the action to the surrounding row/card text, not
  just the child button label.
- Stale UI: after route changes, modal changes, filter changes, or virtualized
  list updates, discard prior element handles and re-observe.

## Risk Signals

Treat these as reasons to slow down, inspect overlay evidence, or ask the user:

- duplicate labels with different meanings
- icon-only controls without accessible names
- disabled or visually hidden targets
- tiny targets, overlapping boxes, or nearby destructive controls
- controls inside virtualized tables or route-specific data grids
- authentication redirects that change the current app shell
- action likely to submit, delete, sign out, pay, invite, publish, or mutate data
