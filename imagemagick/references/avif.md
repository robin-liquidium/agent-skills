# AVIF / HEIC notes (ImageMagick IM7)

ImageMagick typically reads/writes AVIF/HEIC via the **libheif** delegate. Availability and exact behavior depend on your local build.

## First: verify support on this machine

```bash
magick -version
magick -list format | sed -n '1,200p'
magick -list format | rg -n "AVIF|HEIC" || true
magick -list delegate | rg -n "heif|heic|avif" || true
```

If `rg` isn’t available, just use `magick -list format` and search manually.

## Useful knobs (documented as HEIC defines)

From the official ImageMagick `defines` documentation, these are recognized defines:

- `-define heic:speed=N` where `N` is `0`–`9` (default `5`)  
  Higher is usually faster/less dense; lower is slower/better.
- `-define heic:chroma=420|422|444` (default `420`)  
  Use `444` for UI/screenshots/text when you can afford size.
- `-define heic:preserve-orientation=true`  
  Preserve original EXIF orientation during decoding and rotate pixels accordingly.
- `-define heic:cicp=...`  
  Set color primaries / transfer / matrix / range (advanced).

Notes:
- These are documented under HEIC, but are commonly relevant when writing AVIF too, because AVIF lives in the same container ecosystem. If a define is ignored, check your build and `magick -list format` output.

## Baseline recipes

### Photos: JPEG/PNG → AVIF

```bash
# Photo baseline: shrink if needed, convert to sRGB, tune quality + speed
magick in.jpg -auto-orient -resize "2048x2048>" -colorspace sRGB -quality 45 -define heic:speed=6 -strip out.avif

# Higher quality
magick in.jpg -auto-orient -resize "2048x2048>" -colorspace sRGB -quality 60 -define heic:speed=5 -strip out.avif
```

### Graphics/screenshots: preserve edges

```bash
# Try higher chroma fidelity (helps colored text/UI)
magick in.png -colorspace sRGB -quality 55 -define heic:chroma=444 -define heic:speed=5 -strip out.avif

# If banding appears, raise quality
magick in.png -colorspace sRGB -quality 70 -define heic:chroma=444 -define heic:speed=4 -strip out.avif
```

### Transparency

AVIF supports alpha; if you see halos, first ensure you’re not forcing a background.

```bash
# Keep alpha (typical)
magick in.png -colorspace sRGB -quality 60 -define heic:speed=5 -strip out.avif

# If you explicitly want to remove alpha for smaller files
magick in.png -background white -alpha remove -alpha off -colorspace sRGB -quality 55 -define heic:speed=6 -strip out.avif
```

## Compare outputs quickly

```bash
# Dimensions + format + colorspace
magick identify -format "%f  %m  %wx%h  %[colorspace]  Q=%Q\n" out.avif

# Side-by-side montage (quick sanity)
magick montage in.jpg out.avif -tile 2x1 -geometry +10+10 compare.jpg
```

## Official docs

- Formats list (AVIF/HEIC availability depends on delegates): https://imagemagick.org/script/formats.php
- Defines (contains `heic:*` knobs): https://imagemagick.org/script/defines.php
- Command-line processing basics: https://imagemagick.org/script/command-line-processing.php
