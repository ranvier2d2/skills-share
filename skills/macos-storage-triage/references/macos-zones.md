# macOS Storage Zones

## First-Pass Low-Risk Zones

- `~/Library/Caches`
- `~/.cache`
- `~/.npm`
- `~/Library/pnpm`
- Homebrew cache via `brew cleanup` or `brew cleanup -n`
- Xcode unavailable simulators via `xcrun simctl delete unavailable`
- Xcode simulator dyld caches via `xcrun simctl runtime dyld_shared_cache remove --all`

## Manager-Only Zones

- `/System/Volumes/Data/Library/Developer/CoreSimulator`
- `/System/Volumes/Data/System/Library/AssetsV2/*SimulatorRuntime*`
- `/opt/homebrew/Cellar`
- `/opt/homebrew/Caskroom`
- Docker disk images and containers

Use the owning tool first. Avoid manual deletion unless a specific path is user-owned residue, the manager failed, and the user confirmed the exact fallback.

## High-Risk Zones

- `~/Library/Application Support/Google/Chrome/*Profile*`
- Browser `Default` folders
- `~/Library/Application Support/*/IndexedDB`
- `~/Library/Application Support/*/Local Storage`
- `~/Library/Group Containers`
- Dropbox, Google Drive, iCloud, OneDrive local folders
- media folders and datasets
- `~/.codex/sessions`

These may contain identity, offline work, app databases, or human-created value.

## Do-Not-Delete Zones

- `/System/Volumes/VM`
- `/System/Volumes/Preboot`
- Recovery volumes
- OS snapshots without using supported tools
- `_nsurlsessiond`-owned MobileAsset files unless handled by a supported system cleanup path

## Sparse File Rule

Always compare logical and physical size for disk images:

```sh
ls -lh path
du -h path
```

If `ls` is huge but `du` is small, the file is sparse and does not represent reclaimable space.
