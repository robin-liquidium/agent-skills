# Geometry and “resize/crop/extent” patterns

ImageMagick geometry strings show up in many options (`-resize`, `-crop`, `-extent`, `-region`, etc.). Shell quoting matters.

## Safety rules

- Quote any geometry containing `<` or `>`: those can be interpreted as shell redirection.
- On POSIX shells, escape parentheses as `\(` and `\)`.

## Resizing (common forms)

```bash
# Fit within box, keep aspect ratio
magick in.jpg -resize "1200x1200" out.jpg

# Only shrink if larger
magick in.jpg -resize "1600x1600>" out.jpg

# Only enlarge if smaller
magick in.jpg -resize "1600x1600<" out.jpg

# Force exact dimensions (may distort)
magick in.jpg -resize "300x300\!" out.jpg

# Minimum size then crop (cover)
magick in.jpg -resize "1200x1200^" -gravity center -extent 1200x1200 out.jpg

# Area-based resize (approximate)
magick in.jpg -resize "1000000@" out.jpg
```

## Cropping

```bash
# Crop WxH+X+Y and drop the virtual canvas metadata
magick in.jpg -crop "800x600+100+50" +repage out.jpg
```

## Letterbox / padding

```bash
# Contain inside exact size with padding
magick in.jpg -resize "1200x1200" -background black -gravity center -extent 1200x1200 out.jpg
```

## Where this comes from

- Official Command-line Processing (geometry operators table): https://imagemagick.org/script/command-line-processing.php
