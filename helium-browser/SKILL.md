---
name: helium-browser
description: "Attach browser tools to a running Helium profile; troubleshoot WebSocket-only CDP discovery, permissions, and failed attachments."
---

# Helium Browser

Helium (https://helium.computer/) is a Chromium-based browser. Agent tooling (playwright-cli, chrome-devtools-mcp) can attach to a running Helium with the user's real profile, but only over WebSocket. For all actual automation commands after attaching, use the `playwright-cli` skill; this skill only covers the Helium-specific connection setup.

## Prerequisite: enable remote debugging

The user must enable remote debugging once in Helium:

1. Open `helium://inspect/#remote-debugging`
2. Enable remote debugging

This persists across restarts. While enabled, Helium writes a `DevToolsActivePort` file into its user-data directory and may show a permission prompt when a new debugging session connects.

## Key fact: WebSocket-only debug server

Helium's remote debugging server disables the HTTP discovery endpoints. All of these return 404:

- `http://127.0.0.1:<port>/json/version`
- `http://127.0.0.1:<port>/json/list`

Consequences:

- `playwright-cli attach --cdp=http://...` does NOT work (Playwright needs `/json/version`).
- `chrome-devtools-mcp --browserUrl http://...` does NOT work.
- Attaching must use the WebSocket endpoint from `DevToolsActivePort`, or a tool that reads that file itself.

## Helium user-data directory

`DevToolsActivePort` lives in Helium's user-data directory:

- macOS: `~/Library/Application Support/net.imput.helium`
- Windows: `%LOCALAPPDATA%\imput\Helium\User Data`
- Linux: `~/.config/helium`

`DevToolsActivePort` contains two lines: the port, then the browser websocket path. Both change on every Helium restart, so always read the file fresh — never hardcode a `ws://` URL into configs or scripts.

## playwright-cli: attach to the running Helium

macOS / Linux:

```bash
PROFILE="$HOME/Library/Application Support/net.imput.helium"  # Linux: "$HOME/.config/helium"
WS="ws://127.0.0.1:$(sed -n 1p "$PROFILE/DevToolsActivePort")$(sed -n 2p "$PROFILE/DevToolsActivePort")"
playwright-cli -s=helium attach --cdp="$WS"
```

Windows (PowerShell):

```powershell
$lines = Get-Content "$env:LOCALAPPDATA\imput\Helium\User Data\DevToolsActivePort"
playwright-cli -s=helium attach --cdp="ws://127.0.0.1:$($lines[0].Trim())$($lines[1].Trim())"
```

Then run all commands against the named session, e.g. `playwright-cli -s=helium snapshot`. When done, detach so Helium keeps running:

```bash
playwright-cli -s=helium detach
```

Notes:

- `playwright-cli open --profile=<helium user-data dir>` cannot reuse the profile while Helium is running (Chromium profile lock). Attach is the only way to control the live browser.
- The `-s=helium` session name is a convention; any name works, but a stable one makes scripts idempotent.

## Connection permissions

New macOS CDP connections prompt “Allow remote debugging?” and time out in about 30 seconds. The user must approve the prompt directly. Read [connection diagnostics](references/connection-diagnostics.md) for prompt troubleshooting, raw WebSocket checks, and a wedged server.


## chrome-devtools-mcp: attach to the running Helium

`chrome-devtools-mcp` v1.2+ reads `DevToolsActivePort` itself when given `--autoConnect --userDataDir`, so a static MCP client config works across restarts (macOS example):

```json
{
  "mcpServers": {
    "chrome-devtools": {
      "command": "npx",
      "args": [
        "-y",
        "chrome-devtools-mcp@latest",
        "--autoConnect",
        "--userDataDir",
        "/Users/<user>/Library/Application Support/net.imput.helium"
      ]
    }
  }
}
```

Notes:

- Helium must be running with remote debugging enabled; autoConnect never launches a browser.
- If it fails with `Could not connect ... DevToolsActivePort`, re-toggle `helium://inspect/#remote-debugging`.
- Avoid `--executablePath` alone: that launches a separate Helium instance with an isolated throwaway profile instead of attaching to the running one.


## Security note

An open remote debugging port gives any local process full control of the browser (cookies, sessions, page content). Keep it bound to localhost (Helium's default) and be mindful of what runs locally while it is enabled.
