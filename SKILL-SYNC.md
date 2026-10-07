# Shared source installation

When this repository is inside a Syncthing-shared `~/skills/` folder, keep the
working tree synchronized and `.git`, credentials, dependencies, caches, and
generated state excluded. Git commits/branches remain local; push normally.

Use relative per-skill links from a shared installed library (`~/skills/global`)
to this repository, then expose that library in each agent's documented discovery
folder. The same link text works with `/Users/<user>` and `/home/<user>` roots.
Keep agent tool folders real so bundled, plugin, and cloud-managed content can
remain host-local. Do not synchronize whole agent configuration directories.

For the deployed setup, installation, automatic link reconciliation, retirement,
and conflict handling, read the adjacent `~/skills/README.md` and
`~/workspace/agent-setup/README.md`. These are optional environment setup documents,
not dependencies for users installing this repository normally with `npx skills`.
Edit authored skills here, not a separately installed copy.
