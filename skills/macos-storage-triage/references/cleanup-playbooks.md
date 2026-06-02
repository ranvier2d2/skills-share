# Cleanup Playbooks

## Emergency Oxygen

Use when free space is below 10 GiB.

1. Measure baseline:

```sh
df -h /System/Volumes/Data /
```

2. Check VM pressure:

```sh
du -sh /System/Volumes/VM 2>/dev/null
```

If swap is large, recommend closing heavy apps or rebooting. Do not delete swapfiles.

3. Clean only low-risk, manager-supported candidates first:

```sh
brew cleanup -n
xcrun simctl delete unavailable
xcrun simctl runtime dyld_shared_cache remove --all
```

4. Re-measure before escalating.

## Xcode Simulator Runtime Cleanup

1. Dry-run:

```sh
xcrun simctl runtime delete all --dry-run
```

2. If user confirms unused simulators:

```sh
xcrun simctl runtime delete all
```

3. Poll:

```sh
xcrun simctl runtime list
```

Wait until `Total Disk Images: 0 (0.0G)` or until no target runtimes remain.

4. Re-measure:

```sh
df -h /System/Volumes/Data /
du -sh /System/Volumes/Data/Library/Developer/CoreSimulator 2>/dev/null
```

## Homebrew / Conda Cleanup

1. Inspect:

```sh
du -xhd 1 /opt/homebrew /opt/homebrew/Caskroom /opt/homebrew/Cellar 2>/dev/null | sort -h
brew cleanup -n
brew list --cask --versions
```

2. Prefer manager uninstall:

```sh
brew uninstall --cask <name>
```

3. If the manager fails because of non-interactive `sudo`, use direct removal only when all are true:

- user confirmed the cask is unused;
- path is under `/opt/homebrew/Caskroom/<name>`;
- path is user/admin-owned or otherwise safely removable;
- exact path and symlinks are shown first.

## App Support Cleanup

1. Close the app.
2. Prefer cache-only subpaths: `Cache`, `Code Cache`, `Service Worker/CacheStorage`, `GPUCache`.
3. Treat profiles, `IndexedDB`, `Local Storage`, and app databases as high risk.
4. Re-open app only after confirming the user accepts possible cache rebuild/login effects.

## Human Media / Synced Folder Review

Produce a review table with:

- path;
- physical size;
- age;
- likely source;
- cloud/sync status if known;
- recommendation: keep local, offload, archive, or ask.

Do not default-delete.
