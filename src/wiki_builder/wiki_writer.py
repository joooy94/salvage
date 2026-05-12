"""Minimal Wiki page writer helpers and LLM prompt templates."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List


STANDARD_SOURCES: Dict[str, str] = {
    "打捞工具目录": "SY 5069-2017石油天然气工业钻井和采油设备 管柱类落物打捞工具.pdf",
    "解卡操作规程": "SY_T 5587.12-2018常规修井作业规程 第12部分：解卡打捞.pdf",
    "水平井特殊工艺": "SYT 6987-2024 水平井解卡打捞及冲砂方法.pdf",
}


STANDARD_PROMPT_TEMPLATE = """将以下原始 Markdown 编译为可追溯 Wiki 标准页：{title}\n\n{content}"""
CASE_PROMPT_TEMPLATE = """将以下事故案例编译为结构化 Wiki 案例页：{title}\n\n{content}"""
SYNTHESIS_PROMPT_TEMPLATE = """基于已生成 Wiki 页面编写综合分析页：{title}"""


def write_standard_drafts(raw_dir: str | Path = "data/raw_markdown", wiki_dir: str | Path = "wiki") -> None:
    raw_root = Path(raw_dir)
    standards = Path(wiki_dir) / "standards"
    standards.mkdir(parents=True, exist_ok=True)
    for title, source_pdf in STANDARD_SOURCES.items():
        raw_file = raw_root / f"{Path(source_pdf).stem}.md"
        raw_text = raw_file.read_text(encoding="utf-8") if raw_file.exists() else "待解析源文档。"
        (standards / f"{title}.md").write_text(_standard_page(title, source_pdf, raw_text), encoding="utf-8")


def write_synthesis_drafts(wiki_dir: str | Path = "wiki") -> None:
    root = Path(wiki_dir)
    synthesis = root / "synthesis"
    synthesis.mkdir(parents=True, exist_ok=True)
    for title in ["工具选型决策树", "风险评估矩阵", "常见失败原因"]:
        (synthesis / f"{title}.md").write_text(_simple_page(title, "synthesis"), encoding="utf-8")


def write_index_pages(wiki_dir: str | Path = "wiki") -> None:
    root = Path(wiki_dir)
    root.mkdir(parents=True, exist_ok=True)
    links = []
    for path in sorted(root.rglob("*.md")):
        if path.name in {"index.md", "overview.md", "log.md"}:
            continue
        links.append(f"- [[{path.stem}]]")
    (root / "index.md").write_text("# Wiki 总目录\n\n" + "\n".join(links) + "\n", encoding="utf-8")
    (root / "overview.md").write_text("# Wiki 总览\n\n本 Wiki 由源 PDF 编译生成，当前页面为最小可运行草稿。\n", encoding="utf-8")
    (root / "log.md").write_text(f"# 构建与维护日志\n\n- {datetime.now():%Y-%m-%d %H:%M:%S} 最小构建完成。\n", encoding="utf-8")


def _standard_page(title: str, source_pdf: str, raw_text: str) -> str:
    if title == "打捞工具目录":
        body = _fishing_tools_standard(source_pdf, raw_text)
    elif title == "解卡操作规程":
        body = _workover_standard(source_pdf, raw_text)
    elif title == "水平井特殊工艺":
        body = _horizontal_standard(source_pdf, raw_text)
    else:
        body = _generic_standard(source_pdf, raw_text)
    return f"""---
title: {title}
source_pdf: {source_pdf}
doc_type: standard
extracted_at: {datetime.now():%Y-%m-%d %H:%M:%S}
---

# {title}

{body}

