# UI screenshots

For UI-visible changes, capture "after" screenshots of the changed views when trivial, after the [review loop](review-rounds.md) has converged and validation is green. Add before/after comparisons only when cheap to capture.

- Use a browser tool to capture comparable views, such as Playwright CLI, [@Browser](plugin://browser@openai-bundled), the Chrome plugin, or the repo's existing visual QA command.
- Review every image for personal data, credentials, private content, and session details before sharing it. Omit sensitive screenshots and skip gated or difficult captures.
- Keep screenshots as temporary local artifacts; do not commit them. For images safe to share with PR readers, use `gh pr create --attach './screenshot.png#Description of the changed view'` when creating the PR. The CLI adds the uploaded image to the PR body. If attachment upload fails, check whether the PR was created before retrying.
- Any UI-visible change made after capture invalidates the screenshots. Recapture and replace stale PR images before merge, or remove them from the PR.
