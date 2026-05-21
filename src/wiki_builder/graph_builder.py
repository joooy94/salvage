"""Build a simple Wiki wikilink graph."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

try:
    from src.wiki_loader import extract_wikilinks
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from src.wiki_loader import extract_wikilinks


def build_graph(wiki_dir: str | Path = "wiki", graph_dir: str | Path = "graph") -> Path:
    root = Path(wiki_dir)
    out = Path(graph_dir)
    out.mkdir(parents=True, exist_ok=True)
    nodes: list[dict] = []
    edges: list[dict] = []
    aliases: dict[str, str] = {}
    for page in sorted(root.rglob("*.md")):
        rel = page.relative_to(root).as_posix()
        title = page.stem
        node_id = rel
        category = page.parent.relative_to(root).as_posix() if page.parent != root else "root"
        text = page.read_text(encoding="utf-8", errors="ignore")
        metadata_title = _frontmatter_title(text) or title
        nodes.append(
            {
                "id": node_id,
                "label": metadata_title,
                "title": metadata_title,
                "path": rel,
                "category": category,
                "type": _node_type(category),
                "size": max(1, len(text) // 1200),
            }
        )
        aliases[title] = node_id
        aliases[metadata_title] = node_id
        aliases[rel] = node_id

    for page in sorted(root.rglob("*.md")):
        rel = page.relative_to(root).as_posix()
        text = page.read_text(encoding="utf-8", errors="ignore")
        for link in extract_wikilinks(text):
            target = _resolve_link(link, aliases)
            edges.append({"source": rel, "target": target, "label": "wikilink", "type": "wikilink"})
        for target in _extract_path_refs(text, aliases):
            edges.append({"source": rel, "target": target, "label": "引用", "type": "reference"})

    nodes_by_id = {node["id"]: node for node in nodes}
    for edge in edges:
        if edge["target"] not in nodes_by_id:
            nodes_by_id[edge["target"]] = {
                "id": edge["target"],
                "label": Path(edge["target"]).stem,
                "title": Path(edge["target"]).stem,
                "path": "",
                "category": "external",
                "type": "missing",
                "size": 1,
            }
    nodes = sorted(nodes_by_id.values(), key=lambda item: (item["category"], item["label"]))
    edges = _dedupe_edges(edges)
    graph = {"nodes": nodes, "edges": edges}
    target = out / "graph.json"
    target.write_text(json.dumps(graph, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "graph.html").write_text("<!doctype html><meta charset='utf-8'><pre id='graph'></pre><script>fetch('graph.json').then(r=>r.json()).then(j=>graph.textContent=JSON.stringify(j,null,2))</script>", encoding="utf-8")
    return target


def _frontmatter_title(text: str) -> str:
    match = re.search(r"^---\s*\n(.*?)\n---", text, flags=re.DOTALL)
    if not match:
        return ""
    title = re.search(r"^title:\s*(.+)$", match.group(1), flags=re.MULTILINE)
    return title.group(1).strip().strip('"') if title else ""


def _node_type(category: str) -> str:
    if category.startswith("standards"):
        return "standard"
    if category.startswith("cases"):
        return "case"
    if category.startswith("synthesis"):
        return "synthesis"
    if category.startswith("generated_plans"):
        return "plan"
    if category.startswith("tools"):
        return "tool"
    if category.startswith("procedures"):
        return "procedure"
    return category or "root"


def _resolve_link(link: str, aliases: dict[str, str]) -> str:
    clean = link.split("#", 1)[0].strip()
    if clean in aliases:
        return aliases[clean]
    if clean.endswith(".md") and clean in aliases:
        return aliases[clean]
    return clean


def _extract_path_refs(text: str, aliases: dict[str, str]) -> list[str]:
    refs = []
    for raw in re.findall(r"\b(?:standards|cases|synthesis|generated_plans|tools|procedures)/[^\s，。；）)]+?\.md", text):
        if raw in aliases:
            refs.append(aliases[raw])
    return refs


def _dedupe_edges(edges: list[dict]) -> list[dict]:
    seen = set()
    result = []
    for edge in edges:
        key = (edge["source"], edge["target"], edge.get("type", ""))
        if key in seen or edge["source"] == edge["target"]:
            continue
        seen.add(key)
        result.append(edge)
    return sorted(result, key=lambda item: (item["source"], item["target"], item.get("type", "")))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--wiki-dir", default="wiki")
    parser.add_argument("--graph-dir", default="graph")
    args = parser.parse_args()
    print(build_graph(args.wiki_dir, args.graph_dir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
