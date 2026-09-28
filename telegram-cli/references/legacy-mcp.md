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
