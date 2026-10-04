# Helium with chrome-devtools-mcp

chrome-devtools-mcp reaches Helium only when its server is started with `--autoConnect --userDataDir <Helium user-data dir>`. It then reads `DevToolsActivePort` itself, so the config survives Helium restarts. A server without these flags launches its own separate Chrome instead.

## Configure a Helium server

Register a dedicated server so a plain `chrome-devtools` server keeps working for other tasks (macOS example; use the Linux or Windows user-data directory there):

```bash
claude mcp add --scope user helium-devtools -- npx -y chrome-devtools-mcp@latest --autoConnect --userDataDir "$HOME/Library/Application Support/net.imput.helium"
```

Other MCP clients take the same command and arguments in their server config. Do not pass `--executablePath` alone: it launches a separate Helium with a throwaway profile. New MCP servers load only in a new session.

## Use

- The server opens its connection on the first tool call, which triggers the one prompt. Tell the user before that call.
- Call `list_pages` first. If it shows only `about:blank` instead of the user's tabs, the server launched its own browser; stop and fix the config.
- Open your own tab with `new_page` (`background: true` keeps the user's tab in front) and close only your pages with `close_page`.
- The connection lives as long as the MCP server, so later calls need no further prompts.

If it fails with `Could not connect ... DevToolsActivePort`, toggle remote debugging off and on at `helium://inspect/#remote-debugging`.
