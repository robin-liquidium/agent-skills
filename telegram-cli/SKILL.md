---
name: telegram-cli
description: "Read and search personal Telegram chats through Telethon; send, edit own messages, mark read, archive, or mute with explicit dry-run/execute approval."
allowed-tools: Bash(./scripts/telegram-readonly:*), Bash(./scripts/telegram-cli:*)
---

# Telegram CLI

Use the local MTProto/Telethon script for the user's personal account; Telegram Bot API cannot read it.

## Quick rules

- Prefer reads first, then propose the action queue.
- Write commands are dry-run by default and require `--execute`.
- Never run any write command with `--execute` unless the user explicitly approved that specific action or batch first.
- For `send`, present the draft first; `send --execute` requires approval of the final recipient and text.
- For `edit`, show the new text first; `edit --execute` requires approval of the new text. Only the account's own messages can be edited, and Telegram marks them as edited.
- Mark-read/archive/mute are still Telegram writes; use them only after the user has approved the batch/action.
- Do not add delete/bulk export/background automation unless the user explicitly asks.
- Treat the Telethon session like a high-privilege secret.
- Assume unread preservation is best-effort until tested on a real chat.

## Setup

Use the skill-local launcher and cached virtualenv. Read [local setup](references/local-setup.md) for bootstrap, authentication, config, or encrypted credentials, and [setup and safety](references/setup-and-safety.md) for auth/unread-state behavior. `scripts/telegram-readonly` remains a compatibility alias.

Non-auth CLI operations have a 60-second deadline. A timed-out `--execute` write has an unknown outcome; verify it in Telegram before any retry. Interactive `auth` has no routine operation deadline.


## Commands

### Show built-in help

```bash
<skill-path>/scripts/telegram-cli help
```

### Authenticate once

```bash
<skill-path>/scripts/setup-api-key.sh
<skill-path>/scripts/telegram-cli auth
```

### List chats

`dialogs --query` does token-based matching across `name`, `username`, and `title`, so queries like `petros skynet` work even when the exact full string is not present as one substring.

```bash
<skill-path>/scripts/telegram-cli dialogs --limit 50
```

### Read recent messages

```bash
<skill-path>/scripts/telegram-cli messages --chat '@username' --limit 50 --reverse
```

### Search messages

```bash
<skill-path>/scripts/telegram-cli search 'invoice' --limit 50
```

Restrict search to one chat:

```bash
<skill-path>/scripts/telegram-cli search 'deadline' --chat '@username' --limit 50
```

### List recent unread chats

Default behavior is opinionated: exclude **muted** and **archived** chats.

```bash
<skill-path>/scripts/telegram-cli unread-dialogs --limit 10
```

Include muted and/or archived when needed:

```bash
<skill-path>/scripts/telegram-cli unread-dialogs --limit 10 --include-muted --include-archived
```

### List recent unread DMs only

```bash
<skill-path>/scripts/telegram-cli unread-dms --limit 10
```

### Send a message

Draft first in chat, ask the user to confirm, then dry-run:

```bash
<skill-path>/scripts/telegram-cli send --chat '@username' --text 'Thanks, will check.'
```

Send only after the user approves final text and recipient:

```bash
<skill-path>/scripts/telegram-cli send --chat '@username' --text 'Thanks, will check.' --execute
```

### Edit a sent message

Fix one of your own sent messages in place instead of sending a correction. The dry-run shows the current and new text:

```bash
<skill-path>/scripts/telegram-cli edit --chat '@username' --id 12345 --text 'Thanks, will check today.'
```

Edit only after the user approves the new text:

```bash
<skill-path>/scripts/telegram-cli edit --chat '@username' --id 12345 --text 'Thanks, will check today.' --execute
```

### Mark read

```bash
<skill-path>/scripts/telegram-cli mark-read --chat 123456789
<skill-path>/scripts/telegram-cli mark-read --chat 123456789 --execute
```

### Archive or unarchive

```bash
<skill-path>/scripts/telegram-cli archive --chat 123456789
<skill-path>/scripts/telegram-cli archive --chat 123456789 --execute
<skill-path>/scripts/telegram-cli archive --chat 123456789 --unarchive --execute
```

### Mute or unmute

```bash
<skill-path>/scripts/telegram-cli mute --chat 123456789 --hours 8
<skill-path>/scripts/telegram-cli mute --chat 123456789 --hours 8 --execute
<skill-path>/scripts/telegram-cli mute --chat 123456789 --unmute --execute
```

## Workflow

1. Confirm setup, then read only the chats/messages needed.
2. For writes, obtain approval, run the dry-run, verify the JSON target/action, then use `--execute`.

## Expected outputs

The wrapper returns JSON. Parse it instead of relying on fragile text scraping.

Dialog objects include:
- `is_user`
- `is_group`
- `is_channel`
- `is_bot`
- `archived`
- `muted`
- unread counters

## Files

- Launcher: `scripts/telegram-cli`
- Launcher: `scripts/telegram-readonly`
- Python implementation: `scripts/telegram_cli.py`
- Local bootstrap: `scripts/bootstrap_venv.sh`
- Credential setup helper: `scripts/setup-api-key.sh`
- Setup notes: `references/setup-and-safety.md`
- Config storage: `~/.config/telegram-cli/config.json`, or the host's systemd encrypted credential when configured
- `.env` is optional fallback only; it is not the preferred long-term setup.
- `~/.cache/telegram-cli/venv` is generated local state and can be recreated with `<skill-path>/scripts/bootstrap_venv.sh`.
- ChatGPT/Codex MCP server: `mcp/server.mjs`

## Legacy compatibility

Use the CLI for normal tasks. MCP compatibility code remains for existing consumers; only consult [legacy MCP maintenance](references/legacy-mcp.md) when explicitly maintaining that code. Do not restart the retired tunnel as part of ordinary setup.

## When to stop and ask

Stop and ask before:
- sending or editing a Telegram message
- enabling any background watcher/daemon
- broad exporting of large chat histories
- changing how secrets/session storage works

## Docs

Fast lookup:
- Telethon client reference: `https://docs.telethon.dev/en/stable/quick-references/client-reference.html`
- Telethon TelegramClient API: `https://docs.telethon.dev/en/stable/modules/client.html`
- Telegram folders/archive API: `https://core.telegram.org/api/folders`
- Telegram notification settings API: `https://core.telegram.org/method/account.updateNotifySettings`
