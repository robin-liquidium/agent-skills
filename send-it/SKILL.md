---
name: send-it
description: Use when the user wants Codex to send changes toward main by running pre-PR reviews, creating a pull request, attaching before/after screenshots for UI PRs, monitoring CI and review comments, fixing valid feedback, and repeating until clean. Do not merge unless the user explicitly asks for a merge.
---

# Send It

Use this skill for an end-to-end "get this branch into a clean PR" workflow. By default, stop before merge.

## Workflow

1. Inspect the worktree with `git status --short --branch` and `git diff --stat`. Identify intended PR files and leave unrelated dirty or untracked files alone. Determine the PR base branch before changing branches.

2. Confirm the target branch if ambiguous. Do not infer merge intent from phrases like "send it", "ship it", "get this through", or "open the PR"; treat those as PR creation, CI monitoring, and review-comment handling only. Merge is in scope only when the user explicitly asks to merge, enable auto-merge, or merge after checks pass.

3. Create or switch to the intended topic branch before reviews, screenshots, or cleanup. Preserve unrelated dirty and untracked files exactly as found.

4. Before creating the PR, do a diff-minimization cleanup pass against the base branch:
   - Review the full intended PR diff with commands such as `git diff --stat <merge-base>`, `git diff --numstat <merge-base>`, and `git diff <merge-base> -- <intended files>`, where `<merge-base>` is the merge base between the topic branch and the PR base.
   - Look for safe ways to reduce added lines, total diff size, and review noise while preserving the same functionality and tests. Good targets include dead code, duplicated logic, overly broad abstractions, unused helpers, debug scaffolding, generated or accidental files, unnecessary renames, and style-only churn mixed into feature work.
   - Apply cleanup only when it keeps behavior equivalent or clearer. Do not remove meaningful tests, important edge-case handling, accessibility, security checks, or code clarity just to shrink the diff.
   - After cleanup, rerun targeted validation for the touched area, then re-check the diff. If more safe cleanup is obvious, repeat this pass before continuing.
   - Once the diff is as small and focused as reasonably possible, continue automatically with the remaining workflow.

5. Before creating the PR, run independent pre-PR reviews when practical:
   - `codex review --uncommitted`
   - a second `codex review --uncommitted` pass when the change is risky or broad
   - `coderabbit review --agent -t uncommitted` if CodeRabbit CLI is installed and authenticated
   - a second CodeRabbit pass when the first pass found issues or the change is risky

   Treat every finding as a hypothesis. Verify it against the current code, fix valid issues, ignore false positives with a brief rationale, and run targeted checks after fixes.

6. For UI-visible changes, capture before and after screenshots when practical before creating the PR:
   - Use a browser tool to capture comparable views, such as Playwright CLI, [@Browser](plugin://browser@openai-bundled), the Chrome plugin, or the repo's existing visual QA command.
   - Store screenshots as temporary local artifacts only; do not commit them.
   - Upload screenshots to Litterbox with a 72-hour expiry:
     `curl -F "reqtype=fileupload" -F "time=72h" -F "fileToUpload=@screenshot.png" https://litterbox.catbox.moe/resources/internals/api.php`
   - Verify each returned `https://litter.catbox.moe/...` URL is a direct image link with an `image/*` content type before embedding it in the PR description. If verification hangs, retry with HTTP/1.1, for example:
     `curl --http1.1 --max-time 20 -I https://litter.catbox.moe/example.png`
   - If Litterbox upload or verification fails, skip screenshot links and note that the upload failed.

7. Run repo-appropriate validation from `AGENTS.md`, package scripts, and CI config. Commit only intended files, push the topic branch, and create a PR with a concise summary, validation notes, and UI screenshot links when applicable.

8. Monitor the PR until it is clean:
   - Check latest head SHA, merge state, CI/check status, reviews, comments, and review threads.
   - Wait about 15 minutes after PR creation, and about 10-15 minutes after each pushed fix, for CI and review bots.
   - Fix valid comments, resolve fixed, outdated, or false-positive threads, commit, push, and restart this loop from the new head SHA.

9. If and only if the user explicitly requested a merge, merge only when the latest PR head satisfies all gates:
   - merge state is clean
   - required checks are green
   - review bots are success or skipped, not pending
   - all review threads are resolved or outdated
   - no unresolved actionable comments remain
   - local worktree has no unintended tracked changes

   Merge with the verified latest head SHA. Never enable auto-merge or merge manually as part of the default workflow.

10. Report the PR URL, final head SHA, checks passed, review/comment status, merge readiness, UI screenshot links when applicable, and any remaining local untracked files. Include the merge commit SHA only if a user-requested merge was completed.
