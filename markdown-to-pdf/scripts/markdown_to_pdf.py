#!/usr/bin/env python3
"""Render concise Markdown documents to clean local PDFs.

The renderer intentionally supports a narrow Markdown subset:
- headings
- paragraphs
- bullet and numbered lists
- simple pipe tables

Default output is a pageless-style PDF: one tall A4-width page fitted to the
content height. This keeps investor memos, briefs, and other text-first docs
compact and easy to share without manual page-height tuning.
"""

from __future__ import annotations

import argparse
import html
import re
import tempfile
from pathlib import Path
from typing import Iterable

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, StyleSheet1, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    ListFlowable,
    ListItem,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

try:
    from pypdf import PdfReader
except ImportError:  # pragma: no cover - dependency is optional outside fit mode
    PdfReader = None


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", help="Path to the Markdown file.")
    parser.add_argument("output", help="Path to the output PDF file.")
    parser.add_argument(
        "--page-mode",
        choices=("fit-content", "a4", "custom"),
        default="fit-content",
        help="Page sizing mode. Defaults to a single tall page fitted to content.",
    )
    parser.add_argument(
        "--page-width-mm",
        type=float,
        default=210.0,
        help="Page width in millimeters for fit-content or custom modes.",
    )
    parser.add_argument(
        "--page-height-mm",
        type=float,
        default=None,
        help="Page height in millimeters for custom mode.",
    )
    parser.add_argument(
        "--min-height-mm",
        type=float,
        default=297.0,
        help="Minimum page height in millimeters when fitting content.",
    )
    parser.add_argument(
        "--max-height-mm",
        type=float,
        default=1600.0,
        help="Maximum page height in millimeters when fitting content.",
    )
    return parser.parse_args()


