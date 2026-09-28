---
name: imagemagick
description: "Edit, convert, resize, composite, inspect, and compress raster images with ImageMagick CLI."
---

# ImageMagick CLI

## Overview

Use ImageMagick’s `magick` CLI to perform deterministic image transforms and batch processing.
Use the quick-start examples for common operations. When option syntax or behavior is unclear, consult the relevant section of `references/imagemagick-cli.md`; load other references only for the task-specific details needed.

Default preferences:
- Prefer `magick ... output.ext` for safe “read → transform → write”.
- Use `magick mogrify` only when you explicitly want in-place edits (or use `-path out/`).
- For compression or file-size optimization tasks, or when the user requests size comparisons, capture file size before and after and report both sizes plus percent reduction.

## Quick Start (most common)

```bash
# Convert formats
magick input.jpg output.png

# Resize (keep aspect ratio)
magick input.jpg -resize 1200x1200 output.jpg

# Strip metadata (EXIF/ICC/comments)
magick input.jpg -strip output.jpg

# Auto-orient based on EXIF, then strip
magick input.jpg -auto-orient -strip output.jpg

# Web-friendly JPEG (quality + strip)
magick input.png -colorspace sRGB -quality 82 -strip output.jpg

# Web-friendly AVIF baseline (if AVIF/HEIC coder available)
magick input.jpg -auto-orient -resize "2048x2048>" -colorspace sRGB -quality 45 -define heic:speed=6 -strip output.avif
```

## Workflow: Choose the Right Tool

- Use `magick ... output.ext` for safe transforms that preserve the input file.
- Use `magick mogrify ... *.ext` for bulk edits; it can overwrite originals.
- Use `magick identify` to inspect images or extract metadata (scriptable output).
- Use `magick compare` for image differences.
- Use `magick montage` for contact sheets / grids.
- Use `magick composite` for overlaying images (watermarks, badges).

## Core Patterns

### Inspect images (before deciding options)

```bash
# Human-readable summary
magick identify input.png

# Verbose (debug what’s actually in the file)
magick identify -verbose input.png

# Scriptable fields
magick identify -format "%m %wx%h %z-bit %[colorspace]\n" input.png
```

### Batch processing safely

Prefer writing to a new directory over in-place edits:

```bash
# Example pattern: loop in your shell (don’t use mogrify unless requested)
mkdir -p out
for f in *.jpg; do
  magick "$f" -auto-orient -resize "1600x1600>" -strip "out/$f"
done
```

If you must do batch edits, consider `mogrify -path`:

```bash
magick mogrify -path out -auto-orient -resize "1600x1600>" -strip *.jpg
```

### Geometry and parentheses

- Quote geometry arguments containing `<` or `>` (shell redirection).
- On POSIX shells, parentheses must be escaped as `\(` and `\)` (Windows differs).

For a geometry cheat sheet and “cover/crop/letterbox” patterns, read `references/geometry.md`.

## References (read when needed)

- `references/imagemagick-cli.md`: comprehensive CLI reference; consult relevant sections when syntax, options, or command behavior need clarification.
- `references/recipes.md`: practical commands for common tasks (web, overlays, montage, batch).
- `references/avif.md`: AVIF/HEIC-specific recipes + tuning knobs.
- `references/geometry.md`: geometry operators and cropping/extent patterns.
- `references/security.md`: policy/resource-limit guidance for untrusted inputs.
- `references/official-docs.md`: canonical docs + Context7 lookup guidance.

## Troubleshooting checklist

- If an option is interpreted as a filename, enable pedantic option parsing:
  `-define registry:option:pedantic=true`
- If output looks wrong, run `magick identify -verbose ...` and confirm colorspace/alpha/orientation.
- If processing is slow or memory-heavy, resize earlier and review resource limits / policy.
