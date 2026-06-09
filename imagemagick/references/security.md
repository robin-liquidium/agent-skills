# ImageMagick security notes

ImageMagick supports many file formats (“coders”) and can invoke external programs (“delegates”) for some formats (e.g., PDF/PS, some vector formats, remote URLs). If you process untrusted input (especially on servers), use a restrictive `policy.xml` and set resource limits.

## Quick checks

```bash
# Show active policy
magick identify -list policy

# Show supported formats/coders
magick -list format

# Show delegates (if any)
magick -list delegate
```

## Practical guidance

- Prefer allowing only web-safe formats (GIF/JPEG/PNG/WebP) in public pipelines.
- Disable indirect reads (e.g. `@file.txt`) when user input could reach CLI args.
- Set resource limits (time, memory, disk, image dimensions, list-length) to avoid DoS via huge images.
- Consider disabling risky coders/delegates (e.g. PDF/PS/SVG/HTTPS/MVG) unless needed.

## References

- Official Security Policy docs: https://imagemagick.org/script/security-policy.php
- Policy examples: https://imagemagick.org/source/
