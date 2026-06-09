"""
把转录结果格式化为 Markdown 文件。
"""

from pathlib import Path


def format_md(title: str, segments: list[dict], output_path: Path) -> Path:
    """
    生成 Markdown 文件，带时间戳和段落。
    """
    lines = [f"# {title}", ""]

    for seg in segments:
        timestamp = _fmt_time(seg["start"])
        text = seg["text"]
        if text:
            lines.append(f"**[{timestamp}]** {text}")
            lines.append("")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")
    return output_path


def _fmt_time(seconds: float) -> str:
    m = int(seconds // 60)
    s = int(seconds % 60)
    return f"{m:02d}:{s:02d}"
