---
name: helium-browser
description: "Drive the user's running Helium browser (real tabs, logins) with agent-browser over one approved CDP connection; setup, the one-prompt rule, and troubleshooting."
---

# Helium Browser

Helium (https://helium.computer/) is a Chromium-based browser. Use **agent-browser** attached over CDP to control the user's live Helium with its real tabs, cookies, and logins. For agent-browser usage itself, load `agent-browser skills get core`; this skill covers only the Helium-specific connection.

**Every new CDP connection makes Helium show an "Allow remote debugging?" prompt that the user must click.** The whole task must therefore use exactly one connection. agent-browser's per-session daemon holds that connection across commands, so the user approves once.

## Prerequisite

The user enables remote debugging once at `helium://inspect/#remote-debugging`. It persists across restarts. While enabled, Helium writes `DevToolsActivePort` into its user-data directory:

- macOS: `~/Library/Application Support/net.imput.helium`
- Linux: `~/.config/helium`
- Windows: `%LOCALAPPDATA%\imput\Helium\User Data`

The file holds two lines: the port, then the browser WebSocket path. Both change whenever Helium restarts, so read the file fresh; never hardcode the URL.

## Connect once

Tell the user right before the first command: "Approve the 'Allow remote debugging?' prompt in Helium now."

```bash
PROFILE="$HOME/Library/Application Support/net.imput.helium"   # Linux: "$HOME/.config/helium"
export AGENT_BROWSER_CDP="ws://127.0.0.1:$(sed -n 1p "$PROFILE/DevToolsActivePort")$(sed -n 2p "$PROFILE/DevToolsActivePort")"
export AGENT_BROWSER_SESSION=helium
export AGENT_BROWSER_DEFAULT_TIMEOUT=120000   # leave the user time to approve
agent-browser tab list                         # connects; the only prompt of the task
```

Windows (PowerShell):

```powershell
$lines = Get-Content "$env:LOCALAPPDATA\imput\Helium\User Data\DevToolsActivePort"
$env:AGENT_BROWSER_CDP = "ws://127.0.0.1:$($lines[0].Trim())$($lines[1].Trim())"
$env:AGENT_BROWSER_SESSION = "helium"
$env:AGENT_BROWSER_DEFAULT_TIMEOUT = "120000"
agent-browser tab list
```

`tab list` should show the user's real tabs. If it shows only a blank tab, you are not in their Helium.

**Keep the connection settings identical for every later command.** The daemon fingerprints its connection options; a command with a different or missing `AGENT_BROWSER_CDP` relaunches the daemon, which opens a new connection that Helium prompts for again or rejects with `403`. Shell state does not persist between agent tool calls, so put the same three `export` lines (re-reading the same file) at the start of every command. Use the environment variables rather than mixing them with `--cdp` or `--session` flags.

Never retry a failed connection in a loop and never open extra "test" connections; each one is another prompt. On a failure, stop, follow Troubleshooting, and retry at most once after the user confirms.

## Working in the user's browser

- Open your own tabs with `agent-browser tab new <url>`. Do not use `open <url>` right after attaching: it navigates the user's current tab.
- Close only tabs you opened: `agent-browser tab close <tN>`. Afterwards agent-browser re-selects one of the user's tabs, which can make that page reload.
- Treat signed-in sessions as the user's own; act on accounts only as far as the task requires.

When done, run `agent-browser close`. For a CDP-attached browser this only disconnects, and Helium keeps running.

## Troubleshooting

- **Timeout on the first command:** the prompt was not approved in time. Ask the user to dismiss any stale prompts and to approve the next one, then run the first command once more.
- **`403 Forbidden`:** Helium refused an extra connection. Usually a later command ran with different connection settings and relaunched the daemon. Run `agent-browser close`, re-export the identical variables, and connect once more.
- **`ECONNREFUSED`:** Helium is not running, is still starting, or restarted with a new port. Re-read `DevToolsActivePort` and connect again.
- **No prompt appears and connecting hangs:** toggle remote debugging off and on at `helium://inspect/#remote-debugging`, or quit and relaunch Helium.

## Other tools

Helium's debug server is WebSocket-only: its HTTP discovery endpoints (`/json/version`, `/json/list`) return 404, so any tool that needs an `http://` CDP URL cannot attach.

- **playwright-cli** `attach --cdp=ws://…` works, but its 30-second attach timeout races the approval prompt, and each retry is another prompt. Prefer agent-browser.
- **chrome-devtools-mcp** reaches Helium only when configured with `--autoConnect --userDataDir <Helium user-data dir>`. Otherwise it silently launches its own Chrome. Check that `list_pages` shows the user's tabs before acting.
- Launching any tool with Helium's profile directory (`--profile`) fails while Helium runs because of the Chromium profile lock. Attaching is the only way to drive the live browser.

## Security note

While remote debugging is enabled, any local process can connect to it and fully control the browser (cookies, sessions, page content). It stays bound to localhost by default; the user can turn it off at `helium://inspect/#remote-debugging` when not needed.
