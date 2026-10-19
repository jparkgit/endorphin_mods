---
name: fetchpetmods
description: Updates the user's installed pet mods by running git pull origin main in ~/.claude/mods/endorphin_mods and summarizing what changed. Use when the user types /fetchpetmods, or asks to update, pull, fetch or sync their pet mods.
---

# fetchpetmods

Run these from anywhere. The folder is fixed: `~/.claude/mods/endorphin_mods`.

## Steps

1. Record the current commit and confirm the folder is a git repo:

```bash
cd ~/.claude/mods/endorphin_mods && git rev-parse --short HEAD
```

If the folder is missing, stop and tell the user to clone `https://github.com/jparkgit/endorphin_mods.git` there. See the root README.

2. Pull:

```bash
cd ~/.claude/mods/endorphin_mods && git pull origin main
```

3. If the pull fails, for example it cannot fast-forward because of local changes or diverged history, stop. Show git's error and the output of `git status --short`. Change nothing else. Do not stash, reset, rebase or merge.

4. If it succeeds, show what changed since the commit from step 1:

```bash
cd ~/.claude/mods/endorphin_mods && git log --oneline <old>..HEAD && git diff --stat <old> HEAD
```

Name any pet folder that was added or changed. If nothing changed, say it was already up to date.

5. Remind the user that sessions already open do not load updated mods, so they restart Claude Code.

## Verify

Run `git status -sb` in the folder. It must show `main` with no `behind` count.
