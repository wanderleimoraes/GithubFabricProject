# Git Guide — How Version Control Works (and our daily routine)

This is a practical, from-first-principles guide to git, written around how we actually
use it in this project. Read it once and the commands stop feeling like magic.

---

## 1. Why git exists

Git answers three needs:
1. **History** — every saved state is recoverable. You can go back to how the code
   looked last Tuesday, or before a change broke something.
2. **Collaboration** — multiple people (or multiple machines — see §5) can work on the
   same project and merge their changes without overwriting each other.
3. **Safety** — nothing is silently lost or overwritten; git makes you resolve clashes
   explicitly.

A **repository** ("repo") is a folder that git tracks. Ours is `GithubFabricProject`.

---

## 2. The mental model: a change lives in up to 4 places

```
Working directory   →   Staging area   →   Local repository   →   Remote (GitHub)
(files on disk)         (the "index")      (commit history)        (the cloud copy)
```

Every git command just moves a change from one box to the next. Internalize this and
the whole tool makes sense.

| Box | What it is |
|-----|-----------|
| **Working directory** | The actual files you edit on disk. |
| **Staging area** | A holding zone for the changes you've chosen to include in the *next* snapshot. |
| **Local repository** | The `.git` folder — the full history of commits, stored on your machine. |
| **Remote** | The shared copy on a server (GitHub, Bitbucket, etc.). |

---

## 3. The core commands, mapped to the model

| Command | What it does | Moves a change… |
|---------|-------------|-----------------|
| `git status` | Shows what changed and which box it's in | reports only |
| `git diff` | Shows the line-by-line changes not yet staged | reports only |
| `git add <file>` | **Stages** a file for the next snapshot | working dir → staging |
| `git add .` | Stages *everything* changed | working dir → staging |
| `git commit -m "message"` | Records a **snapshot** of staged changes | staging → local repo |
| `git push origin <branch>` | **Uploads** local commits to the remote | local repo → remote |
| `git pull origin <branch>` | **Downloads** + merges remote commits | remote → working dir |
| `git log --oneline -5` | Lists recent commits | reports only |
| `git clone <url>` | Copies a remote repo to a new local folder (one-time setup) | remote → new local repo |

**Why three steps to publish (`add` → `commit` → `push`)?** The separation is the
point:
- `add` lets you choose *exactly* what goes in a snapshot (not necessarily everything you changed).
- `commit` makes a labeled checkpoint you can return to or undo.
- `push` is the deliberate moment you decide to share it.

Saving a file in the folder does **none** of these — it only updates the working
directory. That's why a freshly-saved file "isn't on GitHub" until you add, commit, and push it.

---

## 4. Branches

A **branch** is an independent line of work. The default is usually `main`. We develop
on a feature branch:

```
claude/sp500-data-portfolio-sinj32
```

Why branch instead of committing to `main`? So `main` always stays in a known-good
state while you experiment. When the branch is ready, it's merged into `main` (often via
a **Pull Request** — a request to merge, reviewed before it lands).

Useful branch commands:
```bash
git branch                      # list local branches (* marks current)
git switch <branch>             # move to an existing branch
git switch -c <new-branch>      # create and move to a new branch
```

You stay on one branch until you deliberately switch. `push`/`pull` act on the branch
you name.

---

## 5. The two-machine reality (why "I push, you pull")

In this project the same repo exists in two places:
- **The cloud session** — where lesson files and scripts are edited, then committed and pushed.
- **Your laptop** — where you run dbt, build the `.pbix`, etc.

GitHub is the shared middle. Changes only cross between machines through the remote:
- After the cloud session pushes, your laptop won't have those changes until you `git pull`.
- Your laptop's work (e.g. the `.pbix`) won't reach GitHub until *you* push.

`push` and `pull` are the only two commands that cross machines. Everything else is local.

---

## 6. The daily routine

```bash
# 1. Start — get the latest before touching anything
git pull origin claude/sp500-data-portfolio-sinj32

# 2. Work — edit files, build models, etc.

# 3. See what changed
git status
git diff                  # line-by-line (text files only)

# 4. Stage what belongs together
git add path/to/file1 path/to/file2     # or: git add .

# 5. Snapshot with a clear message
git commit -m "Add price-trend report page and YoY measure"

# 6. Share
git push origin claude/sp500-data-portfolio-sinj32

# Repeat 2–6 in small, logical chunks.
```

Two habits that make this painless:
- **Commit small and often.** One commit per logical change beats one giant end-of-day
  commit — each is a rollback point, and the messages become a readable project history.
- **Pull before you start, push when you pause.** Keeps machines in sync and avoids
  conflicts.

---

## 7. Conflicts (don't panic)

A **conflict** happens when the same lines of a file changed in two places (e.g. the
cloud and your laptop) and git can't auto-merge. On `pull` it stops and marks the file:

```
<<<<<<< HEAD
your version
=======
the incoming version
>>>>>>> origin/branch
```

To resolve: edit the file to the version you want (delete the `<<<`, `===`, `>>>`
markers), then:
```bash
git add <file>
git commit            # completes the merge
```

Git never silently overwrites — a conflict is git protecting your work, not breaking it.

---

## 8. Handy situations

| Situation | Command |
|-----------|---------|
| Discard unstaged changes to a file | `git restore <file>` |
| Unstage a file (keep the edit) | `git restore --staged <file>` |
| See full history | `git log --oneline --graph` |
| Undo the last commit but keep the changes | `git reset --soft HEAD~1` |
| See what a commit changed | `git show <commit-hash>` |
| Stop tracking a file but keep it on disk | `git rm --cached <file>` |

**Binary files (like `.pbix`):** git versions them fine, but `git diff` can't show
*what* changed inside — only that the file changed. That's expected for non-text files.

**`.gitignore`:** lists patterns git should never track (secrets, data, caches). In this
repo it excludes `.env`, `data/`, `*.parquet`, dbt `target/`, etc. — which is why those
never show up in `git status`.

---

## 9. Does Bitbucket / GitLab / Azure DevOps use the same commands?

**Yes — the local git commands are identical everywhere.** Git is the tool; GitHub,
Bitbucket, GitLab, and Azure DevOps Repos are just *hosting services* for git repos.
`add`, `commit`, `push`, `pull`, `branch`, `merge`, `log` work exactly the same against
any of them. What differs is only the layer *around* git:

| Aspect | Differs between hosts? |
|--------|------------------------|
| Core git commands (`add`/`commit`/`push`/`pull`/`branch`/`merge`) | **No — identical** |
| The remote URL you push to | Yes (`github.com/...` vs `bitbucket.org/...`) |
| Authentication | Yes (GitHub tokens/SSH; Bitbucket app passwords/SSH; etc.) |
| "Merge request" naming | GitHub/Bitbucket call it **Pull Request**; GitLab calls it **Merge Request** |
| CLI helper | `gh` is GitHub-only; others have their own CLIs/APIs |
| CI/CD config file | `.github/workflows/` (GitHub Actions) vs `bitbucket-pipelines.yml` vs `.gitlab-ci.yml` |

So everything you've learned here transfers directly. To move this project to Bitbucket
you'd only change the remote:
```bash
git remote set-url origin https://bitbucket.org/<you>/<repo>.git
git push origin claude/sp500-data-portfolio-sinj32
```
The commit history, branches, and your muscle memory all come along unchanged.

---

## 10. One-line summary

> Edit in the **working directory** → `git add` to **stage** → `git commit` to
> **snapshot** locally → `git push` to **share**; `git pull` to **receive**. Hosts
> change; the commands don't.
