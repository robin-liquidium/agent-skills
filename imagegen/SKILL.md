---
name: imagegen
description: Generate images from prompts and reference images via the Codex ChatGPT subscription (no API key). Use when the task needs AI-created bitmaps and the built-in image_gen tool is unavailable or you need a scriptable CLI with explicit output paths.
---

# Image Generation (Codex OAuth)

Scriptable image generation backed by the user's Codex ChatGPT login. No `OPENAI_API_KEY` needed. Works on macOS and Linux with only Python 3.10+.

## What it uses

- **The user's own Codex login.** The CLI reads the ChatGPT OAuth tokens and account id from `$CODEX_HOME/auth.json` or `~/.codex/auth.json`, and when the access token is near expiry it refreshes it with Codex's OAuth client and writes the new tokens back to that file.
- **A private endpoint.** Requests go to `https://chatgpt.com/backend-api/codex/responses` (the Codex backend, not the public OpenAI API) and count against the user's ChatGPT/Codex limits.
- Tell the user this before first use if they have not used the skill before.

## Prerequisites

- Run `codex login` once and choose ChatGPT auth. The CLI reads `$CODEX_HOME/auth.json` or `~/.codex/auth.json`.
- Check state with `scripts/imagegen auth-status`.

## Quick start

Generate an image:

```bash
<skill-path>/scripts/imagegen generate \
  --prompt "A cinematic alpine lake at sunrise, photorealistic" \
  --out output/lake.png
```

Generate with reference images (max 5, used for style/composition/subject guidance):

```bash
<skill-path>/scripts/imagegen generate \
  --prompt "Apply the style of these references to a futuristic city" \
  --reference refs/style-a.png \
  --reference refs/style-b.png \
  --out output/city.png
```

## Parameters

- `--prompt` or `--prompt-file`: required.
- `--reference`: repeatable, max 5. Local image paths only (PNG/JPEG/WebP/GIF).
- `--out`: required. Output path (`.png` appended if missing).
- `--quality`: `low` | `medium` | `high` | `auto` (default `auto`).
- `--size`: `auto` or `WIDTHxHEIGHT`. Must satisfy gpt-image-2 constraints (multiples of 16, max edge 3840, ratio <= 3:1, pixels between 655,360 and 8,294,400).
- `--force`: overwrite existing output (default: auto-version `-v2`, `-v3`, ...).
- `--timeout`: seconds (default 300).
- `--dry-run`: print the planned request without calling the backend.
- `--base-url` / `IMAGEGEN_BASE_URL`: the bearer token is sent only to `https://chatgpt.com`. Any other host is refused unless `--allow-custom-base-url` is also passed, and then it must be https (or http on localhost). Redirects are never followed.

## Output

On success the CLI prints JSON with the saved path, dimensions, and metadata. Always read/inspect the generated file to verify quality before using it in a project.

Output path conventions for the caller:
- User-named destination wins.
- Project-bound assets go directly into the consuming project's asset folder.
- Drafts/previews with no specified destination: use the calling skill's own `outputs/` folder if it has one, otherwise a project-local `output/imagegen/` directory.

## Notes

- This uses the private Codex backend (`/backend-api/codex/responses`) with the hosted `image_generation` tool. It is not a public OpenAI API and can change without notice.
- Generation consumes ChatGPT/Codex usage limits (roughly 3-5x a normal turn).
- `gpt-image-2` does not support native transparency; prompt for a flat chroma-key background and remove it locally if needed.
- The default orchestration model is `gpt-5.5`; override with `--model` or `IMAGEGEN_MODEL`.
