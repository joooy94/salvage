"""Zero-LLM structural checks for the Markdown Wiki."""

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


def check_wiki(wiki_dir: str | Path = "wiki") -> list[str]:
    root = Path(wiki_dir)
    issues: list[str] = []
    for name in ["index.md", "overview.md", "log.md"]:
        if not (root / name).exists():
            issues.append(f"missing {name}")
    if len(list((root / "standards").glob("*.md"))) != 3:
        issues.append("standards page count is not 3")
    case_pages = [p for p in (root / "cases").glob("*.md")]
    if len(case_pages) != 15:
        issues.append("case page count is not 15")
    manifest_path = root / "cases" / "case_manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if len(manifest) != 15:
            issues.append("case_manifest.json count is not 15")
        for item in manifest:
            if not Path(item.get("wiki_file", "")).exists():
                issues.append(f"manifest target missing: {item.get('wiki_file')}")
    else:
        issues.append("missing case_manifest.json")
    for page in root.rglob("*.md"):
        if not page.read_text(encoding="utf-8").strip():
            issues.append(f"empty page: {page}")
    titles = {p.stem for p in root.rglob("*.md")}
    for page in root.rglob("*.md"):
        for link in extract_wikilinks(page.read_text(encoding="utf-8")):
            if link not in titles:
                issues.append(f"broken wikilink in {page}: [[{link}]]")
    return issues


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--wiki-dir", default="wiki")
    args = parser.parse_args()
    issues = check_wiki(args.wiki_dir)
    print("OK" if not issues else "\n".join(issues))
    return 0 if not issues else 1


if __name__ == "__main__":
    raise SystemExit(main())
