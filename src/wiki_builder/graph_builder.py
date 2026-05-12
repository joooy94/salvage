"""Build a simple Wiki wikilink graph."""

from __future__ import annotations

import argparse
import json
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
    nodes = []
    edges = []
    for page in sorted(root.rglob("*.md")):
        title = page.stem
        nodes.append({"id": title, "path": page.as_posix()})
        for link in extract_wikilinks(page.read_text(encoding="utf-8")):
            edges.append({"source": title, "target": link})
    graph = {"nodes": nodes, "edges": edges}
    target = out / "graph.json"
    target.write_text(json.dumps(graph, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "graph.html").write_text("<!doctype html><meta charset='utf-8'><pre id='graph'></pre><script>fetch('graph.json').then(r=>r.json()).then(j=>graph.textContent=JSON.stringify(j,null,2))</script>", encoding="utf-8")
    return target


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--wiki-dir", default="wiki")
    parser.add_argument("--graph-dir", default="graph")
    args = parser.parse_args()
    print(build_graph(args.wiki_dir, args.graph_dir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
