---
name: helium-browser
description: "Drive the user's running Helium browser (real tabs, logins) over one approved CDP connection with agent-browser, playwright-cli, or chrome-devtools-mcp."
---

# Helium Browser

Helium (https://helium.computer/) is a Chromium-based browser. Attach over CDP to control the user's live Helium with its real tabs, cookies, and logins.

**Every new CDP connection makes Helium show an "Allow remote debugging?" prompt that the user must click.** Use exactly one connection per task, held open by the tool's daemon or server. Tell the user right before connecting so they can approve it. Never retry a failed connection in a loop or open extra "test" connections; each one is another prompt.

## Pick a tool

Use the first one available, then read only its reference:

1. **agent-browser** (`command -v agent-browser`): [references/agent-browser.md](references/agent-browser.md)
2. **chrome-devtools-mcp** (an MCP server configured for Helium): [references/chrome-devtools-mcp.md](references/chrome-devtools-mcp.md)
3. **playwright-cli** (`command -v playwright-cli`), only after checking its known issue: [references/playwright-cli.md](references/playwright-cli.md)

## Prerequisite

The user enables remote debugging once at `helium://inspect/#remote-debugging`. It persists across restarts. While enabled, Helium writes `DevToolsActivePort` into its user-data directory:

- macOS: `~/Library/Application Support/net.imput.helium`
- Linux: `~/.config/helium`
- Windows: `%LOCALAPPDATA%\imput\Helium\User Data`

The file holds two lines: the port, then the browser WebSocket path. Both change whenever Helium restarts, so read the file fresh and never hardcode the URL:

```bash
PROFILE="$HOME/Library/Application Support/net.imput.helium"   # Linux: "$HOME/.config/helium"
WS="ws://127.0.0.1:$(sed -n 1p "$PROFILE/DevToolsActivePort")$(sed -n 2p "$PROFILE/DevToolsActivePort")"
```

The debug server is WebSocket-only. Its HTTP discovery endpoints (`/json/version`, `/json/list`) return 404, so an `http://127.0.0.1:<port>` CDP URL never works. Launching a tool with Helium's profile directory also fails while Helium runs (Chromium profile lock); attaching is the only way.

## Working in the user's browser

- Confirm you attached to the right browser: the tab list must show the user's real tabs.
- Open your own tabs instead of navigating the user's tabs, and close only tabs you opened.
- Treat signed-in sessions as the user's own; act on accounts only as far as the task requires.
- Finish by disconnecting as the tool's reference describes. Disconnecting never quits Helium.

## Troubleshooting

- **Timeout while connecting:** the prompt was not approved in time. Ask the user to dismiss any stale prompts and to approve the next one, then connect once more.
- **`ECONNREFUSED`:** Helium is not running, is still starting, or restarted with a new port. Re-read `DevToolsActivePort`.
- **No prompt appears and connecting hangs:** toggle remote debugging off and on at `helium://inspect/#remote-debugging`, or quit and relaunch Helium.

While remote debugging is enabled, any local process can fully control the browser through it. It is bound to localhost; the user can turn it off when not needed.
