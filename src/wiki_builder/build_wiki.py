"""Minimal offline Wiki build orchestrator."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    from .case_splitter import write_cases
    from .pdf_parser import parse_reference_dir
    from .wiki_writer import write_index_pages, write_standard_drafts, write_synthesis_drafts
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from src.wiki_builder.case_splitter import write_cases
    from src.wiki_builder.pdf_parser import parse_reference_dir
    from src.wiki_builder.wiki_writer import write_index_pages, write_standard_drafts, write_synthesis_drafts


def build_wiki(reference_dir: str = "reference", raw_dir: str = "data/raw_markdown", wiki_dir: str = "wiki") -> None:
    parse_reference_dir(reference_dir, raw_dir)
    write_standard_drafts(raw_dir, wiki_dir)
    case_raw = Path(raw_dir) / "钻具断落事故.md"
    if case_raw.exists():
        write_cases(case_raw, Path(wiki_dir) / "cases")
    write_synthesis_drafts(wiki_dir)
    write_index_pages(wiki_dir)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reference-dir", default="reference")
    parser.add_argument("--raw-dir", default="data/raw_markdown")
    parser.add_argument("--wiki-dir", default="wiki")
    args = parser.parse_args()
    build_wiki(args.reference_dir, args.raw_dir, args.wiki_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