## 相关页面
- [[工具选型决策树]]
- [[风险评估矩阵]]
"""


def _generic_standard(source_pdf: str, raw_text: str) -> str:
    return "\n\n".join(
        [
            "## 适用范围\n" + _evidence_block(source_pdf, raw_text, ["1范围", "1 范围", "范围"], 8),
            "## 关键条款摘录\n" + _evidence_block(source_pdf, raw_text, ["技术要求", "施工准备", "施工设计"], 20),
            "## 注意事项与禁忌\n" + _bullet_hits(raw_text, ["不应", "不得", "应", "宜"], 12),
        ]
    )


def _fishing_tools_standard(source_pdf: str, raw_text: str) -> str:
    return "\n\n".join(
        [
            "## 适用范围\n" + _evidence_block(source_pdf, raw_text, ["1范围", "1 范围"], 5),
            "## 工具分类\n" + _evidence_block(source_pdf, raw_text, ["4.1", "打捞工具按产品类型"], 8),
            "## 型号命名\n" + _evidence_block(source_pdf, raw_text, ["4.2.1打捞矛", "4.2.2打捞筒", "4.2.3打捞公锥"], 20),
            "## 工具与适用条件\n" + _tool_table(raw_text),
            "## 技术要求\n" + _evidence_block(source_pdf, raw_text, ["5.1打捞矛", "5.2打捞筒", "5.3打捞公锥"], 36),
            "## 强制复核点\n" + _bullet_hits(raw_text, ["应符合", "应进行", "不应", "许用拉力", "许用扭矩", "正常循环"], 14),
        ]
    )


def _workover_standard(source_pdf: str, raw_text: str) -> str:
    return "\n\n".join(
        [
            "## 适用范围\n" + _evidence_block(source_pdf, raw_text, ["1范围", "1 范围"], 6),
            "## 施工设计与准备\n" + _evidence_block(source_pdf, raw_text, ["4施工设计", "5施工准备", "5.1资料准备"], 18),
            "## 解卡作业流程\n" + _evidence_block(source_pdf, raw_text, ["6解卡作业", "6.1", "6.2震击法", "6.5套、磨铣法", "6.6浸泡法"], 48),
            "## 打捞作业流程\n" + _evidence_block(source_pdf, raw_text, ["7打捞作业", "7.2", "7.3打捞钻具", "7.5打捞作业其他要求"], 36),
            "## 常用管柱组合\n" + _bullet_hits(raw_text, ["组合", "打捞工具", "安全接头", "震击器", "套铣", "磨铣"], 18),
            "## 安全与资料录取\n" + _evidence_block(source_pdf, raw_text, ["9健康", "10资料", "解卡作业主要数据资料", "打捞作业主要数据资料"], 36),
            "## 关键禁忌\n" + _bullet_hits(raw_text, ["不应", "不得", "应暂停", "不应超载荷", "不应猛提"], 12),
        ]
    )


def _horizontal_standard(source_pdf: str, raw_text: str) -> str:
    return "\n\n".join(
        [
            "## 适用范围\n" + _evidence_block(source_pdf, raw_text, ["1范围", "1 范围"], 6),
            "## 施工设计要求\n" + _evidence_block(source_pdf, raw_text, ["4施工设计要求", "施工设计应"], 18),
            "## 解卡方法选择\n" + _evidence_block(source_pdf, raw_text, ["5.1解卡方法", "5.2解卡方法的选择"], 34),
            "## 水平井打捞方法\n" + _evidence_block(source_pdf, raw_text, ["6打捞方法", "6.2打捞方法的选择", "6.5施工步骤"], 34),
            "## 冲砂方法\n" + _evidence_block(source_pdf, raw_text, ["7冲砂方法", "7.4管柱冲砂", "7.5连续油管冲砂"], 46),
            "## 水平井特殊要求\n" + _bullet_hits(raw_text, ["水平井段", "斜井段", "可退工具", "携砂", "扶正器", "不大于", "不小于"], 18),
            "## 质量安全要求\n" + _evidence_block(source_pdf, raw_text, ["8质量要求", "9安全、环境控制要求", "10资料"], 28),
        ]
    )


def _evidence_block(source_pdf: str, raw_text: str, anchors: Iterable[str], max_lines: int) -> str:
    blocks: list[str] = []
    for anchor in anchors:
        snippet, page = _snippet_after(raw_text, anchor, max_lines=max_lines)
        if not snippet:
            continue
        blocks.append(
            f"> 来源：{source_pdf}，第 {page or '待复核'} 页，定位：{anchor}\n>\n"
            + "\n".join(f"> {line}" for line in snippet.splitlines())
        )
    return "\n\n".join(blocks) if blocks else "> 未提取到对应条款，需人工复核。"


def _snippet_after(raw_text: str, anchor: str, *, max_lines: int) -> tuple[str, int | None]:
    lines = raw_text.splitlines()
    page: int | None = None
    current_page: int | None = None
    for index, line in enumerate(lines):
        marker = re.search(r"<!--\s*page:(\d+)\s*-->", line)
        if marker:
            current_page = int(marker.group(1))
        if anchor in _normalize_line(line):
            page = current_page
            selected: list[str] = []
            for follow in lines[index : index + max_lines]:
                cleaned = follow.strip()
                if not cleaned or cleaned.startswith("---") or cleaned.startswith("<!--"):
                    continue
                selected.append(cleaned)
            return "\n".join(selected[:max_lines]), page
    return "", None


def _normalize_line(line: str) -> str:
    return re.sub(r"\s+", "", line)


def _bullet_hits(raw_text: str, keywords: Iterable[str], limit: int) -> str:
    found: list[str] = []
    current_page: int | None = None
    for line in raw_text.splitlines():
        marker = re.search(r"<!--\s*page:(\d+)\s*-->", line)
        if marker:
            current_page = int(marker.group(1))
            continue
        cleaned = line.strip()
        if len(cleaned) < 8:
            continue
        if any(keyword in cleaned for keyword in keywords):
            suffix = f"（第 {current_page} 页）" if current_page else ""
            found.append(f"- {cleaned}{suffix}")
        if len(found) >= limit:
            break
    return "\n".join(found) if found else "- 未提取到，需人工复核。"


def _tool_table(raw_text: str) -> str:
    tool_keywords = {
        "打捞矛": ["打捞矛", "内捞", "倒扣式", "可退式"],
        "打捞筒": ["打捞筒", "外捞", "卡瓦", "可退式"],
        "打捞公锥": ["公锥", "内孔", "造扣", "大头公锥"],
        "打捞母锥": ["母锥", "外部", "造扣"],
    }
    rows = ["| 工具 | 适用线索 | 关键要求 |", "| --- | --- | --- |"]
    for tool, keywords in tool_keywords.items():
        lines = [line.strip() for line in raw_text.splitlines() if any(keyword in line for keyword in keywords)]
        summary = "；".join(lines[:3])[:160] or "需人工复核"
        requirement = "；".join(line.strip() for line in lines if any(k in line for k in ["应", "不应", "许用", "硬度"]) )[:160]
        rows.append(f"| {tool} | {summary} | {requirement or '需结合规格表复核'} |")
    return "\n".join(rows)


def _simple_page(title: str, doc_type: str) -> str:
    return f"---\ntitle: {title}\ndoc_type: {doc_type}\n---\n\n# {title}\n\n待基于 Wiki 内容进一步编译。\n"
