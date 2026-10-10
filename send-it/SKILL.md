---
name: send-it
description: "Review changes, open a PR, resolve CI and review feedback, and verify readiness. Merge only when explicitly requested."
---

# Send it

Take intended changes through a reviewed, verified PR. Stop before merge unless the user explicitly requested merge or auto-merge; “send it”, “ship it”, and “open the PR” alone do not authorize merging.

## Prepare

1. Inspect `git status --short --branch` and `git diff --stat`. Identify intended files and the PR base; clarify only an ambiguous target. Preserve unrelated dirty/untracked files.
2. Create/switch to the topic branch before cleanup, review, or screenshots. Fetch `origin <base>` and compute the merge base against `origin/<base>`. Use fresh remote state for the actual PR diff; do not merge/rebase the base into the topic as part of this workflow.
3. Check required tools/authentication up front: git, authenticated gh, reviewer CLIs (claude, codex, coderabbit), TruffleHog, and repo hook/validation dependencies. Install or fix required dependencies before the loop; follow the review reference's unavailable-reviewer rules. On macOS, start `caffeinate -di &`, record its PID, and stop it at closeout.
4. Secret-scan intended files using the repo scanner (e.g. `pnpm secretlint`), or inspect for keys/tokens, env material, and dumps when none exists. Commit only intended tracked/untracked files; never `git add -A`.

## Clean and review

After the initial commit, inspect the full intended diff with `git diff --stat <merge-base>`, `git diff --numstat <merge-base>`, and `git diff <merge-base> -- <intended files>`.

Remove dead/duplicate code, unnecessary abstractions/helpers, debug scaffolding, accidental/generated noise, needless renames, and unrelated style churn. Preserve behavior, meaningful tests, edge cases, accessibility, security, and clarity. Run targeted checks and commit the cleanup. Allow at most two cleanup passes, then continue.

Read and follow [review rounds](references/review-rounds.md) before invoking reviewers. It defines the exact bundled helper, secret preflight, three reviewers (Claude Opus, Codex GPT sol, CodeRabbit), skip-if-unavailable rules, frozen heads, delta/full-diff phases, rejection ledger, accepted-risk disclosure, serial fix subagent, CodeRabbit retries, and convergence limits. Do not substitute another skill's helper or run `codex review`.

Present accepted risks with reasons before creating the PR and again at closeout. Never report an errored, unavailable, rate-limited, or skipped review as clean.

## Validate and open the PR

Run the checks required by AGENTS.md, package scripts, and CI. Inspect the pre-push hook (e.g. `.husky/pre-push`) first: when it runs the full gate, use focused local checks and let the hook run the suite once.

Wait for commit hooks to finish; poll the same command session after a timeout. Do not start a concurrent build in that worktree or retry a commit before checking hook processes, `git log`, and `git status`.

For UI changes, read [screenshots](references/screenshots.md) after review convergence and green validation. Capture changed views when trivial, before/after only when cheap; skip gated or difficult captures. Any later UI change invalidates the images and requires recapture/replacement. Keep images out of git.

Commit only intended files, push the topic branch, and create the PR with a concise summary, validation, and applicable screenshot links.

## Resolve CI and feedback

1. Watch `gh pr checks <number> --repo <owner>/<repo> --watch --interval 20 2>&1 | tail -15`. Inspect the latest head, merge state, reviews, comments, and review threads after checks settle.
2. After checks turn green, wait about 30 seconds and re-audit review threads (e.g. `gh api graphql` reviewThreads); bots can publish inline feedback later. A green status reporting “Review rate limited” does not prove a review occurred. Use completed local review evidence and disclose the coverage gap.
3. Fix valid feedback locally, secret-scan new files, and commit intended fixes. Follow the same review reference, starting against `origin/<topic-branch>` (the pushed head), with CodeRabbit `-t committed`. Keep the ledger and the skip-if-unavailable rules.
4. After a feedback round touching more than 3 files or about 50 lines, run a final full-branch review against `origin/<base>`; small fixes skip that extra round. Push, resolve fixed/outdated/false-positive threads, and resume CI checks for the new head.
5. Continue until required CI is green and no actionable comments remain. Replace stale screenshots if UI behavior changed.

## Merge and closeout

Only for an explicitly requested merge, verify the latest head has clean merge state, green required checks, review bots successful or skipped (not pending), resolved/outdated review threads, no actionable comments, and no unintended tracked changes. Merge using that verified head SHA. Default workflow never merges or enables auto-merge.

Report PR URL, final head, checks, review coverage/comment status, readiness, screenshot links, remaining local untracked files, and accepted risks with reasons. Include the merge SHA only after an authorized merge. Stop the recorded caffeinate process.
