# Shared source installation

When this repository lives in a Syncthing-shared `~/skills/`, synchronize working
files while excluding `.git`, credentials, dependencies, caches and generated
state. Commit/branch/index metadata remains host-local.

Maintained authored skills are relative source links from `~/skills/global/`
into this repository. The native `~/.agents/skills` directory aliases the shared
library; the global npx lock file aliases a shared registry. Other agent tools
receive individual links while retaining their local bundled/plugin content.

Only verified upstream downloads belong in the npx update registry. Keep
customized/authored source skills out of it to avoid upstream replacement of
local edits. Use agent-secrets for keys and runtime injection; do not synchronize
whole agent configuration folders. Use global scope explicitly, wait for sync
and run fleet mutations on one machine at a time.

For the deployed layout, ownership inventory, commands and migration/installation
instructions, read the adjacent `~/skills/README.md` and
`~/workspace/agent-setup/README.md`. These are optional environment documents,
not dependencies for normal `npx skills` users of this repository.
