---
name: send-it
description: Use when the user wants Codex to send changes to main by running pre-PR reviews, creating a pull request, monitoring CI and review comments, fixing valid feedback, repeating until clean, and merging only after checks and comments are resolved.
---

# Send It

Use this skill for an end-to-end "get this branch safely merged" workflow.

## Workflow

1. Inspect the worktree with `git status --short --branch` and `git diff --stat`. Identify intended PR files and leave unrelated dirty or untracked files alone.

2. Confirm the target branch and merge intent if either is ambiguous. If the user explicitly asked to send the work through, treat PR creation, CI monitoring, review-comment handling, and final merge as in scope.

3. Before creating the PR, run independent pre-PR reviews when practical:
   - `codex review --uncommitted`
   - a second `codex review --uncommitted` pass when the change is risky or broad
   - `coderabbit review --agent -t uncommitted` if CodeRabbit CLI is installed and authenticated
   - a second CodeRabbit pass when the first pass found issues or the change is risky

   Treat every finding as a hypothesis. Verify it against the current code, fix valid issues, ignore false positives with a brief rationale, and run targeted checks after fixes.

4. Run repo-appropriate validation from `AGENTS.md`, package scripts, and CI config. Commit only intended files, push a topic branch, and create a PR with a concise summary and validation notes.

5. Monitor the PR until it is clean:
   - Check latest head SHA, merge state, CI/check status, reviews, comments, and review threads.
   - Wait about 15 minutes after PR creation, and about 10-15 minutes after each pushed fix, for CI and review bots.
   - Fix valid comments, resolve fixed, outdated, or false-positive threads, commit, push, and restart this loop from the new head SHA.

6. Merge only when the latest PR head satisfies all gates:
   - merge state is clean
   - required checks are green
   - review bots are success or skipped, not pending
   - all review threads are resolved or outdated
   - no unresolved actionable comments remain
   - local worktree has no unintended tracked changes

   Merge with the verified latest head SHA.

7. Report the PR URL, merge commit SHA, final head SHA, checks passed, review/comment status, and any remaining local untracked files.
