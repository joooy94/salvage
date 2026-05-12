"""Helpers for reading and writing the persistent Markdown Wiki."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]+)?(?:\|[^\]]+)?\]\]")


@dataclass(frozen=True)
class WikiPage:
    path: Path
    title: str
    content: str
    metadata: Dict[str, Any]

    @property
    def relative_path(self) -> str:
        return self.path.as_posix()


def resolve_wiki_dir(wiki_dir: str | Path = "./wiki") -> Path:
    return Path(wiki_dir).expanduser().resolve()


def parse_front_matter(content: str) -> tuple[Dict[str, Any], str]:
    if not content.startswith("---\n"):
        return {}, content
    end = content.find("\n---\n", 4)
    if end == -1:
        return {}, content
    raw = content[4:end].strip()
    body = content[end + 5 :]
    metadata: Dict[str, Any] = {}
    for line in raw.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        metadata[key.strip()] = _parse_scalar(value.strip())
    return metadata, body


def _parse_scalar(value: str) -> Any:
    if not value:
        return ""
    if value.startswith("[") and value.endswith("]"):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return [item.strip() for item in value[1:-1].split(",") if item.strip()]
    if value.lower() in {"true", "false"}:
        return value.lower() == "true"
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        return value.strip('"').strip("'")


def make_front_matter(metadata: Dict[str, Any]) -> str:
    lines = ["---"]
    for key, value in metadata.items():
        if isinstance(value, (list, dict)):
            rendered = json.dumps(value, ensure_ascii=False)
        else:
            rendered = str(value)
        lines.append(f"{key}: {rendered}")
    lines.append("---")
    return "\n".join(lines) + "\n\n"


def page_title_from_content(path: Path, content: str) -> str:
    metadata, body = parse_front_matter(content)
    if metadata.get("title"):
        return str(metadata["title"])
    for line in body.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return path.stem


def iter_wiki_markdown(wiki_dir: str | Path = "./wiki") -> Iterable[Path]:
    root = resolve_wiki_dir(wiki_dir)
    if not root.exists():
        return []
    return sorted(path for path in root.rglob("*.md") if path.is_file())


def load_page(path: str | Path, wiki_dir: str | Path = "./wiki") -> WikiPage:
    root = resolve_wiki_dir(wiki_dir)
    absolute = Path(path)
    if not absolute.is_absolute():
        parts = absolute.parts
        if parts and parts[0] == "wiki":
            absolute = Path(*parts[1:])
        absolute = root / absolute
    content = absolute.read_text(encoding="utf-8")
    metadata, _body = parse_front_matter(content)
    title = page_title_from_content(absolute, content)
    try:
        relative = absolute.relative_to(root)
    except ValueError:
        relative = absolute
    return WikiPage(path=relative, title=title, content=content, metadata=metadata)


def load_all_pages(wiki_dir: str | Path = "./wiki") -> List[WikiPage]:
    root = resolve_wiki_dir(wiki_dir)
    pages: List[WikiPage] = []
    for path in iter_wiki_markdown(root):
        pages.append(load_page(path, root))
    return pages


def load_all_cases(wiki_dir: str | Path = "./wiki") -> str:
    return "\n\n".join(page.content for page in load_all_pages(wiki_dir) if page.path.as_posix().startswith("cases/"))


def load_standards(wiki_dir: str | Path = "./wiki") -> str:
    return "\n\n".join(page.content for page in load_all_pages(wiki_dir) if page.path.as_posix().startswith("standards/"))


def load_synthesis(wiki_dir: str | Path = "./wiki") -> str:
    return "\n\n".join(page.content for page in load_all_pages(wiki_dir) if page.path.as_posix().startswith("synthesis/"))


def load_index(wiki_dir: str | Path = "./wiki") -> str:
    root = resolve_wiki_dir(wiki_dir)
    path = root / "index.md"
    return path.read_text(encoding="utf-8") if path.exists() else ""


def search_wiki_snippets(
    terms: Iterable[str],
    wiki_dir: str | Path = "./wiki",
    *,
    categories: Iterable[str] | None = None,
    limit: int = 6,
) -> List[Dict[str, Any]]:
    """Return small evidence snippets from Wiki pages.

    This is a deterministic, cheap helper for the first version. It does not
    replace LLM reasoning; it only gives agents concrete quoted Wiki text to
    cite.
    """

    term_list = [term for term in terms if term]
    category_prefixes = tuple(categories or [])
    candidates: List[tuple[int, int, Dict[str, Any]]] = []
    for page in load_all_pages(wiki_dir):
        rel = page.path.as_posix()
        if category_prefixes and not rel.startswith(category_prefixes):
            continue
        _metadata, body = parse_front_matter(page.content)
        lines = body.splitlines()
        for index, line in enumerate(lines):
            cleaned = line.strip("> ").strip()
            if (
                not cleaned
                or cleaned.startswith("来源：")
                or cleaned.startswith("#")
                or cleaned.startswith("- [[")
                or cleaned == "## 相关页面"
            ):
                continue
            matched_terms = [term for term in term_list if term in line]
            if not matched_terms:
                continue
            snippet = _nearby_lines(lines, index)
            source_line = _nearest_source_line(lines, index)
            item = {
                "source_type": str(page.metadata.get("doc_type", "wiki")),
                "source_page": rel,
                "source_pdf": str(page.metadata.get("source_pdf", "")),
                "page_no": _page_no_from_source_line(source_line),
                "clause": _clause_from_line(line),
                "quote": snippet,
                "summary": f"{page.title}：{cleaned[:80]}",
            }
            candidates.append((_snippet_score(cleaned, matched_terms, item), index, item))

    candidates.sort(key=lambda item: (-item[0], item[1]))
    results: List[Dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for _score, _index, item in candidates:
        key = (str(item.get("source_page", "")), str(item.get("summary", "")))
        if key in seen:
            continue
        seen.add(key)
        results.append(item)
        if len(results) >= limit:
            break
    return results


def save_new_case(content: str, wiki_dir: str | Path = "./wiki", filename: str | None = None) -> Path:
    target_name = filename or "生成案例_待命名.md"
    return save_page(Path("generated_plans") / target_name, content, wiki_dir)


def save_page(
    relative_path: str | Path,
    content: str,
    wiki_dir: str | Path = "./wiki",
    *,
    overwrite: bool = True,
) -> Path:
    root = resolve_wiki_dir(wiki_dir)
    target = root / relative_path
    if target.exists() and not overwrite:
        raise FileExistsError(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return target


def extract_wikilinks(content: str) -> List[str]:
    return sorted({match.strip() for match in WIKILINK_RE.findall(content) if match.strip()})


def find_page_by_title(title: str, wiki_dir: str | Path = "./wiki") -> Optional[WikiPage]:
    normalized = title.strip()
    for page in load_all_pages(wiki_dir):
        if page.title == normalized or page.path.stem == normalized:
            return page
    return None


def _nearby_lines(lines: List[str], index: int, radius: int = 2) -> str:
    start = max(0, index - radius)
    end = min(len(lines), index + radius + 1)
    selected = [line.strip("> ").strip() for line in lines[start:end] if line.strip()]
    return "\n".join(selected)[:700]


def _nearest_source_line(lines: List[str], index: int) -> str:
    for cursor in range(index, max(-1, index - 80), -1):
        line = lines[cursor].strip("> ").strip()
        if line.startswith("来源："):
            return line
    return ""


def _page_no_from_source_line(line: str) -> Optional[int]:
    match = re.search(r"第\s*(\d+)\s*页", line)
    return int(match.group(1)) if match else None


def _clause_from_line(line: str) -> Optional[str]:
    cleaned = line.strip("> ").strip()
    match = re.match(r"([0-9]+(?:\.[0-9]+){0,3})", cleaned)
    return match.group(1) if match else None


def _snippet_score(line: str, matched_terms: List[str], item: Dict[str, Any]) -> int:
    score = sum(max(2, len(term)) for term in matched_terms)
    if item.get("clause"):
        score += 10
    if item.get("page_no"):
        score += 2
    if any(word in line for word in ["应", "不应", "宜", "施工步骤", "工艺要求", "解卡顺序", "可退工具"]):
        score += 8
    if any(word in line for word in ["分类", "型号命名", "按产品类型", "管柱组合"]):
        score += 4
    if any(word in line for word in ["本标准规定", "本文件描述", "适用于", "规范性引用文件"]):
        score -= 8
    if "相关页面" in line:
        score -= 20
    return score
