# Ableton Computer Use UI Adapter Workflows

## Operating Contract

Treat Computer Use as a UI adapter with an explicit control contract:

```text
intent -> structured preflight -> UI action -> structured readback -> diff -> decision
```

Use stdout from scripts for machine-readable state, stderr for human diagnostics,
and files only for explicit evidence artifacts.

## Primitive Semantics

| Computer Use primitive | CONTEXT.md role | Use in Ableton |
| --- | --- | --- |
| `get_app_state` | RuntimeState observation | Identify active window, selected track/device, visible controls |
| `click` | DAW Materialization | Toggle Configure, press plugin buttons, select devices |
| `set_value` | DAW Materialization | Set visible text fields/sliders when accessibility exposes values |
| `type_text` | DAW Materialization | Search browser, rename tracks, enter numeric values |
| `scroll` | Runtime navigation | Reveal tracks/devices/browser results |
| `drag` | DAW Materialization | Load devices, move clips, adjust UI controls when safer APIs are missing |
| screenshot/app tree | Evidence Policy support | Preserve visual evidence, never final proof alone |

## Workflow: Expose Plugin Parameters

1. Inspect the target device with the parameter exposure tool:

```bash
uv run python scripts/device_parameter_exposure.py inspect 9 0 --out before.json --json
```

2. Use Computer Use:

```text
get_app_state
select target track/device
open plugin window if needed
enable Configure
touch desired plugin controls
disable Configure
get_app_state
```

3. Verify:

```bash
uv run python scripts/device_parameter_exposure.py inspect 9 0 --out after.json --json
uv run python scripts/device_parameter_exposure.py compare before.json after.json --format names --json | jq '.added_names'
```

4. If the desired control is still missing, report `Unknown State` or create a
MIDI fallback manifest. Do not invent a parameter index.

## Workflow: Load Or Swap Plugin Presets

1. Capture current device and parameter state via AbletonOSC when possible.
2. Use Computer Use to open the preset browser and select the candidate preset.
3. Verify by reading device name, parameter names, selected UI text, or audible
producer acceptance.
4. Record a safe point only after listening or explicit producer approval.

## Workflow: Visual Reconciliation

Use when bridge state and visible UI disagree.

1. Query structured state first:

```bash
uv run python scripts/ableton_state_cli.py --json status
```

2. Use Computer Use to observe the relevant Live surface.
3. Classify the result:

```text
matched: structured and visual evidence agree
mismatch: both are readable but disagree
unknown: one side cannot be observed
```

4. Prefer structured state when it is known-good and recent. Prefer visual state
only for UI-only facts such as plugin window contents or modal dialogs.

## MIDI Fallback Pattern

Use MIDI CC/MIDI Learn only when host-exposed DeviceParameters are unavailable.
Create a manifest with:

```json
{
  "schema_version": "midi-ui-mapping.v1",
  "target": {
    "track_name": "Main",
    "device_name": "Transit 2",
    "control_label": "Macro"
  },
  "midi": {
    "channel": 1,
    "cc": 21,
    "value_range": [0, 127]
  },
  "verification": {
    "method": "visual_plugin_window_or_audio_acceptance",
    "limitations": ["No DeviceParameter automation_state readback"]
  }
}
```

MIDI is lower-observability control. Use it for performance or emergency access,
not as the default automation substrate.

## Failure Modes

- **Focus drift**: UI action hits the wrong window. Mitigation: `get_app_state`
  before every sequence.
- **Coordinate drift**: layout or zoom changes. Mitigation: prefer accessible
  UI elements over raw coordinates.
- **Semantic drift**: visible text is misunderstood. Mitigation: verify against
  structured state or ask the producer.
- **State drift**: UI changed but the agent's model did not. Mitigation:
  after-action readback and compact diffs.
- **Over-materialization**: UI writes too much at once. Mitigation: one UI
  affordance per verify cycle.
