"""Semantic Wiki lint scaffold.

This module is intentionally importable without API keys. Real LLM-backed
checks can be added behind ``lint_wiki`` without changing callers.
"""

from __future__ import annotations

import argparse
from pathlib import Path


def lint_wiki(wiki_dir: str | Path = "wiki") -> list[str]:
    root = Path(wiki_dir)
    issues: list[str] = []
    for page in root.rglob("*.md"):
        text = page.read_text(encoding="utf-8")
        if "doc_type: standard" in text and "页码待复核" in text:
            issues.append(f"standard page needs source page review: {page}")
        if "doc_type: case" in text and "待人工复核" in text:
            issues.append(f"case page needs manual review: {page}")
    return issues


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--wiki-dir", default="wiki")
    args = parser.parse_args()
    issues = lint_wiki(args.wiki_dir)
    print("OK" if not issues else "\n".join(issues))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
