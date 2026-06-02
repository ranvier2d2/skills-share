# Bastian's Codex Skills

Private share repository for Bastian's Codex skills.

## Install

Install all skills globally for Codex:

```bash
npx skills add git@github.com:ranvier2d2/skills-share.git -a codex -g
```

If your GitHub auth is configured for HTTPS:

```bash
npx skills add https://github.com/ranvier2d2/skills-share.git -a codex -g
```

List available skills without installing:

```bash
npx skills add https://github.com/ranvier2d2/skills-share.git --list
```

Install one skill:

```bash
npx skills add https://github.com/ranvier2d2/skills-share.git --skill goal-planner -a codex -g
```

## Contents

This repo flattens user-level and project-level Codex skills into `skills/<name>/` so the Vercel `skills` CLI can discover them reliably.

- User/global skills from `~/.codex/skills`
- User/local skills from `~/.codex/skills/local`
- Project skill from the Convex sandbox worktree

Generated dependency and runtime artifact folders such as `node_modules`, `output`, and `tmp` are intentionally excluded. Environment-variable assignment examples and token-like literals are redacted in this copy.

## Skill Count

60 skills.
