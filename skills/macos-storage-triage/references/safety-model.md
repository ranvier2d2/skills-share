# Safety Model

## Value Classes

| Class | Meaning | Default action |
|---|---|---|
| Regenerable cache | Can be rebuilt by tools or apps | Low-risk candidate after dry-run |
| Developer runtime | Xcode runtimes, package managers, local language stacks | Use native manager; require confirmation |
| App cache/state | Service workers, app caches, IndexedDB, local storage | Close app; cache-only cleanup; profile data is high risk |
| Agent memory/artifact | Codex sessions, render hosts, generated artifacts | Archive or ask; do not blind-delete |
| Human-created value | Media, documents, datasets, project folders | Review/offload/archive; never default delete |
| Installed app | `.app` bundles, casks, complex vendor installs | Human uninstall choice only |
| System-managed | VM swap, Preboot, Recovery, MobileAssets not exposed by managers | Do not manually delete |
| Measurement trap | Sparse files, hardlinks, cloud placeholders | Verify physical allocation with `du` |

## Risk Classes

| Risk | Definition | Examples |
|---|---|---|
| Low | Regenerable and manager-supported | package caches, Homebrew cache, simulator dyld cache |
| Medium | Regenerable but workflow-affecting | Xcode runtimes, Conda, app service-worker caches |
| High | May lose identity, work, local-only data, or history | browser profiles, app databases, Dropbox files, Codex sessions |
| Do-not-delete | OS-managed or unsafe without a specific privileged plan | swapfiles, Recovery, Preboot, arbitrary MobileAssets |

## Non-Negotiable Rules

1. Audit is read-only.
2. Destructive actions require explicit user confirmation.
3. Use `du` for reclaimable size; never trust `ls` alone.
4. Prefer managers (`brew`, `xcrun simctl`, app tools) over direct filesystem deletion.
5. Do not manually delete VM swap, Preboot, Recovery, or `_nsurlsessiond`-owned assets.
6. Do not delete synced folders without proving cloud/local status and asking.
7. Do not delete Codex sessions without an archive/export option.
8. Always remeasure after cleanup.
