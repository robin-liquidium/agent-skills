---
name: twitterapi-io
description: "Retrieve and paginate X/Twitter profiles, tweets, replies, quotes, threads, mentions, and searches through twitterapi.io."
allowed-tools: Bash(./scripts/twitterapi-io:*)
---

# twitterapi-io

Use the local skill script for read-only twitterapi.io access.

The config can hold an `agent-secrets` reference instead of a plaintext key. The CLI resolves the reference at runtime, and setup/auth rotates an existing reference in the vault. The optional Linux launcher can use a systemd encrypted credential. Never paste real keys into command arguments.

## Quick rules

- Use this skill only for reads.
- Do not improvise posting/like/reply/delete flows.
- Prefer compact JSON output by default.
- Use `--raw` only when you actually need full API objects.
- Prefer the official docs links in `references/links.md` when validating endpoint behavior.

## Local setup

Prefer the skill-local script over any global CLI install.
Prefer a saved config file over shell-exported environment variables.

No package install is required for the local script. Use:

```bash
<skill-path>/scripts/twitterapi-io
```

Primary config path:

```bash
~/.config/twitterapi-io/config.json
```

On a Linux host with `~/.config/credentials.encrypted/twitterapi-mcp-tunnel.env.cred`, the launcher can load the key through a `with-systemd-env-credential` helper. This optional host setup does not require a plaintext config.

Recommended one-time setup:

```bash
<skill-path>/scripts/setup-api-key.sh
```

That saves the key to the config file, or rotates the existing vault entry if the config contains an `api_key` object such as `{"$agent_secret":"tools/twitterapi-io/api-key"}`. The local `secrets` CLI must be available for vault-backed config.

## Commands

### Show built-in help

```bash
<skill-path>/scripts/twitterapi-io help
```

### Alternative credentials

`TWITTERAPI_IO_KEY` overrides saved config. The `auth --api-key` command is also available, but its argument can appear in shell history and process listings; prefer the interactive setup script.

### Fetch one tweet

```bash
<skill-path>/scripts/twitterapi-io tweet --url 'https://x.com/jack/status/20'
```

or:

```bash
<skill-path>/scripts/twitterapi-io tweet --id 20
```

### Fetch one user

```bash
<skill-path>/scripts/twitterapi-io user --username OpenAI
```

### Fetch recent tweets for a user

```bash
<skill-path>/scripts/twitterapi-io user-tweets --username OpenAI --limit 10
```

Include replies:

```bash
<skill-path>/scripts/twitterapi-io user-tweets --username OpenAI --limit 10 --include-replies
```

### Fetch replies to a tweet

```bash
<skill-path>/scripts/twitterapi-io replies --url 'https://x.com/jack/status/20' --limit 20
```

Optional unix-time filters:

```bash
<skill-path>/scripts/twitterapi-io replies --id 20 --since-time 1741219200 --until-time 1741305600 --limit 20
```

### Fetch quote tweets

```bash
<skill-path>/scripts/twitterapi-io quotes --id 20 --limit 20
```

### Fetch thread context

```bash
<skill-path>/scripts/twitterapi-io thread-context --id 20 --limit 40
```

### Fetch mentions for a user

```bash
<skill-path>/scripts/twitterapi-io mentions --username OpenAI --limit 20
```

### Advanced search

```bash
<skill-path>/scripts/twitterapi-io search --query 'AI agents -filter:replies' --from-user OpenAI --within-time 24h --max-tweets 50
```

Use `Top` results when needed:

```bash
<skill-path>/scripts/twitterapi-io search --query 'AI agents' --queryType Top --max-pages 2
```

Use explicit unix-time operators when needed:

```bash
<skill-path>/scripts/twitterapi-io search --query '$BTC' --since-time 1741219200 --until-time 1741305600 --max-tweets 50
```

## Workflow

1. Read `references/links.md` if you need the underlying official twitterapi.io docs links.
2. Use the local skill script.
3. Ensure the API key exists in `~/.config/twitterapi-io/config.json` or via env.
4. Use `tweet`, `user`, `user-tweets`, `replies`, `quotes`, `thread-context`, `mentions`, or `search` as needed.
5. Keep reads narrow and intentional.

## Expected outputs

The CLI returns JSON. Parse it instead of scraping human text.

## Files

- Package repo: `https://github.com/robin-liquidium/twitterapi-io-cli`
- Launcher: `scripts/twitterapi-io`
- Python implementation: `scripts/twitterapi_io.py`
- Credential setup helper: `scripts/setup-api-key.sh`
- Official docs links: `references/links.md`
- Config storage: `~/.config/twitterapi-io/config.json`, or the host's systemd encrypted credential when configured
- `.env` is optional fallback only; it is not the preferred long-term setup.

## When to stop and ask

Stop and ask before:
- adding write/posting capabilities
- adding login-cookie flows
- adding broad/high-cost scraping defaults
- changing how API key storage works
