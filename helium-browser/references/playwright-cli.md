# Helium with playwright-cli

**Known issue:** with playwright-cli 0.1.19, `attach` to Helium connects and the user approves the prompt, but the attach never completes and times out. Use this only with a newer playwright-cli, and if the attach has not finished within a minute after the user approved, stop and tell the user instead of retrying.

`playwright-cli attach` starts a session daemon that holds one CDP connection; every later `-s=helium` command reuses it, so the user approves Helium's prompt once.

## Connect once

Tell the user to approve the "Allow remote debugging?" prompt, then:

```bash
PROFILE="$HOME/Library/Application Support/net.imput.helium"   # Linux: "$HOME/.config/helium"
WS="ws://127.0.0.1:$(sed -n 1p "$PROFILE/DevToolsActivePort")$(sed -n 2p "$PROFILE/DevToolsActivePort")"
PLAYWRIGHT_MCP_CDP_TIMEOUT=120000 playwright-cli attach --cdp="$WS" --session=helium
```

Windows (PowerShell):

```powershell
$lines = Get-Content "$env:LOCALAPPDATA\imput\Helium\User Data\DevToolsActivePort"
$env:PLAYWRIGHT_MCP_CDP_TIMEOUT = "120000"
playwright-cli attach --cdp="ws://127.0.0.1:$($lines[0].Trim())$($lines[1].Trim())" --session=helium
```

The default connect timeout is 30 seconds, about as long as Helium keeps the prompt open, so a slow click fails the attach. `PLAYWRIGHT_MCP_CDP_TIMEOUT` raises it. A timeout whose log shows `<ws connected>` means the socket opened but the prompt was not approved.

Run `attach` once per task. Every later command uses the session and opens no new connection:

```bash
playwright-cli -s=helium tab-list
```

## Tabs

- Open your own tab with `playwright-cli -s=helium tab-new <url>`; `goto` would navigate the user's current tab.
- Close only your tabs with `tab-close <index>`, checking the index with `tab-list` first.

## Finish

`playwright-cli -s=helium detach` disconnects and leaves Helium running. Never use `close` on this session.
