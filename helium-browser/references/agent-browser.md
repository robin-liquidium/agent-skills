# Helium with agent-browser

agent-browser's per-session daemon holds one CDP connection across commands, so the user approves Helium's prompt once. For general usage, load `agent-browser skills get core`.

## Connect once

Tell the user to approve the "Allow remote debugging?" prompt, then:

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

**Start every later command with the same three `export` lines.** Shell state does not persist between agent tool calls, and the daemon fingerprints its connection options: a command with a different or missing `AGENT_BROWSER_CDP` relaunches the daemon, which opens a new connection that Helium prompts for again or rejects with `403`. Use the environment variables only; do not mix in `--cdp` or `--session` flags.

## Tabs

- Open your own tab with `agent-browser tab new <url>`. Do not use `open <url>` right after attaching: it navigates the user's current tab.
- Close only your tabs: `agent-browser tab close <tN>`. agent-browser then re-selects one of the user's tabs, which can make that page reload.

## Finish

`agent-browser close` only disconnects from a CDP-attached browser (it sends `Browser.close` only to browsers it launched itself), so Helium keeps running.

## 403 Forbidden

Helium refused an extra connection, usually because a command ran with different connection settings and relaunched the daemon. Run `agent-browser close`, re-export the identical variables, and connect once more.