def build_styles() -> StyleSheet1:
    """Create document styles."""
    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="InvestorBody",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=10.5,
            leading=14,
            spaceAfter=6,
            textColor=colors.HexColor("#111827"),
            alignment=TA_LEFT,
        )
    )
    styles.add(
        ParagraphStyle(
            name="InvestorTitle",
            parent=styles["Title"],
            fontName="Helvetica-Bold",
            fontSize=20,
            leading=24,
            spaceAfter=10,
            textColor=colors.HexColor("#0F172A"),
        )
    )
    styles.add(
        ParagraphStyle(
            name="InvestorH2",
            parent=styles["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=13.5,
            leading=17,
            spaceBefore=10,
            spaceAfter=6,
            textColor=colors.HexColor("#0F172A"),
        )
    )
    styles.add(
        ParagraphStyle(
            name="InvestorH3",
            parent=styles["Heading3"],
            fontName="Helvetica-Bold",
            fontSize=11.5,
            leading=14,
            spaceBefore=8,
            spaceAfter=5,
            textColor=colors.HexColor("#0F172A"),
        )
    )
    styles.add(
        ParagraphStyle(
            name="InvestorList",
            parent=styles["InvestorBody"],
            leftIndent=0,
            firstLineIndent=0,
            spaceBefore=0,
            spaceAfter=2,
        )
    )
    styles.add(
        ParagraphStyle(
            name="InvestorTable",
            parent=styles["InvestorBody"],
            fontSize=9.2,
            leading=12,
            spaceAfter=0,
        )
    )
    return styles


def inline_markup(text: str) -> str:
    """Convert a small subset of inline Markdown to ReportLab markup."""
    escaped = html.escape(text, quote=False)
    escaped = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", escaped)
    escaped = re.sub(
        r"`([^`]+)`",
        r'<font face="Courier" backColor="#F3F4F6">\1</font>',
        escaped,
    )
    return escaped


def paragraph_markup(lines: list[str]) -> str:
    """Convert paragraph lines to ReportLab markup while preserving hard breaks."""
    parts: list[str] = []
    for index, line in enumerate(lines):
        trimmed = line.strip()
        if not trimmed:
            continue
        parts.append(inline_markup(trimmed))
        if index < len(lines) - 1:
            current = line.rstrip("\n")
            if current.endswith("  ") or current.endswith("\\"):
                parts.append("<br/>")
            else:
                parts.append(" ")
    return "".join(parts)


def normalize_table_cell(cell: str) -> str:
    """Normalize a pipe-table cell."""
    return inline_markup(cell.strip())


def is_table_separator(line: str) -> bool:
    """Return True when the line is the Markdown separator row."""
    stripped = line.strip()
    if not stripped.startswith("|"):
        return False
    return all(
        part.strip().replace("-", "").replace(":", "") == ""
        for part in stripped.split("|")[1:-1]
    )


def parse_table_block(lines: list[str]) -> list[list[str]]:
    """Parse a contiguous pipe-table block."""
    rows: list[list[str]] = []
    for line in lines:
        if is_table_separator(line):
            continue
        parts = [
            normalize_table_cell(part) for part in line.strip().strip("|").split("|")
        ]
        rows.append(parts)
    return rows


def build_table(rows: list[list[str]], styles: StyleSheet1) -> Table:
    """Create a styled ReportLab table."""
    para_rows = [
        [Paragraph(cell or "&nbsp;", styles["InvestorTable"]) for cell in row]
        for row in rows
    ]
    table = Table(para_rows, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F8FAFC")),
                ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#111827")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D1D5DB")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("LEADING", (0, 0), (-1, -1), 12),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    return table


def build_list(items: list[str], styles: StyleSheet1, bullet_type: str) -> ListFlowable:
    """Create a styled bullet or numbered list."""
    list_items = [
        ListItem(Paragraph(inline_markup(item), styles["InvestorList"]))
        for item in items
    ]
    return ListFlowable(
        list_items,
        bulletType=bullet_type,
        start="1" if bullet_type == "1" else None,
        leftIndent=14,
    )


def iter_story(markdown_text: str, styles: StyleSheet1) -> Iterable[object]:
    """Convert Markdown text into ReportLab flowables."""
    lines = markdown_text.splitlines()
    index = 0
    while index < len(lines):
        line = lines[index]
        stripped = line.strip()

        if not stripped:
            index += 1
            continue

        if stripped.startswith("|"):
            table_lines: list[str] = []
            while index < len(lines) and lines[index].strip().startswith("|"):
                table_lines.append(lines[index])
                index += 1
            yield build_table(parse_table_block(table_lines), styles)
            yield Spacer(1, 6)
            continue

        if stripped.startswith("# "):
            yield Paragraph(inline_markup(stripped[2:].strip()), styles["InvestorTitle"])
            yield Spacer(1, 2)
            index += 1
            continue

        if stripped.startswith("## "):
            yield Paragraph(inline_markup(stripped[3:].strip()), styles["InvestorH2"])
            index += 1
            continue

        if stripped.startswith("### "):
            yield Paragraph(inline_markup(stripped[4:].strip()), styles["InvestorH3"])
            index += 1
            continue

        bullet_match = re.match(r"^[-*]\s+(.*)$", stripped)
        if bullet_match:
            items: list[str] = []
            while index < len(lines):
                current = lines[index].strip()
                match = re.match(r"^[-*]\s+(.*)$", current)
                if not match:
                    break
                items.append(match.group(1))
                index += 1
            yield build_list(items, styles, "bullet")
            yield Spacer(1, 4)
            continue

        number_match = re.match(r"^\d+\.\s+(.*)$", stripped)
        if number_match:
            items = []
            while index < len(lines):
                current = lines[index].strip()
                match = re.match(r"^\d+\.\s+(.*)$", current)
                if not match:
                    break
                items.append(match.group(1))
                index += 1
            yield build_list(items, styles, "1")
            yield Spacer(1, 4)
            continue

        paragraph_lines = [line]
        index += 1
        while index < len(lines):
            current_line = lines[index]
            current = current_line.strip()
            if (
                not current
                or current.startswith("#")
                or current.startswith("|")
                or re.match(r"^[-*]\s+", current)
                or re.match(r"^\d+\.\s+", current)
            ):
                break
            paragraph_lines.append(current_line)
            index += 1
        paragraph = paragraph_markup(paragraph_lines)
        yield Paragraph(paragraph, styles["InvestorBody"])


def build_story(markdown_text: str) -> list[object]:
    """Build a fresh story list for each render attempt."""
    styles = build_styles()
    return list(iter_story(markdown_text, styles))


def build_pdf(story: list[object], output_path: Path, page_size: tuple[float, float], title: str) -> None:
    """Render the provided story to a PDF."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=page_size,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title=title,
        author="Codex",
    )
    doc.build(story)


def count_pages(pdf_path: Path) -> int:
    """Count pages in a rendered PDF."""
    if PdfReader is None:
        raise RuntimeError(
            "pypdf is required for fit-content mode. Install it or use --page-mode a4."
        )
    return len(PdfReader(str(pdf_path)).pages)


def find_fit_height_mm(markdown_text: str, title: str, page_width_mm: float, min_height_mm: float, max_height_mm: float) -> float:
    """Find the smallest page height that keeps the document on one page."""
    low = max(1, int(min_height_mm))
    high = max(low, int(max_height_mm))
    with tempfile.TemporaryDirectory(prefix="markdown-to-pdf-") as tmpdir:
        probe_path = Path(tmpdir) / "probe.pdf"

        while low < high:
            mid = (low + high) // 2
            build_pdf(
                build_story(markdown_text),
                probe_path,
                (page_width_mm * mm, mid * mm),
                title,
            )
            if count_pages(probe_path) == 1:
                high = mid
            else:
                low = mid + 1

        build_pdf(
            build_story(markdown_text),
            probe_path,
            (page_width_mm * mm, low * mm),
            title,
        )
        if count_pages(probe_path) != 1:
            raise RuntimeError(
                "Could not fit the document onto one page. Increase --max-height-mm."
            )
    return float(low)


def render_markdown_to_pdf(
    input_path: Path,
    output_path: Path,
    page_mode: str,
    page_width_mm: float,
    page_height_mm: float | None,
    min_height_mm: float,
    max_height_mm: float,
) -> None:
    """Render a Markdown file to PDF using the requested page-sizing mode."""
    markdown_text = input_path.read_text(encoding="utf-8")

    if page_mode == "a4":
        page_size = A4
    elif page_mode == "custom":
        if page_height_mm is None:
            raise ValueError("--page-height-mm is required for --page-mode custom.")
        page_size = (page_width_mm * mm, page_height_mm * mm)
    else:
        fitted_height_mm = find_fit_height_mm(
            markdown_text=markdown_text,
            title=input_path.stem,
            page_width_mm=page_width_mm,
            min_height_mm=min_height_mm,
            max_height_mm=max_height_mm,
        )
        page_size = (page_width_mm * mm, fitted_height_mm * mm)

    build_pdf(build_story(markdown_text), output_path, page_size, input_path.stem)


def main() -> int:
    """Entrypoint."""
    args = parse_args()
    render_markdown_to_pdf(
        input_path=Path(args.input),
        output_path=Path(args.output),
        page_mode=args.page_mode,
        page_width_mm=args.page_width_mm,
        page_height_mm=args.page_height_mm,
        min_height_mm=args.min_height_mm,
        max_height_mm=args.max_height_mm,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
