# ImageMagick CLI recipes (IM7)

Keep this file for practical, copy/paste-friendly command patterns.

Principles:
- Prefer `magick` (write to a new output) unless the user explicitly requests in-place edits.
- For batch work, prefer writing to `out/` (or `mogrify -path out`).
- Always sanity-check formats and coders available on this machine:

```bash
magick -version
magick -list format
magick -list delegate
```

## Web optimization baselines

### JPEG (photographic)

```bash
# Good default: orient → shrink-if-needed → convert to sRGB → quality → strip
magick in.jpg -auto-orient -resize "2048x2048>" -colorspace sRGB -quality 82 -strip out.jpg

# If input is PNG but you want JPEG (no alpha) and avoid dark edges:
magick in.png -background white -alpha remove -alpha off -colorspace sRGB -quality 82 -strip out.jpg
```

### PNG (graphics / screenshots)

```bash
# Safe lossless baseline
magick in.png -strip out.png

# Quantize (good for flat graphics; tune colors)
magick in.png -colors 256 -strip out.png
```

### AVIF (see `avif.md` for more)

```bash
# Photo baseline (tune quality + speed)
magick in.jpg -auto-orient -resize "2048x2048>" -colorspace sRGB -quality 45 -define heic:speed=6 -strip out.avif

# Graphics baseline (try higher chroma fidelity)
magick in.png -colorspace sRGB -quality 55 -define heic:chroma=444 -define heic:speed=5 -strip out.avif
```

## Conversions

```bash
# JPEG -> PNG
magick in.jpg out.png

# HEIC -> JPEG (if coder available)
magick in.heic -auto-orient -colorspace sRGB -quality 85 -strip out.jpg

# Convert a whole folder to AVIF (safe, writes to out/)
mkdir -p out
for f in *.jpg; do
  magick "$f" -auto-orient -resize "2048x2048>" -colorspace sRGB -quality 45 -define heic:speed=6 -strip "out/${f%.*}.avif"
done
```

## Resize / thumbnails

```bash
# Fit within box, preserve aspect ratio
magick in.jpg -resize 1200x1200 out.jpg

# Force exact size (may distort)
magick in.jpg -resize 300x300\! out.jpg

# Only shrink if larger
magick in.jpg -resize "1600x1600>" out.jpg

# Cover/crop to exact aspect using ^ then extent
magick in.jpg -resize 1200x1200^ -gravity center -extent 1200x1200 out.jpg

# Add padding / letterbox to exact size
magick in.jpg -resize 1200x1200 -background black -gravity center -extent 1200x1200 out.jpg

# Thumbnails (often faster/appropriate)
magick in.jpg -thumbnail 400x400 -strip out.jpg
```

## Crop

```bash
# Crop WxH+X+Y
magick in.jpg -crop 800x600+100+50 +repage out.jpg
```

## Rotation / orientation

```bash
# Auto-orient per EXIF
magick in.jpg -auto-orient out.jpg

# Rotate 90 degrees clockwise
magick in.jpg -rotate 90 out.jpg
```

## Strip metadata

```bash
# Remove profiles/comments and common metadata chunks
magick in.jpg -strip out.jpg

# If you need to neutralize orientation metadata explicitly
magick in.jpg -orient Undefined -strip out.jpg
```

## Color / colorspace

```bash
# Ensure output in sRGB (common for web)
magick in.png -colorspace sRGB out.png

# Grayscale (Rec709 luminance)
magick in.jpg -intensity Rec709Luminance -colorspace gray out.jpg
```

## WebP

```bash
# Lossy WebP
magick in.jpg -quality 80 -strip out.webp

# Lossless WebP (may be larger)
magick in.png -define webp:lossless=true -strip out.webp
```

## Watermark / overlay

```bash
# Place logo bottom-right with some padding
magick base.jpg \( logo.png -resize 15% \) -gravity southeast -geometry +24+24 -composite out.jpg
```

## Montage (contact sheet)

```bash
# 3 columns, auto rows
magick montage *.jpg -tile 3x -geometry +10+10 montage.jpg
```

## Identify and formatted output

```bash
# Basic
magick identify in.png

# Custom fields (format, dimensions, bit depth, colorspace)
magick identify -format "%m %wx%h %z-bit %[colorspace]\n" in.png

# Computed fields via fx (example)
magick identify -format "%[fx:w/72] by %[fx:h/72] inches\n" in.png
```

## Parentheses / stacks (POSIX shells)

Use stacks to apply operations to a subset of images:

```bash
magick left.png \( right.png -resize 50% \) +append joined.png
```

Notes:
- Escape parentheses as `\(` and `\)` on POSIX shells (bash/zsh).
- Quote geometry args containing `<` or `>`.
