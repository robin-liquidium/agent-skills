# Official docs + Context7 lookup

This skill is intentionally *curated*, not exhaustive. When you need an option/define that isn’t in our recipes, use the official docs and Context7.

## Context7

- Preferred Context7 library ID for ImageMagick CLI docs: `/websites/imagemagick_script`

Use it to search for:
- command-line options (`-resize`, `-extent`, `-strip`, `-quality`, `-colorspace`, `-alpha`, `-define ...`)
- format-specific defines (e.g. `heic:*`, `webp:*`, `png:*`, `jpeg:*`)
- CLI structure (parentheses/stacks, geometry edge cases)

## Canonical ImageMagick docs

- `magick` tool overview: https://imagemagick.org/script/magick.php
- Command-line tools index: https://imagemagick.org/script/command-line-tools.php
- Command-line processing anatomy (geometry/stacks): https://imagemagick.org/script/command-line-processing.php
- Command-line options (huge reference): https://imagemagick.org/script/command-line-options.php
- Defines (format- and feature-specific knobs): https://imagemagick.org/script/defines.php
- Formats (what’s supported + delegate notes): https://imagemagick.org/script/formats.php
- Security policy (policy.xml, limits, delegates): https://imagemagick.org/script/security-policy.php

## Practical examples (external but widely used)

- ImageMagick Usage guide (many recipes): https://usage.imagemagick.org/

## Local discovery commands (most reliable)

```bash
magick -version
magick -list format
magick -list delegate
magick identify -list policy
```
