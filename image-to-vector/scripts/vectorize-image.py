#!/usr/bin/env python3
"""Vectorize raster images with VTracer and optional ImageMagick preprocessing."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Profile:
    """Represent a reusable VTracer/ImageMagick vectorization profile."""

    preset: str
    colormode: str
    mode: str
    hierarchical: str | None
    color_precision: int | None
    filter_speckle: int | None
    gradient_step: int | None
    corner_threshold: int | None
    segment_length: float | None
    splice_threshold: int | None
    path_precision: int | None
    svgo_precision: int | None
    colors: int
    max_size: int


PROFILES: dict[str, Profile] = {
    "balanced": Profile(
        preset="poster",
        colormode="color",
        mode="spline",
        hierarchical="stacked",
        color_precision=6,
        filter_speckle=8,
        gradient_step=16,
        corner_threshold=60,
        segment_length=6.0,
        splice_threshold=45,
        path_precision=2,
        svgo_precision=None,
        colors=16,
        max_size=2048,
    ),
    "web": Profile(
        preset="poster",
        colormode="color",
        mode="spline",
        hierarchical="stacked",
        color_precision=6,
        filter_speckle=8,
        gradient_step=16,
        corner_threshold=60,
        segment_length=6.0,
        splice_threshold=45,
        path_precision=0,
        svgo_precision=0,
        colors=16,
        max_size=2048,
    ),
    "compact": Profile(
        preset="poster",
        colormode="color",
        mode="spline",
        hierarchical="stacked",
        color_precision=5,
        filter_speckle=16,
        gradient_step=32,
        corner_threshold=60,
        segment_length=10.0,
        splice_threshold=50,
        path_precision=1,
        svgo_precision=0,
        colors=12,
        max_size=2048,
    ),
    "ultra": Profile(
        preset="poster",
        colormode="color",
        mode="spline",
        hierarchical="stacked",
        color_precision=4,
        filter_speckle=16,
        gradient_step=32,
        corner_threshold=60,
        segment_length=10.0,
        splice_threshold=50,
        path_precision=0,
        svgo_precision=0,
        colors=8,
        max_size=2048,
    ),
    "cartoon": Profile(
        preset="poster",
        colormode="color",
        mode="spline",
        hierarchical="stacked",
        color_precision=5,
        filter_speckle=12,
        gradient_step=24,
        corner_threshold=60,
        segment_length=8.0,
        splice_threshold=45,
        path_precision=2,
        svgo_precision=None,
        colors=12,
        max_size=2048,
    ),
    "poster": Profile(
        preset="poster",
        colormode="color",
        mode="spline",
        hierarchical="stacked",
        color_precision=6,
        filter_speckle=4,
        gradient_step=16,
        corner_threshold=60,
        segment_length=6.0,
        splice_threshold=45,
        path_precision=2,
        svgo_precision=None,
        colors=24,
        max_size=2048,
    ),
    "photo": Profile(
        preset="photo",
        colormode="color",
        mode="spline",
        hierarchical="stacked",
        color_precision=7,
        filter_speckle=4,
        gradient_step=8,
        corner_threshold=60,
        segment_length=4.0,
        splice_threshold=45,
        path_precision=2,
        svgo_precision=None,
        colors=48,
        max_size=2048,
    ),
    "bw": Profile(
        preset="bw",
        colormode="bw",
        mode="spline",
        hierarchical=None,
        color_precision=None,
        filter_speckle=4,
        gradient_step=None,
        corner_threshold=60,
        segment_length=6.0,
        splice_threshold=45,
        path_precision=2,
        svgo_precision=None,
        colors=2,
        max_size=2048,
    ),
}


class ToolError(RuntimeError):
    """Report a missing tool or failed subprocess with useful context."""


def run_command(args: list[str], *, quiet: bool = False) -> subprocess.CompletedProcess[str]:
    """Run a command and raise a readable error when it fails."""

    try:
        result = subprocess.run(
            args,
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except FileNotFoundError as exc:
        raise ToolError(f"Missing executable: {args[0]}") from exc
    except subprocess.CalledProcessError as exc:
        command = " ".join(args)
        stderr = exc.stderr.strip()
        stdout = exc.stdout.strip()
        details = stderr or stdout or f"exit code {exc.returncode}"
        raise ToolError(f"Command failed: {command}\n{details}") from exc

    if not quiet and result.stderr.strip():
        print(result.stderr.strip(), file=sys.stderr)
    return result


def tool_path(name: str) -> str | None:
    """Return the executable path for a command name if it exists."""

    if os.sep in name:
        return name if Path(name).exists() else None
    return shutil.which(name)


def checked_tool(name: str, install_hint: str) -> str:
    """Return a tool path or raise an error with an install hint."""

    resolved = tool_path(name)
    if not resolved:
        raise ToolError(f"`{name}` is required but was not found on PATH. {install_hint}")
    return resolved


def build_profile(args: argparse.Namespace) -> Profile:
    """Merge CLI overrides into the selected built-in profile."""

    profile = PROFILES[args.profile]
    updates: dict[str, Any] = {}
    if args.mode is not None:
        updates["mode"] = args.mode
    if args.hierarchical is not None:
        updates["hierarchical"] = None if args.hierarchical == "none" else args.hierarchical
    for field_name in (
        "color_precision",
        "filter_speckle",
        "gradient_step",
        "corner_threshold",
        "segment_length",
        "splice_threshold",
        "path_precision",
        "svgo_precision",
        "colors",
        "max_size",
    ):
        value = getattr(args, field_name)
        if value is not None:
            updates[field_name] = value
    profile = replace(profile, **updates)
    validate_profile(profile)
    return profile


def validate_profile(profile: Profile) -> None:
    """Validate VTracer bounds that otherwise panic instead of failing gracefully."""

    if profile.filter_speckle is not None and not 0 <= profile.filter_speckle <= 16:
        raise ToolError("--filter-speckle must be within 0..16 for VTracer 0.6.5.")
    if profile.segment_length is not None and not 3.5 <= profile.segment_length <= 10:
        raise ToolError("--segment-length must be within 3.5..10 for VTracer 0.6.5.")
    if profile.path_precision is not None and profile.path_precision < 0:
        raise ToolError("--path-precision must be zero or greater.")
    if profile.svgo_precision is not None and profile.svgo_precision < 0:
        raise ToolError("--svgo-precision must be zero or greater.")


def add_option(command: list[str], name: str, value: Any) -> None:
    """Append a VTracer option if its value is not empty."""

    if value is not None:
        command.extend([name, str(value)])


def vtracer_command(vtracer_bin: str, source: Path, output: Path, profile: Profile) -> list[str]:
    """Build the VTracer command for a source image and output SVG."""

    command = [
        vtracer_bin,
        "--input",
        str(source),
        "--output",
        str(output),
        "--preset",
        profile.preset,
        "--colormode",
        profile.colormode,
        "--mode",
        profile.mode,
    ]
    add_option(command, "--hierarchical", profile.hierarchical)
    add_option(command, "--color_precision", profile.color_precision)
    add_option(command, "--filter_speckle", profile.filter_speckle)
    add_option(command, "--gradient_step", profile.gradient_step)
    add_option(command, "--corner_threshold", profile.corner_threshold)
    add_option(command, "--segment_length", profile.segment_length)
    add_option(command, "--splice_threshold", profile.splice_threshold)
    add_option(command, "--path_precision", profile.path_precision)
    return command


def preprocess_image(
    magick_bin: str,
    source: Path,
    output: Path,
    profile: Profile,
    background: str,
) -> None:
    """Prepare a cleaner PNG for tracing with ImageMagick."""

    output.parent.mkdir(parents=True, exist_ok=True)
    command = [
        magick_bin,
        str(source),
        "-auto-orient",
        "-alpha",
        "remove",
        "-background",
        background,
        "-resize",
        f"{profile.max_size}x{profile.max_size}>",
        "-colorspace",
        "sRGB",
        "-colors",
        str(profile.colors),
        "-strip",
        f"PNG32:{output}",
    ]
    run_command(command, quiet=True)


def render_preview(magick_bin: str, svg: Path, output: Path) -> str | None:
    """Render an SVG preview PNG, returning an error string if rendering fails."""

    output.parent.mkdir(parents=True, exist_ok=True)
    command = [
        magick_bin,
        "-background",
        "white",
        "-density",
        "144",
        str(svg),
        "-alpha",
        "remove",
        "-resize",
        "1024x1024>",
        str(output),
    ]
    try:
        run_command(command, quiet=True)
    except ToolError as exc:
        return str(exc)
    return None


def svgo_command(optimize_mode: str, svgo_bin: str | None) -> list[str] | None:
    """Resolve an SVGO command, optionally falling back to npx."""

    if optimize_mode == "none":
        return None
    if svgo_bin:
        resolved = tool_path(svgo_bin)
        if not resolved:
            raise ToolError(f"`{svgo_bin}` was requested for SVG optimization but was not found.")
        if Path(resolved).name == "npx":
            return [resolved, "--yes", "svgo"]
        return [resolved]

    resolved_svgo = tool_path("svgo")
    if resolved_svgo:
        return [resolved_svgo]

    resolved_npx = tool_path("npx")
    if resolved_npx:
        return [resolved_npx, "--yes", "svgo"]

    if optimize_mode == "svgo":
        raise ToolError("SVG optimization requested, but neither `svgo` nor `npx` was found.")
    return None


def optimize_svg(
    svg: Path,
    optimize_mode: str,
    svgo_bin: str | None,
    svgo_precision: int | None,
) -> dict[str, Any]:
    """Optimize an SVG in place with SVGO and return size metadata."""

    before_bytes = svg.stat().st_size
    command = svgo_command(optimize_mode, svgo_bin)
    if not command:
        return {
            "optimized": False,
            "optimizer": None,
            "before_bytes": before_bytes,
            "after_bytes": before_bytes,
            "skipped": optimize_mode != "none",
        }

    temp_output = svg.with_name(f"{svg.stem}.svgo-tmp.svg")
    svgo_args = command + ["--multipass"]
    if svgo_precision is not None:
        svgo_args.extend(["--precision", str(svgo_precision)])
    svgo_args.extend(["--input", str(svg), "--output", str(temp_output)])
    run_command(svgo_args, quiet=True)
    temp_output.replace(svg)
    after_bytes = svg.stat().st_size
    return {
        "optimized": True,
        "optimizer": " ".join(command),
        "precision": svgo_precision,
        "before_bytes": before_bytes,
        "after_bytes": after_bytes,
        "saved_bytes": before_bytes - after_bytes,
    }


def svg_metrics(svg: Path) -> dict[str, Any]:
    """Collect lightweight metrics that help judge SVG complexity."""

    text = svg.read_text(encoding="utf-8", errors="replace")
    fill_values = set(re.findall(r'fill="([^"]+)"', text))
    return {
        "path_count": len(re.findall(r"<path\b", text)),
        "shape_count": len(re.findall(r"<(?:path|rect|circle|ellipse|polygon|polyline)\b", text)),
        "fill_count": len(fill_values),
        "fills": sorted(fill_values)[:32],
        "bytes": svg.stat().st_size,
    }


def image_metrics(magick_bin: str | None, image: Path) -> dict[str, Any]:
    """Collect basic raster metrics with ImageMagick when available."""

    if not magick_bin:
        return {"bytes": image.stat().st_size}

    command = [
        magick_bin,
        "identify",
        "-format",
        "%m %wx%h %[colorspace] %[colors]\n",
        str(image),
    ]
    try:
        result = run_command(command, quiet=True)
    except ToolError:
        return {"bytes": image.stat().st_size}

    parts = result.stdout.strip().split()
    metrics: dict[str, Any] = {"bytes": image.stat().st_size}
    if len(parts) >= 4:
        metrics.update(
            {
                "format": parts[0],
                "dimensions": parts[1],
                "colorspace": parts[2],
                "colors": parts[3],
            }
        )
    return metrics


def output_base(args: argparse.Namespace, source: Path) -> tuple[Path, str]:
    """Choose the output directory and basename for generated files."""

    if args.compare:
        if args.output:
            return args.output.parent, args.output.stem
        if args.out_dir:
            return args.out_dir, source.stem
        return Path.cwd() / f"{source.stem}-vectorized", source.stem

    if args.output:
        return args.output.parent, args.output.stem
    if args.out_dir:
        return args.out_dir, source.stem
    return Path.cwd(), source.stem


def run_variant(
    *,
    name: str,
    source: Path,
    output_svg: Path,
    profile: Profile,
    vtracer_bin: str,
    magick_bin: str | None,
    preprocess: bool,
    background: str,
    preview_mode: str,
    optimize_mode: str,
    svgo_bin: str | None,
) -> dict[str, Any]:
    """Run one vectorization variant and return report data."""

    output_svg.parent.mkdir(parents=True, exist_ok=True)
    trace_source = source
    preprocessed_path: Path | None = None
    if preprocess:
        if not magick_bin:
            raise ToolError("ImageMagick is required for --preprocess quantize but `magick` was not found.")
        preprocessed_path = output_svg.with_name(f"{output_svg.stem}.quantized-input.png")
        preprocess_image(magick_bin, source, preprocessed_path, profile, background)
        trace_source = preprocessed_path

    run_command(vtracer_command(vtracer_bin, trace_source, output_svg, profile), quiet=True)
    optimization = optimize_svg(output_svg, optimize_mode, svgo_bin, profile.svgo_precision)

    preview_path = output_svg.with_suffix(".png")
    preview_error: str | None = None
    if preview_mode != "never":
        if magick_bin:
            preview_error = render_preview(magick_bin, output_svg, preview_path)
        elif preview_mode == "always":
            raise ToolError("Preview rendering requires ImageMagick, but `magick` was not found.")

    data: dict[str, Any] = {
        "variant": name,
        "svg": str(output_svg),
        "source": str(trace_source),
        "preprocessed": str(preprocessed_path) if preprocessed_path else None,
        "preview": str(preview_path) if preview_path.exists() else None,
        "preview_error": preview_error,
        "optimization": optimization,
        "svg_metrics": svg_metrics(output_svg),
    }
    return data


def write_report(report_path: Path, data: dict[str, Any]) -> None:
    """Write a JSON report for generated vectorization artifacts."""

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def parse_args(argv: list[str]) -> argparse.Namespace:
    """Parse command-line arguments."""

    parser = argparse.ArgumentParser(
        description="Vectorize raster images with VTracer and optional ImageMagick preprocessing."
    )
    parser.add_argument("input", type=Path, help="Input raster image path.")
    parser.add_argument("-o", "--output", type=Path, help="Output SVG path for a single run.")
    parser.add_argument("--out-dir", type=Path, help="Output directory for generated artifacts.")
    parser.add_argument("--profile", choices=sorted(PROFILES), default="balanced", help="Vectorization profile.")
    parser.add_argument(
        "--preprocess",
        choices=("none", "quantize"),
        default="none",
        help="Preprocess with ImageMagick before tracing.",
    )
    parser.add_argument("--compare", action="store_true", help="Run both direct and preprocessed variants.")
    parser.add_argument("--background", default="white", help="Background used when flattening alpha.")
    parser.add_argument("--preview", choices=("auto", "always", "never"), default="auto", help="Render PNG previews.")
    parser.add_argument("--report", type=Path, help="JSON report path.")
    parser.add_argument("--vtracer-bin", default="vtracer", help="VTracer executable name or path.")
    parser.add_argument("--magick-bin", default="magick", help="ImageMagick executable name or path.")
    parser.add_argument(
        "--optimize-svg",
        choices=("auto", "none", "svgo"),
        default="auto",
        help="Optimize SVG output with SVGO. Auto uses `svgo` or `npx --yes svgo` when available.",
    )
    parser.add_argument("--svgo-bin", help="SVGO executable path/name. Use `npx` to force npx-based SVGO.")
    parser.add_argument("--svgo-precision", type=int, help="Override SVGO numeric precision.")
    parser.add_argument("--mode", choices=("pixel", "polygon", "spline"), help="Override VTracer curve fitting mode.")
    parser.add_argument(
        "--hierarchical",
        choices=("stacked", "cutout", "none"),
        help="Override VTracer color hierarchy. Use none for black-and-white mode.",
    )
    parser.add_argument("--color-precision", type=int, help="Override VTracer color precision.")
    parser.add_argument("--filter-speckle", type=int, help="Override VTracer speckle filter.")
    parser.add_argument("--gradient-step", type=int, help="Override VTracer gradient step.")
    parser.add_argument("--corner-threshold", type=int, help="Override VTracer corner threshold.")
    parser.add_argument("--segment-length", type=float, help="Override VTracer segment length.")
    parser.add_argument("--splice-threshold", type=int, help="Override VTracer splice threshold.")
    parser.add_argument("--path-precision", type=int, help="Override VTracer SVG path precision.")
    parser.add_argument("--colors", type=int, help="Override ImageMagick quantization color count.")
    parser.add_argument("--max-size", type=int, help="Override preprocessing max width/height.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Run the vectorization CLI."""

    args = parse_args(argv or sys.argv[1:])
    source = args.input.expanduser().resolve()
    if not source.exists():
        raise ToolError(f"Input image does not exist: {source}")

    vtracer_bin = checked_tool(args.vtracer_bin, "Install with `cargo install vtracer`.")
    magick_bin = tool_path(args.magick_bin)
    if args.preprocess == "quantize" and not magick_bin:
        raise ToolError("ImageMagick is required for --preprocess quantize. Install `magick` first.")

    profile = build_profile(args)
    out_dir, stem = output_base(args, source)
    out_dir.mkdir(parents=True, exist_ok=True)

    report: dict[str, Any] = {
        "input": str(source),
        "profile": args.profile,
        "preprocess": args.preprocess,
        "input_metrics": image_metrics(magick_bin, source),
        "variants": [],
    }

    if args.compare:
        variants = [
            ("direct", False, out_dir / f"{stem}.direct.svg"),
            ("preprocessed", True, out_dir / f"{stem}.preprocessed.svg"),
        ]
    else:
        variants = [
            (
                "preprocessed" if args.preprocess == "quantize" else "direct",
                args.preprocess == "quantize",
                out_dir / f"{stem}.svg",
            )
        ]

    for name, should_preprocess, output_svg in variants:
        report["variants"].append(
            run_variant(
                name=name,
                source=source,
                output_svg=output_svg,
                profile=profile,
                vtracer_bin=vtracer_bin,
                magick_bin=magick_bin,
                preprocess=should_preprocess,
                background=args.background,
                preview_mode=args.preview,
                optimize_mode=args.optimize_svg,
                svgo_bin=args.svgo_bin,
            )
        )

    report_path = args.report or out_dir / f"{stem}.vectorize-report.json"
    write_report(report_path, report)
    print(json.dumps({"report": str(report_path), "variants": report["variants"]}, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ToolError as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
