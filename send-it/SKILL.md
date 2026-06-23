---
name: send-it
description: Use when the user wants Codex to send changes toward main by running pre-PR reviews, creating a pull request, attaching before/after screenshots for UI PRs, monitoring CI and review comments, fixing valid feedback, and repeating until clean. Do not merge unless the user explicitly asks for a merge.
---

# Send It

Use this skill for an end-to-end "get this branch into a clean PR" workflow. By default, stop before merge.

## Workflow

1. Inspect the worktree with `git status --short --branch` and `git diff --stat`. Identify intended PR files and leave unrelated dirty or untracked files alone.

2. Confirm the target branch if ambiguous. Do not infer merge intent from phrases like "send it", "ship it", "get this through", or "open the PR"; treat those as PR creation, CI monitoring, and review-comment handling only. Merge is in scope only when the user explicitly asks to merge, enable auto-merge, or merge after checks pass.

3. Before creating the PR, run independent pre-PR reviews when practical:
   - `codex review --uncommitted`
   - a second `codex review --uncommitted` pass when the change is risky or broad
   - `coderabbit review --agent -t uncommitted` if CodeRabbit CLI is installed and authenticated
   - a second CodeRabbit pass when the first pass found issues or the change is risky

   Treat every finding as a hypothesis. Verify it against the current code, fix valid issues, ignore false positives with a brief rationale, and run targeted checks after fixes.

4. For UI-visible changes, capture before and after screenshots when practical before creating the PR:
   - Use a browser tool to capture comparable views, such as Playwright CLI, [@Browser](plugin://browser@openai-bundled), the Chrome plugin, or the repo's existing visual QA command.
   - Store screenshots as temporary local artifacts only; do not commit them.
   - Upload screenshots to Litterbox with a 72-hour expiry:
     `curl -F "reqtype=fileupload" -F "time=72h" -F "fileToUpload=@screenshot.png" https://litterbox.catbox.moe/resources/internals/api.php`
   - Verify each returned `https://litter.catbox.moe/...` URL is a direct image link with an `image/*` content type before embedding it in the PR description. If verification hangs, retry with HTTP/1.1, for example:
     `curl --http1.1 --max-time 20 -I https://litter.catbox.moe/example.png`
   - If Litterbox upload or verification fails, skip screenshot links and note that the upload failed.

5. Run repo-appropriate validation from `AGENTS.md`, package scripts, and CI config. Commit only intended files, push a topic branch, and create a PR with a concise summary, validation notes, and UI screenshot links when applicable.

6. Monitor the PR until it is clean:
   - Check latest head SHA, merge state, CI/check status, reviews, comments, and review threads.
   - Wait about 15 minutes after PR creation, and about 10-15 minutes after each pushed fix, for CI and review bots.
   - Fix valid comments, resolve fixed, outdated, or false-positive threads, commit, push, and restart this loop from the new head SHA.

7. If and only if the user explicitly requested a merge, merge only when the latest PR head satisfies all gates:
   - merge state is clean
   - required checks are green
   - review bots are success or skipped, not pending
   - all review threads are resolved or outdated
   - no unresolved actionable comments remain
   - local worktree has no unintended tracked changes

   Merge with the verified latest head SHA. Never enable auto-merge or merge manually as part of the default workflow.

8. Report the PR URL, final head SHA, checks passed, review/comment status, merge readiness, UI screenshot links when applicable, and any remaining local untracked files. Include the merge commit SHA only if a user-requested merge was completed.
