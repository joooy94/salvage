"""Command line entry point for build, solve, and query modes."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

try:
    from .graph import query_wiki_or_solve, solve_accident
except ImportError:
    if __package__ is None or __package__ == "":
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from src.graph import query_wiki_or_solve, solve_accident


def _print_json(data: Any) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2))


def _run_build() -> int:
    builder = Path("src/wiki_builder/build_wiki.py")
    if builder.exists():
        return subprocess.call([sys.executable, str(builder)])
    print("Wiki builder is not available yet. Worker 1 owns the offline Wiki layer.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="钻具落断事故处置系统 CLI")
    parser.add_argument("--mode", choices=["build", "solve", "query"], required=True)
    parser.add_argument("--description", default="", help="事故描述，用于 solve 模式")
    parser.add_argument("--question", default="", help="查询问题，用于 query 模式")
    parser.add_argument("--wiki-dir", default="wiki")
    parser.add_argument("--outputs-dir", default="outputs")
    parser.add_argument("--no-archive", action="store_true")
    args = parser.parse_args(argv)

    if args.mode == "build":
        return _run_build()

    if args.mode == "solve":
        description = args.description or sys.stdin.read().strip()
        if not description:
            parser.error("--description or stdin content is required for --mode solve")
        result = solve_accident(
            description,
            wiki_dir=args.wiki_dir,
            outputs_dir=args.outputs_dir,
            archive=not args.no_archive,
        )
        _print_json(
            {
                "accident": result.get("accident"),
                "confidence_score": result.get("confidence_score"),
                "output_path": result.get("output_path"),
                "final_plan": result.get("final_plan"),
                "evidence": result.get("evidence", []),
            }
        )
        return 0

    if args.mode == "query":
        question = args.question or sys.stdin.read().strip()
        if not question:
            parser.error("--question or stdin content is required for --mode query")
        result = query_wiki_or_solve(question, wiki_dir=args.wiki_dir)
        _print_json(
            {
                "answer": result.get("final_plan"),
                "confidence_score": result.get("confidence_score"),
                "evidence": result.get("evidence", []),
                "wiki_pages_used": result.get("wiki_pages_used", []),
            }
        )
        return 0

    parser.error("Unsupported mode")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
