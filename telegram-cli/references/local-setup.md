## Local setup

Prefer the skill-local script and cached virtualenv over any global CLI install.
Prefer saved Telegram config over shell-exported environment variables once setup is complete.
Treat the virtualenv under `~/.cache/telegram-cli/venv` as generated local state, not part of the skill itself.
If the installer drops skill-local dotfiles, the bootstrap script recreates `.gitignore` automatically.

Bootstrap the local environment:

```bash
<skill-path>/scripts/bootstrap_venv.sh
```

After bootstrap, use:

```bash
<skill-path>/scripts/telegram-cli
```

`scripts/telegram-readonly` remains as a backwards-compatible alias for older workflows.

If the cached virtualenv is missing later, just run the bootstrap script again.

Primary config path:

```bash
~/.config/telegram-cli/config.json
```

On a Linux host with `~/.config/credentials.encrypted/telegram-mcp-tunnel.env.cred`, the launcher can instead load Telegram credentials from that systemd encrypted credential through the host's `with-systemd-env-credential` helper. The plaintext config is not required in that setup.

Recommended one-time setup:

1. Make sure `api_id` and `api_hash` are available.
2. Save them with:

```bash
<skill-path>/scripts/setup-api-key.sh
```

3. Run:

```bash
<skill-path>/scripts/telegram-cli auth
```

After successful login, the config file stores `api_id`, `api_hash`, and the Telegram session string so future reads do not need exported shell variables.
