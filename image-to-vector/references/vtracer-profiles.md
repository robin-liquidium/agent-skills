# VTracer Profiles

Use this reference when choosing profiles or changing wrapper defaults.

## Engine Choice

VTracer is the default engine because it handles color PNG/JPG input directly and produces compact SVG output. Potrace can be better for pure black-and-white masks, but generated artwork, icons, diagrams, logos, and cartoons often have antialiasing, fills, shadows, and multiple colors that make VTracer the better single-engine default.

## Preprocessing

The wrapper's `--preprocess quantize` mode uses ImageMagick to:

- auto-orient the source,
- flatten alpha onto a background color,
- resize very large images,
- convert to sRGB,
- reduce the palette with `-colors`,
- strip metadata,
- write a PNG before tracing.

Preprocessing can help noisy JPEGs or raster images with speckles, compression artifacts, very large dimensions, or too many near-duplicate colors. For clean generated images, icons, logos, and simple artwork, prefer direct tracing first because palette reduction can distort antialiasing and shading.

## SVG Optimization

The wrapper optimizes SVG output with SVGO by default when `svgo` or `npx` is available. This is separate from tracing accuracy: SVGO removes XML overhead and rewrites paths without intentionally changing the artwork.

Use `--optimize-svg none` when raw VTracer output is needed. Use `--optimize-svg svgo` when optimization must happen and should fail loudly if neither `svgo` nor `npx` is available.

Use `--svgo-precision 0` for simple website assets when file size matters. This can dramatically reduce path-data decimals while preserving smooth spline curves. Use a higher precision if curves or tiny details visibly shift.

## Practical Defaults

`balanced` is the default general-purpose profile:

- VTracer preset: `poster`
- curve mode: `spline`
- hierarchy: `stacked`
- color precision: `6`
- gradient step: `16`
- speckle filter: `8`
- path precision: `2`
- preprocessing colors: `16`
- preprocessing max size: `2048`

Use `web` for website SVGs that should stay close to `balanced` while reducing size. It uses integer path coordinates plus SVGO precision `0`.

Use `compact` when byte size matters more than exact shape fidelity. It raises speckle filtering, uses fewer color bits, widens gradient steps, uses the maximum valid VTracer segment length, and uses SVGO precision `0`.

Use `ultra` when the smallest smooth SVG matters most. It drops color precision further and uses heavier simplification. It can produce very small SVGs, but small details and subtle fills flatten sooner.

Use `cartoon` when the SVG is too detailed or noisy but the source remains flat-color. Use `poster` when the source is not icon-like but still posterized or illustration-like. Use `photo` only for image-like sources where compact editability matters less than visual approximation. Use `bw` for pure black-and-white assets.

## VTracer Bounds

VTracer 0.6.5 panics instead of gracefully rejecting some invalid simplification values. Keep overrides inside these bounds:

- `--filter-speckle`: `0` to `16`
- `--segment-length`: `3.5` to `10`
- `--path-precision`: `0` or greater

## Quality Checks

After vectorizing, inspect:

- rendered PNG preview,
- SVG file size,
- path count,
- unique fill count,
- whether outlines stay continuous,
- whether tiny speckles or antialiasing fragments became shapes,
- whether straight edges remain straight,
- whether curves stay smooth,
- compressed size if the SVG will be served over the web.

Lower `--path-precision`, lower `--svgo-precision`, lower `--color-precision`, raise `--gradient-step`, raise `--segment-length`, or raise `--filter-speckle` if the SVG is too complex. Disable preprocessing or raise `--colors` if important shading disappears.

## Tuning Notes

For simple artwork, staying in VTracer `spline` mode often gives a better size/quality balance than polygon mode. Polygon mode can be small, but curves may become visibly faceted. Spline mode plus SVGO precision reduction keeps smooth curves while still cutting file size.

Post-trace smoothing libraries are not part of this skill by default. They add dependency and licensing complexity, and they can round intentional hard corners or increase output size. Prefer VTracer settings and SVGO precision first.
