# GitHub setup (one-time)

Repo is ready to push once a remote exists.

## 1. Create repo + remote

```powershell
# On GitHub: create empty repo (no README if you already have one locally)
git remote add origin https://github.com/<owner>/starscream.git
git push -u origin master
```

## 2. Install GitHub CLI

https://cli.github.com/

```powershell
gh auth login
```

## 3. Create roadmap issues (21 issues)

```powershell
python scripts/create_roadmap_issues.py --create
```

Creates labels (`tier-0`…`tier-8`), milestones (`v0.1`, `v0.2`), and issues from [GITHUB_ISSUES.md](./GITHUB_ISSUES.md).

## 4. Open PR + confirm CI

```powershell
git checkout -b release/v0.1-prep
git push -u origin release/v0.1-prep
gh pr create --title "v0.1 prep: commit core + roadmap" --body "Tier 0: untracked core committed. Watch integration job."
```

Confirm three jobs green: **lint**, **test**, **integration** (testcontainers).

## 5. Heavy proof (dedicated machine)

See [PHASE2_RUNBOOK.md](./PHASE2_RUNBOOK.md) — smoke E2E + corpus build.
