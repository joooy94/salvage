"""Conservative splitter for the 15-case drilling accident source Markdown."""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import List


CASE_PDF_NAME = "钻具断落事故.pdf"


@dataclass(frozen=True)
class CaseChunk:
    case_no: str
    title: str
    text: str
    start_marker: str
    end_marker: str
    confidence: float
    source_pages: list[int]


def split_cases(raw_markdown: str) -> List[CaseChunk]:
    """Split case-library Markdown into case chunks.

    The splitter is intentionally conservative. It first looks for explicit
    Chinese case headings; if it cannot find exactly 15 chunks, it returns 15
    placeholder chunks so downstream build/health interfaces remain runnable
    and the manifest clearly marks low confidence.
    """
    pattern = re.compile(
        r"(?m)^(?:#+\s*)?(?:案例|事故案例|例)\s*([一二三四五六七八九十0-9]{1,3})[、.．：:\s]*(.{2,80})$"
    )
    matches = list(pattern.finditer(raw_markdown))
    chunks: List[CaseChunk] = []
    for index, match in enumerate(matches):
        start = match.start()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(raw_markdown)
        body = raw_markdown[start:end].strip()
        if len(body) < 80:
            continue
        no = f"{len(chunks) + 1:02d}"
        title_tail = match.group(2).strip() or f"案例{no}"
        end_marker = matches[index + 1].group(0) if index + 1 < len(matches) else "文档结束"
        chunks.append(
            CaseChunk(
                no,
                _safe_title(title_tail),
                body,
                match.group(0),
                end_marker,
                0.9,
                _source_pages(raw_markdown[:start], body),
            )
        )

    if len(chunks) == 15:
        return chunks

    return [
        CaseChunk(f"{i:02d}", f"待复核案例{i:02d}", "", "自动占位", "自动占位", 0.0, [])
        for i in range(1, 16)
    ]


def write_cases(raw_markdown_path: str | Path, wiki_cases_dir: str | Path = "wiki/cases") -> Path:
    raw_path = Path(raw_markdown_path)
    cases_dir = Path(wiki_cases_dir)
    cases_dir.mkdir(parents=True, exist_ok=True)
    for old_case in cases_dir.glob("案例*.md"):
        old_case.unlink()
    chunks = split_cases(raw_path.read_text(encoding="utf-8"))
    manifest = []
    for chunk in chunks:
        filename = f"案例{chunk.case_no}_{chunk.title}.md"
        wiki_file = cases_dir / filename
        wiki_file.write_text(render_case_page(chunk), encoding="utf-8")
        manifest.append(
            {
                "case_no": chunk.case_no,
                "title": chunk.title,
                "source_pdf": CASE_PDF_NAME,
                "source_pages": chunk.source_pages,
                "start_marker": chunk.start_marker,
                "end_marker": chunk.end_marker,
                "confidence": chunk.confidence,
                "wiki_file": wiki_file.as_posix(),
            }
        )
    manifest_path = cases_dir / "case_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest_path


def render_case_page(chunk: CaseChunk) -> str:
    parsed = _parse_case_content(chunk)
    return f"""---
title: 案例{chunk.case_no}_{chunk.title}
source_pdf: {CASE_PDF_NAME}
doc_type: case
case_no: {chunk.case_no}
source_pages: {json.dumps(chunk.source_pages, ensure_ascii=False)}
split_confidence: {chunk.confidence}
---

# 案例{chunk.case_no}_{chunk.title}

## 基本信息
- 井名/井型：{parsed["well_name"]}
- 事故发生层位/深度：{parsed["depth"]}
- 钻具组合：{parsed["bha"]}
- 落鱼描述：{parsed["fish"]}
- 事故原因：{parsed["cause"]}

## 井况条件
- 井斜/方位：{parsed["inclination"]}
- 钻井液类型及性能：{parsed["mud"]}
- 地层特征：{parsed["formation"]}

## 处置过程
{parsed["handling"]}

## 使用工具
{parsed["tools"]}

## 处置结果
- 最终结果：{parsed["result"]}
- 耗时：
- 关键经验：{parsed["lesson"]}

## 失败教训
{parsed["failure"]}

## 相关页面
"""


def _safe_title(value: str) -> str:
    value = re.sub(r"[\\/:*?\"<>|\s]+", "_", value.strip())
    return value[:40].strip("_") or "未命名案例"


