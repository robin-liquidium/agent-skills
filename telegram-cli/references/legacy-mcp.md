# Legacy MCP maintenance

These instructions are retained only for maintaining existing compatibility code or an explicitly requested MCP setup. Use the CLI for normal tasks.

## ChatGPT/Codex MCP

The MCP server exposes typed read tools for dialogs, messages, search, and unread lists. Telegram writes use a mandatory two-step flow: a `telegram_prepare_*` tool returns the resolved dry-run preview and a short-lived one-time token; `telegram_execute_prepared_action` can consume that frozen token only after the user explicitly approves the exact preview in a new message.

The MCP intentionally does not expose arbitrary shell arguments, local text-file paths, interactive auth, edit/delete operations, or background watchers. Run interactive Telegram authentication through the local CLI before starting the MCP.

Install and start locally:

```bash
cd <skill-path>/mcp
npm install
node server.mjs
```

The durable launcher is `scripts/telegram-mcp`.

## Optional remote tunnel (legacy, off by default)

`scripts/finish-telegram-mcp-tunnel` and `mcp/telegram-mcp-tunnel.service` are optional legacy pieces. Never run them as part of normal setup. Together they:

- expose the local MCP server (all read tools plus approval-gated writes on the user's personal Telegram account) to ChatGPT through OpenAI's `tunnel-client`, which this skill does not ship;
- store a runtime API key in `~/.config/openai-tunnel-telegram/runtime.env` (mode 0600, read by systemd as data);
- enable an always-on systemd user service with `Restart=always`.

The helper refuses to run without `--enable-always-on-tunnel` and asks for a final y/N confirmation. Run it only after the user explicitly asks for remote ChatGPT access. Remove it with:

```bash
systemctl --user disable --now telegram-mcp-tunnel.service
rm -f ~/.config/openai-tunnel-telegram/runtime.env
```
