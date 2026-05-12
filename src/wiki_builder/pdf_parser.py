"""PDF to Markdown conversion using MarkItDown with local fallbacks."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Optional


@dataclass(frozen=True)
class ParseResult:
    source_pdf: Path
    output_markdown: Path
    parser: str
    ok: bool
    error: Optional[str] = None


def parse_pdf(pdf_path: str | Path, output_dir: str | Path = "data/raw_markdown") -> ParseResult:
    source = Path(pdf_path)
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)
    target = output_root / f"{source.stem}.md"

    errors: list[str] = []
    text = ""
    parser = "none"

    for name, parser_fn in (
        ("markitdown", _parse_with_markitdown),
        ("pymupdf", _parse_with_pymupdf),
        ("rapidocr", _parse_with_rapidocr),
    ):
        try:
            candidate = parser_fn(source)
            if _is_useful_text(candidate):
                text = candidate
                parser = name
                break
            errors.append(f"{name} returned low-quality text")
        except Exception as error:
            errors.append(f"{name} failed: {error}")

    if not text:
        message = "; ".join(errors)
        target.write_text(_failure_markdown(source, message), encoding="utf-8")
        return ParseResult(source, target, "none", False, message)

    target.write_text(_wrap_markdown(source, text, parser), encoding="utf-8")
    return ParseResult(source, target, parser, True)


def parse_reference_dir(
    reference_dir: str | Path = "reference",
    output_dir: str | Path = "data/raw_markdown",
) -> List[ParseResult]:
    reference_root = Path(reference_dir)
    return [parse_pdf(pdf, output_dir) for pdf in iter_pdfs(reference_root)]


def iter_pdfs(reference_dir: str | Path) -> Iterable[Path]:
    return sorted(Path(reference_dir).glob("*.pdf"))


def _parse_with_markitdown(pdf_path: Path) -> str:
    from markitdown import MarkItDown

    converter = MarkItDown()
    result = converter.convert(str(pdf_path))
    text = getattr(result, "text_content", None) or getattr(result, "markdown", None)
    if not text:
        raise ValueError("MarkItDown returned empty content")
    return str(text)


def _parse_with_pymupdf(pdf_path: Path) -> str:
    import fitz

    chunks: List[str] = []
    with fitz.open(pdf_path) as doc:
        for index, page in enumerate(doc, start=1):
            text = page.get_text("text").strip()
            chunks.append(f"\n\n<!-- page:{index} -->\n\n{text}\n")
    output = "\n".join(chunks).strip()
    if not output:
        raise ValueError("PyMuPDF returned empty content")
    return output


def _parse_with_rapidocr(pdf_path: Path) -> str:
    import fitz
    import numpy as np
    from rapidocr_onnxruntime import RapidOCR

    engine = RapidOCR()
    chunks: List[str] = []
    with fitz.open(pdf_path) as doc:
        for index, page in enumerate(doc, start=1):
            text = page.get_text("text").strip()
            if len(text) < 50:
                pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
                image = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
                result, _elapsed = engine(image)
                lines = [line[1].strip() for line in result or [] if len(line) > 1 and line[1].strip()]
                text = "\n".join(lines)
            chunks.append(f"\n\n<!-- page:{index} -->\n\n{text}\n")
    output = "\n".join(chunks).strip()
    if not output:
        raise ValueError("RapidOCR returned empty content")
    return output


def _is_useful_text(text: str) -> bool:
    compact = "".join(ch for ch in text if not ch.isspace())
    if len(compact) < 1000:
        return False
    watermark = "公众号：规范标准库"
    if compact.count(watermark) >= 5 and len(compact.replace(watermark, "")) < 1000:
        return False
    return True


def _wrap_markdown(source: Path, text: str, parser: str) -> str:
    extracted_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return (
        "---\n"
        f"source_pdf: {source.name}\n"
        f"parser: {parser}\n"
        f"extracted_at: {extracted_at}\n"
        "---\n\n"
        f"# {source.stem}\n\n"
        f"{text.strip()}\n"
    )


def _failure_markdown(source: Path, error: str) -> str:
    extracted_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return (
        "---\n"
        f"source_pdf: {source.name}\n"
        "parser: none\n"
        f"extracted_at: {extracted_at}\n"
        "parse_failed: true\n"
        "---\n\n"
        f"# {source.stem}\n\n"
        "PDF 解析失败，需要人工复核。\n\n"
        f"> {error}\n"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Convert reference PDFs to raw Markdown.")
    parser.add_argument("--reference-dir", default="reference")
    parser.add_argument("--output-dir", default="data/raw_markdown")
    args = parser.parse_args()

    results = parse_reference_dir(args.reference_dir, args.output_dir)
    for result in results:
        status = "OK" if result.ok else "FAIL"
        print(f"[{status}] {result.source_pdf} -> {result.output_markdown} ({result.parser})")
        if result.error:
            print(f"  {result.error}")
    return 0 if all(result.ok for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