def _source_pages(prefix: str, text: str) -> list[int]:
    pages = [int(match) for match in re.findall(r"<!--\s*page:(\d+)\s*-->", text)]
    before = re.findall(r"<!--\s*page:(\d+)\s*-->", prefix)
    if before:
        pages.append(int(before[-1]))
    return sorted(set(pages))


def _parse_case_content(chunk: CaseChunk) -> dict[str, str]:
    text = chunk.text or "待人工复核原始案例内容。"
    facts = _section(text, ["基础资料"], ["事故发生经过", "事故处理过程", "认识与建议"])
    accident = _section(text, ["事故发生经过"], ["事故处理过程", "认识与建议"])
    handling = _section(text, ["事故处理过程", "处理过程"], ["认识与建议"])
    lesson = _section(text, ["认识与建议", "认识和建议"], [])
    merged = "\n".join([facts, accident, handling, lesson, text])

    return {
        "well_name": chunk.title.replace("_", " "),
        "depth": _first_match(
            [r"(?:钻深|井深|钻至井深|钻至)[^0-9]{0,8}([0-9]+(?:\.[0-9]+)?\s*m)", r"鱼顶[^0-9]{0,8}([0-9]+(?:\.[0-9]+)?\s*m)"],
            merged,
        ),
        "bha": _line_containing(facts, ["钻具结构", "钻具组合", "钻柱结构"]),
        "fish": _line_containing(merged, ["落鱼", "鱼顶"]),
        "cause": _summarize(accident or _line_containing(merged, ["造成", "原因", "事故"]), 180),
        "inclination": _line_containing(facts, ["井斜", "方位"]) or "未提取",
        "mud": _line_containing(facts, ["钻井液", "泥浆", "井液"]),
        "formation": _line_containing(facts, ["地层", "层位"]) or "未提取",
        "handling": handling or text,
        "tools": _tools(merged),
        "result": _result("\n".join([handling, lesson])),
        "lesson": _summarize(lesson, 240),
        "failure": _summarize(_failure_notes(lesson or handling), 240),
    }


def _section(text: str, starts: list[str], stops: list[str]) -> str:
    start_pattern = "|".join(re.escape(item) for item in starts)
    start = re.search(rf"(?m)^[（(]?\d+[）).、]?\s*(?:{start_pattern})\s*$", text)
    if not start:
        start = re.search(rf"(?:{start_pattern})", text)
    if not start:
        return ""
    begin = start.end()
    end = len(text)
    for stop in stops:
        match = re.search(rf"(?m)^[（(]?\d+[）).、]?\s*{re.escape(stop)}\s*$", text[begin:])
        if match:
            end = min(end, begin + match.start())
    return text[begin:end].strip()


def _first_match(patterns: list[str], text: str) -> str:
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1).strip()
    return "未提取"


def _line_containing(text: str, needles: list[str]) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped and any(needle in stripped for needle in needles):
            return stripped
    return "未提取"


def _summarize(text: str, limit: int) -> str:
    compact = re.sub(r"\s+", " ", text).strip()
    return compact[:limit] if compact else "未提取"


def _tools(text: str) -> str:
    names = [
        "公锥",
        "母锥",
        "卡瓦打捞筒",
        "打捞筒",
        "打捞矛",
        "套铣筒",
        "磨鞋",
        "震击器",
        "加速器",
        "安全接头",
        "反循环打捞篮",
        "钻头",
    ]
    found = [name for name in names if name in text]
    return "\n".join(f"- {name}" for name in found) if found else "未提取"


def _result(text: str) -> str:
    if any(word in text for word in ["捞完", "起出", "成功", "解卡"]):
        return "成功或部分成功，需结合原文复核"
    if any(word in text for word in ["报废", "侧钻", "失败"]):
        return "失败/报废/侧钻，需结合原文复核"
    return "未提取"


def _failure_notes(text: str) -> str:
    lines = [line.strip() for line in text.splitlines() if any(key in line for key in ["不应", "盲目", "无效", "失败", "事故", "损失"])]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("raw_markdown")
    parser.add_argument("--wiki-cases-dir", default="wiki/cases")
    args = parser.parse_args()
    print(write_cases(args.raw_markdown, args.wiki_cases_dir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
