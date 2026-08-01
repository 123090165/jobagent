from __future__ import annotations

import re
import unicodedata
from pathlib import Path

import fitz


_FONT_CANDIDATES = (
    Path("C:/Windows/Fonts/msyh.ttc"),
    Path("C:/Windows/Fonts/simhei.ttf"),
    Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
)


def render_resume_pdf(markdown_text: str) -> bytes:
    """将用户批准的 Markdown 简历即时渲染为简洁 PDF，不保存额外文件状态。"""
    document = fitz.open()
    page = document.new_page(width=595, height=842)
    left, top, right, bottom = 48.0, 48.0, 547.0, 794.0
    y = top
    font_kwargs = _font_kwargs()

    for raw_line in markdown_text.splitlines():
        text, font_size, spacing = _line_style(raw_line)
        if not text:
            y += 6
            continue
        wrapped = _wrap_text(text, max_units=max(20, int((right - left) / font_size * 1.7)))
        for line in wrapped:
            line_height = font_size * 1.45
            if y + line_height > bottom:
                page = document.new_page(width=595, height=842)
                y = top
            page.insert_text(
                (left, y + font_size),
                line,
                fontsize=font_size,
                color=(0.08, 0.1, 0.14),
                **font_kwargs,
            )
            y += line_height
        y += spacing

    payload = document.tobytes(garbage=4, deflate=True)
    document.close()
    return payload


def _font_kwargs() -> dict[str, str]:
    font_file = next((path for path in _FONT_CANDIDATES if path.exists()), None)
    if font_file is None:
        return {"fontname": "china-s"}
    return {"fontname": "jobagent-resume", "fontfile": str(font_file)}


def _line_style(raw_line: str) -> tuple[str, float, float]:
    stripped = raw_line.strip()
    heading = re.match(r"^(#{1,3})\s+(.*)$", stripped)
    if heading:
        level = len(heading.group(1))
        return _plain_text(heading.group(2)), {1: 18.0, 2: 14.0, 3: 12.0}[level], 5.0
    if re.match(r"^[-*+]\s+", stripped):
        return "• " + _plain_text(re.sub(r"^[-*+]\s+", "", stripped)), 10.5, 1.5
    return _plain_text(stripped), 10.5, 1.5


def _plain_text(value: str) -> str:
    value = re.sub(r"\[([^]]+)]\(([^)]+)\)", r"\1 (\2)", value)
    value = re.sub(r"[*_`]+", "", value)
    return value.replace("\t", "    ").strip()


def _wrap_text(value: str, *, max_units: int) -> list[str]:
    if not value:
        return [""]
    lines: list[str] = []
    current: list[str] = []
    units = 0
    for char in value:
        width = 2 if unicodedata.east_asian_width(char) in {"W", "F"} else 1
        if current and units + width > max_units:
            lines.append("".join(current).rstrip())
            current = []
            units = 0
        current.append(char)
        units += width
    if current:
        lines.append("".join(current).rstrip())
    return lines
