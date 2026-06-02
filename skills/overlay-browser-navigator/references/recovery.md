# Recovery

Use this reference when an action fails, the page navigates unexpectedly, the
session redirects, or verification does not match the intended state.

## Recovery Loop

1. Capture the failure: failed locator, attempted action, current URL, and
   expected verification signal.
2. Re-observe with fresh DOM/accessibility state and screenshot.
3. Add overlay semantic map if the first attempt did not already use it.
4. Remove the failed target from the candidate set unless the failure was caused
   by stale state rather than wrong target.
5. Re-rank candidates using current state.
6. Try one safer alternate action, then verify again.
7. If still ambiguous or high risk, stop and ask the user.

## Self-Healing Rules

- If a ref is stale, re-snapshot and retry by semantic locator.
- If the app redirects to sign-in, stop unless the user has explicitly asked to
  continue after sign-in or provided an authenticated persistent session.
- If a menu or modal closed during the action, re-open it before selecting a
  nested item.
- If route navigation fails, try the visible navbar link, then direct href/URL
  only if it is clearly equivalent.
- If a click lands on the wrong repeated row/card, use row/card context from
  nearby text and overlay bounding boxes before retrying.

## Reversibility

Prefer reversible or low-risk probes during recovery:

- hover or focus before click when it reveals labels
- open menus before selecting menu items
- inspect route links before navigating
- fill but do not submit until fields and submit target are verified
- use dry-run/evidence mode for destructive workflows

Escalate to the user before destructive actions when verification depends on
private or business-critical state.

