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

### Optional: systemd encrypted credential (Linux, opt-in)

By default the launcher only uses `config.json` or exported `TELEGRAM_*` variables. It loads credentials from a systemd encrypted credential only when the user sets both of these explicitly (for example in their shell profile):

```bash
export TELEGRAM_CLI_ENCRYPTED_CREDENTIAL="$HOME/.config/credentials.encrypted/telegram-mcp-tunnel.env.cred"
# Optional; this is the default helper path:
export TELEGRAM_CLI_CREDENTIAL_LOADER="$HOME/.local/libexec/with-systemd-env-credential"
```

Services and timers don't read shell profiles, so the same opt-in can also be a file: put the credential path on the first line of `~/.config/telegram-cli/encrypted-credential`:

```bash
mkdir -p ~/.config/telegram-cli && printf '%s\n' "$HOME/.config/credentials.encrypted/telegram-mcp-tunnel.env.cred" > ~/.config/telegram-cli/encrypted-credential
```

The helper is not part of this skill: it must already exist on the host, take a credential name and a command, and export the credential's env lines before running the command. When enabled and no plaintext credentials are present, the launcher re-runs itself in a transient `systemd-run --user` unit with `LoadCredentialEncrypted=`, so the plaintext config is not required. Unset the variable or delete the file to turn this off.

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
